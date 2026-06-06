"""Envío masivo del email de bienvenida con throttling.

Resend SMTP impone un límite ~2 req/s (free) / 10 req/s (paid). Inyectamos
un sleep entre envíos para mantenernos por debajo aunque haya 200 cuentas
pendientes. El envío corre en un hilo de fondo para no bloquear la request
del gestor.
"""

from __future__ import annotations

import logging
import time
from threading import Thread

from django.db import close_old_connections

from accounts.models import AuditLog, User
from accounts.services.password_reset import send_password_reset_email

logger = logging.getLogger(__name__)

DEFAULT_DELAY_SECONDS = 0.6


def pending_welcome_recipients():
    """Usuarios activos que aún no han activado su cuenta.

    Criterio de "pendiente": nunca se han logueado (last_login IS NULL) y
    siguen con must_change_password=True. Coincide con la chip "Pendiente
    de activar" de la pantalla de Jugadores.
    """
    return User.objects.filter(
        is_active=True,
        last_login__isnull=True,
        must_change_password=True,
    ).order_by("name")


def send_bulk_welcome(users, actor=None, delay_seconds: float = DEFAULT_DELAY_SECONDS):
    """Envía welcome a los usuarios indicados, uno por uno con sleep.

    Devuelve (sent, failed) donde failed es una lista de dicts con detalle
    del error para auditoría posterior.
    """
    sent = 0
    failed: list[dict] = []
    users = list(users)
    total = len(users)
    for idx, user in enumerate(users):
        try:
            send_password_reset_email(user, purpose="welcome", actor=actor)
            sent += 1
        except Exception as exc:
            logger.exception("bulk_welcome: fallo enviando a %s", user.email)
            failed.append({"user_id": user.id, "email": user.email, "error": str(exc)})
        if idx < total - 1 and delay_seconds > 0:
            time.sleep(delay_seconds)
    return sent, failed


def send_bulk_welcome_async(user_ids, actor=None, delay_seconds: float = DEFAULT_DELAY_SECONDS):
    """Dispara send_bulk_welcome en un Thread daemon.

    Toma snapshot de los IDs para que el queryset se materialice dentro del
    hilo con una conexión limpia (close_old_connections antes y después).
    Registra un AuditLog de inicio y otro de fin con el resumen.
    """
    user_ids = list(user_ids)
    actor_id = actor.id if actor else None

    AuditLog.objects.create(
        actor=actor,
        action="bulk_welcome_emails_started",
        target_type="users",
        target_id="*",
        payload={"count": len(user_ids), "delay_seconds": delay_seconds},
    )

    def _run():
        close_old_connections()
        try:
            actor_user = User.objects.filter(id=actor_id).first() if actor_id else None
            users_qs = User.objects.filter(id__in=user_ids).order_by("name")
            sent, failed = send_bulk_welcome(
                users_qs, actor=actor_user, delay_seconds=delay_seconds
            )
            AuditLog.objects.create(
                actor=actor_user,
                action="bulk_welcome_emails_finished",
                target_type="users",
                target_id="*",
                payload={
                    "requested": len(user_ids),
                    "sent": sent,
                    "failed_count": len(failed),
                    "failed": failed,
                },
            )
            logger.info("bulk_welcome: %s enviados, %s fallos", sent, len(failed))
        finally:
            close_old_connections()

    thread = Thread(target=_run, name="bulk-welcome", daemon=True)
    thread.start()
    return thread
