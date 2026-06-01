# Cierre de apuestas → Email → Teams (sin premium) — diseño

**Fecha:** 2026-06-01
**Autor:** Ignacio Borrajo (con Claude)
**Estado:** propuesto, pendiente de ejecutar el plan asociado

---

## 1. Motivación

La feature original `Cierre de apuestas → Teams` (spec [2026-06-01-cierre-apuestas-teams-design.md](./2026-06-01-cierre-apuestas-teams-design.md), implementada en `main` hasta el commit `1e86e88`) usaba tres acciones HTTP de Power Automate para sondear Django y publicar el PDF en Teams. Al guardar el flow descubrimos que **el conector HTTP de Power Automate es premium** (≈ €12/usuario/mes) y la organización no quiere pagar premium. Microsoft Graph + Entra ID tampoco es viable (IT no autoriza el registro de app).

Reescribimos la integración para usar **solo conectores estándar de Power Automate**. La idea:

1. **Lado servidor**: un *scheduled task* de PythonAnywhere (plan de pago, Hacker $5/mes) ejecuta cada 10 min un comando Django que envía un email con el PDF adjunto por cada cierre pendiente.
2. **Lado Power Automate**: un flow con trigger **"When a new email arrives (V3)"** (Outlook 365 — estándar, no premium) recibe el email, sube el adjunto a OneDrive con **Create file** (estándar), crea share link con **Create share link** (estándar) y publica en el chat de grupo con **Post message** (estándar).

Cero conectores premium en ambos lados.

## 2. Restricciones nuevas y aceptadas

- **PythonAnywhere paid plan (Hacker $5/mes)**: necesario para:
  - SMTP saliente libre (el plan free solo permite outbound a una whitelist).
  - Múltiples *scheduled tasks* (free permite solo una, diaria).
- **Cuenta de correo "bot"**: IT debe proveer o autorizar una cuenta corporativa desde la que enviar (por ejemplo `porra26-bot@edisa.com`). Fallback aceptable: la cuenta personal de Ignacio con *app password* configurado en MFA.
- **Buzón destino**: dirección donde escucha Power Automate. Lo más simple: el propio Ignacio (o quien sea dueño del flow).

## 3. Decisiones tomadas (sin negociar más)

| Tema | Decisión |
|------|----------|
| Patrón | *Push* desde Django: scheduled task ejecuta management command que envía emails. |
| Trigger en PythonAnywhere | Scheduled task cada 10 min ejecuta `python manage.py send_pending_closures`. |
| Asunto del email | `<prefijo> <slug>` — p. ej. `[Porra26] esp-vs-arg-2026-06-14`. Prefijo configurable, default `[Porra26]`. Power Automate filtra por prefijo. |
| Cuerpo del email | Texto plano corto + PDF adjunto. El texto incluye: equipos, ronda, kickoff y un resumen mínimo (jugadores que han apostado de N). Hace de fallback si el PDF no se ve. |
| Adjunto | `cierre-<slug>.pdf` generado al vuelo con el `build_closing_pdf` existente. |
| Estado | Reusa `BetsClosingReport` tal cual: el service fija `sent_at`, `generated_at`, `attempts` y `last_sha256` como ya hace el endpoint `/pdf`. |
| `cierres-pendientes` API | Se mantiene (utilidad: monitorización vía `curl` con el Bearer token). |
| `/pdf` API | Se mantiene (lo usa el botón "PDF cierre" del gestor). |
| `marcar-enviado` API | **Se elimina** junto con sus tests. La marca la pone el service al enviar el email, no un cliente externo. |
| Auth Bearer del decorador | Se mantiene tal cual; sigue protegiendo `cierres-pendientes` y `/pdf`. |
| Idempotencia | El service comprueba `BetsClosingReport.sent_at`: si está fijado, no-op. Si no, envía y lo fija. |
| Reintentos | Si SMTP falla, no se fija `sent_at` ni `last_sha256`; la siguiente vuelta del cron lo reintenta. `attempts` sí se incrementa en cada intento (visible en la sección "Estado de envíos"). |
| SMTP backend | `django.core.mail.backends.smtp.EmailBackend` con TLS, credenciales en `.env`. |
| Tests | Usan el backend `locmem` de Django (`mail.outbox`). Cero emails reales. |
| Política frente a errores SMTP | El management command captura excepciones por partido y loguea; un mail roto no para los demás. |
| Sin tope de reintentos | No hay max attempts. Si un mail siempre falla, aparecerá con `attempts` creciente y `sent_at = NULL` en la sección "Estado de envíos a Teams"; el gestor lo gestiona desde el admin (puede fijar manualmente `sent_at` para silenciarlo). |

