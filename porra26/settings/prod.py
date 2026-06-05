import os

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = [
    h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()
]
# Railway expone el dominio público del servicio en esta variable.
_railway_host = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if _railway_host and _railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_host)
# Railway lanza los healthchecks desde el host interno `healthcheck.railway.app`
# por HTTP plano. Sin esto Django responde 400 DisallowedHost y el deploy nunca
# pasa de fase Network → Healthcheck.
if "healthcheck.railway.app" not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append("healthcheck.railway.app")

# PostgreSQL en Railway. DATABASE_URL la inyecta el plugin de Postgres al
# enlazarlo al servicio web. Requiere SSL (conn_max_age reusa conexiones).
DATABASES = {
    "default": dj_database_url.config(
        env="DATABASE_URL",
        conn_max_age=600,
        ssl_require=True,
    )
}

# Whitenoise sirve los estáticos compactados desde el propio proceso gunicorn.
# Debe ir justo después de SecurityMiddleware.
MIDDLEWARE = [
    MIDDLEWARE[0],
    "whitenoise.middleware.WhiteNoiseMiddleware",
    *MIDDLEWARE[1:],
]
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

SECURE_SSL_REDIRECT = True
# El healthcheck de Railway llega por HTTP plano; si lo redirigimos a HTTPS
# obtiene un 301 y marca el deploy como fallido. Eximimos solo /healthz/.
SECURE_REDIRECT_EXEMPT = [r"^healthz/$"]
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
# La expiración la gestiona LoginView por sesión (set_expiry(0) si el usuario
# no marca 'Recordarme', 30 días si lo marca). No forzamos cierre al navegador
# a nivel global porque ese flag invalida el 'remember me'.

# Railway expone el servicio detrás de un proxy: el origen del POST llega
# como https://<dominio> y Django lo compara con la cabecera Origin para CSRF.
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "porra26_cache",
    }
}

# SMTP saliente y TEAMS_DESTINATION_EMAIL viven en base.py (leídos del
# entorno) para que el management command de cierre por email funcione en
# todos los entornos. Aquí no hace falta nada específico de producción.
