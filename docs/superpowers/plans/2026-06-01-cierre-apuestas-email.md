# Cierre de apuestas → Email → Teams (sin premium) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir la integración HTTP-pull con Power Automate (que requería conectores premium) por un patrón email-push: Django envía un email con el PDF adjunto cada vez que un partido se cierra, y un flow de Power Automate con conectores solo estándar (Outlook trigger + OneDrive + Teams) lo recoge y publica.

**Architecture:** Scheduled task en PythonAnywhere (Hacker plan) ejecuta `python manage.py send_pending_closures` cada 10 min. El comando recorre los matches con cierre pasado y sin `sent_at`, llama a `send_closure_email(match)`, que genera el PDF con `build_closing_pdf` y lo envía vía SMTP-TLS. Un único service idempotente concentra toda la lógica de envío. El endpoint `marcar-enviado` ya no hace falta y se elimina junto con sus tests.

**Tech Stack:** Django 5 · Python 3.12 · `django.core.mail` con backend SMTP (built-in) · `locmem` backend en tests · pytest-django + factory-boy.

**Spec de referencia:** [`docs/superpowers/specs/2026-06-01-cierre-apuestas-email-design.md`](../specs/2026-06-01-cierre-apuestas-email-design.md).

**Punto de partida:** `main` con la versión HTTP-pull ya implementada (commit `1e86e88` o posterior). El feature de la spec original (`docs/superpowers/specs/2026-06-01-cierre-apuestas-teams-design.md`) sigue siendo la base; aquí solo se reescribe la integración con Power Automate.

---

## Estructura de archivos

**Nuevos:**

- `competition/services/closing_email.py` — `send_closure_email(match)`.
- `competition/management/commands/send_pending_closures.py` — comando Django.
- `competition/tests/test_closing_email_service.py` — tests del service.
- `competition/tests/test_send_pending_closures_command.py` — tests del comando.

**Modificados:**

- `porra26/settings/base.py` — añade configuración SMTP y vars `TEAMS_CLOSURE_*`.
- `porra26/settings/test.py` — fuerza backend `locmem`.
- `.env.example` — añade variables SMTP.
- `competition/api/views.py` — elimina `cierre_marcar_enviado` y sus imports.
- `competition/api/urls.py` — elimina la ruta `marcar-enviado`.
- `competition/tests/test_teams_api_endpoints.py` — elimina los tests `test_marcar_enviado_*` (y el `_get_without_auth_returns_401`).
- `docs/PLAN.md` — reescribe la Fase 7.
- `docs/DEPLOY.md` — añade sección de Hacker plan + SMTP + scheduled task.
- `docs/RUNBOOK.md` — actualiza verificación de envíos.
- `docs/TEAMS_FLOW.md` — reescribe entero (versión email-driven).

---

## Task 1: SMTP settings y variables de entorno

**Files:**
- Modify: `porra26/settings/base.py`
- Modify: `porra26/settings/test.py`
- Modify: `.env.example`

- [ ] **Step 1: Añadir configuración SMTP a `base.py`**

Al final de `porra26/settings/base.py`, añade:

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

- [ ] **Step 2: Forzar backend `locmem` en `test.py`**

Añade al final de `porra26/settings/test.py`:

```python

# Email — backend en memoria para tests; nunca emite tráfico real.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
TEAMS_CLOSURE_EMAIL_TO = "test-destino@edisa.com"
TEAMS_CLOSURE_SUBJECT_PREFIX = "[Porra26]"
DEFAULT_FROM_EMAIL = "porra26-bot@edisa.com"
```

- [ ] **Step 3: Añadir variables a `.env.example`**

Al final de `.env.example`:

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

- [ ] **Step 4: Verificar Django arranca**

```bash
python manage.py check
```

Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 5: Commit**

```bash
git add porra26/settings/base.py porra26/settings/test.py .env.example
git commit -m "feat(email): configuración SMTP y variables TEAMS_CLOSURE_*"
```

---

## Task 2: Eliminar el endpoint `marcar-enviado`

**Files:**
- Modify: `competition/api/views.py`
- Modify: `competition/api/urls.py`
- Modify: `competition/tests/test_teams_api_endpoints.py`

- [ ] **Step 1: Borrar la vista**

En `competition/api/views.py`, elimina:

- La función completa `cierre_marcar_enviado(request, match_id)`.
- El decorador `@require_POST` que la precede.
- El import `from django.views.decorators.http import require_POST` (si no se usa en otra parte del fichero — verifica con `grep`).
- El import `import json as _json` (solo lo usaba `marcar-enviado`).
- El import `from accounts.models import AuditLog` (solo lo usaba `marcar-enviado` — el nuevo service también lo importará, pero en otro fichero).