## 4. Arquitectura

```
┌───────────────────────────────────────────────┐    ┌────────────────────────┐
│  porra26.pythonanywhere.com (Hacker plan)     │    │  Outlook 365           │
│                                                │    │  (cuenta destino)      │
│  Scheduled task cada 10 min                    │    │                        │
│   └─ python manage.py send_pending_closures    │    │                        │
│         │                                      │    │                        │
│         ▼                                      │    │                        │
│   For each match pendiente:                    │    │                        │
│     ├─ build_closing_pdf(match) → PDF bytes    │    │                        │
│     ├─ send EmailMessage(...)  ────SMTP TLS───►│    │  📥 Inbox              │
│     │     to: TEAMS_CLOSURE_EMAIL_TO           │    │   [Porra26] esp-vs-arg │
│     │     attachment: cierre-<slug>.pdf        │    │   + PDF adjunto        │
│     └─ on success: BetsClosingReport.sent_at   │    └──────────┬─────────────┘
│                                                │               │
└───────────────────────────────────────────────┘               │ Outlook trigger
                                                                │ (estándar)
                                                                ▼
                                                ┌──────────────────────────┐
                                                │  Power Automate flow     │
                                                │  (todo estándar)         │
                                                │                          │
                                                │  1. When email arrives   │
                                                │     (filter subject)     │
                                                │  2. Apply to each        │
                                                │     attachment:          │
                                                │     ├ OneDrive Create    │
                                                │     │   file              │
                                                │     ├ Create share link  │
                                                │     └ Post message in    │
                                                │       group chat         │
                                                └──────────────────────────┘
```

## 5. Cambios en el código

### 5.1 Nuevo service `competition/services/closing_email.py`

Función única: enviar el email para un match. Idempotente.

```python
def send_closure_email(match: Match) -> BetsClosingReport
```

Comportamiento:

1. Si el match aún no está cerrado (`kickoff − 2h > now()`) → lanza `ValueError("match aún no cerrado")`.
2. Obtiene o crea el `BetsClosingReport` del match.
3. Si `report.sent_at is not None` → retorna el report sin enviar (no-op idempotente).
4. Genera PDF con `build_closing_pdf(match)`.
5. Calcula `sha256` y actualiza `report.attempts += 1`, `generated_at`, `last_sha256` (independientemente del envío).
6. Construye `EmailMessage`:
   - **From**: `settings.DEFAULT_FROM_EMAIL`.
   - **To**: `[settings.TEAMS_CLOSURE_EMAIL_TO]`.
   - **Subject**: `f"{settings.TEAMS_CLOSURE_SUBJECT_PREFIX} {match.teams_slug}"`.
   - **Body**: texto plano con el resumen.
   - **Attachment**: `(f"cierre-{match.teams_slug}.pdf", pdf_bytes, "application/pdf")`.
7. Envía con `message.send(fail_silently=False)`.
8. Si el send tiene éxito: fija `report.sent_at = now()`, crea `AuditLog(action="bets_pdf_emailed")`, devuelve report.
9. Si falla: propaga la excepción (el management command la captura).

### 5.2 Nuevo management command `competition/management/commands/send_pending_closures.py`

Argumentos:

- `--match-id <id>`: envía solo ese match (para pruebas / reintentos manuales). Si no, recorre todos los pendientes.
- `--dry-run`: lista los matches que se enviarían pero no envía.

