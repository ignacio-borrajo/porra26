from django.urls import path
from django.http import HttpResponse


def _stub(request, *a, **kw):
    return HttpResponse("stub")


urlpatterns = [
    path("", _stub, name="dashboard"),
    path("chart-data.json", _stub, name="chart_data"),
]
