from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from competition.models import BetsReminderLog, Prediction
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
    return RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)


def _ko(**kw):
    defaults = dict(
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        kickoff=timezone.now() + timedelta(days=10),
    )
    defaults.update(kw)
    return MatchFactory(**defaults)


@pytest.mark.django_db
def test_edit_assigns_teams_and_kickoff(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    m = _ko(round=r32, bracket_code="M73")
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ARG", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home == esp
    assert m.away == arg
    assert m.kickoff.year == 2026 and m.kickoff.month == 7 and m.kickoff.day == 15


@pytest.mark.django_db
def test_edit_allows_empty_teams(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    m = _ko(round=r32, home=esp, away=TeamFactory(code="ARG"), bracket_code="M74")
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "", "away_code": "", "date": "2026-07-16", "time": "18:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home is None and m.away is None
    assert m.status == "pending_teams"


@pytest.mark.django_db
def test_edit_rejects_same_team_both_sides(client, gestor, r32):
    TeamFactory(code="ESP")
    m = _ko(round=r32, bracket_code="M75")
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ESP", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home is None and m.away is None


@pytest.mark.django_db
def test_edit_requires_confirmation_to_invalidate_predictions(client, gestor, jugador, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    TeamFactory(code="FRA")
    m = _ko(round=r32, home=esp, away=arg, bracket_code="M76")
    Prediction.objects.create(player=jugador, match=m, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "FRA", "away_code": "ARG", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home == esp
    assert Prediction.objects.filter(match=m).count() == 1


@pytest.mark.django_db
def test_edit_invalidates_predictions_with_confirmation(client, gestor, jugador, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    m = _ko(round=r32, home=esp, away=arg, bracket_code="M77")
    Prediction.objects.create(player=jugador, match=m, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {
            "home_code": "FRA",
            "away_code": "ARG",
            "date": "2026-07-15",
            "time": "21:00",
            "confirm_invalidate": "1",
        },
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home == fra
    assert Prediction.objects.filter(match=m).count() == 0


@pytest.mark.django_db
def test_edit_future_kickoff_resets_auto_reminders(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    m = _ko(
        round=r32,
        home=esp,
        away=arg,
        bracket_code="M78",
        kickoff=timezone.now() + timedelta(hours=1),
    )
    BetsReminderLog.objects.create(
        match=m,
        kind=BetsReminderLog.KIND_T_MINUS_2H,
        sent_at=timezone.now(),
        pending_count=3,
        pending_names=["A", "B", "C"],
    )
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ARG", "date": "2026-08-01", "time": "20:00"},
    )
    assert resp.status_code == 302
    assert BetsReminderLog.objects.filter(match=m).count() == 0


@pytest.mark.django_db
def test_edit_non_gestor_forbidden(client, jugador, r32):
    TeamFactory(code="ESP")
    TeamFactory(code="ARG")
    m = _ko(round=r32, bracket_code="M79")
    client.force_login(jugador)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ARG", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code in (302, 403)
    m.refresh_from_db()
    assert m.home is None