Tras los cambios, el fichero queda con `_match_payload`, `cierres_pendientes` y `cierre_pdf`.

- [ ] **Step 2: Borrar la ruta**

En `competition/api/urls.py`, deja `urlpatterns` así:

```python
urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
    path("cierres/<int:match_id>/pdf/", views.cierre_pdf, name="cierre_pdf"),
]
```

- [ ] **Step 3: Borrar los tests obsoletos**

En `competition/tests/test_teams_api_endpoints.py`, elimina los siguientes tests (7 en total):

- `test_marcar_enviado_marks_sent_and_creates_audit`
- `test_marcar_enviado_idempotent`
- `test_marcar_enviado_creates_report_if_missing`
- `test_marcar_enviado_handles_empty_body`
- `test_marcar_enviado_requires_token`
- `test_marcar_enviado_404_unknown_match`
- `test_marcar_enviado_get_without_auth_returns_401_not_405`

Tras quitarlos, revisa los imports al inicio del fichero. Probablemente puedas eliminar `import json` y `from accounts.models import AuditLog` si ya no los usa ninguno de los tests restantes (revisa con `grep`).

- [ ] **Step 4: Ejecutar tests**

```bash
pytest -q
```

Expected: todos los tests restantes pasan; el contador baja en 7. Anota el número resultante.

- [ ] **Step 5: Verificar lint y formato**

```bash
python3 -m ruff check competition/ porra26/
python3 -m ruff format --check competition/ porra26/
```

Expected: ambos limpios.

- [ ] **Step 6: Commit**

```bash
git add competition/api/views.py competition/api/urls.py competition/tests/test_teams_api_endpoints.py
git commit -m "refactor(teams): elimina endpoint marcar-enviado y tests asociados"
```

---

## Task 3: Service `send_closure_email`

**Files:**
- Create: `competition/services/closing_email.py`
- Create: `competition/tests/test_closing_email_service.py`

- [ ] **Step 1: Crear tests fallidos**

Crea `competition/tests/test_closing_email_service.py`:

```python
from datetime import timedelta
from unittest.mock import patch

import pytest
from django.core import mail
from django.test import override_settings
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import BetsClosingReport
from competition.services.closing_email import send_closure_email
from competition.tests.factories import MatchFactory, PredictionFactory, TeamFactory


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


@pytest.mark.django_db
def test_send_creates_email_with_pdf_attachment():
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(home=home, away=away, kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert len(msg.attachments) == 1
    name, content, mime = msg.attachments[0]
    assert name == f"cierre-{match.teams_slug}.pdf"
    assert mime == "application/pdf"
    assert content.startswith(b"%PDF-")


@pytest.mark.django_db
def test_send_subject_includes_prefix_and_slug():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    msg = mail.outbox[0]
    assert msg.subject == f"[Porra26] {match.teams_slug}"


@pytest.mark.django_db
def test_send_body_includes_summary():
    home = TeamFactory(code="ESP", name="España")
    away = TeamFactory(code="ARG", name="Argentina")
    match = MatchFactory(home=home, away=away, kickoff=timezone.now() - timedelta(minutes=30))
    from accounts.tests.factories import UserFactory
    p = UserFactory(is_jugador=True, is_active=True)
    UserFactory(is_jugador=True, is_active=True)
    PredictionFactory(match=match, player=p, home=2, away=1)
    send_closure_email(match)
    body = mail.outbox[0].body
    assert "España" in body
    assert "Argentina" in body
    assert "1 de 2" in body


@pytest.mark.django_db
def test_send_marks_report_and_creates_audit():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    report = BetsClosingReport.objects.get(match=match)
    assert report.sent_at is not None
    assert report.attempts == 1
    assert len(report.last_sha256) == 64
    audits = AuditLog.objects.filter(action="bets_pdf_emailed")
    assert audits.count() == 1
    assert audits.first().target_id == str(match.id)


@pytest.mark.django_db
def test_send_is_idempotent():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    send_closure_email(match)
    assert len(mail.outbox) == 1
    assert AuditLog.objects.filter(action="bets_pdf_emailed").count() == 1
    assert BetsClosingReport.objects.get(match=match).attempts == 1


@pytest.mark.django_db
def test_send_raises_if_match_not_closed():
    match = MatchFactory(kickoff=timezone.now() + timedelta(hours=4))
    with pytest.raises(ValueError, match="cerrado"):
        send_closure_email(match)
    assert len(mail.outbox) == 0


@pytest.mark.django_db
def test_send_increments_attempts_even_on_smtp_failure():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    with patch("competition.services.closing_email.EmailMessage.send", side_effect=OSError("SMTP boom")):
        with pytest.raises(OSError):
            send_closure_email(match)
    report = BetsClosingReport.objects.get(match=match)
    assert report.sent_at is None
    assert report.attempts == 1
    assert AuditLog.objects.filter(action="bets_pdf_emailed").count() == 0


@pytest.mark.django_db
@override_settings(TEAMS_CLOSURE_EMAIL_TO="custom@example.com", TEAMS_CLOSURE_SUBJECT_PREFIX="[Test]")
def test_send_uses_settings_for_destination_and_prefix():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    send_closure_email(match)
    msg = mail.outbox[0]
    assert msg.to == ["custom@example.com"]
    assert msg.subject.startswith("[Test] ")
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_closing_email_service.py -v
```

