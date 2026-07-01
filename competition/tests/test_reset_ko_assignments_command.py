from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from competition.models import Prediction
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)


@pytest.fixture
def r32(db):
    return RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)


@pytest.mark.django_db
def test_reset_nulls_unfinished_ko_and_deletes_predictions(r32):
    ko = MatchFactory(
        round=r32,
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        kickoff=timezone.now() + timedelta(days=5),
    )
    PredictionFactory(match=ko, home=1, away=0)

    call_command("reset_ko_assignments")

    ko.refresh_from_db()
    assert ko.home is None and ko.away is None
    assert Prediction.objects.filter(match=ko).count() == 0


@pytest.mark.django_db
def test_reset_leaves_finished_ko_untouched(r32):
    done = MatchFactory(
        round=r32,
        matchday=None,
        home=TeamFactory(code="FRA"),
        away=TeamFactory(code="BRA"),
        result_home=2,
        result_away=1,
        kickoff=timezone.now() - timedelta(days=1),
    )
    PredictionFactory(match=done, home=2, away=1)

    call_command("reset_ko_assignments")

    done.refresh_from_db()
    assert done.home is not None and done.away is not None
    assert Prediction.objects.filter(match=done).count() == 1


@pytest.mark.django_db
def test_reset_dry_run_changes_nothing(r32):
    ko = MatchFactory(
        round=r32,
        matchday=None,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        kickoff=timezone.now() + timedelta(days=5),
    )
    PredictionFactory(match=ko, home=1, away=0)

    call_command("reset_ko_assignments", "--dry-run")

    ko.refresh_from_db()
    assert ko.home is not None and ko.away is not None
    assert Prediction.objects.filter(match=ko).count() == 1


@pytest.mark.django_db
def test_reset_ignores_group_matches(r32):
    groups = RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)
    gm = MatchFactory(
        round=groups,
        matchday=1,
        home=TeamFactory(code="ESP"),
        away=TeamFactory(code="ARG"),
        kickoff=timezone.now() + timedelta(days=1),
    )

    call_command("reset_ko_assignments")

    gm.refresh_from_db()
    assert gm.home is not None and gm.away is not None
