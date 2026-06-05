from competition.models import Match
from pot.services.prizes import matchday_winners

from .models import WinnerAnnouncement


def detect_after_match(match: Match) -> list[WinnerAnnouncement]:
    """Llamado tras resolve_match(). Crea (idempotentemente) los anuncios de
    ganador del scope al que pertenece el partido recién resuelto, si ese scope
    acaba de cerrarse. Devuelve los anuncios creados en esta llamada (0..N).

    Reglas:
    - Cualquier partido de la fase de grupos: 1 anuncio matchday(N) si la
      jornada N acaba de cerrar.
    - r32/r16/qf/sf: ningún anuncio (esperan a que la Final cierre la jornada
      eliminatoria entera).
    - final: 3 anuncios simultáneos (ko → sede → global) en ese orden, para
      que el feed de modales muestre la jornada KO primero, luego sede y por
      último el campeón del Mundial (climax).
    """
    created: list[WinnerAnnouncement] = []

    if match.round_id == "groups" and match.matchday is not None:
        ann = _try_create("matchday", matchday=match.matchday)
        if ann is not None:
            created.append(ann)
    elif match.round_id == "final":
        for kind in ("ko", "sede", "global"):
            ann = _try_create(kind)
            if ann is not None:
                created.append(ann)

    return created


def _try_create(
    scope_kind: str,
    *,
    matchday: int | None = None,
) -> WinnerAnnouncement | None:
    if scope_kind == "matchday":
        filter_kwargs = {"scope_kind": "matchday", "scope_matchday": matchday}
    elif scope_kind in ("ko", "global", "sede"):
        filter_kwargs = {"scope_kind": scope_kind}
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
            points=0,
            tied=False,
            share=Decimal("0"),
        )
        ann.winners.set(winners_users)
        return ann

    scope_key = (
        scope_kind,
        matchday if scope_kind == "matchday" else None,
    )
    result = matchday_winners(scope_key)
    if result.status != "resolved":
        return None

    ann = WinnerAnnouncement.objects.create(
        scope_kind=scope_kind,
        scope_matchday=matchday,
        points=result.points,
        tied=result.tied,
        share=result.share,
    )
    if result.winners:
        ann.winners.set(result.winners)
    return ann
