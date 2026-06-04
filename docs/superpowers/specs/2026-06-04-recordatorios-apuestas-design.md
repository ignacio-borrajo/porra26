# Recordatorios de apuestas → Teams — diseño

**Fecha:** 2026-06-04
**Autor:** Ignacio Borrajo (con Claude)
**Estado:** propuesto, pendiente de ejecutar el plan asociado

---

## 1. Motivación

Algunos jugadores se olvidan de apostar antes de que se cierre el plazo (kickoff − 2 h). Queremos un recordatorio automático en el chat de grupo de Teams **2 horas y 30 minutos antes del cierre** de cada partido, mencionando por nombre a los rezagados. También queremos que el gestor pueda forzar un recordatorio manual desde la pantalla de Resultados.

## 2. Restricciones aceptadas

- **No hay conectores premium de Power Automate** (mismo veto que la feature de cierre — ver `2026-06-01-cierre-apuestas-email-design.md`).
- **No queremos un cron continuo en Railway** que consuma recursos por nada cuando no hay partidos cerca. El cron debe ejecutarse "fuera" de Railway.
- **No queremos infra async pesada** (Celery + Redis añade ~$10–15/mes en Railway para resolver 128 envíos en 6 semanas).

## 3. Decisiones tomadas

| Tema | Decisión |
|------|----------|
| Patrón general | Email-push desde Django → Outlook → Power Automate → Teams. Reusa el SMTP + Outlook + cuenta destino del flow de cierre existente, con un flow PA independiente filtrado por prefijo distinto. |
| Disparador externo | **GitHub Actions cron** (`*/15 * * * *`) llamando un endpoint Django con Bearer. Cero coste Railway cuando no hay trabajo. |
| Antelaciones | **2 avisos por partido**: kickoff − 4 h (= 2 h antes del cierre) y kickoff − 2,5 h (= 30 min antes del cierre). |
| Caso vacío | Si en el momento del aviso ya han apostado todos los esperados → no se envía nada, no se crea log. |
| Cuerpo del mensaje | HTML conversacional con lista de nombres en texto plano (sin @menciones reales — requieren HTTP premium o app registrada). |
| Agregación | Un mensaje por partido. Si en una misma pasada del cron caen varios partidos, salen mensajes separados. |
| Universo de "esperados" | `User.objects.filter(is_active=True, is_jugador=True)`. Incluye gestores que también juegan; excluye gestores puros e inactivos. |
| Botón manual del gestor | En `/competicion/resultados/`, sobre cada partido todavía no cerrado. Envía con `kind=MANUAL`. Reenviable cuantas veces quiera. |
| Pill de "sin apostar" | Junto al botón, calculado en tiempo real (no del último log). 🟠 si > 0, 🟢 si 0. |
| Idempotencia | Modelo nuevo `BetsReminderLog` con `unique_together(match, kind)`. Para AUTO kinds → fila inmutable. Para MANUAL → `update_or_create` sobre la misma fila; el historial completo de envíos manuales queda en `AuditLog`. |
| Frecuencia GHA cron | Cada 15 min, 24/7. Free tier de GitHub cubre de sobra. Jitter aceptable porque el backend filtra los avisos cuyo cierre ya pasó. |

## 4. Arquitectura

