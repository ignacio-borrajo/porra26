"""Tests para que las vistas de Rankings inyecten partidos live al contexto."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_rankings_context_includes_live_matches(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)

    res = client.get(reverse("stats:rankings"))

    assert res.status_code == 200
    assert [m.id for m in res.context["live_matches"]] == [live.id]
    assert res.context["awaiting_matches"] == []
    assert res.context["has_live_matches"] is True


@pytest.mark.django_db
def test_rankings_context_has_live_matches_false_when_none(client):
    user = UserFactory()
    client.force_login(user)
    RoundFactory(id="groups", points=3, order=1)

    res = client.get(reverse("stats:rankings"))

    assert res.context["live_matches"] == []
    assert res.context["awaiting_matches"] == []
    assert res.context["has_live_matches"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("tab", ["general", "sede", "puesto", "dept"])
def test_rankings_live_context_present_in_all_tabs(client, tab):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)

    res = client.get(reverse("stats:rankings"), {"tab": tab})

    assert res.status_code == 200
    assert [m.id for m in res.context["live_matches"]] == [live.id]
    assert res.context["has_live_matches"] is True


@pytest.mark.django_db
def test_group_rankings_context_includes_live_matches(client):
    user = UserFactory(sede="vigo")
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=2, away_score=2, period="2H", minute=80)

    res = client.get(reverse("stats:rankings_group", kwargs={"dim": "sede", "key": "vigo"}))

    assert res.status_code == 200
    assert [m.id for m in res.context["live_matches"]] == [live.id]
    assert res.context["has_live_matches"] is True
