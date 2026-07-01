import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_stats_requires_login(client):
    r = client.get(reverse("stats:dashboard"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_stats_renders(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("stats:dashboard"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_stats_renders_charts_with_data(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    me = UserFactory(must_change_password=False)
    other = UserFactory(name="Rival")
    for earned, p in [(3, me), (1, me), (1, other), (0, other)]:
        m = MatchFactory(round=grp, result_home=1, result_away=0)
        PredictionFactory(player=p, match=m, earned=earned)
    client.force_login(me)
    html = client.get(reverse("stats:dashboard")).content.decode()
    assert "data-evo-canvas" in html  # gráfica de evolución
    assert "data-donut-canvas" in html  # donut
    assert "Tú frente al grupo" in html  # panel comparativo
    assert "js/vendor/chart.umd.min.js" in html  # Chart.js cargado


@pytest.mark.django_db
def test_chart_data_returns_json(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("stats:chart_data"))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/json")
    data = r.json()
    assert "me" in data
    assert "finished" in data
    assert "players" in data
    assert isinstance(data["players"], list)
