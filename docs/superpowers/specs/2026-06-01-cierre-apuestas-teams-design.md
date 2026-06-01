# Cierre de apuestas → PDF → Teams — diseño

**Fecha:** 2026-06-01
**Autor:** Ignacio Borrajo (con Claude)
**Estado:** propuesto, pendiente de plan de implementación

---

## 1. Motivación

Cuando se cierra la ventana de apuestas de un partido (`kickoff − 2 h`), las apuestas quedan congeladas en la base de datos pero no hay rastro fuera de la aplicación. Queremos que en el canal interno de Teams de la empresa quede automáticamente un mensaje con un PDF que recoja:

- El partido (equipos, ronda, kickoff, hora de cierre).
- Un breve resumen estadístico (cuántos han apostado, marcador más popular, reparto 1/X/2, sin apostar).
- La tabla completa de pronósticos de todos los jugadores activos.
- La clasificación general en ese momento.

Esto da **auditoría externa** (cualquiera del canal ve el cierre sin acceder a la app) y **ceremonia** (genera conversación antes de cada partido).

## 2. Restricción operativa

La app vive en **PythonAnywhere**, plan free. Implicaciones:

- **Tráfico saliente**: solo a la whitelist de PythonAnywhere. Las URLs de Power Automate (`*.logic.azure.com`) **no** están en la whitelist del plan free, así que **descartamos cualquier patrón push** (que la app llame a Teams o a un Flow).
- **Microsoft Graph / Entra ID**: la organización no concede permisos para registrar una app en Entra ID, así que descartamos esa vía.
- **Disco**: PythonAnywhere ofrece disco escribible, pero preferimos no usarlo (ver §5).
- **Scheduled tasks**: el plan free permite 1 tarea diaria. Reservada para otras cosas; este sistema no la usa.

La única dirección viable es **entrante**: Django expone endpoints y un agente externo los consume.

## 3. Decisiones tomadas en brainstorming

| Tema | Decisión |
|------|----------|
| Arquitectura | *Pull* desde Power Automate: Django expone HTTP, Power Automate sondea cada 10 min. |
| Contenido del PDF | Cabecera + bloque partido + resumen estadístico + tabla de pronósticos + clasificación general. |
| Estado de envíos | Nueva tabla `BetsClosingReport` (1‑1 con `Match`), con `generated_at`, `sent_at`, `attempts`, `last_sha256`. |
| Persistencia del binario | Regenerar al vuelo en cada GET. Sin disco. Determinista porque el partido está cerrado. |
| Capacidades del gestor | Botón "📄 PDF cierre" en página de Resultados + tabla solo-lectura "Estado de envíos a Teams". Reintento manual queda en Django admin (no UI dedicada). |
| Autenticación API | Token Bearer único en variable de entorno `TEAMS_API_TOKEN`. |
| Estilo del PDF | Limpio y funcional con ReportLab (sin libs del sistema; trabaja en plan free). |
| Librería PDF | `reportlab>=4.0`. |
| Despliegue | Documentar Flow en `docs/TEAMS_FLOW.md`; token en `docs/DEPLOY.md` y `docs/RUNBOOK.md`. |

## 4. Arquitectura

```
┌──────────────────────────────┐         ┌──────────────────────────────┐
│  Power Automate              │         │  porra26.pythonanywhere.com   │
│  Scheduled cloud flow        │         │  Django                       │
│  (Recurrence: cada 10 min)   │         │                               │
│                              │         │                               │
│  1. GET cierres-pendientes ──┼────────►│  /api/teams/cierres-          │
│     [Authorization: Bearer]  │         │      pendientes               │
│                              │         │                               │
│  2. Apply to each match:     │         │                               │
│     a. GET …/<id>/pdf ───────┼────────►│  /api/teams/cierres/<id>/pdf  │
│        ← binary application/pdf        │                               │
│     b. Post message in       │         │                               │
│        channel (con adjunto) │         │                               │
│     c. POST …/marcar-enviado ┼────────►│  /api/teams/cierres/<id>/     │
│        (solo si paso b OK)   │         │      marcar-enviado           │
└──────────────────────────────┘         └──────────────────────────────┘
```

**Latencia máxima** cierre → mensaje en Teams: 10 min (intervalo del flow). Aceptable; el cierre ocurre 2 h antes del saque.

