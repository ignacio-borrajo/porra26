"""Endpoints admin del módulo accounts.

Reutilizan el decorador ``require_teams_api_token`` de ``competition.api.auth``
para aceptar tanto bearer token (cron externo) como sesión de gestor logueado.
"""

import logging
from io import StringIO

from django.core.management import call_command
from django.http import JsonResponse
from django.views.decorators.http import require_POST

from competition.api.auth import require_teams_api_token

logger = logging.getLogger(__name__)


@require_POST
@require_teams_api_token
def prune_sessions(request):
    """Dispara ``prune_user_sessions``.

    Llamado por GitHub Actions diariamente. También lo puede ejecutar un
    gestor logueado para forzar la limpieza puntualmente.
    """
    buf = StringIO()
    call_command("prune_user_sessions", stdout=buf)
    summary = buf.getvalue().strip()
    logger.info("prune_sessions endpoint: %s", summary)
    return JsonResponse({"ok": True, "summary": summary})
