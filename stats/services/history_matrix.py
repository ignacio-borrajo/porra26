"""Construye la matriz jugador × partido para la página de Histórico.

Entran los partidos cuyo plazo de apuestas ya ha cerrado: tanto los finalizados
(con resultado oficial) como los que están en juego o a la espera de resultado
(`kickoff <= now`). Los partidos abiertos (apuestas activas) y los KO sin
equipos asignados quedan fuera. El orden es cronológico (kickoff ascendente).

Los jugadores van en el mismo orden que la clasificación general (gestores
puros excluidos). Cada celda es el pronóstico del jugador para ese partido,
etiquetado por estado:

- ``exact``   — marcador exacto (puntos == ``exact_points_applied``).
- ``partial`` — acierto 1·X·2 (``earned > 0`` y no exacto).
- ``miss``    — pronosticó pero falló (``earned == 0``).
- ``pending`` — pronosticó y el partido aún no tiene resultado oficial.
- ``empty``   — no apostó.
"""

from dataclasses import dataclass

from django.utils import timezone

from competition.models import Match, Prediction
from competition.services.standings import standings


@dataclass(frozen=True)
class HistoryMatch:
    id: int
    home_code: str
    home_name: str
    home_flag: str
    away_code: str
    away_name: str
    away_flag: str
    result_home: int | None
    result_away: int | None
    resolved: bool


@dataclass(frozen=True)
class HistoryPlayer:
    id: int
    name: str
    initials: str
    position: int


@dataclass(frozen=True)
class HistoryCell:
    state: str  # "exact" | "partial" | "miss" | "pending" | "empty"
    home: int | None
    away: int | None


@dataclass(frozen=True)
class HistoryMatrix:
    matches: list[HistoryMatch]
    players: list[HistoryPlayer]
    cells: dict[int, dict[int, HistoryCell]]  # player_id -> match_id -> Cell
    totals: dict[int, int]  # player_id -> total pts


_EMPTY = HistoryCell(state="empty", home=None, away=None)


def build_matrix() -> HistoryMatrix:
    now = timezone.now()
    matches_qs = (
        Match.objects.filter(kickoff__lte=now, home__isnull=False, away__isnull=False)
        .select_related("home", "away")
        .order_by("kickoff", "id")
    )
    matches = [
        HistoryMatch(
            id=m.id,
            home_code=m.home.code,
            home_name=m.home.name,
            home_flag=m.home.flag,
            away_code=m.away.code,
            away_name=m.away.name,
            away_flag=m.away.flag,
            result_home=m.result_home,
            result_away=m.result_away,
            resolved=m.finished_at is not None,
        )
        for m in matches_qs
    ]
    match_ids = [m.id for m in matches]
    resolved_ids = {m.id for m in matches if m.resolved}
    exact_by_match = {m.id: m.exact_points_applied for m in matches_qs}

    rows = standings()
    players = [
        HistoryPlayer(
            id=r.player_id,
            name=r.name,
            initials="".join(p[0] for p in r.name.split() if p)[:2].upper(),
            position=r.position,
        )
        for r in rows
    ]
    totals = {r.player_id: r.pts for r in rows}
    player_ids = [p.id for p in players]

    cells: dict[int, dict[int, HistoryCell]] = {pid: {} for pid in player_ids}
    if match_ids and player_ids:
        preds = Prediction.objects.filter(
            match_id__in=match_ids, player_id__in=player_ids
        ).values_list("player_id", "match_id", "home", "away", "earned")
        for player_id, match_id, home, away, earned in preds:
            if match_id not in resolved_ids:
                state = "pending"
            else:
                exact_pts = exact_by_match.get(match_id)
                if earned is None:
                    state = "pending"
                elif earned == exact_pts:
                    state = "exact"
                elif earned > 0:
                    state = "partial"
                else:
                    state = "miss"
            cells[player_id][match_id] = HistoryCell(state=state, home=home, away=away)

    for pid in player_ids:
        for mid in match_ids:
            cells[pid].setdefault(mid, _EMPTY)

    return HistoryMatrix(matches=matches, players=players, cells=cells, totals=totals)
