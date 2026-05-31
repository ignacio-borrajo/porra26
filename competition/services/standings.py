from dataclasses import dataclass

from django.db.models import Count, F, Q, Sum

from accounts.models import User
from competition.models import Prediction


@dataclass
class StandingRow:
    position: int
    player_id: int
    name: str
    email: str
    pts: int
    hits: int
    exact_hits: int


def standings() -> list[StandingRow]:
    rows = list(
        Prediction.objects.filter(player__is_active=True, earned__isnull=False)
        .values("player_id", "player__name", "player__email")
        .annotate(
            pts=Sum("earned"),
            hits=Count("id", filter=Q(earned__gt=0)),
            exact_hits=Count("id", filter=Q(earned=F("match__round__points"))),
        )
    )

    seen = {r["player_id"] for r in rows}
    extras = [
        {
            "player_id": u.id,
            "player__name": u.name,
            "player__email": u.email,
            "pts": 0,
            "hits": 0,
            "exact_hits": 0,
        }
        for u in User.objects.filter(is_active=True).exclude(id__in=seen)
    ]
    merged = list(rows) + extras
    merged.sort(
        key=lambda r: (-(r["pts"] or 0), -r["exact_hits"], -r["hits"], r["player__name"].lower())
    )

    out = []
    for i, r in enumerate(merged, start=1):
        out.append(
            StandingRow(
                position=i,
                player_id=r["player_id"],
                name=r["player__name"],
                email=r["player__email"],
                pts=int(r["pts"] or 0),
                hits=int(r["hits"]),
                exact_hits=int(r["exact_hits"]),
            )
        )
    return out
