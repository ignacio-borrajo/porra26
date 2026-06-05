from django.urls import reverse

from accounts.forms import LoginForm
from accounts.models import AuditLog, UserSession
from accounts.tests.factories import UserFactory


def test_login_form_has_remember_field_initial_true():
    form = LoginForm()
    assert "remember" in form.fields
    assert form.fields["remember"].required is False
    assert form.fields["remember"].initial is True


def test_login_form_accepts_remember_off():
    form = LoginForm(data={"email": "x@edisa.com", "password": "p", "remember": ""})
    form.is_valid()
    assert form.cleaned_data.get("remember", False) is False


def test_login_form_accepts_remember_on():
    form = LoginForm(data={"email": "x@edisa.com", "password": "p", "remember": "1"})
    form.is_valid()
    assert form.cleaned_data.get("remember") is True


def test_login_with_remember_sets_30_day_expiry_and_creates_user_session(client):
    user = UserFactory(email="x@edisa.com", password="Secret123")
    resp = client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123", "remember": "1"},
    )
    assert resp.status_code == 302

    session = client.session
    assert 30 * 24 * 3600 - 60 <= session.get_expiry_age() <= 30 * 24 * 3600 + 60

    us = UserSession.objects.get(user=user)
    assert us.session_key == session.session_key
    assert us.remembered is True


def test_login_without_remember_uses_browser_session_and_marks_not_remembered(client):
    UserFactory(email="x@edisa.com", password="Secret123")
    resp = client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123"},
    )
    assert resp.status_code == 302
    assert client.session.get_expire_at_browser_close() is True
    us = UserSession.objects.get(session_key=client.session.session_key)
    assert us.remembered is False


def test_login_with_is_pwa_marks_user_session(client):
    UserFactory(email="x@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {
            "email": "x@edisa.com",
            "password": "Secret123",
            "remember": "1",
            "is_pwa": "1",
        },
    )
    us = UserSession.objects.get(session_key=client.session.session_key)
    assert us.is_pwa is True


def test_failed_login_does_not_create_user_session(client):
    UserFactory(email="x@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "WRONG"},
    )
    assert UserSession.objects.count() == 0


def test_login_records_audit_log(client):
    user = UserFactory(email="x@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123", "remember": "1"},
    )
    log = AuditLog.objects.get(action="login", target_id=str(user.id))
    assert log.payload["remembered"] is True