**Reintentos**: si Teams falla en el paso b, el flow no llama al paso c (configuración *Run after: succeeded*), el partido reaparece en `/cierres-pendientes` en el siguiente ciclo y se reintenta automáticamente.

**Idempotencia**: el endpoint `/marcar-enviado` admite ser llamado varias veces sin efecto; los endpoints `/pdf` y `/cierres-pendientes` no tienen efectos colaterales relevantes más allá de incrementar `attempts`.

## 5. Modelo de datos

Nueva tabla `BetsClosingReport` en la app `competition`:

```python
class BetsClosingReport(models.Model):
    match = models.OneToOneField(
        Match, on_delete=models.CASCADE, primary_key=True,
        related_name="closing_report"
    )
    generated_at = models.DateTimeField(null=True, blank=True)
    sent_at = models.DateTimeField(null=True, blank=True)
    attempts = models.PositiveSmallIntegerField(default=0)
    last_sha256 = models.CharField(max_length=64, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        indexes = [models.Index(fields=["sent_at"])]
```

- **Creación perezosa**: la fila se crea en el primer `GET /pdf` (vía `get_or_create`) o en el primer `POST /marcar-enviado` (si por algún motivo se llamara antes que al PDF). `GET /cierres-pendientes` es **lectura pura**, no crea filas. No se pre-crean filas por cada match al hacer la migración.
- **`attempts`** se incrementa **en cada GET de `/pdf`** (no solo en envíos exitosos): refleja "veces servido".
- **`last_sha256`**: hash SHA-256 del PDF más reciente. Útil para auditar si distintas regeneraciones difieren (no deberían, salvo que el código del PDF cambie entre versiones).
- **AuditLog**: cada actualización de `sent_at` (de `NULL` a fecha) emite un `AuditLog` con `action="bets_pdf_sent"`, `target_type="match"`, `target_id=<id>`, `payload={"teams_message_id": ...}`.

**No** se añaden campos a `Match`. Toda la información de cierre vive en `BetsClosingReport`.

## 6. Endpoints

Todos bajo el prefijo `/api/teams/`, declarados en `competition/urls.py` con namespace `api`. Decorador `@require_teams_api_token` que admite:

1. Cabecera `Authorization: Bearer <TEAMS_API_TOKEN>` → autenticación de servicio (Power Automate).
2. Usuario con sesión activa y `is_gestor=True` → autenticación de UI (botón de descarga).

Si ninguna condición se cumple: `401 Unauthorized` con `{"detail": "Token inválido o sesión no autorizada"}`. CSRF-exempt (no hay sesión que validar para el caso Bearer; en el caso UI el verbo es GET o POST sin formulario clásico).

### 6.1 `GET /api/teams/cierres-pendientes`

**Criterio de pendiente:**

- `match.kickoff − 2h ≤ now()` (la ventana de cierre ya ha pasado), AND
- (no existe `BetsClosingReport` para el match) OR (`BetsClosingReport.sent_at IS NULL`).

**Respuesta** (HTTP 200, `application/json`):

```json
{
  "matches": [
    {
      "id": 42,
      "slug": "esp-vs-arg-2026-06-14",
      "round": "Fase de grupos",
      "round_id": "groups",
      "group": "D",
      "home": {"code": "ESP", "name": "España"},
      "away": {"code": "ARG", "name": "Argentina"},
      "kickoff": "2026-06-14T21:00:00+02:00",
      "closed_at": "2026-06-14T19:00:00+02:00"
    }
  ]
}
```

- Ordenado por `kickoff` ascendente.
- `slug`: `<home_code>-vs-<away_code>-<YYYY-MM-DD>` en minúsculas. Se usa como nombre del fichero PDF.
- Sin paginación: volumen máximo ≈ 64 (todos los partidos del Mundial).

### 6.2 `GET /api/teams/cierres/<match_id>/pdf`

- **404** si el match no existe o si su `kickoff − 2h > now()` (todavía no cerrado).
- **200** con `Content-Type: application/pdf` y `Content-Disposition: attachment; filename="cierre-<slug>.pdf"`.
- Efectos colaterales (dentro de transacción):
  - `BetsClosingReport.objects.get_or_create(match=match)`.
  - `report.attempts += 1`.
  - `report.generated_at = timezone.now()`.
  - `report.last_sha256 = sha256(pdf_bytes).hexdigest()`.
  - `report.save()`.

Acepta también query param opcional `?download=1` (sin efecto funcional; sirve para que el navegador del gestor fuerce la descarga).

