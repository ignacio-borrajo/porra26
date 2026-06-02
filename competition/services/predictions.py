from __future__ import annotations

from competition.models import Match


def _candidates(user, after_match=None):
    qs = Match.objects.filter(result_home__isnull=True).exclude(predictions__player=user)
    if after_match is not None:
        qs = qs.exclude(pk=after_match.pk)
    return qs.select_related("round").order_by("kickoff", "pk")


def next_pending_match(user, after_match=None) -> Match | None:
    """Siguiente partido pronosticable por `user` sin Prediction suya.

    `predictions_open` depende de `now()` y del gate de jornada; iteramos
    sobre los candidatos del ORM y filtramos en Python.
    """
    for m in _candidates(user, after_match=after_match):
        if m.predictions_open:
            return m
    return None


def pending_matches_count(user) -> int:
    return sum(1 for m in _candidates(user) if m.predictions_open)


def _result_candidates(after_match=None):
    qs = Match.objects.filter(result_home__isnull=True).select_related("round")
    if after_match is not None:
        qs = qs.exclude(pk=after_match.pk)
    return qs.order_by("kickoff", "pk")


def next_pending_result_match(after_match=None) -> Match | None:
    for m in _result_candidates(after_match=after_match):
        if m.status in ("closed", "live"):
            return m
    return None


def pending_result_matches_count() -> int:
    return sum(1 for m in _result_candidates() if m.status in ("closed", "live"))
