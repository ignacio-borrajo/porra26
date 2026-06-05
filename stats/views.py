from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View

from accounts.models import User
from stats.services.group_standings import CHOICES_BY_DIMENSION, group_standings
from stats.services.history import per_player_history
from stats.services.history_matrix import build_matrix
from stats.services.history_xlsx import render_xlsx
from stats.services.kpis import donut, kpis
from stats.services.rankings_context import build_general_context


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
            ctx.update(build_general_context(request.user, request.GET.get("scope")))
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


class HistoryView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "stats/historico.html", {"matrix": build_matrix()})


class HistoryExportView(LoginRequiredMixin, View):
    def get(self, request):
        content = render_xlsx(build_matrix())
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="historico-porra-26.xlsx"'
        return response


class GroupRankingsView(LoginRequiredMixin, View):
    VALID_DIMS = ("sede", "puesto", "dept")

    def get(self, request, dim: str, key: str):
        if dim not in self.VALID_DIMS:
            raise Http404("Dimensión desconocida")
        labels = dict(CHOICES_BY_DIMENSION[dim])
        if key not in labels:
            raise Http404("Grupo desconocido")
        player_ids = list(
            User.objects.filter(is_active=True, is_jugador=True, **{dim: key}).values_list(
                "id", flat=True
            )
        )
        ctx = build_general_context(request.user, request.GET.get("scope"), player_ids=player_ids)
        ctx.update(
            {
                "dim": dim,
                "dim_label": RankingsView.TAB_LABELS[dim],
                "group_label": labels[key],
                "group_key": key,
                "player_count": len(player_ids),
            }
        )
        return render(request, "stats/rankings_group.html", ctx)
