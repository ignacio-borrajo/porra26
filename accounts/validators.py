import os

from django.core.exceptions import ValidationError


def _allowed_domains() -> list[str]:
    raw = os.getenv("EMAIL_DOMAIN", "")
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def validate_email_domain(email: str) -> None:
    allowed = _allowed_domains()
    if not allowed:
        return
    domain = email.lower().rsplit("@", 1)[-1]
    if domain not in allowed:
        raise ValidationError(
            f"El correo debe pertenecer a uno de los dominios permitidos: {', '.join(allowed)}."
        )
