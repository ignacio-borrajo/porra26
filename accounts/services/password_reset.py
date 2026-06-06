"""Servicio de envío de emails de reset y bienvenida.

Centraliza la generación de URLs firmadas y el envío del email, para
que la vista pública y el endpoint del gestor compartan la misma
lógica (asunto, body, AuditLog).
"""

from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import AuditLog, User
from accounts.services.token_generator import token_generator

SUBJECTS = {
    "welcome": "¡Bienvenido a La Porra del Jefe! 🏆 Mundial FIFA 2026",
    "reset": "Restablece tu contraseña",
}

TEMPLATES = {
    "welcome": ("accounts/emails/welcome.html", "accounts/emails/welcome.txt"),
    "reset": ("accounts/emails/password_reset.html", "accounts/emails/password_reset.txt"),
}


def build_reset_url(user, purpose: str) -> str:
    if purpose not in SUBJECTS:
        raise ValueError(f"purpose desconocido: {purpose!r}")
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user, purpose)
    path = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": uidb64, "purpose": purpose, "token": token},
    )
    return urljoin(settings.SITE_URL, path)


def send_password_reset_email(user, purpose: str, actor=None) -> None:
    if purpose not in SUBJECTS:
        raise ValueError(f"purpose desconocido: {purpose!r}")
    reset_url = build_reset_url(user, purpose)
    logo_url = urljoin(settings.SITE_URL, static("img/logo.png"))
    ctx = {
        "user": user,
        "purpose": purpose,
        "reset_url": reset_url,
        "logo_url": logo_url,
    }
    html_template, text_template = TEMPLATES[purpose]
    html = render_to_string(html_template, ctx)
    text = render_to_string(text_template, ctx)
    subject = SUBJECTS[purpose]

    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.PASSWORD_RESET_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)

    AuditLog.objects.create(
        actor=actor,
        action="password_reset_email_sent",
        target_type="user",
        target_id=str(user.id),
        payload={"purpose": purpose, "subject": subject},
    )


def validate_reset_token(uidb64: str, purpose: str, token: str) -> User | None:
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not token_generator.check_token(user, token, purpose):
        return None
    return user


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
