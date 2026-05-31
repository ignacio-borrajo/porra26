# PORRA 26 — Plan de implementación v1

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Construir la aplicación web interna PORRA 26 (porra del Mundial FIFA 2026) sobre Django + MySQL siguiendo el spec aprobado en `docs/superpowers/specs/2026-05-31-porra26-design.md`, con fidelidad de píxel al prototipo de `design-reference/` y desplegable en PythonAnywhere free.

**Architecture:** Backend Django 5 con apps por dominio (`accounts`, `competition`, `pot`, `stats`, `core`). UI con templates Django + CSS estático del prototipo + JS vanilla modular (sin SPA, sin bundler). Sin SMTP saliente (contraseñas temporales se muestran al gestor en pantalla). Estado de partido y standings derivados, no almacenados.

**Tech Stack:** Python 3.12, Django 5.x, MySQL (prod) / SQLite (dev+test), pytest+pytest-django+factory-boy+freezegun, django-axes, django-csp, ruff. JS ES modules vanilla, sin bundler.

---

## Convenciones del plan

- **Idioma del código:** identificadores y comentarios en inglés; cadenas de UI en español de España.
- **Tests primero:** cada nueva pieza de lógica viene con su test antes de la implementación.
- **Commits frecuentes:** cada tarea termina con un commit. Mensajes en español, imperativo, prefijos `feat:` / `test:` / `chore:` / `docs:` / `fix:`.
- **Path absoluto del proyecto:** `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/`. Los paths en el plan son relativos a esa raíz.
- **Comandos:** se ejecutan desde la raíz salvo que se indique otra cosa.

---

## Fase 0 — Cimientos del proyecto

### Tarea 0.1: pyproject.toml y dependencias base

**Files:**
- Create: `pyproject.toml`
- Create: `requirements.txt`
- Create: `requirements-dev.txt`

- [ ] **Step 1: Crear `pyproject.toml`**

```toml
[project]
name = "porra26"
version = "0.1.0"
description = "Porra interna del Mundial FIFA 2026"
requires-python = ">=3.12"

[tool.ruff]
line-length = 100
target-version = "py312"
extend-exclude = ["design-reference", "migrations"]

[tool.ruff.lint]
select = ["E", "F", "I", "B", "UP", "DJ"]
ignore = ["E501"]

[tool.pytest.ini_options]
DJANGO_SETTINGS_MODULE = "porra26.settings.test"
python_files = ["tests.py", "test_*.py", "*_tests.py"]
addopts = "-ra --strict-markers"
```

- [ ] **Step 2: Crear `requirements.txt`** (deps de producción)

```
Django>=5.0,<5.2
mysqlclient>=2.2
django-axes>=6.4
django-csp>=3.8
python-dotenv>=1.0
```

- [ ] **Step 3: Crear `requirements-dev.txt`**

```
-r requirements.txt
pytest>=8.0
pytest-django>=4.8
pytest-cov>=4.1
factory-boy>=3.3
freezegun>=1.4
ruff>=0.5
playwright>=1.45
```

- [ ] **Step 4: Crear virtualenv e instalar**

```bash
python3.12 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt
```

Esperado: instalación termina sin error. `django-admin --version` muestra 5.x.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml requirements.txt requirements-dev.txt
git commit -m "chore: añadir pyproject.toml y dependencias base"
```

---

### Tarea 0.2: Esqueleto del proyecto Django

**Files:**
- Create: `manage.py`
- Create: `porra26/__init__.py`
- Create: `porra26/asgi.py`
- Create: `porra26/wsgi.py`
- Create: `porra26/urls.py`

- [ ] **Step 1: Generar proyecto en la raíz**

```bash
django-admin startproject porra26 .
```

Esperado: se crean `manage.py` y `porra26/` con `settings.py`, `urls.py`, `wsgi.py`, `asgi.py`.

- [ ] **Step 2: Sustituir `porra26/urls.py`** con esqueleto vacío

```python
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
```

- [ ] **Step 3: Verificar arranque básico**

```bash
python manage.py check
```

Esperado: `System check identified no issues (0 silenced).`

- [ ] **Step 4: Commit**

```bash
git add manage.py porra26/
git commit -m "chore: inicializar proyecto Django"
```

---

### Tarea 0.3: Settings split (base/dev/test/prod)

**Files:**
- Delete: `porra26/settings.py`
- Create: `porra26/settings/__init__.py`
- Create: `porra26/settings/base.py`
- Create: `porra26/settings/dev.py`
- Create: `porra26/settings/test.py`
- Create: `porra26/settings/prod.py`
- Create: `.env.example`

- [ ] **Step 1: Convertir `settings.py` en paquete**

```bash
mkdir -p porra26/settings
git mv porra26/settings.py porra26/settings/base.py
touch porra26/settings/__init__.py
```

- [ ] **Step 2: Reescribir `porra26/settings/base.py`**

```python
from pathlib import Path
import os
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent.parent
load_dotenv(BASE_DIR / ".env")

SECRET_KEY = os.getenv("DJANGO_SECRET_KEY", "dev-insecure-key")
DEBUG = False
ALLOWED_HOSTS: list[str] = []

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "competition",
    "pot",
    "stats",
    "core",
]

MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "accounts.middleware.ForcePasswordChangeMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "porra26.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "core.context_processors.app_context",
            ],
        },
    },
]

WSGI_APPLICATION = "porra26.wsgi.application"

AUTH_USER_MODEL = "accounts.User"

LANGUAGE_CODE = "es-es"
TIME_ZONE = "Europe/Madrid"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

LOGIN_URL = "/"
LOGIN_REDIRECT_URL = "/competicion/"
LOGOUT_REDIRECT_URL = "/"

SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = "Lax"
```

- [ ] **Step 3: Crear `porra26/settings/dev.py`**

```python
from .base import *  # noqa: F401,F403

DEBUG = True
ALLOWED_HOSTS = ["*"]
SECRET_KEY = "dev-insecure-key-only-for-local"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.sqlite3",
        "NAME": BASE_DIR / "db.sqlite3",  # noqa: F405
    }
}
```

- [ ] **Step 4: Crear `porra26/settings/test.py`**

```python
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

# acelera tests
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
```

- [ ] **Step 5: Crear `porra26/settings/prod.py`**

```python
import os
from .base import *  # noqa: F401,F403

DEBUG = False
SECRET_KEY = os.environ["DJANGO_SECRET_KEY"]
ALLOWED_HOSTS = os.environ["DJANGO_ALLOWED_HOSTS"].split(",")

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.mysql",
        "NAME": os.environ["MYSQL_NAME"],
        "USER": os.environ["MYSQL_USER"],
        "PASSWORD": os.environ["MYSQL_PASSWORD"],
        "HOST": os.environ["MYSQL_HOST"],
        "PORT": "3306",
        "OPTIONS": {"charset": "utf8mb4"},
    }
}

SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
SESSION_EXPIRE_AT_BROWSER_CLOSE = True

CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.db.DatabaseCache",
        "LOCATION": "porra26_cache",
    }
}
```

- [ ] **Step 6: Crear `.env.example`**

```
DJANGO_SECRET_KEY=replace-me
DJANGO_ALLOWED_HOSTS=porra26.pythonanywhere.com
MYSQL_NAME=user$porra26
MYSQL_USER=user
MYSQL_PASSWORD=replace-me
MYSQL_HOST=user.mysql.pythonanywhere-services.com
EMAIL_DOMAIN=edisa.com
```

- [ ] **Step 7: Configurar el módulo de settings por defecto**

Edit `manage.py` línea con `os.environ.setdefault`:

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "porra26.settings.dev")
```

Edit `porra26/wsgi.py` y `porra26/asgi.py` igualmente para usar `porra26.settings.prod` (lo dejamos así porque WSGI/ASGI se usan en producción):

```python
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "porra26.settings.prod")
```

- [ ] **Step 8: Verificar**

```bash
python manage.py check --settings=porra26.settings.dev
```

Esperado: `no issues`. Si Django falla diciendo que faltan apps (accounts, competition, pot, stats, core), es esperado — las creamos en la siguiente tarea.

- [ ] **Step 9: Commit**

```bash
git add porra26/settings/ .env.example manage.py porra26/wsgi.py porra26/asgi.py
git commit -m "chore: settings split base/dev/test/prod"
```

---

### Tarea 0.4: Crear apps por dominio

**Files:**
- Create: `accounts/` (django startapp)
- Create: `competition/`
- Create: `pot/`
- Create: `stats/`
- Create: `core/`

- [ ] **Step 1: Generar las 5 apps**

```bash
for app in accounts competition pot stats core; do
  python manage.py startapp $app --settings=porra26.settings.dev
done
```

- [ ] **Step 2: Crear placeholder de middleware referenciado en base.py**

Create `accounts/middleware.py`:

```python
class ForcePasswordChangeMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        # implementación real en tarea 3.5
        return self.get_response(request)
```

- [ ] **Step 3: Crear placeholder del context processor referenciado en base.py**

Create `core/context_processors.py`:

```python
def app_context(request):
    return {
        "app_version": "0.1.0",
    }
```

- [ ] **Step 4: Crear `core/__init__.py`** (ya creado por startapp, verificar)

- [ ] **Step 5: Verificar**

```bash
python manage.py check --settings=porra26.settings.dev
```

Esperado: `no issues`.

- [ ] **Step 6: Commit**

```bash
git add accounts competition pot stats core
git commit -m "chore: crear esqueleto de apps por dominio"
```

---

### Tarea 0.5: Estructura de carpetas estáticas y plantillas

**Files:**
- Create: `static/css/.gitkeep`
- Create: `static/js/.gitkeep`
- Create: `static/icons/.gitkeep`
- Create: `templates/.gitkeep`
- Create: `fixtures/.gitkeep`

- [ ] **Step 1: Crear directorios**

```bash
mkdir -p static/css static/js static/icons templates fixtures
touch static/css/.gitkeep static/js/.gitkeep static/icons/.gitkeep templates/.gitkeep fixtures/.gitkeep
```

- [ ] **Step 2: Copiar el CSS del prototipo**

```bash
cp design-reference/styles.css static/css/styles.css
```

- [ ] **Step 3: Verificar**

```bash
ls static/css/styles.css
```

Esperado: el fichero existe.

- [ ] **Step 4: Commit**

```bash
git add static templates fixtures
git commit -m "chore: estructura de static/, templates/, fixtures/ y copia del CSS del prototipo"
```

---

### Tarea 0.6: Pytest setup y smoke test

**Files:**
- Create: `conftest.py`
- Create: `tests/__init__.py`
- Create: `tests/test_smoke.py`

- [ ] **Step 1: Crear `conftest.py` en la raíz**

```python
import pytest


@pytest.fixture(autouse=True)
def _enable_db_for_tests(db):
    """Autoriza acceso a BD en todos los tests."""
    pass
```

- [ ] **Step 2: Crear `tests/__init__.py`** vacío y `tests/test_smoke.py`

```python
def test_django_setup_works():
    from django.conf import settings
    assert settings.AUTH_USER_MODEL == "accounts.User"
```

- [ ] **Step 3: Ejecutar pytest**

```bash
pytest tests/test_smoke.py -v
```

Esperado: PASS (puede salir warning sobre AUTH_USER_MODEL no aplicado todavía — se resuelve en Fase 1).

> Si falla por "no module named accounts" — ejecuta tras la tarea 1.1.

- [ ] **Step 4: Commit**

```bash
git add conftest.py tests/
git commit -m "test: pytest setup y smoke test"
```

---

## Fase 1 — Modelos de datos

### Tarea 1.1: Modelo `accounts.User`

**Files:**
- Modify: `accounts/models.py`
- Create: `accounts/managers.py`
- Test: `accounts/tests/test_user_model.py`

- [ ] **Step 1: Escribir test fallido `accounts/tests/test_user_model.py`**

```python
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
def test_user_uses_email_as_username_field():
    assert User.USERNAME_FIELD == "email"


@pytest.mark.django_db
def test_create_user_persists():
    u = User.objects.create_user(email="a@edisa.com", password="pw", name="Ana")
    assert u.pk is not None
    assert u.email == "a@edisa.com"
    assert u.check_password("pw")


@pytest.mark.django_db
def test_create_user_defaults_role_to_jugador():
    u = User.objects.create_user(email="a@edisa.com", password="pw", name="Ana")
    assert u.role == "jugador"
    assert u.must_change_password is True
    assert u.is_active is True


@pytest.mark.django_db
def test_create_superuser_is_gestor():
    u = User.objects.create_superuser(email="g@edisa.com", password="pw", name="G")
    assert u.is_staff and u.is_superuser
    assert u.role == "gestor"
```

Crear directorio: `mkdir -p accounts/tests && touch accounts/tests/__init__.py`

- [ ] **Step 2: Ejecutar test (debe fallar)**

```bash
pytest accounts/tests/test_user_model.py -v
```

Esperado: FAIL (model placeholder vacío).

- [ ] **Step 3: Crear `accounts/managers.py`**

```python
from django.contrib.auth.models import BaseUserManager


class UserManager(BaseUserManager):
    use_in_migrations = True

    def _create_user(self, email, password, **extra):
        if not email:
            raise ValueError("Email obligatorio")
        email = self.normalize_email(email).lower()
        user = self.model(email=email, **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_user(self, email, password=None, **extra):
        extra.setdefault("role", "jugador")
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("role", "gestor")
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("must_change_password", False)
        return self._create_user(email, password, **extra)
```

- [ ] **Step 4: Sustituir `accounts/models.py`**

```python
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    ROLE_CHOICES = [("jugador", "Jugador"), ("gestor", "Gestor")]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    dept = models.CharField(max_length=80, blank=True)
    role = models.CharField(max_length=10, choices=ROLE_CHOICES, default="jugador")
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    must_change_password = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = ["name"]

    objects = UserManager()

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return f"{self.name} <{self.email}>"

    @property
    def initials(self) -> str:
        parts = [p for p in self.name.split() if p]
        if not parts:
            return "?"
        if len(parts) == 1:
            return parts[0][:2].upper()
        return (parts[0][0] + parts[-1][0]).upper()
```

- [ ] **Step 5: Generar migración inicial**

```bash
python manage.py makemigrations accounts --settings=porra26.settings.dev
```

Esperado: crea `accounts/migrations/0001_initial.py`.

- [ ] **Step 6: Ejecutar tests (deben pasar)**

```bash
pytest accounts/tests/test_user_model.py -v
```

Esperado: 4 PASS.

- [ ] **Step 7: Commit**

```bash
git add accounts/
git commit -m "feat(accounts): User custom con email como USERNAME_FIELD"
```

---

### Tarea 1.2: Validador de dominio de email

**Files:**
- Create: `accounts/validators.py`
- Test: `accounts/tests/test_validators.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from django.core.exceptions import ValidationError

from accounts.validators import validate_email_domain


def test_validate_email_domain_accepts_allowed(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    validate_email_domain("a@edisa.com")  # no raise


def test_validate_email_domain_rejects_other(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    with pytest.raises(ValidationError):
        validate_email_domain("a@gmail.com")


def test_validate_email_domain_case_insensitive(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    validate_email_domain("A@EDISA.COM")
```

- [ ] **Step 2: Ejecutar (FAIL: módulo no existe)**

