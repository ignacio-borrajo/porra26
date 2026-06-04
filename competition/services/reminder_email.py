"""Servicio de envío de emails de recordatorio pre-cierre.

El cuerpo del email *es* el mensaje que Power Automate publicará en Teams: no
hay adjunto, no hay paso intermedio en OneDrive. Por eso construimos el HTML
con cuidado — es lo que verán los jugadores.
"""

from datetime import timedelta

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.utils import timezone

from accounts.models import AuditLog, User
from competition.models import BET_CLOSE_HOURS, BetsReminderLog, Match
from competition.services.reminders import get_pending_bettors

DEFAULT_SUBJECT_PREFIX = "[Porra26 RECORDATORIO]"
SITE_URL = "https://laporradeljefe.es"
COMPETICION_URL = f"{SITE_URL}/competicion/"
MAX_NAMES_IN_BODY = 30


def _subject_prefix() -> str:
    return getattr(settings, "TEAMS_REMINDER_SUBJECT_PREFIX", DEFAULT_SUBJECT_PREFIX)


def _remaining_phrase(match: Match, kind: str, now) -> str:
    """Texto del tiempo restante hasta el cierre, en español.

    AUTO kinds usan textos fijos; MANUAL calcula al vuelo.
    """
    if kind == BetsReminderLog.KIND_T_MINUS_4H:
        return "2 horas"
    if kind == BetsReminderLog.KIND_T_MINUS_2_5H:
        return "30 min"
    # MANUAL — calcular delta hasta cierre
    closure = match.kickoff - timedelta(hours=BET_CLOSE_HOURS)
    delta = closure - now
    total_minutes = max(0, int(delta.total_seconds() // 60))
    hours, minutes = divmod(total_minutes, 60)
    if hours and minutes:
        return f"{hours} h {minutes} min"
    if hours:
        return f"{hours} h"
    return f"{minutes} min"


def _format_names(pending: list[User]) -> tuple[str, int]:
    """Devuelve la lista de nombres a mostrar (truncada) y cuántos sobran."""
    if len(pending) <= MAX_NAMES_IN_BODY:
        return ", ".join(u.name for u in pending), 0
    shown = pending[:MAX_NAMES_IN_BODY]
    return ", ".join(u.name for u in shown), len(pending) - MAX_NAMES_IN_BODY


def _build_subject(match: Match) -> str:
    kickoff_local = timezone.localtime(match.kickoff)
    return (
        f"{_subject_prefix()} {match.home.name} vs {match.away.name} "
        f"· {kickoff_local:%d/%m %H:%M}"
    )


def _build_plain(match: Match, kind: str, pending: list[User], now) -> str:
    closure_local = timezone.localtime(match.kickoff - timedelta(hours=BET_CLOSE_HOURS))
    remaining = _remaining_phrase(match, kind, now)
    names_str, overflow = _format_names(pending)
    lines = [
        f"{match.home.name} vs {match.away.name} cierra apuestas a las "
        f"{closure_local:%H:%M}.",
        "",
        f"Faltan {remaining} y quedan {len(pending)} jugadores sin apostar:",
        names_str + (f" … y {overflow} más." if overflow else ""),
        "",
        COMPETICION_URL,
    ]
    return "\n".join(lines)


def _build_html(match: Match, kind: str, pending: list[User], now) -> str:
    closure_local = timezone.localtime(match.kickoff - timedelta(hours=BET_CLOSE_HOURS))
    remaining = _remaining_phrase(match, kind, now)
    names_str, overflow = _format_names(pending)
    tail = f" … y {overflow} más." if overflow else ""
    return (
        f"<p>⏰ <b>{match.home.name} vs {match.away.name}</b> cierra apuestas a las "
        f"<b>{closure_local:%H:%M}</b>.</p>\n"
        f"<p>Faltan <b>{remaining}</b> y quedan <b>{len(pending)} jugadores</b> "
        f"sin apostar:</p>\n"
        f"<p>{names_str}{tail}</p>\n"
        f'<p><a href="{COMPETICION_URL}">Ir a apostar →</a></p>'
    )


def send_reminder_email(match: Match, kind: str) -> BetsReminderLog | None:
    """Envía el recordatorio del ``match`` con el ``kind`` dado.

    - Lanza ``ValueError`` si el cierre ya pasó (``kickoff − 2h ≤ now``).
    - Si ``kind`` ∈ AUTO_KINDS y ya existe log para ``(match, kind)`` → no-op,
      devuelve ``None``.
    - Si no hay rezagados → no-op, devuelve ``None`` (no crea log).
    - Si SMTP falla → propaga la excepción.
    """
    if kind not in {k for k, _ in BetsReminderLog.KIND_CHOICES}:
        raise ValueError(f"kind desconocido: {kind!r}")

    now = timezone.now()
    if match.kickoff - timedelta(hours=BET_CLOSE_HOURS) <= now:
        raise ValueError(f"El match {match.id} ya tiene las apuestas cerradas")

    if (
        kind in BetsReminderLog.AUTO_KINDS
        and BetsReminderLog.objects.filter(match=match, kind=kind).exists()
    ):
        return None

    pending = get_pending_bettors(match)
    if not pending:
        return None

    subject = _build_subject(match)
    plain = _build_plain(match, kind, pending, now)
    html = _build_html(match, kind, pending, now)

    message = EmailMultiAlternatives(
        subject=subject,
        body=plain,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[settings.TEAMS_DESTINATION_EMAIL],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)

    log, _ = BetsReminderLog.objects.update_or_create(
        match=match,
        kind=kind,
        defaults={
            "sent_at": timezone.now(),
            "pending_count": len(pending),
            "pending_names": [u.name for u in pending],
        },
    )
    AuditLog.objects.create(
        actor=None,
        action="bets_reminder_sent",
        target_type="match",
        target_id=str(match.id),
        payload={
            "kind": kind,
            "pending_count": len(pending),
            "to": settings.TEAMS_DESTINATION_EMAIL,
            "subject": subject,
        },
    )
    return log
