from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Sum

from competition.models import Match, Prediction


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


def matchday_winners(scope_key) -> WinnerResult:
    matches = list(_matches_for_scope(scope_key))
    if not matches:
        return WinnerResult(status="pending")
    if any(m.result_home is None for m in matches):
        return WinnerResult(status="pending")

    agg = (
        Prediction.objects.filter(match__in=matches, player__is_active=True)
        .values("player_id", "player__name")
        .annotate(p=Sum("earned"))
        .order_by("-p")
    )
    rows = [r for r in agg if (r["p"] or 0) > 0]
    if not rows:
        return WinnerResult(status="desierto")

    top = rows[0]["p"]
    winners_raw = [r for r in rows if r["p"] == top]

    from accounts.models import User

    winners = list(User.objects.filter(id__in=[w["player_id"] for w in winners_raw]))
    return WinnerResult(status="resolved", winners=winners, points=int(top), tied=len(winners) > 1)