```bash
pytest accounts/tests/test_validators.py -v
```

- [ ] **Step 3: Implementar `accounts/validators.py`**

```python
import os
from django.core.exceptions import ValidationError


def _allowed_domains() -> list[str]:
    """Lee dominios permitidos. En v1, desde env; en v2, desde PotSettings."""
    raw = os.getenv("EMAIL_DOMAIN", "")
    return [d.strip().lower() for d in raw.split(",") if d.strip()]


def validate_email_domain(email: str) -> None:
    allowed = _allowed_domains()
    if not allowed:
        return  # sin restricción si no se configura
    domain = email.lower().rsplit("@", 1)[-1]
    if domain not in allowed:
        raise ValidationError(
            f"El correo debe pertenecer a uno de los dominios permitidos: {', '.join(allowed)}."
        )
```

- [ ] **Step 4: Tests pasan**

```bash
pytest accounts/tests/test_validators.py -v
```

Esperado: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add accounts/validators.py accounts/tests/test_validators.py
git commit -m "feat(accounts): validador de dominio de email corporativo"
```

---

### Tarea 1.3: Modelo `accounts.AuditLog`

**Files:**
- Modify: `accounts/models.py`
- Test: `accounts/tests/test_audit_log.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.models import AuditLog, User


@pytest.mark.django_db
def test_audit_log_can_be_created():
    actor = User.objects.create_user(email="g@edisa.com", password="x", name="G", role="gestor")
    entry = AuditLog.objects.create(
        actor=actor, action="password_reset",
        target_type="user", target_id="42", payload={"by": "g@edisa.com"},
    )
    assert entry.pk
    assert entry.created_at is not None
    assert entry.payload == {"by": "g@edisa.com"}
```

- [ ] **Step 2: Añadir `AuditLog` a `accounts/models.py`**

```python
class AuditLog(models.Model):
    actor = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, related_name="audit_actions")
    action = models.CharField(max_length=40)
    target_type = models.CharField(max_length=20)
    target_id = models.CharField(max_length=64)
    payload = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["-created_at"]
        indexes = [models.Index(fields=["action", "-created_at"])]

    def __str__(self):
        return f"{self.action} on {self.target_type}#{self.target_id} by {self.actor_id}"
```

- [ ] **Step 3: Migración**

```bash
python manage.py makemigrations accounts --settings=porra26.settings.dev
```

- [ ] **Step 4: Tests pasan**

```bash
pytest accounts/tests/test_audit_log.py -v
```

- [ ] **Step 5: Commit**

```bash
git add accounts/
git commit -m "feat(accounts): modelo AuditLog para trazabilidad del gestor"
```

---

### Tarea 1.4: Modelo `competition.Team`

**Files:**
- Modify: `competition/models.py`
- Test: `competition/tests/test_team.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from competition.models import Team


@pytest.mark.django_db
def test_team_pk_is_code():
    t = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    assert t.pk == "ESP"
    assert str(t) == "España"
```

`mkdir -p competition/tests && touch competition/tests/__init__.py`

- [ ] **Step 2: Implementar en `competition/models.py`**

```python
from django.db import models


class Team(models.Model):
    code = models.CharField(primary_key=True, max_length=3)
    name = models.CharField(max_length=80)
    flag = models.CharField(max_length=8)

    class Meta:
        ordering = ["name"]

    def __str__(self):
        return self.name
```

- [ ] **Step 3: Migración + test**

```bash
python manage.py makemigrations competition --settings=porra26.settings.dev
pytest competition/tests/test_team.py -v
```

- [ ] **Step 4: Commit**

```bash
git add competition/
git commit -m "feat(competition): modelo Team"
```

---

### Tarea 1.5: Modelo `competition.Round`

**Files:**
- Modify: `competition/models.py`
- Test: `competition/tests/test_round.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from competition.models import Round


@pytest.mark.django_db
def test_round_ordering_by_order_field():
    Round.objects.create(id="qf", label="Cuartos", short="QF", points=10, order=4)
    Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    ids = list(Round.objects.values_list("id", flat=True))
    assert ids == ["groups", "qf"]
```

- [ ] **Step 2: Añadir Round a `competition/models.py`**

```python
class Round(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    label = models.CharField(max_length=40)
    short = models.CharField(max_length=10)
    points = models.PositiveSmallIntegerField()
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label
```

- [ ] **Step 3: Migración + test**

```bash
python manage.py makemigrations competition --settings=porra26.settings.dev
pytest competition/tests/test_round.py -v
```

- [ ] **Step 4: Commit**

```bash
git add competition/
git commit -m "feat(competition): modelo Round"
```

---

### Tarea 1.6: Modelo `competition.Match` con property `status`

**Files:**
- Modify: `competition/models.py`
- Test: `competition/tests/test_match.py`

- [ ] **Step 1: Test fallido**

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from competition.models import Match, Round, Team


@pytest.fixture
def setup_match(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    esp = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    arg = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    return grp, esp, arg


def _match(round, home, away, kickoff, **kw):
    return Match.objects.create(round=round, group="A", matchday=1, home=home, away=away, kickoff=kickoff, **kw)


@pytest.mark.django_db
def test_status_open_when_far_from_kickoff(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() + timedelta(hours=10))
        assert m.status == "open"


@pytest.mark.django_db
def test_status_closing_within_two_hours(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() + timedelta(hours=3))
        # close_at = kickoff - 2h = +1h; closing si close_at - now <= 2h
        assert m.status == "closing"


@pytest.mark.django_db
def test_status_closed_after_close_before_kickoff(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() + timedelta(minutes=30))
        assert m.status == "closed"


@pytest.mark.django_db
def test_status_live_after_kickoff_without_result(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() - timedelta(minutes=10))
        assert m.status == "live"


@pytest.mark.django_db
def test_status_done_when_result_set(setup_match):
    grp, esp, arg = setup_match
    with freeze_time("2026-06-12 12:00:00", tz_offset=0):
        m = _match(grp, esp, arg, timezone.now() - timedelta(hours=3), result_home=2, result_away=1)
        assert m.status == "done"
```

- [ ] **Step 2: Añadir Match a `competition/models.py`**

```python
from datetime import timedelta
from django.utils import timezone


class Match(models.Model):
    round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="matches")
    group = models.CharField(max_length=20)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    home = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="home_matches")
    away = models.ForeignKey(Team, on_delete=models.PROTECT, related_name="away_matches")
    kickoff = models.DateTimeField()
    result_home = models.PositiveSmallIntegerField(null=True, blank=True)
    result_away = models.PositiveSmallIntegerField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["kickoff"]
        indexes = [
            models.Index(fields=["round", "matchday", "kickoff"]),
            models.Index(fields=["finished_at"]),
        ]

    def __str__(self):
        return f"{self.home_id} vs {self.away_id} @ {self.kickoff:%Y-%m-%d %H:%M}"

    @property
    def has_result(self) -> bool:
        return self.result_home is not None and self.result_away is not None

    @property
    def status(self) -> str:
        now = timezone.now()
        if self.has_result:
            return "done"
        close_at = self.kickoff - timedelta(hours=2)
        if now >= self.kickoff:
            return "live"
        if now >= close_at:
            return "closed"
        if close_at - now <= timedelta(hours=2):
            return "closing"
        return "open"

    @property
    def editable(self) -> bool:
        return self.status in ("open", "closing")
```

- [ ] **Step 3: Migración + tests**

```bash
python manage.py makemigrations competition --settings=porra26.settings.dev
pytest competition/tests/test_match.py -v
```

Esperado: 5 PASS.

- [ ] **Step 4: Commit**

```bash
git add competition/
git commit -m "feat(competition): modelo Match con estado derivado"
```

---

### Tarea 1.7: Modelo `competition.Prediction`

**Files:**
- Modify: `competition/models.py`
- Test: `competition/tests/test_prediction.py`

- [ ] **Step 1: Test fallido**

```python
from datetime import timedelta

import pytest
from django.db.utils import IntegrityError
from django.utils import timezone

from accounts.models import User
from competition.models import Match, Prediction, Round, Team


@pytest.fixture
def setup(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    esp = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    arg = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    m = Match.objects.create(round=grp, group="A", matchday=1, home=esp, away=arg,
                              kickoff=timezone.now() + timedelta(days=1))
    u = User.objects.create_user(email="a@edisa.com", password="x", name="Ana")
    return u, m


@pytest.mark.django_db
def test_prediction_create(setup):
    u, m = setup
    p = Prediction.objects.create(player=u, match=m, home=2, away=1)
    assert p.earned is None


@pytest.mark.django_db
def test_prediction_unique_player_match(setup):
    u, m = setup
    Prediction.objects.create(player=u, match=m, home=2, away=1)
    with pytest.raises(IntegrityError):
        Prediction.objects.create(player=u, match=m, home=0, away=0)
```

- [ ] **Step 2: Añadir Prediction**

```python
class Prediction(models.Model):
    player = models.ForeignKey("accounts.User", on_delete=models.CASCADE, related_name="predictions")
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name="predictions")
    home = models.PositiveSmallIntegerField()
    away = models.PositiveSmallIntegerField()
    earned = models.PositiveSmallIntegerField(null=True, blank=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(fields=["player", "match"], name="uniq_pred_per_player_match"),
        ]
        indexes = [models.Index(fields=["match", "player"])]
```

- [ ] **Step 3: Migración + tests**

```bash
python manage.py makemigrations competition --settings=porra26.settings.dev
pytest competition/tests/test_prediction.py -v
```

- [ ] **Step 4: Commit**

```bash
git add competition/
git commit -m "feat(competition): modelo Prediction con unique (player, match)"
```

---

### Tarea 1.8: Modelo `pot.PotSettings` (singleton)

**Files:**
- Modify: `pot/models.py`
- Test: `pot/tests/test_pot_settings.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from pot.models import PotSettings


@pytest.mark.django_db
def test_load_creates_singleton():
    s = PotSettings.load()
    assert s.pk == 1
    assert s.per_player == 10


@pytest.mark.django_db
def test_load_returns_existing():
    s1 = PotSettings.load()
    s1.per_player = 15
    s1.save()
    s2 = PotSettings.load()
    assert s2.per_player == 15
```

`mkdir -p pot/tests && touch pot/tests/__init__.py`

- [ ] **Step 2: Implementar `pot/models.py`**

```python
from decimal import Decimal
from django.db import models


class PotSettings(models.Model):
    per_player = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("10.00"))
    allowed_email_domains = models.JSONField(default=list, blank=True)

    class Meta:
        verbose_name = "Pot settings"

    def save(self, *args, **kwargs):
        self.pk = 1
        super().save(*args, **kwargs)

    @classmethod
    def load(cls):
        obj, _ = cls.objects.get_or_create(pk=1)
        return obj
```

- [ ] **Step 3: Migración + tests**

```bash
python manage.py makemigrations pot --settings=porra26.settings.dev
pytest pot/tests/test_pot_settings.py -v
```

- [ ] **Step 4: Commit**

```bash
git add pot/
git commit -m "feat(pot): PotSettings como singleton (pk=1)"
```

---

### Tarea 1.9: Modelos `pot.Prize` y `pot.Payment`

**Files:**
- Modify: `pot/models.py`
- Test: `pot/tests/test_prize_payment.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.models import User
from competition.models import Round
from pot.models import Payment, Prize


@pytest.mark.django_db
def test_prize_global_top1():
    p = Prize.objects.create(scope="global", position=1, amount=200, label="1er premio")
    assert p.scope == "global"
    assert p.position == 1


@pytest.mark.django_db
def test_prize_matchday():
    p = Prize.objects.create(scope="matchday", matchday=2, amount=20, label="Jornada 2")
    assert p.matchday == 2


@pytest.mark.django_db
def test_prize_round_only_for_ko():
    r = Round.objects.create(id="qf", label="Cuartos", short="QF", points=10, order=4)
    p = Prize.objects.create(scope="round", round=r, amount=30, label="Cuartos")
    assert p.round_id == "qf"


@pytest.mark.django_db
def test_payment_default_unpaid():
    u = User.objects.create_user(email="a@edisa.com", password="x", name="A")
    pay = Payment.objects.create(player=u)
    assert pay.paid is False
    assert pay.paid_at is None
```

- [ ] **Step 2: Añadir a `pot/models.py`**

```python
class Prize(models.Model):
    SCOPE_CHOICES = [("global", "Global"), ("matchday", "Jornada"), ("round", "Ronda KO")]

    scope = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    position = models.PositiveSmallIntegerField(null=True, blank=True)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    round = models.ForeignKey("competition.Round", on_delete=models.PROTECT,
                              null=True, blank=True, related_name="prizes")
    amount = models.DecimalField(max_digits=8, decimal_places=2, default=0)
    label = models.CharField(max_length=60)

    class Meta:
        ordering = ["scope", "position", "matchday", "round_id"]


class Payment(models.Model):
    player = models.OneToOneField("accounts.User", on_delete=models.CASCADE, related_name="payment")
    paid = models.BooleanField(default=False)
    paid_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 3: Migración + tests**

```bash
python manage.py makemigrations pot --settings=porra26.settings.dev
pytest pot/tests/test_prize_payment.py -v
```

- [ ] **Step 4: Commit**

```bash
git add pot/
git commit -m "feat(pot): modelos Prize (global/matchday/round) y Payment"
```

---

### Tarea 1.10: Factories de test (factory-boy)

**Files:**
- Create: `accounts/tests/factories.py`
- Create: `competition/tests/factories.py`
- Create: `pot/tests/factories.py`

- [ ] **Step 1: `accounts/tests/factories.py`**

```python
import factory
from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@edisa.com")
    name = factory.Faker("name", locale="es_ES")
    dept = "Desarrollo"
    role = "jugador"
    must_change_password = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        password = kwargs.pop("password", "test-password")
        user = model_class.objects.create_user(password=password, **kwargs)
        return user


class GestorFactory(UserFactory):
    role = "gestor"
```

- [ ] **Step 2: `competition/tests/factories.py`**

```python
from datetime import timedelta

import factory
from django.utils import timezone

from competition.models import Match, Prediction, Round, Team


class RoundFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Round
        django_get_or_create = ("id",)

    id = "groups"
    label = "Fase de grupos"
    short = "GRP"
    points = 3
    order = 1


class TeamFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Team
        django_get_or_create = ("code",)

    code = factory.Sequence(lambda n: f"T{n:02d}")
    name = factory.Sequence(lambda n: f"Equipo {n}")
    flag = "🏳️"


class MatchFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Match

    round = factory.SubFactory(RoundFactory)
    group = "A"
    matchday = 1
    home = factory.SubFactory(TeamFactory)
    away = factory.SubFactory(TeamFactory)
    kickoff = factory.LazyFunction(lambda: timezone.now() + timedelta(days=1))


class PredictionFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prediction

    player = factory.SubFactory("accounts.tests.factories.UserFactory")
    match = factory.SubFactory(MatchFactory)
    home = 1
    away = 0
```

- [ ] **Step 3: `pot/tests/factories.py`**

```python
import factory
from pot.models import Payment, Prize


class PrizeFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Prize

    scope = "global"
    position = 1
    amount = 200
    label = "1er premio"


class PaymentFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Payment

    player = factory.SubFactory("accounts.tests.factories.UserFactory")
    paid = False
```

- [ ] **Step 4: Smoke test**

```bash
pytest -v --collect-only | head -50
```

Esperado: las factories se importan sin error.

- [ ] **Step 5: Commit**

```bash
git add accounts/tests/factories.py competition/tests/factories.py pot/tests/factories.py
git commit -m "test: factories de factory-boy para User/Team/Round/Match/Prediction/Prize/Payment"
```

---

### Tarea 1.11: Fixtures de rondas y data migration de premios

**Files:**
- Create: `fixtures/rounds.json`
- Create: `pot/migrations/0002_seed_prizes.py` (data migration)

- [ ] **Step 1: Crear `fixtures/rounds.json`**

```json
[
  {"model": "competition.round", "pk": "groups", "fields": {"label": "Fase de grupos", "short": "GRP", "points": 3, "order": 1}},
  {"model": "competition.round", "pk": "r32",    "fields": {"label": "Dieciseisavos", "short": "R32", "points": 5, "order": 2}},
  {"model": "competition.round", "pk": "r16",    "fields": {"label": "Octavos",       "short": "R16", "points": 7, "order": 3}},
  {"model": "competition.round", "pk": "qf",     "fields": {"label": "Cuartos",       "short": "QF",  "points": 10, "order": 4}},
  {"model": "competition.round", "pk": "sf",     "fields": {"label": "Semifinales",   "short": "SF",  "points": 15, "order": 5}},
  {"model": "competition.round", "pk": "final",  "fields": {"label": "Final",         "short": "FIN", "points": 25, "order": 6}}
]
```

- [ ] **Step 2: Generar migración vacía para pot**

```bash
python manage.py makemigrations pot --empty --name seed_prizes --settings=porra26.settings.dev
```

- [ ] **Step 3: Editar la migración generada**

```python
from django.db import migrations
from decimal import Decimal


def seed_prizes(apps, schema_editor):
    Round = apps.get_model("competition", "Round")
    Prize = apps.get_model("pot", "Prize")
    PotSettings = apps.get_model("pot", "PotSettings")

    PotSettings.objects.get_or_create(pk=1, defaults={"per_player": Decimal("10.00")})

    # 3 globales
    for pos, label in [(1, "1er premio"), (2, "2º premio"), (3, "3er premio")]:
        Prize.objects.get_or_create(scope="global", position=pos,
                                     defaults={"amount": 0, "label": label})

    # 3 jornadas de grupos
    for md in (1, 2, 3):
        Prize.objects.get_or_create(scope="matchday", matchday=md,
                                     defaults={"amount": 0, "label": f"Jornada {md} (Grupos)"})

    # 3 rondas KO (r32, r16, qf). NO semis ni final.
    for rid, label in [("r32", "Dieciseisavos"), ("r16", "Octavos"), ("qf", "Cuartos")]:
        try:
            r = Round.objects.get(pk=rid)
        except Round.DoesNotExist:
            continue
        Prize.objects.get_or_create(scope="round", round=r,
                                     defaults={"amount": 0, "label": f"Ronda · {label}"})


def reverse_seed(apps, schema_editor):
    apps.get_model("pot", "Prize").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pot", "0001_initial"),
        ("competition", "0001_initial"),  # ajustar al nombre real
    ]
    operations = [migrations.RunPython(seed_prizes, reverse_seed)]
