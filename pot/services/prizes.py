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

    Si tras las 3 reglas siguen empatados, todos son ganadores y se reparte
    `PotSettings.matchday_winner_prize` a partes iguales.
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
    from pot.models import PotSettings

    winners = list(User.objects.filter(id__in=[r.player_id for r in rows]))
    prize = PotSettings.load().matchday_winner_prize
    share = (prize / len(winners)) if winners else Decimal("0")
    return WinnerResult(
        status="resolved",
        winners=winners,
        points=int(rows[0].pts),
        tied=len(winners) > 1,
        share=share,
    )
