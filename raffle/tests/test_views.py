import pytest
from django.urls import reverse

from accounts.models import AuditLog
from accounts.tests.factories import GestorFactory, UserFactory
from pot.tests.factories import PaymentFactory
from raffle.models import Raffle
from raffle.services import get_or_create_raffle, spin


def _make_players(n):
    for _ in range(n):
        PaymentFactory(player=UserFactory(), paid=True)


@pytest.mark.django_db
def test_draw_requiere_gestor(client):
    client.force_login(UserFactory())
    r = client.get(reverse("raffle:draw"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_draw_renderiza_para_gestor(client):
    _make_players(3)
    client.force_login(GestorFactory())
    r = client.get(reverse("raffle:draw"))
    assert r.status_code == 200
    assert "Que gire la ruleta" in r.content.decode()


@pytest.mark.django_db
def test_draw_sin_sorteo_muestra_elegibles(client):
    _make_players(3)
    client.force_login(GestorFactory())
    r = client.get(reverse("raffle:draw"))
    data = r.context["state"]
    assert len(data["participants"]) == 3
    assert all(p["eliminatedOrder"] is None for p in data["participants"])


@pytest.mark.django_db
def test_spin_requiere_gestor(client):
    client.force_login(UserFactory())
    r = client.post(reverse("raffle:spin"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_spin_elimina_y_devuelve_json(client):
    _make_players(20)
    client.force_login(GestorFactory())

    r = client.post(reverse("raffle:spin"))

    assert r.status_code == 200
    data = r.json()
    assert len(data["eliminated"]) == 5
    assert data["remaining"] == 15
    assert data["winner"] is None
    raffle = Raffle.objects.get()
    assert raffle.entries.filter(eliminated_order__isnull=False).count() == 5
    assert AuditLog.objects.filter(action="raffle_spin").count() == 1


@pytest.mark.django_db
def test_spin_devuelve_ganador(client):
    _make_players(2)
    client.force_login(GestorFactory())

    data = client.post(reverse("raffle:spin")).json()

    assert data["remaining"] == 1
    assert data["winner"] is not None


@pytest.mark.django_db
def test_spin_con_ganador_decidido_devuelve_400(client):
    _make_players(2)
    raffle = get_or_create_raffle()
    spin(raffle)
    client.force_login(GestorFactory())

    r = client.post(reverse("raffle:spin"))

    assert r.status_code == 400


@pytest.mark.django_db
def test_reset_borra_el_sorteo(client):
    _make_players(3)
    raffle = get_or_create_raffle()
    spin(raffle)
    client.force_login(GestorFactory())

    r = client.post(reverse("raffle:reset"))

    assert r.status_code == 302
    assert not Raffle.objects.exists()
    assert AuditLog.objects.filter(action="raffle_reset").count() == 1


@pytest.mark.django_db
def test_topbar_muestra_sorteo_solo_a_gestores(client):
    gestor = GestorFactory()
    client.force_login(gestor)
    assert reverse("raffle:draw") in client.get(reverse("competicion:dashboard")).content.decode()

    client.force_login(UserFactory())
    assert (
        reverse("raffle:draw") not in client.get(reverse("competicion:dashboard")).content.decode()
    )
