"""Tests del estado "pendiente oficial" (match terminado, sin validar)."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.models import LiveScore
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_awaiting_validation_true_when_live_with_ft_period():
    match = MatchFactory(kickoff=timezone.now() - timedelta(hours=2), external_id="ext-ft")
    LiveScore.objects.create(match=match, home_score=2, away_score=1, period="FT", minute=90)
    assert match.awaiting_validation is True


@pytest.mark.django_db
def test_awaiting_validation_false_when_still_playing():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=30), external_id="ext-2h")
    LiveScore.objects.create(match=match, home_score=1, away_score=0, period="2H", minute=70)
    assert match.awaiting_validation is False


@pytest.mark.django_db
def test_awaiting_validation_false_when_no_live_score():
    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=5), external_id="ext-no-ls")
    assert match.awaiting_validation is False


@pytest.mark.django_db
def test_awaiting_validation_false_when_done():
    match = MatchFactory(
        kickoff=timezone.now() - timedelta(hours=3),
        external_id="ext-done",
        result_home=2,
        result_away=1,
    )
    LiveScore.objects.create(match=match, home_score=2, away_score=1, period="FT", minute=90)
    assert match.awaiting_validation is False


@pytest.mark.django_db
def test_dashboard_categorizes_awaiting_separately(client):
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)
    grp = RoundFactory(id="groups", points=3, order=1)

    still_live = MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(minutes=10),
        external_id="L-still",
    )
    LiveScore.objects.create(match=still_live, home_score=1, away_score=0, period="2H", minute=60)

    awaiting = MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(hours=2),
        external_id="L-await",
    )
    LiveScore.objects.create(match=awaiting, home_score=2, away_score=2, period="FT", minute=90)

    res = client.get(reverse("competicion:dashboard"))
    live_ids = {m.id for m in res.context["live_matches"]}
    awaiting_ids = {m.id for m in res.context["awaiting_matches"]}

    assert live_ids == {still_live.id}
    assert awaiting_ids == {awaiting.id}


@pytest.mark.django_db
def test_dashboard_html_shows_pendiente_oficial_section(client):
    alice = UserFactory(must_change_password=False)
    client.force_login(alice)
    grp = RoundFactory(id="groups", points=3, order=1)

    match = MatchFactory(
        round=grp,
        kickoff=timezone.now() - timedelta(hours=2),
        external_id="L-html",
    )
    LiveScore.objects.create(match=match, home_score=1, away_score=1, period="FT", minute=90)

    res = client.get(reverse("competicion:dashboard"))
    html = res.content.decode("utf-8")
    assert "PENDIENTE OFICIAL" in html.upper() or "Pendiente oficial" in html
    assert "chip-awaiting" in html


@pytest.mark.django_db
def test_official_modal_prefills_with_live_score_when_no_official_result(client):
    """El modal oficial muestra el marcador de LiveScore como valor por defecto."""
    gestor = GestorFactory(must_change_password=False)
    client.force_login(gestor)

    match = MatchFactory(
        kickoff=timezone.now() - timedelta(hours=2),
        external_id="ext-prefill",
    )
    LiveScore.objects.create(match=match, home_score=3, away_score=1, period="FT", minute=90)

    res = client.get(reverse("competicion:official", args=[match.id]))
    html = res.content.decode("utf-8")
    assert 'name="home" type="text" inputmode="numeric" data-max="20" value="3"' in html
    assert 'name="away" type="text" inputmode="numeric" data-max="20" value="1"' in html


@pytest.mark.django_db
def test_official_modal_uses_official_result_when_already_set(client):
    """Si ya hay resultado oficial, los inputs muestran el oficial, no el LiveScore."""
    gestor = GestorFactory(must_change_password=False)
    client.force_login(gestor)

    match = MatchFactory(
        kickoff=timezone.now() - timedelta(hours=3),
        external_id="ext-already",
        result_home=2,
        result_away=2,
    )
    LiveScore.objects.create(match=match, home_score=99, away_score=99, period="FT", minute=90)

    res = client.get(reverse("competicion:official", args=[match.id]))
    html = res.content.decode("utf-8")
    assert 'value="2"' in html
    assert 'value="99"' not in html


@pytest.mark.django_db
def test_official_modal_defaults_to_zero_when_no_live_score(client):
    """Sin LiveScore ni resultado oficial, los inputs siguen siendo 0."""
    gestor = GestorFactory(must_change_password=False)
    client.force_login(gestor)

    match = MatchFactory(kickoff=timezone.now() - timedelta(minutes=5))

    res = client.get(reverse("competicion:official", args=[match.id]))
    html = res.content.decode("utf-8")
    assert 'name="home" type="text" inputmode="numeric" data-max="20" value="0"' in html
    assert 'name="away" type="text" inputmode="numeric" data-max="20" value="0"' in html