Expected: 8 FAIL — `ModuleNotFoundError: No module named 'competition.services.closing_email'`.

- [ ] **Step 3: Implementar el service**

Crea `competition/services/closing_email.py`:

```python
import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import BET_CLOSE_HOURS, BetsClosingReport, Match
from competition.services.closing_report import build_closing_pdf, compute_closing_stats


def _build_body(match: Match) -> str:
    stats = compute_closing_stats(match)
    kickoff_local = timezone.localtime(match.kickoff)
    close_local = timezone.localtime(match.kickoff - timedelta(hours=BET_CLOSE_HOURS))
    lines = [
        f"Cierre de apuestas — {match.home.name} vs {match.away.name}",
        "",
        f"{match.round.label} · Grupo {match.group}",
        f"Saque: {kickoff_local:%d %b %Y, %H:%M}",
        f"Cierre: {close_local:%d %b %Y, %H:%M}",
        "",
        f"{stats.bets_count} de {stats.total_players} jugadores han apostado.",
        "",
        "PDF adjunto con el detalle completo (pronósticos, resumen y clasificación general).",
        "",
        "— porra26.pythonanywhere.com",
    ]
    return "\n".join(lines)


def send_closure_email(match: Match) -> BetsClosingReport:
    """Envía email de cierre para un match. Idempotente.

    - Si el match aún no está cerrado, lanza ValueError.
    - Si BetsClosingReport.sent_at ya está fijado, no-op (devuelve el report).
    - Si SMTP falla, propaga la excepción tras incrementar `attempts`.
    """
    now = timezone.now()
    if match.kickoff - timedelta(hours=BET_CLOSE_HOURS) > now:
        raise ValueError(f"El match {match.id} aún no está cerrado")

    with transaction.atomic():
        report, _ = BetsClosingReport.objects.select_for_update().get_or_create(match=match)
        if report.sent_at is not None:
            return report
        pdf_bytes = build_closing_pdf(match)
        sha = hashlib.sha256(pdf_bytes).hexdigest()
        report.attempts += 1
        report.generated_at = now
        report.last_sha256 = sha
        report.save(update_fields=["attempts", "generated_at", "last_sha256"])

    subject = f"{settings.TEAMS_CLOSURE_SUBJECT_PREFIX} {match.teams_slug}"
    body = _build_body(match)
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.TEAMS_CLOSURE_EMAIL_TO],
    )
    message.attach(f"cierre-{match.teams_slug}.pdf", pdf_bytes, "application/pdf")
    message.send(fail_silently=False)

    report.sent_at = timezone.now()
    report.save(update_fields=["sent_at"])
    AuditLog.objects.create(
        actor=None,
        action="bets_pdf_emailed",
        target_type="match",
        target_id=str(match.id),
        payload={"to": settings.TEAMS_CLOSURE_EMAIL_TO, "subject": subject},
    )
    return report
```

- [ ] **Step 4: Ejecutar tests**

```bash
pytest competition/tests/test_closing_email_service.py -v
```

Expected: 8 passed.

- [ ] **Step 5: Ejecutar suite completa**

```bash
pytest -q
```

Expected: count = `<count tras Task 2>` + 8.

- [ ] **Step 6: Lint y format**

```bash
python3 -m ruff check competition/ porra26/
python3 -m ruff format --check competition/ porra26/
```

Si format pide ajustes, aplícalos con `python3 -m ruff format <ficheros>`.

- [ ] **Step 7: Commit**

```bash
git add competition/services/closing_email.py competition/tests/test_closing_email_service.py
git commit -m "feat(email): service send_closure_email con tests"
```

---

## Task 4: Management command `send_pending_closures`

**Files:**
- Create: `competition/management/commands/send_pending_closures.py`
- Create: `competition/tests/test_send_pending_closures_command.py`

- [ ] **Step 1: Crear tests fallidos**

