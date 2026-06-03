import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_topbar_has_premios_y_puntos_link_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("pot:prizes") in content
    assert "Premios y puntos" in content


@pytest.mark.django_db
def test_topbar_no_premios_link_for_jugador(client):
    client.force_login(UserFactory(must_change_password=False, is_jugador=True))
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("pot:prizes") not in content


@pytest.mark.django_db
def test_topbar_premios_is_active_on_prizes_page(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    href = reverse("pot:prizes")
    assert f'href="{href}" class="nav-item is-active"' in content


@pytest.mark.django_db
def test_topbar_jugadores_not_active_on_prizes_page(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    href_jugadores = reverse("pot:manage_players")
    # El enlace de jugadores aparece pero SIN is-active.
    assert href_jugadores in content
    assert f'href="{href_jugadores}" class="nav-item is-active"' not in content
