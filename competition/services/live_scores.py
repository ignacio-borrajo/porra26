"""Polling de marcadores parciales contra un sports API externo.

Arquitectura: ver `docs/PLAN.md` §Fase 9. El cron externo golpea
`POST /competicion/api/teams/live/tick/`, la vista invoca `tick()` y este
service decide a quién llamar y qué persistir.

`Match.result_home` y `Match.result_away` quedan intocables — solo cambian
desde la pantalla del gestor (resultado oficial).
"""

from __future__ import annotations

import logging
from collections.abc import Iterable
from dataclasses import dataclass
from typing import Protocol

from django.utils import timezone

from competition.models import LiveScore, Match

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class LiveScoreUpdate:
    external_id: str
    home_score: int
    away_score: int
    minute: int | None = None
    period: str = LiveScore.PERIOD_FIRST_HALF


class LiveScoreProvider(Protocol):
    name: str

    def fetch(self, external_ids: Iterable[str]) -> list[LiveScoreUpdate]:
        """Devuelve los marcadores conocidos para los IDs solicitados.

        Puede omitir IDs sin datos. Si lanza una excepción, el tick lo
        absorbe y lo contabiliza en `errors` sin propagar a la vista.
        """
        ...


def _live_matches_with_external_id() -> tuple[list[Match], int]:
    """Devuelve (matches con external_id, nº de matches live sin external_id).

    "Live" = kickoff pasó y no hay resultado oficial. Es la misma definición
    que la propiedad `Match.status` ("live"), pero la implementamos a nivel
    de queryset para no traer todos los matches del torneo a memoria.
    """
    now = timezone.now()
    base = Match.objects.filter(
        kickoff__lte=now,
        result_home__isnull=True,
        result_away__isnull=True,
        home__isnull=False,
        away__isnull=False,
    )
    with_eid = list(base.exclude(external_id__isnull=True).exclude(external_id=""))
    skipped = base.filter(external_id__isnull=True).count() + base.filter(external_id="").count()
    return with_eid, skipped


def tick(provider: LiveScoreProvider) -> dict:
    """Procesa un disparo del cron: actualiza marcadores de partidos en juego.

    Retorna un resumen para logging y la respuesta del endpoint. Nunca lanza
    aunque el provider falle, así un crash del API externo no rompe el cron.
    """
    matches, skipped = _live_matches_with_external_id()
    summary: dict = {
        "processed": 0,
        "created": 0,
        "updated": 0,
        "skipped_no_external_id": skipped,
        "errors": 0,
        "provider": getattr(provider, "name", "unknown"),
    }
    if not matches:
        return summary

    external_ids = [m.external_id for m in matches]
    try:
        updates = provider.fetch(external_ids)
    except Exception:  # noqa: BLE001
        logger.exception("live_scores: provider %s falló al hacer fetch", summary["provider"])
        summary["errors"] = 1
        return summary

    by_eid = {u.external_id: u for u in updates}
    for match in matches:
        update = by_eid.get(match.external_id)
        if update is None:
            continue
        try:
            _, created = LiveScore.objects.update_or_create(
                match=match,
                defaults={
                    "home_score": update.home_score,
                    "away_score": update.away_score,
                    "minute": update.minute,
                    "period": update.period,
                    "source": summary["provider"],
                },
            )
        except Exception:  # noqa: BLE001
            logger.exception("live_scores: fallo persistiendo match=%s", match.id)
            summary["errors"] += 1
            continue
        summary["processed"] += 1
        if created:
            summary["created"] += 1
        else:
            summary["updated"] += 1
    return summary
