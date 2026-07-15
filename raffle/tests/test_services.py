from datetime import timedelta

import pytest

from accounts.tests.factories import UserFactory
from pot.tests.factories import PaymentFactory
from raffle.models import Raffle, RaffleEntry
from raffle.services import (
    CADENCE_SECONDS,
    REVEAL_AHEAD_SECONDS,
    public_state,
    start_raffle,
)


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
    otro = UserFactory()
    PaymentFactory(player=otro, paid=True)
    sin_pagar = UserFactory()
    PaymentFactory(player=sin_pagar, paid=False)
    inactivo = UserFactory(is_active=False)
    PaymentFactory(player=inactivo, paid=True)
    no_jugador = UserFactory(is_jugador=False)
    PaymentFactory(player=no_jugador, paid=True)
    UserFactory()  # sin Payment

    raffle = start_raffle()

    players = {e.player for e in raffle.entries.all()}
    assert players == {pagado, otro}


@pytest.mark.django_db
def test_start_precalcula_el_guion_completo():
    _make_players(10)

    raffle = start_raffle()

    assert raffle.started_at is not None
    eliminadas = raffle.entries.filter(eliminated_order__isnull=False).order_by("eliminated_order")
    assert [e.eliminated_order for e in eliminadas] == list(range(1, 10))
    for e in eliminadas:
        esperado = raffle.started_at + timedelta(seconds=e.eliminated_order * CADENCE_SECONDS)
        assert e.eliminated_at == esperado
    assert raffle.entries.filter(eliminated_order__isnull=True).count() == 1


@pytest.mark.django_db
def test_start_con_sorteo_en_marcha_lanza_error():
    _make_players(3)
    start_raffle()
    with pytest.raises(ValueError):
        start_raffle()


@pytest.mark.django_db
def test_start_sin_participantes_suficientes_lanza_error():
    _make_players(1)
    with pytest.raises(ValueError):
        start_raffle()
    assert not Raffle.objects.exists()


@pytest.mark.django_db
def test_start_descarta_sorteo_legado_sin_iniciar():
    jugadores = _make_players(3)
    legado = Raffle.objects.create()
    RaffleEntry.objects.bulk_create(RaffleEntry(raffle=legado, player=p) for p in jugadores)

    raffle = start_raffle()

    assert raffle.pk != legado.pk
    assert Raffle.objects.count() == 1
    assert raffle.entries.count() == 3


@pytest.mark.django_db
def test_public_state_sin_sorteo_lista_elegibles():
    _make_players(3)
    state = public_state()
    assert state["startedAtMs"] is None
    assert len(state["participants"]) == 3
    assert all(p["eliminatedOrder"] is None for p in state["participants"])


@pytest.mark.django_db
def test_public_state_no_revela_mas_alla_del_horizonte():
    _make_players(5)
    raffle = start_raffle()

    # En el arranque la primera caída (t+30s) queda fuera del horizonte (t+20s).
    state = public_state(now=raffle.started_at)
    assert all(p["eliminatedOrder"] is None for p in state["participants"])

    # A t+15s el horizonte llega a t+35s: se revela la primera caída y solo esa.
    state = public_state(now=raffle.started_at + timedelta(seconds=15))
    revelados = [p for p in state["participants"] if p["eliminatedOrder"] is not None]
    assert [p["eliminatedOrder"] for p in revelados] == [1]
    assert revelados[0]["eliminatedAtMs"] is not None


@pytest.mark.django_db
def test_public_state_al_final_revela_todo_el_guion():
    _make_players(5)
    raffle = start_raffle()

    fin = raffle.started_at + timedelta(seconds=5 * CADENCE_SECONDS)
    state = public_state(now=fin)

    ordenes = sorted(
        p["eliminatedOrder"] for p in state["participants"] if p["eliminatedOrder"] is not None
    )
    assert ordenes == [1, 2, 3, 4]
    assert sum(1 for p in state["participants"] if p["eliminatedOrder"] is None) == 1


@pytest.mark.django_db
def test_horizonte_menor_que_cadencia():
    # Si el horizonte alcanzara la cadencia se revelaría más de una caída futura.
    assert REVEAL_AHEAD_SECONDS < CADENCE_SECONDS
