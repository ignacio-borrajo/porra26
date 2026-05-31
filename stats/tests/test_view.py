import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


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
def test_chart_data_returns_json(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("stats:chart_data"))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/json")
