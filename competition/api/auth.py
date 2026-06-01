import logging
import secrets
from functools import wraps

from django.conf import settings
from django.http import JsonResponse
from django.views.decorators.csrf import csrf_exempt

logger = logging.getLogger(__name__)


def _bearer_token_ok(request) -> bool:
    expected = getattr(settings, "TEAMS_API_TOKEN", "") or ""
    if not expected:
        return False
    header = request.META.get("HTTP_AUTHORIZATION", "")
    if not header.startswith("Bearer "):
        return False
    received = header[len("Bearer ") :].strip()
    return secrets.compare_digest(received, expected)


def _gestor_session_ok(request) -> bool:
    user = getattr(request, "user", None)
    return bool(
        user and getattr(user, "is_authenticated", False) and getattr(user, "is_gestor", False)
    )


def require_teams_api_token(view):
    @csrf_exempt
    @wraps(view)
    def wrapper(request, *args, **kwargs):
        if _bearer_token_ok(request) or _gestor_session_ok(request):
            return view(request, *args, **kwargs)
        logger.warning(
            "teams-api: unauthorized request path=%s ip=%s ua=%s",
            request.path,
            request.META.get("REMOTE_ADDR"),
            request.META.get("HTTP_USER_AGENT", "")[:120],
        )
        return JsonResponse(
            {"detail": "Token inválido o sesión no autorizada"},
            status=401,
        )

    return wrapper
