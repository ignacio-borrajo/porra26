from typing import Optional

from competition.models import Match
from pot.services.prizes import matchday_winners

from .models import WinnerAnnouncement


def detect_after_match(match: Match) -> list[WinnerAnnouncement]:
    """Llamado tras resolve_match(). Crea (idempotentemente) los anuncios de
    ganador que corresponda al scope al que pertenece el partido recién
    resuelto, si y solo si ese scope acaba de cerrarse. Devuelve la lista
    de anuncios creados en esta llamada (0..N)."""
    created: list[WinnerAnnouncement] = []

    if match.round_id == "groups" and match.matchday is not None:
        ann = _try_create("matchday", matchday=match.matchday)
        if ann is not None:
            created.append(ann)
    else:
        ann = _try_create("round", round_id=match.round_id)
        if ann is not None:
            created.append(ann)
        if match.round_id == "final":
            ann_global = _try_create("global")
            if ann_global is not None:
                created.append(ann_global)

    return created


def _try_create(
    scope_kind: str,
    *,
    matchday: Optional[int] = None,
    round_id: Optional[str] = None,
) -> Optional[WinnerAnnouncement]:
    if scope_kind == "matchday":
        scope_key = ("matchday", matchday)
        filter_kwargs = {"scope_kind": "matchday", "scope_matchday": matchday}
    elif scope_kind == "round":
        scope_key = ("round", round_id)
        filter_kwargs = {"scope_kind": "round", "scope_round_id": round_id}
    elif scope_kind == "global":
        scope_key = ("global", None)
        filter_kwargs = {"scope_kind": "global"}
    else:
        raise ValueError(scope_kind)

    if WinnerAnnouncement.objects.filter(**filter_kwargs).exists():
        return None

    result = matchday_winners(scope_key)
    if result.status != "resolved":
        return None

    ann = WinnerAnnouncement.objects.create(
        scope_kind=scope_kind,
        scope_matchday=matchday,
        scope_round_id=round_id,
        points=result.points,
        tied=result.tied,
        share=result.share,
    )
    if result.winners:
        ann.winners.set(result.winners)
    return ann
