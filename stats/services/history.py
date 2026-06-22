from collections import defaultdict

from accounts.models import User
from competition.models import Match, Prediction
from competition.services.standings import standings


def build_chart_payload(me_id: int) -> dict:
    """Datos para las gráficas de la pantalla de estadísticas.

    Devuelve, para todos los jugadores activos ordenados por clasificación,
    las series temporales de puntos acumulados y de posición alineadas a los
    partidos finalizados (longitud = ``finished``), más los totales finales
    (rank/pts/hits/exact) que alimentan el donut y el panel comparativo.

    Las posiciones de cada partido se calculan con el mismo desempate base que
    ``standings`` permite reconstruir con los datos acumulados (puntos desc,
    nombre asc); la posición final autoritativa de cada jugador es ``rank``.
    """
    matches = list(Match.objects.filter(finished_at__isnull=False).order_by("kickoff", "id"))
    rows = standings()
    users = User.objects.in_bulk([r.player_id for r in rows])

    player_ids = [r.player_id for r in rows]
    name_of = {r.player_id: r.name for r in rows}

    earned: dict[int, dict[int, int]] = defaultdict(dict)
    if matches and player_ids:
        preds = Prediction.objects.filter(
            match_id__in=[m.id for m in matches],
            player_id__in=player_ids,
            earned__isnull=False,
        ).values_list("match_id", "player_id", "earned")
        for mid, pid, e in preds:
            earned[mid][pid] = e or 0

    cum = dict.fromkeys(player_ids, 0)
    pts_hist: dict[int, list[int]] = {pid: [] for pid in player_ids}
    rank_hist: dict[int, list[int]] = {pid: [] for pid in player_ids}
    for m in matches:
        em = earned.get(m.id, {})
        for pid in player_ids:
            cum[pid] += em.get(pid, 0)
        order = sorted(player_ids, key=lambda pid: (-cum[pid], name_of[pid].lower()))
        pos = {pid: i for i, pid in enumerate(order, start=1)}
        for pid in player_ids:
            pts_hist[pid].append(cum[pid])
            rank_hist[pid].append(pos[pid])

    players = []
    for r in rows:
        u = users.get(r.player_id)
        players.append(
            {
                "id": r.player_id,
                "name": r.name,
                "initials": u.initials if u else "?",
                "avatar_url": u.avatar.url if u and u.avatar else None,
                "rank": r.position,
                "pts": r.pts,
                "hits": r.hits,
                "exact": r.exact_hits,
                "pts_hist": pts_hist[r.player_id],
                "rank_hist": rank_hist[r.player_id],
            }
        )

    return {"me": me_id, "finished": len(matches), "players": players}
