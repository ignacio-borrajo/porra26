from datetime import timedelta

from django.contrib.sessions.models import Session
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def _login(client, user, password="Secret123"):
    client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": password, "remember": "1"},
    )


def _create_session(session_key):
    Session.objects.create(
        session_key=session_key,
        session_data="",
        expire_date=timezone.now() + timedelta(days=30),
    )


def test_my_account_lists_user_sessions(client):
    user = UserFactory(email="ms@edisa.com", password="Secret123")
    _login(client, user)
    UserSession.objects.create(
        user=user,
        session_key="other-key-12345",
        device_label="iPhone — Safari",
        last_seen_at=timezone.now(),
        remembered=True,
    )
    resp = client.get(reverse("accounts:my_account"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "iPhone" in body
    assert "ESTA SESIÓN" in body


def test_my_account_does_not_list_other_users_sessions(client):
    me = UserFactory(email="me@edisa.com", password="Secret123")
    other = UserFactory(email="other@edisa.com", password="Secret123")
    _login(client, me)
    UserSession.objects.create(
        user=other,
        session_key="other-session",
        device_label="Edge en Windows",
        last_seen_at=timezone.now(),
    )
    resp = client.get(reverse("accounts:my_account"))
    body = resp.content.decode()
    assert "Edge en Windows" not in body


def test_revoke_session_action_kills_specific_session(client):
    user = UserFactory(email="rs@edisa.com", password="Secret123")
    _login(client, user)
    _create_session("kill-this")
    UserSession.objects.create(
        user=user, session_key="kill-this", device_label="d", last_seen_at=timezone.now()
    )

    resp = client.post(
        reverse("accounts:my_account"),
        {"action": "revoke_session", "session_key": "kill-this"},
    )
    assert resp.status_code == 302
    assert not UserSession.objects.filter(session_key="kill-this").exists()


def test_revoke_session_rejects_current_session(client):
    user = UserFactory(email="rsc@edisa.com", password="Secret123")
    _login(client, user)
    current = client.session.session_key
    resp = client.post(
        reverse("accounts:my_account"),
        {"action": "revoke_session", "session_key": current},
    )
    assert resp.status_code == 400


def test_revoke_session_rejects_other_users_session(client):
    me = UserFactory(email="rsu@edisa.com", password="Secret123")
    other = UserFactory(email="oo@edisa.com", password="Secret123")
    _login(client, me)
    UserSession.objects.create(
        user=other, session_key="other-key", device_label="d", last_seen_at=timezone.now()
    )
    client.post(
        reverse("accounts:my_account"),
        {"action": "revoke_session", "session_key": "other-key"},
    )
    assert UserSession.objects.filter(session_key="other-key").exists()


def test_revoke_others_kills_all_other_sessions(client):
    user = UserFactory(email="ro@edisa.com", password="Secret123")
    _login(client, user)
    current_key = client.session.session_key
    for k in ["k1", "k2", "k3"]:
        UserSession.objects.create(
            user=user, session_key=k, device_label="d", last_seen_at=timezone.now()
        )
    resp = client.post(reverse("accounts:my_account"), {"action": "revoke_others"})
    assert resp.status_code == 302
    remaining = list(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
    assert remaining == [current_key]
