from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import Prize
from pot.services.payouts import podium_payouts


def _seed_prizes():
    Prize.objects.create(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    Prize.objects.create(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    Prize.objects.create(scope="global", position=3, amount=Decimal("96"), label="3er premio")


@pytest.mark.django_db
def test_podium_payout_splits_p1_among_tied():
    _seed_prizes()
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    d = UserFactory(name="Dani", email="d@e.com")
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    # Ana y Borja empatan en 1ª (3 pts cada uno); Carla en 2ª (1 pt); Dani sin puntos.
    PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=c, match=m, home=1, away=1, earned=1)
    PredictionFactory(player=d, match=m, home=0, away=2, earned=0)

    payouts = {p.name: p for p in podium_payouts()}
    assert payouts["Ana"].share == Decimal("120")
    assert payouts["Ana"].position == 1
    assert payouts["Ana"].tied is True
    assert payouts["Borja"].share == Decimal("120")
    assert payouts["Carla"].share == Decimal("144")
    assert payouts["Carla"].position == 2
    assert payouts["Carla"].tied is False
    # Dani no entra en el podio (no tiene puntos)
    assert "Dani" not in payouts


@pytest.mark.django_db
def test_podium_payout_handles_tie_on_second_place():
    _seed_prizes()
    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    d = UserFactory(name="Dani", email="d@e.com")
    e = UserFactory(name="Eva", email="e@e.com")
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    # Ana 1ª (3 pts). Borja, Carla, Dani empatados en 2ª (1 pt cada uno). Eva sin puntos.
    PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m, home=2, away=1, earned=1)
    PredictionFactory(player=c, match=m, home=3, away=1, earned=1)
    PredictionFactory(player=d, match=m, home=4, away=1, earned=1)
    PredictionFactory(player=e, match=m, home=0, away=2, earned=0)

    payouts = {p.name: p for p in podium_payouts()}
    assert payouts["Ana"].share == Decimal("240")
    assert payouts["Ana"].position == 1
    assert payouts["Borja"].share == Decimal("48")
    assert payouts["Borja"].position == 2
    assert payouts["Borja"].tied is True
    assert payouts["Carla"].share == Decimal("48")
    assert payouts["Dani"].share == Decimal("48")
    # Eva no entra (sin puntos)
    assert "Eva" not in payouts


@pytest.mark.django_db
def test_podium_payout_returns_empty_when_no_data():
    _seed_prizes()
    assert podium_payouts() == []
