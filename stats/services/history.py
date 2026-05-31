from collections import defaultdict

from competition.models import Match


def per_player_history() -> dict[int, list[dict]]:
    matches = list(
        Match.objects.filter(finished_at__isnull=False)
        .order_by("kickoff")
        .prefetch_related("predictions")
    )
    pts = defaultdict(int)
    history = defaultdict(list)
    for idx, m in enumerate(matches, start=1):
        for pred in m.predictions.all():
            pts[pred.player_id] += pred.earned or 0
        order = sorted(pts.items(), key=lambda x: -x[1])
        positions = {pid: pos for pos, (pid, _) in enumerate(order, start=1)}
        for pid, total in pts.items():
            history[pid].append({"idx": idx, "pts": total, "pos": positions[pid]})
    return dict(history)
