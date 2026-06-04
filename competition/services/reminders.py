"""Detección de rezagados y ventanas de aviso para recordatorios de apuestas."""

from datetime import timedelta

from django.db.models import QuerySet
from django.utils import timezone

from accounts.models import User
from competition.models import BET_CLOSE_HOURS, BetsReminderLog, Match, Prediction


def get_pending_bettors(match: Match) -> list[User]:
    """Jugadores activos que aún no han creado Prediction para `match`.

    Universo: ``is_active=True AND is_jugador=True``. Incluye gestores que
    también juegan; excluye gestores puros e inactivos. Ordenados por nombre.
    """
    already_bet_ids = Prediction.objects.filter(match=match).values_list("player_id", flat=True)
    qs = (
        User.objects.filter(is_active=True, is_jugador=True)
        .exclude(id__in=already_bet_ids)
        .order_by("name")
    )
    return list(qs)


_KIND_TO_LEAD = {
    BetsReminderLog.KIND_T_MINUS_4H: timedelta(hours=4),
    BetsReminderLog.KIND_T_MINUS_2_5H: timedelta(hours=2, minutes=30),
}


def matches_due_for_kind(kind: str) -> QuerySet[Match]:
    """Matches que entran en la ventana de aviso para `kind` y aún no lo tienen.

    Ventana:
    - el umbral del kind ya llegó (``kickoff <= now + lead``).
    - el cierre aún no pasó (``kickoff > now + BET_CLOSE_HOURS``).
    - no existe un :class:`BetsReminderLog` previo para ``(match, kind)``.

    Lanza ``ValueError`` para kinds desconocidos o ``MANUAL`` (que no tiene
    ventana: se envía a petición desde el botón del gestor).
    """
    if kind not in _KIND_TO_LEAD:
        raise ValueError(f"kind sin ventana de aviso: {kind!r}")
    now = timezone.now()
    lead = _KIND_TO_LEAD[kind]
    return (
        Match.objects.filter(
            kickoff__lte=now + lead,
            kickoff__gt=now + timedelta(hours=BET_CLOSE_HOURS),
        )
        .exclude(reminder_logs__kind=kind)
        .order_by("kickoff")
    )
