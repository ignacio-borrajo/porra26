from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views import View

from accounts.mixins import GestorRequiredMixin
from accounts.models import AuditLog

from .models import Raffle
from .services import public_state, start_raffle


def _state(request):
    state = public_state()
    state["isGestor"] = request.user.is_gestor
    state["stateUrl"] = reverse("raffle:state")
    state["startUrl"] = reverse("raffle:start")
    return state


class DrawView(GestorRequiredMixin, View):
    def get(self, request):
        return render(request, "raffle/draw.html", {"state": _state(request)})


class StateView(GestorRequiredMixin, View):
    def get(self, request):
        return JsonResponse(public_state())


class StartView(GestorRequiredMixin, View):
    def post(self, request):
        try:
            raffle = start_raffle()
        except ValueError as exc:
            return JsonResponse({"error": str(exc)}, status=400)
        AuditLog.objects.create(
            actor=request.user,
            action="raffle_start",
            target_type="raffle",
            target_id=str(raffle.pk),
            payload={"participants": raffle.entries.count()},
        )
        return JsonResponse(public_state())


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
