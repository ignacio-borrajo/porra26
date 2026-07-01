from django.urls import include, path

from . import views

urlpatterns = [
    path("", views.CompetitionView.as_view(), name="dashboard"),
    path("pronosticar/<int:match_id>/", views.PredictView.as_view(), name="predict"),
    path("partido/<int:match_id>/", views.MatchDetailView.as_view(), name="detail"),
    path("resultados/", views.ManageResultsView.as_view(), name="manage_results"),
    path("resultados/<int:match_id>/", views.ResultOfficialView.as_view(), name="official"),
    path(
        "resultados/<int:match_id>/editar/",
        views.MatchEditView.as_view(),
        name="edit",
    ),
    path(
        "resultados/<int:match_id>/borrar/",
        views.DeleteMatchView.as_view(),
        name="delete_match",
    ),
    path("api/teams/", include(("competition.api.urls", "api"), namespace="api")),
]
