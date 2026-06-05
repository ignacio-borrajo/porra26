from datetime import timedelta

import pytest
from django.core import mail
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.models import BetsReminderLog
from competition.tests.factories import MatchFactory, PredictionFactory, TeamFactory

TOKEN = "testing-token-1234567890"
AUTH = {"HTTP_AUTHORIZATION": f"Bearer {TOKEN}"}


@pytest.fixture(autouse=True)
def clear_outbox():
    mail.outbox = []
    yield
    mail.outbox = []


def _open_match(hours_to_kickoff=1, code_home="ESP", code_away="MEX"):
    h = TeamFactory(code=code_home, name=code_home)
    a = TeamFactory(code=code_away, name=code_away)
    return MatchFactory(home=h, away=a, kickoff=timezone.now() + timedelta(hours=hours_to_kickoff))


# -------------------------------------------------------------------
# POST /api/recordatorios/disparar/
# -------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_disparar_requires_auth(client):
    res = client.post(reverse("competicion:api:recordatorios_disparar"))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_disparar_with_bearer_returns_summary_json(client):
    res = client.post(reverse("competicion:api:recordatorios_disparar"), **AUTH)
    assert res.status_code == 200
    data = res.json()
    assert "T_MINUS_2H" in data
    assert "T_MINUS_30M" in data
    for kind_data in (data["T_MINUS_2H"], data["T_MINUS_30M"]):
        assert set(kind_data.keys()) == {"checked", "sent", "skipped_empty", "errors"}


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_disparar_with_gestor_session_returns_summary_json(client):
    g = GestorFactory()
    client.force_login(g)
    res = client.post(reverse("competicion:api:recordatorios_disparar"))
    assert res.status_code == 200


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_disparar_sends_due_matches(client):
    UserFactory(name="Ana")
    _open_match(hours_to_kickoff=1.5)
    res = client.post(reverse("competicion:api:recordatorios_disparar"), **AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["T_MINUS_2H"]["sent"] == 1
    assert data["T_MINUS_2H"]["errors"] == 0
    assert len(mail.outbox) == 1


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_disparar_counts_skipped_when_no_pending(client):
    m = _open_match(hours_to_kickoff=1.5)
    # Hay match en ventana pero universo vacío → skipped_empty=1
    res = client.post(reverse("competicion:api:recordatorios_disparar"), **AUTH)
    data = res.json()
    assert data["T_MINUS_2H"]["checked"] == 1
    assert data["T_MINUS_2H"]["sent"] == 0
    assert data["T_MINUS_2H"]["skipped_empty"] == 1
    assert mail.outbox == []
    assert not BetsReminderLog.objects.filter(match=m).exists()


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_disparar_counts_errors(monkeypatch, client):
    UserFactory(name="Ana")
    _open_match(hours_to_kickoff=1.5)

    def boom(*args, **kwargs):
        raise RuntimeError("SMTP roto")

    monkeypatch.setattr("competition.api.views.send_reminder_email", boom)
    res = client.post(reverse("competicion:api:recordatorios_disparar"), **AUTH)
    assert res.status_code == 200
    data = res.json()
    assert data["T_MINUS_2H"]["errors"] == 1


# -------------------------------------------------------------------
# POST /api/recordatorios/<match_id>/enviar/
# -------------------------------------------------------------------


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_requires_auth(client):
    m = _open_match()
    res = client.post(reverse("competicion:api:recordatorio_enviar", args=[m.id]))
    assert res.status_code == 401


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_with_gestor_session_returns_sent_true(client):
    g = GestorFactory()
    client.force_login(g)
    UserFactory(name="Ana")
    m = _open_match()
    res = client.post(reverse("competicion:api:recordatorio_enviar", args=[m.id]))
    assert res.status_code == 200
    data = res.json()
    assert data["sent"] is True
    assert data["pending_count"] >= 1


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_returns_no_pending_when_all_bet(client):
    g = GestorFactory(name="Gestor que también juega")
    client.force_login(g)
    m = _open_match()
    PredictionFactory(player=g, match=m)
    res = client.post(reverse("competicion:api:recordatorio_enviar", args=[m.id]))
    assert res.status_code == 200
    data = res.json()
    assert data["sent"] is False
    assert data["reason"] == "no_pending"
    assert mail.outbox == []


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_returns_409_when_closed(client):
    g = GestorFactory()
    client.force_login(g)
    UserFactory(name="Ana")
    h = TeamFactory(code="CL1", name="CL1")
    a = TeamFactory(code="CL2", name="CL2")
    m = MatchFactory(home=h, away=a, kickoff=timezone.now() - timedelta(minutes=5))
    res = client.post(reverse("competicion:api:recordatorio_enviar", args=[m.id]))
    assert res.status_code == 409
    assert mail.outbox == []


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_manual_creates_log_with_kind_manual(client):
    g = GestorFactory()
    client.force_login(g)
    UserFactory(name="Ana")
    m = _open_match()
    client.post(reverse("competicion:api:recordatorio_enviar", args=[m.id]))
    log = BetsReminderLog.objects.get(match=m)
    assert log.kind == BetsReminderLog.KIND_MANUAL


@pytest.mark.django_db
@override_settings(TEAMS_API_TOKEN=TOKEN)
def test_enviar_html_redirects_with_flash(client):
    g = GestorFactory()
    client.force_login(g)
    UserFactory(name="Ana")
    m = _open_match()
    res = client.post(
        reverse("competicion:api:recordatorio_enviar", args=[m.id]),
        HTTP_ACCEPT="text/html",
    )
    assert res.status_code == 302
    assert reverse("competicion:manage_results") in res["Location"]
