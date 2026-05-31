from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    EXEMPT = ("/cambiar-password/", "/logout/", "/static/", "/admin/")

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, "must_change_password", False):
            if not any(request.path.startswith(p) for p in self.EXEMPT):
                return redirect(reverse("accounts:change_password"))
        return self.get_response(request)
