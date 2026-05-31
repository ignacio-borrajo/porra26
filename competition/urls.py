from django.urls import path
from django.http import HttpResponse


def _stub(request, *a, **kw):
    return HttpResponse("stub")


urlpatterns = [
    path("", _stub, name="dashboard"),
    path("resultados/", _stub, name="manage_results"),
    path("pronosticar/<int:match_id>/", _stub, name="predict"),
    path("resultados/<int:match_id>/", _stub, name="official"),
]
