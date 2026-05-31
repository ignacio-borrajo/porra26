import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_middleware_redirects_when_must_change_password(client):
    u = UserFactory(must_change_password=True)
    u.set_password("Test123!")
    u.save()
    client.force_login(u)
    r = client.get("/competicion/")
    assert r.status_code == 302
    assert reverse("accounts:change_password") in r.url


@pytest.mark.django_db
def test_middleware_allows_change_password_route(client):
    u = UserFactory(must_change_password=True)
    u.set_password("Test123!")
    u.save()
    client.force_login(u)
    r = client.get(reverse("accounts:change_password"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_middleware_allows_logout(client):
    u = UserFactory(must_change_password=True)
    client.force_login(u)
    r = client.post(reverse("accounts:logout"))
    assert r.status_code == 302
