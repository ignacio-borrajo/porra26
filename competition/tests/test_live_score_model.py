from datetime import timedelta

import pytest
from django.db import IntegrityError
from django.utils import timezone

from competition.models import LiveScore, Match
from competition.tests.factories import MatchFactory


@pytest.mark.django_db
def test_live_score_one_to_one_with_match():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30))
    LiveScore.objects.create(match=match, home_score=1, away_score=0, minute=42)

    with pytest.raises(IntegrityError):
        LiveScore.objects.create(match=match, home_score=2, away_score=0, minute=50)


@pytest.mark.django_db
def test_live_score_period_defaults_to_first_half():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10))
    ls = LiveScore.objects.create(match=match)
    assert ls.period == LiveScore.PERIOD_PRE
    assert ls.home_score == 0
    assert ls.away_score == 0


@pytest.mark.django_db
def test_live_score_reverse_accessor_on_match():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=5))
    LiveScore.objects.create(match=match, home_score=3, away_score=2, minute=85)
    match.refresh_from_db()
    assert match.live_score.home_score == 3
    assert match.live_score.away_score == 2


@pytest.mark.django_db
def test_match_external_id_optional_and_unique():
    Match._meta.get_field("external_id")
    m1 = MatchFactory(external_id="api-football-1234")
    assert m1.external_id == "api-football-1234"

    m2 = MatchFactory()
    assert m2.external_id is None or m2.external_id == ""

    with pytest.raises(IntegrityError):
        MatchFactory(external_id="api-football-1234")
