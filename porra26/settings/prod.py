import os

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

ALLOWED_HOSTS = [h.strip() for h in os.environ.get("DJANGO_ALLOWED_HOSTS", "").split(",") if h.strip()]
# Railway expone el dominio público del servicio en esta variable.
_railway_host = os.environ.get("RAILWAY_PUBLIC_DOMAIN")
if _railway_host and _railway_host not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append(_railway_host)

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
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_HSTS_PRELOAD = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

# Railway expone el servicio detrás de un proxy: el origen del POST llega
# como https://<dominio> y Django lo compara con la cabecera Origin para CSRF.
CSRF_TRUSTED_ORIGINS = [f"https://{h}" for h in ALLOWED_HOSTS if h]

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "porra26_cache",
    }
}

# SMTP saliente: Railway permite tráfico saliente al puerto 587. Apuntamos al
# SMTP corporativo (Office 365 por defecto). Si falta EMAIL_HOST se cae al
# backend de consola para no romper en arranques sin SMTP configurado.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "")
if EMAIL_HOST:
    EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
    EMAIL_PORT = int(os.environ.get("EMAIL_PORT", "587"))
    EMAIL_USE_TLS = os.environ.get("EMAIL_USE_TLS", "True").lower() in {"1", "true", "yes"}
    EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
    EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
    DEFAULT_FROM_EMAIL = os.environ.get("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER or "porra26@localhost")
else:
    EMAIL_BACKEND = "django.core.mail.backends.console.EmailBackend"

# Buzón destino al que se envía el PDF de cierre de cada partido. Power
# Automate vigila este buzón y republica el adjunto en el chat de Teams.
TEAMS_DESTINATION_EMAIL = os.environ.get("TEAMS_DESTINATION_EMAIL", "")
