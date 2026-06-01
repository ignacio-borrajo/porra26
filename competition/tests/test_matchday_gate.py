from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from competition.services.matchday_gate import (
    is_matchday_open,
    previous_matchday_close_info,
)
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.mark.django_db
def test_matchday_one_is_always_open():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert is_matchday_open("groups", 1) is True


@pytest.mark.django_db
def test_none_matchday_is_always_open():
    RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    assert is_matchday_open("r16", None) is True


@pytest.mark.django_db
def test_empty_previous_matchday_means_open():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert is_matchday_open("groups", 2) is True


@pytest.mark.django_db
def test_matchday_two_blocked_while_md1_pending():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-15 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="AA1"),
            away=TeamFactory(code="AA2"),
            kickoff=timezone.now() + timedelta(hours=5),
        )
        assert is_matchday_open("groups", 2) is False


@pytest.mark.django_db
def test_matchday_two_open_when_all_md1_kicked_off():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-20 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="BB1"),
            away=TeamFactory(code="BB2"),
            kickoff=timezone.now() - timedelta(hours=2),
        )
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="BB3"),
            away=TeamFactory(code="BB4"),
            kickoff=timezone.now() - timedelta(minutes=1),
        )
        assert is_matchday_open("groups", 2) is True


@pytest.mark.django_db
def test_matchday_three_depends_on_md2_only():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-22 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="CC1"),
            away=TeamFactory(code="CC2"),
            kickoff=timezone.now() - timedelta(days=5),
        )
        MatchFactory(
            round=grp,
            matchday=2,
            home=TeamFactory(code="CC3"),
            away=TeamFactory(code="CC4"),
            kickoff=timezone.now() + timedelta(hours=2),
        )
        assert is_matchday_open("groups", 3) is False


@pytest.mark.django_db
def test_previous_matchday_close_info_returns_last_kickoff():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-15 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="DD1"),
            away=TeamFactory(code="DD2"),
            kickoff=timezone.now() + timedelta(hours=1),
        )
        last = MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="DD3"),
            away=TeamFactory(code="DD4"),
            kickoff=timezone.now() + timedelta(hours=8),
        )
        match, kickoff = previous_matchday_close_info("groups", 2)
        assert match.id == last.id
        assert kickoff == last.kickoff


@pytest.mark.django_db
def test_previous_matchday_close_info_none_when_no_prev():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert previous_matchday_close_info("groups", 1) == (None, None)
    assert previous_matchday_close_info("groups", 2) == (None, None)