```

> Ajusta la dependencia a la migración real de `competition` (mira `competition/migrations/`).

- [ ] **Step 4: Ejecutar migraciones contra dev DB**

```bash
python manage.py migrate --settings=porra26.settings.dev
python manage.py loaddata fixtures/rounds.json --settings=porra26.settings.dev
python manage.py migrate --settings=porra26.settings.dev  # re-ejecuta la data migration con rounds presentes
```

> Si la migración de premios se ejecutó antes de cargar rondas, los Prizes de scope=round no se crearon. Para forzar: borrar `db.sqlite3` y empezar de cero.

- [ ] **Step 5: Test de comprobación**

```python
# pot/tests/test_seed.py
import pytest
from django.core.management import call_command
from pot.models import Prize


@pytest.mark.django_db
def test_seed_creates_nine_prizes_after_loaddata():
    call_command("loaddata", "fixtures/rounds.json")
    call_command("migrate", "pot", verbosity=0)
    assert Prize.objects.count() >= 9
```

```bash
pytest pot/tests/test_seed.py -v
```

- [ ] **Step 6: Commit**

```bash
git add fixtures/rounds.json pot/migrations/ pot/tests/test_seed.py
git commit -m "feat(pot): data migration con 9 premios iniciales y seed de rondas"
```

---

## Fase 2 — Servicios (lógica de negocio pura)

### Tarea 2.1: `competition.services.score`

**Files:**
- Create: `competition/services/__init__.py`
- Create: `competition/services/score.py`
- Test: `competition/tests/test_score.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from competition.services.score import score
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)


def _match_with_result(groups_round, rh, ra):
    return MatchFactory(round=groups_round, result_home=rh, result_away=ra)


@pytest.mark.django_db
@pytest.mark.parametrize("ph,pa,rh,ra,expected", [
    (2, 1, 2, 1, 3),   # exacto en grupos
    (3, 1, 2, 1, 1),   # signo correcto (victoria local)
    (0, 0, 1, 1, 1),   # signo correcto (empate)
    (1, 2, 0, 3, 1),   # signo correcto (visitante)
    (2, 0, 0, 1, 0),   # fallo
    (1, 1, 2, 0, 0),   # fallo (empate vs local)
])
def test_score_groups(groups_round, ph, pa, rh, ra, expected):
    m = _match_with_result(groups_round, rh, ra)
    pred = type("P", (), {"home": ph, "away": pa})()
    assert score(pred, m) == expected


@pytest.mark.django_db
def test_score_uses_round_points():
    final = RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)
    m = MatchFactory(round=final, result_home=1, result_away=0)
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) == 25


@pytest.mark.django_db
def test_score_returns_none_for_unresolved(groups_round):
    m = MatchFactory(round=groups_round, result_home=None, result_away=None)
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) is None
```

- [ ] **Step 2: Implementar `competition/services/__init__.py`** (vacío) y `competition/services/score.py`

```python
from __future__ import annotations


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def score(pred, match) -> int | None:
    """Puntos ganados por un pronóstico tras resolver el partido.

    Reglas:
    - Marcador exacto -> round.points
    - Mismo signo (1X2) -> 1
    - Otro caso -> 0
    Si el partido no tiene resultado -> None.
    """
    if match.result_home is None or match.result_away is None:
        return None
    if pred.home == match.result_home and pred.away == match.result_away:
        return match.round.points
    if _sign(pred.home - pred.away) == _sign(match.result_home - match.result_away):
        return 1
    return 0
```

- [ ] **Step 3: Tests pasan**

```bash
pytest competition/tests/test_score.py -v
```

Esperado: 8 PASS.

- [ ] **Step 4: Commit**

```bash
git add competition/services/ competition/tests/test_score.py
git commit -m "feat(competition): servicio de puntuación de pronósticos"
```

---

### Tarea 2.2: `competition.services.resolve_match`

**Files:**
- Create: `competition/services/resolve.py`
- Test: `competition/tests/test_resolve.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.tests.factories import UserFactory, GestorFactory
from competition.models import Prediction
from competition.services.resolve import resolve_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_resolve_match_persists_result_and_earned():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    p_exact = PredictionFactory(match=m, home=2, away=1, player=UserFactory())
    p_signo = PredictionFactory(match=m, home=3, away=1, player=UserFactory())
    p_fail = PredictionFactory(match=m, home=0, away=1, player=UserFactory())
    actor = GestorFactory()

    resolve_match(m, home=2, away=1, actor=actor)

    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (2, 1)
    assert m.finished_at is not None

    p_exact.refresh_from_db(); assert p_exact.earned == 3
    p_signo.refresh_from_db(); assert p_signo.earned == 1
    p_fail.refresh_from_db();  assert p_fail.earned == 0


@pytest.mark.django_db
def test_resolve_match_creates_audit_log():
    from accounts.models import AuditLog
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    g = GestorFactory()
    resolve_match(m, home=1, away=0, actor=g)
    log = AuditLog.objects.get(action="match_resolved")
    assert log.actor_id == g.id
    assert log.target_id == str(m.id)
```

- [ ] **Step 2: Implementar `competition/services/resolve.py`**

```python
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import Match, Prediction
from competition.services.score import score


@transaction.atomic
def resolve_match(match: Match, *, home: int, away: int, actor) -> None:
    """Confirma el resultado oficial y recalcula `earned` de los pronósticos."""
    match.result_home = home
    match.result_away = away
    match.finished_at = timezone.now()
    match.save(update_fields=["result_home", "result_away", "finished_at"])

    preds = list(Prediction.objects.select_for_update().filter(match=match).select_related("match__round"))
    for p in preds:
        p.earned = score(p, match)
    if preds:
        Prediction.objects.bulk_update(preds, ["earned"])

    AuditLog.objects.create(
        actor=actor,
        action="match_resolved",
        target_type="match",
        target_id=str(match.id),
        payload={"home": home, "away": away},
    )
```

- [ ] **Step 3: Tests pasan**

```bash
pytest competition/tests/test_resolve.py -v
```

- [ ] **Step 4: Commit**

```bash
git add competition/services/resolve.py competition/tests/test_resolve.py
git commit -m "feat(competition): resolve_match atómico con recálculo de earned"
```

---

### Tarea 2.3: `competition.services.standings`

**Files:**
- Create: `competition/services/standings.py`
- Test: `competition/tests/test_standings.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.tests.factories import UserFactory
from competition.services.standings import standings
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_standings_orders_by_points():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="ana@e.com")
    luis = UserFactory(name="Luis", email="luis@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, result_home=2, result_away=2)

    PredictionFactory(player=ana, match=m1, home=1, away=0, earned=3)   # exacto
    PredictionFactory(player=ana, match=m2, home=0, away=0, earned=1)   # signo
    PredictionFactory(player=luis, match=m1, home=1, away=2, earned=0)
    PredictionFactory(player=luis, match=m2, home=2, away=2, earned=3)

    s = standings()
    pts_by_name = [(r.name, r.pts) for r in s]
    assert pts_by_name[0] == ("Ana", 4)
    assert pts_by_name[1] == ("Luis", 3)


@pytest.mark.django_db
def test_standings_tiebreak_by_exact_then_hits_then_name():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    z = UserFactory(name="Zoe", email="z@e.com")
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, result_home=0, result_away=0)
    # todos suman 4 pts; desempate por exactos -> hits -> nombre
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3); PredictionFactory(player=a, match=m2, home=2, away=2, earned=1)
    PredictionFactory(player=b, match=m1, home=2, away=0, earned=1); PredictionFactory(player=b, match=m2, home=0, away=0, earned=3)
    PredictionFactory(player=z, match=m1, home=1, away=0, earned=3); PredictionFactory(player=z, match=m2, home=0, away=0, earned=3)

    s = standings()
    names = [r.name for r in s]
    # Zoe (2 exactos) > Ana (1 exacto) / Borja (1 exacto) -> alfabético
    assert names[:3] == ["Zoe", "Ana", "Borja"]


@pytest.mark.django_db
def test_standings_excludes_inactive_users():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    UserFactory(name="Ina", email="i@e.com", is_active=False)
    UserFactory(name="Act", email="a@e.com", is_active=True)
    s = standings()
    assert [r.name for r in s] == ["Act"]
```

- [ ] **Step 2: Implementar `competition/services/standings.py`**

```python
from dataclasses import dataclass

from django.db.models import Case, Count, IntegerField, Sum, When, F
from accounts.models import User
from competition.models import Prediction


@dataclass
class StandingRow:
    position: int
    player_id: int
    name: str
    email: str
    pts: int
    hits: int
    exact_hits: int

    @property
    def is_user(self):  # placeholder; el cliente la rellena
        return False


def standings() -> list[StandingRow]:
    qs = (
        User.objects.filter(is_active=True)
        .annotate(
            pts=Sum("predictions__earned"),
            hits=Count("predictions", filter=~Case(When(predictions__earned=None, then=0)) ),  # placeholder
        )
    )
    # Aproximación más legible: hacemos un ORM agrupado por user
    rows = (
        Prediction.objects.filter(player__is_active=True, earned__isnull=False)
        .values("player_id", "player__name", "player__email")
        .annotate(
            pts=Sum("earned"),
            hits=Count("id", filter=Case(When(earned__gt=0, then=1), output_field=IntegerField())),
            exact_hits=Count("id", filter=Case(When(earned=F("match__round__points"), then=1), output_field=IntegerField())),
        )
    )
    # Añadir activos sin pronósticos resueltos para que aparezcan con 0 pts
    seen = {r["player_id"] for r in rows}
    extras = [
        {"player_id": u.id, "player__name": u.name, "player__email": u.email,
         "pts": 0, "hits": 0, "exact_hits": 0}
        for u in User.objects.filter(is_active=True).exclude(id__in=seen)
    ]
    merged = list(rows) + extras

    merged.sort(key=lambda r: (-(r["pts"] or 0), -r["exact_hits"], -r["hits"], r["player__name"].lower()))

    out = []
    for i, r in enumerate(merged, start=1):
        out.append(StandingRow(
            position=i,
            player_id=r["player_id"],
            name=r["player__name"],
            email=r["player__email"],
            pts=int(r["pts"] or 0),
            hits=int(r["hits"]),
            exact_hits=int(r["exact_hits"]),
        ))
    return out
```

- [ ] **Step 3: Tests pasan**

```bash
pytest competition/tests/test_standings.py -v
```

- [ ] **Step 4: Commit**

```bash
git add competition/services/standings.py competition/tests/test_standings.py
git commit -m "feat(competition): standings con desempate exactos→aciertos→nombre"
```

---

### Tarea 2.4: `competition.services.streak`

**Files:**
- Create: `competition/services/streak.py`
- Test: `competition/tests/test_streak.py`

- [ ] **Step 1: Test fallido**

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from accounts.tests.factories import UserFactory
from competition.services.streak import streak
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_streak_counts_consecutive_hits_from_latest():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    u = UserFactory()
    base = timezone.now()
    for i, earned in enumerate([0, 1, 3, 1, 3]):   # más viejo a más nuevo
        m = MatchFactory(round=groups, kickoff=base + timedelta(hours=i),
                          result_home=1, result_away=0)
        PredictionFactory(player=u, match=m, earned=earned)
    assert streak(u.id) == 4   # los 4 últimos > 0


@pytest.mark.django_db
def test_streak_zero_if_latest_is_zero():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    u = UserFactory()
    base = timezone.now()
    for i, earned in enumerate([3, 1, 0]):
        m = MatchFactory(round=groups, kickoff=base + timedelta(hours=i),
                          result_home=1, result_away=0)
        PredictionFactory(player=u, match=m, earned=earned)
    assert streak(u.id) == 0


@pytest.mark.django_db
def test_streak_zero_if_no_resolved_predictions():
    u = UserFactory()
    assert streak(u.id) == 0
```

- [ ] **Step 2: Implementar**

```python
from competition.models import Prediction


def streak(player_id: int) -> int:
    rows = (
        Prediction.objects.filter(player_id=player_id, earned__isnull=False)
        .order_by("-match__kickoff")
        .values_list("earned", flat=True)
    )
    n = 0
    for e in rows:
        if e and e > 0:
            n += 1
        else:
            break
    return n
```

