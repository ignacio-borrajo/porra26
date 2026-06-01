from django.urls import path

from competition.api import views

app_name = "api"

urlpatterns = [
    path("cierres-pendientes/", views.cierres_pendientes, name="cierres_pendientes"),
]
