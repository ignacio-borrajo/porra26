from django.core.cache import cache
from django.shortcuts import redirect
from django.urls import reverse
from django.utils import timezone


class ForcePasswordChangeMiddleware:
    EXEMPT = ("/cambiar-password/", "/logout/", "/static/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, "must_change_password", False):
            if not any(request.path.startswith(p) for p in self.EXEMPT):
                return redirect(reverse("accounts:change_password"))
        return self.get_response(request)


class RememberMeRefreshMiddleware:
    """Renueva 'sliding window' la expiración de sesiones recordadas y
    actualiza last_seen_at en UserSession. Throttle de 60s por sesión
    para no martillear DB."""

    THROTTLE_SECONDS = 60
    REMEMBERED_EXPIRY = 30 * 24 * 3600

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return response
        session_key = request.session.session_key
        if not session_key:
            return response

        cache_key = f"session_touch:{session_key}"
        if cache.get(cache_key):
            return response
        cache.set(cache_key, 1, timeout=self.THROTTLE_SECONDS)

        from .models import UserSession

        try:
            us = UserSession.objects.get(session_key=session_key)
        except UserSession.DoesNotExist:
            return response

        if us.remembered:
            request.session.set_expiry(self.REMEMBERED_EXPIRY)

        UserSession.objects.filter(pk=us.pk).update(last_seen_at=timezone.now())
        return response
