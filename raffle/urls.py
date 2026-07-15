from django.urls import path

from . import views

urlpatterns = [
    path("", views.DrawView.as_view(), name="draw"),
    path("estado/", views.StateView.as_view(), name="state"),
    path("iniciar/", views.StartView.as_view(), name="start"),
    path("reiniciar/", views.ResetView.as_view(), name="reset"),
]
