from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import GestorRequiredMixin
from accounts.models import User
from competition.models import Match, Prediction, Round
from competition.services.resolve import resolve_match
from competition.services.standings import standings


class CompetitionView(LoginRequiredMixin, View):
    def get(self, request):
        from competition.services.matchday_gate import (
            is_matchday_open,
            previous_matchday_close_info,
        )

        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")

        matchdays = sorted(
            Match.objects.filter(round_id=active_id, matchday__isnull=False)
            .values_list("matchday", flat=True)
            .distinct()
        )
        active_md = None
        if matchdays:
            requested = request.GET.get("matchday")
            if requested and requested.isdigit() and int(requested) in matchdays:
                active_md = int(requested)
            else:
                active_md = _default_matchday(active_id, matchdays)

        match_qs = Match.objects.filter(round_id=active_id).select_related(
            "home", "away", "round"
        )
        if active_md is not None:
            match_qs = match_qs.filter(matchday=active_md)
        matches = list(match_qs.order_by("kickoff"))

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

        matchday_state = []
        locked = False
        locked_last_match = None
        locked_last_kickoff = None
        if active_md is not None:
            for md in matchdays:
                matchday_state.append(
                    {
                        "matchday": md,
                        "open": is_matchday_open(active_id, md),
                        "active": md == active_md,
                    }
                )
            locked = not is_matchday_open(active_id, active_md)
            if locked:
                locked_last_match, locked_last_kickoff = previous_matchday_close_info(
                    active_id, active_md
                )

        return render(
            request,
            "competition/dashboard.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "matchdays": matchdays,
                "active_matchday": active_md,
                "matchday_state": matchday_state,
                "locked": locked,
                "locked_last_match": locked_last_match,
                "locked_last_kickoff": locked_last_kickoff,
                "open_matches": open_matches,
                "live_matches": live_matches,
                "done_matches": done_matches,
                "standings": standings()[:50],
            },
        )


def _default_matchday(round_id: str, matchdays: list[int]) -> int:
    """Jornada por defecto: la primera con algún partido sin resolver; si no, la última."""
    if not matchdays:
        return 1
    for md in matchdays:
        any_active = (
            Match.objects.filter(round_id=round_id, matchday=md)
            .filter(result_home__isnull=True)
            .exists()
        )
        if any_active:
            return md
    return matchdays[-1]


class PredictView(LoginRequiredMixin, View):
    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not request.user.is_jugador:
            raise PermissionDenied("Solo los jugadores pueden pronosticar.")
        if not m.editable:
            messages.error(request, "Las apuestas para este partido están cerradas.")
            return redirect("competicion:dashboard")
        from competition.services.matchday_gate import is_matchday_open

        if not is_matchday_open(m.round_id, m.matchday):
            messages.error(
                request,
                f"La J{m.matchday} se desbloqueará cuando termine la J{m.matchday - 1}.",
            )
            return redirect("competicion:dashboard")
        pred = Prediction.objects.filter(player=request.user, match=m).first()
        return render(request, "competition/_predict_modal.html", {"match": m, "pred": pred})

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not request.user.is_jugador:
            raise PermissionDenied("Solo los jugadores pueden pronosticar.")
        if not m.predictions_open:
            raise PermissionDenied("Apuestas cerradas o jornada bloqueada.")
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


class MatchDetailView(LoginRequiredMixin, View):
    """Modal con todas las apuestas de un partido cuyo plazo ya está cerrado."""

    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if m.editable:
            return redirect("competicion:dashboard")

        preds = list(
            Prediction.objects.filter(match=m).select_related("player").order_by("player__name")
        )
        round_points = m.round.points
        has_result = m.has_result

        rows = []
        for p in preds:
            earned = p.earned or 0
            rows.append(
                {
                    "name": p.player.name,
                    "is_me": p.player_id == request.user.id,
                    "home": p.home,
                    "away": p.away,
                    "earned": earned,
                    "exact": has_result and earned >= round_points,
                    "hit": has_result and earned > 0,
                    "no_pred": False,
                }
            )

        bettor_ids = {p.player_id for p in preds}
        absent = (
            User.objects.filter(is_active=True, is_jugador=True)
            .exclude(id__in=bettor_ids)
            .order_by("name")
        )
        for u in absent:
            rows.append(
                {
                    "name": u.name,
                    "is_me": u.id == request.user.id,
                    "home": None,
                    "away": None,
                    "earned": 0,
                    "exact": False,
                    "hit": False,
                    "no_pred": True,
                }
            )

        if has_result:
            rows.sort(
                key=lambda r: (
                    r["no_pred"],
                    -r["earned"],
                    r["name"].lower(),
                )
            )

        return render(
            request,
            "competition/_detail_modal.html",
            {
                "match": m,
                "rows": rows,
                "has_result": has_result,
                "round_points": round_points,
            },
        )