Crea `competition/tests/test_send_pending_closures_command.py`:

```python
from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core import mail
from django.core.management import call_command
from django.utils import timezone

from competition.models import BetsClosingReport
from competition.tests.factories import MatchFactory


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


@pytest.mark.django_db
def test_command_sends_for_each_pending_match():
    now = timezone.now()
    MatchFactory(kickoff=now - timedelta(minutes=30))
    MatchFactory(kickoff=now - timedelta(minutes=20))
    MatchFactory(kickoff=now - timedelta(minutes=10))
    call_command("send_pending_closures")
    assert len(mail.outbox) == 3


@pytest.mark.django_db
def test_command_skips_already_sent_matches():
    now = timezone.now()
    m_sent = MatchFactory(kickoff=now - timedelta(minutes=30))
    BetsClosingReport.objects.create(match=m_sent, sent_at=now)
    MatchFactory(kickoff=now - timedelta(minutes=20))  # pendiente
    call_command("send_pending_closures")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_command_skips_open_matches():
    now = timezone.now()
    MatchFactory(kickoff=now + timedelta(hours=6))  # aún abierto
    MatchFactory(kickoff=now - timedelta(minutes=10))  # cerrado
    call_command("send_pending_closures")
    assert len(mail.outbox) == 1


@pytest.mark.django_db
def test_command_continues_on_individual_error():
    now = timezone.now()
    m1 = MatchFactory(kickoff=now - timedelta(minutes=30))
    m2 = MatchFactory(kickoff=now - timedelta(minutes=20))
    m3 = MatchFactory(kickoff=now - timedelta(minutes=10))

    real_send = __import__("competition.services.closing_email", fromlist=["send_closure_email"]).send_closure_email

    def flaky(match):
        if match.id == m2.id:
            raise RuntimeError("boom")
        return real_send(match)

    with patch("competition.management.commands.send_pending_closures.send_closure_email", side_effect=flaky):
        call_command("send_pending_closures")

    # m1 y m3 enviaron, m2 falló → outbox tiene 2.
    assert len(mail.outbox) == 2


@pytest.mark.django_db
def test_command_dry_run_does_not_send():
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    out = StringIO()
    call_command("send_pending_closures", "--dry-run", stdout=out)
    assert len(mail.outbox) == 0
    assert "dry-run" in out.getvalue().lower()


@pytest.mark.django_db
def test_command_match_id_filter():
    now = timezone.now()
    m1 = MatchFactory(kickoff=now - timedelta(minutes=30))
    MatchFactory(kickoff=now - timedelta(minutes=20))  # otro pendiente, NO debe enviarse
    call_command("send_pending_closures", "--match-id", str(m1.id))
    assert len(mail.outbox) == 1
    assert m1.teams_slug in mail.outbox[0].subject


@pytest.mark.django_db
def test_command_match_id_filter_404_logs_and_continues():
    out = StringIO()
    err = StringIO()
    call_command("send_pending_closures", "--match-id", "999999", stdout=out, stderr=err)
    assert len(mail.outbox) == 0
    # No revienta — solo loguea.
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_send_pending_closures_command.py -v
```

Expected: 7 FAIL — `CommandError: Unknown command: 'send_pending_closures'`.

- [ ] **Step 3: Crear el comando**

Crea `competition/management/commands/send_pending_closures.py`:

```python
import logging
from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from competition.models import BET_CLOSE_HOURS, Match
from competition.services.closing_email import send_closure_email

logger = logging.getLogger(__name__)


class Command(BaseCommand):
    help = "Envía por email los PDFs de cierre de apuestas pendientes."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista los matches que se enviarían pero no envía nada.",
        )
        parser.add_argument(
            "--match-id",
            type=int,
            default=None,
            help="Envía solo el match indicado (útil para reintentos manuales).",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        match_id = options["match_id"]
        now = timezone.now()

        qs = Match.objects.filter(
            kickoff__lte=now + timedelta(hours=BET_CLOSE_HOURS)
        ).select_related("home", "away", "round", "closing_report")
        if match_id is not None:
            qs = qs.filter(pk=match_id)

        pendientes = []
        for m in qs.order_by("kickoff"):
            report = getattr(m, "closing_report", None)
            if report is None or report.sent_at is None:
                pendientes.append(m)

        if match_id is not None and not pendientes:
            self.stderr.write(
                f"send_pending_closures: match {match_id} no existe o ya fue enviado."
            )
            return

        if dry_run:
            self.stdout.write(f"send_pending_closures (dry-run): {len(pendientes)} pendientes")
            for m in pendientes:
                self.stdout.write(f"  - {m.id} · {m.teams_slug}")
            return

        ok = 0
        ko = 0
        for m in pendientes:
            try:
                send_closure_email(m)
                ok += 1
                self.stdout.write(f"OK · {m.teams_slug}")
            except Exception as exc:  # noqa: BLE001
                ko += 1
                logger.exception("send_closure_email falló para match %s", m.id)
                self.stderr.write(f"ERR · {m.teams_slug} · {exc}")

        self.stdout.write(f"send_pending_closures: {ok} OK · {ko} ERR · {len(pendientes)} total")
```

