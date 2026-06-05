import pytest
from django.urls import reverse

from accounts.models import User
from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_manage_players_requires_gestor(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("pot:manage_players"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_manage_players_renders_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:manage_players"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_manage_players_sort_by_name(client):
    client.force_login(GestorFactory(must_change_password=False, name="ZZGestor"))
    UserFactory(name="AnaTest")
    UserFactory(name="LuisTest")
    UserFactory(name="MarioTest")

    r_asc = client.get(reverse("pot:manage_players"), {"sort": "name", "dir": "asc"})
    assert r_asc.status_code == 200
    body_asc = r_asc.content.decode()
    assert body_asc.index("AnaTest") < body_asc.index("LuisTest") < body_asc.index("MarioTest")

    r_desc = client.get(reverse("pot:manage_players"), {"sort": "name", "dir": "desc"})
    body_desc = r_desc.content.decode()
    assert body_desc.index("MarioTest") < body_desc.index("LuisTest") < body_desc.index("AnaTest")


@pytest.mark.django_db
def test_manage_players_sort_ignores_invalid_params(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:manage_players"), {"sort": "bogus", "dir": "sideways"})
    assert r.status_code == 200


@pytest.mark.django_db
def test_toggle_payment(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory()
    from pot.models import Payment

    Payment.objects.create(player=p, paid=False)
    r = client.post(reverse("pot:player_toggle_payment", args=[p.id]))
    assert r.status_code == 302
    assert Payment.objects.get(player=p).paid is True


@pytest.mark.django_db
def test_toggle_player_active(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory(is_active=True)
    r = client.post(reverse("pot:player_toggle_active", args=[p.id]))
    assert r.status_code == 302
    p.refresh_from_db()
    assert p.is_active is False


@pytest.mark.django_db
def test_reset_password_changes_password_and_shows_temp(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory(must_change_password=False)
    old_hash = p.password
    r = client.post(reverse("pot:player_reset", args=[p.id]))
    assert r.status_code == 200
    p.refresh_from_db()
    assert p.password != old_hash
    assert p.must_change_password is True


@pytest.mark.django_db
def test_player_new_get_returns_fragment_with_x_modal_header(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:player_new"), HTTP_X_MODAL="1")
    assert r.status_code == 200
    assert b"<html" not in r.content.lower()  # fragmento, no página completa
    assert b"Nuevo jugador" in r.content


@pytest.mark.django_db
def test_player_edit_post_ok_returns_x_modal_redirect(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    p = UserFactory()
    r = client.post(
        reverse("pot:player_edit", args=[p.id]),
        {
            "name": "Nuevo Nombre",
            "email": p.email,
            "dept": "",
            "sede": "",
            "puesto": "",
            "is_jugador": "on",
            "is_gestor": "",
        },
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Redirect", "").endswith("/gestion/jugadores/")


@pytest.mark.django_db
def test_player_new_post_ok_redirects_to_password_reveal(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    r = client.post(
        reverse("pot:player_new"),
        {
            "name": "Nuevo",
            "email": "nuevo@edisa.com",
            "dept": "",
            "sede": "",
            "puesto": "",
            "is_jugador": "on",
            "is_gestor": "",
        },
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    # El header apunta al password reveal de ese usuario.
    redirect = r.headers.get("X-Modal-Redirect", "")
    user = User.objects.get(email="nuevo@edisa.com")
    assert redirect == reverse("pot:player_reveal", args=[user.id])


@pytest.mark.django_db
def test_player_form_invalid_returns_x_modal_errors_header(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    r = client.post(
        reverse("pot:player_new"),
        {
            "name": "",
            "email": "no-email",
            "dept": "",
            "sede": "",
            "puesto": "",
            "is_jugador": "on",
            "is_gestor": "",
        },
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Errors") == "1"