- [ ] **Step 3: Tests pasan + Commit**

```bash
pytest competition/tests/test_streak.py -v
git add competition/services/streak.py competition/tests/test_streak.py
git commit -m "feat(competition): cálculo de racha de aciertos"
```

---

### Tarea 2.5: `pot.services.prizes` (ganadores por jornada/ronda)

**Files:**
- Create: `pot/services/__init__.py`
- Create: `pot/services/prizes.py`
- Test: `pot/tests/test_prizes.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.services.prizes import matchday_winners, WinnerResult


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_matchday_pending_if_any_match_unresolved(groups_round):
    MatchFactory(round=groups_round, matchday=1, result_home=None, result_away=None)
    MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    res = matchday_winners(("matchday", 1))
    assert res.status == "pending"


@pytest.mark.django_db
def test_matchday_single_winner(groups_round):
    a = UserFactory(name="A"); b = UserFactory(name="B")
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=a, match=m2, earned=1)
    PredictionFactory(player=b, match=m1, earned=1)
    PredictionFactory(player=b, match=m2, earned=0)
    res = matchday_winners(("matchday", 1))
    assert res.status == "resolved"
    assert [w.id for w in res.winners] == [a.id]


@pytest.mark.django_db
def test_matchday_tie_splits_prize(groups_round):
    a = UserFactory(name="A"); b = UserFactory(name="B")
    m1 = MatchFactory(round=groups_round, matchday=2, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=b, match=m1, earned=3)
    res = matchday_winners(("matchday", 2))
    assert res.status == "resolved"
    assert sorted(w.id for w in res.winners) == sorted([a.id, b.id])
    assert res.tied is True


@pytest.mark.django_db
def test_matchday_desierto_when_nobody_scored(groups_round):
    UserFactory()
    MatchFactory(round=groups_round, matchday=3, result_home=1, result_away=0)
    res = matchday_winners(("matchday", 3))
    assert res.status == "desierto"
```

- [ ] **Step 2: Implementar `pot/services/prizes.py`**

```python
from dataclasses import dataclass, field
from decimal import Decimal

from django.db.models import Sum
from competition.models import Match, Prediction


@dataclass
class WinnerResult:
    status: str                 # pending | resolved | desierto
    winners: list = field(default_factory=list)
    points: int = 0
    tied: bool = False
    share: Decimal = Decimal("0")


def _matches_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return Match.objects.filter(round_id="groups", matchday=value)
    if kind == "round":
        return Match.objects.filter(round_id=value)
    if kind == "global":
        return Match.objects.all()
    raise ValueError(f"unknown scope: {kind}")


def matchday_winners(scope_key) -> WinnerResult:
    matches = list(_matches_for_scope(scope_key))
    if not matches:
        return WinnerResult(status="pending")
    if any(m.result_home is None for m in matches):
        return WinnerResult(status="pending")

    agg = (
        Prediction.objects.filter(match__in=matches, player__is_active=True)
        .values("player_id", "player__name")
        .annotate(p=Sum("earned"))
        .order_by("-p")
    )
    rows = [r for r in agg if (r["p"] or 0) > 0]
    if not rows:
        return WinnerResult(status="desierto")

    top = rows[0]["p"]
    winners_raw = [r for r in rows if r["p"] == top]

    from accounts.models import User
    winners = list(User.objects.filter(id__in=[w["player_id"] for w in winners_raw]))
    return WinnerResult(status="resolved", winners=winners, points=int(top), tied=len(winners) > 1)
```

- [ ] **Step 3: Tests pasan + commit**

```bash
pytest pot/tests/test_prizes.py -v
git add pot/services/ pot/tests/test_prizes.py
git commit -m "feat(pot): cálculo de ganadores de jornada/ronda con empate y desierto"
```

---

### Tarea 2.6: `stats.services.history` (gráfico de evolución)

**Files:**
- Create: `stats/services/__init__.py`
- Create: `stats/services/history.py`
- Test: `stats/tests/test_history.py`

- [ ] **Step 1: Test fallido**

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.history import per_player_history


@pytest.mark.django_db
def test_history_increments_per_resolved_match():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="A"); b = UserFactory(name="B")
    t0 = timezone.now()
    m1 = MatchFactory(round=grp, kickoff=t0, result_home=1, result_away=0, finished_at=t0)
    m2 = MatchFactory(round=grp, kickoff=t0 + timedelta(hours=1), result_home=2, result_away=2, finished_at=t0)
    PredictionFactory(player=a, match=m1, earned=3)
    PredictionFactory(player=a, match=m2, earned=0)
    PredictionFactory(player=b, match=m1, earned=1)
    PredictionFactory(player=b, match=m2, earned=3)
    h = per_player_history()
    assert h[a.id][-1]["pts"] == 3
    assert h[b.id][-1]["pts"] == 4
    assert h[b.id][-1]["pos"] == 1
```

`mkdir -p stats/tests stats/services && touch stats/tests/__init__.py`

- [ ] **Step 2: Implementar `stats/services/history.py`**

```python
from collections import defaultdict
from competition.models import Match


def per_player_history() -> dict[int, list[dict]]:
    matches = list(
        Match.objects.filter(finished_at__isnull=False)
        .order_by("kickoff")
        .prefetch_related("predictions")
    )
    pts = defaultdict(int)
    history = defaultdict(list)
    for idx, m in enumerate(matches, start=1):
        for pred in m.predictions.all():
            pts[pred.player_id] += pred.earned or 0
        order = sorted(pts.items(), key=lambda x: -x[1])
        positions = {pid: pos for pos, (pid, _) in enumerate(order, start=1)}
        for pid, total in pts.items():
            history[pid].append({"idx": idx, "pts": total, "pos": positions[pid]})
    return dict(history)
```

- [ ] **Step 3: Tests + commit**

```bash
pytest stats/tests/test_history.py -v
git add stats/services/ stats/tests/test_history.py
git commit -m "feat(stats): histórico por jugador para el gráfico de evolución"
```

---

### Tarea 2.7: `stats.services.kpis` y donut

**Files:**
- Create: `stats/services/kpis.py`
- Test: `stats/tests/test_kpis.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.kpis import kpis, donut


@pytest.mark.django_db
def test_donut_segments():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    u = UserFactory()
    for earned in (3, 1, 1, 0):
        m = MatchFactory(round=grp, result_home=1, result_away=0)
        PredictionFactory(player=u, match=m, earned=earned)
    d = donut(u.id)
    assert d == {"exact": 1, "partial": 2, "fail": 1}


@pytest.mark.django_db
def test_kpis_basic():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    me = UserFactory(name="Me", email="me@e.com")
    other = UserFactory(name="X", email="x@e.com")
    for earned, p in [(3, me), (1, me), (0, me), (1, other), (1, other), (1, other)]:
        m = MatchFactory(round=grp, result_home=1, result_away=0)
        PredictionFactory(player=p, match=m, earned=earned)
    k = kpis(me)
    assert k["exact"] == 1
    assert k["hit_rate"] == pytest.approx(2/3)
    assert k["vs_leader"] >= 0
```

- [ ] **Step 2: Implementar `stats/services/kpis.py`**

```python
from statistics import mean
from competition.services.standings import standings
from competition.models import Prediction


def donut(player_id: int) -> dict:
    rows = (
        Prediction.objects.filter(player_id=player_id, earned__isnull=False)
        .values_list("earned", "match__round__points")
    )
    exact = partial = fail = 0
    for earned, round_points in rows:
        if earned == round_points:
            exact += 1
        elif earned > 0:
            partial += 1
        else:
            fail += 1
    return {"exact": exact, "partial": partial, "fail": fail}


def kpis(player) -> dict:
    s = standings()
    if not s:
        return {}
    me = next((r for r in s if r.player_id == player.id), None)
    if me is None:
        return {}
    avg = mean(r.pts for r in s)
    leader = s[0].pts
    return {
        "pts": me.pts,
        "position": me.position,
        "total_players": len(s),
        "exact": me.exact_hits,
        "hits": me.hits,
        "hit_rate": me.hits / max(me.hits + (donut(player.id)["fail"]), 1),
        "vs_avg": me.pts - avg,
        "vs_leader": leader - me.pts,
        "percentile": (me.position - 1) / len(s) * 100,
        "better_than": len(s) - me.position,
    }
```

- [ ] **Step 3: Tests + commit**

```bash
pytest stats/tests/test_kpis.py -v
git add stats/services/kpis.py stats/tests/test_kpis.py
git commit -m "feat(stats): KPIs y donut por jugador"
```

---

## Fase 3 — Autenticación, autorización y plantilla base

### Tarea 3.1: Plantilla base + partials `ambient`, `topbar`, `toast`

**Files:**
- Create: `templates/base.html`
- Create: `templates/partials/_ambient.html`
- Create: `templates/partials/_topbar.html`
- Create: `templates/partials/_toast.html`

- [ ] **Step 1: `templates/base.html`**

```django
{% load static %}<!doctype html>
<html lang="es" data-theme="{{ request.session.theme|default:'dark' }}">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>{% block title %}PORRA 26 · Mundial 2026{% endblock %}</title>
  <link rel="stylesheet" href="{% static 'css/styles.css' %}">
</head>
<body>
  {% include "partials/_ambient.html" %}
  {% if user.is_authenticated %}{% include "partials/_topbar.html" %}{% endif %}
  <main style="position:relative;z-index:1;min-height:0;padding:clamp(16px,2.4vw,32px) clamp(16px,3vw,40px)">
    {% block main %}{% endblock %}
  </main>
  {% include "partials/_toast.html" %}
  <script type="module" src="{% static 'js/theme.js' %}"></script>
  <script type="module" src="{% static 'js/toast.js' %}"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

- [ ] **Step 2: `templates/partials/_ambient.html`**

```django
<div class="ambient" aria-hidden="true"></div>
```

- [ ] **Step 3: `templates/partials/_topbar.html`**

```django
{% load icons %}
<header class="glass" style="border-radius:0;border-left:none;border-right:none;border-top:none;padding:12px clamp(16px,3vw,40px);display:flex;align-items:center;gap:18px;flex-shrink:0;z-index:20">
  <a href="{% url 'competicion:dashboard' %}" class="logo" style="text-decoration:none;color:inherit;font-size:17px">
    <span class="logo-mark" style="width:30px;height:30px;font-size:13px"><span>26</span></span>
    PORRA<span class="grad-text">26</span>
  </a>
  <nav style="display:flex;gap:4px;margin-left:12px">
    {% url 'competicion:dashboard' as competicion_url %}
    <a href="{{ competicion_url }}" class="nav-item {% if request.path|slice:':12' == '/competicion' %}active{% endif %}">
      {% icon "ball" width=17 height=17 %} Competición
    </a>
    <a href="{% url 'stats:dashboard' %}" class="nav-item {% if request.path|slice:':6' == '/stats' %}active{% endif %}">
      {% icon "chart" width=17 height=17 %} Estadísticas
    </a>
    {% if user.role == 'gestor' %}
    <a href="{% url 'pot:manage_players' %}" class="nav-item {% if '/gestion/jugadores' in request.path %}active{% endif %}">
      {% icon "users" width=17 height=17 %} Jugadores
    </a>
    <a href="{% url 'competicion:manage_results' %}" class="nav-item {% if '/gestion/resultados' in request.path %}active{% endif %}">
      {% icon "whistle" width=17 height=17 %} Resultados
    </a>
    {% endif %}
  </nav>
  <div style="margin-left:auto;display:flex;align-items:center;gap:12px">
    <span class="chip" style="color:var(--c-gold);border-color:oklch(from var(--c-gold) l c h / 0.35);padding:5px 11px">
      {% icon "euro" width=12 height=12 %} Bote {{ pot_total|default:0 }} €
    </span>
    <button class="btn btn-ghost" data-theme-toggle style="width:40px;height:40px;padding:0;border-radius:12px" title="Cambiar tema">
      {% icon "sun" width=18 height=18 class="theme-icon-light" %}
      {% icon "moon" width=18 height=18 class="theme-icon-dark" %}
    </button>
    <div style="display:flex;align-items:center;gap:9px;padding-left:6px">
      <span class="avatar" data-name="{{ user.name }}">{{ user.initials }}</span>
      <div style="line-height:1.2">
        <div style="font-size:13px;font-weight:700">{{ user.name }}</div>
        <div class="mono" style="font-size:10.5px;color:var(--text-faint);text-transform:capitalize">{{ user.role }}</div>
      </div>
      <a href="{% url 'accounts:logout' %}" class="btn btn-ghost" style="width:38px;height:38px;padding:0;border-radius:11px;margin-left:4px" title="Salir">
        {% icon "logout" width=16 height=16 %}
      </a>
    </div>
  </div>
</header>
```

- [ ] **Step 4: `templates/partials/_toast.html`**

```django
{% if messages %}
<div id="dj-messages" aria-live="polite" hidden>
  {% for message in messages %}<span data-msg="{{ message|escape }}" data-tag="{{ message.tags }}"></span>{% endfor %}
</div>
{% endif %}
```

- [ ] **Step 5: Commit**

```bash
git add templates/
git commit -m "feat(templates): base + partials ambient/topbar/toast"
```

> Las URLs y el template tag `icons` referenciados se crean en tareas posteriores; ahora pueden romper `{% url %}` — los probaremos al construir las vistas.

---

### Tarea 3.2: `core` context processor con `pot_total`

**Files:**
- Modify: `core/context_processors.py`
- Test: `core/tests/test_context.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from accounts.tests.factories import UserFactory
from pot.models import Payment, PotSettings


@pytest.mark.django_db
def test_pot_total_uses_paid_players():
    PotSettings.objects.update_or_create(pk=1, defaults={"per_player": 10})
    a = UserFactory(); b = UserFactory(); c = UserFactory()
    Payment.objects.create(player=a, paid=True)
    Payment.objects.create(player=b, paid=False)
    Payment.objects.create(player=c, paid=True)

    from core.context_processors import app_context
    rf = __import__("django.test", fromlist=["RequestFactory"]).RequestFactory()
    ctx = app_context(rf.get("/"))
    assert ctx["pot_total"] == 20
```

`mkdir -p core/tests && touch core/tests/__init__.py`

- [ ] **Step 2: Sustituir `core/context_processors.py`**

```python
from decimal import Decimal
from pot.models import Payment, PotSettings


def app_context(request):
    try:
        per = PotSettings.load().per_player
    except Exception:
        per = Decimal("10")
    paid_count = Payment.objects.filter(paid=True).count()
    return {
        "app_version": "0.1.0",
        "pot_total": int(per * paid_count),
    }
```

- [ ] **Step 3: Test + commit**

```bash
pytest core/tests/test_context.py -v
git add core/
git commit -m "feat(core): context processor con pot_total"
```

---

### Tarea 3.3: Iconos como template tag

**Files:**
- Create: `core/templatetags/__init__.py`
- Create: `core/templatetags/icons.py`
- Create: `static/icons/<24 svg files>.svg`

- [ ] **Step 1: Crear 24 SVG en `static/icons/`**