```
┌──────────────────────────────────────────────────┐    ┌──────────────────────────┐
│  Railway (Django + Postgres)                     │    │  Outlook 365             │
│                                                  │    │  (cuenta destino)        │
│  ┌─────── POST /api/recordatorios/disparar/ ─┐   │    │                          │
│  │ Bearer auth (mismo token que cierres)     │   │    │                          │
│  └────────────┬───────────────────────────────┘   │    │                          │
│               │                                  │    │                          │
│               │  matches_due_for_kind(4H, 2_5H)  │    │                          │
│               ▼                                  │    │                          │
│  ┌─── services/reminder_email.py ─────────────┐ │    │                          │
│  │ send_reminder_email(match, kind):          │ │    │                          │
│  │  1. ValueError si cierre pasado            │ │    │                          │
│  │  2. AUTO + log existe → no-op              │ │    │                          │
│  │  3. pending = get_pending_bettors(match)   │ │    │                          │
│  │  4. lista vacía → no-op (sin log)          │ │    │                          │
│  │  5. EmailMessage (HTML + plain) ───SMTP───►│ │    │  📥 Inbox PORRA26        │
│  │  6. BetsReminderLog.update_or_create       │ │    │  [Porra26 RECORDATORIO]  │
│  │  7. AuditLog(action="bets_reminder_sent")  │ │    │                          │
│  └────────────────────────────────────────────┘ │    └──────────┬───────────────┘
│               ▲                                  │               │ Trigger Outlook
│               │                                  │               │ (filtro asunto)
│  ┌── Botón "✉ Recordatorio" del gestor ──┐     │               ▼
│  │  /competicion/resultados/             │     │    ┌──────────────────────────┐
│  │  POST /api/recordatorios/<id>/enviar/ │     │    │  Power Automate flow     │
│  │  (sesión gestor o Bearer)             │     │    │  NUEVO, hermano del de  │
│  │  → send_reminder_email(m, MANUAL)     │     │    │  cierre, 2 pasos:        │
│  └────────────────────────────────────────┘     │    │  - When email arrives   │
└──────────────────────────────────────────────────┘    │    (subject filter)     │
                                                       │  - Post message in      │
┌──────────────────────────────────────────────────┐    │    group chat con HTML  │
│  GitHub Actions                                  │    │    del body del email   │
│  .github/workflows/match-reminders.yml           │    └──────────────────────────┘
│                                                  │
│  schedule: '*/15 * * * *'                        │
│  workflow_dispatch: (botón manual desde UI)      │
│                                                  │
│  curl -X POST -H "Authorization: Bearer ..."    │
│    https://laporradeljefe.es/competicion/api/   │
│    recordatorios/disparar/                       │
└──────────────────────────────────────────────────┘
```

## 5. Modelo de datos

### `BetsReminderLog` (nuevo, en `competition/models.py`)

```python
class BetsReminderLog(models.Model):
    KIND_T_MINUS_4H = "T_MINUS_4H"
    KIND_T_MINUS_2_5H = "T_MINUS_2_5H"
    KIND_MANUAL = "MANUAL"
    KIND_CHOICES = [
        (KIND_T_MINUS_4H, "2 h antes del cierre"),
        (KIND_T_MINUS_2_5H, "30 min antes del cierre"),
        (KIND_MANUAL, "Manual"),
    ]
    AUTO_KINDS = (KIND_T_MINUS_4H, KIND_T_MINUS_2_5H)

    match = ForeignKey(Match, on_delete=CASCADE, related_name="reminder_logs")
    kind = CharField(max_length=20, choices=KIND_CHOICES)
    sent_at = DateTimeField()
    pending_count = PositiveSmallIntegerField()
    pending_names = JSONField(default=list)  # snapshot textual

    class Meta:
        constraints = [
            UniqueConstraint(fields=["match", "kind"], name="uniq_reminder_per_match_kind"),
        ]
        indexes = [Index(fields=["sent_at"])]
```

- `pending_names` se almacena como `list[str]` para auditoría sin acoplar a FK de User.
- Las 3 kinds son mutuamente exclusivas: máximo 3 filas por match.

## 6. Servicios

### `competition/services/reminders.py` (nuevo)

```python
def get_pending_bettors(match: Match) -> list[User]:
    """Jugadores activos que no han creado Prediction para este match."""

def matches_due_for_kind(kind: str) -> QuerySet[Match]:
    """Matches que entran en ventana de aviso para el `kind` dado y no tienen log."""
```

Ventanas:
- `T_MINUS_4H`: `kickoff__lte = now + 4h` AND `kickoff > now + 2h` (= cierre) AND no log previo.
- `T_MINUS_2_5H`: `kickoff__lte = now + 2.5h` AND `kickoff > now + 2h` AND no log previo.

### `competition/services/reminder_email.py` (nuevo)

```python
def send_reminder_email(match: Match, kind: str) -> BetsReminderLog | None:
    """Envía email de recordatorio para `match` con el `kind` dado.
    Devuelve el log creado/actualizado, o None si no se envió (sin pendientes
    o kind AUTO ya enviado). Lanza ValueError si el cierre ya pasó.
    """
```

Flujo (8 pasos):

1. Si `now >= kickoff − 2h` → `ValueError("apuestas ya cerradas")`.
2. Si `kind in AUTO_KINDS` y existe `BetsReminderLog.objects.filter(match, kind)` → devolver `None`.
3. `pending = get_pending_bettors(match)`. Si `len(pending) == 0` → devolver `None` sin crear log.
4. Construir asunto (`f"{prefix} {home} vs {away} · {dd/mm HH:MM}"`) y body (HTML + plain).
5. `message.send(fail_silently=False)`. Si SMTP falla → propaga.
6. `BetsReminderLog.objects.update_or_create(match, kind, defaults={...})`.
7. `AuditLog(action="bets_reminder_sent", payload={"kind": kind, "pending_count": N, "to": ...})`.
8. Devolver el log.

