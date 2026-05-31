from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from stats.services.group_standings import group_standings
from stats.services.history import per_player_history
from stats.services.kpis import donut, kpis


class StatsView(LoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "stats/stats.html",
            {
                "kpis": kpis(request.user),
                "donut": donut(request.user.id),
            },
        )


class ChartDataView(LoginRequiredMixin, View):
    def get(self, request):
        h = per_player_history()
        return JsonResponse({"history": h, "me": request.user.id})


class RankingsView(LoginRequiredMixin, View):
    VALID_TABS = ("sede", "puesto", "dept")
    TAB_LABELS = {"sede": "Sede", "puesto": "Puesto", "dept": "Departamento"}

    def get(self, request):
        tab = request.GET.get("tab", "sede")
        if tab not in self.VALID_TABS:
            tab = "sede"
        rows = group_standings(tab)
        my_group = getattr(request.user, tab, "") or "__none__"
        return render(request, "stats/rankings.html", {
            "tab": tab,
            "rows": rows,
            "tabs": [(k, self.TAB_LABELS[k]) for k in self.VALID_TABS],
            "my_group": my_group,
        })
