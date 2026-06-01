from django.urls import path

from . import views

urlpatterns = [
    path("", views.RulesView.as_view(), name="rules"),
]
