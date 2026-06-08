from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import ValidationError
from django.http import HttpResponse, HttpResponseBadRequest, HttpResponseNotFound
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.utils import timezone
from django.views import View
from django.views.generic import TemplateView

from competition.models import Match
from pot.models import Payment, Prize

from .forms import ChangePasswordForm, LoginForm, ProfileForm, TeamProfileForm
from .models import AuditLog, User, UserSession
from .services.notifications import send_password_changed_email
from .services.password_reset import (
    _client_ip,
    send_password_reset_email,
    validate_reset_token,
)
from .services.sessions import parse_device_label, revoke_sessions
from .validators import validate_email_domain


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
        return {
            "players_count": Payment.objects.filter(paid=True).count(),
            "first_prize": int(first_prize) if first_prize is not None else 0,
            "next_matches": next_matches,
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
                remembered = bool(form.cleaned_data.get("remember"))
                if remembered:
                    request.session.set_expiry(30 * 24 * 3600)
                else:
                    request.session.set_expiry(0)

                is_pwa = request.POST.get("is_pwa") == "1"
                ua_raw = request.META.get("HTTP_USER_AGENT", "")[:400]
                ip = _client_ip(request)
                UserSession.objects.create(
                    user=user,
                    session_key=request.session.session_key,
                    device_label=parse_device_label(ua_raw),
                    user_agent_raw=ua_raw,
                    ip_at_login=ip,
                    is_pwa=is_pwa,
                    remembered=remembered,
                    last_seen_at=timezone.now(),
                )
                AuditLog.objects.create(
                    actor=user,
                    action="login",
                    target_type="user",
                    target_id=str(user.id),
                    payload={
                        "remembered": remembered,
                        "is_pwa": is_pwa,
                        "ip": ip,
                    },
                )

                if user.must_change_password:
                    return redirect("accounts:change_password")
                return redirect("competicion:dashboard")
            messages.error(request, "Correo o contraseña incorrectos.")
        return render(request, self.template_name, {"form": form, **self._info_context()})


class LogoutView(View):
    def post(self, request):
        if request.user.is_authenticated and request.session.session_key:
            UserSession.objects.filter(session_key=request.session.session_key).delete()
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
            current_us = UserSession.objects.filter(session_key=request.session.session_key).first()
            others = list(
                UserSession.objects.filter(user=request.user)
                .exclude(session_key=request.session.session_key)
                .values_list("session_key", flat=True)
            )
            revoke_sessions(
                user=request.user,
                session_keys=others,
                actor=request.user,
                reason="password_change_forced",
            )

            request.user.set_password(form.cleaned_data["new1"])
            request.user.must_change_password = False
            request.user.save(update_fields=["password", "must_change_password"])
            update_session_auth_hash(request, request.user)

            if current_us:
                UserSession.objects.create(
                    user=request.user,
                    session_key=request.session.session_key,
                    device_label=current_us.device_label,
                    user_agent_raw=current_us.user_agent_raw,
                    ip_at_login=current_us.ip_at_login,
                    is_pwa=current_us.is_pwa,
                    remembered=current_us.remembered,
                    last_seen_at=timezone.now(),
                )

            send_password_changed_email(request.user)
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
                "user_sessions": (
                    UserSession.objects.filter(user=request.user).order_by("-last_seen_at")
                ),
                "current_session_key": request.session.session_key,
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
        if action == "revoke_session":
            return self._post_revoke_session(request)
        if action == "revoke_others":
            return self._post_revoke_others(request)
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

        # Snapshot de la sesión actual: tras set_password el signal borra
        # todas las UserSession del usuario; la recreamos al final.
        current_us = UserSession.objects.filter(session_key=request.session.session_key).first()

        # Revocar OTRAS sesiones explícitamente, con AuditLog del count real.
        others = list(
            UserSession.objects.filter(user=request.user)
            .exclude(session_key=request.session.session_key)
            .values_list("session_key", flat=True)
        )
        revoke_sessions(
            user=request.user,
            session_keys=others,
            actor=request.user,
            reason="password_change",
        )

        request.user.set_password(form.cleaned_data["new1"])
        request.user.must_change_password = False
        request.user.save(update_fields=["password", "must_change_password"])
        update_session_auth_hash(request, request.user)

        # Restaurar UserSession actual (el signal la había borrado).
        if current_us:
            UserSession.objects.create(
                user=request.user,
                session_key=request.session.session_key,
                device_label=current_us.device_label,
                user_agent_raw=current_us.user_agent_raw,
                ip_at_login=current_us.ip_at_login,
                is_pwa=current_us.is_pwa,
                remembered=current_us.remembered,
                last_seen_at=timezone.now(),
            )

        AuditLog.objects.create(
            actor=request.user,
            action="password.change",
            target_type="user",
            target_id=str(request.user.id),
        )
        send_password_changed_email(request.user)
        if others:
            n = len(others)
            messages.success(
                request,
                f"Contraseña actualizada. Se han cerrado {n} otra{'s' if n != 1 else ''} sesion{'es' if n != 1 else ''}.",
            )
        else:
            messages.success(request, "Contraseña actualizada.")
        return redirect("accounts:my_account")

    def _post_revoke_session(self, request):
        target = (request.POST.get("session_key") or "").strip()
        if not target or target == request.session.session_key:
            return HttpResponseBadRequest("sesión no válida")
        keys = list(
            UserSession.objects.filter(user=request.user, session_key=target).values_list(
                "session_key", flat=True
            )
        )
        if keys:
            revoke_sessions(
                user=request.user,
                session_keys=keys,
                actor=request.user,
                reason="user_revoke",
            )
            messages.success(request, "Sesión cerrada.")
        return redirect("accounts:my_account")

    def _post_revoke_others(self, request):
        others = list(
            UserSession.objects.filter(user=request.user)
            .exclude(session_key=request.session.session_key)
            .values_list("session_key", flat=True)
        )
        if others:
            n = revoke_sessions(
                user=request.user,
                session_keys=others,
                actor=request.user,
                reason="user_revoke_others",
            )
            messages.success(
                request,
                f"Se han cerrado {n} sesion{'es' if n != 1 else ''}.",
            )
        return redirect("accounts:my_account")


class TeamProfileModalView(LoginRequiredMixin, View):
    """Modal que aparece en /competicion/ si al usuario le falta sede, dept o
    puesto. Visualizarlo marca un flag en la sesión para no volver a abrirlo
    hasta el próximo login, aunque se cierre con X o Escape."""

    login_url = reverse_lazy("accounts:login")
    template_name = "accounts/_team_profile_modal.html"

    def get(self, request):
        request.session["team_profile_dismissed"] = True
        return render(
            request,
            self.template_name,
            {"form": TeamProfileForm(instance=request.user)},
        )

    def post(self, request):
        form = TeamProfileForm(request.POST, instance=request.user)
        if not form.is_valid():
            resp = render(request, self.template_name, {"form": form})
            resp["X-Modal-Errors"] = "1"
            return resp
        changed = list(form.changed_data)
        form.save()
        if changed:
            AuditLog.objects.create(
                actor=request.user,
                action="profile.update",
                target_type="user",
                target_id=str(request.user.id),
                payload={"changed": changed, "source": "team_profile_modal"},
            )
        messages.success(request, "¡Listo! Ya compites también en equipo.")
        return HttpResponse(status=200)


class PasswordResetRequestView(View):
    template_name = "accounts/password_reset_request.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = (request.POST.get("email") or "").strip().lower()
        encontrado = False
        user = None
        domain_ok = bool(email and "@" in email)
        if domain_ok:
            try:
                validate_email_domain(email)
            except ValidationError:
                domain_ok = False
        if domain_ok:
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
                encontrado = True
            except User.DoesNotExist:
                pass
        AuditLog.objects.create(
            actor=None,
            action="password_reset_requested",
            target_type="user",
            target_id=str(user.id) if user else "",
            payload={
                "email_intentado": email,
                "encontrado": encontrado,
                "ip": _client_ip(request),
                "purpose": "reset",
            },
        )
        if user:
            send_password_reset_email(user, purpose="reset")
        request.session["password_reset_email"] = email
        return redirect("accounts:password_reset_sent")


class PasswordResetSentView(TemplateView):
    template_name = "accounts/password_reset_sent.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["email"] = self.request.session.pop("password_reset_email", "")
        return ctx


class PasswordResetConfirmView(View):
    template_name = "accounts/password_reset_confirm.html"
    invalid_template_name = "accounts/password_reset_invalid.html"

    def dispatch(self, request, uidb64, purpose, token, *args, **kwargs):
        if purpose not in ("reset", "welcome"):
            return HttpResponseNotFound()
        self.user = validate_reset_token(uidb64, purpose, token)
        self.purpose = purpose
        if self.user is None:
            return render(request, self.invalid_template_name, status=410)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"purpose": self.purpose, "form": SetPasswordForm(self.user)},
        )

    def post(self, request):
        form = SetPasswordForm(self.user, request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"purpose": self.purpose, "form": form},
            )
        user = form.save()
        user.must_change_password = False
        user.save(update_fields=["must_change_password"])

        # Tras un reset por email asumimos posible compromiso: cerrar TODAS
        # las sesiones del usuario (incluidas las que un atacante pueda tener).
        all_keys = list(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
        revoke_sessions(
            user=user,
            session_keys=all_keys,
            actor=None,
            reason="password_reset_email",
        )
        send_password_changed_email(user)

        AuditLog.objects.create(
            actor=None,
            action="password_reset_completed",
            target_type="user",
            target_id=str(user.id),
            payload={"purpose": self.purpose, "ip": _client_ip(request)},
        )
        return redirect("accounts:password_reset_complete")


class PasswordResetCompleteView(TemplateView):
    template_name = "accounts/password_reset_complete.html"
