from django.contrib import messages
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from accounts.mixins import GestorRequiredMixin
from accounts.models import AuditLog

from .models import Raffle
from .services import eligible_players, get_or_create_raffle, spin


def _state(request):
    """Estado del sorteo para el JS: participantes (snapshot o elegibles) y urls."""
    raffle = Raffle.objects.first()
    if raffle is not None:
        participants = [
            {"id": e.player_id, "name": e.player.name, "eliminatedOrder": e.eliminated_order}
            for e in raffle.entries.select_related("player")
        ]
    else:
        participants = [
            {"id": p.id, "name": p.name, "eliminatedOrder": None}
            for p in eligible_players().order_by("name")
        ]
    return {
        "participants": participants,
        "isGestor": request.user.is_gestor,
        "spinUrl": reverse("raffle:spin"),
    }


class DrawView(GestorRequiredMixin, View):
    def get(self, request):
        return render(request, "raffle/draw.html", {"state": _state(request)})


class SpinView(GestorRequiredMixin, View):
    def post(self, request):
        raffle = get_or_create_raffle()
        try:
            eliminated, remaining, winner = spin(raffle)
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        AuditLog.objects.create(
            actor=request.user,
            action="raffle_spin",
            target_type="raffle",
            target_id=str(raffle.pk),
            payload={
                "eliminated": [e.player_id for e in eliminated],
                "remaining": remaining,
                "winner": winner.player_id if winner else None,
            },
        )
        return JsonResponse(
            {
                "eliminated": [e.player_id for e in eliminated],
                "remaining": remaining,
                "winner": winner.player_id if winner else None,
            }
        )


class ResetView(GestorRequiredMixin, View):
    def post(self, request):
        deleted, _ = Raffle.objects.all().delete()
        if deleted:
            AuditLog.objects.create(
                actor=request.user,
                action="raffle_reset",
                target_type="raffle",
                target_id="",
                payload={},
            )
            messages.success(request, "Sorteo reiniciado.")
        return redirect("raffle:draw")
