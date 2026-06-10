"""Tests del comando seed_match_external_ids."""

from __future__ import annotations

import io
import json
from datetime import UTC, datetime
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.test import override_settings

from competition.models import Match
from competition.tests.factories import MatchFactory, TeamFactory


def _fd_response(matches: list[dict]):
    body = json.dumps({"matches": matches}).encode("utf-8")

    class _Fake(io.BytesIO):
        def __enter__(self):
            return self

        def __exit__(self, *args):
            self.close()

    return _Fake(body)


def _fd_match(*, id_, utc_date, home_tla, away_tla):
    return {
        "id": id_,
        "utcDate": utc_date,
        "homeTeam": {"tla": home_tla, "name": home_tla},
        "awayTeam": {"tla": away_tla, "name": away_tla},
    }


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="key", FOOTBALL_DATA_COMPETITION="WC")
@patch("competition.management.commands.seed_match_external_ids.urlopen")
def test_seed_matches_by_date_and_team_tla(urlopen):
    arg = TeamFactory(code="ARG")
    bra = TeamFactory(code="BRA")
    kickoff = datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
    match = MatchFactory(home=arg, away=bra, kickoff=kickoff)
    assert match.external_id is None

    urlopen.return_value = _fd_response(
        [_fd_match(id_=99001, utc_date="2026-06-14T18:00:00Z", home_tla="ARG", away_tla="BRA")]
    )

    call_command("seed_match_external_ids")

    match.refresh_from_db()
    assert match.external_id == "99001"


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="key")
@patch("competition.management.commands.seed_match_external_ids.urlopen")
def test_seed_skips_matches_already_with_external_id(urlopen):
    arg = TeamFactory(code="ARG")
    bra = TeamFactory(code="BRA")
    kickoff = datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
    match = MatchFactory(home=arg, away=bra, kickoff=kickoff, external_id="already-set")

    urlopen.return_value = _fd_response(
        [_fd_match(id_=99001, utc_date="2026-06-14T18:00:00Z", home_tla="ARG", away_tla="BRA")]
    )

    call_command("seed_match_external_ids")

    match.refresh_from_db()
    assert match.external_id == "already-set"


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="key")
@patch("competition.management.commands.seed_match_external_ids.urlopen")
def test_seed_with_force_overwrites_existing(urlopen):
    arg = TeamFactory(code="ARG")
    bra = TeamFactory(code="BRA")
    kickoff = datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
    match = MatchFactory(home=arg, away=bra, kickoff=kickoff, external_id="old-id")

    urlopen.return_value = _fd_response(
        [_fd_match(id_=99002, utc_date="2026-06-14T18:00:00Z", home_tla="ARG", away_tla="BRA")]
    )

    call_command("seed_match_external_ids", "--force")

    match.refresh_from_db()
    assert match.external_id == "99002"


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="key")
@patch("competition.management.commands.seed_match_external_ids.urlopen")
def test_seed_ignores_match_with_unknown_teams(urlopen):
    """Si las TLAs de football-data no coinciden con ningún Match nuestro, se omite."""
    arg = TeamFactory(code="ARG")
    bra = TeamFactory(code="BRA")
    kickoff = datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
    MatchFactory(home=arg, away=bra, kickoff=kickoff)

    urlopen.return_value = _fd_response(
        [_fd_match(id_=99003, utc_date="2026-06-14T18:00:00Z", home_tla="ZZZ", away_tla="YYY")]
    )

    call_command("seed_match_external_ids")
    assert not Match.objects.exclude(external_id__isnull=True).exists()


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="key")
@patch("competition.management.commands.seed_match_external_ids.urlopen")
def test_seed_matches_when_team_order_is_swapped(urlopen):
    """Si football-data invierte home/away, también lo casamos."""
    arg = TeamFactory(code="ARG")
    bra = TeamFactory(code="BRA")
    kickoff = datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
    match = MatchFactory(home=arg, away=bra, kickoff=kickoff)

    urlopen.return_value = _fd_response(
        [_fd_match(id_=99004, utc_date="2026-06-14T18:00:00Z", home_tla="BRA", away_tla="ARG")]
    )

    call_command("seed_match_external_ids")

    match.refresh_from_db()
    assert match.external_id == "99004"


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="")
def test_seed_errors_without_api_key():
    from django.core.management.base import CommandError

    with pytest.raises(CommandError):
        call_command("seed_match_external_ids")


@pytest.mark.django_db
@override_settings(FOOTBALL_DATA_API_KEY="key")
@patch("competition.management.commands.seed_match_external_ids.urlopen")
def test_seed_dry_run_does_not_persist(urlopen):
    arg = TeamFactory(code="ARG")
    bra = TeamFactory(code="BRA")
    kickoff = datetime(2026, 6, 14, 18, 0, tzinfo=UTC)
    match = MatchFactory(home=arg, away=bra, kickoff=kickoff)

    urlopen.return_value = _fd_response(
        [_fd_match(id_=99005, utc_date="2026-06-14T18:00:00Z", home_tla="ARG", away_tla="BRA")]
    )

    call_command("seed_match_external_ids", "--dry-run")

    match.refresh_from_db()
    assert match.external_id is None
