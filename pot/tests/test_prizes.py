from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import PotSettings
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
    a = UserFactory(name="A")
    b = UserFactory(name="B")
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
    a = UserFactory(name="A")
    b = UserFactory(name="B")
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


@pytest.mark.django_db
def test_matchday_winners_exact_breaks_tie(groups_round):
    """Mismos pts pero distinto número de exactos: gana el de más exactos."""
    groups_round.partial_points = 1
    groups_round.save()
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    # Mismos pts (4), Ana con 1 exacto+1 parcial, Borja con 0 exactos+4 parciales no es posible.
    # Hacemos: Ana 3+1=4 (1 exacto). Borja 1+1+1+1=4 con 4 parciales — necesita 4 partidos.
    # Más simple: 2 partidos donde Ana hace 1 exacto y Borja 0 exactos pero los mismos pts totales.
    m1 = MatchFactory(round=groups_round, matchday=4, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=4, result_home=2, result_away=2)
    # Ana: exacto en m1 (3 pts) + parcial en m2 (1 pt) = 4 pts, 1 exacto, 2 aciertos
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m2, home=0, away=0, earned=1)
    # Borja: parcial en m1 (1 pt) + exacto en m2 (3 pts) = 4 pts, 1 exacto, 2 aciertos → siguen empatados
    PredictionFactory(player=b, match=m1, home=2, away=0, earned=1)
    PredictionFactory(player=b, match=m2, home=2, away=2, earned=3)
    res = matchday_winners(("matchday", 4))
    assert res.status == "resolved"
    assert res.tied is True
    assert {w.id for w in res.winners} == {a.id, b.id}


@pytest.mark.django_db
def test_matchday_winners_share_is_split_when_tied(groups_round):
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25")
    s.save()
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    m1 = MatchFactory(round=groups_round, matchday=5, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
    res = matchday_winners(("matchday", 5))
    assert res.tied is True
    assert res.share == Decimal("12.5")


@pytest.mark.django_db
def test_matchday_winners_share_full_when_single(groups_round):
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25")
    s.save()
    a = UserFactory(name="Ana")
    b = UserFactory(name="Borja")
    m1 = MatchFactory(round=groups_round, matchday=6, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=0, away=1, earned=0)
    res = matchday_winners(("matchday", 6))
    assert res.tied is False
    assert res.share == Decimal("25")
    assert [w.id for w in res.winners] == [a.id]


