from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import GestorRequiredMixin
from competition.models import Match, Prediction, Round
from competition.services.resolve import resolve_match
from competition.services.standings import standings


class CompetitionView(LoginRequiredMixin, View):
    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")
        matches = list(
            Match.objects.filter(round_id=active_id)
            .select_related("home", "away", "round")
            .order_by("kickoff")
        )
        my_preds = {
            p.match_id: p for p in Prediction.objects.filter(player=request.user, match__in=matches)
        }
        open_matches, live_matches, done_matches = [], [], []
        for m in matches:
            m.my_pred = my_preds.get(m.id)
            st = m.status
            if st == "live":
                live_matches.append(m)
            elif st == "done":
                done_matches.append(m)
            else:
                open_matches.append(m)
        return render(
            request,
            "competition/dashboard.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "open_matches": open_matches,
                "live_matches": live_matches,
                "done_matches": done_matches,
                "standings": standings()[:50],
            },
        )


class PredictView(LoginRequiredMixin, View):
    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not m.editable:
            messages.error(request, "Las apuestas para este partido están cerradas.")
            return redirect("competicion:dashboard")
        pred = Prediction.objects.filter(player=request.user, match=m).first()
        return render(request, "competition/_predict_modal.html", {"match": m, "pred": pred})

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not m.editable:
            raise PermissionDenied("Apuestas cerradas")
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:dashboard")
        Prediction.objects.update_or_create(
            player=request.user, match=m, defaults={"home": h, "away": a}
        )
        messages.success(request, f"Pronóstico guardado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect("competicion:dashboard")


class ManageResultsView(GestorRequiredMixin, View):
    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")
        ms = list(
            Match.objects.filter(round_id=active_id)
            .select_related("home", "away", "round")
            .order_by("kickoff")
        )
        pending, upcoming, done = [], [], []
        for m in ms:
            st = m.status
            if st == "done":
                done.append(m)
            elif st in ("live", "closed"):
                pending.append(m)
            else:
                upcoming.append(m)
        return render(
            request,
            "competition/manage_results.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "pending": pending,
                "upcoming": upcoming,
                "done": done,
            },
        )


class ResultOfficialView(GestorRequiredMixin, View):
    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        return render(request, "competition/_official_modal.html", {"match": m})

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:manage_results")
        resolve_match(m, home=h, away=a, actor=request.user)
        messages.success(request, f"Resultado confirmado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect("competicion:manage_results")
