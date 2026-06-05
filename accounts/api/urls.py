from django.urls import path

from accounts.api import views

app_name = "api"

urlpatterns = [
    path("sesiones/prune/", views.prune_sessions, name="prune_sessions"),
]
