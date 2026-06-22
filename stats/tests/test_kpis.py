import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.kpis import compare, donut, kpis


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
def test_donut_uses_match_exact_points_applied():
    """Un acierto exacto con points=3 sigue contando como exacto aunque
    ahora la ronda valga 5."""
    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    u = UserFactory()
    m = MatchFactory(round=grp, result_home=2, result_away=1)
    PredictionFactory(player=u, match=m, home=2, away=1, earned=3)

    grp.points = 5
    grp.save()

    assert donut(u.id) == {"exact": 1, "partial": 0, "fail": 0}


@pytest.mark.django_db
def test_compare_metrics():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    me = UserFactory(name="Me", email="me@e.com")
    other = UserFactory(name="X", email="x@e.com")
    for earned, p in [(3, me), (1, me), (1, other), (0, other)]:
        m = MatchFactory(round=grp, result_home=1, result_away=0)
        PredictionFactory(player=p, match=m, earned=earned)
    c = compare(me.id)
    metrics = {row["label"]: row for row in c["metrics"]}
    assert metrics["Puntos"]["me"] == 4  # 3 + 1
    assert metrics["Puntos"]["best"] == 4
    assert metrics["Puntos"]["avg"] == pytest.approx(2.5)  # (4 + 1) / 2


@pytest.mark.django_db
def test_compare_empty_for_non_player():
    assert compare(99999) == {}


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
    assert k["hit_rate"] == pytest.approx(2 / 3)
    assert k["vs_leader"] >= 0
