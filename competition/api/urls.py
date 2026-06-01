from django.urls import path

from competition.api import views

app_name = "api"

urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
    path("cierres/<int:match_id>/pdf/", views.cierre_pdf, name="cierre_pdf"),
    path(
        "cierres/<int:match_id>/marcar-enviado/",
        views.cierre_marcar_enviado,
        name="cierre_marcar_enviado",
    ),
]
