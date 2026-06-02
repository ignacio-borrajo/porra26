from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from accounts.models import User
from competition.services.standings import standings
from stats.services.group_standings import group_standings
from stats.services.history import per_player_history
from stats.services.kpis import donut, kpis
from stats.services.matchday_options import (
    current_option,
    matchday_options,
    parse_scope_key,
)


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
        "general": "Clasificación",
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
            my_rank = next((r.position for r in rows if r.player_id == request.user.id), None)
            max_pts = max((r.pts for r in rows), default=0) or 1

            md_opts = matchday_options()
            requested = parse_scope_key(request.GET.get("scope"), md_opts)
            current = current_option(md_opts)
            scope = requested or current
            for o in md_opts:
                o.is_active = scope is not None and o.key == scope.key

            scope_rows: list = []
            scope_my_rank = None
            scope_max_pts = 1
            scope_label = None
            if scope is not None:
                scope_rows = standings(
                    round_id=scope.round_id, matchday=scope.matchday
                )[:50]
                scope_my_rank = next(
                    (r.position for r in scope_rows if r.player_id == request.user.id),
                    None,
                )
                scope_max_pts = max((r.pts for r in scope_rows), default=0) or 1
                scope_label = scope.label

            all_ids = {r.player_id for r in rows} | {r.player_id for r in scope_rows}
            users_by_id = User.objects.in_bulk(all_ids)
            ctx.update(
                {
                    "standings": rows,
                    "standings_users": users_by_id,
                    "my_rank": my_rank,
                    "max_pts": max_pts,
                    "scope_standings": scope_rows,
                    "scope_my_rank": scope_my_rank,
                    "scope_max_pts": scope_max_pts,
                    "scope_label": scope_label,
                    "md_options": md_opts,
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
