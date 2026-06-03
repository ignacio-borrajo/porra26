from dataclasses import dataclass

from django.db.models import Count, F, Q, Sum

from accounts.models import User
from competition.models import Match, Prediction


@dataclass
class StandingRow:
    position: int
    player_id: int
    name: str
    email: str
    pts: int
    hits: int
    exact_hits: int
    streak: int = 0
    trend: str = "flat"  # "up" | "down" | "flat"


def standings(round_id: str | None = None, matchday: int | None = None) -> list[StandingRow]:
    """Clasificación general o limitada a una ronda y/o jornada.

    Con `round_id`/`matchday` solo se suman los puntos de las predicciones cuyo
    partido cae dentro del scope. Para esos scopes locales no se calculan
    `streak` ni `trend` (no aportan información útil de una sola jornada/ronda).
    """
    scoped = round_id is not None or matchday is not None
    qs = Prediction.objects.filter(
        player__is_active=True, player__is_jugador=True, earned__isnull=False
    )
    if round_id is not None:
        qs = qs.filter(match__round_id=round_id)
    if matchday is not None:
        qs = qs.filter(match__matchday=matchday)

    rows = list(
        qs.values("player_id", "player__name", "player__email").annotate(
            pts=Sum("earned"),
            hits=Count("id", filter=Q(earned__gt=0)),
            exact_hits=Count("id", filter=Q(earned=F("match__exact_points_applied"))),
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
        for u in User.objects.filter(is_active=True, is_jugador=True).exclude(id__in=seen)
    ]
    merged = list(rows) + extras
    merged.sort(
        key=lambda r: (-(r["pts"] or 0), -r["exact_hits"], -r["hits"], r["player__name"].lower())
    )

    if scoped:
        streaks: dict[int, int] = {}
        trends: dict[int, str] = {}
    else:
        player_ids = [r["player_id"] for r in merged]
        streaks = _compute_streaks(player_ids)
        trends = _compute_trends(merged)

    out = []
    for i, r in enumerate(merged, start=1):
        pid = r["player_id"]
        out.append(
            StandingRow(
                position=i,
                player_id=pid,
                name=r["player__name"],
                email=r["player__email"],
                pts=int(r["pts"] or 0),
                hits=int(r["hits"]),
                exact_hits=int(r["exact_hits"]),
                streak=streaks.get(pid, 0),
                trend=trends.get(pid, "flat"),
            )
        )
    return out


def _compute_streaks(player_ids: list[int]) -> dict[int, int]:
    """Racha de aciertos consecutivos en los partidos finalizados más recientes.

    Se cuenta hacia atrás desde el último partido finalizado en el que el
    jugador apostó (no apostar también rompe la racha)."""
    if not player_ids:
        return {}
    matches = list(
        Match.objects.filter(finished_at__isnull=False)
        .order_by("-finished_at", "-kickoff", "-id")
        .values_list("id", flat=True)
    )
    if not matches:
        return {pid: 0 for pid in player_ids}

    preds = Prediction.objects.filter(
        player_id__in=player_ids, match_id__in=matches, earned__isnull=False
    ).values_list("player_id", "match_id", "earned")
    by_player: dict[int, dict[int, int]] = {}
    for pid, mid, earned in preds:
        by_player.setdefault(pid, {})[mid] = earned or 0

    streaks: dict[int, int] = {}
    for pid in player_ids:
        per_match = by_player.get(pid, {})
        count = 0
        for mid in matches:
            earned = per_match.get(mid)
            if earned is None or earned <= 0:
                break
            count += 1
        streaks[pid] = count
    return streaks


def _compute_trends(merged: list[dict]) -> dict[int, str]:
    """Tendencia respecto al estado previo al último partido finalizado.

    Se reconstruye la clasificación restando los puntos del último partido
    finalizado y se compara la posición previa con la actual."""
    last_match = (
        Match.objects.filter(finished_at__isnull=False).order_by("-finished_at", "-id").first()
    )
    current_positions = {row["player_id"]: idx for idx, row in enumerate(merged, start=1)}
    if last_match is None:
        return {pid: "flat" for pid in current_positions}

    delta = {
        p.player_id: (p.earned or 0)
        for p in Prediction.objects.filter(match_id=last_match.id, earned__isnull=False)
    }
    prev = []
    for r in merged:
        pid = r["player_id"]
        prev.append(
            {
                "player_id": pid,
                "pts": (r["pts"] or 0) - delta.get(pid, 0),
                "exact_hits": r["exact_hits"]
                - (1 if delta.get(pid, 0) == last_match.exact_points_applied else 0),
                "hits": r["hits"] - (1 if delta.get(pid, 0) > 0 else 0),
                "name": r["player__name"],
            }
        )
    prev.sort(key=lambda r: (-r["pts"], -r["exact_hits"], -r["hits"], r["name"].lower()))
    prev_positions = {r["player_id"]: idx for idx, r in enumerate(prev, start=1)}

    trends: dict[int, str] = {}
    for pid, pos in current_positions.items():
        before = prev_positions.get(pid, pos)
        if pos < before:
            trends[pid] = "up"
        elif pos > before:
            trends[pid] = "down"
        else:
            trends[pid] = "flat"
    return trends
