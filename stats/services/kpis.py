from statistics import mean
from competition.services.standings import standings
from competition.models import Prediction


def donut(player_id: int) -> dict:
    rows = (
        Prediction.objects.filter(player_id=player_id, earned__isnull=False)
        .values_list("earned", "match__round__points")
    )
    exact = partial = fail = 0
    for earned, round_points in rows:
        if earned == round_points:
            exact += 1
        elif earned > 0:
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