Los 24 son: `ball, trophy, cal, clock, users, edit, check, x, lock, mail, flame, up, down, euro, whistle, plus, logout, sun, moon, grid, chart, target, scale, gauge`.

Ejemplo `static/icons/check.svg` (formato común — `currentColor` para herencia):

```svg
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <path d="M20 6 9 17l-5-5"/>
</svg>
```

Hay que crear los 24. Usar como referencia el objeto `I` de `design-reference/shared.jsx`. Para abreviar, los paths exactos están en ese fichero.

`mkdir -p core/templatetags && touch core/templatetags/__init__.py`

- [ ] **Step 2: `core/templatetags/icons.py`**

```python
from functools import lru_cache
from pathlib import Path

from django import template
from django.conf import settings
from django.utils.safestring import mark_safe

register = template.Library()


@lru_cache(maxsize=64)
def _read(name: str) -> str:
    p = Path(settings.BASE_DIR) / "static" / "icons" / f"{name}.svg"
    return p.read_text(encoding="utf-8") if p.exists() else ""


@register.simple_tag
def icon(name: str, width=18, height=18, **kw):
    raw = _read(name)
    if not raw:
        return ""
    attrs = f'width="{width}" height="{height}"'
    extra = " ".join(f'{k}="{v}"' for k, v in kw.items())
    out = raw.replace("<svg", f'<svg {attrs} {extra}', 1)
    return mark_safe(out)
```

- [ ] **Step 3: Smoke test del tag**

```python
# core/tests/test_icons.py
from django.template import Context, Template


def test_icon_renders_check():
    t = Template("{% load icons %}{% icon 'check' width=20 %}")
    out = t.render(Context({}))
    assert "<svg" in out
    assert 'width="20"' in out
```

```bash
pytest core/tests/test_icons.py -v
git add core/templatetags core/tests/test_icons.py static/icons/
git commit -m "feat(core): template tag {% icon %} con SVG inline desde static/icons/"
```

---

### Tarea 3.4: URLs raíz + accounts:login

**Files:**
- Modify: `porra26/urls.py`
- Create: `accounts/urls.py`
- Create: `accounts/views.py`
- Create: `accounts/forms.py`
- Create: `templates/accounts/login.html`
- Test: `accounts/tests/test_login_view.py`

- [ ] **Step 1: `porra26/urls.py`**

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("competicion/", include(("competition.urls", "competicion"), namespace="competicion")),
    path("stats/", include(("stats.urls", "stats"), namespace="stats")),
    path("gestion/", include(("pot.urls", "pot"), namespace="pot")),
]
```

- [ ] **Step 2: `accounts/urls.py`**

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("cambiar-password/", views.ChangePasswordView.as_view(), name="change_password"),
]
```

- [ ] **Step 3: `accounts/forms.py`**

```python
from django import forms
from django.contrib.auth import authenticate

from .validators import validate_email_domain


class LoginForm(forms.Form):
    email = forms.EmailField(label="Correo")
    password = forms.CharField(label="Contraseña", widget=forms.PasswordInput)

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        validate_email_domain(email)
        return email

    def get_user(self, request):
        return authenticate(
            request,
            email=self.cleaned_data.get("email"),
            password=self.cleaned_data.get("password"),
        )


class ChangePasswordForm(forms.Form):
    current = forms.CharField(label="Contraseña actual", widget=forms.PasswordInput)
    new1 = forms.CharField(label="Nueva contraseña", widget=forms.PasswordInput, min_length=10)
    new2 = forms.CharField(label="Repite la contraseña", widget=forms.PasswordInput, min_length=10)

    def __init__(self, user, *args, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)

    def clean_current(self):
        if not self.user.check_password(self.cleaned_data["current"]):
            raise forms.ValidationError("La contraseña actual no es correcta.")
        return self.cleaned_data["current"]

    def clean(self):
        c = super().clean()
        if c.get("new1") and c.get("new2") and c["new1"] != c["new2"]:
            raise forms.ValidationError("Las dos contraseñas no coinciden.")
        if c.get("new1"):
            pwd = c["new1"]
            if not any(ch.isupper() for ch in pwd) or not any(ch.isdigit() for ch in pwd):
                raise forms.ValidationError("La contraseña debe tener al menos una mayúscula y un dígito.")
        return c
```

- [ ] **Step 4: `accounts/views.py`**

```python
from django.contrib import messages
from django.contrib.auth import login, logout
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect, render
from django.urls import reverse_lazy
from django.views import View

from .forms import ChangePasswordForm, LoginForm


class LoginView(View):
    template_name = "accounts/login.html"

    def get(self, request):
        if request.user.is_authenticated:
            return redirect("competicion:dashboard")
        return render(request, self.template_name, {"form": LoginForm()})

    def post(self, request):
        form = LoginForm(request.POST)
        if form.is_valid():
            user = form.get_user(request)
            if user is not None:
                login(request, user)
                if user.must_change_password:
                    return redirect("accounts:change_password")
                return redirect("competicion:dashboard")
            messages.error(request, "Correo o contraseña incorrectos.")
        return render(request, self.template_name, {"form": form})


class LogoutView(View):
    def post(self, request):
        logout(request)
        return redirect("accounts:login")

    def get(self, request):
        return self.post(request)


class ChangePasswordView(LoginRequiredMixin, View):
    login_url = reverse_lazy("accounts:login")
    template_name = "accounts/change_password.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ChangePasswordForm(request.user)})

    def post(self, request):
        form = ChangePasswordForm(request.user, request.POST)
        if form.is_valid():
            request.user.set_password(form.cleaned_data["new1"])
            request.user.must_change_password = False
            request.user.save(update_fields=["password", "must_change_password"])
            login(request, request.user)  # mantener sesión tras cambiar
            messages.success(request, "Contraseña actualizada.")
            return redirect("competicion:dashboard")
        return render(request, self.template_name, {"form": form})
```

- [ ] **Step 5: Authentication backend custom**

Edit `accounts/backends.py` (nuevo):

```python
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import ModelBackend

User = get_user_model()


class EmailBackend(ModelBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        if not email:
            return None
        try:
            user = User.objects.get(email__iexact=email)
        except User.DoesNotExist:
            return None
        if user.check_password(password) and user.is_active:
            return user
        return None
```

Añadir a `porra26/settings/base.py`:

```python
AUTHENTICATION_BACKENDS = ["accounts.backends.EmailBackend"]
```

- [ ] **Step 6: Plantillas mínimas**

`templates/accounts/login.html`:

```django
{% extends "base.html" %}
{% load icons %}
{% block main %}
<section class="glass pop" style="max-width:460px;margin:6vh auto;padding:32px;border-radius:24px">
  <div class="eyebrow">PORRA 26 · MUNDIAL 2026</div>
  <h1 class="display" style="font-size:34px;margin:4px 0 18px">Bienvenido de nuevo</h1>
  <form method="post" novalidate>
    {% csrf_token %}
    <div class="field"><label>Correo</label>
      <input class="input" type="email" name="email" required value="{{ form.email.value|default:'' }}">
    </div>
    <div class="field" style="margin-top:14px"><label>Contraseña</label>
      <input class="input" type="password" name="password" required>
    </div>
    {% if form.non_field_errors %}<p style="color:var(--c-red)">{{ form.non_field_errors|join:' ' }}</p>{% endif %}
    {% for f in form %}{% for e in f.errors %}<p style="color:var(--c-red)">{{ e }}</p>{% endfor %}{% endfor %}
    <button type="submit" class="btn btn-primary" style="margin-top:20px;width:100%">Entrar al torneo</button>
    <p class="mono" style="margin-top:14px;color:var(--text-faint);font-size:11px">
      ¿Olvidaste tu contraseña? Pídele a un gestor que la restablezca.
    </p>
  </form>
</section>
{% endblock %}
```

`templates/accounts/change_password.html`:

```django
{% extends "base.html" %}
{% block main %}
<section class="glass" style="max-width:460px;margin:6vh auto;padding:32px;border-radius:24px">
  <h1 class="display" style="font-size:24px">Cambia tu contraseña</h1>
  <form method="post">
    {% csrf_token %}
    {% for f in form %}
      <div class="field" style="margin-top:14px">
        <label>{{ f.label }}</label>
        {{ f.as_widget }}
        {% for e in f.errors %}<p style="color:var(--c-red)">{{ e }}</p>{% endfor %}
      </div>
    {% endfor %}
    {% if form.non_field_errors %}<p style="color:var(--c-red)">{{ form.non_field_errors|join:' ' }}</p>{% endif %}
    <button type="submit" class="btn btn-primary" style="margin-top:20px;width:100%">Guardar</button>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 7: Tests `accounts/tests/test_login_view.py`**

```python
import pytest
from django.urls import reverse
from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_login_get_renders(client):
    r = client.get(reverse("accounts:login"))
    assert r.status_code == 200
    assert b"Bienvenido" in r.content


