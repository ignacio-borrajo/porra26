from datetime import timedelta

import pytest
from django.utils import timezone
from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.history import per_player_history


@pytest.mark.django_db
def test_history_increments_per_resolved_match():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="A"); b = UserFactory(name="B")
    t0 = timezone.now()
    m1 = MatchFactory(round=grp, kickoff=t0, result_home=1, result_away=0, finished_at=t0)
    m2 = MatchFactory(round=grp, kickoff=t0 + timedelta(hours=1), result_home=2, result_away=2, finished_at=t0)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=a, match=m2, earned=0)
    PredictionFactory(player=b, match=m1, earned=1)
    PredictionFactory(player=b, match=m2, earned=3)
    h = per_player_history()
    assert h[a.id][-1]["pts"] == 3
    assert h[b.id][-1]["pts"] == 4
    assert h[b.id][-1]["pos"] == 1
