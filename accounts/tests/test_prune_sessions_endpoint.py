from datetime import timedelta

from django.test import override_settings
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import GestorFactory, UserFactory


@override_settings(TEAMS_API_TOKEN="test-token")
def test_prune_sessions_endpoint_requires_token(client):
    resp = client.post(reverse("accounts:api:prune_sessions"))
    assert resp.status_code == 401


@override_settings(TEAMS_API_TOKEN="test-token")
def test_prune_sessions_endpoint_with_token_runs_command(client):
    user = UserFactory()
    UserSession.objects.create(
        user=user,
        session_key="orphan-1",
        device_label="d",
        last_seen_at=timezone.now() - timedelta(days=40),
    )
    resp = client.post(
        reverse("accounts:api:prune_sessions"),
        HTTP_AUTHORIZATION="Bearer test-token",
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert "Pruned" in body["summary"]
    assert not UserSession.objects.filter(session_key="orphan-1").exists()


@override_settings(TEAMS_API_TOKEN="test-token")
def test_prune_sessions_endpoint_allows_gestor_session(client):
    GestorFactory(email="g@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "g@edisa.com", "password": "Secret123", "remember": "1"},
    )
    resp = client.post(reverse("accounts:api:prune_sessions"))
    assert resp.status_code == 200
    assert resp.json()["ok"] is True


@override_settings(TEAMS_API_TOKEN="test-token")
def test_prune_sessions_endpoint_rejects_get(client):
    resp = client.get(
        reverse("accounts:api:prune_sessions"),
        HTTP_AUTHORIZATION="Bearer test-token",
    )
    assert resp.status_code == 405
