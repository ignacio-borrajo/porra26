from django.urls import path

from . import views

urlpatterns = [
    path("", views.DrawView.as_view(), name="draw"),
    path("girar/", views.SpinView.as_view(), name="spin"),
    path("reiniciar/", views.ResetView.as_view(), name="reset"),
]
