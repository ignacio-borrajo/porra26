import pytest
from django.urls import reverse

from accounts.models import AuditLog
from accounts.tests.factories import GestorFactory, UserFactory
from pot.tests.factories import PaymentFactory
from raffle.models import Raffle
from raffle.services import start_raffle


def _make_players(n):
    for _ in range(n):
        PaymentFactory(player=UserFactory(), paid=True)


@pytest.mark.django_db
def test_draw_requiere_login(client):
    r = client.get(reverse("raffle:draw"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_draw_abierta_a_jugadores(client):
    _make_players(3)
    client.force_login(UserFactory())
    r = client.get(reverse("raffle:draw"))
    assert r.status_code == 200
    html = r.content.decode()
    assert "Activar sonido" in html
    assert "Iniciar sorteo" not in html  # el botón es solo del gestor


@pytest.mark.django_db
def test_draw_muestra_boton_iniciar_al_gestor(client):
    _make_players(3)
    client.force_login(GestorFactory())
    r = client.get(reverse("raffle:draw"))
    assert r.status_code == 200
    assert "Iniciar sorteo" in r.content.decode()


@pytest.mark.django_db
def test_draw_sin_sorteo_muestra_elegibles(client):
    _make_players(3)
    client.force_login(UserFactory())  # sin pago: no cuenta como elegible
    data = client.get(reverse("raffle:draw")).context["state"]
    assert len(data["participants"]) == 3
    assert all(p["eliminatedOrder"] is None for p in data["participants"])


@pytest.mark.django_db
def test_estado_requiere_login(client):
    r = client.get(reverse("raffle:state"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_estado_devuelve_json_a_jugadores(client):
    _make_players(2)
    client.force_login(UserFactory())
    r = client.get(reverse("raffle:state"))
    assert r.status_code == 200
    data = r.json()
    assert data["startedAtMs"] is None
    assert len(data["participants"]) == 2


@pytest.mark.django_db
def test_iniciar_requiere_gestor(client):
    _make_players(2)
    client.force_login(UserFactory())
    r = client.post(reverse("raffle:start"))
    assert r.status_code == 302
    assert not Raffle.objects.exists()


@pytest.mark.django_db
def test_iniciar_crea_el_guion_y_audita(client):
    _make_players(5)
    client.force_login(GestorFactory())

    r = client.post(reverse("raffle:start"))

    assert r.status_code == 200
    data = r.json()
    assert data["startedAtMs"] is not None
    raffle = Raffle.objects.get()
    assert raffle.entries.filter(eliminated_order__isnull=False).count() == 4
    assert AuditLog.objects.filter(action="raffle_start").count() == 1


@pytest.mark.django_db
def test_iniciar_dos_veces_devuelve_400(client):
    _make_players(3)
    client.force_login(GestorFactory())
    client.post(reverse("raffle:start"))

    r = client.post(reverse("raffle:start"))

    assert r.status_code == 400


@pytest.mark.django_db
def test_reset_borra_el_sorteo(client):
    _make_players(3)
    start_raffle()
    client.force_login(GestorFactory())

    r = client.post(reverse("raffle:reset"))

    assert r.status_code == 302
    assert not Raffle.objects.exists()
    assert AuditLog.objects.filter(action="raffle_reset").count() == 1


@pytest.mark.django_db
def test_topbar_muestra_sorteo_a_todos(client):
    client.force_login(GestorFactory())
    assert reverse("raffle:draw") in client.get(reverse("competicion:dashboard")).content.decode()

    client.force_login(UserFactory())
    assert reverse("raffle:draw") in client.get(reverse("competicion:dashboard")).content.decode()
