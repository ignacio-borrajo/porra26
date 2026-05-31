from django.urls import path
from . import views

urlpatterns = [
    path("", views.StatsView.as_view(), name="dashboard"),
    path("chart-data.json", views.ChartDataView.as_view(), name="chart_data"),
]
