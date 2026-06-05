from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from accounts.mixins import GestorRequiredMixin
from pot.services.prizes import announcement_podium

from .models import WinnerAnnouncement, WinnerAnnouncementSeen
from .preview import build_preview, build_preview_podium


class AnnouncementModalView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ann = get_object_or_404(
            WinnerAnnouncement.objects.prefetch_related("winners").select_related("scope_round"),
            pk=pk,
        )
        return render(
            request,
            "announcements/_winner_modal.html",
            {"announcement": ann, "podium": announcement_podium(ann)},
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
            },
        )
