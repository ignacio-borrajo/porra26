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
