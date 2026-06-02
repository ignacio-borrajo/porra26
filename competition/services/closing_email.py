import hashlib
from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMessage
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import BET_CLOSE_HOURS, BetsClosingReport, Match
from competition.services.closing_report import build_closing_pdf, compute_closing_stats

SUBJECT_PREFIX = "[Porra26]"


def _build_body(match: Match) -> str:
    stats = compute_closing_stats(match)
    kickoff_local = timezone.localtime(match.kickoff)
    close_local = timezone.localtime(match.kickoff - timedelta(hours=BET_CLOSE_HOURS))
    return "\n".join(
        [
            f"Cierre de apuestas — {match.home.name} vs {match.away.name}",
            "",
            f"{match.round.label} · Grupo {match.group}",
            f"Saque: {kickoff_local:%d %b %Y, %H:%M}",
            f"Cierre: {close_local:%d %b %Y, %H:%M}",
            "",
            f"{stats.bets_count} de {stats.total_players} jugadores han apostado.",
            "",
            "PDF adjunto con el detalle completo (pronósticos, resumen y clasificación general).",
        ]
    )


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

    subject = f"{SUBJECT_PREFIX} {match.teams_slug}"
    body = _build_body(match)
    message = EmailMessage(
        subject=subject,
        body=body,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.TEAMS_DESTINATION_EMAIL],
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
        payload={"to": settings.TEAMS_DESTINATION_EMAIL, "subject": subject},
    )
    return report
