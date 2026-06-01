from dataclasses import dataclass, field

from accounts.models import User
from competition.models import Match, Prediction


@dataclass
class ClosingStats:
    total_players: int
    bets_count: int
    absent_names: list[str] = field(default_factory=list)
    most_popular: list[tuple[str, int]] = field(default_factory=list)
    split_home: int = 0
    split_draw: int = 0
    split_away: int = 0

    @property
    def split_total(self) -> int:
        return self.split_home + self.split_draw + self.split_away


def compute_closing_stats(match: Match) -> ClosingStats:
    active_jugadores = list(
        User.objects.filter(is_jugador=True, is_active=True).order_by("name")
    )
    preds = list(
        Prediction.objects.filter(match=match).select_related("player")
    )
    bettor_ids = {p.player_id for p in preds}
    absent_names = [u.name for u in active_jugadores if u.id not in bettor_ids]

    counter: dict[str, int] = {}
    split_home = split_draw = split_away = 0
    for p in preds:
        key = f"{p.home}-{p.away}"
        counter[key] = counter.get(key, 0) + 1
        if p.home > p.away:
            split_home += 1
        elif p.home == p.away:
            split_draw += 1
        else:
            split_away += 1

    most_popular: list[tuple[str, int]] = []
    if counter:
        top = max(counter.values())
        most_popular = sorted(
            [(k, v) for k, v in counter.items() if v == top],
            key=lambda kv: kv[0],
        )

    return ClosingStats(
        total_players=len(active_jugadores),
        bets_count=len(preds),
        absent_names=absent_names,
        most_popular=most_popular,
        split_home=split_home,
        split_draw=split_draw,
        split_away=split_away,
    )
