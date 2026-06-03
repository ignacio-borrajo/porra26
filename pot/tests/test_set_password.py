import re

from pot.forms import generate_suggested_password


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