- [ ] **Step 4: Ejecutar tests**

```bash
pytest competition/tests/test_send_pending_closures_command.py -v
```

Expected: 7 passed.

- [ ] **Step 5: Ejecutar suite completa**

```bash
pytest -q
```

Expected: count anterior + 7.

- [ ] **Step 6: Lint y format**

```bash
python3 -m ruff check competition/ porra26/
python3 -m ruff format --check competition/ porra26/
```

- [ ] **Step 7: Commit**

```bash
git add competition/management/commands/send_pending_closures.py competition/tests/test_send_pending_closures_command.py
git commit -m "feat(email): management command send_pending_closures con tests"
```

---

## Task 5: Actualizar `docs/PLAN.md`

**Files:**
- Modify: `docs/PLAN.md`

- [ ] **Step 1: Reescribir la Fase 7**

Reemplaza el bloque actual `## Fase 7 — Cierre de apuestas → PDF → Teams` por:

```markdown
## Fase 7 — Cierre de apuestas → PDF → Teams (vía email)

**Objetivo:** dejar constancia automática en el chat de Teams de todas las apuestas realizadas para cada partido, en cuanto se cierra la ventana de pronósticos (kickoff − 2 h). Spec original: [`docs/superpowers/specs/2026-06-01-cierre-apuestas-teams-design.md`](superpowers/specs/2026-06-01-cierre-apuestas-teams-design.md). Spec final (email-driven, sin connectores premium): [`docs/superpowers/specs/2026-06-01-cierre-apuestas-email-design.md`](superpowers/specs/2026-06-01-cierre-apuestas-email-design.md).

**Por qué dos specs**: el primer intento usaba Power Automate llamando a tres endpoints HTTP de Django. Al desplegar descubrimos que el conector HTTP es **premium** (≈ €12/usuario/mes). La reescritura usa solo conectores estándar: Django envía un email con el PDF adjunto vía SMTP, y un flow de Power Automate con trigger Outlook + OneDrive + Teams lo recoge y publica.

Backend ya implementado (modelo, PDF, endpoint `/pdf` para descarga manual y sección "Estado de envíos") sigue valiendo tal cual; solo cambia el "transporte" de PDF al chat.

- [x] Modelo `BetsClosingReport` + migración. *(ya en main)*
- [x] PDF con ReportLab (`build_closing_pdf`). *(ya en main)*
- [x] UI gestor: botón "📄 PDF" + sección "Estado de envíos a Teams". *(ya en main)*
- [x] Endpoint `/api/teams/cierres/<id>/pdf` para descarga manual. *(ya en main)*
- [ ] Service `send_closure_email` con SMTP + tests.
- [ ] Management command `send_pending_closures` + tests.
- [ ] Eliminar endpoint `marcar-enviado` (ya no se consume).
- [ ] PythonAnywhere Hacker plan: scheduled task cada 10 min ejecutando el comando.
- [ ] `docs/TEAMS_FLOW.md` reescrito con la versión email-driven.
- [ ] `DEPLOY.md` y `RUNBOOK.md` actualizados.

**Hecho cuando:** al cerrarse un partido, en ≤ 10 min llega al chat de Teams un mensaje con el PDF accesible vía OneDrive, y reintenta automáticamente si el envío falló.
```

- [ ] **Step 2: Commit**

```bash
git add docs/PLAN.md
git commit -m "docs(plan): reescribe Fase 7 para reflejar el patrón email-driven"
```

---

## Task 6: Reescribir `docs/TEAMS_FLOW.md`

**Files:**
- Modify: `docs/TEAMS_FLOW.md`

- [ ] **Step 1: Reemplazar el contenido completo**

Sobrescribe `docs/TEAMS_FLOW.md` con:

