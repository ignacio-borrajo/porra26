"""Provider real contra football-data.org (tier gratuito).

Hace una sola llamada por tick:
`GET /v4/competitions/{code}/matches?status=LIVE,IN_PLAY,PAUSED`

Devuelve **todos** los partidos en juego de la competición; filtramos en
Python contra los `external_ids` que nos pide el service. Eso evita N
llamadas (una por partido) y respeta el rate limit del tier gratis
(~10 req/min).

`external_id` se almacena en `Match.external_id` como el ID numérico de
football-data convertido a string. El comando `seed_match_external_ids`
rellena ese campo casando por fecha + TLA de equipos.
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from competition.models import LiveScore
from competition.services.live_scores import LiveScoreUpdate

logger = logging.getLogger(__name__)


_STATUS_TO_PERIOD = {
    "SCHEDULED": LiveScore.PERIOD_PRE,
    "TIMED": LiveScore.PERIOD_PRE,
    "POSTPONED": LiveScore.PERIOD_PRE,
    "PAUSED": LiveScore.PERIOD_HALFTIME,
    "FINISHED": LiveScore.PERIOD_FULL_TIME,
    "AWARDED": LiveScore.PERIOD_FULL_TIME,
}


def _period_from(status: str, minute: int | None) -> str:
    mapped = _STATUS_TO_PERIOD.get(status)
    if mapped is not None:
        return mapped
    if status != "IN_PLAY":
        return LiveScore.PERIOD_FIRST_HALF
    if minute is None:
        return LiveScore.PERIOD_FIRST_HALF
    if minute <= 45:
        return LiveScore.PERIOD_FIRST_HALF
    if minute <= 90:
        return LiveScore.PERIOD_SECOND_HALF
    if minute <= 120:
        return LiveScore.PERIOD_EXTRA_TIME
    return LiveScore.PERIOD_PENALTIES


class FootballDataProvider:
    """Consulta marcadores en vivo de football-data.org.

    Pensado para el Mundial (`competition_code="WC"`) en el tier gratuito.
    """

    name = "football-data.org"

    def __init__(
        self,
        api_key: str,
        competition_code: str = "WC",
        base_url: str = "https://api.football-data.org/v4",
        timeout: float = 10.0,
    ):
        self.api_key = api_key
        self.competition_code = competition_code
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def fetch(self, external_ids: Iterable[str]) -> list[LiveScoreUpdate]:
        wanted = {str(eid) for eid in external_ids}
        if not wanted:
            return []

        params = urlencode({"status": "LIVE,IN_PLAY,PAUSED"})
        url = f"{self.base_url}/competitions/{self.competition_code}/matches?{params}"
        request = Request(
            url,
            headers={"X-Auth-Token": self.api_key, "Accept": "application/json"},
        )
        with urlopen(request, timeout=self.timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))

        out: list[LiveScoreUpdate] = []
        for match in payload.get("matches", []):
            eid = str(match.get("id"))
            if eid not in wanted:
                continue
            score = (match.get("score") or {}).get("fullTime") or {}
            home = score.get("home") or 0
            away = score.get("away") or 0
            minute = match.get("minute")
            status = match.get("status", "")
            out.append(
                LiveScoreUpdate(
                    external_id=eid,
                    home_score=int(home),
                    away_score=int(away),
                    minute=minute if minute is not None else None,
                    period=_period_from(status, minute),
                )
            )
        return out
