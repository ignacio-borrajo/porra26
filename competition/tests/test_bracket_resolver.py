from datetime import timedelta

import pytest
from django.utils import timezone

from competition.models import Match
from competition.services.bracket import resolve_slot
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
