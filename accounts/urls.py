from django.urls import include, path

from . import views

urlpatterns = [
    path("api/", include("accounts.api.urls", namespace="api")),
    path("", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("cambiar-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("mi-cuenta/", views.MyAccountView.as_view(), name="my_account"),
    path(
        "cuenta/equipo/",
        views.TeamProfileModalView.as_view(),
        name="team_profile_modal",
    ),
    path(
        "recuperar/",
        views.PasswordResetRequestView.as_view(),
        name="password_reset",
    ),
    path(
        "recuperar/enviado/",
        views.PasswordResetSentView.as_view(),
        name="password_reset_sent",
    ),
    path(
        "recuperar/<uidb64>/<str:purpose>/<token>/",
        views.PasswordResetConfirmView.as_view(),
        name="password_reset_confirm",
    ),
    path(
        "recuperar/cambiada/",
        views.PasswordResetCompleteView.as_view(),
        name="password_reset_complete",
    ),
]