```markdown
# Flujo de Power Automate — Cierre de apuestas a Teams (email-driven)

Esta guía describe cómo configurar el *flow* que recibe los emails de cierre que envía PythonAnywhere y los publica en el chat de grupo de Teams. Usa **solo conectores estándar** (Outlook + OneDrive + Teams) — sin licencia Power Automate Premium.

> **Cambio respecto a versiones anteriores:** la primera versión de esta guía usaba acciones HTTP para sondear directamente la API de PORRA 26 desde Power Automate. Esas acciones son premium. La versión actual delega el sondeo a un scheduled task de PythonAnywhere que envía un email con el PDF adjunto, y este flow solo escucha esa bandeja.

## Prerrequisitos

- Cuenta de Microsoft 365 (cualquier plan que incluya Outlook + OneDrive + Teams — los conectores son estándar).
- Pertenencia al chat de grupo de Teams de destino.
- Carpeta `/Apps/Porra26/Cierres` creada en tu OneDrive (créala una vez a mano desde OneDrive web).
- PythonAnywhere ya configurado con el scheduled task `send_pending_closures` y enviando emails a una bandeja a la que tienes acceso (ver `docs/DEPLOY.md`).

## 1. Crear el flow

1. Entra en https://make.powerautomate.com.
2. **Crear → Flujo de nube automatizado** (*Automated cloud flow*). Nombre sugerido: `PORRA 26 · Cierre apuestas a Teams (email)`.
3. Como trigger, busca y selecciona **Office 365 Outlook → When a new email arrives (V3)** (*Cuando llega un nuevo correo electrónico*). Es un conector estándar.

## 2. Configurar el trigger

| Campo | Valor |
|-------|-------|
| Folder (*Carpeta*) | `Inbox`. |
| From (*De*) | La dirección que configures en `EMAIL_HOST_USER` / `DEFAULT_FROM_EMAIL` de PythonAnywhere (p. ej. `porra26-bot@edisa.com`). |
| Subject Filter (*Filtro de asunto*) | `[Porra26]` (sin comillas; coincide por substring). |
| Include Attachments (*Incluir datos adjuntos*) | Yes. |
| Only with Attachments (*Solo con datos adjuntos*) | Yes. |

Renombra esta acción a algo legible como **"Cuando llega cierre de Porra26"**.

## 3. Bucle sobre los adjuntos

Añade **Aplicar a cada uno** (*Apply to each*) sobre `Attachments` (selecciona desde Contenido dinámico → "When a new email arrives" → **Attachments**).

> Power Automate puede crear el Aplicar a cada uno automáticamente cuando referencies un campo dentro de un array desde una acción posterior. Si te resulta más cómodo, salta a la siguiente acción y deja que el editor lo envuelva solo.

Dentro del bucle, las tres acciones que siguen:

### 3.1 OneDrive — Crear archivo

Acción **OneDrive para la Empresa → Crear archivo** (*Create file*).

| Campo | Valor |
|-------|-------|
| Ruta de carpeta (*Folder Path*) | `/Apps/Porra26/Cierres`. |
| Nombre de archivo (*File Name*) | Desde Contenido dinámico → **Attachments Name**. |
| Contenido del archivo (*File Content*) | Desde Contenido dinámico → **Attachments Content**. |

### 3.2 OneDrive — Crear vínculo para compartir

Acción **OneDrive para la Empresa → Crear vínculo para compartir** (*Create share link*).

| Campo | Valor |
|-------|-------|
| Archivo (*File*) | Desde Contenido dinámico → **Crear archivo · Id**. |
| Tipo de vínculo (*Link Type*) | **Ver** (*View*). |
| Ámbito del vínculo (*Link Scope*) | **Organización** (*Organization*). |

### 3.3 Teams — Publicar en el chat de grupo

Acción **Microsoft Teams → Publicar mensaje en un chat o canal** (*Post message in a chat or channel*).

- **Publicar como** (*Post as*): Flow bot.
- **Publicar en** (*Post in*): **Chat de grupo** (*Group chat*).
- **Chat de grupo**: el del campeonato.
- **Mensaje** (HTML):

  ```html
  📣 <b>Cierre de apuestas</b><br>
  <i>@{triggerOutputs()?['body/subject']}</i><br><br>
  📄 <a href="@{outputs('Crear_vínculo_para_compartir')?['body/link/webUrl']}">Descargar PDF de cierre</a>
  ```

  > Ajusta `'Crear_vínculo_para_compartir'` si renombraste esa acción (los espacios en el nombre se sustituyen por `_`).

### 3.4 Configure run after en cada acción

Menu `...` de cada acción → **Configurar ejecutar después**: solo si la anterior terminó como **correcto** (*is successful*). Así, si OneDrive falla, no se publica un mensaje roto en Teams.

## 4. Probar

1. **Guardar**.
2. Desde PythonAnywhere, ejecuta manualmente el comando para un match concreto:

   ```bash
   python manage.py send_pending_closures --match-id <id>
   ```

3. Verifica:
   - El email llega a la bandeja configurada.
   - El flow se dispara (panel **Mis flujos → Historial de ejecuciones**).
   - El PDF aparece en `/Apps/Porra26/Cierres` de OneDrive.
   - El mensaje aparece en el chat de grupo con el enlace clicable.

## 5. Si algo falla

| Síntoma | Diagnóstico |
|---------|-------------|
| El email llega pero el flow no se dispara | Revisa el filtro del trigger (sender, subject). Outlook puede tardar 1-3 min en procesar reglas. |
| El flow se dispara pero falla en "Crear archivo" | La ruta no existe en OneDrive. Créala a mano. |
| El mensaje sale a Teams pero el enlace pide login | El ámbito del share link debe ser **Organización**, no **People with existing access**. |
| Nadie ve el mensaje en el chat | Comprueba que el flow está publicando en el chat de grupo correcto (los IDs se enumeran al elegirlo). |

## 6. Mantenimiento

- Si la cuenta del flow se desactiva, los enlaces de OneDrive dejan de funcionar. Plan a largo plazo: migrar la carpeta a una biblioteca SharePoint compartida del equipo (cambia los pasos 3.1-3.2 por **SharePoint → Crear archivo** + ajustar el ámbito del share link).
- Si Microsoft retira "Create share link" (sin previsión por ahora), alternativa: usar la URL directa del archivo (`File Path`) y dejar que Teams pida login para abrirlo.
- Rotación de credenciales SMTP: ver `docs/DEPLOY.md` §8.
```

