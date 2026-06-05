from dataclasses import dataclass, field
from decimal import Decimal

from competition.models import Match
from competition.services.standings import standings


@dataclass
class WinnerResult:
    status: str
    winners: list = field(default_factory=list)
    points: int = 0
    tied: bool = False
    share: Decimal = Decimal("0")


@dataclass
class PodiumEntry:
    position: int
    users: list = field(default_factory=list)
    prize_per_user: Decimal = Decimal("0")
    tied: bool = False


def _prizes_by_position_for(scope_kind: str) -> dict[int, Decimal]:
    from pot.models import PotSettings, Prize

    if scope_kind == "global":
        return {
            p.position: p.amount
            for p in Prize.objects.filter(scope="global", position__in=[1, 2, 3])
        }
    return {1: PotSettings.load().matchday_winner_prize}


def announcement_podium(announcement) -> list["PodiumEntry"]:
    """Top 3 plazas (1·2·3) del scope del anuncio, con su premio por jugador.

    Se computa al renderizar: la clasificación filtrada por scope es estable
    una vez resueltos los partidos, y los importes son los vigentes en el
    momento de mostrar el modal.
    """
    from itertools import groupby

    from accounts.models import User

    if announcement.scope_kind == "matchday":
        rows = standings(round_id="groups", matchday=announcement.scope_matchday)
    elif announcement.scope_kind == "round":
        rows = standings(round_id=announcement.scope_round_id)
    else:
        rows = standings()

    rows = [r for r in rows if r.pts > 0 and r.position <= 3]
    if not rows:
        return []

    prizes = _prizes_by_position_for(announcement.scope_kind)
    users_by_id = User.objects.in_bulk([r.player_id for r in rows])

    entries: list[PodiumEntry] = []
    for position, group_iter in groupby(rows, key=lambda r: r.position):
        group = list(group_iter)
        users = [users_by_id[r.player_id] for r in group if r.player_id in users_by_id]
        base = prizes.get(position, Decimal("0"))
        prize_per_user = (base / len(users)) if users else Decimal("0")
        entries.append(
            PodiumEntry(
                position=position,
                users=users,
                prize_per_user=prize_per_user,
                tied=len(users) > 1,
            )
        )
    return entries


def _matches_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return Match.objects.filter(round_id="groups", matchday=value)
    if kind == "round":
        return Match.objects.filter(round_id=value)
    if kind == "global":
        return Match.objects.all()
    raise ValueError(f"unknown scope: {kind}")


def _standings_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return standings(round_id="groups", matchday=value)
    if kind == "round":
        return standings(round_id=value)
    return standings()


def matchday_winners(scope_key) -> WinnerResult:
    """Ganador(es) del scope aplicando las 3 reglas: pts → exactos → aciertos.

    El premio a repartir depende del scope:
    - `matchday` y `round`: `PotSettings.matchday_winner_prize`.
    - `global`: `Prize[scope='global', position=1].amount` (premio del podio final).
    """
    matches = list(_matches_for_scope(scope_key))
    if not matches:
        return WinnerResult(status="pending")
    if any(m.result_home is None for m in matches):
        return WinnerResult(status="pending")

    rows = [r for r in _standings_for_scope(scope_key) if r.pts > 0 and r.position == 1]
    if not rows:
        return WinnerResult(status="desierto")

    from accounts.models import User

    winners = list(User.objects.filter(id__in=[r.player_id for r in rows]))
    prize = _prizes_by_position_for(scope_key[0]).get(1, Decimal("0"))
    share = (prize / len(winners)) if winners else Decimal("0")
    return WinnerResult(
        status="resolved",
        winners=winners,
        points=int(rows[0].pts),
        tied=len(winners) > 1,
        share=share,
    )
