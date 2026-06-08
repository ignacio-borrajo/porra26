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


@pytest.mark.django_db
def test_login_get_emits_diagnostic_log(client, caplog):
    """Log diagnóstico del bug 'logout en redeploy': cada hit a la página de
    login debe registrar qué ve Django (cookie, sesión, autenticación). Se usa
    para correlacionar picos de logout con su causa real."""
    import logging

    with caplog.at_level(logging.INFO, logger="accounts.views"):
        r = client.get(reverse("accounts:login"))
    assert r.status_code == 200
    diag = [rec for rec in caplog.records if "login.get" in rec.getMessage()]
    assert diag, "Se esperaba un log 'login.get ...' por cada GET a /"
    msg = diag[0].getMessage()
    assert "cookie_present=" in msg
    assert "session_loaded=" in msg
    assert "authenticated=" in msg


@pytest.mark.django_db
def test_login_get_log_does_not_leak_full_session_key(client, caplog):
    """El log nunca debe contener el sessionid completo: solo un prefijo de
    8 chars. Si esto rompe, alguien filtra credenciales en logs."""
    import logging

    # Simulamos que el cliente trae una cookie sessionid larga.
    client.cookies["sessionid"] = "a" * 32
    with caplog.at_level(logging.INFO, logger="accounts.views"):
        client.get(reverse("accounts:login"))
    diag = [rec for rec in caplog.records if "login.get" in rec.getMessage()]
    assert diag
    msg = diag[0].getMessage()
    assert "a" * 32 not in msg
    # El prefijo es 8 chars + un ellipsis.
    assert "aaaaaaaa…" in msg
