import pytest
from django.core.management import call_command

from competition.models import Match, Prediction
from competition.tests.factories import (
    MatchFactory, PredictionFactory, RoundFactory, TeamFactory,
)


@pytest.fixture(autouse=True)
def _rounds(db):
    for rid, order in [("groups", 1), ("r32", 2), ("r16", 3),
                       ("qf", 4), ("sf", 5), ("final", 6)]:
        RoundFactory(id=rid, order=order, short=rid.upper())


@pytest.mark.django_db
def test_reset_returns_r32_to_pending_and_clears_predictions():
    call_command("seed_world_cup_2026")
    m = Match.objects.get(bracket_code="M73")
    a, b = TeamFactory(code="AA1"), TeamFactory(code="BB1")
    m.home, m.away = a, b
    m.result_home, m.result_away = 2, 1
    m.save()
    PredictionFactory(match=m, home=2, away=1)

    call_command("reset_r32_crosses")

    m.refresh_from_db()
    assert m.home_id is None and m.away_id is None
    assert m.result_home is None and m.result_away is None
    assert m.status == "pending_teams"
    assert m.kickoff.isoformat().startswith("2026-06-28T19:00")
    assert m.bracket_order == 3
    assert not Prediction.objects.filter(match=m).exists()


@pytest.mark.django_db
def test_reset_clears_downstream_ko_teams():
    call_command("seed_world_cup_2026")
    r16 = Match.objects.get(bracket_code="M89")
    r16.home = TeamFactory(code="CC1")
    r16.save()
    call_command("reset_r32_crosses")
    r16.refresh_from_db()
    assert r16.home_id is None


@pytest.mark.django_db
def test_reset_removes_ko_winner_announcements():
    from announcements.models import WinnerAnnouncement

    call_command("seed_world_cup_2026")
    WinnerAnnouncement.objects.create(scope_kind="r32", points=10)
    # Un anuncio de grupos NO debe borrarse.
    WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=5)

    call_command("reset_r32_crosses")

    assert not WinnerAnnouncement.objects.filter(scope_kind="r32").exists()
    assert WinnerAnnouncement.objects.filter(scope_kind="matchday").exists()
