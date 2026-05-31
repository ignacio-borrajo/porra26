from django.urls import path

from . import views

urlpatterns = [
    path("", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("cambiar-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("mi-cuenta/", views.MyAccountView.as_view(), name="my_account"),
]
