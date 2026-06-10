"""Tests del provider football-data.org sin tocar la red.

Mockeamos `urllib.request.urlopen` en el módulo del provider y comprobamos
que parsea bien la respuesta JSON y mapea los campos a `LiveScoreUpdate`.
"""

from __future__ import annotations

import io
import json
from unittest.mock import patch

import pytest

from competition.services.football_data import FootballDataProvider
from competition.services.live_scores import LiveScoreUpdate


def _resp(payload: dict, status: int = 200):
    class _FakeResp(io.BytesIO):
        def __init__(self, body: bytes):
            super().__init__(body)
            self.status = status

        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    return _FakeResp(json.dumps(payload).encode("utf-8"))


@pytest.fixture
def provider():
    return FootballDataProvider(api_key="test-key", competition_code="WC")


def test_provider_name():
    p = FootballDataProvider(api_key="x")
    assert p.name == "football-data.org"


@patch("competition.services.football_data.urlopen")
def test_fetch_returns_score_for_live_match(urlopen, provider):
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 12345,
                    "status": "IN_PLAY",
                    "minute": 67,
                    "score": {
                        "fullTime": {"home": 2, "away": 1},
                        "halfTime": {"home": 1, "away": 0},
                    },
                    "homeTeam": {"tla": "ARG"},
                    "awayTeam": {"tla": "BRA"},
                }
            ]
        }
    )

    out = provider.fetch(["12345"])

    assert out == [
        LiveScoreUpdate(
            external_id="12345",
            home_score=2,
            away_score=1,
            minute=67,
            period="2H",
        )
    ]


@patch("competition.services.football_data.urlopen")
def test_fetch_filters_out_matches_not_requested(urlopen, provider):
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 11111,
                    "status": "IN_PLAY",
                    "minute": 23,
                    "score": {"fullTime": {"home": 0, "away": 0}},
                    "homeTeam": {"tla": "A"},
                    "awayTeam": {"tla": "B"},
                },
                {
                    "id": 22222,
                    "status": "IN_PLAY",
                    "minute": 80,
                    "score": {"fullTime": {"home": 3, "away": 0}},
                    "homeTeam": {"tla": "C"},
                    "awayTeam": {"tla": "D"},
                },
            ]
        }
    )

    out = provider.fetch(["22222"])
    assert len(out) == 1
    assert out[0].external_id == "22222"
    assert out[0].home_score == 3


@patch("competition.services.football_data.urlopen")
def test_fetch_handles_halftime_status(urlopen, provider):
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 1,
                    "status": "PAUSED",
                    "minute": 45,
                    "score": {"fullTime": {"home": 1, "away": 1}},
                    "homeTeam": {"tla": "A"},
                    "awayTeam": {"tla": "B"},
                }
            ]
        }
    )
    out = provider.fetch(["1"])
    assert out[0].period == "HT"


@patch("competition.services.football_data.urlopen")
def test_fetch_handles_extra_time_status(urlopen, provider):
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 1,
                    "status": "IN_PLAY",
                    "minute": 105,
                    "score": {"fullTime": {"home": 2, "away": 2}},
                    "homeTeam": {"tla": "A"},
                    "awayTeam": {"tla": "B"},
                }
            ]
        }
    )
    out = provider.fetch(["1"])
    assert out[0].period == "ET"


@patch("competition.services.football_data.urlopen")
def test_fetch_handles_null_minute(urlopen, provider):
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 1,
                    "status": "IN_PLAY",
                    "minute": None,
                    "score": {"fullTime": {"home": 0, "away": 0}},
                    "homeTeam": {"tla": "A"},
                    "awayTeam": {"tla": "B"},
                }
            ]
        }
    )
    out = provider.fetch(["1"])
    assert out[0].minute is None
    assert out[0].home_score == 0


@patch("competition.services.football_data.urlopen")
def test_fetch_handles_null_score_treats_as_zero(urlopen, provider):
    """Football-data devuelve `null` en home/away cuando aún no ha empezado;
    si nos llega así para un IN_PLAY (raro pero defensivo), tratamos 0-0."""
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 1,
                    "status": "IN_PLAY",
                    "minute": 5,
                    "score": {"fullTime": {"home": None, "away": None}},
                    "homeTeam": {"tla": "A"},
                    "awayTeam": {"tla": "B"},
                }
            ]
        }
    )
    out = provider.fetch(["1"])
    assert out[0].home_score == 0
    assert out[0].away_score == 0


@patch("competition.services.football_data.urlopen")
def test_fetch_skips_finished_matches(urlopen, provider):
    """Si football-data marca FINISHED y nuestro tick aún lo pide, lo devolvemos
    como FT — el service decide si actualiza."""
    urlopen.return_value = _resp(
        {
            "matches": [
                {
                    "id": 1,
                    "status": "FINISHED",
                    "minute": 90,
                    "score": {"fullTime": {"home": 2, "away": 0}},
                    "homeTeam": {"tla": "A"},
                    "awayTeam": {"tla": "B"},
                }
            ]
        }
    )
    out = provider.fetch(["1"])
    assert out[0].period == "FT"


@patch("competition.services.football_data.urlopen")
def test_fetch_returns_empty_when_no_ids(urlopen, provider):
    out = provider.fetch([])
    assert out == []
    urlopen.assert_not_called()


@patch("competition.services.football_data.urlopen")
def test_fetch_sends_auth_header(urlopen, provider):
    urlopen.return_value = _resp({"matches": []})

    provider.fetch(["123"])

    request = urlopen.call_args.args[0]
    assert request.get_header("X-auth-token") == "test-key"


@patch("competition.services.football_data.urlopen")
def test_fetch_targets_competition_endpoint(urlopen, provider):
    urlopen.return_value = _resp({"matches": []})

    provider.fetch(["1"])

    request = urlopen.call_args.args[0]
    assert "competitions/WC/matches" in request.full_url
