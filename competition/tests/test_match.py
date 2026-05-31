from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from competition.models import Match, Round, Team


@pytest.fixture
def setup_match(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    esp = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    arg = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    return grp, esp, arg


def _match(round, home, away, kickoff, **kw):
    return Match.objects.create(
        round=round, group="A", matchday=1, home=home, away=away, kickoff=kickoff, **kw
    )


@pytest.mark.django_db
def test_status_open_when_far_from_kickoff(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() + timedelta(hours=10))
        assert m.status == "open"


@pytest.mark.django_db
def test_status_closing_within_two_hours(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() + timedelta(hours=3))
        assert m.status == "closing"


@pytest.mark.django_db
def test_status_closed_after_close_before_kickoff(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() + timedelta(minutes=30))
        assert m.status == "closed"


@pytest.mark.django_db
def test_status_live_after_kickoff_without_result(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() - timedelta(minutes=10))
        assert m.status == "live"


@pytest.mark.django_db
def test_status_done_when_result_set(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() - timedelta(hours=3), result_home=2, result_away=1)
        assert m.status == "done"
