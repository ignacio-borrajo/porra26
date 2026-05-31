import pytest
from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.kpis import kpis, donut


@pytest.mark.django_db
def test_donut_segments():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    u = UserFactory()
    for earned in (3, 1, 1, 0):
        m = MatchFactory(round=grp, result_home=1, result_away=0)
        PredictionFactory(player=u, match=m, earned=earned)
    d = donut(u.id)
    assert d == {"exact": 1, "partial": 2, "fail": 1}


@pytest.mark.django_db
def test_kpis_basic():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    me = UserFactory(name="Me", email="me@e.com")
    other = UserFactory(name="X", email="x@e.com")
    for earned, p in [(3, me), (1, me), (0, me), (1, other), (1, other), (1, other)]:
        m = MatchFactory(round=grp, result_home=1, result_away=0)
        PredictionFactory(player=p, match=m, earned=earned)
    k = kpis(me)
    assert k["exact"] == 1
    assert k["hit_rate"] == pytest.approx(2/3)
    assert k["vs_leader"] >= 0
