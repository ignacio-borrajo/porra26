from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog, User
from competition.models import Match, Prediction
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
def test_delete_match_without_data(client, gestor, r32):
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        bracket_code="M73",
        kickoff=timezone.now() + timedelta(days=10),
    )
    client.force_login(gestor)
    resp = client.post(reverse("competicion:delete_match", args=[ko.id]))
    assert resp.status_code == 302
    assert not Match.objects.filter(pk=ko.id).exists()
    assert AuditLog.objects.filter(action="match_deleted", target_id=str(ko.id)).exists()


@pytest.mark.django_db
def test_delete_match_with_predictions_requires_confirmation(client, gestor, jugador, r32):
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        bracket_code="M74",
        kickoff=timezone.now() + timedelta(days=10),
    )
    Prediction.objects.create(player=jugador, match=ko, home=2, away=1)
    client.force_login(gestor)

    # Sin confirmación: no se borra.
    resp = client.post(reverse("competicion:delete_match", args=[ko.id]))
    assert resp.status_code == 302
    assert Match.objects.filter(pk=ko.id).exists()

    # Con confirmación: se borra el partido y sus pronósticos en cascada.
    resp = client.post(
        reverse("competicion:delete_match", args=[ko.id]),
        {"confirm_delete": "1"},
    )
    assert resp.status_code == 302
    assert not Match.objects.filter(pk=ko.id).exists()
    assert Prediction.objects.filter(match_id=ko.id).count() == 0


@pytest.mark.django_db
def test_delete_match_with_result(client, gestor, r32):
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        bracket_code="M75",
        kickoff=timezone.now() - timedelta(days=1),
        result_home=2,
        result_away=0,
    )
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:delete_match", args=[ko.id]),
        {"confirm_delete": "1"},
    )
    assert resp.status_code == 302
    assert not Match.objects.filter(pk=ko.id).exists()


@pytest.mark.django_db
def test_delete_match_pending_teams_no_teams(client, gestor, r32):
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
    resp = client.post(reverse("competicion:delete_match", args=[ko.id]))
    assert resp.status_code == 302
    assert not Match.objects.filter(pk=ko.id).exists()


@pytest.mark.django_db
def test_delete_match_non_gestor_forbidden(client, jugador, r32):
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        bracket_code="M77",
        kickoff=timezone.now() + timedelta(days=10),
    )
    client.force_login(jugador)
    resp = client.post(reverse("competicion:delete_match", args=[ko.id]))
    # GestorRequiredMixin redirige al dashboard si no es gestor.
    assert resp.status_code in (302, 403)
    assert Match.objects.filter(pk=ko.id).exists()
