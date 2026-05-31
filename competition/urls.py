from django.urls import path
from . import views

urlpatterns = [
    path("", views.CompetitionView.as_view(), name="dashboard"),
    path("pronosticar/<int:match_id>/", views.PredictView.as_view(), name="predict"),
    path("resultados/", views.ManageResultsView.as_view(), name="manage_results"),
    path("resultados/<int:match_id>/", views.ResultOfficialView.as_view(), name="official"),
]
