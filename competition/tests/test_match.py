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


@pytest.fixture
def setup_two_md(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    a = Team.objects.create(code="T1A", name="A1", flag="🏳️")
    b = Team.objects.create(code="T1B", name="B1", flag="🏳️")
    c = Team.objects.create(code="T2A", name="A2", flag="🏳️")
    d = Team.objects.create(code="T2B", name="B2", flag="🏳️")
    return grp, (a, b), (c, d)


@pytest.mark.django_db
def test_predictions_open_md1_when_editable(setup_two_md):
    grp, (a, b), _ = setup_two_md
    with freeze_time("2026-06-10 10:00:00", tz_offset=0):
        m = Match.objects.create(
            round=grp,
            group="A",
            matchday=1,
            home=a,
            away=b,
            kickoff=timezone.now() + timedelta(days=1),
        )
        assert m.editable is True
        assert m.predictions_open is True


@pytest.mark.django_db
def test_predictions_open_md2_blocked_by_gate(setup_two_md):
    grp, (a, b), (c, d) = setup_two_md
    with freeze_time("2026-06-10 10:00:00", tz_offset=0):
        Match.objects.create(
            round=grp,
            group="A",
            matchday=1,
            home=a,
            away=b,
            kickoff=timezone.now() + timedelta(hours=10),
        )
        m2 = Match.objects.create(
            round=grp,
            group="A",
            matchday=2,
            home=c,
            away=d,
            kickoff=timezone.now() + timedelta(days=8),
        )
        assert m2.editable is True
        assert m2.predictions_open is False


@pytest.mark.django_db
def test_predictions_open_false_when_not_editable(setup_two_md):
    grp, (a, b), _ = setup_two_md
    with freeze_time("2026-06-10 10:00:00", tz_offset=0):
        m = Match.objects.create(
            round=grp,
            group="A",
            matchday=1,
            home=a,
            away=b,
            kickoff=timezone.now() - timedelta(minutes=10),
        )
        assert m.editable is False
        assert m.predictions_open is False
