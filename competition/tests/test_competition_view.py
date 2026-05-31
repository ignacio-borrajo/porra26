from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_dashboard_shows_matches(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_predict_post_creates_prediction(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    assert m.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_predict_post_rejected_when_live(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=1))  # live
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 1, "away": 0})
    assert r.status_code == 403


@pytest.mark.django_db
def test_manage_results_requires_gestor(client):
    u = UserFactory(must_change_password=False, role="jugador")
    client.force_login(u)
    r = client.get(reverse("competicion:manage_results"))
    assert r.status_code == 302  # redirect to dashboard


@pytest.mark.django_db
def test_official_post_resolves_match(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=3))
    r = client.post(reverse("competicion:official", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (2, 1)
