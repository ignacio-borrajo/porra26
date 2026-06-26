import pytest

from accounts.tests.factories import GestorFactory
from competition.services.bracket import propagate_after_match
from competition.services.resolve import resolve_match
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture(autouse=True)
def _rounds(db):
    RoundFactory(id="groups", points=3, order=1)
    RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)


@pytest.mark.django_db
def test_r32_no_autofill_from_group_standings():
    a, b = TeamFactory(), TeamFactory()
    # Grupo A de 1 partido ya resuelto: standings calculables.
    MatchFactory(
        round_id="groups", group="A", matchday=1, home=a, away=b, result_home=1, result_away=0
    )
    # Cruce R32 que apunta a "1A".
    r32 = MatchFactory(
        round_id="r32",
        group="Dieciseisavos",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2A",
        bracket_code="M73",
    )
    propagate_after_match(r32)
    r32.refresh_from_db()
    assert r32.home_id is None and r32.away_id is None  # NO autorrelleno


@pytest.mark.django_db
def test_r16_autofills_from_r32_winner():
    actor = GestorFactory()
    a, b = TeamFactory(), TeamFactory()
    r32 = MatchFactory(
        round_id="r32",
        group="Dieciseisavos",
        matchday=None,
        home=a,
        away=b,
        home_slot="1A",
        away_slot="2A",
        bracket_code="M73",
    )
    r16 = MatchFactory(
        round_id="r16",
        group="Octavos",
        matchday=None,
        home=None,
        away=None,
        home_slot="WM73",
        away_slot="WM75",
        bracket_code="M89",
    )
    resolve_match(r32, home=2, away=1, actor=actor)
    r16.refresh_from_db()
    assert r16.home_id == a.code  # ganador de M73 propagado a octavos