- [ ] **Step 2: Commit**

```bash
git add docs/TEAMS_FLOW.md
git commit -m "docs(teams): reescribe TEAMS_FLOW.md para versión email-driven"
```

---

## Task 7: Actualizar `docs/DEPLOY.md` y `docs/RUNBOOK.md`

**Files:**
- Modify: `docs/DEPLOY.md`
- Modify: `docs/RUNBOOK.md`

- [ ] **Step 1: Añadir sección "8. SMTP y scheduled task" a `DEPLOY.md`**

Al final de `docs/DEPLOY.md`, después de la sección 7 (Token de integración con Teams) — que se mantiene porque el endpoint `/pdf` sigue usándolo —, añade:

```markdown
## 8. SMTP y scheduled task para envío automático

El envío automático del PDF de cierre al chat de Teams se hace por email (ver `docs/TEAMS_FLOW.md`). Requiere PythonAnywhere **Hacker plan** ($5/mes) para SMTP saliente libre y scheduled tasks con frecuencia minute-level.

### 8.1 Upgrade a Hacker plan

Panel PythonAnywhere → **Account → Plans → Hacker**.

### 8.2 Variables SMTP en `.env`

Añade al `.env` de PythonAnywhere:

```
EMAIL_HOST=smtp.office365.com
EMAIL_PORT=587
EMAIL_HOST_USER=porra26-bot@edisa.com
EMAIL_HOST_PASSWORD=<app password>
EMAIL_USE_TLS=True
DEFAULT_FROM_EMAIL=porra26-bot@edisa.com
TEAMS_CLOSURE_EMAIL_TO=<buzón donde escucha Power Automate>
TEAMS_CLOSURE_SUBJECT_PREFIX=[Porra26]
```

Si IT no permite SMTP AUTH para Office 365, alternativas:
- **SendGrid free tier** (`smtp.sendgrid.net:587`, ~100 emails/día).
- **Brevo free tier** (similar).
- **Gmail SMTP** de una cuenta personal con app password.

En todos los casos solo cambia `EMAIL_HOST` y `EMAIL_HOST_PASSWORD`.

Recarga la web app desde el panel.

### 8.3 Scheduled task

Panel **Tasks → Schedule task → New scheduled task**:

- Comando:
  ```
  cd ~/apuestas-interna && /home/<user>/.virtualenvs/<venv>/bin/python manage.py send_pending_closures
  ```
- Frecuencia: **cada 10 minutos**.

### 8.4 Verificación inicial

Desde una bash console:

```bash
cd ~/apuestas-interna
python manage.py send_pending_closures --dry-run
```

Lista los matches pendientes sin enviar nada. Si la lista tiene sentido, ejecuta sin `--dry-run` para un envío real, o espera a la siguiente vuelta del cron.

### 8.5 Rotar credenciales SMTP

1. Genera una nueva contraseña / app password en el panel de la cuenta del proveedor.
2. Actualiza `EMAIL_HOST_PASSWORD` en `.env`.
3. Recarga la web app.
4. Espera al siguiente disparo del scheduled task y verifica que el envío sigue funcionando.
```

