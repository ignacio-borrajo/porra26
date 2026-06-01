"""Puerta de jornada: abre J{N} cuando todos los partidos de J{N-1} alcanzaron su kickoff."""

from datetime import datetime

from django.utils import timezone

from competition.models import Match


def is_matchday_open(round_id: str, matchday: int | None) -> bool:
    if matchday is None or matchday <= 1:
        return True
    prev_kickoffs = list(
        Match.objects.filter(round_id=round_id, matchday=matchday - 1).values_list(
            "kickoff", flat=True
        )
    )
    if not prev_kickoffs:
        return True
    now = timezone.now()
    return all(now >= k for k in prev_kickoffs)


def previous_matchday_close_info(
    round_id: str, matchday: int | None
) -> tuple[Match | None, datetime | None]:
    """Devuelve el último partido de la jornada anterior (por kickoff) y su kickoff."""
    if matchday is None or matchday <= 1:
        return None, None
    last = (
        Match.objects.filter(round_id=round_id, matchday=matchday - 1)
        .select_related("home", "away")
        .order_by("-kickoff")
        .first()
    )
    if last is None:
        return None, None
    return last, last.kickoff