Lógica:

1. Calcula la lista de matches con `kickoff − 2h ≤ now()` y `(no report) or (report.sent_at is None)`. Mismo criterio que el endpoint `cierres-pendientes`.
2. Para cada uno, captura excepciones individualmente:
   - `try: send_closure_email(m)` → logguea OK.
   - `except Exception as e:` → logguea el error con `match_id` y deja `sent_at = None` (se reintenta en la próxima vuelta).
3. Sale con código 0 incluso si hubo errores (el cron de PythonAnywhere no debe marcar la ejecución como fallida solo porque un email falló; los errores se ven en los logs).

### 5.3 Eliminar `marcar-enviado`

- Quita de `competition/api/views.py` la función `cierre_marcar_enviado`.
- Quita de `competition/api/urls.py` la ruta `cierres/<int:match_id>/marcar-enviado/`.
- Borra de `competition/tests/test_teams_api_endpoints.py` los 6 tests que la cubrían: `test_marcar_enviado_*`.
- Quita los imports que solo servían para ese endpoint (`require_POST`, `_json`, `AuditLog` si no se usa en otra parte de ese fichero — verificar).
- `AuditLog` sigue usándose en el nuevo service para `action="bets_pdf_emailed"`; este sustituye al antiguo `bets_pdf_sent`.

### 5.4 Cambios en settings (`porra26/settings/base.py`)

Añadir al final del fichero:

```python
# Email (SMTP) — usado por el management command `send_pending_closures`.
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = os.getenv("EMAIL_HOST", "")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "porra26@edisa.com")

# Destinatario del email de cierre — buzón donde escucha el flow de Power Automate.
TEAMS_CLOSURE_EMAIL_TO = os.getenv("TEAMS_CLOSURE_EMAIL_TO", "")
TEAMS_CLOSURE_SUBJECT_PREFIX = os.getenv("TEAMS_CLOSURE_SUBJECT_PREFIX", "[Porra26]")
```

En `porra26/settings/test.py`, forzar backend `locmem`:

```python
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
TEAMS_CLOSURE_EMAIL_TO = "test-destino@edisa.com"
TEAMS_CLOSURE_SUBJECT_PREFIX = "[Porra26]"
```

### 5.5 Cambios en `.env.example`

Añadir:

```
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_HOST_USER=porra26-bot@edisa.com
EMAIL_HOST_PASSWORD=
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=porra26-bot@edisa.com
TEAMS_CLOSURE_EMAIL_TO=ignacio.borrajo@edisa.com
TEAMS_CLOSURE_SUBJECT_PREFIX=[Porra26]
```

## 6. Estructura del email

**Asunto**: `[Porra26] esp-vs-arg-2026-06-14` (sin acentos ni espacios — el slug es predecible y Power Automate filtra fácil).

**Body** (texto plano, ASCII-safe en lo razonable):

```
Cierre de apuestas — España vs Argentina

Fase de grupos · Grupo D
Saque: 14 jun 2026, 21:00
Cierre: 14 jun 2026, 19:00

42 de 48 jugadores han apostado.

PDF adjunto con el detalle completo (pronósticos, resumen y clasificación general).

— porra26.pythonanywhere.com
```

**Adjunto**: `cierre-esp-vs-arg-2026-06-14.pdf` (`application/pdf`).

## 7. Power Automate flow (versión email-driven)

`docs/TEAMS_FLOW.md` se reescribe entero con este flujo. Resumen:

1. **Trigger**: *Office 365 Outlook → When a new email arrives (V3)* (estándar):
   - **Folder**: Inbox.
   - **From**: la cuenta bot (filtra por sender exacto).
   - **Subject Filter**: `[Porra26]`.
   - **Include Attachments**: Yes.
   - **Only with Attachments**: Yes.

