import pytest
from django.urls import reverse

from accounts.models import User
from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_manage_players_requires_gestor(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("pot:manage_players"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_manage_players_renders_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:manage_players"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_create_player_shows_temp_password(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    r = client.post(
        reverse("pot:player_new"),
        {
            "name": "Nuevo",
            "email": "nuevo@edisa.com",
            "dept": "Dev",
            "role": "jugador",
        },
    )
    assert r.status_code == 200
    assert "Contraseña temporal".encode() in r.content
    assert User.objects.filter(email="nuevo@edisa.com").exists()


@pytest.mark.django_db
def test_toggle_payment(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory()
    from pot.models import Payment

    Payment.objects.create(player=p, paid=False)
    r = client.post(reverse("pot:player_toggle_payment", args=[p.id]))
    assert r.status_code == 302
    assert Payment.objects.get(player=p).paid is True


@pytest.mark.django_db
def test_toggle_player_active(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory(is_active=True)
    r = client.post(reverse("pot:player_toggle_active", args=[p.id]))
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.is_active is False


@pytest.mark.django_db
def test_reset_password_changes_password_and_shows_temp(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory(must_change_password=False)
    old_hash = p.password
    r = client.post(reverse("pot:player_reset", args=[p.id]))
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.password != old_hash
    assert p.must_change_password is True
