import json
import re

import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory
from pot.forms import generate_suggested_password, SetPlayerPasswordForm


def test_generate_suggested_password_meets_rules():
    for _ in range(50):
        pwd = generate_suggested_password()
        assert len(pwd) >= 10
        assert any(ch.isupper() for ch in pwd)
        assert any(ch.isdigit() for ch in pwd)
        # No espacios ni caracteres raros que rompan al copiarla en un correo.
        assert re.fullmatch(r"[A-Za-z0-9!@#$%&*?-]+", pwd)


def test_generate_suggested_password_is_not_deterministic():
    samples = {generate_suggested_password() for _ in range(20)}
    assert len(samples) >= 18  # entropía suficiente


def _data(new1="Abcdefghi1", new2=None):
    return {"new1": new1, "new2": new2 if new2 is not None else new1}


def test_set_player_password_form_valid():
    form = SetPlayerPasswordForm(data=_data())
    assert form.is_valid(), form.errors


def test_set_player_password_form_min_length():
    form = SetPlayerPasswordForm(data=_data(new1="Abc1", new2="Abc1"))
    assert not form.is_valid()
    assert "new1" in form.errors


def test_set_player_password_form_requires_upper_and_digit():
    form = SetPlayerPasswordForm(data=_data(new1="abcdefghij", new2="abcdefghij"))
    assert not form.is_valid()
    assert any("mayúscula" in e for e in form.errors.get("__all__", []))


def test_set_player_password_form_requires_digit_when_upper_present():
    form = SetPlayerPasswordForm(data=_data(new1="Abcdefghij", new2="Abcdefghij"))
    assert not form.is_valid()
    assert any("mayúscula" in e for e in form.errors.get("__all__", []))


def test_set_player_password_form_mismatch():
    form = SetPlayerPasswordForm(data=_data(new1="Abcdefghi1", new2="Abcdefghi2"))
    assert not form.is_valid()
    assert any("no coinciden" in e for e in form.errors.get("__all__", []))


def test_set_player_password_form_renders_value_for_re_render():
    # PasswordInput por defecto oculta el value tras un POST inválido.
    # Aquí queremos preservar lo tecleado: render_value=True.
    form = SetPlayerPasswordForm(initial={"new1": "Hola12345A", "new2": "Hola12345A"})
    html = form.as_p()
    assert 'value="Hola12345A"' in html


@pytest.mark.django_db
def test_get_requires_gestor(client):
    client.force_login(UserFactory())
    target = UserFactory()
    r = client.get(reverse("pot:player_set_password", args=[target.id]))
    assert r.status_code == 302  # redirect a dashboard


@pytest.mark.django_db
def test_get_renders_modal_with_suggestion(client):
    client.force_login(GestorFactory())
    target = UserFactory()
    r = client.get(
        reverse("pot:player_set_password", args=[target.id]),
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert b"<html" not in r.content.lower()  # es fragmento
    assert target.name.encode() in r.content
    # El formulario está presente (contendrá los inputs pre-rellenados tras Task 6).
    body = r.content.decode()
    assert "method=\"post\"" in body
    assert "class=\"glass pop\"" in body


@pytest.mark.django_db
def test_get_suggest_returns_json(client):
    client.force_login(GestorFactory())
    target = UserFactory()
    r = client.get(
        reverse("pot:player_set_password", args=[target.id]) + "?suggest=1"
    )
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/json")
    payload = json.loads(r.content)
    pwd = payload["password"]
    assert len(pwd) >= 10
    assert any(ch.isupper() for ch in pwd)
    assert any(ch.isdigit() for ch in pwd)


@pytest.mark.django_db
def test_get_404_for_unknown_user(client):
    client.force_login(GestorFactory())
    r = client.get(reverse("pot:player_set_password", args=[99999]))
    assert r.status_code == 404


from accounts.models import AuditLog


@pytest.mark.django_db
def test_post_valid_changes_password_and_forces_change(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory(must_change_password=False)
    old_hash = target.password
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Nueva1234X", "new2": "Nueva1234X"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Redirect") == reverse("pot:manage_players")
    target.refresh_from_db()
    assert target.password != old_hash
    assert target.check_password("Nueva1234X")
    assert target.must_change_password is True
    log = AuditLog.objects.get(action="password_set_by_manager", target_id=str(target.id))
    assert log.actor_id == g.id
    assert log.payload == {"self": False}


@pytest.mark.django_db
def test_post_self_does_not_force_change_and_keeps_session(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    r = client.post(
        reverse("pot:player_set_password", args=[g.id]),
        {"new1": "MiNueva1Pwd", "new2": "MiNueva1Pwd"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    g.refresh_from_db()
    assert g.check_password("MiNueva1Pwd")
    assert g.must_change_password is False
    log = AuditLog.objects.get(action="password_set_by_manager", target_id=str(g.id))
    assert log.payload == {"self": True}
    # Sesión sigue activa: una vista protegida responde 200.
    r2 = client.get(reverse("pot:manage_players"))
    assert r2.status_code == 200


@pytest.mark.django_db
def test_post_mismatch_re_renders_with_errors(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory()
    old_hash = target.password
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Abcdefghi1", "new2": "Abcdefghi2"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Errors") == "1"
    target.refresh_from_db()
    assert target.password == old_hash
    assert not AuditLog.objects.filter(action="password_set_by_manager").exists()


@pytest.mark.django_db
def test_post_short_password_re_renders(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory()
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Abc1", "new2": "Abc1"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Errors") == "1"


@pytest.mark.django_db
def test_post_no_uppercase_re_renders(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory()
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "abcdefghij1", "new2": "abcdefghij1"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Errors") == "1"


@pytest.mark.django_db
def test_post_requires_gestor(client):
    client.force_login(UserFactory())
    target = UserFactory()
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Nueva1234X", "new2": "Nueva1234X"},
    )
    assert r.status_code == 302
    target.refresh_from_db()
    assert not target.check_password("Nueva1234X")
