from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, render
from django.urls import reverse
from django.views import View

from .models import WinnerAnnouncement, WinnerAnnouncementSeen


class AnnouncementModalView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ann = get_object_or_404(
            WinnerAnnouncement.objects.prefetch_related("winners").select_related("scope_round"),
            pk=pk,
        )
        return render(
            request,
            "announcements/_winner_modal.html",
            {"announcement": ann},
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
