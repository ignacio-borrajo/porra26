"""Helper para listar los partidos en juego y los pendientes de oficial.

Compartido entre el dashboard de Competición y la página de Rankings,
así no duplicamos la separación `live` vs `awaiting`.
"""

from __future__ import annotations

from django.utils import timezone

from competition.models import Match


def current_live_matches() -> tuple[list[Match], list[Match]]:
    """Devuelve `(live_matches, awaiting_matches)` ordenados por kickoff ASC.

    - `live_matches`: partidos con `status == 'live'` que NO están
      `awaiting_validation` (cron aún no ha visto FT o el live_score no es FT).
    - `awaiting_matches`: partidos con `status == 'live'` y `awaiting_validation`
      (FT en football-data pero el gestor no ha confirmado el oficial).

    Ambos quedan con `home`, `away`, `round` y `live_score` precargados.
    """
    qs = (
        Match.objects.filter(
            kickoff__lte=timezone.now(),
            result_home__isnull=True,
            result_away__isnull=True,
            home__isnull=False,
            away__isnull=False,
        )
        .select_related("home", "away", "round", "live_score")
        .order_by("kickoff")
    )
    live: list[Match] = []
    awaiting: list[Match] = []
    for m in qs:
        if m.awaiting_validation:
            awaiting.append(m)
        else:
            live.append(m)
    return live, awaiting
