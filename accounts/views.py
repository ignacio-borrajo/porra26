from datetime import timedelta

from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View

from competition.models import BET_CLOSE_HOURS, Match
from competition.services.standings import standings
from pot.models import Payment, Prize

from .forms import ChangePasswordForm, LoginForm, ProfileForm
from .models import AuditLog, User


class LoginView(View):
    template_name = "accounts/login.html"

    def _info_context(self) -> dict:
        first_prize = (
            Prize.objects.filter(scope="global", position=1)
            .values_list("amount", flat=True)
            .first()
        )
        next_matches = list(
            Match.objects.filter(kickoff__gt=timezone.now())
            .select_related("home", "away", "round")
            .order_by("kickoff")[:3]
        )
        for m in next_matches:
            m.close_at = m.kickoff - timedelta(hours=BET_CLOSE_HOURS)
        top_rows = standings()[:5]
        users_by_id = User.objects.in_bulk([r.player_id for r in top_rows])
        return {
            "players_count": Payment.objects.filter(paid=True).count(),
            "first_prize": int(first_prize) if first_prize is not None else 0,
            "next_matches": next_matches,
            "top_rows": top_rows,
            "top_users": users_by_id,
        }

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("competicion:dashboard")
        return render(request, self.template_name, {"form": LoginForm(), **self._info_context()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.get_user(request)
            if user is not None:
                login(request, user)
                if user.must_change_password:
                    return redirect("accounts:change_password")
                return redirect("competicion:dashboard")
            messages.error(request, "Correo o contraseña incorrectos.")
        return render(request, self.template_name, {"form": form, **self._info_context()})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("accounts:login")

    def get(self, request):
        return self.post(request)


class ChangePasswordView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")
    template_name = "accounts/change_password.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ChangePasswordForm(request.user)})

    def post(self, request):
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new1"])
            request.user.must_change_password = False
            request.user.save(update_fields=["password", "must_change_password"])
            update_session_auth_hash(request, request.user)
            messages.success(request, "Contraseña actualizada.")
            return redirect("competicion:dashboard")
        return render(request, self.template_name, {"form": form})


class MyAccountView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")
    template_name = "accounts/my_account.html"

    def _render(self, request, profile_form=None, password_form=None, status=200):
        return render(
            request,
            self.template_name,
            {
                "profile_form": profile_form or ProfileForm(instance=request.user),
                "password_form": password_form or ChangePasswordForm(request.user),
            },
            status=status,
        )

    def get(self, request):
        return self._render(request)

    def post(self, request):
        action = request.POST.get("action")
        if action == "profile":
            return self._post_profile(request)
        if action == "password":
            return self._post_password(request)
        return HttpResponseBadRequest("acción no válida")

    def _post_profile(self, request):
        old_avatar_name = request.user.avatar.name if request.user.avatar else ""
        form = ProfileForm(request.POST, request.FILES, instance=request.user)
        if not form.is_valid():
            return self._render(request, profile_form=form)
        changed = list(form.changed_data)
        wants_clear = bool(request.POST.get("avatar-clear") and not request.FILES.get("avatar"))
        new_avatar = form.cleaned_data.get("avatar")
        form.save()
        if new_avatar and old_avatar_name:
            request.user.avatar.storage.delete(old_avatar_name)
        if wants_clear and request.user.avatar:
            request.user.avatar.delete(save=False)
            request.user.avatar = None
            request.user.save(update_fields=["avatar"])
            if "avatar" not in changed:
                changed.append("avatar")
        if changed:
            AuditLog.objects.create(
                actor=request.user,
                action="profile.update",
                target_type="user",
                target_id=str(request.user.id),
                payload={"changed": changed},
            )
        messages.success(request, "Datos actualizados.")
        return redirect("accounts:my_account")

    def _post_password(self, request):
        form = ChangePasswordForm(request.user, request.POST)
        if not form.is_valid():
            return self._render(request, password_form=form)
        request.user.set_password(form.cleaned_data["new1"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, request.user)
        AuditLog.objects.create(
            actor=request.user,
            action="password.change",
            target_type="user",
            target_id=str(request.user.id),
        )
        messages.success(request, "Contraseña actualizada.")
        return redirect("accounts:my_account")
