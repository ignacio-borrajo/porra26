from django.urls import path

from competition.api import views

app_name = "api"

urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
    path("cierres/disparar/", views.cierres_disparar, name="cierres_disparar"),
    path("cierres/<int:match_id>/pdf/", views.cierre_pdf, name="cierre_pdf"),
    path("cierres/<int:match_id>/enviar/", views.cierre_enviar, name="cierre_enviar"),
    path(
        "recordatorios/disparar/",
        views.recordatorios_disparar,
        name="recordatorios_disparar",
    ),
    path(
        "recordatorios/<int:match_id>/enviar/",
        views.recordatorio_enviar,
        name="recordatorio_enviar",
    ),
    path("live/tick/", views.live_tick, name="live_tick"),
]