2. **Apply to each** sobre `Attachments`:
   - **OneDrive Create file**:
     - Folder Path: `/Apps/Porra26/Cierres`.
     - File Name: `Name` del adjunto.
     - File Content: `Content` del adjunto.
   - **OneDrive Create share link**:
     - File Identifier: `Id` del paso anterior.
     - Link Type: View.
     - Link Scope: Organization.
   - **Post message in chat or channel**:
     - Post as: Flow bot.
     - Post in: Group chat.
     - Group chat: seleccionado del desplegable.
     - Message (HTML):
       ```
       📣 <b>Cierre de apuestas</b><br>
       <i>Asunto: @{triggerOutputs()?['body/subject']}</i><br><br>
       📄 <a href="@{outputs('Crear_vínculo_para_compartir')?['body/link/webUrl']}">Descargar PDF de cierre</a>
       ```

3. Configure run after en cada paso: solo si el anterior fue `is successful`.

## 8. Configuración en PythonAnywhere

### 8.1 Plan Hacker

Upgrade desde el panel Account → Plans. Coste $5/mes.

### 8.2 Variables de entorno

Editar `~/apuestas-interna/.env` y añadir todas las `EMAIL_*` y `TEAMS_CLOSURE_*` del ejemplo de §5.5 con valores reales. Recargar la web app.

### 8.3 Scheduled task

Panel **Tasks** → **Create a new scheduled task**:

- Comando:
  ```
  cd ~/apuestas-interna && /home/<user>/.virtualenvs/<venv>/bin/python manage.py send_pending_closures
  ```
- Frecuencia: cada 10 minutos (Hacker plan permite frecuencias minute-level).

### 8.4 Permisos SMTP de la cuenta bot

Para SMTP con Microsoft 365 (`smtp.office365.com:587` con TLS):

- La cuenta necesita **SMTP AUTH habilitado** (IT lo controla a nivel de tenant y por usuario).
- Si la cuenta tiene MFA, generar un **App Password** y usarlo como `EMAIL_HOST_PASSWORD`.
- Si IT no permite SMTP AUTH (cada vez más común), alternativa: usar Gmail SMTP de una cuenta personal con app password, o un servicio transaccional (SendGrid free tier, Brevo free tier, ~100 emails/día).

## 9. Tests

Nuevos ficheros / tests:

### `competition/tests/test_closing_email_service.py`

| Test | Comportamiento esperado |
|------|------------------------|
| `test_send_creates_email_with_pdf_attachment` | Tras llamar al service, `mail.outbox` tiene 1 email; tiene 1 adjunto; mime type `application/pdf`; filename empieza por `cierre-`. |
| `test_send_subject_includes_prefix_and_slug` | Asunto es `[Porra26] esp-vs-arg-2026-06-14` con el slug correcto. |
| `test_send_body_includes_summary` | El body de texto contiene el nombre de los equipos y "N de M han apostado". |
| `test_send_marks_report_and_creates_audit` | Tras enviar, `BetsClosingReport.sent_at` está fijado, `attempts` es 1, `last_sha256` tiene 64 hex; existe un `AuditLog(action="bets_pdf_emailed")`. |
| `test_send_is_idempotent` | Segunda llamada no añade segundo email a `mail.outbox` ni segundo AuditLog. |
| `test_send_raises_if_match_not_closed` | Match con `kickoff` futuro lanza `ValueError`. |
| `test_send_increments_attempts_even_on_smtp_failure` | Con `EMAIL_BACKEND` que lanza, el service propaga; `attempts` se incrementó y `sent_at` sigue None. |

### `competition/tests/test_send_pending_closures_command.py`

| Test | Comportamiento esperado |
|------|------------------------|
| `test_command_sends_for_each_pending_match` | Con 3 matches cerrados sin enviar, `call_command(...)` produce 3 emails en `mail.outbox`. |
| `test_command_skips_already_sent_matches` | Match con `sent_at` no genera email. |
| `test_command_skips_open_matches` | Match aún abierto no genera email. |
| `test_command_continues_on_individual_error` | Si un match falla (mockeamos `send_closure_email` para que lance en uno solo), los demás se envían igual. El comando exit code 0. |
| `test_command_dry_run_does_not_send` | Con `--dry-run`, `mail.outbox` está vacío. |
| `test_command_match_id_filter` | Con `--match-id <id>`, solo se procesa ese match. |

