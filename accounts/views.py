from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from .forms import ChangePasswordForm, LoginForm, ProfileForm


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
            login(request, request.user)
            messages.success(request, "Contraseña actualizada.")
            return redirect("competicion:dashboard")
        return render(request, self.template_name, {"form": form})


class MyAccountView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")

    def get(self, request):
        return render(
            request,
            "accounts/my_account.html",
            {
                "profile_form": ProfileForm(instance=request.user),
                "password_form": ChangePasswordForm(request.user),
            },
        )