## 7. Email

### Asunto

```
[Porra26 RECORDATORIO] España vs México · 04/06 16:00
```

El prefijo es **distinto** del de cierre (`[Porra26]`) para que cada flow PA filtre solo lo suyo. Configurable por env var `TEAMS_REMINDER_SUBJECT_PREFIX` (default `[Porra26 RECORDATORIO]`).

### Cuerpo HTML

```html
<p>⏰ <b>España vs México</b> cierra apuestas a las <b>14:00</b>.</p>
<p>Faltan <b>2 horas</b> y quedan <b>12 jugadores</b> sin apostar:</p>
<p>Ana Pérez, Juan Gómez, María López, Carlos Ruiz, Laura Díaz,
Pedro Sanz, Eva Marín, Luis Cano, Marta Rey, Diego Núñez,
Sara Vidal, Iván Soto.</p>
<p><a href="https://laporradeljefe.es/competicion/">Ir a apostar →</a></p>
```

### Cuerpo texto plano (fallback)

Versión texto del mismo contenido. Outlook envía `multipart/alternative`, Power Automate publica el HTML.

### Variaciones por `kind`

- `T_MINUS_4H` → "Faltan **2 horas**".
- `T_MINUS_2_5H` → "Faltan **30 minutos**".
- `MANUAL` → "Faltan **{hh}h {mm}min**" (calculado desde `kickoff − 2h − now`).

### Truncado defensivo

Si `len(pending) > 30` → mostrar primeros 30 + "… y N más" (no realista hoy, defensivo para el futuro).

## 8. Endpoints

### `POST /competicion/api/recordatorios/disparar/`

- Auth: `require_teams_api_token` (Bearer o sesión gestor).
- Comportamiento: recorre `matches_due_for_kind("T_MINUS_4H")` y `..._2_5H`, llama `send_reminder_email` para cada uno. Errores individuales capturados y logueados; no aborta.
- Respuesta:
  ```json
  {
    "T_MINUS_4H": {"checked": 2, "sent": 1, "skipped_empty": 1, "errors": 0},
    "T_MINUS_2_5H": {"checked": 0, "sent": 0, "skipped_empty": 0, "errors": 0}
  }
  ```

### `POST /competicion/api/recordatorios/<match_id>/enviar/`

- Auth: `require_teams_api_token` (mismo decorador).
- Comportamiento: invoca `send_reminder_email(match, kind=MANUAL)`.
- Respuestas:
  - 200 `{"sent": true, "pending_count": N, "sent_at": "..."}` si envió.
  - 200 `{"sent": false, "reason": "no_pending"}` si no había rezagados.
  - 409 `{"detail": "apuestas ya cerradas"}` si `ValueError`.
  - 401 si auth inválida.
- Si `Accept: text/html` (botón del gestor en HTML form): redirige a `manage_results` con `messages` flash. Mismo patrón que `cierre_enviar`.

## 9. Management command

```bash
python manage.py send_match_reminders [--match-id N] [--kind ...] [--dry-run]
```

- Sin args: equivalente a llamar al endpoint `disparar/`.
- Útil para debug local y como entry point alternativo al endpoint.

## 10. GitHub Actions

`.github/workflows/match-reminders.yml`:

```yaml
name: Recordatorios de apuestas

on:
  schedule:
    - cron: '*/15 * * * *'
  workflow_dispatch:

jobs:
  trigger:
    runs-on: ubuntu-latest
    steps:
      - name: Disparar recordatorios pendientes
        run: |
          curl --fail --silent --show-error --max-time 60 \
            -X POST \
            -H "Authorization: Bearer ${{ secrets.PORRA26_API_TOKEN }}" \
            "${{ secrets.PORRA26_BASE_URL }}/competicion/api/recordatorios/disparar/"
```

Secrets:
- `PORRA26_API_TOKEN` → mismo valor que la env var `TEAMS_API_TOKEN` del backend.
- `PORRA26_BASE_URL` → `https://laporradeljefe.es`.

## 11. Power Automate flow

Hermano del de cierre, **independiente** para no tocar el flow vivo.

| Paso | Configuración |
|---|---|
| **Trigger** *When a new email arrives (V3)* | Folder: `PORRA26` · From: `onboarding@resend.dev` (o dominio verificado) · **Subject Filter: `[Porra26 RECORDATORIO]`** · Only with Attachments: **No** · Include Attachments: **No** |
| **Acción** *Post message in a chat or channel* | Post as: Flow bot · Post in: Group chat · Group chat: mismo del de cierre · **Message** (Code view): `@{triggerOutputs()?['body/Body']}` |