### 6.3 `POST /api/teams/cierres/<match_id>/marcar-enviado`

- **404** si el match no existe.
- Cuerpo opcional `application/json`: `{"teams_message_id": "<id de mensaje de Teams>"}`.
- Si no existe `BetsClosingReport` para el match: lo crea (caso límite: alguien llama directo a este endpoint sin pasar antes por `/pdf`).
- Si `sent_at` ya está fijado: responde `200` con `{"already_sent": true, "sent_at": "..."}` y **no** crea otro AuditLog.
- Si no estaba enviado:
  - `sent_at = now()`.
  - Crea `AuditLog(action="bets_pdf_sent", actor=None, target_type="match", target_id=str(match_id), payload={"teams_message_id": ...})`.
  - Responde `200` con `{"sent_at": "..."}`.

`actor` queda `None` porque la acción la dispara Power Automate, no un usuario.

## 7. Contenido y maquetación del PDF

Generado con ReportLab usando el módulo `platypus` (flowables) sobre un `SimpleDocTemplate`. A4 vertical, márgenes 18 mm. Fuentes built-in (`Helvetica`, `Helvetica-Bold`) — sin descargas externas ni dependencias del sistema.

**Layout, de arriba a abajo:**

1. **Banda superior** (alto ≈ 28 mm): rectángulo con degradado horizontal **naranja (#FF7A00)** → **cyan (#00C2FF)** → **violeta (#7A5AF8)** dibujado directamente sobre el canvas (no es un Flowable trivial; se hace en `onFirstPage`). Sobre la banda, en blanco:
   - Línea 1: `PORRA 26` en `Helvetica-Bold` 18 pt.
   - Línea 2: `Cierre de apuestas` en `Helvetica` 12 pt.

2. **Bloque partido** (≈ 24 mm de altura):
   - `ESP · España  vs  ARG · Argentina` en `Helvetica-Bold` 16 pt.
   - Subtexto en gris: `Fase de grupos · Grupo D · 14 jun 2026, 21:00 · Cierre 19:00`.

   > **Decisión:** se descartan banderas-emoji porque las fuentes built-in de ReportLab no las renderizan. Si en una iteración futura se desean pictogramas, se añadirán PNGs de 24×16 px en `static/flags/<code>.png`.

3. **Resumen** (4 bullets, `Helvetica` 10 pt):
   - `42 de 48 jugadores han apostado`
   - `Marcador más popular: 2-1 (8 votos)` — si hay empate a votos, se muestran todos: `2-1 (8) · 1-0 (8)`.
   - `Reparto 1 · X · 2: 58 % / 17 % / 25 %`
   - `Sin apostar: Elena Ruiz, Marcos Vidal, …` si son ≤ 10; en caso contrario `Sin apostar: 12 jugadores`.

4. **Tabla de pronósticos**: dos columnas, `Jugador | Pronóstico`. Ancho: 60 % / 40 %. Cabecera con fondo gris claro (#EEE), filas con striping (#F8F8F8). Orden alfabético por `name`. Pronóstico formateado `H - A`; ausentes → `—`. Sólo se incluyen jugadores con `is_jugador=True, is_active=True`.

5. **Clasificación general** al momento del cierre: tabla de tres columnas `Pos | Jugador | Pts`. Mismo orden que la página de clasificación (puntos descendente, desempate por nº de exactos, después por nº de aciertos, después alfabético). Solo incluye jugadores con `is_jugador=True, is_active=True`. Se muestran las primeras 20 filas; si hay más, se añade una fila final `… y N jugadores más`.

6. **Pie de página** (renderizado en `onLaterPages`/`onFirstPage`):
   - `Generado el 14 jun 2026 a las 19:00 · porra26.pythonanywhere.com`
   - `Página X de Y` a la derecha.

**Generación**: función `generar_pdf_cierre(match: Match) -> bytes` en `competition/services/closing_report.py`. Devuelve `bytes`; el endpoint la envuelve en `HttpResponse(pdf_bytes, content_type="application/pdf")`.

## 8. UI de gestión

Cambios en la vista `ManageResultsView` (`/competicion/resultados/`):

### 8.1 Botón de descarga por partido

En la tarjeta de cada partido con `status ∈ {closed, live, done}`:

- Se añade un botón secundario **"📄 PDF cierre"** (estilo `.btn .btn-ghost`).
- Enlace a `/api/teams/cierres/<match_id>/pdf?download=1`.
- Al pulsarlo se descarga el PDF gracias al `Content-Disposition: attachment`.
- El decorador acepta la sesión del gestor (sin necesidad del token Bearer).

### 8.2 Sección "Estado de envíos a Teams"

Sección colapsable al final de la vista (cerrada por defecto). Tabla solo-lectura con columnas:

| Partido | Estado partido | Generado | Enviado | Intentos | Última generación |
|---------|----------------|----------|---------|----------|-------------------|

- Listado de todos los matches con `BetsClosingReport` existente (es decir, los que han pasado por `/pdf` al menos una vez).
- `Generado`: ✓ con tooltip de fecha si `generated_at`, `—` si no.
- `Enviado`: ✓ verde si `sent_at`, ⏳ ámbar si `attempts > 0 AND sent_at IS NULL` (en cola de reintento), `—` si nunca tocado.
- Ordenado por `kickoff` descendente (los más recientes arriba).

Reintento manual: **no** en UI. Si el gestor necesita forzar reenvío, entra en Django admin y vacía el campo `sent_at` de la fila correspondiente; el flow lo recogerá en su siguiente vuelta.

## 9. Seguridad

- **`TEAMS_API_TOKEN`**: 64 caracteres aleatorios (`secrets.token_urlsafe(48)`). Vive en `.env` y en cada HTTP action del Flow como *Secure input* (Power Automate ofrece marcar inputs como secret para no loguearlos).
- **Comparación constante**: usar `secrets.compare_digest()` para evitar timing attacks.
- **Logging**: el decorador loguea (a `logging.WARNING`) intentos con token incorrecto, incluyendo IP de origen (`request.META["REMOTE_ADDR"]`) y user-agent. **Nunca** loguea el token recibido.
- **Rate limiting**: ninguno explícito. Volumen máximo ≈ 64 partidos × 144 sondeos/día = ~9 200 requests/día, todas por la misma IP. `django-axes` ya está activo para el login; no aplica aquí.
- **CSRF**: endpoints `@csrf_exempt`. No reciben cookies de sesión salvo en el camino "gestor descarga PDF", donde la sesión sí está activa pero el endpoint es GET (no necesita CSRF) o POST con CSRF gestionado por separado.
- **Datos expuestos**: los pronósticos de un partido ya cerrado son visibles para todos los jugadores dentro de la app (no hay secreto). El listado de "quién no ha apostado" sí es información que la app no publica a no-gestores; aparece en el PDF, y el canal de Teams es interno de la empresa.

## 10. Configuración

- **`requirements.txt`**: añadir `reportlab>=4.0`.
- **`.env.example`** y **`.env` en PythonAnywhere**: añadir `TEAMS_API_TOKEN=<64 chars>` y `PORRA_BASE_URL=https://<user>.pythonanywhere.com` (esta última se usa solo como referencia documental para configurar el Flow).
- **`porra26/settings/base.py`**: lectura del token vía `os.getenv("TEAMS_API_TOKEN", "")`. Si está vacío, los endpoints siguen respondiendo pero **rechazan toda autenticación Bearer** (no se debe arrancar en producción sin token).
- **`docs/DEPLOY.md`**: nueva sección "Token de integración Teams".
- **`docs/RUNBOOK.md`**: añadir verificación periódica del estado de envíos en la página de Resultados.
- **`docs/TEAMS_FLOW.md`** (nuevo): paso a paso para configurar el Scheduled cloud flow en Power Automate, incluyendo:
  - Recurrence cada 10 min.
  - Tres acciones HTTP (`GET cierres-pendientes`, `GET pdf`, `POST marcar-enviado`).
  - Acción "Post message in a chat or channel" del conector de Teams, con adjunto construido desde el cuerpo binario del paso PDF.
  - Configuración de *Run after* para que `marcar-enviado` se ejecute solo si "Post message" fue *succeeded*.
  - Marcado de los inputs como *Secure input*.

## 11. Tests

Nuevo fichero `competition/tests/test_teams_bridge.py`:

| Test | Comportamiento esperado |
|------|------------------------|
| `test_endpoints_require_token` | GET y POST sin cabecera Bearer responden 401 con cuerpo JSON. |
| `test_endpoints_reject_wrong_token` | Cabecera con token distinto → 401. |
| `test_pendientes_lists_only_closed_unsent` | Partidos `open`/`closing` no aparecen; `closed` sin envío sí; `closed` con `sent_at` no; `live` y `done` sin envío sí (porque el cierre ya pasó). |
| `test_pdf_returns_pdf_and_updates_report` | Respuesta es `application/pdf`, `BetsClosingReport` queda con `attempts=1`, `generated_at`, `last_sha256` con 64 caracteres hex. |
| `test_pdf_404_when_not_closed` | Match aún abierto → 404. |
| `test_pdf_content_includes_predictions` | El texto extraído del PDF (con `pdfplumber` o `pdfminer.six` en `requirements-dev.txt`) contiene los nombres de los jugadores y sus pronósticos. |
| `test_pdf_handles_no_predictions` | Match sin pronósticos: PDF se genera; tabla muestra `—` para todos los activos. |
| `test_marcar_enviado_idempotente` | Segunda llamada devuelve `already_sent: true` y **no** crea un segundo AuditLog. |
| `test_marcar_enviado_creates_audit` | Primera llamada crea `AuditLog(action="bets_pdf_sent")` con `target_id` correcto. |
| `test_session_gestor_can_download_without_token` | Cliente con sesión de gestor accede a `/pdf` sin cabecera Bearer → 200. |
| `test_session_jugador_no_puede` | Cliente con sesión de jugador (no gestor) sin token → 401. |

`requirements-dev.txt`: añadir `pdfplumber` para los tests de contenido del PDF.

## 12. Migración y compatibilidad

- Migración Django nueva: `competition/migrations/0XXX_betsclosingreport.py` con `CreateModel`.
- Sin backfill: los partidos ya cerrados antes del despliegue aparecerán inmediatamente en `/cierres-pendientes` la primera vez que el Flow corra. Esto es deseado (auditoría retrospectiva). Si no se quiere, se puede ejecutar un *one-off* `BetsClosingReport.objects.bulk_create([...sent_at=now()...])` para los matches ya pasados.
- Sin cambios en `Match` ni en `Prediction`.
- Sin cambios en `Round`, `Team`, `User`, `AuditLog` (se aprovecha tal cual).

## 13. Fuera de alcance

- **No** se usa Microsoft Graph ni Entra ID.
- **No** se hace *push* desde Django a Teams ni a Power Automate.
- **No** se usan scheduled tasks de Django para este sistema.
- **No** se notifica a los jugadores individualmente (correo, push); el único destinatario es el canal de Teams.
- **No** se genera un PDF al confirmar resultados oficiales (eso podría ser una iteración futura, "PDF de cierre + resultado").
- **No** se versionan los PDFs; un mismo match siempre regenera el mismo contenido (el hash queda como prueba).
- **No** hay reintentos automáticos en el lado servidor: la responsabilidad de reintento es del Flow.

## 14. Riesgos y mitigaciones

| Riesgo | Mitigación |
|--------|------------|
| Power Automate cambia el formato esperado del adjunto. | Documentar la versión concreta del conector en `TEAMS_FLOW.md`; los tests no cubren el Flow (es externo). |
| El token se filtra (commit accidental, captura de logs). | `secrets.compare_digest`; logs no incluyen el token; instrucción explícita en `RUNBOOK.md` de rotar el token y actualizar el Flow si hay sospecha. |
| El Flow se desactiva por inactividad de la cuenta de M365. | El gestor verá en la sección "Estado de envíos" que los partidos cerrados no pasan a "enviado" → señal visible. |
| El plan free de PythonAnywhere expira o el dominio cambia. | El Flow tiene la URL en un solo sitio; basta con actualizarla. |
| El PDF crece tanto que ReportLab tarda > 30 s y PythonAnywhere corta. | Improbable con ≤ 64 jugadores; cubierto por el límite de los datos del proyecto. Si pasa, paginar la tabla. |

## 15. Trabajo futuro (no en esta entrega)

- Variante "cierre + resultado": al confirmar el resultado oficial, generar un segundo PDF con los puntos obtenidos por cada jugador y enviarlo al canal.
- Banderas de selección como PNGs en el PDF.
- Configuración por canal: distintos canales por ronda (ej. fase de grupos vs. eliminatorias).
- Página pública (sin auth) para que el Flow consuma sin token, restringiendo por IP. Solo viable si se acepta el plan Hacker de PythonAnywhere y se quiere simplificar el Flow.
