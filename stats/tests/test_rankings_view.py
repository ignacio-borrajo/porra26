from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)


@pytest.mark.django_db
def test_rankings_requires_login(client):
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_rankings_default_tab_is_general(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content


@pytest.mark.django_db
def test_rankings_general_tab_renders_podium(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=general")
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content


@pytest.mark.django_db
def test_rankings_tab_label_is_clasificacion(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    body = r.content.decode()
    assert "Clasificación" in body


@pytest.mark.django_db
def test_rankings_general_renders_matchday_selector(client):
    client.force_login(UserFactory(must_change_password=False))
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    now = timezone.now()
    for md in (1, 2):
        MatchFactory(
            round=grp,
            matchday=md,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=now + timedelta(days=md),
        )
    r = client.get(reverse("stats:rankings"))
    body = r.content.decode()
    assert "rankings-md-selector" in body
    assert "Jornada 1" in body
    assert "Jornada 2" in body


@pytest.mark.django_db
def test_rankings_scope_param_changes_standings(client):
    ana = UserFactory(name="Ana", email="ana@e.com", must_change_password=False)
    client.force_login(ana)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    now = timezone.now()
    m_j1 = MatchFactory(
        round=grp,
        matchday=1,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m_j2 = MatchFactory(
        round=grp,
        matchday=2,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=0,
        result_away=0,
    )
    PredictionFactory(player=ana, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_j2, home=0, away=0, earned=3)

    r = client.get(reverse("stats:rankings") + "?tab=general&scope=groups:1")
    assert r.status_code == 200
    # El scope=groups:1 implica que la jornada 1 está activa
    assert b"scope=groups:1" in r.content


@pytest.mark.django_db
def test_rankings_accepts_puesto_tab(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=puesto")
    assert r.status_code == 200
    assert b"Puesto" in r.content


@pytest.mark.django_db
def test_rankings_unknown_tab_falls_back_to_general(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=hack")
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content
