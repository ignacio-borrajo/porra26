import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_topbar_has_rules_link(client):
    client.force_login(UserFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("core:rules") in content
    assert "Reglas" in content


@pytest.mark.django_db
def test_rules_active_class_on_rules_page(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    href = reverse("core:rules")
    # El enlace activo lleva clase is-active en el mismo elemento.
    assert f'href="{href}" class="nav-item is-active"' in content


@pytest.mark.django_db
def test_topbar_nav_order_competicion_rankings_stats(client):
    """Tras el reorden, Rankings va antes que Estadísticas en el HTML."""
    client.force_login(UserFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    # Limitamos la búsqueda al <nav class="topbar-nav topbar-nav-desktop">
    # para no confundirnos con apariciones posteriores en la bottom nav.
    start = content.find("topbar-nav-desktop")
    end = content.find("</nav>", start)
    topnav = content[start:end]
    # Usamos href="..." para que /stats/ no haga match dentro de
    # /stats/rankings/ (substring).
    competicion = topnav.find(f'href="{reverse("competicion:dashboard")}"')
    rankings = topnav.find(f'href="{reverse("stats:rankings")}"')
    stats = topnav.find(f'href="{reverse("stats:dashboard")}"')
    assert competicion != -1 and rankings != -1 and stats != -1
    assert competicion < rankings < stats, (
        f"orden esperado Competición < Rankings < Estadísticas, "
        f"obtenido {competicion}, {rankings}, {stats}"
    )


@pytest.mark.django_db
def test_jugador_has_bottom_nav_no_drawer(client):
    client.force_login(UserFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert "data-bottom-nav" in content
    assert "data-mobile-menu-toggle" not in content
    assert "data-mobile-drawer" not in content


@pytest.mark.django_db
def test_gestor_has_drawer_no_bottom_nav(client):
    client.force_login(GestorFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert "data-mobile-menu-toggle" in content
    assert "data-mobile-drawer" in content
    assert "data-bottom-nav" not in content


@pytest.mark.django_db
def test_jugador_bottom_nav_has_four_player_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    start = content.find("data-bottom-nav")
    end = content.find("</nav>", start)
    bottom = content[start:end]
    assert reverse("competicion:dashboard") in bottom
    assert reverse("stats:rankings") in bottom
    assert reverse("stats:dashboard") in bottom
    assert reverse("core:rules") in bottom
    # Enlaces solo de gestor NO deben aparecer en la bottom nav.
    assert reverse("pot:manage_players") not in bottom
    assert reverse("competicion:manage_results") not in bottom
    assert reverse("pot:prizes") not in bottom


@pytest.mark.django_db
def test_gestor_drawer_contains_seven_links_and_actions(client):
    client.force_login(GestorFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    start = content.find('id="mobile-drawer"')
    end = content.find("</div>\n{%", start)
    if end == -1:
        # En el HTML renderizado el {% endif %} ya está resuelto; buscamos
        # el cierre del div del drawer.
        end = content.find("</nav>", start)
        end = content.find("</div>", end)
    drawer = content[start:end]
    for url in [
        reverse("competicion:dashboard"),
        reverse("stats:rankings"),
        reverse("stats:dashboard"),
        reverse("core:rules"),
        reverse("pot:manage_players"),
        reverse("competicion:manage_results"),
        reverse("pot:prizes"),
    ]:
        assert url in drawer, f"falta en drawer: {url}"
    assert "data-theme-toggle" in drawer
    assert reverse("accounts:logout") in drawer
