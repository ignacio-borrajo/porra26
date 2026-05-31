import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_profile_requires_login(client):
    r = client.get(reverse("accounts:profile"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_profile_get_shows_user_fields(client):
    u = UserFactory(name="Ana", sede="vigo", puesto="desarrollo")
    client.force_login(u)
    r = client.get(reverse("accounts:profile"))
    assert r.status_code == 200
    assert b"Ana" in r.content
    assert b"vigo" in r.content or b"Vigo" in r.content


@pytest.mark.django_db
def test_profile_post_updates_fields(client):
    u = UserFactory(name="Antes", sede="")
    client.force_login(u)
    r = client.post(
        reverse("accounts:profile"),
        {
            "name": "Después",
            "dept": "nominas",
            "sede": "madrid",
            "puesto": "sistemas",
        },
    )
    assert r.status_code == 302
    u.refresh_from_db()
    assert u.name == "Después"
    assert u.dept == "nominas"
    assert u.sede == "madrid"
    assert u.puesto == "sistemas"


@pytest.mark.django_db
def test_profile_post_cannot_grant_flags(client):
    u = UserFactory(is_gestor=False, is_jugador=True)
    client.force_login(u)
    client.post(
        reverse("accounts:profile"),
        {
            "name": u.name,
            "dept": "",
            "sede": "",
            "puesto": "",
            "is_gestor": "on",  # debería ser ignorado
            "is_jugador": "",  # debería ser ignorado
            "email": "hacker@evil.com",
        },
    )
    u.refresh_from_db()
    assert u.is_gestor is False
    assert u.is_jugador is True
    assert u.email != "hacker@evil.com"
