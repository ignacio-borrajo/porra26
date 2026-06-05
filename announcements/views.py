from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from accounts.mixins import GestorRequiredMixin
from pot.services.prizes import announcement_podium

from .models import WinnerAnnouncement, WinnerAnnouncementSeen
from .preview import build_preview, build_preview_podium


def _podium_visual_order(podium):
    """Devuelve los slots en orden visual 2º · 1º · 3º.

    Cada elemento es (rank, entry_or_none). Un rank sin entrada significa
    que esa plaza no tiene a nadie con puntos (placeholder).
    """
    by_position = {e.position: e for e in podium}
    return [(rank, by_position.get(rank)) for rank in (2, 1, 3)]


class AnnouncementModalView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ann = get_object_or_404(
            WinnerAnnouncement.objects.prefetch_related("winners").select_related("scope_round"),
            pk=pk,
        )
        if ann.scope_kind == "sede":
            from pot.services.prizes import sede_winners

            return render(
                request,
                "announcements/_winner_modal.html",
                {"announcement": ann, "sede_winners": sede_winners()},
            )
        podium = announcement_podium(ann)
        return render(
            request,
            "announcements/_winner_modal.html",
            {
                "announcement": ann,
                "podium": podium,
                "podium_visual": _podium_visual_order(podium),
            },
        )


class AnnouncementSeenView(LoginRequiredMixin, View):
    def post(self, request, pk):
        ann = get_object_or_404(WinnerAnnouncement, pk=pk)
        WinnerAnnouncementSeen.objects.get_or_create(announcement=ann, user=request.user)

        next_ann = (
            WinnerAnnouncement.objects.exclude(seen_by__user=request.user)
            .exclude(pk=ann.pk)
            .order_by("created_at")
            .first()
        )
        resp = HttpResponse(status=204)
        if next_ann is not None:
            resp["X-Modal-Next"] = reverse("announcements:modal", args=[next_ann.id])
        return resp


class AnnouncementPreviewView(GestorRequiredMixin, View):
    def get(self, request):
        scope = request.GET.get("scope", "matchday")
        if scope == "sede":
            from .preview import build_preview_sede

            ann, sede_winners_preview = build_preview_sede(current_user=request.user)
            return render(
                request,
                "announcements/_winner_modal.html",
                {
                    "announcement": ann,
                    "preview": True,
                    "sede_winners": sede_winners_preview,
                },
            )
        tied = request.GET.get("tied") == "1"
        ann, winners = build_preview(scope, tied=tied, current_user=request.user)
        podium = build_preview_podium(scope, tied=tied, current_user=request.user)
        return render(
            request,
            "announcements/_winner_modal.html",
            {
                "announcement": ann,
                "preview": True,
                "preview_winners": winners,
                "podium": podium,
                "podium_visual": _podium_visual_order(podium),
            },
        )
