from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from accounts.mixins import RoleRequiredMixin
from accounts.models import AuditLog, User
from pot.forms import PlayerForm, generate_temp_password
from pot.models import Payment, Prize


class ManagePlayersView(RoleRequiredMixin, View):
    required_role = "gestor"

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


class PlayerFormView(RoleRequiredMixin, View):
    required_role = "gestor"

    def _get_object(self, pk):
        return User.objects.get(pk=pk) if pk else None

    def get(self, request, pk=None):
        obj = self._get_object(pk)
        form = PlayerForm(instance=obj)
        return render(request, "pot/_player_modal.html", {"form": form, "player": obj})

    def post(self, request, pk=None):
        obj = self._get_object(pk)
        form = PlayerForm(request.POST, instance=obj)
        if not form.is_valid():
            return render(request, "pot/_player_modal.html", {"form": form, "player": obj})
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
            messages.success(request, "Jugador creado.")
            return render(
                request, "pot/_password_reveal.html", {"player": user, "temp_password": temp}
            )
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect("pot:manage_players")


class ResetPasswordView(RoleRequiredMixin, View):
    required_role = "gestor"

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


class TogglePlayerActiveView(RoleRequiredMixin, View):
    required_role = "gestor"

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        u.is_active = not u.is_active
        u.save(update_fields=["is_active"])
        return redirect("pot:manage_players")


class TogglePaymentView(RoleRequiredMixin, View):
    required_role = "gestor"

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


class PrizesSettingsView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request):
        return render(
            request,
            "pot/prizes_settings.html",
            {"prizes": Prize.objects.all().select_related("round")},
        )

    def post(self, request):
        for prize in Prize.objects.all():
            raw = request.POST.get(f"amount_{prize.id}")
            if raw is None:
                continue
            try:
                prize.amount = max(0, int(raw))
                prize.save(update_fields=["amount"])
            except (ValueError, TypeError):
                pass
        AuditLog.objects.create(
            actor=request.user,
            action="prize_changed",
            target_type="prize",
            target_id="*",
            payload={},
        )
        messages.success(request, "Premios actualizados.")
        return redirect("pot:prizes")


class AuditLogView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request):
        return render(request, "accounts/audit_log.html", {"logs": AuditLog.objects.all()[:200]})
