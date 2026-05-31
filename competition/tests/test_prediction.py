from datetime import timedelta

import pytest
from django.db.utils import IntegrityError
from django.utils import timezone

from accounts.models import User
from competition.models import Match, Prediction, Round, Team


@pytest.fixture
def setup(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    esp = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    arg = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    m = Match.objects.create(round=grp, group="A", matchday=1, home=esp, away=arg,
                              kickoff=timezone.now() + timedelta(days=1))
    u = User.objects.create_user(email="a@edisa.com", password="x", name="Ana")
    return u, m


@pytest.mark.django_db
def test_prediction_create(setup):
    u, m = setup
    p = Prediction.objects.create(player=u, match=m, home=2, away=1)
    assert p.earned is None


@pytest.mark.django_db
def test_prediction_unique_player_match(setup):
    u, m = setup
    Prediction.objects.create(player=u, match=m, home=2, away=1)
    with pytest.raises(IntegrityError):
        Prediction.objects.create(player=u, match=m, home=0, away=0)
