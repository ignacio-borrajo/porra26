import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_rankings_requires_login(client):
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_rankings_default_tab_is_sede(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 200
    assert b"Sede" in r.content


@pytest.mark.django_db
def test_rankings_accepts_puesto_tab(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=puesto")
    assert r.status_code == 200
    assert b"Puesto" in r.content


@pytest.mark.django_db
def test_rankings_unknown_tab_falls_back_to_sede(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=hack")
    assert r.status_code == 200
