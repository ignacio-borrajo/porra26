from datetime import timedelta

import pytest
from django.utils import timezone
from accounts.tests.factories import UserFactory
from competition.services.streak import streak
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_streak_counts_consecutive_hits_from_latest():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    u = UserFactory()
    base = timezone.now()
    for i, earned in enumerate([0, 1, 3, 1, 3]):
        m = MatchFactory(round=groups, kickoff=base + timedelta(hours=i),
                          result_home=1, result_away=0)
        PredictionFactory(player=u, match=m, earned=earned)
    assert streak(u.id) == 4


@pytest.mark.django_db
def test_streak_zero_if_latest_is_zero():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    u = UserFactory()
    base = timezone.now()
    for i, earned in enumerate([3, 1, 0]):
        m = MatchFactory(round=groups, kickoff=base + timedelta(hours=i),
                          result_home=1, result_away=0)
        PredictionFactory(player=u, match=m, earned=earned)
    assert streak(u.id) == 0


@pytest.mark.django_db
def test_streak_zero_if_no_resolved_predictions():
    u = UserFactory()
    assert streak(u.id) == 0
