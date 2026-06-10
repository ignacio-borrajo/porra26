"""Tests para la integración de live_standings + live scores en CompetitionView."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_dashboard_uses_live_standings_when_live_match_has_score(client):
    """Si Alice apostó y va ganando en directo, sus pts en la tabla incluyen el live."""
    alice = UserFactory(name="Alice", must_change_password=False)
    bob = UserFactory(name="Bob", must_change_password=False)
    client.force_login(alice)

    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    live = MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(minutes=10),
        external_id="ext-live-dash",
    )
    LiveScore.objects.create(match=live, home_score=2, away_score=1, period="2H", minute=70)
    PredictionFactory(player=alice, match=live, home=2, away=1)
    PredictionFactory(player=bob, match=live, home=0, away=0)

    res = client.get(reverse("competicion:dashboard"))
    assert res.status_code == 200

    standings = res.context["standings"]
    alice_row = next(r for r in standings if r.player_id == alice.id)
    assert alice_row.pts == grp.points
    bob_row = next(r for r in standings if r.player_id == bob.id)
    assert bob_row.pts == 0


@pytest.mark.django_db
def test_dashboard_max_pts_reflects_live(client):
    alice = UserFactory(name="Alice", must_change_password=False)
    client.force_login(alice)

    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    live = MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(minutes=10),
        external_id="ext-maxpts",
    )
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)
    PredictionFactory(player=alice, match=live, home=1, away=0)

    res = client.get(reverse("competicion:dashboard"))
    assert res.context["max_pts"] == grp.points


@pytest.mark.django_db
def test_dashboard_exposes_has_live_matches_flag(client):
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)

    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10), external_id="L")
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2), external_id="O")

    res = client.get(reverse("competicion:dashboard"))
    assert res.context["has_live_matches"] is True


@pytest.mark.django_db
def test_dashboard_has_live_matches_false_when_none_live(client):
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)

    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2), external_id="O")

    res = client.get(reverse("competicion:dashboard"))
    assert res.context["has_live_matches"] is False


@pytest.mark.django_db
def test_dashboard_match_card_shows_live_score_instead_of_vs(client):
    """Cuando el match está live y tiene LiveScore, el HTML muestra el marcador parcial."""
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(minutes=10),
        external_id="ext-card",
    )
    LiveScore.objects.create(match=live, home_score=3, away_score=1, period="2H", minute=80)

    res = client.get(reverse("competicion:dashboard"))
    html = res.content.decode("utf-8")
    assert "match-card-live" in html
    assert ">3<" in html
    assert ">1<" in html
    assert "live-colon" in html or "colon-live" in html


@pytest.mark.django_db
def test_dashboard_match_card_keeps_vs_when_live_without_score(client):
    """Match live recién kickoff, sin LiveScore todavía → seguir mostrando VS."""
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)

    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(seconds=30),
        external_id="ext-no-livescore",
    )

    res = client.get(reverse("competicion:dashboard"))
    html = res.content.decode("utf-8")
    assert ">VS<" in html


@pytest.mark.django_db
def test_dashboard_renders_autorefresh_script_only_when_live(client):
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)
    grp = RoundFactory(id="groups", points=3, order=1)

    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2), external_id="O")
    res_no_live = client.get(reverse("competicion:dashboard"))
    assert b"live-autorefresh" not in res_no_live.content

    MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10), external_id="L")
    res_live = client.get(reverse("competicion:dashboard"))
    assert b"live-autorefresh" in res_live.content
