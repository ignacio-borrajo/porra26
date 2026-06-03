from django.contrib import messages
from django.http import HttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.views import View

from accounts.mixins import GestorRequiredMixin
from accounts.models import AuditLog, User
from competition.models import Round
from pot.forms import PlayerForm, generate_temp_password
from pot.models import Payment, PotSettings, Prize


class ManagePlayersView(GestorRequiredMixin, View):
    def get(self, request):
        q = request.GET.get("q", "").strip()
        players = User.objects.all().order_by("name")
        if q:
            from django.db.models import Q

            players = players.filter(Q(name__icontains=q) | Q(email__icontains=q))
        return render(
            request,
            "pot/manage_players.html",
            {
                "players": players,
                "q": q,
                "active_count": User.objects.filter(is_active=True).count(),
                "paid_count": Payment.objects.filter(paid=True).count(),
                "total_count": User.objects.count(),
            },
        )


class PlayerFormView(GestorRequiredMixin, View):
    def _is_modal(self, request) -> bool:
        return request.headers.get("X-Modal") == "1"

    def _get_object(self, pk):
        return User.objects.get(pk=pk) if pk else None

    def _render_form(self, request, form, obj):
        return render(
            request,
            "pot/_player_modal.html",
            {"form": form, "player": obj, "modal": self._is_modal(request)},
        )

    def get(self, request, pk=None):
        obj = self._get_object(pk)
        return self._render_form(request, PlayerForm(instance=obj), obj)

    def post(self, request, pk=None):
        obj = self._get_object(pk)
        form = PlayerForm(request.POST, instance=obj)
        if not form.is_valid():
            response = self._render_form(request, form, obj)
            if self._is_modal(request):
                response["X-Modal-Errors"] = "1"
            return response

        is_new = obj is None
        if is_new:
            temp = generate_temp_password()
            user = form.save(commit=False)
            user.set_password(temp)
            user.must_change_password = True
            user.save()
            Payment.objects.get_or_create(player=user)
            AuditLog.objects.create(
                actor=request.user,
                action="player_created",
                target_type="user",
                target_id=str(user.id),
                payload={},
            )
            request.session[f"temp_pw_{user.id}"] = temp
            target = reverse("pot:player_reveal", args=[user.id])
        else:
            form.save()
            target = reverse("pot:manage_players")

        messages.success(request, "Jugador guardado." if not is_new else "Jugador creado.")
        if self._is_modal(request):
            response = HttpResponse(status=200)
            response["X-Modal-Redirect"] = target
            return response
        return redirect(target)


class ResetPasswordView(GestorRequiredMixin, View):
    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        temp = generate_temp_password()
        u.set_password(temp)
        u.must_change_password = True
        u.save(update_fields=["password", "must_change_password"])
        AuditLog.objects.create(
            actor=request.user,
            action="password_reset",
            target_type="user",
            target_id=str(u.id),
            payload={},
        )
        return render(request, "pot/_password_reveal.html", {"player": u, "temp_password": temp})


class PasswordRevealView(GestorRequiredMixin, View):
    """Pantalla que muestra la contraseña temporal generada para un alta.

    Se accede vía X-Modal-Redirect tras un POST exitoso de alta. Es
    información sensible y por eso vive en una página propia, fuera del
    overlay.
    """

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        temp = request.session.pop(f"temp_pw_{pk}", None)
        if not temp:
            messages.warning(request, "La contraseña ya no está disponible.")
            return redirect("pot:manage_players")
        return render(
            request,
            "pot/_password_reveal.html",
            {"player": user, "temp_password": temp},
        )


class TogglePlayerActiveView(GestorRequiredMixin, View):
    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        u.is_active = not u.is_active
        u.save(update_fields=["is_active"])
        return redirect("pot:manage_players")


class TogglePaymentView(GestorRequiredMixin, View):
    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        pay, _ = Payment.objects.get_or_create(player=u)
        pay.paid = not pay.paid
        pay.paid_at = timezone.now() if pay.paid else None
        pay.save()
        AuditLog.objects.create(
            actor=request.user,
            action="payment_toggled",
            target_type="user",
            target_id=str(u.id),
            payload={"paid": pay.paid},
        )
        return redirect("pot:manage_players")


class PrizesSettingsView(GestorRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "pot/prizes_settings.html",
            {
                "prizes": Prize.objects.filter(scope="global").order_by("position"),
                "settings": PotSettings.load(),
                "paid_count": Payment.objects.filter(paid=True).count(),
                "rounds": Round.objects.all().order_by("order"),
            },
        )

    def post(self, request):
        from decimal import Decimal, InvalidOperation
        from django.db import transaction

        def _parse_decimal(raw):
            try:
                value = Decimal(raw)
            except (TypeError, InvalidOperation):
                return None
            return value if value >= 0 else None

        def _parse_int(raw):
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return None
            return value if value >= 0 else None

        scoring_changes: dict[str, dict[str, int]] = {}

        with transaction.atomic():
            for prize in Prize.objects.filter(scope="global"):
                raw = request.POST.get(f"amount_{prize.id}")
                value = _parse_decimal(raw)
                if value is not None:
                    prize.amount = value
                    prize.save(update_fields=["amount"])

            mw_raw = request.POST.get("matchday_winner_prize")
            mw_value = _parse_decimal(mw_raw)
            if mw_value is not None:
                settings_obj = PotSettings.load()
                settings_obj.matchday_winner_prize = mw_value
                settings_obj.save(update_fields=["matchday_winner_prize"])

            for round_ in Round.objects.all():
                changes: dict[str, int] = {}
                new_exact = _parse_int(request.POST.get(f"exact_{round_.id}"))
                if new_exact is not None and new_exact != round_.points:
                    round_.points = new_exact
                    round_.save(update_fields=["points"])
                    changes["exact"] = new_exact
                new_partial = _parse_int(request.POST.get(f"partial_{round_.id}"))
                if new_partial is not None and new_partial != round_.partial_points:
                    round_.partial_points = new_partial
                    round_.save(update_fields=["partial_points"])
                    changes["partial"] = new_partial
                if changes:
                    scoring_changes[round_.id] = changes

            AuditLog.objects.create(
                actor=request.user,
                action="prize_changed",
                target_type="prize",
                target_id="*",
                payload={},
            )
            if scoring_changes:
                AuditLog.objects.create(
                    actor=request.user,
                    action="scoring_changed",
                    target_type="round",
                    target_id="*",
                    payload=scoring_changes,
                )

        messages.success(request, "Premios y puntos actualizados.")
        return redirect("pot:prizes")


class AuditLogView(GestorRequiredMixin, View):
    def get(self, request):
        return render(request, "accounts/audit_log.html", {"logs": AuditLog.objects.all()[:200]})
