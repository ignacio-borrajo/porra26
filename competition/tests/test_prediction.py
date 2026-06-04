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
def test_predict_post_rejected_when_match_has_no_teams(client, setup):
    """Si un cruce KO no tiene los dos equipos asignados aún, POST está prohibido."""
    u, m = setup
    u.must_change_password = False
    u.save()
    client.force_login(u)
    with freeze_time("2026-06-09 10:00:00", tz_offset=0):
        r32 = m.round
        ko = Match.objects.create(
            round=r32,
            group="R32",
            matchday=None,
            home=None,
            away=None,
            home_slot="1A",
            away_slot="2B",
            bracket_code="M73",
            kickoff=timezone.now() + timedelta(days=10),
        )
        r = client.post(reverse("competicion:predict", args=[ko.id]), {"home": 1, "away": 0})
        assert r.status_code == 403
        assert not ko.predictions.filter(player=u).exists()