@pytest.mark.django_db
def test_login_post_success(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    u = UserFactory(email="a@edisa.com", must_change_password=False)
    u.set_password("Secret123!"); u.save()
    r = client.post(reverse("accounts:login"), {"email": "a@edisa.com", "password": "Secret123!"})
    assert r.status_code == 302


@pytest.mark.django_db
def test_login_post_wrong_password(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    u = UserFactory(email="a@edisa.com")
    u.set_password("Right123!"); u.save()
    r = client.post(reverse("accounts:login"), {"email": "a@edisa.com", "password": "Wrong123!"})
    assert r.status_code == 200
    assert b"incorrectos" in r.content


@pytest.mark.django_db
def test_login_post_domain_blocked(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    r = client.post(reverse("accounts:login"), {"email": "x@gmail.com", "password": "x"})
    assert r.status_code == 200
    assert b"dominios permitidos" in r.content
```

- [ ] **Step 8: Stub URLs faltantes para que `{% url %}` no rompa**

Crear `competition/urls.py` y `stats/urls.py` y `pot/urls.py` con un stub:

```python
# competition/urls.py
from django.urls import path
from django.http import HttpResponse
def stub(req, *a, **kw): return HttpResponse("stub")
urlpatterns = [
    path("", stub, name="dashboard"),
    path("resultados/", stub, name="manage_results"),
]
```

Análogo para `stats/urls.py` (`name="dashboard"`) y `pot/urls.py` (`name="manage_players"`, `name="prizes"`, etc.). Los reemplazaremos por las vistas reales en sus tareas.

- [ ] **Step 9: Tests pasan + Commit**

```bash
pytest accounts/tests/test_login_view.py -v
git add accounts/ porra26/urls.py templates/accounts/ competition/urls.py stats/urls.py pot/urls.py porra26/settings/base.py
git commit -m "feat(accounts): login, logout y cambio de contraseña + backend por email"
```

---

### Tarea 3.5: `ForcePasswordChangeMiddleware`

**Files:**
- Modify: `accounts/middleware.py`
- Test: `accounts/tests/test_middleware.py`

- [ ] **Step 1: Test fallido**

```python
import pytest
from django.urls import reverse
from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_middleware_redirects_when_must_change_password(client):
    u = UserFactory(must_change_password=True)
    u.set_password("Test123!"); u.save()
    client.force_login(u)
    r = client.get("/competicion/")
    assert r.status_code == 302
    assert reverse("accounts:change_password") in r.url


@pytest.mark.django_db
def test_middleware_allows_change_password_route(client):
    u = UserFactory(must_change_password=True)
    u.set_password("Test123!"); u.save()
    client.force_login(u)
    r = client.get(reverse("accounts:change_password"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_middleware_allows_logout(client):
    u = UserFactory(must_change_password=True)
    client.force_login(u)
    r = client.get(reverse("accounts:logout"))
    assert r.status_code == 302
```

- [ ] **Step 2: Implementar**

```python
from django.shortcuts import redirect
from django.urls import reverse


class ForcePasswordChangeMiddleware:
    EXEMPT = {"/cambiar-password/", "/logout/", "/static/", "/admin/"}

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.user.is_authenticated and getattr(request.user, "must_change_password", False):
            if not any(request.path.startswith(p) for p in self.EXEMPT):
                return redirect(reverse("accounts:change_password"))
        return self.get_response(request)
```

- [ ] **Step 3: Tests + commit**

```bash
pytest accounts/tests/test_middleware.py -v
git add accounts/middleware.py accounts/tests/test_middleware.py
git commit -m "feat(accounts): middleware de cambio forzado de contraseña"
```

---

### Tarea 3.6: `RoleRequiredMixin` y `django-axes`

**Files:**
- Create: `accounts/mixins.py`
- Modify: `porra26/settings/base.py`
- Modify: `porra26/settings/test.py`

- [ ] **Step 1: `accounts/mixins.py`**

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class RoleRequiredMixin(LoginRequiredMixin):
    required_role: str | None = None

    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if self.required_role and request.user.role != self.required_role:
            messages.warning(request, "No tienes permisos para esa sección.")
            return redirect("competicion:dashboard")
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 2: Añadir `django-axes` en settings/base.py**

```python
INSTALLED_APPS += ["axes"]
AUTHENTICATION_BACKENDS = ["axes.backends.AxesStandaloneBackend", "accounts.backends.EmailBackend"]

MIDDLEWARE.append("axes.middleware.AxesMiddleware")

AXES_FAILURE_LIMIT = 5
AXES_COOLOFF_TIME = 0.25  # 15 minutos en horas
AXES_LOCKOUT_PARAMETERS = [["username", "ip_address"]]
AXES_RESET_ON_SUCCESS = True
```

En `porra26/settings/test.py` añadir:

```python
AXES_ENABLED = False
```

- [ ] **Step 3: `python manage.py migrate axes` (en dev)**

- [ ] **Step 4: Commit**

```bash
git add accounts/mixins.py porra26/settings/
git commit -m "feat(accounts): RoleRequiredMixin + django-axes contra fuerza bruta"
```

---

## Fase 4 — Pantalla Competición (jugador) y resolución de partidos (gestor)

### Tarea 4.1: `CompetitionView` + plantilla dashboard

**Files:**
- Modify: `competition/urls.py`
- Create: `competition/views.py`
- Create: `templates/competition/dashboard.html`
- Create: `templates/competition/_match_card.html`
- Create: `templates/partials/_round_selector.html`
- Test: `competition/tests/test_competition_view.py`

- [ ] **Step 1: Reescribir `competition/urls.py`**

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.CompetitionView.as_view(), name="dashboard"),
    path("pronosticar/<int:match_id>/", views.PredictView.as_view(), name="predict"),
    path("resultados/", views.ManageResultsView.as_view(), name="manage_results"),
    path("resultados/<int:match_id>/", views.ResultOfficialView.as_view(), name="official"),
]
```

- [ ] **Step 2: Implementar `competition/views.py`**

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.core.exceptions import PermissionDenied
from django.shortcuts import get_object_or_404, redirect, render
from django.views import View

from accounts.mixins import RoleRequiredMixin
from competition.models import Match, Prediction, Round
from competition.services.resolve import resolve_match
from competition.services.standings import standings


class CompetitionView(LoginRequiredMixin, View):
    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")
        matches = list(
            Match.objects.filter(round_id=active_id)
            .select_related("home", "away", "round")
            .order_by("kickoff")
        )
        my_preds = {p.match_id: p for p in Prediction.objects.filter(player=request.user, match__in=matches)}
        groups_open, groups_live, groups_done = [], [], []
        for m in matches:
            (groups_live if m.status == "live" else groups_done if m.status == "done" else groups_open).append(m)
        return render(request, "competition/dashboard.html", {
            "rounds": rounds,
            "active_round": active_id,
            "open_matches": groups_open,
            "live_matches": groups_live,
            "done_matches": groups_done,
            "my_preds": my_preds,
            "standings": standings()[:50],
        })


class PredictView(LoginRequiredMixin, View):
    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not m.editable:
            messages.error(request, "Las apuestas para este partido están cerradas.")
            return redirect("competicion:dashboard")
        pred = Prediction.objects.filter(player=request.user, match=m).first()
        return render(request, "competition/_predict_modal.html", {"match": m, "pred": pred})

    def post(self, request, match_id):
        m = get_object_or_404(Match, pk=match_id)
        if not m.editable:
            raise PermissionDenied("Apuestas cerradas")
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:dashboard")
        Prediction.objects.update_or_create(player=request.user, match=m, defaults={"home": h, "away": a})
        messages.success(request, f"Pronóstico guardado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect(f"{request.path.rsplit('/pronosticar', 1)[0]}/?round={m.round_id}" if False else "/competicion/")


class ManageResultsView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")
        ms = list(Match.objects.filter(round_id=active_id).select_related("home", "away", "round").order_by("kickoff"))
        pending, upcoming, done = [], [], []
        for m in ms:
            if m.status == "done":
                done.append(m)
            elif m.status in ("live", "closed"):
                pending.append(m)
            else:
                upcoming.append(m)
        return render(request, "competition/manage_results.html", {
            "rounds": rounds, "active_round": active_id,
            "pending": pending, "upcoming": upcoming, "done": done,
        })


class ResultOfficialView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        return render(request, "competition/_official_modal.html", {"match": m})

    def post(self, request, match_id):
        m = get_object_or_404(Match, pk=match_id)
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:manage_results")
        resolve_match(m, home=h, away=a, actor=request.user)
        messages.success(request, f"Resultado confirmado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect("competicion:manage_results")
```

- [ ] **Step 3: Plantillas**

`templates/competition/dashboard.html`:

```django
{% extends "base.html" %}
{% load icons %}
{% block main %}
<div style="display:grid;grid-template-columns:1fr 380px;gap:24px">
  <section>
    {% include "partials/_round_selector.html" with rounds=rounds active=active_round %}
    {% if open_matches %}
    <h2 class="eyebrow" style="margin-top:24px">ABIERTOS · {{ open_matches|length }}</h2>
    <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
      {% for m in open_matches %}{% include "competition/_match_card.html" with match=m my_pred=my_preds|dictsort:'match_id' editable=True %}{% endfor %}
    </div>
    {% endif %}
    {% if live_matches %}
    <h2 class="eyebrow" style="margin-top:24px">EN JUEGO · {{ live_matches|length }}</h2>
    <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
      {% for m in live_matches %}{% include "competition/_match_card.html" with match=m my_pred=my_preds %}{% endfor %}
    </div>
    {% endif %}
    {% if done_matches %}
    <h2 class="eyebrow" style="margin-top:24px">FINALIZADOS · {{ done_matches|length }}</h2>
    <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
      {% for m in done_matches %}{% include "competition/_match_card.html" with match=m my_pred=my_preds %}{% endfor %}
    </div>
    {% endif %}
  </section>
  <aside>{% include "partials/_leaderboard.html" with rows=standings me=request.user %}</aside>
</div>
{% endblock %}
```

`templates/competition/_match_card.html`:

```django
{% load icons %}
{% with mp=my_preds|default_if_none:None %}
<article class="glass" style="border-radius:20px;padding:14px;position:relative">
  <header style="display:flex;justify-content:space-between;align-items:center">
    <span class="mono" style="color:var(--text-faint);font-size:11px">Grupo {{ match.group }}</span>
    <span class="chip chip-{{ match.status }}">{{ match.get_status_display|default:match.status }}</span>
  </header>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:10px;margin:10px 0">
    <div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1">
      <span style="font-size:34px">{{ match.home.flag }}</span>
      <strong style="font-size:13px">{{ match.home.name }}</strong>
    </div>
    <div class="display" style="font-size:22px;min-width:60px;text-align:center">
      {% if match.has_result %}{{ match.result_home }}–{{ match.result_away }}{% else %}VS{% endif %}
    </div>
    <div style="display:flex;flex-direction:column;align-items:center;gap:4px;flex:1">
      <span style="font-size:34px">{{ match.away.flag }}</span>
      <strong style="font-size:13px">{{ match.away.name }}</strong>
    </div>
  </div>
  <footer style="display:flex;justify-content:space-between;align-items:center;margin-top:10px">
    <span class="mono" style="font-size:11px;color:var(--text-faint)">
      {% icon "cal" width=11 height=11 %} {{ match.kickoff|date:"d M · H:i" }}
    </span>
    {% if match.editable %}
      <a class="btn btn-primary" href="{% url 'competicion:predict' match.id %}" data-modal-url="{% url 'competicion:predict' match.id %}" style="padding:6px 12px;font-size:12px">Pronosticar</a>
    {% else %}
      <span class="chip">{{ match.status }}</span>
    {% endif %}
  </footer>
</article>
{% endwith %}
```

`templates/partials/_round_selector.html`:

```django
<nav class="glass" style="display:flex;gap:6px;padding:8px;border-radius:14px">
  {% for r in rounds %}
  <a href="?round={{ r.id }}" class="chip {% if r.id == active %}chip-open{% endif %}" style="text-decoration:none">
    {{ r.label }} · <span class="mono">{{ r.points }}p</span>
  </a>
  {% endfor %}
</nav>
```

`templates/competition/_predict_modal.html`:

```django
{% extends "base.html" %}
{% block main %}
<section class="glass pop" style="max-width:520px;margin:6vh auto;padding:28px;border-radius:24px">
  <div class="eyebrow">PRONÓSTICO</div>
  <h1 class="display" style="font-size:24px">¿Cómo va a quedar?</h1>
  <form method="post" action="{% url 'competicion:predict' match.id %}">
    {% csrf_token %}
    <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:14px;margin:18px 0">
      <div style="text-align:center">
        <div style="font-size:46px">{{ match.home.flag }}</div><strong>{{ match.home.name }}</strong>
        <input name="home" type="number" min="0" max="20" value="{{ pred.home|default:0 }}" class="input" style="font-size:32px;text-align:center;width:84px;margin:8px auto 0">
      </div>
      <div class="display" style="font-size:30px">:</div>
      <div style="text-align:center">
        <div style="font-size:46px">{{ match.away.flag }}</div><strong>{{ match.away.name }}</strong>
        <input name="away" type="number" min="0" max="20" value="{{ pred.away|default:0 }}" class="input" style="font-size:32px;text-align:center;width:84px;margin:8px auto 0">
      </div>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <a class="btn btn-ghost" href="{% url 'competicion:dashboard' %}">Cancelar</a>
      <button class="btn btn-primary" type="submit">Guardar pronóstico</button>
    </div>
  </form>
</section>
{% endblock %}
```

`templates/competition/manage_results.html`:

```django
{% extends "base.html" %}
{% block main %}
<h1 class="display" style="font-size:28px">Resultados oficiales</h1>
<p style="color:var(--text-dim)">Confirma los marcadores. Al confirmar se recalculan los puntos.</p>
{% include "partials/_round_selector.html" with rounds=rounds active=active_round %}
{% for section, items in pending|zip:upcoming|zip:done %}{% endfor %}
{% if pending %}
<h2 class="eyebrow" style="margin-top:18px">PENDIENTES DE FINALIZAR</h2>
<div style="display:flex;flex-direction:column;gap:8px">
  {% for m in pending %}
  <div class="glass" style="display:grid;grid-template-columns:auto 1fr auto auto;gap:14px;align-items:center;padding:12px 14px;border-radius:14px">
    <span class="mono" style="color:var(--text-faint)">Grupo {{ m.group }}</span>
    <span>{{ m.home.flag }} {{ m.home.name }} vs {{ m.away.flag }} {{ m.away.name }}</span>
    <span class="chip chip-{{ m.status }}">{{ m.status }}</span>
    <a class="btn btn-primary" href="{% url 'competicion:official' m.id %}" style="padding:6px 12px;font-size:12px">Finalizar</a>
  </div>
  {% endfor %}
</div>
{% endif %}
{% if upcoming %}
<h2 class="eyebrow" style="margin-top:18px">PRÓXIMOS</h2>
<div style="display:flex;flex-direction:column;gap:8px">
  {% for m in upcoming %}
  <div class="glass" style="display:grid;grid-template-columns:auto 1fr auto;gap:14px;align-items:center;padding:12px 14px;border-radius:14px">
    <span class="mono" style="color:var(--text-faint)">Grupo {{ m.group }}</span>
    <span>{{ m.home.flag }} {{ m.home.name }} vs {{ m.away.flag }} {{ m.away.name }}</span>
    <span class="mono" style="font-size:11px">{{ m.kickoff|date:"d M · H:i" }}</span>
  </div>
  {% endfor %}
</div>
{% endif %}
{% if done %}
<h2 class="eyebrow" style="margin-top:18px">FINALIZADOS</h2>
<div style="display:flex;flex-direction:column;gap:8px">
  {% for m in done %}
  <div class="glass" style="display:grid;grid-template-columns:auto 1fr auto auto;gap:14px;align-items:center;padding:12px 14px;border-radius:14px">
    <span class="mono" style="color:var(--text-faint)">Grupo {{ m.group }}</span>
    <span>{{ m.home.flag }} {{ m.home.name }} {{ m.result_home }}–{{ m.result_away }} {{ m.away.flag }} {{ m.away.name }}</span>
    <span class="chip chip-done">Final</span>
    <a class="btn btn-ghost" href="{% url 'competicion:official' m.id %}" style="padding:6px 12px;font-size:12px">Editar</a>
  </div>
  {% endfor %}
</div>
{% endif %}
{% endblock %}
```

`templates/competition/_official_modal.html`:

```django
{% extends "base.html" %}
{% block main %}
<section class="glass pop" style="max-width:520px;margin:6vh auto;padding:28px;border-radius:24px">
  <div class="eyebrow">RESULTADO OFICIAL</div>
  <h1 class="display" style="font-size:24px">Marcar resultado final</h1>
  <form method="post" action="{% url 'competicion:official' match.id %}">
    {% csrf_token %}
    <div style="display:grid;grid-template-columns:1fr auto 1fr;gap:14px;margin:18px 0;align-items:center">
      <div style="text-align:center">
        <div style="font-size:46px">{{ match.home.flag }}</div><strong>{{ match.home.name }}</strong>
        <input name="home" type="number" min="0" max="20" value="{{ match.result_home|default:0 }}" class="input" style="font-size:32px;text-align:center;width:84px;margin:8px auto 0">
      </div>
      <div class="display" style="font-size:30px">:</div>
      <div style="text-align:center">
        <div style="font-size:46px">{{ match.away.flag }}</div><strong>{{ match.away.name }}</strong>
        <input name="away" type="number" min="0" max="20" value="{{ match.result_away|default:0 }}" class="input" style="font-size:32px;text-align:center;width:84px;margin:8px auto 0">
      </div>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end">
      <a class="btn btn-ghost" href="{% url 'competicion:manage_results' %}">Cancelar</a>
      <button class="btn btn-primary" type="submit">Confirmar y finalizar</button>
    </div>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 4: Tests `competition/tests/test_competition_view.py`**

```python
from datetime import timedelta
import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import GestorFactory, UserFactory
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_dashboard_requires_login(client):
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_dashboard_shows_matches(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:dashboard"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_predict_post_creates_prediction(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    assert m.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_predict_post_rejected_when_closed(client):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=1))  # live
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 1, "away": 0})
    assert r.status_code == 403


@pytest.mark.django_db
def test_manage_results_requires_gestor(client):
    u = UserFactory(must_change_password=False, role="jugador")
    client.force_login(u)
    r = client.get(reverse("competicion:manage_results"))
    assert r.status_code == 302  # redirect to dashboard


@pytest.mark.django_db
def test_official_post_resolves_match(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=3))
    r = client.post(reverse("competicion:official", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    m.refresh_from_db()
    assert (m.result_home, m.result_away) == (2, 1)
```

- [ ] **Step 5: Tests + commit**

```bash
pytest competition/tests/test_competition_view.py -v
git add competition/ templates/competition/ templates/partials/_round_selector.html
git commit -m "feat(competition): dashboard del jugador + pronosticar + resolver oficial"
```

---

### Tarea 4.2: `Leaderboard` partial reutilizable

**Files:**
- Create: `templates/partials/_leaderboard.html`

- [ ] **Step 1: Implementar `templates/partials/_leaderboard.html`**

```django
{% load icons %}
<section class="glass" style="padding:18px;border-radius:20px;position:sticky;top:18px;max-height:calc(100vh - 100px);overflow:auto">
  <header style="display:flex;align-items:center;gap:8px;margin-bottom:12px">
    {% icon "trophy" width=18 height=18 class="text-gold" %}
    <h2 class="display" style="font-size:18px;margin:0">Clasificación</h2>
  </header>
  <ol style="list-style:none;padding:0;margin:0;display:flex;flex-direction:column;gap:6px">
    {% for r in rows %}
    <li style="display:grid;grid-template-columns:26px 1fr auto;gap:10px;align-items:center;padding:8px;border-radius:10px;{% if r.player_id == me.id %}background:oklch(from var(--accent) l c h / 0.12);{% endif %}">
      <span class="mono" style="font-size:13px;color:var(--text-faint)">{{ r.position }}</span>
      <div>
        <strong style="font-size:13px">{{ r.name }}{% if r.player_id == me.id %} · tú{% endif %}</strong>
        <div class="mono" style="font-size:10px;color:var(--text-faint)">{{ r.hits }}h · {{ r.exact_hits }}e</div>
      </div>
      <strong class="display" style="font-size:16px">{{ r.pts }}</strong>
    </li>
    {% empty %}
    <li style="color:var(--text-faint)">Sin jugadores todavía.</li>
    {% endfor %}
  </ol>
</section>
```

- [ ] **Step 2: Commit**

```bash
git add templates/partials/_leaderboard.html
git commit -m "feat(templates): partial reutilizable de clasificación"
```

---

## Fase 5 — Panel de gestor (jugadores y premios)

### Tarea 5.1: `ManagePlayersView` + tabla y modal

**Files:**
- Modify: `pot/urls.py`
- Create: `pot/views.py`
- Create: `pot/forms.py`
- Create: `templates/pot/manage_players.html`
- Create: `templates/pot/_player_modal.html`
- Create: `templates/pot/_password_reveal.html`
- Test: `pot/tests/test_views.py`

- [ ] **Step 1: `pot/urls.py`**

```python
from django.urls import path
from . import views

urlpatterns = [
    path("jugadores/", views.ManagePlayersView.as_view(), name="manage_players"),
    path("jugadores/nuevo/", views.PlayerFormView.as_view(), name="player_new"),
    path("jugadores/<int:pk>/", views.PlayerFormView.as_view(), name="player_edit"),
    path("jugadores/<int:pk>/reset/", views.ResetPasswordView.as_view(), name="player_reset"),
    path("jugadores/<int:pk>/baja/", views.TogglePlayerActiveView.as_view(), name="player_toggle_active"),
    path("jugadores/<int:pk>/pago/", views.TogglePaymentView.as_view(), name="player_toggle_payment"),
    path("premios/", views.PrizesSettingsView.as_view(), name="prizes"),
    path("auditoria/", views.AuditLogView.as_view(), name="audit"),
]
```

- [ ] **Step 2: `pot/forms.py`**

```python
import secrets
from django import forms
from accounts.models import User
from accounts.validators import validate_email_domain


class PlayerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "dept", "role"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        validate_email_domain(email)
        return email


def generate_temp_password() -> str:
    return secrets.token_urlsafe(9)
```

- [ ] **Step 3: `pot/views.py`**

```python
from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views import View

from accounts.mixins import RoleRequiredMixin
from accounts.models import AuditLog, User
from pot.forms import PlayerForm, generate_temp_password
from pot.models import Payment, Prize


class ManagePlayersView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request):
        q = request.GET.get("q", "").strip()
        players = User.objects.all().order_by("name")
        if q:
            players = players.filter(name__icontains=q) | players.filter(email__icontains=q)
        return render(request, "pot/manage_players.html", {
            "players": players,
            "q": q,
            "active_count": User.objects.filter(is_active=True).count(),
            "paid_count": Payment.objects.filter(paid=True).count(),
            "total_count": User.objects.count(),
        })


class PlayerFormView(RoleRequiredMixin, View):
    required_role = "gestor"

    def _get_object(self, pk):
        return User.objects.get(pk=pk) if pk else None

    def get(self, request, pk=None):
        obj = self._get_object(pk)
        form = PlayerForm(instance=obj)
        return render(request, "pot/_player_modal.html", {"form": form, "player": obj})

    def post(self, request, pk=None):
        obj = self._get_object(pk)
        form = PlayerForm(request.POST, instance=obj)
        if not form.is_valid():
            return render(request, "pot/_player_modal.html", {"form": form, "player": obj})
        is_new = obj is None
        if is_new:
            temp = generate_temp_password()
            user = form.save(commit=False)
            user.set_password(temp)
            user.must_change_password = True
            user.save()
            Payment.objects.get_or_create(player=user)
            AuditLog.objects.create(actor=request.user, action="player_created",
                                     target_type="user", target_id=str(user.id), payload={})
            messages.success(request, "Jugador creado.")
            return render(request, "pot/_password_reveal.html", {"player": user, "temp_password": temp})
        form.save()
        messages.success(request, "Cambios guardados.")
        return redirect("pot:manage_players")


class ResetPasswordView(RoleRequiredMixin, View):
    required_role = "gestor"

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        temp = generate_temp_password()
        u.set_password(temp)
        u.must_change_password = True
        u.save(update_fields=["password", "must_change_password"])
        AuditLog.objects.create(actor=request.user, action="password_reset",
                                 target_type="user", target_id=str(u.id), payload={})
        return render(request, "pot/_password_reveal.html", {"player": u, "temp_password": temp})


class TogglePlayerActiveView(RoleRequiredMixin, View):
    required_role = "gestor"

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        u.is_active = not u.is_active
        u.save(update_fields=["is_active"])
        return redirect("pot:manage_players")


class TogglePaymentView(RoleRequiredMixin, View):
    required_role = "gestor"

    def post(self, request, pk):
        u = get_object_or_404(User, pk=pk)
        pay, _ = Payment.objects.get_or_create(player=u)
        pay.paid = not pay.paid
        pay.paid_at = timezone.now() if pay.paid else None
        pay.save()
        AuditLog.objects.create(actor=request.user, action="payment_toggled",
                                 target_type="user", target_id=str(u.id), payload={"paid": pay.paid})
        return redirect("pot:manage_players")


class PrizesSettingsView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request):
        return render(request, "pot/prizes_settings.html", {"prizes": Prize.objects.all().select_related("round")})

    def post(self, request):
        for prize in Prize.objects.all():
            raw = request.POST.get(f"amount_{prize.id}")
            if raw is None:
                continue
            try:
                prize.amount = max(0, int(raw))
                prize.save(update_fields=["amount"])
            except ValueError:
                pass
        AuditLog.objects.create(actor=request.user, action="prize_changed",
                                 target_type="prize", target_id="*", payload={})
        messages.success(request, "Premios actualizados.")
        return redirect("pot:prizes")


class AuditLogView(RoleRequiredMixin, View):
    required_role = "gestor"

    def get(self, request):
        return render(request, "accounts/audit_log.html", {"logs": AuditLog.objects.all()[:200]})
```

- [ ] **Step 4: Plantillas mínimas**

`templates/pot/manage_players.html`:

```django
{% extends "base.html" %}
{% load icons %}
{% block main %}
<header style="display:flex;align-items:center;gap:14px;margin-bottom:16px">
  <h1 class="display" style="font-size:28px;margin:0">Jugadores</h1>
  <span class="chip chip-open">{{ active_count }} activos</span>
  <span class="chip">{{ paid_count }}/{{ total_count }} pagado</span>
  <a class="btn btn-primary" style="margin-left:auto" href="{% url 'pot:player_new' %}">{% icon "plus" width=14 %} Nuevo jugador</a>
</header>
<form method="get" style="margin-bottom:12px">
  <input class="input" type="search" name="q" value="{{ q }}" placeholder="Buscar por nombre o correo" style="max-width:360px">
</form>
<div class="glass" style="border-radius:16px;overflow:hidden">
  <div style="display:grid;grid-template-columns:2.4fr 1fr 0.8fr 1fr 1.1fr 90px;padding:14px;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.18em;border-bottom:1px solid var(--border)">
    <span>Jugador</span><span>Departamento</span><span>Puntos</span><span>Pago</span><span>Estado</span><span></span>
  </div>
  {% for p in players %}
  <div style="display:grid;grid-template-columns:2.4fr 1fr 0.8fr 1fr 1.1fr 90px;padding:14px;align-items:center;border-bottom:1px solid var(--border);{% if not p.is_active %}opacity:0.5{% endif %}">
    <div>
      <strong>{{ p.name }}</strong>
      <div class="mono" style="font-size:11px;color:var(--text-faint)">{{ p.email }}</div>
    </div>
    <span>{{ p.dept|default:"—" }}</span>
    <span class="display">—</span>
    <form method="post" action="{% url 'pot:player_toggle_payment' p.id %}" style="display:flex;align-items:center;gap:6px">
      {% csrf_token %}
      <button type="submit" class="chip {% if p.payment.paid %}chip-open{% endif %}">{{ p.payment.paid|yesno:"Pagado,Pendiente,Pendiente" }}</button>
    </form>
    <span class="chip {% if p.is_active %}chip-open{% endif %}">{{ p.is_active|yesno:"Activo,Baja" }}</span>
    <div style="display:flex;gap:6px">
      <a class="btn btn-ghost" href="{% url 'pot:player_edit' p.id %}" style="width:32px;height:32px;padding:0">{% icon "edit" width=14 %}</a>
      <form method="post" action="{% url 'pot:player_toggle_active' p.id %}" style="display:inline">
        {% csrf_token %}
        <button class="btn btn-ghost" style="width:32px;height:32px;padding:0">{% if p.is_active %}{% icon "x" width=14 %}{% else %}{% icon "check" width=14 %}{% endif %}</button>
      </form>
    </div>
  </div>
  {% empty %}
  <p style="padding:18px;color:var(--text-faint)">No hay jugadores todavía.</p>
  {% endfor %}
</div>
{% endblock %}
```

`templates/pot/_player_modal.html`:

```django
{% extends "base.html" %}
{% block main %}
<section class="glass pop" style="max-width:520px;margin:6vh auto;padding:28px;border-radius:24px">
  <h1 class="display" style="font-size:22px">{% if player %}{{ player.name }}{% else %}Nuevo jugador{% endif %}</h1>
  <form method="post">
    {% csrf_token %}
    {% for f in form %}
      <div class="field" style="margin-top:14px">
        <label>{{ f.label }}</label>
        {{ f }}
        {% for e in f.errors %}<p style="color:var(--c-red)">{{ e }}</p>{% endfor %}
      </div>
    {% endfor %}
    {% if not player %}
    <p class="mono" style="font-size:11px;color:var(--text-faint);margin-top:14px">
      Se generará una contraseña temporal y se mostrará en pantalla. Compártela por canal privado.
    </p>
    {% endif %}
    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:18px">
      <a class="btn btn-ghost" href="{% url 'pot:manage_players' %}">Cancelar</a>
      <button class="btn btn-primary" type="submit">{% if player %}Guardar{% else %}Crear jugador{% endif %}</button>
    </div>
  </form>
</section>
{% endblock %}
```

`templates/pot/_password_reveal.html`:

```django
{% extends "base.html" %}
{% block main %}
<section class="glass pop" style="max-width:520px;margin:6vh auto;padding:28px;border-radius:24px;text-align:center">
  <h1 class="display" style="font-size:22px">Contraseña temporal de {{ player.name }}</h1>
  <p style="color:var(--text-dim)">Cópiala y pásasela por un canal privado. Sólo se muestra una vez.</p>
  <code class="mono" style="display:block;background:var(--surface-hi);padding:18px;font-size:22px;border-radius:12px;margin:16px 0">{{ temp_password }}</code>
  <button class="btn btn-primary" onclick="navigator.clipboard.writeText('{{ temp_password }}')">Copiar al portapapeles</button>
  <a class="btn btn-ghost" href="{% url 'pot:manage_players' %}" style="margin-left:8px">Volver</a>
</section>
{% endblock %}
```

`templates/pot/prizes_settings.html`:

```django
{% extends "base.html" %}
{% block main %}
<h1 class="display" style="font-size:28px">Premios del bote</h1>
<form method="post">
  {% csrf_token %}
  <div class="glass" style="padding:18px;border-radius:16px">
    {% for prize in prizes %}
    <div style="display:grid;grid-template-columns:1.5fr 1fr;gap:14px;align-items:center;padding:10px 0;border-bottom:1px solid var(--border)">
      <span>{{ prize.label }}</span>
      <div style="display:flex;align-items:center;gap:8px">
        <input class="input" type="number" min="0" name="amount_{{ prize.id }}" value="{{ prize.amount|floatformat:0 }}" style="max-width:160px">
        <span class="mono">€</span>
      </div>
    </div>
    {% endfor %}
  </div>
  <button class="btn btn-primary" style="margin-top:18px" type="submit">Guardar premios</button>
</form>
{% endblock %}
```

`templates/accounts/audit_log.html`:

```django
{% extends "base.html" %}
{% block main %}
<h1 class="display" style="font-size:28px">Auditoría</h1>
<div class="glass" style="padding:18px;border-radius:16px">
  {% for log in logs %}
  <div style="display:grid;grid-template-columns:1fr 2fr 2fr 1fr;gap:14px;padding:8px 0;border-bottom:1px solid var(--border);font-size:13px">
    <span class="mono">{{ log.created_at|date:"d M H:i" }}</span>
    <span><strong>{{ log.action }}</strong> · {{ log.target_type }}#{{ log.target_id }}</span>
    <span>{{ log.actor.name|default:"—" }}</span>
    <span class="mono" style="color:var(--text-faint)">{{ log.payload|stringformat:"s"|truncatechars:40 }}</span>
  </div>
  {% empty %}<p>Sin eventos todavía.</p>{% endfor %}
</div>
{% endblock %}
```

- [ ] **Step 5: Tests `pot/tests/test_views.py`**

```python
import pytest
from django.urls import reverse
from accounts.models import User
from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_manage_players_requires_gestor(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("pot:manage_players"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_create_player_shows_temp_password(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    r = client.post(reverse("pot:player_new"), {
        "name": "Nuevo", "email": "nuevo@edisa.com", "dept": "Dev", "role": "jugador",
    })
    assert r.status_code == 200
    assert b"Contrase\xc3\xb1a temporal" in r.content
    assert User.objects.filter(email="nuevo@edisa.com").exists()


@pytest.mark.django_db
def test_toggle_payment(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    p = UserFactory()
    from pot.models import Payment
    Payment.objects.create(player=p, paid=False)
    r = client.post(reverse("pot:player_toggle_payment", args=[p.id]))
    assert r.status_code == 302
    assert Payment.objects.get(player=p).paid is True
```

- [ ] **Step 6: Tests + commit**

```bash
pytest pot/tests/test_views.py -v
git add pot/ templates/pot/ templates/accounts/audit_log.html
git commit -m "feat(pot): gestión de jugadores, pagos, reset de contraseña, premios y auditoría"
```

---

## Fase 6 — Pantalla Estadísticas

### Tarea 6.1: `StatsView` con KPIs, donut y endpoint JSON del gráfico

**Files:**
- Modify: `stats/urls.py`
- Create: `stats/views.py`
- Create: `templates/stats/stats.html`
- Test: `stats/tests/test_view.py`

- [ ] **Step 1: `stats/urls.py`**

```python
from django.urls import path
from . import views

urlpatterns = [
    path("", views.StatsView.as_view(), name="dashboard"),
    path("chart-data.json", views.ChartDataView.as_view(), name="chart_data"),
]
```

- [ ] **Step 2: `stats/views.py`**

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import JsonResponse
from django.shortcuts import render
from django.views import View

from stats.services.history import per_player_history
from stats.services.kpis import donut, kpis


class StatsView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "stats/stats.html", {
            "kpis": kpis(request.user),
            "donut": donut(request.user.id),
        })


class ChartDataView(LoginRequiredMixin, View):
    def get(self, request):
        h = per_player_history()
        return JsonResponse({"history": h, "me": request.user.id})
```

- [ ] **Step 3: `templates/stats/stats.html`**

```django
{% extends "base.html" %}
{% load static %}
{% block main %}
<h1 class="display" style="font-size:28px">Tu rendimiento</h1>
{% if kpis %}
<div style="display:grid;grid-template-columns:repeat(4,1fr);gap:14px;margin-top:18px">
  <article class="glass" style="padding:18px;border-radius:18px"><div class="eyebrow">% Aciertos</div><div class="display" style="font-size:32px">{{ kpis.hit_rate|floatformat:0 }}%</div></article>
  <article class="glass" style="padding:18px;border-radius:18px"><div class="eyebrow">vs Media</div><div class="display" style="font-size:32px">{{ kpis.vs_avg|floatformat:1 }}</div></article>
  <article class="glass" style="padding:18px;border-radius:18px"><div class="eyebrow">vs Líder</div><div class="display" style="font-size:32px">{{ kpis.vs_leader }}</div></article>
  <article class="glass" style="padding:18px;border-radius:18px"><div class="eyebrow">Percentil</div><div class="display" style="font-size:32px">Top {{ kpis.percentile|floatformat:0 }}%</div></article>
</div>
{% else %}
<p class="glass" style="padding:18px">Aún no hay partidos resueltos para calcular tus estadísticas.</p>
{% endif %}

<div class="stats-grid" style="display:grid;grid-template-columns:4fr 1fr;gap:14px;margin-top:18px">
  <article class="glass" style="padding:18px;border-radius:18px;min-height:360px">
    <div class="eyebrow">EVOLUCIÓN</div>
    <div data-rank-chart data-src="{% url 'stats:chart_data' %}">
      <noscript><p>Activa JavaScript para ver el gráfico de evolución.</p></noscript>
    </div>
  </article>
  <article class="glass" style="padding:18px;border-radius:18px">
    <div class="eyebrow">PRONÓSTICOS</div>
    {% with d=donut %}
    {% with total=d.exact|add:d.partial|add:d.fail %}
    <div class="display" style="font-size:30px;color:var(--c-cyan)">{% if total %}{{ d.partial|add:d.exact|floatformat:0 }}/{{ total }}{% else %}—{% endif %}</div>
    <ul style="list-style:none;padding:0;margin:10px 0;font-size:13px">
      <li>Exactos · {{ d.exact }}</li>
      <li>Aciertos · {{ d.partial }}</li>
      <li>Fallos · {{ d.fail }}</li>
    </ul>
    {% endwith %}
    {% endwith %}
  </article>
</div>
{% endblock %}
{% block scripts %}<script type="module" src="{% static 'js/rank-chart.js' %}"></script>{% endblock %}
```

- [ ] **Step 4: Tests + commit**

```python
# stats/tests/test_view.py
import pytest
from django.urls import reverse
from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_stats_requires_login(client):
    r = client.get(reverse("stats:dashboard"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_stats_renders(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("stats:dashboard"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_chart_data_returns_json(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("stats:chart_data"))
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/json")
```

```bash
pytest stats/tests/test_view.py -v
git add stats/ templates/stats/
git commit -m "feat(stats): pantalla con KPIs, donut, endpoint JSON del gráfico"
```

---

## Fase 7 — JS vanilla (módulos)

### Tarea 7.1: `static/js/theme.js` y `toast.js`

**Files:**
- Create: `static/js/theme.js`
- Create: `static/js/toast.js`

- [ ] **Step 1: `static/js/theme.js`**

```javascript
const root = document.documentElement;
const KEY = "porra26:theme";

function apply(theme) {
  root.setAttribute("data-theme", theme);
}

function init() {
  const saved = localStorage.getItem(KEY);
  if (saved) apply(saved);
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      localStorage.setItem(KEY, next);
    });
  });
}

init();
```

- [ ] **Step 2: `static/js/toast.js`**

```javascript
const box = document.getElementById("dj-messages");
if (box) {
  for (const span of box.querySelectorAll("[data-msg]")) {
    const t = document.createElement("div");
    t.className = "glass pop toast";
    t.style.cssText = "position:fixed;bottom:24px;left:50%;transform:translateX(-50%);z-index:80;padding:13px 20px;border-radius:16px;display:flex;align-items:center;gap:10px";
    t.textContent = span.dataset.msg;
    document.body.appendChild(t);
    setTimeout(() => t.remove(), 2600);
  }
}
```

- [ ] **Step 3: Commit**

```bash
git add static/js/theme.js static/js/toast.js
git commit -m "feat(js): theme.js (dark/light) y toast.js (mensajes Django)"
```

---

### Tarea 7.2: `anim-num.js`, `countdown.js`, `modal.js`

**Files:**
- Create: `static/js/anim-num.js`
- Create: `static/js/countdown.js`
- Create: `static/js/modal.js`

- [ ] **Step 1: `static/js/anim-num.js`**

```javascript
function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

function animate(el) {
  const target = Number(el.dataset.animNum || "0");
  const start = performance.now();
  const dur = 900;
  function tick(now) {
    const t = Math.min(1, (now - start) / dur);
    el.textContent = Math.round(target * easeOutCubic(t));
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

document.querySelectorAll("[data-anim-num]").forEach(animate);
```

- [ ] **Step 2: `static/js/countdown.js`**

```javascript
function pad(n) { return String(n).padStart(2, "0"); }

function update(el, target) {
  const ms = target - Date.now();
  if (ms <= 0) { el.textContent = "00:00:00"; el.classList.add("expired"); return; }
  const h = Math.floor(ms / 3600000);
  const m = Math.floor((ms / 60000) % 60);
  const s = Math.floor((ms / 1000) % 60);
  el.textContent = `${pad(h)}:${pad(m)}:${pad(s)}`;
  if (ms < 3600000) el.classList.add("under-hour");
}

document.querySelectorAll("[data-countdown-to]").forEach((el) => {
  const target = new Date(el.dataset.countdownTo).getTime();
  update(el, target);
  setInterval(() => update(el, target), 1000);
});
```

- [ ] **Step 3: `static/js/modal.js`**

```javascript
function openModal(url) {
  fetch(url, { headers: { "X-Requested-With": "fetch" } })
    .then((r) => r.text())
    .then((html) => {
      const wrap = document.createElement("div");
      wrap.className = "modal-overlay";
      wrap.style.cssText = "position:fixed;inset:0;z-index:90;background:rgba(0,0,0,0.55);backdrop-filter:blur(8px);display:grid;place-items:center";
      wrap.innerHTML = html;
      document.body.appendChild(wrap);

      const onClose = () => wrap.remove();
      wrap.addEventListener("click", (e) => { if (e.target === wrap) onClose(); });
      document.addEventListener("keydown", (e) => { if (e.key === "Escape") onClose(); }, { once: true });
    });
}

document.addEventListener("click", (e) => {
  const a = e.target.closest("[data-modal-url]");
  if (!a) return;
  e.preventDefault();
  openModal(a.dataset.modalUrl);
});
```

- [ ] **Step 4: Commit**

```bash
git add static/js/anim-num.js static/js/countdown.js static/js/modal.js
git commit -m "feat(js): anim-num, countdown y modal vanilla"
```

---

### Tarea 7.3: `rank-chart.js` (SVG con tooltip)

**Files:**
- Create: `static/js/rank-chart.js`

- [ ] **Step 1: Implementación mínima viable**

```javascript
async function build(container) {
  const src = container.dataset.src;
  const data = await fetch(src).then((r) => r.json());
  const series = Object.entries(data.history);
  if (!series.length) { container.innerHTML = "<p>Sin datos todavía.</p>"; return; }

  const W = container.clientWidth || 700, H = 340, PAD = 30;
  const allIdx = series[0][1].map((p) => p.idx);
  const xMax = Math.max(...allIdx);
  const yMax = Math.max(...series.flatMap(([, pts]) => pts.map((p) => p.pts))) || 1;

  const xScale = (i) => PAD + (i / xMax) * (W - 2 * PAD);
  const yScale = (v) => H - PAD - (v / yMax) * (H - 2 * PAD);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.style.width = "100%"; svg.style.height = "auto";

  for (const [pid, pts] of series) {
    const d = pts.map((p, k) => `${k === 0 ? "M" : "L"} ${xScale(p.idx)} ${yScale(p.pts)}`).join(" ");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    const isMe = Number(pid) === data.me;
    path.setAttribute("stroke", isMe ? "var(--accent)" : "var(--border-hi)");
    path.setAttribute("stroke-width", isMe ? "3" : "1.5");
    svg.appendChild(path);
  }
  container.innerHTML = "";
  container.appendChild(svg);
}

document.querySelectorAll("[data-rank-chart]").forEach(build);
```

- [ ] **Step 2: Commit**

```bash
git add static/js/rank-chart.js
git commit -m "feat(js): rank-chart.js — gráfico SVG mínimo viable de evolución"
```

> Iteración futura: tooltip, etiquetas de nombre en el extremo derecho, modos Posición/Puntos, "mostrar todos". Se añadirán en sub-tareas si llegan a ser necesarias para v1.

---

## Fase 8 — Calendario del Mundial y seed inicial

### Tarea 8.1: Selecciones + fixture parcial de partidos

**Files:**
- Create: `fixtures/teams.json`
- Create: `fixtures/world_cup_2026.json` (parcial, ampliable)

- [ ] **Step 1: `fixtures/teams.json`**

Empezar con las 16 del prototipo (`design-reference/data.jsx` → array `TEAMS`); luego ampliar a las 48 oficiales cuando se publique el calendario:

```json
[
  {"model":"competition.team","pk":"ESP","fields":{"name":"España","flag":"🇪🇸"}},
  {"model":"competition.team","pk":"ARG","fields":{"name":"Argentina","flag":"🇦🇷"}},
  {"model":"competition.team","pk":"FRA","fields":{"name":"Francia","flag":"🇫🇷"}},
  {"model":"competition.team","pk":"BRA","fields":{"name":"Brasil","flag":"🇧🇷"}},
  {"model":"competition.team","pk":"ENG","fields":{"name":"Inglaterra","flag":"🏴󠁧󠁢󠁥󠁮󠁧󠁿"}},
  {"model":"competition.team","pk":"POR","fields":{"name":"Portugal","flag":"🇵🇹"}},
  {"model":"competition.team","pk":"GER","fields":{"name":"Alemania","flag":"🇩🇪"}},
  {"model":"competition.team","pk":"NED","fields":{"name":"Países Bajos","flag":"🇳🇱"}},
  {"model":"competition.team","pk":"MEX","fields":{"name":"México","flag":"🇲🇽"}},
  {"model":"competition.team","pk":"USA","fields":{"name":"Estados Unidos","flag":"🇺🇸"}},
  {"model":"competition.team","pk":"CAN","fields":{"name":"Canadá","flag":"🇨🇦"}},
  {"model":"competition.team","pk":"JPN","fields":{"name":"Japón","flag":"🇯🇵"}},
  {"model":"competition.team","pk":"CRO","fields":{"name":"Croacia","flag":"🇭🇷"}},
  {"model":"competition.team","pk":"MAR","fields":{"name":"Marruecos","flag":"🇲🇦"}},
  {"model":"competition.team","pk":"URU","fields":{"name":"Uruguay","flag":"🇺🇾"}},
  {"model":"competition.team","pk":"BEL","fields":{"name":"Bélgica","flag":"🇧🇪"}}
]
```

- [ ] **Step 2: `fixtures/world_cup_2026.json`** con 4 partidos de muestra

```json
[
  {"model":"competition.match","pk":1,"fields":{"round":"groups","group":"A","matchday":1,"home":"MEX","away":"USA","kickoff":"2026-06-11T18:00:00Z"}},
  {"model":"competition.match","pk":2,"fields":{"round":"groups","group":"A","matchday":1,"home":"CAN","away":"JPN","kickoff":"2026-06-11T21:00:00Z"}},
  {"model":"competition.match","pk":3,"fields":{"round":"groups","group":"B","matchday":1,"home":"ESP","away":"POR","kickoff":"2026-06-12T18:00:00Z"}},
  {"model":"competition.match","pk":4,"fields":{"round":"groups","group":"B","matchday":1,"home":"ARG","away":"BRA","kickoff":"2026-06-12T21:00:00Z"}}
]
```

> El fichero completo de los 104 partidos se generará cuando la FIFA publique el calendario definitivo. Hasta entonces, esta muestra basta para desarrollar.

- [ ] **Step 3: Cargar fixtures en dev y verificar**

```bash
python manage.py migrate --settings=porra26.settings.dev
python manage.py loaddata fixtures/rounds.json fixtures/teams.json fixtures/world_cup_2026.json --settings=porra26.settings.dev
python manage.py shell --settings=porra26.settings.dev -c "from competition.models import Match; print(Match.objects.count())"
```

Esperado: 4.

- [ ] **Step 4: Commit**

```bash
git add fixtures/
git commit -m "chore(fixtures): seed inicial de 16 selecciones y 4 partidos de muestra"
```

---

## Fase 9 — Despliegue en PythonAnywhere y documentación operativa

### Tarea 9.1: Documentación de despliegue (`docs/DEPLOY.md`)

**Files:** Create: `docs/DEPLOY.md`

- [ ] **Step 1: Escribir documento**

Contenido: pasos 1-11 de la sección 7.3 del spec (clone, virtualenv, BD MySQL, .env, migrate, loaddata, createsuperuser, web app, static mapping, reload). + scripts `docs/scripts/deploy.sh` y `docs/scripts/backup.sh`.

- [ ] **Step 2: Crear `docs/scripts/deploy.sh`**

```bash
#!/usr/bin/env bash
set -euo pipefail
cd ~/apuestas-interna
git pull
source ~/.virtualenvs/porra26/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --no-input
touch /var/www/${PA_USER}_pythonanywhere_com_wsgi.py
```

`chmod +x docs/scripts/deploy.sh`.

- [ ] **Step 3: Crear `docs/scripts/backup.sh`** (también ejecutable)

```bash
#!/usr/bin/env bash
set -euo pipefail
mkdir -p ~/backups
mysqldump -u "$MYSQL_USER" -p"$MYSQL_PASSWORD" -h "$MYSQL_HOST" "$MYSQL_NAME" | gzip > ~/backups/porra26-$(date +%F).sql.gz
find ~/backups -name "porra26-*.sql.gz" -mtime +30 -delete
```

- [ ] **Step 4: Commit**

```bash
git add docs/DEPLOY.md docs/scripts/
git commit -m "docs: guía de despliegue en PythonAnywhere y scripts deploy/backup"
```

---

### Tarea 9.2: `docs/SYNC_DESIGN.md` y `docs/RUNBOOK.md`

**Files:**
- Create: `docs/SYNC_DESIGN.md`
- Create: `docs/RUNBOOK.md`

- [ ] **Step 1: `docs/SYNC_DESIGN.md`** (procedimiento "sincroniza el diseño" — ver spec §5)

- [ ] **Step 2: `docs/RUNBOOK.md`** (reset de contraseña por consola, regenerar standings, restaurar backup)

- [ ] **Step 3: Commit**

```bash
git add docs/SYNC_DESIGN.md docs/RUNBOOK.md
git commit -m "docs: SYNC_DESIGN y RUNBOOK"
```

---

### Tarea 9.3: GitHub Actions CI

**Files:** Create: `.github/workflows/ci.yml`

- [ ] **Step 1: Escribir workflow**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
          cache: "pip"
      - run: pip install -r requirements-dev.txt
      - run: ruff check .
      - run: ruff format --check .
      - run: pytest -q --cov=. --cov-fail-under=70
```

- [ ] **Step 2: Commit**

```bash
git add .github/workflows/ci.yml
git commit -m "ci: workflow de lint + tests con cobertura mínima 70%"
```

---

## Fase 10 — Cierre

### Tarea 10.1: Validación de criterios de aceptación (manual)

- [ ] **Step 1:** Arrancar dev (`python manage.py runserver --settings=porra26.settings.dev`).
- [ ] **Step 2:** Recorrer la lista de 11 criterios del spec §8.3, marcando cada uno.
- [ ] **Step 3:** Capturas de pantalla lado a lado vs prototipo (`design-reference/PORRA 26.html`), tema oscuro y claro.
- [ ] **Step 4:** Tag de versión:

```bash
git tag -a v0.1.0 -m "PORRA 26 v0.1.0 — primer release interno"
```

---

## Notas finales

- **Cuando una tarea modifique sustancialmente el `design-reference/`**, regenerar el prototipo y volcar de nuevo (NO editar a mano). La fidelidad visual se valida siempre contra esa carpeta.
- **`PLAN.md` original** queda como narrativa de fases; este plan lo reemplaza operativamente.
- **Riesgo principal:** completar las 24 SVG de iconos a la altura del prototipo (Tarea 3.3) — extraer manualmente desde `design-reference/shared.jsx`.