Dos pasos, sin Apply to each, sin OneDrive.

## 12. UI — `/competicion/resultados/`

Sección **PRÓXIMOS** del template `manage_results.html`. Por cada match no cerrado:

- Pill con `pending_count` calculado en tiempo real (server-side):
  - 🟠 ámbar `{N} sin apostar` si N > 0.
  - 🟢 verde `Todos han apostado` si N = 0.
- Botón **"✉ Recordatorio"** que dispara `POST /api/recordatorios/<id>/enviar/` con CSRF (form HTML, redirect tras submit).
- Si N = 0 → botón con `disabled` y tooltip "No quedan rezagados".
- Tooltip del botón cuando hay log previo: "Último recordatorio: hace X (N rezagados)".

Vista pasa un dict `pending_counts: {match_id: int}` y `last_reminders: {match_id: BetsReminderLog}` precalculados con queries agregadas (no N+1).

## 13. Settings

```python
# porra26/settings/base.py
TEAMS_REMINDER_SUBJECT_PREFIX = os.getenv("TEAMS_REMINDER_SUBJECT_PREFIX", "[Porra26 RECORDATORIO]")
# Reutiliza TEAMS_DESTINATION_EMAIL y EMAIL_* existentes.
```

```
# .env.example — añadir
TEAMS_REMINDER_SUBJECT_PREFIX=[Porra26 RECORDATORIO]
```

## 14. Tests

| Fichero | Casos |
|---|---|
| `test_reminder_detection.py` | `get_pending_bettors` filtra is_active + is_jugador; incluye gestor jugador; excluye los que apostaron. `matches_due_for_kind` ventanas correctas; excluye post-cierre; excluye con log previo. |
| `test_reminder_email_service.py` | Envío crea email + log; sin pendientes es no-op sin log; AUTO idempotente; MANUAL update_or_create; asunto incluye prefix + slug; body lista nombres; HTML + plain ambos presentes; ValueError tras cierre; AuditLog. |
| `test_send_match_reminders_command.py` | Envía ambos kinds en ventana; continúa ante error individual; dry-run no envía; --match-id filtra; --kind filtra. |
| `test_reminder_api_endpoints.py` | `disparar/` Bearer ok + sesión ok + 401 sin auth; resumen JSON; `enviar/<id>/` sesión gestor; 200 sent; 200 no_pending; 409 cerrado. |
| `test_manage_results_reminders.py` | Botón visible en upcoming; pill ámbar con cuenta; pill verde si 0; botón disabled si 0; tooltip muestra último log. |

## 15. Docs a actualizar

- `docs/TEAMS_FLOW.md` → nueva sección "Flow de recordatorios" con la configuración Power Automate.
- `docs/RUNBOOK.md` → entrada "Verificar recordatorios" (revisar Actions tab en GitHub + AuditLog).
- `docs/PLAN.md` → marcar feature.
- `.env.example` → `TEAMS_REMINDER_SUBJECT_PREFIX`.

## 16. Fuera de alcance

- No se toca el flow de cierre existente (PDF).
- No se modifican modelos `Prediction` ni `Match`.
- No se introduce modelo genérico de notificaciones (`WinnerAnnouncement` y `BetsReminderLog` quedan como entidades específicas).
- No se hacen @menciones reales en Teams (texto plano).
- No se gestiona internacionalización ni TZ del lado del email — kickoff se formatea en TZ del servidor (Europe/Madrid).

## 17. Riesgos

| Riesgo | Mitigación |
|---|---|
| GHA cron retrasado >1 h (avisa la propia documentación de GitHub) | El backend filtra `kickoff > now + 2h` — un retraso degrada el aviso a no-op, no a "aviso tardío inútil". `workflow_dispatch` permite forzar desde UI. |
| El flow viejo de cierre intercepta los emails de recordatorio | El filtro del flow viejo es `[Porra26]` literal; los recordatorios usan `[Porra26 RECORDATORIO]`. Hay que verificarlo en PA al crear el flow nuevo. |
| Lista muy larga | Truncar a 30 nombres + "… y N más" en el body. |
| SMTP rebota | El service propaga la excepción; el endpoint la captura y loguea; el siguiente disparo del cron lo reintenta (idempotente: no se creó log). |
| Bearer token filtrado | Mismo riesgo que el endpoint `cierres-pendientes`. Rotación desde Railway env vars. |
| El gestor pulsa el botón manual repetidamente | `update_or_create` sobre la misma fila; cada pulsación deja entrada en `AuditLog` para historial. |
