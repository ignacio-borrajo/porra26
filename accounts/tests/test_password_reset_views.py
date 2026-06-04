from urllib.parse import urlparse

import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import AuditLog
from accounts.services.password_reset import build_reset_url
from accounts.tests.factories import UserFactory


@pytest.fixture
def alice(db):
    return UserFactory(email="alice@edisa.com", password="OldPwd1234!")


@pytest.fixture
def inactive_bob(db):
    u = UserFactory(email="bob@edisa.com", password="OldPwd1234!")
    u.is_active = False
    u.save(update_fields=["is_active"])
    return u


# ---------- request view ----------


def test_request_get_renderiza(client, db):
    response = client.get(reverse("accounts:password_reset"))
    assert response.status_code == 200
    assert "Recupera tu contrase" in response.content.decode()


def test_request_post_email_existente_envia_email(client, alice):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "alice@edisa.com"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_sent")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["alice@edisa.com"]

    log = AuditLog.objects.get(action="password_reset_requested")
    assert log.payload["encontrado"] is True
    assert log.payload["email_intentado"] == "alice@edisa.com"


def test_request_post_email_inexistente_no_envia_pero_redirige(client, db):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "nadie@edisa.com"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_sent")
    assert len(mail.outbox) == 0

    log = AuditLog.objects.get(action="password_reset_requested")
    assert log.payload["encontrado"] is False


def test_request_post_email_fuera_dominio_no_envia(client, db):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "alguien@gmail.com"}
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 0


def test_request_post_email_inactivo_no_envia(client, inactive_bob):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "bob@edisa.com"}
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 0

    log = AuditLog.objects.get(action="password_reset_requested")
    assert log.payload["encontrado"] is False


def test_request_post_email_mayusculas_normaliza(client, alice):
    client.post(reverse("accounts:password_reset"), {"email": "ALICE@EDISA.COM"})
    assert len(mail.outbox) == 1


# ---------- sent view ----------


def test_sent_renderiza_email_de_sesion(client, alice):
    client.post(reverse("accounts:password_reset"), {"email": "alice@edisa.com"})
    response = client.get(reverse("accounts:password_reset_sent"))
    assert response.status_code == 200
    assert b"alice@edisa.com" in response.content


# ---------- confirm view ----------


def _confirm_url_for(user, purpose):
    full = build_reset_url(user, purpose)
    return urlparse(full).path


def test_confirm_get_reset_renderiza_copy_reset(client, alice):
    response = client.get(_confirm_url_for(alice, "reset"))
    assert response.status_code == 200
    assert "Nueva contrase" in response.content.decode()


def test_confirm_get_welcome_renderiza_copy_welcome(client, alice):
    response = client.get(_confirm_url_for(alice, "welcome"))
    assert response.status_code == 200
    assert "Bienvenido a la porra" in response.content.decode()


def test_confirm_get_token_invalido_devuelve_invalid_page(client, alice):
    url = _confirm_url_for(alice, "reset")
    bad = url.rsplit("-", 1)[0] + "-XXXXXXXXXXXXXXXXXXXX/"
    response = client.get(bad)
    assert response.status_code == 410
    assert "Enlace no v" in response.content.decode()


def test_confirm_get_purpose_no_valido_404(client, alice):
    url = _confirm_url_for(alice, "reset").replace("/reset/", "/bogus/")
    response = client.get(url)
    assert response.status_code == 404


def test_confirm_post_password_valida_cambia_y_redirige(client, alice):
    url = _confirm_url_for(alice, "reset")
    response = client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "NuevaPwd1234!"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_complete")

    alice.refresh_from_db()
    assert alice.check_password("NuevaPwd1234!") is True
    assert alice.must_change_password is False

    log = AuditLog.objects.get(action="password_reset_completed")
    assert log.payload["purpose"] == "reset"


def test_confirm_post_welcome_marca_must_change_false(client, alice):
    alice.must_change_password = True
    alice.save(update_fields=["must_change_password"])
    url = _confirm_url_for(alice, "welcome")
    client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "NuevaPwd1234!"}
    )
    alice.refresh_from_db()
    assert alice.must_change_password is False


def test_confirm_post_passwords_no_coinciden_re_renderiza(client, alice):
    url = _confirm_url_for(alice, "reset")
    response = client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "Distinta1234!"}
    )
    assert response.status_code == 200
    alice.refresh_from_db()
    assert alice.check_password("OldPwd1234!") is True


def test_confirm_post_token_usado_segunda_vez_falla(client, alice):
    url = _confirm_url_for(alice, "reset")
    client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "NuevaPwd1234!"}
    )
    response = client.post(
        url, {"new_password1": "OtraPwd1234!", "new_password2": "OtraPwd1234!"}
    )
    assert response.status_code == 410


# ---------- complete view ----------


def test_complete_renderiza(client, db):
    response = client.get(reverse("accounts:password_reset_complete"))
    assert response.status_code == 200
    assert "Contrase" in response.content.decode()
