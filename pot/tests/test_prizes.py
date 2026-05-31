import pytest
from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.services.prizes import matchday_winners


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_matchday_pending_if_any_match_unresolved(groups_round):
    MatchFactory(round=groups_round, matchday=1, result_home=None, result_away=None)
    MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    res = matchday_winners(("matchday", 1))
    assert res.status == "pending"


@pytest.mark.django_db
def test_matchday_single_winner(groups_round):
    a = UserFactory(name="A"); b = UserFactory(name="B")
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=a, match=m2, earned=1)
    PredictionFactory(player=b, match=m1, earned=1)
    PredictionFactory(player=b, match=m2, earned=0)
    res = matchday_winners(("matchday", 1))
    assert res.status == "resolved"
    assert [w.id for w in res.winners] == [a.id]


@pytest.mark.django_db
def test_matchday_tie_splits_prize(groups_round):
    a = UserFactory(name="A"); b = UserFactory(name="B")
    m1 = MatchFactory(round=groups_round, matchday=2, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=b, match=m1, earned=3)
    res = matchday_winners(("matchday", 2))
    assert res.status == "resolved"
    assert sorted(w.id for w in res.winners) == sorted([a.id, b.id])
    assert res.tied is True


@pytest.mark.django_db
def test_matchday_desierto_when_nobody_scored(groups_round):
    UserFactory()
    MatchFactory(round=groups_round, matchday=3, result_home=1, result_away=0)
    res = matchday_winners(("matchday", 3))
    assert res.status == "desierto"
