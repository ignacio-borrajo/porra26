from django.urls import path

from . import views

urlpatterns = [
    path("jugadores/", views.ManagePlayersView.as_view(), name="manage_players"),
    path("jugadores/importar/", views.PlayersImportView.as_view(), name="players_import"),
    path(
        "jugadores/importar/resultado/",
        views.PlayersImportResultView.as_view(),
        name="players_import_result",
    ),
    path(
        "jugadores/bienvenida-masiva/",
        views.PlayersBulkWelcomeView.as_view(),
        name="players_bulk_welcome",
    ),
    path("jugadores/nuevo/", views.PlayerFormView.as_view(), name="player_new"),
    path("jugadores/<int:pk>/", views.PlayerFormView.as_view(), name="player_edit"),
    path("jugadores/<int:pk>/reset/", views.ResetPasswordView.as_view(), name="player_reset"),
    path(
        "jugadores/<int:pk>/reenviar-email/",
        views.PlayerResendInviteView.as_view(),
        name="player_resend_invite",
    ),
    path("jugadores/<int:pk>/clave/", views.PasswordRevealView.as_view(), name="player_reveal"),
    path(
        "jugadores/<int:pk>/contrasena/",
        views.SetPasswordView.as_view(),
        name="player_set_password",
    ),
    path(
        "jugadores/<int:pk>/baja/",
        views.TogglePlayerActiveView.as_view(),
        name="player_toggle_active",
    ),
    path(
        "jugadores/<int:pk>/pago/", views.TogglePaymentView.as_view(), name="player_toggle_payment"
    ),
    path("premios/", views.PrizesSettingsView.as_view(), name="prizes"),
    path("auditoria/", views.AuditLogView.as_view(), name="audit"),
]
