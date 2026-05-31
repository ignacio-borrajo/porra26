from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class GestorRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_gestor:
            messages.warning(request, "No tienes permisos para esa sección.")
            return redirect("competicion:dashboard")
        return super().dispatch(request, *args, **kwargs)
