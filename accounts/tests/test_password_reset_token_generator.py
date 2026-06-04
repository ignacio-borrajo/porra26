from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from accounts.services.token_generator import token_generator
from accounts.tests.factories import UserFactory


@pytest.fixture
def alice(db):
    return UserFactory(email="alice@edisa.com", password="OldPwd1234!")


def test_token_difiere_segun_purpose(alice):
    reset = token_generator.make_token(alice, "reset")
    welcome = token_generator.make_token(alice, "welcome")
    assert reset != welcome


def test_check_token_valido_mismo_purpose(alice):
    token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, token, "reset") is True


def test_check_token_rechaza_purpose_cruzado(alice):
    reset_token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, reset_token, "welcome") is False

    welcome_token = token_generator.make_token(alice, "welcome")
    assert token_generator.check_token(alice, welcome_token, "reset") is False


def test_check_token_caduca_reset_a_24h(alice):
    base = datetime(2026, 6, 4, 12, 0, 0)
    with patch.object(token_generator, "_now", return_value=base):
        token = token_generator.make_token(alice, "reset")

    with patch.object(
        token_generator,
        "_now",
        return_value=base + timedelta(hours=23, minutes=59),
    ):
        assert token_generator.check_token(alice, token, "reset") is True

    with patch.object(
        token_generator,
        "_now",
        return_value=base + timedelta(hours=24, minutes=1),
    ):
        assert token_generator.check_token(alice, token, "reset") is False


def test_check_token_caduca_welcome_a_7d(alice):
    base = datetime(2026, 6, 4, 12, 0, 0)
    with patch.object(token_generator, "_now", return_value=base):
        token = token_generator.make_token(alice, "welcome")

    with patch.object(
        token_generator,
        "_now",
        return_value=base + timedelta(days=6, hours=23),
    ):
        assert token_generator.check_token(alice, token, "welcome") is True

    with patch.object(
        token_generator,
        "_now",
        return_value=base + timedelta(days=7, hours=1),
    ):
        assert token_generator.check_token(alice, token, "welcome") is False


def test_token_invalidado_al_cambiar_password(alice):
    token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, token, "reset") is True

    alice.set_password("NuevaPwd1234!")
    alice.save(update_fields=["password"])
    assert token_generator.check_token(alice, token, "reset") is False


def test_make_token_rechaza_purpose_desconocido(alice):
    with pytest.raises(ValueError):
        token_generator.make_token(alice, "bogus")


def test_check_token_rechaza_purpose_desconocido(alice):
    token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, token, "bogus") is False


def test_check_token_rechaza_token_malformado(alice):
    assert token_generator.check_token(alice, "no-es-un-token", "reset") is False
    assert token_generator.check_token(alice, "", "reset") is False
    assert token_generator.check_token(None, "anything", "reset") is False
