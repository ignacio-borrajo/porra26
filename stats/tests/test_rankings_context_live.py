"""Tests para que build_general_context() use puntos live."""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.rankings_context import build_general_context


@pytest.mark.django_db
def test_general_standings_include_live_points():
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice")
    bob = UserFactory(name="Bob")

    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=2, away_score=1, period="2H", minute=70)
    PredictionFactory(player=alice, match=m, home=2, away=1)
    PredictionFactory(player=bob, match=m, home=0, away=0)

    ctx = build_general_context(alice, requested_scope_key=None)

    rows_by_player = {r.player_id: r for r in ctx["standings"]}
    assert rows_by_player[alice.id].pts == grp.points
    assert rows_by_player[bob.id].pts == 0


@pytest.mark.django_db
def test_scope_standings_include_live_points():
    """El scope (jornada/ronda) también suma puntos hipotéticos."""
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice")

    m = MatchFactory(round=grp, matchday=1, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=1, away_score=0, period="1H", minute=20)
    PredictionFactory(player=alice, match=m, home=1, away=0)

    ctx = build_general_context(alice, requested_scope_key="groups:1")

    scope_rows_by_player = {r.player_id: r for r in ctx["scope_standings"]}
    assert scope_rows_by_player[alice.id].pts == grp.points


@pytest.mark.django_db
def test_no_live_matches_keeps_standings_unchanged():
    """Sin LiveScore, live_pts == pts → comportamiento idéntico al antiguo."""
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice")
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2))
    PredictionFactory(player=alice, match=m, home=1, away=0)

    ctx = build_general_context(alice, requested_scope_key=None)

    assert all(r.pts == 0 for r in ctx["standings"])
