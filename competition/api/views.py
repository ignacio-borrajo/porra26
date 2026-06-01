import hashlib
from datetime import timedelta

from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils import timezone as _tz

from competition.api.auth import require_teams_api_token
from competition.models import BET_CLOSE_HOURS, BetsClosingReport, Match
from competition.services.closing_report import build_closing_pdf


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


@require_teams_api_token
def cierre_pdf(request, match_id: int):
    match = get_object_or_404(
        Match.objects.select_related("home", "away", "round"),
        pk=match_id,
    )
    now = _tz.now()
    if match.kickoff - timedelta(hours=BET_CLOSE_HOURS) > now:
        # todavía abierto → no hay PDF de cierre
        return JsonResponse({"detail": "Partido todavía no cerrado"}, status=404)

    pdf_bytes = build_closing_pdf(match)
    sha = hashlib.sha256(pdf_bytes).hexdigest()
    with transaction.atomic():
        report, _ = BetsClosingReport.objects.select_for_update().get_or_create(match=match)
        report.attempts += 1
        report.generated_at = now
        report.last_sha256 = sha
        report.save(update_fields=["attempts", "generated_at", "last_sha256"])

    resp = HttpResponse(pdf_bytes, content_type="application/pdf")
    filename = f"cierre-{match.teams_slug}.pdf"
    resp["Content-Disposition"] = f'attachment; filename="{filename}"'
    return resp
