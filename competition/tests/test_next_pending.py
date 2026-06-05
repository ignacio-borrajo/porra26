from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.services.predictions import (
    next_pending_match,
    pending_matches_count,
)
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
)


def _now():
    return timezone.now()


@pytest.fixture
def grp(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_returns_none_when_no_candidates(grp):
    u = UserFactory(must_change_password=False)
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_excludes_matches_with_official_result(grp):
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    m.result_home = 1
    m.result_away = 0
    m.save()
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_excludes_matches_with_user_prediction(grp):
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    PredictionFactory(player=u, match=m, home=1, away=0)
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_includes_match_when_only_other_user_predicted(grp):
    u = UserFactory(must_change_password=False)
    other = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    PredictionFactory(player=other, match=m, home=2, away=2)
    assert next_pending_match(u) == m
    assert pending_matches_count(u) == 1


@pytest.mark.django_db
def test_excludes_live_match(grp):
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() - timedelta(minutes=30))
    assert m.status == "live"
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_next_pending_ignores_matchday_order(grp):
    """Sin gate de jornada: el siguiente pendiente es siempre el de kickoff más
    próximo, independientemente de la jornada."""
    u = UserFactory(must_change_password=False)
    m1_md1 = MatchFactory(round=grp, matchday=1, kickoff=_now() + timedelta(days=2))
    MatchFactory(round=grp, matchday=2, kickoff=_now() + timedelta(days=3))
    assert next_pending_match(u) == m1_md1
    j1_earlier = MatchFactory(round=grp, matchday=1, kickoff=_now() + timedelta(days=1))
    assert next_pending_match(u) == j1_earlier


@pytest.mark.django_db
def test_orders_by_kickoff_asc(grp):
    u = UserFactory(must_change_password=False)
    later = MatchFactory(round=grp, kickoff=_now() + timedelta(days=2))
    earlier = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    assert next_pending_match(u) == earlier
    PredictionFactory(player=u, match=earlier, home=0, away=0)
    assert next_pending_match(u) == later


@pytest.mark.django_db
def test_after_match_excludes_given_match(grp):
    u = UserFactory(must_change_password=False)
    a = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    b = MatchFactory(round=grp, kickoff=_now() + timedelta(days=2))
    assert next_pending_match(u) == a
    assert next_pending_match(u, after_match=a) == b
    assert next_pending_match(u, after_match=b) == a
