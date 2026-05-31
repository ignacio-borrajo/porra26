import pytest
from django.core.exceptions import ValidationError

from accounts.validators import validate_email_domain


def test_validate_email_domain_accepts_allowed(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    validate_email_domain("a@edisa.com")  # no raise


def test_validate_email_domain_rejects_other(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    with pytest.raises(ValidationError):
        validate_email_domain("a@gmail.com")


def test_validate_email_domain_case_insensitive(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    validate_email_domain("A@EDISA.COM")
