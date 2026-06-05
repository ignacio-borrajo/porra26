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
            ann_sede = _try_create("sede")
            if ann_sede is not None:
                created.append(ann_sede)

    return created


def _try_create(
    scope_kind: str,
    *,
    matchday: int | None = None,
    round_id: str | None = None,
) -> WinnerAnnouncement | None:
    if scope_kind == "matchday":
        filter_kwargs = {"scope_kind": "matchday", "scope_matchday": matchday}
    elif scope_kind == "round":
        filter_kwargs = {"scope_kind": "round", "scope_round_id": round_id}
    elif scope_kind == "global":
        filter_kwargs = {"scope_kind": "global"}
    elif scope_kind == "sede":
        filter_kwargs = {"scope_kind": "sede"}
    else:
        raise ValueError(scope_kind)

    if WinnerAnnouncement.objects.filter(**filter_kwargs).exists():
        return None

    if scope_kind == "sede":
        from decimal import Decimal

        from pot.services.prizes import sede_winners

        if Match.objects.filter(round_id="final", result_home__isnull=True).exists():
            return None
        sede_results = sede_winners()
        winners_users = [u for sw in sede_results if sw.status == "resolved" for u in sw.users]
        if not winners_users:
            return None
        ann = WinnerAnnouncement.objects.create(
            scope_kind="sede",
            scope_matchday=None,
            scope_round_id=None,
            points=0,
            tied=False,
            share=Decimal("0"),
        )
        ann.winners.set(winners_users)
        return ann

    scope_key = (
        scope_kind,
        matchday if scope_kind == "matchday" else round_id if scope_kind == "round" else None,
    )
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
