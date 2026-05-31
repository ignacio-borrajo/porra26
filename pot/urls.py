from django.urls import path
from django.http import HttpResponse


def _stub(request, *a, **kw):
    return HttpResponse("stub")


urlpatterns = [
    path("jugadores/", _stub, name="manage_players"),
    path("jugadores/nuevo/", _stub, name="player_new"),
    path("jugadores/<int:pk>/", _stub, name="player_edit"),
    path("jugadores/<int:pk>/reset/", _stub, name="player_reset"),
    path("jugadores/<int:pk>/baja/", _stub, name="player_toggle_active"),
    path("jugadores/<int:pk>/pago/", _stub, name="player_toggle_payment"),
    path("premios/", _stub, name="prizes"),
    path("auditoria/", _stub, name="audit"),
]
