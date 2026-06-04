import re

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve

from pwa import views as pwa_views


def _serve_media(request, path):
    """Sirve los archivos de MEDIA_ROOT.

    Lee settings.MEDIA_ROOT en cada request (no se congela en registro) para
    respetar overrides en tests y eventuales cambios en runtime.
    """
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", lambda r: HttpResponse("ok", content_type="text/plain")),
    # Endpoints PWA: deben servirse desde la raíz para que el scope del
    # service worker sea "/" y controle toda la app.
    path("manifest.webmanifest", pwa_views.manifest, name="pwa-manifest"),
    path("service-worker.js", pwa_views.service_worker, name="pwa-sw"),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("competicion/", include(("competition.urls", "competicion"), namespace="competicion")),
    path("stats/", include(("stats.urls", "stats"), namespace="stats")),
    path("gestion/", include(("pot.urls", "pot"), namespace="pot")),
    path("reglas/", include(("core.urls", "core"), namespace="core")),
    path("anuncios/", include(("announcements.urls", "announcements"), namespace="announcements")),
    # Sirve MEDIA_URL también con DEBUG=False. WhiteNoise solo atiende
    # STATIC_URL y Railway monta /app/media como volumen persistente; sin
    # esta ruta los avatares devuelven 404. La vista `serve` es adecuada
    # aquí: solo guardamos avatares normalizados a JPEG y la app es interna
    # y de bajo tráfico.
    re_path(
        rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$",
        _serve_media,
    ),
]
