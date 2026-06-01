from datetime import timedelta

import pytest
from django.db.utils import IntegrityError
from django.urls import reverse
from django.utils import timezone
from freezegun import freeze_time

from accounts.models import User
from competition.models import Match, Prediction, Round, Team


@pytest.fixture
def setup(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    esp = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    arg = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    m = Match.objects.create(
        round=grp,
        group="A",
        matchday=1,
        home=esp,
        away=arg,
        kickoff=timezone.now() + timedelta(days=1),
    )
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


@pytest.mark.django_db
def test_predict_post_rejected_when_matchday_locked(client, setup):
    u, m = setup
    u.must_change_password = False
    u.save()
    client.force_login(u)
    with freeze_time("2026-06-09 10:00:00", tz_offset=0):
        # MD1 (m) con kickoff aún en el futuro: bloquea MD2
        m.kickoff = timezone.now() + timedelta(days=2)
        m.save()
        x1 = Team.objects.create(code="X1", name="Equipo X1", flag="🏳️")
        x2 = Team.objects.create(code="X2", name="Equipo X2", flag="🏳️")
        m2 = Match.objects.create(
            round=m.round,
            group="A",
            matchday=2,
            home=x1,
            away=x2,
            kickoff=timezone.now() + timedelta(days=10),
        )
        r = client.post(reverse("competicion:predict", args=[m2.id]), {"home": 1, "away": 0})
        assert r.status_code == 403
        assert not m2.predictions.filter(player=u).exists()
