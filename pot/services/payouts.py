from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

from competition.services.standings import standings
from pot.models import Prize


@dataclass
class PodiumPayout:
    player_id: int
    name: str
    position: int
    share: Decimal
    tied: bool
    group_size: int
    base_prize: Decimal


def podium_payouts() -> list[PodiumPayout]:
    """Reparto del bote del podio (P1·P2·P3) entre los jugadores que ocupan cada plaza.

    Cada plaza se reparte a partes iguales entre quienes la ocupen.
    Las plazas sin ocupantes con puntos quedan fuera del resultado.
    """
    rows = [r for r in standings() if r.pts > 0 and r.position <= 3]
    if not rows:
        return []
    base = {
        p.position: p.amount
        for p in Prize.objects.filter(scope="global", position__in=[1, 2, 3])
    }
    out: list[PodiumPayout] = []
    for position, group_iter in groupby(rows, key=lambda r: r.position):
        group = list(group_iter)
        base_prize = base.get(position, Decimal("0"))
        share = (base_prize / len(group)) if group else Decimal("0")
        for r in group:
            out.append(
                PodiumPayout(
                    player_id=r.player_id,
                    name=r.name,
                    position=position,
                    share=share,
                    tied=len(group) > 1,
                    group_size=len(group),
                    base_prize=base_prize,
                )
            )
    return out
