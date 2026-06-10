"""Clasificación en directo: puntos congelados + puntos hipotéticos de los `LiveScore`.

Los puntos solo se congelan en `Prediction.earned` cuando el gestor confirma
el resultado oficial. Para mostrar "qué iría ganando cada uno si el partido
acabara como va ahora" recalculamos al vuelo combinando:

- `Prediction.earned` para partidos resueltos.
- `LiveScore` + `Prediction` para partidos en juego (puntos hipotéticos
  según el marcador parcial).

Es solo lectura — no escribe nada.
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, replace

from competition.models import LiveScore, Prediction
from competition.services.standings import StandingRow, standings


@dataclass
class LiveStandingRow(StandingRow):
    live_pts: int = 0


def _live_points_for(pred: Prediction, ls: LiveScore, round_) -> int:
    """Puntos que sumaría `pred` si el partido acabara con el marcador `ls`.

    Misma lógica que `services.score.score` pero usando los puntos
    configurados en `Round` (`points`, `partial_points`) en lugar de los
    congelados en `Match.exact_points_applied`, que aún no existen para un
    partido sin resolver.
    """
    if pred.home == ls.home_score and pred.away == ls.away_score:
        return round_.points
    pred_sign = (pred.home > pred.away) - (pred.home < pred.away)
    live_sign = (ls.home_score > ls.away_score) - (ls.home_score < ls.away_score)
    if pred_sign == live_sign:
        return round_.partial_points
    return 0


def _live_deltas(player_ids: Iterable[int] | None = None) -> dict[int, int]:
    """Suma puntos hipotéticos por jugador para partidos con LiveScore.

    Solo considera partidos **sin resolver** (sin `result_home`/`result_away`)
    para no duplicar con `standings()`, que ya cuenta los resueltos vía
    `Prediction.earned`.
    """
    qs = Prediction.objects.filter(
        match__live_score__isnull=False,
        match__result_home__isnull=True,
        match__result_away__isnull=True,
        player__is_active=True,
        player__is_jugador=True,
    ).select_related("match", "match__round", "match__live_score")
    if player_ids is not None:
        qs = qs.filter(player_id__in=list(player_ids))

    deltas: dict[int, int] = {}
    for pred in qs:
        ls = pred.match.live_score
        deltas[pred.player_id] = deltas.get(pred.player_id, 0) + _live_points_for(
            pred, ls, pred.match.round
        )
    return deltas


def live_standings(player_ids: Iterable[int] | None = None) -> list[LiveStandingRow]:
    """Clasificación general con `pts` (oficial) y `live_pts` (oficial + parciales).

    Reordenado por `live_pts`, así el podio "en directo" refleja el estado
    actual de los partidos. Si no hay ningún `LiveScore`, `live_pts == pts`
    y el orden es idéntico al de `standings()`.
    """
    base = standings(player_ids=player_ids)
    deltas = _live_deltas(player_ids)

    rows = [
        LiveStandingRow(**{**row.__dict__, "live_pts": row.pts + deltas.get(row.player_id, 0)})
        for row in base
    ]
    rows.sort(
        key=lambda r: (-r.live_pts, -r.exact_hits, -r.hits, r.name.lower()),
    )

    key_counts: dict[tuple[int, int, int], int] = {}
    for r in rows:
        k = (r.live_pts, r.exact_hits, r.hits)
        key_counts[k] = key_counts.get(k, 0) + 1

    out: list[LiveStandingRow] = []
    prev_key: tuple[int, int, int] | None = None
    position = 0
    for r in rows:
        key = (r.live_pts, r.exact_hits, r.hits)
        if key != prev_key:
            position += 1
            first = True
        else:
            first = False
        prev_key = key
        out.append(
            replace(
                r,
                position=position,
                is_tied=key_counts[key] > 1,
                is_first_in_tie=first,
            )
        )
    return out
