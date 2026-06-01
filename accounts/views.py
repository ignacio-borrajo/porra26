from django.contrib import messages
from django.contrib.auth import login, logout, update_session_auth_hash
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import HttpResponseBadRequest
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from .forms import ChangePasswordForm, LoginForm, ProfileForm
from .models import AuditLog


class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("competicion:dashboard")
        return render(request, self.template_name, {"form": LoginForm()})

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
        return render(request, self.template_name, {"form": form})


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
        form = ProfileForm(request.POST, instance=request.user)
        if not form.is_valid():
            return self._render(request, profile_form=form)
        changed = list(form.changed_data)
        form.save()
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
