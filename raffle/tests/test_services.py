import pytest

from accounts.tests.factories import UserFactory
from pot.tests.factories import PaymentFactory
from raffle.models import Raffle, RaffleEntry
from raffle.services import get_or_create_raffle, spin


def _make_players(n):
    users = []
    for _ in range(n):
        u = UserFactory()
        PaymentFactory(player=u, paid=True)
        users.append(u)
    return users


@pytest.mark.django_db
def test_snapshot_solo_activos_jugadores_pagados():
    pagado = UserFactory()
    PaymentFactory(player=pagado, paid=True)
    sin_pagar = UserFactory()
    PaymentFactory(player=sin_pagar, paid=False)
    inactivo = UserFactory(is_active=False)
    PaymentFactory(player=inactivo, paid=True)
    no_jugador = UserFactory(is_jugador=False)
    PaymentFactory(player=no_jugador, paid=True)
    UserFactory()  # sin Payment

    raffle = get_or_create_raffle()

    players = {e.player for e in raffle.entries.all()}
    assert players == {pagado}


@pytest.mark.django_db
def test_get_or_create_reutiliza_el_sorteo_existente():
    _make_players(3)
    r1 = get_or_create_raffle()
    r2 = get_or_create_raffle()
    assert r1 == r2
    assert Raffle.objects.count() == 1


@pytest.mark.django_db
def test_snapshot_congela_participantes():
    _make_players(3)
    raffle = get_or_create_raffle()
    _make_players(1)  # alta posterior: no entra
    assert get_or_create_raffle() == raffle
    assert raffle.entries.count() == 3


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("restantes", "tanda"),
    [(70, 5), (21, 5), (18, 3), (17, 2), (16, 1), (15, 1), (5, 1), (2, 1)],
)
def test_tamano_de_tanda(restantes, tanda):
    _make_players(restantes)
    raffle = get_or_create_raffle()

    eliminated, remaining, winner = spin(raffle)

    assert len(eliminated) == tanda
    assert remaining == restantes - tanda


@pytest.mark.django_db
def test_orden_de_eliminacion_secuencial():
    _make_players(20)
    raffle = get_or_create_raffle()

    spin(raffle)  # elimina 5
    spin(raffle)  # elimina 1 (quedan 15 -> de uno en uno)

    orders = list(
        raffle.entries.filter(eliminated_order__isnull=False)
        .order_by("eliminated_order")
        .values_list("eliminated_order", flat=True)
    )
    assert orders == [1, 2, 3, 4, 5, 6]


@pytest.mark.django_db
def test_spin_con_dos_restantes_devuelve_ganador():
    _make_players(2)
    raffle = get_or_create_raffle()

    eliminated, remaining, winner = spin(raffle)

    assert len(eliminated) == 1
    assert remaining == 1
    assert winner is not None
    assert winner.eliminated_order is None
    assert winner != eliminated[0]


@pytest.mark.django_db
def test_spin_sin_restantes_suficientes_lanza_error():
    _make_players(2)
    raffle = get_or_create_raffle()
    spin(raffle)

    with pytest.raises(ValueError):
        spin(raffle)


@pytest.mark.django_db
def test_spin_sin_participantes_lanza_error():
    raffle = get_or_create_raffle()
    assert not RaffleEntry.objects.exists()
    with pytest.raises(ValueError):
        spin(raffle)
