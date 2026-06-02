from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", lambda r: HttpResponse("ok", content_type="text/plain")),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("competicion/", include(("competition.urls", "competicion"), namespace="competicion")),
    path("stats/", include(("stats.urls", "stats"), namespace="stats")),
    path("gestion/", include(("pot.urls", "pot"), namespace="pot")),
    path("reglas/", include(("core.urls", "core"), namespace="core")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
