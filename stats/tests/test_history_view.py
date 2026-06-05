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
def test_historico_requires_login(client):
    r = client.get(reverse("stats:historico"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_historico_renders_matrix_for_authenticated_user(client):
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    esp = TeamFactory(code="ESP", name="España", flag="🇪🇸")
    fra = TeamFactory(code="FRA", name="Francia", flag="🇫🇷")
    m = MatchFactory(
        round=grp,
        home=esp,
        away=fra,
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=1,
        finished_at=now,
    )
    ana = UserFactory(name="Ana López", email="ana@edisa.com")
    PredictionFactory(player=ana, match=m, home=2, away=1, earned=3)

    client.force_login(ana)
    r = client.get(reverse("stats:historico"))
    assert r.status_code == 200
    body = r.content.decode()
    assert "Ana López" in body
    assert "ESP" in body and "FRA" in body
    assert "2-1" in body  # marcador oficial y pronóstico


@pytest.mark.django_db
def test_historico_includes_export_link(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:historico"))
    body = r.content.decode()
    assert reverse("stats:historico_export") in body


@pytest.mark.django_db
def test_historico_omits_unfinished_matches(client):
    grp = RoundFactory(id="groups", points=3, partial_points=1, short="G", order=1)
    now = timezone.now()
    finished = MatchFactory(
        round=grp,
        home=TeamFactory(code="AAA", name="Aaa"),
        away=TeamFactory(code="BBB", name="Bbb"),
        kickoff=now - timedelta(days=1),
        result_home=0,
        result_away=0,
        finished_at=now,
    )
    open_match = MatchFactory(
        round=grp,
        home=TeamFactory(code="CCC", name="Ccc"),
        away=TeamFactory(code="DDD", name="Ddd"),
        kickoff=now + timedelta(days=2),
    )

    client.force_login(UserFactory())
    r = client.get(reverse("stats:historico"))
    body = r.content.decode()
    assert "AAA" in body and "BBB" in body
    assert "CCC" not in body and "DDD" not in body
    _ = finished, open_match
