import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_login_get_renders(client):
    r = client.get(reverse("accounts:login"))
    assert r.status_code == 200
    assert b"Bienvenido" in r.content


@pytest.mark.django_db
def test_login_post_success(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    u = UserFactory(email="a@edisa.com", must_change_password=False)
    u.set_password("Secret123!")
    u.save()
    r = client.post(reverse("accounts:login"), {"email": "a@edisa.com", "password": "Secret123!"})
    assert r.status_code == 302


@pytest.mark.django_db
def test_login_post_wrong_password(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    u = UserFactory(email="a@edisa.com")
    u.set_password("Right123!")
    u.save()
    r = client.post(reverse("accounts:login"), {"email": "a@edisa.com", "password": "Wrong123!"})
    assert r.status_code == 200
    assert b"incorrectos" in r.content


@pytest.mark.django_db
def test_login_post_domain_blocked(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    r = client.post(reverse("accounts:login"), {"email": "x@gmail.com", "password": "x"})
    assert r.status_code == 200
    assert b"dominios permitidos" in r.content
