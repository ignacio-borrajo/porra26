from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from stats.services.history import per_player_history
from stats.services.kpis import donut, kpis


class StatsView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "stats/stats.html", {
            "kpis": kpis(request.user),
            "donut": donut(request.user.id),
        })


class ChartDataView(LoginRequiredMixin, View):
    def get(self, request):
        h = per_player_history()
        return JsonResponse({"history": h, "me": request.user.id})
