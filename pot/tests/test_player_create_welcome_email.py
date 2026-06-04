import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import User
from accounts.tests.factories import GestorFactory


@pytest.fixture
def gestor(db, client):
    u = GestorFactory(email="gestor@edisa.com", password="OldPwd1234!")
    client.force_login(u)
    return u


def test_alta_con_checkbox_envia_welcome(gestor, client):
    response = client.post(
        reverse("pot:player_new"),
        {
            "email": "nuevo@edisa.com",
            "name": "Nuevo Jugador",
            "is_jugador": "on",
            "enviar_bienvenida": "on",
        },
    )
    assert response.status_code in (200, 302)
    assert User.objects.filter(email="nuevo@edisa.com").exists()
    assert len(mail.outbox) == 1
    assert "Bienvenido" in mail.outbox[0].subject
    assert mail.outbox[0].to == ["nuevo@edisa.com"]


def test_alta_sin_checkbox_no_envia(gestor, client):
    response = client.post(
        reverse("pot:player_new"),
        {
            "email": "otro@edisa.com",
            "name": "Otro Jugador",
            "is_jugador": "on",
        },
    )
    assert response.status_code in (200, 302)
    assert User.objects.filter(email="otro@edisa.com").exists()
    assert len(mail.outbox) == 0
