from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from accounts.models import User
from competition.services.standings import standings
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
        users = User.objects.in_bulk(list(h.keys()))
        players = {
            pid: {
                "name": u.name,
                "initials": u.initials,
                "hue": (ord(str(pid)[-1]) * 47) % 360,
                "avatar_url": u.avatar.url if u.avatar else None,
            }
            for pid, u in users.items()
        }
        return JsonResponse({"history": h, "me": request.user.id, "players": players})


class RankingsView(LoginRequiredMixin, View):
    VALID_TABS = ("general", "sede", "puesto", "dept")
    TAB_LABELS = {
        "general": "General",
        "sede": "Sede",
        "puesto": "Puesto",
        "dept": "Departamento",
    }

    def get(self, request):
        tab = request.GET.get("tab", "general")
        if tab not in self.VALID_TABS:
            tab = "general"
        ctx = {
            "tab": tab,
            "tabs": [(k, self.TAB_LABELS[k]) for k in self.VALID_TABS],
        }
        if tab == "general":
            rows = standings()[:50]
            users_by_id = User.objects.in_bulk([r.player_id for r in rows])
            my_rank = next((r.position for r in rows if r.player_id == request.user.id), None)
            max_pts = max((r.pts for r in rows), default=0) or 1
            ctx.update(
                {
                    "standings": rows,
                    "standings_users": users_by_id,
                    "my_rank": my_rank,
                    "max_pts": max_pts,
                }
            )
        else:
            rows = group_standings(tab)
            my_group = getattr(request.user, tab, "") or "__none__"
            top_ids = [r.top_user_id for r in rows if r.top_user_id]
            top_users = User.objects.in_bulk(top_ids) if top_ids else {}
            ctx.update(
                {
                    "rows": rows,
                    "my_group": my_group,
                    "top_users": top_users,
                }
            )
        return render(request, "stats/rankings.html", ctx)
