"""Tests de render para la banda de partidos en juego en Rankings."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore, Team
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_live_strip_renders_match_with_score(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    home = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    away = Team.objects.create(code="FRA", name="Francia", flag="🇫🇷")
    m = MatchFactory(
        round=grp, home=home, away=away, kickoff=timezone.now() - timedelta(minutes=10)
    )
    LiveScore.objects.create(match=m, home_score=2, away_score=1, period="2H", minute=70)

    res = client.get(reverse("stats:rankings"))
    html = res.content.decode()

    assert "live-strip" in html
    assert "EN JUEGO" in html
    assert "ESP" in html and "FRA" in html
    assert ">2<" in html and ">1<" in html  # los score-bubbles


@pytest.mark.django_db
def test_live_strip_renders_empty_placeholder(client):
    user = UserFactory()
    client.force_login(user)
    RoundFactory(id="groups", points=3, order=1)

    res = client.get(reverse("stats:rankings"))

    assert "No hay partidos en juego ahora mismo." in res.content.decode()


@pytest.mark.django_db
def test_live_strip_does_not_leak_template_comments(client):
    """`{# ... #}` solo cierra una línea; los multilínea se escapaban como texto."""
    user = UserFactory()
    client.force_login(user)
    RoundFactory(id="groups", points=3, order=1)

    res = client.get(reverse("stats:rankings"))
    html = res.content.decode()

    assert "{#" not in html
    assert "#}" not in html
    assert "live_matches, awaiting_matches" not in html


@pytest.mark.django_db
def test_live_strip_renders_awaiting_chip(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    home = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    away = Team.objects.create(code="BRA", name="Brasil", flag="🇧🇷")
    m = MatchFactory(round=grp, home=home, away=away, kickoff=timezone.now() - timedelta(hours=2))
    LiveScore.objects.create(match=m, home_score=1, away_score=1, period="FT", minute=95)

    res = client.get(reverse("stats:rankings"))
    html = res.content.decode()

    assert "live-strip__chip--awaiting" in html
    assert "Pendiente oficial" in html


@pytest.mark.django_db
def test_autorefresh_script_only_when_live(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=0, away_score=0, period="1H", minute=5)

    res_live = client.get(reverse("stats:rankings"))
    assert b"live-autorefresh" in res_live.content

    m.delete()  # ya no quedan live
    res_calm = client.get(reverse("stats:rankings"))
    assert b"live-autorefresh" not in res_calm.content


@pytest.mark.django_db
def test_group_detail_renders_live_strip(client):
    user = UserFactory(sede="vigo")
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    home = Team.objects.create(code="POR", name="Portugal", flag="🇵🇹")
    away = Team.objects.create(code="GER", name="Alemania", flag="🇩🇪")
    m = MatchFactory(
        round=grp, home=home, away=away, kickoff=timezone.now() - timedelta(minutes=15)
    )
    LiveScore.objects.create(match=m, home_score=1, away_score=2, period="2H", minute=65)

    res = client.get(reverse("stats:rankings_group", kwargs={"dim": "sede", "key": "vigo"}))
    html = res.content.decode()

    assert "live-strip" in html
    assert "POR" in html and "GER" in html
    assert b"live-autorefresh" in res.content
