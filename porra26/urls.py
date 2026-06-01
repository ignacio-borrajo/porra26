from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("competicion/", include(("competition.urls", "competicion"), namespace="competicion")),
    path("stats/", include(("stats.urls", "stats"), namespace="stats")),
    path("gestion/", include(("pot.urls", "pot"), namespace="pot")),
    path("reglas/", include(("core.urls", "core"), namespace="core")),
]
