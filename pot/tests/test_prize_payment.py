import pytest

from accounts.models import User
from competition.models import Round
from pot.models import Payment, Prize


@pytest.mark.django_db
def test_prize_global_top1():
    p = Prize.objects.create(scope="global", position=1, amount=200, label="1er premio")
    assert p.scope == "global"
    assert p.position == 1


@pytest.mark.django_db
def test_prize_matchday():
    p = Prize.objects.create(scope="matchday", matchday=2, amount=20, label="Jornada 2")
    assert p.matchday == 2


@pytest.mark.django_db
def test_prize_round_only_for_ko():
    r = Round.objects.create(id="qf", label="Cuartos", short="QF", points=10, order=4)
    p = Prize.objects.create(scope="round", round=r, amount=30, label="Cuartos")
    assert p.round_id == "qf"


@pytest.mark.django_db
def test_payment_default_unpaid():
    u = User.objects.create_user(email="a@edisa.com", password="x", name="A")
    pay = Payment.objects.create(player=u)
    assert pay.paid is False
    assert pay.paid_at is None
