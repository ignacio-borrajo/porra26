from statistics import mean

from competition.models import Prediction
from competition.services.standings import standings


def donut(player_id: int) -> dict:
    rows = Prediction.objects.filter(player_id=player_id, earned__isnull=False).values_list(
        "earned", "match__exact_points_applied"
    )
    exact = partial = fail = 0
    for earned, exact_applied in rows:
        if exact_applied is not None and earned == exact_applied:
            exact += 1
        elif earned and earned > 0:
            partial += 1
        else:
            fail += 1
    return {"exact": exact, "partial": partial, "fail": fail}


def kpis(player) -> dict:
    s = standings()
    if not s:
        return {}
    me = next((r for r in s if r.player_id == player.id), None)
    if me is None:
        return {}
    avg = mean(r.pts for r in s)
    leader = s[0].pts
    d = donut(player.id)
    total = d["exact"] + d["partial"] + d["fail"]
    return {
        "pts": me.pts,
        "position": me.position,
        "total_players": len(s),
        "exact": me.exact_hits,
        "hits": me.hits,
        "hit_rate": me.hits / total if total else 0,
        "vs_avg": me.pts - avg,
        "vs_leader": leader - me.pts,
        "percentile": (me.position - 1) / len(s) * 100,
        "better_than": len(s) - me.position,
    }
