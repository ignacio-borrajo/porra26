from datetime import timedelta

import pytest
from django.utils import timezone

from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory
from stats.services.matchday_options import (
    KO_SCOPE_KEY,
    KO_SCOPE_LABEL,
    matchday_options,
)


@pytest.mark.django_db
def test_matchday_options_groups_yield_one_per_matchday():
    grp = RoundFactory(id="groups", label="Grupos", short="G", order=1)
    now = timezone.now()
    for md in (1, 2, 3):
        MatchFactory(
            round=grp,
            matchday=md,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=now + timedelta(days=md),
        )

    labels = [o.label for o in matchday_options()]
    assert labels == ["Jornada 1", "Jornada 2", "Jornada 3"]


@pytest.mark.django_db
def test_matchday_options_collapses_ko_rounds_into_fases_finales():
    grp = RoundFactory(id="groups", label="Grupos", short="G", order=1)
    r32 = RoundFactory(id="r32", label="Dieciseisavos", short="R32", order=2)
    r16 = RoundFactory(id="r16", label="Octavos", short="R16", order=3)
    qf = RoundFactory(id="qf", label="Cuartos", short="QF", order=4)
    sf = RoundFactory(id="sf", label="Semifinales", short="SF", order=5)
    final = RoundFactory(id="final", label="Final", short="F", order=6)
    now = timezone.now()
    MatchFactory(
        round=grp,
        matchday=1,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=1),
    )
    for i, rnd in enumerate((r32, r16, qf, sf, final), start=10):
        MatchFactory(
            round=rnd,
            matchday=None,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=now + timedelta(days=i),
        )

    options = matchday_options()
    labels = [o.label for o in options]
    assert labels == ["Jornada 1", KO_SCOPE_LABEL]

    fases = options[-1]
    assert fases.key == KO_SCOPE_KEY
    assert fases.round_ids == ["r32", "r16", "qf", "sf", "final"]
    assert fases.round_id is None
    assert fases.matchday is None


@pytest.mark.django_db
def test_matchday_options_fases_finales_fully_resolved_only_when_all_ko_done():
    r32 = RoundFactory(id="r32", label="Dieciseisavos", short="R32", order=2)
    final = RoundFactory(id="final", label="Final", short="F", order=6)
    now = timezone.now()
    MatchFactory(
        round=r32,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    MatchFactory(
        round=final,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=2),
    )

    fases = matchday_options()[-1]
    assert fases.label == KO_SCOPE_LABEL
    assert fases.fully_resolved is False
