from unittest.mock import patch

import pytest
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
def pendientes(db):
    a = UserFactory(email="a@edisa.com", must_change_password=True, last_login=None)
    b = UserFactory(email="b@edisa.com", must_change_password=True, last_login=None)
    return [a, b]


@pytest.fixture
def ya_dentro(db):
    u = UserFactory(email="vet@edisa.com", must_change_password=False)
    u.last_login = timezone.now()
    u.save(update_fields=["last_login"])
    return u


def test_get_modal_muestra_recuento_y_destinatarios(gestor, client, pendientes, ya_dentro):
    response = client.get(
        reverse("pot:players_bulk_welcome"),
        HTTP_X_MODAL="1",
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "Enviar a 2" in html
    assert "a@edisa.com" in html
    assert "b@edisa.com" in html
    assert "vet@edisa.com" not in html


def test_get_modal_sin_pendientes_muestra_mensaje(gestor, client, ya_dentro):
    response = client.get(
        reverse("pot:players_bulk_welcome"),
        HTTP_X_MODAL="1",
    )
    assert response.status_code == 200
    html = response.content.decode()
    assert "No hay jugadores pendientes" in html


def test_post_dispara_envio_async_y_redirige(gestor, client, pendientes):
    with patch("pot.views.send_bulk_welcome_async") as mock_async:
        response = client.post(
            reverse("pot:players_bulk_welcome"),
            HTTP_X_MODAL="1",
        )
    assert response.status_code == 200
    assert response["X-Modal-Redirect"] == reverse("pot:manage_players")
    mock_async.assert_called_once()
    sent_ids = mock_async.call_args.args[0]
    assert sorted(sent_ids) == sorted([p.id for p in pendientes])


def test_post_sin_pendientes_no_lanza_envio(gestor, client, ya_dentro):
    with patch("pot.views.send_bulk_welcome_async") as mock_async:
        response = client.post(
            reverse("pot:players_bulk_welcome"),
            HTTP_X_MODAL="1",
        )
    assert response.status_code == 200
    assert response["X-Modal-Redirect"] == reverse("pot:manage_players")
    mock_async.assert_not_called()


def test_post_solo_gestor(client, pendientes, db):
    no_gestor = UserFactory(email="player@edisa.com", password="OldPwd1234!")
    client.force_login(no_gestor)
    response = client.post(reverse("pot:players_bulk_welcome"))
    assert response.status_code in (302, 403)


def test_post_anonimo_redirige(client, pendientes):
    response = client.post(reverse("pot:players_bulk_welcome"))
    assert response.status_code == 302


def test_post_registra_auditlog_started(gestor, client, pendientes):
    with patch("accounts.services.bulk_welcome.time.sleep"):
        with patch("accounts.services.bulk_welcome.Thread") as thread_cls:
            client.post(
                reverse("pot:players_bulk_welcome"),
                HTTP_X_MODAL="1",
            )
            thread_cls.assert_called_once()
    log = AuditLog.objects.get(action="bulk_welcome_emails_started")
    assert log.payload["count"] == len(pendientes)
