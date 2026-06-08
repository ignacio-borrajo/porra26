import hashlib
import logging
import os
import sys

import dj_database_url

from .base import *  # noqa: F401,F403
from .base import MIDDLEWARE

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]

# Soporte para rotar SECRET_KEY sin desloguear a todos los usuarios. Django
# verifica firmas de cookies de sesión contra `SECRET_KEY` primero y, si
# falla, contra cada entrada de `SECRET_KEY_FALLBACKS`. Para rotar:
#   1. Mueve el SECRET_KEY actual a DJANGO_SECRET_KEY_FALLBACK.
#   2. Pon uno nuevo en DJANGO_SECRET_KEY.
#   3. Tras 30 días (vida útil máxima de las cookies de sesión) borra el
#      fallback.
_fallback = os.environ.get("DJANGO_SECRET_KEY_FALLBACK", "").strip()
SECRET_KEY_FALLBACKS = [_fallback] if _fallback else []


# Diagnóstico: imprime un fingerprint del SECRET_KEY (SHA-256 truncado, no la
# clave) al arranque del proceso. Si en dos deploys consecutivos el
# fingerprint cambia sin que hayamos rotado adrede, Railway está mutando la
# variable: TODA cookie de sesión queda inválida y los usuarios se deslogean.
def _secret_fingerprint(key: str) -> str:
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:12]


_fp_current = _secret_fingerprint(SECRET_KEY)
_fp_fallback = _secret_fingerprint(_fallback) if _fallback else "—"
print(
    f"[boot] SECRET_KEY fingerprint={_fp_current} fallback={_fp_fallback}",
    file=sys.stderr,
    flush=True,
)
logging.getLogger("django").info("SECRET_KEY fingerprint=%s fallback=%s", _fp_current, _fp_fallback)

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

# Logging: sin esta config, el LOGGING por defecto de Django filtra los logs
# INFO/WARNING de la aplicación cuando DEBUG=False (el handler de consola por
# defecto tiene un filtro `require_debug_true`). Resultado: cualquier
# `logger.info(...)` desde nuestro código se descarta y nunca llega a stderr,
# que es lo que Railway captura como "Deploy Logs". Esta configuración mínima
# manda INFO+ del root a stderr para que nuestros logs sean visibles, y
# silencia el SQL de django.db.backends (que es ruido a este nivel).
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "concise": {
            "format": "[{asctime}] {levelname} {name}: {message}",
            "style": "{",
        },
    },
    "handlers": {
        "stderr": {
            "class": "logging.StreamHandler",
            "stream": "ext://sys.stderr",
            "formatter": "concise",
        },
    },
    "root": {
        "handlers": ["stderr"],
        "level": "INFO",
    },
    "loggers": {
        # django.db.backends emite cada SQL a DEBUG; lo dejamos en WARNING
        # para no inundar los logs de Railway con cada query.
        "django.db.backends": {"level": "WARNING", "propagate": True},
    },
}
