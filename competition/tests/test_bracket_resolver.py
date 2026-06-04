from datetime import timedelta

import pytest
from django.utils import timezone

from competition.models import Match
from competition.services.bracket import propagate_after_match, resolve_slot
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="GRP", short="GRP", order=1)


def _played(round_, group, home, away, hg, ag, matchday=1, **kw):
    """Crea un Match ya con resultado oficial."""
    return MatchFactory(
        round=round_,
        group=group,
        matchday=matchday,
        home=home,
        away=away,
        result_home=hg,
        result_away=ag,
        finished_at=timezone.now(),
        kickoff=timezone.now() - timedelta(days=1),
        exact_points_applied=round_.points,
        partial_points_applied=round_.partial_points,
        **kw,
    )


@pytest.mark.django_db
def test_resolve_1a_returns_leader_when_group_complete(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    # ESP gana sus 3 partidos → líder claro
    _played(groups_round, "A", esp, arg, 2, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 1, matchday=1)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 2, 1, matchday=2)
    _played(groups_round, "A", esp, bra, 3, 0, matchday=3)
    _played(groups_round, "A", arg, fra, 0, 0, matchday=3)
    assert resolve_slot("1A") == esp


@pytest.mark.django_db
def test_resolve_1a_returns_none_when_group_incomplete(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    _played(groups_round, "A", esp, arg, 2, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 1, matchday=1)
    # falta partido
    MatchFactory(
        round=groups_round,
        group="A",
        matchday=2,
        home=esp,
        away=fra,
        kickoff=timezone.now() + timedelta(days=1),
    )
    assert resolve_slot("1A") is None


@pytest.mark.django_db
def test_resolve_2a_returns_runner_up(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    # ESP: 9pts, ARG: 6pts, FRA: 3pts, BRA: 0pts
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=3)
    assert resolve_slot("2A") == arg


@pytest.mark.django_db
def test_resolve_3a_returns_third_place(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=3)
    assert resolve_slot("3A") == fra


@pytest.mark.django_db
def test_resolve_unknown_slot_returns_none(db):
    assert resolve_slot("XYZ") is None
    assert resolve_slot("") is None
    assert resolve_slot("4A") is None


@pytest.mark.django_db
def test_resolve_wm_returns_winner_in_90():
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    _played(r32, "R32", esp, arg, 2, 1, matchday=None, bracket_code="M49")
    assert resolve_slot("WM49") == esp


@pytest.mark.django_db
def test_resolve_wm_returns_none_on_draw():
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    _played(r32, "R32", esp, arg, 1, 1, matchday=None, bracket_code="M50")
    assert resolve_slot("WM50") is None


@pytest.mark.django_db
def test_resolve_wm_returns_none_when_no_result():
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        bracket_code="M51",
        kickoff=timezone.now() + timedelta(days=1),
    )
    assert resolve_slot("WM51") is None


@pytest.mark.django_db
def test_resolve_wm_unknown_code(db):
    assert resolve_slot("WM999") is None


@pytest.mark.django_db
def test_propagate_fills_r32_when_groups_a_and_b_close(groups_round):
    """Al cerrar el grupo A, el R32 que dependía de 1A/2B se rellena
    (si el grupo B ya estaba cerrado)."""
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    ned = TeamFactory(code="NED")
    ger = TeamFactory(code="GER")
    bel = TeamFactory(code="BEL")
    por = TeamFactory(code="POR")
    # Grupo B ya cerrado: NED 1º, GER 2º
    _played(groups_round, "B", ned, ger, 1, 0, matchday=1)
    _played(groups_round, "B", bel, por, 0, 0, matchday=1)
    _played(groups_round, "B", ned, bel, 1, 0, matchday=2)
    _played(groups_round, "B", ger, por, 2, 0, matchday=2)
    _played(groups_round, "B", ned, por, 3, 0, matchday=3)
    _played(groups_round, "B", ger, bel, 1, 0, matchday=3)
    # Grupo A: cerramos todos los partidos. ESP 1º, ARG 2º.
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    last = _played(groups_round, "A", esp, fra, 1, 0, matchday=3)

    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M73",
        kickoff=timezone.now() + timedelta(days=10),
    )

    updated = propagate_after_match(last)
    ko.refresh_from_db()
    assert ko.home == esp
    assert ko.away == ger
    assert ko in updated


@pytest.mark.django_db
def test_propagate_is_idempotent_does_not_overwrite(groups_round):
    """Si el gestor ya asignó manualmente un equipo, propagate no lo sobrescribe."""
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    custom = TeamFactory(code="ZZZ")
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=custom,
        away=None,
        home_slot="1A",
        away_slot="",
        bracket_code="M74",
        kickoff=timezone.now() + timedelta(days=10),
    )
    propagate_after_match(ko)
    ko.refresh_from_db()
    assert ko.home == custom


@pytest.mark.django_db
def test_resolve_match_hooks_propagation(groups_round):
    """Confirmar un resultado debe invocar propagate y rellenar KO dependientes."""
    from accounts.models import User

    from competition.services.resolve import resolve_match

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    ned = TeamFactory(code="NED")
    ger = TeamFactory(code="GER")
    bel = TeamFactory(code="BEL")
    por = TeamFactory(code="POR")
    _played(groups_round, "B", ned, ger, 1, 0, matchday=1)
    _played(groups_round, "B", bel, por, 0, 0, matchday=1)
    _played(groups_round, "B", ned, bel, 1, 0, matchday=2)
    _played(groups_round, "B", ger, por, 2, 0, matchday=2)
    _played(groups_round, "B", ned, por, 3, 0, matchday=3)
    _played(groups_round, "B", ger, bel, 1, 0, matchday=3)
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    # Último partido del grupo A sin resolver todavía
    last = MatchFactory(
        round=groups_round,
        group="A",
        matchday=3,
        home=esp,
        away=fra,
        kickoff=timezone.now() - timedelta(hours=1),
    )
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M75",
        kickoff=timezone.now() + timedelta(days=10),
    )

    gestor = User.objects.create(email="g@x.es", is_gestor=True, name="G", is_active=True)
    resolve_match(last, home=1, away=0, actor=gestor)

    ko.refresh_from_db()
    assert ko.home == esp
    assert ko.away == ger
