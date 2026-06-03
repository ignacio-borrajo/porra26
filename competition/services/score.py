from __future__ import annotations


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def score(pred, match) -> int | None:
    """Puntos ganados por un pronóstico tras resolver el partido."""
    if match.result_home is None or match.result_away is None:
        return None
    if pred.home == match.result_home and pred.away == match.result_away:
        return match.exact_points_applied
    if _sign(pred.home - pred.away) == _sign(match.result_home - match.result_away):
        return match.partial_points_applied
    return 0
