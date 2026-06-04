from urllib.parse import urlparse

import pytest
from django.core import mail
from django.urls import resolve

from accounts.models import AuditLog
from accounts.services.password_reset import (
    build_reset_url,
    send_password_reset_email,
    validate_reset_token,
)
from accounts.tests.factories import GestorFactory, UserFactory


@pytest.fixture
def alice(db):
    return UserFactory(email="alice@edisa.com", password="OldPwd1234!")


@pytest.fixture
def gestor(db):
    return GestorFactory(email="gestor@edisa.com", password="OldPwd1234!")


def test_send_reset_envia_email_con_asunto_y_destinatario(alice):
    send_password_reset_email(alice, purpose="reset")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["alice@edisa.com"]
    assert msg.subject == "[Porra26] Restablece tu contraseña"
    assert "restablecer" in msg.body.lower() or "Restablece" in msg.body


def test_send_welcome_usa_otro_asunto_y_copy(alice):
    send_password_reset_email(alice, purpose="welcome")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.subject == "[Porra26] Bienvenido a la porra del Mundial"
    assert "bienvenido" in msg.body.lower() or "te han creado cuenta" in msg.body.lower()


def test_send_incluye_html_alternative(alice):
    send_password_reset_email(alice, purpose="reset")

    msg = mail.outbox[0]
    assert len(msg.alternatives) == 1
    html, mime = msg.alternatives[0]
    assert mime == "text/html"
    assert "<html" in html.lower() or "<body" in html.lower()


def test_send_genera_url_absoluta_en_email(alice):
    send_password_reset_email(alice, purpose="reset")
    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    assert "https://laporradeljefe.es/" in msg.body
    assert "https://laporradeljefe.es/" in html


def test_send_registra_auditlog(alice, gestor):
    send_password_reset_email(alice, purpose="welcome", actor=gestor)

    log = AuditLog.objects.get(action="password_reset_email_sent")
    assert log.actor == gestor
    assert log.target_type == "user"
    assert log.target_id == str(alice.id)
    assert log.payload["purpose"] == "welcome"
    assert "Bienvenido" in log.payload["subject"]


def test_send_rechaza_purpose_invalido(alice):
    with pytest.raises(ValueError):
        send_password_reset_email(alice, purpose="bogus")


def test_build_reset_url_usa_purpose_y_token(alice):
    url = build_reset_url(alice, purpose="reset")
    assert "/recuperar/" in url
    assert "/reset/" in url
    assert url.startswith("https://")


def test_validate_token_devuelve_user_con_token_valido(alice):
    url = build_reset_url(alice, purpose="reset")
    path = urlparse(url).path
    match = resolve(path)
    user = validate_reset_token(
        match.kwargs["uidb64"],
        match.kwargs["purpose"],
        match.kwargs["token"],
    )
    assert user == alice


def test_validate_token_falla_si_user_inactivo(alice):
    url = build_reset_url(alice, purpose="reset")
    path = urlparse(url).path
    match = resolve(path)
    alice.is_active = False
    alice.save(update_fields=["is_active"])

    user = validate_reset_token(
        match.kwargs["uidb64"],
        match.kwargs["purpose"],
        match.kwargs["token"],
    )
    assert user is None


def test_validate_token_falla_si_purpose_cruzado(alice):
    url = build_reset_url(alice, purpose="welcome")
    path = urlparse(url).path
    match = resolve(path)
    user = validate_reset_token(
        match.kwargs["uidb64"],
        "reset",  # cross-purpose
        match.kwargs["token"],
    )
    assert user is None
