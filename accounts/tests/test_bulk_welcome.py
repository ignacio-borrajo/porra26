from unittest.mock import patch

import pytest
from django.core import mail
from django.utils import timezone

from accounts.models import AuditLog
from accounts.services.bulk_welcome import (
    pending_welcome_recipients,
    send_bulk_welcome,
    send_bulk_welcome_async,
)
from accounts.tests.factories import GestorFactory, UserFactory


@pytest.fixture
def gestor(db):
    return GestorFactory(email="gestor@edisa.com")


@pytest.fixture
def pendiente(db):
    return UserFactory(
        email="pendiente@edisa.com",
        must_change_password=True,
        last_login=None,
    )


@pytest.fixture
def ya_activado(db):
    return UserFactory(
        email="ya@edisa.com",
        must_change_password=False,
        last_login=timezone.now(),
    )


@pytest.fixture
def inactivo(db):
    return UserFactory(
        email="off@edisa.com",
        is_active=False,
        must_change_password=True,
        last_login=None,
    )


def test_pending_recipients_filtra_pendientes(pendiente, ya_activado, inactivo):
    qs = pending_welcome_recipients()
    emails = list(qs.values_list("email", flat=True))
    assert pendiente.email in emails
    assert ya_activado.email not in emails
    assert inactivo.email not in emails


def test_send_bulk_welcome_envia_uno_por_usuario(pendiente, gestor):
    otro = UserFactory(
        email="otro@edisa.com",
        must_change_password=True,
        last_login=None,
    )
    with patch("accounts.services.bulk_welcome.time.sleep") as sleep_mock:
        sent, failed = send_bulk_welcome([pendiente, otro], actor=gestor, delay_seconds=0.6)

    assert sent == 2
    assert failed == []
    assert len(mail.outbox) == 2
    destinos = sorted(m.to[0] for m in mail.outbox)
    assert destinos == ["otro@edisa.com", "pendiente@edisa.com"]
    sleep_mock.assert_called_once_with(0.6)


def test_send_bulk_welcome_no_duerme_tras_ultimo(pendiente, gestor):
    with patch("accounts.services.bulk_welcome.time.sleep") as sleep_mock:
        send_bulk_welcome([pendiente], actor=gestor, delay_seconds=0.6)
    sleep_mock.assert_not_called()


def test_send_bulk_welcome_captura_fallo_y_continua(pendiente, gestor):
    bueno = UserFactory(
        email="ok@edisa.com",
        must_change_password=True,
        last_login=None,
    )
    real = __import__(
        "accounts.services.bulk_welcome", fromlist=["send_password_reset_email"]
    ).send_password_reset_email

    def maybe_raise(user, purpose, actor=None):
        if user.email == "pendiente@edisa.com":
            raise RuntimeError("smtp down")
        return real(user, purpose, actor=actor)

    with patch("accounts.services.bulk_welcome.send_password_reset_email", side_effect=maybe_raise):
        with patch("accounts.services.bulk_welcome.time.sleep"):
            sent, failed = send_bulk_welcome([pendiente, bueno], actor=gestor)

    assert sent == 1
    assert len(failed) == 1
    assert failed[0]["email"] == "pendiente@edisa.com"
    assert "smtp down" in failed[0]["error"]


@pytest.mark.django_db(transaction=True)
def test_send_bulk_welcome_async_registra_auditlog_start_y_finish():
    gestor = GestorFactory(email="gestor_async@edisa.com")
    pendiente = UserFactory(
        email="pendiente_async@edisa.com",
        must_change_password=True,
        last_login=None,
    )
    with patch("accounts.services.bulk_welcome.time.sleep"):
        thread = send_bulk_welcome_async([pendiente.id], actor=gestor)
    thread.join(timeout=5)
    assert not thread.is_alive()

    assert AuditLog.objects.filter(action="bulk_welcome_emails_started").exists()
    finish = AuditLog.objects.get(action="bulk_welcome_emails_finished")
    assert finish.payload["sent"] == 1
    assert finish.payload["failed_count"] == 0


def test_send_bulk_welcome_async_devuelve_inmediatamente(pendiente, gestor):
    # No debe bloquear: la función crea el hilo y vuelve. Mockeamos Thread
    # para no lanzar el worker contra la BD del test (SQLite + transacción).
    with patch("accounts.services.bulk_welcome.Thread") as thread_cls:
        thread = send_bulk_welcome_async([pendiente.id], actor=gestor)
    thread_cls.assert_called_once()
    # start() debe haberse llamado en la instancia devuelta
    instance = thread_cls.return_value
    instance.start.assert_called_once()
    assert thread is instance
