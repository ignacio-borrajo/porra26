from datetime import timedelta
from unittest.mock import patch

import pytest
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from competition.api.views import _build_default_provider
from competition.services.football_data import FootballDataProvider
from competition.services.live_scores import LiveScoreUpdate
from competition.tests.factories import MatchFactory

URL_NAME = "competicion:api:live_tick"
TOKEN = "live-test-token-1234567890"


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_endpoint_rejects_missing_token(client):
    res = client.post(reverse(URL_NAME))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_endpoint_rejects_wrong_token(client):
    res = client.post(reverse(URL_NAME), HTTP_AUTHORIZATION="Bearer wrong-token")
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_endpoint_rejects_get(client):
    res = client.get(reverse(URL_NAME), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert res.status_code in (405, 401)


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_endpoint_returns_204_when_no_live_matches(client):
    MatchFactory(kickoff=timezone.now() + timedelta(hours=2), external_id="ext-future")
    with patch("competition.api.views.tick") as tick_mock:
        tick_mock.return_value = {
            "processed": 0,
            "created": 0,
            "updated": 0,
            "skipped_no_external_id": 0,
            "errors": 0,
            "provider": "stub",
        }
        res = client.post(reverse(URL_NAME), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert res.status_code == 204


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_endpoint_returns_summary_when_live_match_updated(client):
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=10), external_id="ext-live-1")
    with patch("competition.api.views.tick") as tick_mock:
        tick_mock.return_value = {
            "processed": 1,
            "created": 1,
            "updated": 0,
            "skipped_no_external_id": 0,
            "errors": 0,
            "provider": "stub",
        }
        res = client.post(reverse(URL_NAME), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert data["processed"] == 1
    assert data["created"] == 1


@override_settings(FOOTBALL_DATA_API_KEY="")
def test_default_provider_is_noop_without_api_key():
    provider = _build_default_provider()
    assert provider.name == "noop"
    assert provider.fetch(["123"]) == []


@override_settings(FOOTBALL_DATA_API_KEY="real-key", FOOTBALL_DATA_COMPETITION="WC")
def test_default_provider_is_football_data_with_api_key():
    provider = _build_default_provider()
    assert isinstance(provider, FootballDataProvider)
    assert provider.api_key == "real-key"
    assert provider.competition_code == "WC"


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_endpoint_invokes_real_service_path(client):
    MatchFactory(kickoff=timezone.now() - timedelta(minutes=10), external_id="ext-live-real")
    with patch("competition.api.views._build_default_provider") as build_mock:
        provider = build_mock.return_value
        provider.name = "fake-real"
        provider.fetch.return_value = [
            LiveScoreUpdate(
                external_id="ext-live-real",
                home_score=2,
                away_score=2,
                minute=88,
                period="2H",
            )
        ]
        res = client.post(reverse(URL_NAME), HTTP_AUTHORIZATION=f"Bearer {TOKEN}")
    assert res.status_code == 200
    data = res.json()
    assert data["processed"] == 1
    assert data["created"] == 1
    assert data["provider"] == "fake-real"