### Tests existentes a eliminar

En `competition/tests/test_teams_api_endpoints.py`, borrar los 7 tests `test_marcar_enviado_*` y el helper `test_marcar_enviado_get_without_auth_returns_401_not_405` (que añadimos en el code review). Total: ~7 tests menos. La suite final debe quedar verde con un count menor.

## 10. Documentación a actualizar

- **`docs/PLAN.md`**: reescribir la Fase 7 explicando que pasamos del patrón HTTP-pull al patrón email-push por el problema de premium connectors.
- **`docs/DEPLOY.md`**: añadir sección 8 con plan Hacker, variables SMTP y scheduled task. La sección 7 (token de Teams) se mantiene porque el `/pdf` endpoint sigue usándolo.
- **`docs/RUNBOOK.md`**: cambiar la entrada "Verificar envíos a Teams" — los partidos en estado ámbar (`attempts > 0, sent_at = NULL`) ahora indican fallo SMTP, no fallo Power Automate. Diagnóstico: revisar los logs del scheduled task en PythonAnywhere (panel Tasks → log file).
- **`docs/TEAMS_FLOW.md`**: reescribir entero (versión email-driven, §7 del spec).

## 11. Fuera de alcance

- No se cambia el modelo `BetsClosingReport` (sigue igual: `match`, `generated_at`, `sent_at`, `attempts`, `last_sha256`, `created_at`).
- No se cambia la UI del gestor (`/competicion/resultados/` con botón "📄 PDF" + sección "Estado de envíos a Teams" siguen iguales).
- No se cambia el PDF en sí (`build_closing_pdf` ni `compute_closing_stats` se tocan).
- No se cambia el endpoint `/pdf` (sigue siendo el origen del PDF para la UI y, eventualmente, para `curl` con Bearer).
- No se cambia el endpoint `cierres-pendientes` (se mantiene como utilidad de monitorización; nadie lo consume desde Power Automate, pero es útil con `curl`).
- No se cambia el decorador `require_teams_api_token` (se mantiene; el Bearer sigue habilitando llamadas externas a los dos endpoints supervivientes).

## 12. Migración / despliegue

1. Mergear el plan asociado en `main`.
2. Implementar y testear.
3. Subir el plan PythonAnywhere a Hacker, configurar variables, crear scheduled task.
4. Confirmar con un envío manual (`python manage.py send_pending_closures --match-id <X>`).
5. Construir el nuevo flow en Power Automate siguiendo el `TEAMS_FLOW.md` reescrito.
6. Borrar el flow viejo (el de HTTP) si quedó alguna versión guardada.
7. Tras el primer envío real exitoso, observar la sección "Estado de envíos a Teams" durante 24 h.

## 13. Riesgos

| Riesgo | Mitigación |
|--------|------------|
| IT no autoriza SMTP AUTH para Office 365. | Plan B documentado: usar un proveedor transaccional gratuito (SendGrid/Brevo) — solo cambia `EMAIL_HOST` y credenciales. |
| El email se cuela en spam de la cuenta destino. | Crear una regla en Outlook que marque mensajes con `[Porra26]` como nunca-spam; documentar en RUNBOOK. |
| Microsoft retira la app password / SMTP AUTH legacy. | Migrar a OAuth2 con `django-anymail` o equivalente (no en alcance ahora). |
| PythonAnywhere scheduled task se desactiva por quota o por error persistente. | RUNBOOK incluye verificación semanal: el gestor mira la sección "Estado de envíos a Teams" cada lunes. |
| El attachment del email se renombra al pasar por Outlook (algunos clientes recodifican). | El flow no depende del nombre del adjunto para nada funcional; el nombre del fichero en OneDrive viene del adjunto, así que se conservará. Aceptable. |
