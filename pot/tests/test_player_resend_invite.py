import json

import pytest
from django.core import mail
from django.urls import reverse
from django.utils import timezone

from accounts.models import AuditLog
from accounts.tests.factories import GestorFactory, UserFactory


@pytest.fixture
def gestor(db, client):
    u = GestorFactory(email="gestor@edisa.com", password="OldPwd1234!")
    client.force_login(u)
    return u


@pytest.fixture
def jugador_pendiente(db):
    return UserFactory(
        email="pendiente@edisa.com",
        password="OldPwd1234!",
        must_change_password=True,
    )


@pytest.fixture
def jugador_veterano(db):
    u = UserFactory(
        email="veterano@edisa.com",
        password="OldPwd1234!",
        must_change_password=False,
    )
    u.last_login = timezone.now()
    u.save(update_fields=["last_login"])
    return u


def test_resend_pendiente_envia_welcome(gestor, client, jugador_pendiente):
    response = client.post(reverse("pot:player_resend_invite", args=[jugador_pendiente.id]))
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["ok"] is True
    assert data["purpose"] == "welcome"
    assert len(mail.outbox) == 1
    assert "Bienvenido" in mail.outbox[0].subject

    log = AuditLog.objects.get(action="password_reset_email_sent")
    assert log.actor == gestor


def test_resend_veterano_envia_reset(gestor, client, jugador_veterano):
    response = client.post(reverse("pot:player_resend_invite", args=[jugador_veterano.id]))
    data = json.loads(response.content)
    assert data["purpose"] == "reset"
    assert "Restablece" in mail.outbox[0].subject


def test_resend_con_purpose_welcome_forzado_envia_welcome(gestor, client, jugador_veterano):
    """El botón "Enviar bienvenida" de la columna acciones permite forzar
    welcome aunque el usuario ya hubiera entrado al portal."""
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_veterano.id]),
        {"purpose": "welcome"},
    )
    data = json.loads(response.content)
    assert data["purpose"] == "welcome"
    assert "Bienvenido" in mail.outbox[0].subject


def test_resend_con_purpose_invalido_cae_a_auto(gestor, client, jugador_veterano):
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_veterano.id]),
        {"purpose": "bogus"},
    )
    data = json.loads(response.content)
    assert data["purpose"] == "reset"


def test_resend_a_inactivo_404(gestor, client, jugador_pendiente):
    jugador_pendiente.is_active = False
    jugador_pendiente.save(update_fields=["is_active"])
    response = client.post(reverse("pot:player_resend_invite", args=[jugador_pendiente.id]))
    assert response.status_code == 404


def test_resend_no_gestor_redirige(client, jugador_pendiente, db):
    no_gestor = UserFactory(email="player@edisa.com", password="OldPwd1234!")
    client.force_login(no_gestor)
    response = client.post(reverse("pot:player_resend_invite", args=[jugador_pendiente.id]))
    assert response.status_code in (302, 403)


def test_resend_anonimo_redirige_a_login(client, jugador_pendiente):
    response = client.post(reverse("pot:player_resend_invite", args=[jugador_pendiente.id]))
    assert response.status_code == 302
