from datetime import timedelta

import pytest
from django.utils import timezone

from competition.models import LiveScore
from competition.services.live_scores import (
    LiveScoreProvider,
    LiveScoreUpdate,
    tick,
)
from competition.tests.factories import MatchFactory


class StubProvider(LiveScoreProvider):
    """Provider determinista para tests. Devuelve los updates que se le pasen."""

    name = "stub"

    def __init__(self, by_external_id=None, fail=False):
        self.by_external_id = by_external_id or {}
        self.fail = fail
        self.calls = []

    def fetch(self, external_ids):
        self.calls.append(list(external_ids))
        if self.fail:
            raise RuntimeError("provider boom")
        out = []
        for eid in external_ids:
            payload = self.by_external_id.get(eid)
            if payload is not None:
                out.append(payload)
        return out


def _live_match(**kwargs):
    kwargs.setdefault("kickoff", timezone.now() - timedelta(minutes=30))
    return MatchFactory(**kwargs)


@pytest.mark.django_db
def test_tick_with_no_live_matches_does_not_call_provider():
    MatchFactory(kickoff=timezone.now() + timedelta(hours=2), external_id="ext-1")
    provider = StubProvider()

    summary = tick(provider=provider)

    assert summary["processed"] == 0
    assert summary["updated"] == 0
    assert summary["created"] == 0
    assert provider.calls == []


@pytest.mark.django_db
def test_tick_skips_live_matches_without_external_id():
    _live_match(external_id=None)
    provider = StubProvider()

    summary = tick(provider=provider)

    assert summary["processed"] == 0
    assert summary["skipped_no_external_id"] == 1
    assert provider.calls == []


@pytest.mark.django_db
def test_tick_creates_live_score_for_live_match():
    match = _live_match(external_id="ext-100")
    provider = StubProvider(
        by_external_id={
            "ext-100": LiveScoreUpdate(
                external_id="ext-100", home_score=1, away_score=0, minute=23, period="1H"
            )
        }
    )

    summary = tick(provider=provider)

    assert summary["processed"] == 1
    assert summary["created"] == 1
    assert summary["updated"] == 0
    ls = LiveScore.objects.get(match=match)
    assert ls.home_score == 1
    assert ls.away_score == 0
    assert ls.minute == 23
    assert ls.period == "1H"
    assert ls.source == "stub"


@pytest.mark.django_db
def test_tick_updates_existing_live_score():
    match = _live_match(external_id="ext-200")
    LiveScore.objects.create(match=match, home_score=0, away_score=0, minute=10, period="1H")
    provider = StubProvider(
        by_external_id={
            "ext-200": LiveScoreUpdate(
                external_id="ext-200", home_score=2, away_score=1, minute=72, period="2H"
            )
        }
    )

    summary = tick(provider=provider)

    assert summary["created"] == 0
    assert summary["updated"] == 1
    ls = LiveScore.objects.get(match=match)
    assert (ls.home_score, ls.away_score, ls.minute, ls.period) == (2, 1, 72, "2H")


@pytest.mark.django_db
def test_tick_does_not_touch_official_result():
    match = _live_match(external_id="ext-300")
    provider = StubProvider(
        by_external_id={
            "ext-300": LiveScoreUpdate(
                external_id="ext-300", home_score=3, away_score=3, minute=90, period="FT"
            )
        }
    )

    tick(provider=provider)

    match.refresh_from_db()
    assert match.result_home is None
    assert match.result_away is None
    assert match.finished_at is None


@pytest.mark.django_db
def test_tick_handles_provider_exception():
    _live_match(external_id="ext-400")
    provider = StubProvider(fail=True)

    summary = tick(provider=provider)

    assert summary["errors"] == 1
    assert summary["processed"] == 0
    assert not LiveScore.objects.exists()


@pytest.mark.django_db
def test_tick_ignores_done_matches():
    match = MatchFactory(
        kickoff=timezone.now() - timedelta(hours=3),
        external_id="ext-500",
        result_home=2,
        result_away=1,
    )
    provider = StubProvider(
        by_external_id={
            "ext-500": LiveScoreUpdate(
                external_id="ext-500", home_score=2, away_score=1, minute=90, period="FT"
            )
        }
    )

    summary = tick(provider=provider)

    assert summary["processed"] == 0
    assert provider.calls == []
    assert not LiveScore.objects.filter(match=match).exists()
