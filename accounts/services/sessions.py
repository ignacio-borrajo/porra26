from collections.abc import Iterable

from django.contrib.sessions.models import Session
from django.db import transaction
from user_agents import parse as parse_user_agent

from accounts.models import AuditLog, UserSession

UNKNOWN_DEVICE_LABEL = "Dispositivo desconocido"


def parse_device_label(user_agent_raw: str) -> str:
    """Devuelve una etiqueta legible del dispositivo, máx. 80 chars.

    Ejemplos:
        'iPhone — Safari'
        'Chrome en macOS'
        'Edge en Windows'
    """
    if not user_agent_raw:
        return UNKNOWN_DEVICE_LABEL
    try:
        ua = parse_user_agent(user_agent_raw[:1000])
    except Exception:
        return UNKNOWN_DEVICE_LABEL

    browser = ua.browser.family or ""
    os_family = ua.os.family or ""
    device = ua.device.family or ""

    if ua.is_mobile or ua.is_tablet:
        if device and device != "Other":
            label = f"{device} — {browser}".strip(" —")
        else:
            label = f"{os_family} — {browser}".strip(" —")
    else:
        label = f"{browser} en {os_family}".strip()
        if label.endswith(" en"):
            label = label[:-3].rstrip()

    label = label or UNKNOWN_DEVICE_LABEL
    return label[:80]


@transaction.atomic
def revoke_sessions(
    *,
    user,
    session_keys: Iterable[str],
    actor=None,
    reason: str = "manual",
) -> int:
    """Revoca sesiones del usuario indicado.

    Borra primero la Session real (la cookie deja de valer) y luego la
    UserSession asociada. Registra una sola entrada de AuditLog con el
    count y la razón. Devuelve nº de UserSession borradas.
    """
    keys = list(session_keys)
    if not keys:
        return 0
    Session.objects.filter(session_key__in=keys).delete()
    deleted, _ = UserSession.objects.filter(user=user, session_key__in=keys).delete()
    AuditLog.objects.create(
        actor=actor,
        action="sessions.revoked",
        target_type="user",
        target_id=str(user.id),
        payload={"count": deleted, "reason": reason},
    )
    return deleted
