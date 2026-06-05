from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone


def send_password_changed_email(user) -> None:
    """Avisa al usuario de que su contraseña ha sido cambiada.

    Se llama tras cualquier cambio efectivo (voluntario, forzado o reset
    por email). Usa fail_silently para no romper el flujo si el SMTP cae:
    la sesión ya está invalidada y la app debe seguir respondiendo.
    """
    reset_url = settings.SITE_URL.rstrip("/") + reverse("accounts:password_reset")
    body = render_to_string(
        "accounts/emails/password_changed.txt",
        {"user": user, "when": timezone.localtime(), "reset_url": reset_url},
    )
    send_mail(
        subject="Tu contraseña en La Porra del Jefe se ha cambiado",
        message=body,
        from_email=settings.PASSWORD_RESET_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
