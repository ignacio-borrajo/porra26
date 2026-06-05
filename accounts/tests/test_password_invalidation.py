import re

from django.core import mail
from django.test import Client
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from accounts.services.password_reset import send_password_reset_email
from accounts.tests.factories import UserFactory


def _login(client, user, password="Secret123"):
    client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": password, "remember": "1"},
    )


def test_admin_password_change_wipes_user_sessions():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="k1", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=user, session_key="k2", device_label="d", last_seen_at=timezone.now()
    )
    user.set_password("NewPass123")
    user.save(update_fields=["password"])
    assert UserSession.objects.filter(user=user).count() == 0


def test_voluntary_password_change_kills_other_sessions_but_keeps_current(client):
    user = UserFactory(email="vp@edisa.com", password="Secret123")
    _login(client, user)
    UserSession.objects.create(
        user=user, session_key="other-1", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=user, session_key="other-2", device_label="d", last_seen_at=timezone.now()
    )

    resp = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Secret123",
            "new1": "NewPass123",
            "new2": "NewPass123",
        },
    )
    assert resp.status_code == 302
    # update_session_auth_hash rota la session_key — la actual es la nueva.
    new_key = client.session.session_key
    remaining = list(
        UserSession.objects.filter(user=user).values_list("session_key", flat=True)
    )
    assert remaining == [new_key]
    assert not UserSession.objects.filter(session_key__in=["other-1", "other-2"]).exists()


def test_forced_password_change_kills_other_sessions(client):
    user = UserFactory(email="fp@edisa.com", password="Secret123")
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    _login(client, user)
    UserSession.objects.create(
        user=user, session_key="other", device_label="d", last_seen_at=timezone.now()
    )

    client.post(
        reverse("accounts:change_password"),
        {"current": "Secret123", "new1": "NewPass123", "new2": "NewPass123"},
    )
    assert not UserSession.objects.filter(session_key="other").exists()


def test_email_reset_kills_all_sessions(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = UserFactory(email="er@edisa.com", password="Secret123")
    # Simulamos sesiones activas (en otros dispositivos) sin hacer login aquí:
    # un atacante podría tener una de ellas — el reset por email debe cerrarlas
    # TODAS, incluida la del propio usuario.
    UserSession.objects.create(
        user=user, session_key="s1", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=user, session_key="s2", device_label="d", last_seen_at=timezone.now()
    )
    mail.outbox = []

    send_password_reset_email(user, purpose="reset")
    body = mail.outbox[-1].body
    match = re.search(r"(/recuperar/[^\s]+/reset/[^\s]+/)", body)
    assert match, body
    confirm_url = match.group(1)

    anon = Client()
    resp = anon.post(
        confirm_url,
        {"new_password1": "NewPass123", "new_password2": "NewPass123"},
    )
    assert resp.status_code == 302
    assert UserSession.objects.filter(user=user).count() == 0
