"""Tests para el helper current_live_matches()."""

from datetime import timedelta

import pytest
from django.utils import timezone

from competition.models import LiveScore
from competition.services.live_view import current_live_matches
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_returns_live_and_awaiting_separately():
    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)
    awaiting = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=2))
    LiveScore.objects.create(
        match=awaiting, home_score=2, away_score=2, period="FT", minute=95
    )

    live_matches, awaiting_matches = current_live_matches()

    assert [m.id for m in live_matches] == [live.id]
    assert [m.id for m in awaiting_matches] == [awaiting.id]


@pytest.mark.django_db
def test_ignores_open_and_done_matches():
    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2))  # open
    done = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(days=2))
    done.result_home, done.result_away = 1, 0
    done.save()

    live_matches, awaiting_matches = current_live_matches()

    assert live_matches == []
    assert awaiting_matches == []


@pytest.mark.django_db
def test_orders_by_kickoff_ascending():
    grp = RoundFactory(id="groups", points=3, order=1)
    later = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=5))
    LiveScore.objects.create(match=later, home_score=0, away_score=0, period="1H", minute=5)
    earlier = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=80))
    LiveScore.objects.create(match=earlier, home_score=1, away_score=1, period="2H", minute=80)

    live_matches, _ = current_live_matches()

    assert [m.id for m in live_matches] == [earlier.id, later.id]


@pytest.mark.django_db
def test_returns_empty_lists_when_nothing_live():
    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2))

    live_matches, awaiting_matches = current_live_matches()

    assert live_matches == []
    assert awaiting_matches == []


@pytest.mark.django_db
def test_live_match_without_live_score_still_returned_as_live():
    """kickoff pasado pero sin LiveScore aún (cron no disparó): debe seguir
    contando como live (sin awaiting porque no hay period=FT)."""
    grp = RoundFactory(id="groups", points=3, order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=2))

    live_matches, awaiting_matches = current_live_matches()

    assert [x.id for x in live_matches] == [m.id]
    assert awaiting_matches == []
