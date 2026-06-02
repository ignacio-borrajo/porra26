from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = "test-key"
ALLOWED_HOSTS = ["testserver"]

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": ":memory:",
    }
}

PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
AXES_ENABLED = False

# Email — backend en memoria; los tests nunca emiten tráfico real.
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
DEFAULT_FROM_EMAIL = "porra26-bot@edisa.com"
TEAMS_DESTINATION_EMAIL = "test-destino@edisa.com"
