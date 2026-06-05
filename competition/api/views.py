import hashlib
import logging

from django.contrib import messages
from django.db import transaction
from django.http import HttpResponse, JsonResponse
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.utils import timezone
from django.views.decorators.http import require_POST

from competition.api.auth import require_teams_api_token
from competition.models import BetsClosingReport, BetsReminderLog, Match
from competition.services.closing_email import send_closure_email
from competition.services.closing_report import build_closing_pdf
from competition.services.reminder_email import send_reminder_email
from competition.services.reminders import matches_due_for_kind

logger = logging.getLogger(__name__)


def _match_payload(m: Match) -> dict:
    return {
        "id": m.id,
        "slug": m.teams_slug,
        "round": m.round.label,
        "round_id": m.round_id,
        "group": m.group,
        "home": {"code": m.home_id, "name": m.home.name},
        "away": {"code": m.away_id, "name": m.away.name},
        "kickoff": m.kickoff.isoformat(),
        "closed_at": m.kickoff.isoformat(),
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
        Match.objects.filter(kickoff__lte=now)
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
    if not match.has_result and match.kickoff > now:
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


@require_teams_api_token
@require_POST
def recordatorios_disparar(request):
    """Procesa las dos ventanas de aviso y dispara los pendientes.

    Endpoint pensado para ser llamado por GitHub Actions cada 15 min. También
    lo puede ejecutar un gestor logueado para forzar la verificación.
    """
    summary: dict[str, dict[str, int]] = {}
    for kind in BetsReminderLog.AUTO_KINDS:
        checked = sent = skipped_empty = errors = 0
        for match in matches_due_for_kind(kind):
            checked += 1
            try:
                result = send_reminder_email(match, kind)
            except Exception as exc:  # noqa: BLE001
                errors += 1
                logger.exception(
                    "recordatorios_disparar: error en match=%s kind=%s: %s",
                    match.id,
                    kind,
                    exc,
                )
                continue
            if result is None:
                skipped_empty += 1
            else:
                sent += 1
        summary[kind] = {
            "checked": checked,
            "sent": sent,
            "skipped_empty": skipped_empty,
            "errors": errors,
        }
    return JsonResponse(summary)


@require_teams_api_token
@require_POST
def recordatorio_enviar(request, match_id: int):
    """Envía manualmente el recordatorio (kind=MANUAL) para un match.

    Disparado desde el botón del gestor en /competicion/resultados/.
    - 200 con ``sent=true`` si se envió.
    - 200 con ``sent=false`` y ``reason="no_pending"`` si no quedaban rezagados.
    - 409 si las apuestas ya están cerradas.
    - Si el cliente espera HTML (form submit del botón), redirige a
      ``manage_results`` con un ``messages`` flash. Si es API/Bearer, JSON.
    """
    match = get_object_or_404(Match, pk=match_id)
    wants_html = "text/html" in request.META.get("HTTP_ACCEPT", "")
    try:
        log = send_reminder_email(match, BetsReminderLog.KIND_MANUAL)
    except ValueError as exc:
        if wants_html:
            messages.error(request, f"No se pudo enviar: {exc}")
            return redirect(reverse("competicion:manage_results"))
        return JsonResponse({"detail": str(exc)}, status=409)

    if log is None:
        if wants_html:
            messages.info(
                request,
                f"Sin rezagados para {match.home.name} vs {match.away.name}: "
                "ya han apostado todos.",
            )
            return redirect(reverse("competicion:manage_results"))
        return JsonResponse({"sent": False, "reason": "no_pending"})

    if wants_html:
        messages.success(
            request,
            f"Recordatorio enviado · {match.home.name} vs {match.away.name} "
            f"({log.pending_count} rezagados)",
        )
        return redirect(reverse("competicion:manage_results"))
    return JsonResponse(
        {
            "sent": True,
            "pending_count": log.pending_count,
            "sent_at": log.sent_at.isoformat(),
        }
    )
