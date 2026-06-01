from datetime import timedelta

from django.http import JsonResponse
from django.utils import timezone

from competition.api.auth import require_teams_api_token
from competition.models import BET_CLOSE_HOURS, Match


def _match_payload(m: Match) -> dict:
    closed_at = m.kickoff - timedelta(hours=BET_CLOSE_HOURS)
    return {
        "id": m.id,
        "slug": m.teams_slug,
        "round": m.round.label,
        "round_id": m.round_id,
        "group": m.group,
        "home": {"code": m.home_id, "name": m.home.name},
        "away": {"code": m.away_id, "name": m.away.name},
        "kickoff": m.kickoff.isoformat(),
        "closed_at": closed_at.isoformat(),
    }


@require_teams_api_token
def cierres_pendientes(request):
    """Devuelve los matches cuyo cierre ya pasó y que aún no se han enviado a Teams.

    El filtro `closing_report__sent_at__isnull=True` no nos vale por sí solo
    porque deja fuera los matches sin BetsClosingReport. Filtramos en Python
    para cubrir ambos casos en una única consulta con prefetch del OneToOne.
    """
    now = timezone.now()
    qs = (
        Match.objects
        .filter(kickoff__lte=now + timedelta(hours=BET_CLOSE_HOURS))
        .select_related("home", "away", "round")
        .order_by("kickoff")
    )
    pendientes = []
    for m in qs:
        report = getattr(m, "closing_report", None)
        if report is None or report.sent_at is None:
            pendientes.append(m)
    return JsonResponse({"matches": [_match_payload(m) for m in pendientes]})
