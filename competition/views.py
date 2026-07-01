from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import GestorRequiredMixin
from accounts.models import User
from competition.models import Match, Prediction, Round
from competition.services.live_standings import live_standings
from competition.services.resolve import clear_match_result, delete_match, resolve_match

KO_ROUND_IDS = ("r32", "r16", "qf", "sf", "final")
# Rondas que comparten un único ámbito de clasificación/premio ("Fases
# Finales"), igual que el sistema de premios (pot.services.prizes._FINALS_ROUND_IDS).
# R32 (Dieciseisavos) tiene su propio ámbito y queda fuera de este grupo.
FINALS_ROUND_IDS = ("r16", "qf", "sf", "final")


def _default_round(rounds: list[Round]) -> str:
    """Ronda activa por defecto cuando no se pide una explícita en `?round`.

    Devuelve la ronda del primer partido sin resolver (por orden de ronda y
    kickoff), es decir, la fase "en juego". Si está todo resuelto, la última
    ronda. Así, con la fase de grupos terminada y R32 en juego, el dashboard
    aterriza en R32 en lugar de la última jornada de grupos."""
    current = (
        Match.objects.filter(result_home__isnull=True)
        .order_by("round__order", "kickoff")
        .values_list("round_id", flat=True)
        .first()
    )
    if current:
        return current
    return rounds[-1].id if rounds else "groups"


def _order_ko_column(matches: list) -> list:
    """Ordena los partidos de una columna KO: primero los no finalizados
    (`has_result` False) y luego los finalizados, ambos por kickoff ascendente."""
    return sorted(matches, key=lambda m: (m.has_result, m.kickoff))


