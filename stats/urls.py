from django.urls import path

from . import views

urlpatterns = [
    path("", views.StatsView.as_view(), name="dashboard"),
    path("chart-data.json", views.ChartDataView.as_view(), name="chart_data"),
    path("rankings/", views.RankingsView.as_view(), name="rankings"),
    path(
        "rankings/<slug:dim>/<slug:key>/",
        views.GroupRankingsView.as_view(),
        name="rankings_group",
    ),
    path("historico/", views.HistoryView.as_view(), name="historico"),
    path("historico.xlsx", views.HistoryExportView.as_view(), name="historico_export"),
]
