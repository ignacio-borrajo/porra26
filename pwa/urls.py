# Las rutas PWA viven en porra26/urls.py porque el scope del service
# worker depende de su ubicación: debe servirse desde la raíz. Este
# archivo existe para mantener la convención de tener un urls.py por
# app, pero no expone rutas propias.
from django.urls import path

app_name = "pwa"

urlpatterns: list[path] = []