class CompetitionView(LoginRequiredMixin, View):
    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", _default_round(rounds))
        is_ko_view = active_id in KO_ROUND_IDS

        matchdays = sorted(
            Match.objects.filter(round_id=active_id, matchday__isnull=False)
            .order_by("matchday")
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
            "home", "away", "round", "live_score"
        )
        if active_md is not None:
            match_qs = match_qs.filter(matchday=active_md)
        matches = list(match_qs.order_by("kickoff"))

        my_preds = {
            p.match_id: p for p in Prediction.objects.filter(player=request.user, match__in=matches)
        }
        open_matches, live_matches, awaiting_matches, done_matches = [], [], [], []
        for m in matches:
            m.my_pred = my_preds.get(m.id)
            st = m.status
            if st == "live":
                if m.awaiting_validation:
                    awaiting_matches.append(m)
                else:
                    live_matches.append(m)
            elif st == "done":
                done_matches.append(m)
            else:
                open_matches.append(m)

        matchday_state = [
            {"matchday": md, "open": True, "active": md == active_md} for md in matchdays
        ]

        rows = live_standings()
        for r in rows:
            r.pts = r.live_pts
        has_points = bool(rows) and rows[0].pts > 0
        my_row = next((r for r in rows if r.player_id == request.user.id), None)
        my_rank = my_row.position if my_row and has_points else None
        my_is_tied = bool(my_row and my_row.is_tied and has_points)
        max_pts = max((r.pts for r in rows), default=0) or 1

        # Ámbito de la clasificación local. Las rondas de fases finales
        # (r16/qf/sf/final) se agrupan bajo un único ámbito "Fases Finales",
        # igual que el sistema de premios; R32 y cada jornada de grupos son
        # ámbitos propios.
        active_round_obj = next((r for r in rounds if r.id == active_id), None)
        if active_md is not None:
            scope_rows = live_standings(round_id=active_id, matchday=active_md)
            scope_label = f"Jornada {active_md}"
        elif active_id in FINALS_ROUND_IDS:
            scope_rows = live_standings(round_ids=FINALS_ROUND_IDS)
            scope_label = "Fases Finales"
        elif active_round_obj is not None:
            scope_rows = live_standings(round_id=active_id)
            scope_label = active_round_obj.label
        else:
            scope_rows = live_standings(round_id=active_id)
            scope_label = "Ronda"
        for r in scope_rows:
            r.pts = r.live_pts
        scope_has_points = bool(scope_rows) and scope_rows[0].pts > 0
        scope_my_row = next((r for r in scope_rows if r.player_id == request.user.id), None)
        scope_my_rank = scope_my_row.position if scope_my_row and scope_has_points else None
        scope_my_is_tied = bool(scope_my_row and scope_my_row.is_tied and scope_has_points)
        scope_max_pts = max((r.pts for r in scope_rows), default=0) or 1

        all_ids = {r.player_id for r in rows} | {r.player_id for r in scope_rows}
        users_by_id = User.objects.in_bulk(all_ids)

        ko_rounds: list[dict] = []
        if is_ko_view:
            ko_matches = list(
                Match.objects.filter(round_id__in=KO_ROUND_IDS).select_related(
                    "home", "away", "round"
                )
            )
            # Los partidos KO se consultan aparte de `matches`, así que hay que
            # adjuntarles también el pronóstico del jugador para que la card lo
            # muestre (la card lee `match.my_pred`).
            ko_my_preds = {
                p.match_id: p
                for p in Prediction.objects.filter(player=request.user, match__in=ko_matches)
            }
            for m in ko_matches:
                m.my_pred = ko_my_preds.get(m.id)
            rounds_by_id = {r.id: r for r in rounds}
            for rid in KO_ROUND_IDS:
                r_obj = rounds_by_id.get(rid)
                if r_obj is None:
                    continue
                rmatches = _order_ko_column([m for m in ko_matches if m.round_id == rid])
                ko_rounds.append({"round": r_obj, "matches": rmatches})

        from announcements.models import WinnerAnnouncement

        first_announcement_id = (
            WinnerAnnouncement.objects.exclude(seen_by__user=request.user)
            .order_by("created_at")
            .values_list("id", flat=True)
            .first()
        )

        show_team_profile_modal = bool(
            not (request.user.sede and request.user.dept and request.user.puesto)
            and not request.session.get("team_profile_dismissed")
        )

        return render(
            request,
            "competition/dashboard.html",
            {
                "first_announcement_id": first_announcement_id,
                "show_team_profile_modal": show_team_profile_modal,
                "rounds": rounds,
                "active_round": active_id,
                "matchdays": matchdays,
                "active_matchday": active_md,
                "matchday_state": matchday_state,
                "open_matches": open_matches,
                "live_matches": live_matches,
                "awaiting_matches": awaiting_matches,
                "done_matches": done_matches,
                "has_live_matches": bool(live_matches) or bool(awaiting_matches),
                "standings": rows,
                "standings_users": users_by_id,
                "my_rank": my_rank,
                "my_is_tied": my_is_tied,
                "max_pts": max_pts,
                "scope_standings": scope_rows,
                "scope_my_rank": scope_my_rank,
                "scope_my_is_tied": scope_my_is_tied,
                "scope_max_pts": scope_max_pts,
                "scope_label": scope_label,
                "is_ko_view": is_ko_view,
                "ko_rounds": ko_rounds,
                "active_ko_id": active_id if is_ko_view else None,
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
        if not m.has_teams:
            messages.error(request, "Este cruce aún no tiene los dos equipos definidos.")
            return redirect("competicion:dashboard")
        if not m.editable:
            messages.error(request, "Las apuestas para este partido están cerradas.")
            return redirect("competicion:dashboard")
        from competition.services.predictions import (
            next_pending_match,
            pending_matches_count,
        )

        pred = Prediction.objects.filter(player=request.user, match=m).first()
        pending_count = pending_matches_count(request.user)
        has_next = next_pending_match(request.user, after_match=m) is not None
        return render(
            request,
            "competition/_predict_modal.html",
            {
                "match": m,
                "pred": pred,
                "pending_count": pending_count,
                "has_next": has_next,
            },
        )

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not request.user.is_jugador:
            raise PermissionDenied("Solo los jugadores pueden pronosticar.")
        if not m.predictions_open:
            raise PermissionDenied("Apuestas cerradas.")
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:dashboard")
        Prediction.objects.update_or_create(
            player=request.user, match=m, defaults={"home": h, "away": a}
        )
        if request.POST.get("chain") == "1":
            from django.http import HttpResponse
            from django.urls import reverse

            from competition.services.predictions import next_pending_match

            nxt = next_pending_match(request.user, after_match=m)
            if nxt is not None:
                resp = HttpResponse(status=204)
                resp["X-Modal-Next"] = reverse("competicion:predict", args=[nxt.id])
                return resp
            messages.success(request, "¡Has apostado todos los partidos disponibles!")
            resp = HttpResponse(status=200)
            resp["X-Modal-Redirect"] = reverse("competicion:dashboard")
            return resp
        messages.success(request, f"Pronóstico guardado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect("competicion:dashboard")


class ManageResultsView(GestorRequiredMixin, View):
    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")
        matchdays = sorted(
            Match.objects.filter(round_id=active_id, matchday__isnull=False)
            .order_by("matchday")
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
            "home", "away", "round", "closing_report"
        )
        if active_md is not None:
            match_qs = match_qs.filter(matchday=active_md)
        ms = list(match_qs.order_by("kickoff"))

        matchday_state = [
            {"matchday": md, "open": True, "active": md == active_md} for md in matchdays
        ]

        pending, upcoming, done, pending_teams_matches = [], [], [], []
        for m in ms:
            st = m.status
            if st == "done":
                done.append(m)
            elif st == "live":
                pending.append(m)
            elif st == "pending_teams":
                pending_teams_matches.append(m)
            else:
                upcoming.append(m)

        from competition.models import Team

        all_teams = list(Team.objects.order_by("name"))

        from django.db.models import Count

        from accounts.models import User
        from competition.models import BetsClosingReport, BetsReminderLog, Prediction

        reports = list(
            BetsClosingReport.objects.select_related(
                "match__home", "match__away", "match__round"
            ).order_by("-match__kickoff")
        )

        # Pill "N sin apostar" y tooltip del último recordatorio — solo para
        # upcoming (los únicos donde el cierre todavía no pasó).
        upcoming_ids = [m.id for m in upcoming]
        pending_counts: dict[int, int] = {}
        last_reminders: dict[int, BetsReminderLog] = {}
        if upcoming_ids:
            expected_total = User.objects.filter(is_active=True, is_jugador=True).count()
            bets_per_match = dict(
                Prediction.objects.filter(
                    match_id__in=upcoming_ids,
                    player__is_active=True,
                    player__is_jugador=True,
                )
                .values_list("match_id")
                .annotate(c=Count("id"))
                .values_list("match_id", "c")
            )
            pending_counts = {
                mid: max(0, expected_total - bets_per_match.get(mid, 0)) for mid in upcoming_ids
            }
            for log in BetsReminderLog.objects.filter(match_id__in=upcoming_ids).order_by(
                "match_id", "-sent_at"
            ):
                if log.match_id not in last_reminders:
                    last_reminders[log.match_id] = log

        return render(
            request,
            "competition/manage_results.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "matchdays": matchdays,
                "active_matchday": active_md,
                "matchday_state": matchday_state,
                "pending": pending,
                "upcoming": upcoming,
                "done": done,
                "pending_teams_matches": pending_teams_matches,
                "all_teams": all_teams,
                "reports": reports,
                "pending_counts": pending_counts,
                "last_reminders": last_reminders,
            },
        )


class ResultOfficialView(GestorRequiredMixin, View):
    def get(self, request, match_id):
        m = get_object_or_404(
            Match.objects.select_related("home", "away", "round", "live_score"),
            pk=match_id,
        )
        from competition.services.predictions import (
            next_pending_result_match,
            pending_result_matches_count,
        )

        pending_count = pending_result_matches_count()
        has_next = next_pending_result_match(after_match=m) is not None

        # Pre-rellenar inputs: oficial > live_score > 0. Si football-data ya
        # marcó FT, el gestor abre el modal y solo tiene que pulsar Confirmar.
        if m.has_result:
            default_home = m.result_home
            default_away = m.result_away
        elif getattr(m, "live_score", None):
            default_home = m.live_score.home_score
            default_away = m.live_score.away_score
        else:
            default_home = 0
            default_away = 0

        return render(
            request,
            "competition/_official_modal.html",
            {
                "match": m,
                "pending_count": pending_count,
                "has_next": has_next,
                "default_home": default_home,
                "default_away": default_away,
            },
        )

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if request.POST.get("action") == "delete":
            if not m.has_result:
                messages.error(request, "Este partido aún no tiene resultado que borrar.")
                return redirect("competicion:manage_results")
            clear_match_result(m, actor=request.user)
            messages.success(
                request,
                f"Resultado borrado · {m.home.name} vs {m.away.name}",
            )
            return redirect("competicion:manage_results")
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:manage_results")
        resolve_match(m, home=h, away=a, actor=request.user)
        messages.success(request, f"Resultado confirmado · {m.home.name} {h}–{a} {m.away.name}")
        if request.POST.get("chain") == "1":
            from django.http import HttpResponse
            from django.urls import reverse

            from competition.services.predictions import next_pending_result_match

            nxt = next_pending_result_match(after_match=m)
            if nxt is not None:
                resp = HttpResponse(status=204)
                resp["X-Modal-Next"] = reverse("competicion:official", args=[nxt.id])
                return resp
            resp = HttpResponse(status=200)
            resp["X-Modal-Redirect"] = reverse("competicion:manage_results")
            return resp
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
        round_points = m.exact_points_applied or m.round.points
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


class MatchEditView(GestorRequiredMixin, View):
    """Edita cualquier partido: equipos (pueden quedar vacíos → 'Por definir')
    y fecha/hora de saque. Si al cambiar los equipos el partido ya tenía
    pronósticos, exige `confirm_invalidate=1` y los borra. Si el nuevo kickoff
    es futuro y cambió, resetea los recordatorios automáticos para que se
    reprogramen en las nuevas ventanas."""

    def get(self, request, match_id):
        from competition.models import Team

        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        return render(
            request,
            "competition/_match_edit_modal.html",
            {
                "match": m,
                "all_teams": list(Team.objects.order_by("name")),
                "has_predictions": Prediction.objects.filter(match=m).exists(),
            },
        )

    def post(self, request, match_id):
        from datetime import datetime

        from django.utils import timezone

        from accounts.models import AuditLog
        from competition.models import BetsReminderLog, Team

        m = get_object_or_404(Match, pk=match_id)
        home_code = (request.POST.get("home_code") or "").strip()
        away_code = (request.POST.get("away_code") or "").strip()
        date_str = (request.POST.get("date") or "").strip()
        time_str = (request.POST.get("time") or "").strip()

        if home_code and away_code and home_code == away_code:
            messages.error(request, "Local y visitante no pueden ser el mismo equipo.")
            return redirect(self._back_url(request))

        home = Team.objects.filter(code=home_code).first() if home_code else None
        away = Team.objects.filter(code=away_code).first() if away_code else None
        if (home_code and home is None) or (away_code and away is None):
            messages.error(request, "Equipo no encontrado.")
            return redirect(self._back_url(request))

        try:
            new_kickoff = timezone.make_aware(
                datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            )
        except ValueError:
            messages.error(request, "Fecha u hora inválidas.")
            return redirect(self._back_url(request))

        teams_changed = m.home_id != (home.code if home else None) or m.away_id != (
            away.code if away else None
        )
        existing_preds = Prediction.objects.filter(match=m).exists()
        if teams_changed and existing_preds and request.POST.get("confirm_invalidate") != "1":
            messages.error(
                request,
                "Este partido ya tiene pronósticos. Marca la casilla de confirmación "
                "para cambiar los equipos y borrar los pronósticos existentes.",
            )
            return redirect(self._back_url(request))

        if teams_changed and existing_preds:
            Prediction.objects.filter(match=m).delete()

        old_kickoff = m.kickoff
        m.home = home
        m.away = away
        m.kickoff = new_kickoff
        m.save(update_fields=["home", "away", "kickoff"])

        if new_kickoff != old_kickoff and new_kickoff > timezone.now():
            BetsReminderLog.objects.filter(match=m, kind__in=BetsReminderLog.AUTO_KINDS).delete()

        AuditLog.objects.create(
            actor=request.user,
            action="match_edited",
            target_type="match",
            target_id=str(m.id),
            payload={
                "home": home.code if home else None,
                "away": away.code if away else None,
                "kickoff": new_kickoff.isoformat(),
            },
        )

        label = f"{home.name if home else 'Por definir'} vs {away.name if away else 'Por definir'}"
        messages.success(request, f"Partido actualizado · {label}")
        return redirect(self._back_url(request))

    @staticmethod
    def _back_url(request):
        from urllib.parse import urlencode

        from django.urls import reverse

        params = {}
        rnd = request.POST.get("round")
        md = request.POST.get("matchday")
        if rnd:
            params["round"] = rnd
        if md:
            params["matchday"] = md
        url = reverse("competicion:manage_results")
        return f"{url}?{urlencode(params)}" if params else url


class DeleteMatchView(GestorRequiredMixin, View):
    """Borra un partido por completo. Pensado para limpiar partidos creados por
    error (p. ej. cruces de prueba en producción). Si el partido tiene
    pronósticos o resultado, exige `confirm_delete=1` para evitar borrados
    accidentales, igual que `MatchEditView` con la invalidación."""

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)

        has_data = m.has_result or Prediction.objects.filter(match=m).exists()
        if has_data and request.POST.get("confirm_delete") != "1":
            messages.error(
                request,
                "Este partido tiene pronósticos o resultado. Confirma el borrado "
                "para eliminarlo junto con sus datos asociados.",
            )
            return redirect(self._back_url(request))

        if m.has_teams:
            label = f"{m.home.name} vs {m.away.name}"
        else:
            from competition.templatetags.competition_extras import slot_label

            label = f"{slot_label(m.home_slot)} vs {slot_label(m.away_slot)}"
        delete_match(m, actor=request.user)
        messages.success(request, f"Partido borrado · {label}")
        return redirect(self._back_url(request))

    @staticmethod
    def _back_url(request):
        """Vuelve a Resultados conservando la ronda/jornada seleccionada."""
        from urllib.parse import urlencode

        from django.urls import reverse

        params = {}
        rnd = request.POST.get("round")
        md = request.POST.get("matchday")
        if rnd:
            params["round"] = rnd
        if md:
            params["matchday"] = md
        url = reverse("competicion:manage_results")
        return f"{url}?{urlencode(params)}" if params else url