- [ ] **Step 2: Actualizar la entrada "Verificar envíos a Teams" en `RUNBOOK.md`**

Reemplaza la sección existente "## Verificar envíos a Teams" por:

```markdown
## Verificar envíos a Teams

Cada lunes, abre `/competicion/resultados/` como gestor y revisa la sección **"Estado de envíos a Teams"**:

- Todos los partidos cerrados desde la semana pasada deben aparecer con ✓ en Generado y ✓ en Enviado.
- Si algún partido aparece con ⏳ (ámbar) o solo Generado ✓ pero Enviado —, significa que el envío SMTP falló:
  1. Revisa el log del scheduled task en PythonAnywhere: panel **Tasks** → fila del task → enlace al log.
  2. Errores típicos:
     - `SMTPAuthenticationError`: contraseña / app password mal. Ver `docs/DEPLOY.md` §8.2.
     - `SMTPConnectError`: host inalcanzable. Comprueba que el plan sigue siendo Hacker.
     - `SMTPRecipientsRefused`: dirección destino mal escrita. Revisa `TEAMS_CLOSURE_EMAIL_TO`.
  3. Tras arreglar la causa, el próximo cron lo reintenta solo (no hace falta intervención manual).
- Si quieres forzar un reenvío inmediato sin esperar al cron:
  ```bash
  python manage.py send_pending_closures --match-id <id>
  ```
- Si quieres silenciar un partido permanentemente (por ejemplo porque se envió a mano):
  En Django admin → BetsClosingReport → fija `sent_at` a la fecha actual.
- Solución manual de emergencia: descarga el PDF con el botón "📄 PDF" en la propia página de Resultados y súbelo a Teams a mano.
```

- [ ] **Step 3: Commit**

```bash
git add docs/DEPLOY.md docs/RUNBOOK.md
git commit -m "docs(deploy): SMTP + scheduled task en DEPLOY; runbook actualizado"
```

---

## Task 8: Verificación final

**Files:** ninguno (verificación).

- [ ] **Step 1: Suite completa**

```bash
pytest -q
```

Expected: todo verde. Apunta el count final (debería ser ~`(count Task 4) − 7 (marcar-enviado) + 8 (service) + 7 (command)` = baseline + 8 respecto a `main` actual).

- [ ] **Step 2: Lint y format**

```bash
python3 -m ruff check competition/ porra26/
python3 -m ruff format --check competition/ porra26/
```

Expected: limpios. Si hay format pendiente, aplica:

```bash
python3 -m ruff format competition/ porra26/
git add -A
git commit -m "chore: ruff format tras feature email"
```

- [ ] **Step 3: Verificación local del comando**

Crea un match cerrado en una shell de Django, envía con backend `locmem`, comprueba mail.outbox.

```bash
python manage.py shell <<'EOF'
from django.utils import timezone
from datetime import timedelta
from competition.tests.factories import MatchFactory, TeamFactory
from django.core import mail
# Solo para inspección local — no toca DB en producción si lo haces en una shell aislada.
EOF
```

(Salta este paso si ya tienes la suite de tests cubriéndolo, que sí.)

- [ ] **Step 4: Verificación del comando contra la DB de dev**

Si tienes datos de seed en SQLite local:

```bash
python manage.py send_pending_closures --dry-run
```

Expected: imprime la lista de matches pendientes o "0 pendientes".

- [ ] **Step 5: Merge a `main`**

```bash
git checkout main
git merge feat/teams-email-driven --no-ff -m "Merge feature: cierre apuestas vía email (sin Power Automate premium)"
git push origin main
```

> Si trabajaste directamente en `main` sin worktree, salta el checkout/merge y solo haz `git push origin main`.

- [ ] **Step 6: Cleanup del worktree si lo usaste**

```bash
git worktree remove .worktrees/feat-teams-email-driven
git branch -d feat/teams-email-driven
```

---

## Resumen

8 tasks. Al final:

- 1 service nuevo (`send_closure_email`) + tests.
- 1 management command (`send_pending_closures`) + tests.
- 1 endpoint eliminado (`marcar-enviado`) + sus tests retirados.
- 4 docs actualizados (PLAN, DEPLOY, RUNBOOK, TEAMS_FLOW).
- Suite verde, lint limpio, listo para configurar PythonAnywhere Hacker plan y construir el flow.

Trabajo manual posterior (no parte del plan):
1. Upgrade PythonAnywhere a Hacker plan.
2. Configurar `.env` con credenciales SMTP reales.
3. Crear el scheduled task en PythonAnywhere.
4. Construir el flow en Power Automate siguiendo el `TEAMS_FLOW.md` reescrito.
