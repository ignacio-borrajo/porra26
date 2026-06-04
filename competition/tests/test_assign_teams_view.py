from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from competition.models import Prediction
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture
def gestor(db):
    return User.objects.create(
        email="g@example.com",
        is_gestor=True,
        name="G",
        is_active=True,
        must_change_password=False,
    )


@pytest.fixture
def jugador(db):
    return User.objects.create(
        email="j@example.com",
        is_jugador=True,
        name="J",
        is_active=True,
        must_change_password=False,
    )


@pytest.fixture
def r32(db):
    return RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)


@pytest.mark.django_db
def test_assign_teams_initial(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    ko = MatchFactory(
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
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "ESP", "away_code": "ARG"},
    )
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home == esp
    assert ko.away == arg


@pytest.mark.django_db
def test_assign_teams_correction_invalidates_predictions(client, gestor, jugador, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=esp,
        away=arg,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M74",
        kickoff=timezone.now() + timedelta(days=10),
    )
    Prediction.objects.create(player=jugador, match=ko, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "FRA", "away_code": "ARG", "confirm_invalidate": "1"},
    )
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home == fra
    assert Prediction.objects.filter(match=ko).count() == 0


@pytest.mark.django_db
def test_assign_teams_correction_requires_confirmation(client, gestor, jugador, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    TeamFactory(code="FRA")
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=esp,
        away=arg,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M75",
        kickoff=timezone.now() + timedelta(days=10),
    )
    Prediction.objects.create(player=jugador, match=ko, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "FRA", "away_code": "ARG"},
    )
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home == esp
    assert Prediction.objects.filter(match=ko).count() == 1


@pytest.mark.django_db
def test_assign_teams_rejects_same_team_both_sides(client, gestor, r32):
    TeamFactory(code="ESP")
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M76",
        kickoff=timezone.now() + timedelta(days=10),
    )
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "ESP", "away_code": "ESP"},
    )
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home is None and ko.away is None


@pytest.mark.django_db
def test_assign_teams_non_gestor_forbidden(client, jugador, r32):
    TeamFactory(code="ESP")
    TeamFactory(code="ARG")
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M77",
        kickoff=timezone.now() + timedelta(days=10),
    )
    client.force_login(jugador)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "ESP", "away_code": "ARG"},
    )
    # GestorRequiredMixin redirige al dashboard si no es gestor
    assert resp.status_code in (302, 403)
    ko.refresh_from_db()
    assert ko.home is None
