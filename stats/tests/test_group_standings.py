from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import Prediction
from competition.tests.factories import MatchFactory, RoundFactory
from stats.services.group_standings import group_standings


@pytest.fixture
def finished_match(db):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(days=2))
    m.result_home, m.result_away, m.finished_at = 1, 0, timezone.now()
    m.save()
    return m


@pytest.mark.django_db
def test_group_standings_sede_aggregates_totals(finished_match):
    a = UserFactory(sede="vigo", is_jugador=True)
    b = UserFactory(sede="vigo", is_jugador=True)
    c = UserFactory(sede="madrid", is_jugador=True)
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=2, away=1, earned=1)
    Prediction.objects.create(player=c, match=finished_match, home=0, away=0, earned=0)

    rows = {r.key: r for r in group_standings("sede")}
    assert rows["vigo"].total == 4
    assert rows["vigo"].players == 2
    assert rows["vigo"].avg == 2.0
    assert rows["madrid"].total == 0
    assert rows["madrid"].players == 1


@pytest.mark.django_db
def test_group_standings_includes_choices_without_members():
    UserFactory(sede="vigo", is_jugador=True)
    keys = {r.key for r in group_standings("sede")}
    assert {"ourense", "vigo", "asturias", "madrid", "barcelona"}.issubset(keys)


@pytest.mark.django_db
def test_group_standings_orphan_users_go_to_sin_asignar():
    UserFactory(sede="", is_jugador=True)
    rows = group_standings("sede")
    last = rows[-1]
    assert last.key == "__none__"
    assert last.label == "Sin asignar"
    assert last.players == 1


@pytest.mark.django_db
def test_group_standings_orders_by_avg_then_total(finished_match):
    a = UserFactory(sede="vigo", is_jugador=True)
    b = UserFactory(sede="madrid", is_jugador=True)
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=0, away=2, earned=0)

    rows = [r for r in group_standings("sede") if r.players > 0 and r.key != "__none__"]
    assert rows[0].key == "vigo"  # avg 3 > avg 0


@pytest.mark.django_db
def test_group_standings_ignores_non_jugadores(finished_match):
    invisible = UserFactory(sede="vigo", is_jugador=False)
    Prediction.objects.create(player=invisible, match=finished_match, home=1, away=0, earned=3)
    rows = {r.key: r for r in group_standings("sede")}
    assert rows["vigo"].players == 0
    assert rows["vigo"].total == 0


@pytest.mark.django_db
def test_group_standings_records_top_player(finished_match):
    a = UserFactory(sede="vigo", is_jugador=True, name="Ana")
    b = UserFactory(sede="vigo", is_jugador=True, name="Beto")
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=2, away=2, earned=1)
    rows = {r.key: r for r in group_standings("sede")}
    assert rows["vigo"].top_name == "Ana"
    assert rows["vigo"].top_pts == 3
    assert rows["vigo"].top_user_id == a.id
    assert rows["vigo"].top_tied_count == 1


@pytest.mark.django_db
def test_group_leader_chip_shows_tied_count_when_multiple_leaders(finished_match):
    """Si dos jugadores del mismo grupo empatan tras las 3 reglas, top_tied_count refleja el empate."""
    a = UserFactory(sede="vigo", is_jugador=True, name="Borja")
    b = UserFactory(sede="vigo", is_jugador=True, name="Ana")
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=1, away=0, earned=3)
    rows = {r.key: r for r in group_standings("sede")}
    target = rows["vigo"]
    assert target.top_pts == 3
    assert target.top_tied_count == 2
    assert target.top_name == "Ana"  # alfabético dentro del empate


@pytest.mark.django_db
def test_group_standings_has_dense_position_with_ties(finished_match):
    """Dos sedes con la misma media comparten posición; la siguiente no salta."""
    UserFactory(sede="vigo", is_jugador=True, name="V1")  # avg 0
    UserFactory(sede="madrid", is_jugador=True, name="M1")  # avg 0
    UserFactory(sede="barcelona", is_jugador=True, name="B1")  # avg 0
    rows = [r for r in group_standings("sede") if r.players > 0 and r.key != "__none__"]
    # Las tres con jugadores tienen avg 0, total 0 → todas en posición 1
    positions = sorted({r.position for r in rows})
    assert positions == [1]
    for r in rows:
        assert r.is_tied is True
