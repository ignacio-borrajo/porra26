import hashlib
from datetime import timedelta

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from competition.api.auth import require_teams_api_token
from competition.models import BET_CLOSE_HOURS, BetsClosingReport, Match
from competition.services.closing_email import send_closure_email
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
    porque deja fuera los matches sin BetsClosingReport. Hacemos `select_related`
    del OneToOne y filtramos en Python para cubrir ambos casos en una sola consulta.
    """
    now = timezone.now()
    qs = (
        Match.objects.filter(kickoff__lte=now + timedelta(hours=BET_CLOSE_HOURS))
        .select_related("home", "away", "round", "closing_report")
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
    now = timezone.now()
    if not match.has_result and match.kickoff - timedelta(hours=BET_CLOSE_HOURS) > now:
        # todavía abierto y sin resultado → no hay nada que retratar
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


@require_teams_api_token
@require_POST
def cierre_enviar(request, match_id: int):
    """Envía (o reenvía) el PDF de cierre del match por email.

    Disparo on-demand desde el panel del gestor — sustituye al cron service.
    Como la intención del gestor al pulsar "Reenviar" es siempre forzar un
    envío fresco, limpiamos `sent_at` antes de invocar al service (que es
    idempotente: si encuentra sent_at fijado no enviaría nada).

    Si la request es de navegador (Accept text/html), redirige a la pantalla
    de resultados con un mensaje flash. Si es de API (Bearer token), devuelve
    JSON. Detectamos por `Accept`.
    """
    match = get_object_or_404(Match, pk=match_id)
    BetsClosingReport.objects.filter(match=match).update(sent_at=None)
    wants_html = "text/html" in request.META.get("HTTP_ACCEPT", "")
    try:
        report = send_closure_email(match)
    except ValueError as exc:
        if wants_html:
            messages.error(request, f"No se pudo enviar: {exc}")
            return redirect(reverse("competicion:manage_results"))
        return JsonResponse({"detail": str(exc)}, status=404)

    if wants_html:
        messages.success(
            request, f"PDF enviado a Teams para {match.home.name} vs {match.away.name}"
        )
        return redirect(reverse("competicion:manage_results"))
    return JsonResponse(
        {
            "match_id": match.id,
            "sent_at": report.sent_at.isoformat() if report.sent_at else None,
        }
    )
