from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore
from competition.services.live_standings import live_standings
from competition.services.score import score
from competition.tests.factories import MatchFactory, PredictionFactory


def _mark_earned(pred):
    pred.earned = score(pred, pred.match)
    pred.save(update_fields=["earned"])
    return pred


@pytest.mark.django_db
def test_live_standings_includes_hypothetical_points_for_live_match():
    alice = UserFactory(name="Alice")
    bob = UserFactory(name="Bob")
    live = MatchFactory(kickoff=timezone.now() - timedelta(minutes=20), external_id="L1")
    LiveScore.objects.create(match=live, home_score=2, away_score=1, period="2H", minute=78)
    PredictionFactory(player=alice, match=live, home=2, away=1)
    PredictionFactory(player=bob, match=live, home=0, away=0)

    rows = live_standings()
    by_name = {r.name: r for r in rows}

    assert by_name["Alice"].pts == 0
    assert by_name["Alice"].live_pts == live.round.points
    assert by_name["Bob"].pts == 0
    assert by_name["Bob"].live_pts == 0


@pytest.mark.django_db
def test_live_standings_adds_partial_points_for_correct_winner():
    """Alice acierta solo el resultado (no el marcador exacto): 1·X·2 points."""
    alice = UserFactory(name="Alice")
    live = MatchFactory(kickoff=timezone.now() - timedelta(minutes=15), external_id="L2")
    LiveScore.objects.create(match=live, home_score=3, away_score=1, period="2H", minute=70)
    PredictionFactory(player=alice, match=live, home=2, away=0)

    rows = live_standings()
    by_name = {r.name: r for r in rows}
    assert by_name["Alice"].live_pts == live.round.partial_points


@pytest.mark.django_db
def test_live_standings_combines_official_and_live_points():
    alice = UserFactory(name="Alice")
    done = MatchFactory(
        kickoff=timezone.now() - timedelta(hours=3),
        external_id="D1",
        result_home=1,
        result_away=0,
    )
    _mark_earned(PredictionFactory(player=alice, match=done, home=1, away=0))

    live = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10), external_id="L3")
    LiveScore.objects.create(match=live, home_score=2, away_score=2, period="2H", minute=60)
    PredictionFactory(player=alice, match=live, home=2, away=2)

    rows = live_standings()
    alice_row = next(r for r in rows if r.name == "Alice")
    assert alice_row.pts == done.exact_points_applied
    assert alice_row.live_pts == done.exact_points_applied + live.round.points


@pytest.mark.django_db
def test_live_standings_no_live_score_means_zero_extra():
    alice = UserFactory(name="Alice")
    live = MatchFactory(kickoff=timezone.now() - timedelta(minutes=5), external_id="L4")
    PredictionFactory(player=alice, match=live, home=1, away=0)
    assert not LiveScore.objects.filter(match=live).exists()

    rows = live_standings()
    alice_row = next(r for r in rows if r.name == "Alice")
    assert alice_row.pts == 0
    assert alice_row.live_pts == 0


@pytest.mark.django_db
def test_live_standings_ignores_predictions_without_live_score_on_done_match():
    """Si un partido se resolvió ya, sus puntos se cuentan vía Prediction.earned;
    no se vuelven a sumar usando LiveScore aunque exista."""
    alice = UserFactory(name="Alice")
    done = MatchFactory(
        kickoff=timezone.now() - timedelta(hours=4),
        external_id="D2",
        result_home=2,
        result_away=2,
    )
    _mark_earned(PredictionFactory(player=alice, match=done, home=2, away=2))
    LiveScore.objects.create(match=done, home_score=2, away_score=2, period="FT", minute=90)

    rows = live_standings()
    alice_row = next(r for r in rows if r.name == "Alice")
    assert alice_row.pts == done.exact_points_applied
    assert alice_row.live_pts == done.exact_points_applied


@pytest.mark.django_db
def test_live_standings_sorts_by_live_pts():
    a = UserFactory(name="Aaa")
    b = UserFactory(name="Bbb")
    live = MatchFactory(kickoff=timezone.now() - timedelta(minutes=10), external_id="LS")
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)
    PredictionFactory(player=a, match=live, home=1, away=0)
    PredictionFactory(player=b, match=live, home=0, away=1)

    rows = live_standings()
    assert rows[0].name == "Aaa"
    assert rows[0].position == 1
    b_row = next(r for r in rows if r.name == "Bbb")
    assert b_row.live_pts == 0
