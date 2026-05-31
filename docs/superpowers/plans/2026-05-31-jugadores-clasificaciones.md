# Roles, perfil organizativo y rankings — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir el `role` enum por dos flags independientes (`is_jugador`, `is_gestor`), añadir `sede`/`puesto` y enum `dept`, dar al jugador una pantalla "Mi perfil", convertir el alta/edición de jugadores en una modal real, y crear una página "Rankings" con tres pestañas (Sede / Puesto / Departamento).

**Architecture:** Cambios sobre el modelo `accounts.User` con una sola migración (schema + data + cleanup). Se aprovecha el `static/js/modal.js` ya existente (hoy no carga ni soporta POST) ampliándolo a un protocolo basado en headers `X-Modal-Redirect` / `X-Modal-Errors`. La página Rankings vive en el app `stats/` y reutiliza el servicio `standings()` existente para no duplicar agregaciones.

**Tech Stack:** Django 5.1, pytest-django, vanilla JS (ES modules), CSS con tokens OKLCH. Sin nuevas dependencias.

**Spec de referencia:** `docs/superpowers/specs/2026-05-31-jugadores-clasificaciones-design.md`

---

## Convenciones del plan

- Antes de empezar: branch `git checkout -b feat/roles-rankings` desde `main`.
- Cada Task termina en `pytest -x && ruff check . && commit`.
- Mensajes de commit en español, mayúscula inicial, imperativo, prefijo convencional (`feat:`, `refactor:`, `test:`, `docs:`, `chore:`).
- Si una Task incluye varios archivos, agrupa todo en un único commit (la Task es la unidad).

---

## Task 1: Choices de `dept`, `sede` y `puesto` en el modelo

**Files:**
- Modify: `accounts/models.py`
- Test: `accounts/tests/test_user_model.py`

- [ ] **Step 1: Escribir tests fallidos para los nuevos choices**

Añade al final de `accounts/tests/test_user_model.py`:

```python
@pytest.mark.django_db
def test_user_dept_accepts_known_choice():
    u = User.objects.create_user(email="d@edisa.com", password="pw", name="D", dept="nominas")
    assert u.dept == "nominas"


@pytest.mark.django_db
def test_user_sede_defaults_blank():
    u = User.objects.create_user(email="s@edisa.com", password="pw", name="S")
    assert u.sede == ""


@pytest.mark.django_db
def test_user_puesto_defaults_blank():
    u = User.objects.create_user(email="p@edisa.com", password="pw", name="P")
    assert u.puesto == ""


@pytest.mark.django_db
def test_user_is_jugador_default_true():
    u = User.objects.create_user(email="j@edisa.com", password="pw", name="J")
    assert u.is_jugador is True


@pytest.mark.django_db
def test_user_is_gestor_default_false():
    u = User.objects.create_user(email="g2@edisa.com", password="pw", name="G2")
    assert u.is_gestor is False


@pytest.mark.django_db
def test_superuser_is_admin_not_jugador():
    u = User.objects.create_superuser(email="root@edisa.com", password="pw", name="Root")
    assert u.is_staff and u.is_superuser
    assert u.is_jugador is False
    assert u.is_gestor is False
```

Y **elimina** los tests `test_create_user_defaults_role_to_jugador` y `test_create_superuser_is_gestor` (el campo `role` desaparece).

- [ ] **Step 2: Verificar que los tests fallan**

```
pytest accounts/tests/test_user_model.py -x
```

Esperado: errores `AttributeError: ... has no attribute 'is_jugador'` / `sede` / `puesto`.

- [ ] **Step 3: Editar `accounts/models.py`**

Reemplaza el contenido de la clase `User` (mantén `AuditLog` intacto) por:

```python
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.db import models

from .managers import UserManager


class User(AbstractBaseUser, PermissionsMixin):
    DEPT_CHOICES = [
        ("nominas", "Nóminas"),
        ("gestion", "Gestión"),
        ("financiera", "Financiera"),
        ("pesca", "Pesca"),
    ]
    SEDE_CHOICES = [
        ("ourense", "Ourense"),
        ("vigo", "Vigo"),
        ("asturias", "Asturias"),
        ("madrid", "Madrid"),
        ("barcelona", "Barcelona"),
        ("latam", "Latinoamérica"),
    ]
    PUESTO_CHOICES = [
        ("desarrollo", "Desarrollo"),
        ("sistemas", "Sistemas"),
        ("consultoria", "Consultoría"),
        ("administracion", "Administración"),
    ]

    email = models.EmailField(unique=True)
    name = models.CharField(max_length=120)
    dept = models.CharField(max_length=20, choices=DEPT_CHOICES, blank=True)
    sede = models.CharField(max_length=20, choices=SEDE_CHOICES, blank=True)
    puesto = models.CharField(max_length=20, choices=PUESTO_CHOICES, blank=True)
    is_jugador = models.BooleanField(default=True)
    is_gestor = models.BooleanField(default=False)
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

> El campo `role` se elimina aquí; la migración se encarga en la Task 3.

- [ ] **Step 4: Actualizar `accounts/managers.py`**

Reemplaza el contenido completo por:

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
        extra.setdefault("is_jugador", True)
        extra.setdefault("is_gestor", False)
        extra.setdefault("is_staff", False)
        extra.setdefault("is_superuser", False)
        return self._create_user(email, password, **extra)

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault("is_jugador", False)
        extra.setdefault("is_gestor", False)
        extra.setdefault("is_staff", True)
        extra.setdefault("is_superuser", True)
        extra.setdefault("must_change_password", False)
        return self._create_user(email, password, **extra)
```

- [ ] **Step 5: Confirmar que los tests pasan en modelo y manager**

```
pytest accounts/tests/test_user_model.py -x
```

Esperado: tests del modelo en verde. Cualquier test que falle por `role` o por las factories es esperado y se arregla en las Tasks 2 y 3 antes de commitear.

> No hagas commit aún. Continúa con Task 2 antes del primer commit; los cambios de modelo, factories y migración van juntos para no dejar el repo en estado roto.

---

## Task 2: Factories y test de audit log

**Files:**
- Modify: `accounts/tests/factories.py`
- Modify: `accounts/tests/test_audit_log.py`

- [ ] **Step 1: Reescribir `accounts/tests/factories.py`**

```python
import factory

from accounts.models import User


class UserFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = User

    email = factory.Sequence(lambda n: f"user{n}@edisa.com")
    name = factory.Faker("name", locale="es_ES")
    dept = "desarrollo"  # se ignora — `dept` ya no acepta "desarrollo"; sobrescribimos abajo
    is_jugador = True
    must_change_password = False

    @classmethod
    def _create(cls, model_class, *args, **kwargs):
        kwargs.pop("dept", None)  # quita el valor inválido por defecto
        password = kwargs.pop("password", "test-password")
        user = model_class.objects.create_user(password=password, **kwargs)
        return user


class GestorFactory(UserFactory):
    is_jugador = True
    is_gestor = True
```

> Nota: dejamos a las pruebas que pasen `dept="nominas"` explícitamente si necesitan agrupar por departamento. El factory por defecto crea usuarios sin departamento, lo que coincide con jugadores recién dados de alta.

- [ ] **Step 2: Actualizar `accounts/tests/test_audit_log.py`**

Reemplaza la línea de creación del actor:

```python
actor = User.objects.create_user(
    email="g@edisa.com", password="x", name="G", is_gestor=True
)
```

- [ ] **Step 3: Lanzar la suite parcial para verificar**

```
pytest accounts/ -x
```

Esperado: pasan los tests de `accounts/` salvo los que dependen de la migración (no debería haber ninguno).

> Sigue sin commitear: continúa con la Task 3.

---

## Task 3: Migración `accounts.0003_role_split_and_org_fields`

**Files:**
- Create: `accounts/migrations/0003_role_split_and_org_fields.py`

- [ ] **Step 1: Crear la migración manualmente**

Crea `accounts/migrations/0003_role_split_and_org_fields.py` con:

```python
from django.db import migrations, models


DEPT_KEYS = {
    "nóminas": "nominas",
    "nominas": "nominas",
    "gestión": "gestion",
    "gestion": "gestion",
    "financiera": "financiera",
    "pesca": "pesca",
}


def forwards(apps, schema_editor):
    User = apps.get_model("accounts", "User")
    for u in User.objects.all():
        u.is_gestor = (u.role == "gestor")
        u.is_jugador = not u.is_superuser
        normalized = DEPT_KEYS.get((u.dept or "").strip().lower(), "")
        u.dept = normalized
        u.save(update_fields=["is_gestor", "is_jugador", "dept"])


def reverse_noop(apps, schema_editor):
    # No restauramos el campo `role`: la separación en flags es irreversible.
    pass


class Migration(migrations.Migration):

    dependencies = [
        ("accounts", "0002_auditlog"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="is_jugador",
            field=models.BooleanField(default=True),
        ),
        migrations.AddField(
            model_name="user",
            name="is_gestor",
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name="user",
            name="sede",
            field=models.CharField(
                blank=True,
                choices=[
                    ("ourense", "Ourense"),
                    ("vigo", "Vigo"),
                    ("asturias", "Asturias"),
                    ("madrid", "Madrid"),
                    ("barcelona", "Barcelona"),
                    ("latam", "Latinoamérica"),
                ],
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="puesto",
            field=models.CharField(
                blank=True,
                choices=[
                    ("desarrollo", "Desarrollo"),
                    ("sistemas", "Sistemas"),
                    ("consultoria", "Consultoría"),
                    ("administracion", "Administración"),
                ],
                max_length=20,
            ),
        ),
        migrations.AlterField(
            model_name="user",
            name="dept",
            field=models.CharField(blank=True, max_length=20),
        ),
        migrations.RunPython(forwards, reverse_noop),
        migrations.AlterField(
            model_name="user",
            name="dept",
            field=models.CharField(
                blank=True,
                choices=[
                    ("nominas", "Nóminas"),
                    ("gestion", "Gestión"),
                    ("financiera", "Financiera"),
                    ("pesca", "Pesca"),
                ],
                max_length=20,
            ),
        ),
        migrations.RemoveField(
            model_name="user",
            name="role",
        ),
    ]
```

- [ ] **Step 2: Verificar que no hay `makemigrations` pendientes**

```
python manage.py makemigrations --check --dry-run
```

Esperado: `No changes detected`.

- [ ] **Step 3: Aplicar la migración localmente**

```
python manage.py migrate accounts
```

Esperado: aplica `0003_role_split_and_org_fields` sin errores.

- [ ] **Step 4: Lanzar la suite completa**

```
pytest -x
```

Esperado: pasan los tests de `accounts/` y de cualquier otro módulo que usase `UserFactory`/`GestorFactory`. Si algún test de `competition/`, `pot/` o `stats/` falla por `role`, **anótalo** — se arregla en las Tasks 4-6.

- [ ] **Step 5: Commit (tasks 1+2+3 juntas)**

```
git add accounts/
git commit -m "feat: separar role en is_jugador/is_gestor y añadir sede/puesto

- Modelo `User`: elimina `role`; añade `is_jugador`, `is_gestor`,
  `sede`, `puesto` y convierte `dept` en enum.
- Migración 0003 con backfill: is_gestor=(role=='gestor'),
  is_jugador=not is_superuser, dept normalizado a enum o vacío.
- Manager: create_user marca is_jugador=True; create_superuser
  desactiva ambos flags (admin invisible en juego).
- Factories actualizadas."
```

---

## Task 4: Renombrar `RoleRequiredMixin` → `GestorRequiredMixin`

**Files:**
- Modify: `accounts/mixins.py`
- Modify: `pot/views.py`
- Modify: `competition/views.py`
- Test: `pot/tests/test_views.py`, `competition/tests/test_competition_view.py`

- [ ] **Step 1: Sustituir el mixin en `accounts/mixins.py`**

```python
from django.contrib import messages
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import redirect


class GestorRequiredMixin(LoginRequiredMixin):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return self.handle_no_permission()
        if not request.user.is_gestor:
            messages.warning(request, "No tienes permisos para esa sección.")
            return redirect("competicion:dashboard")
        return super().dispatch(request, *args, **kwargs)
```

- [ ] **Step 2: Actualizar `pot/views.py`**

Cambia la importación:

```python
from accounts.mixins import GestorRequiredMixin
```

Y reemplaza en todas las vistas:

- `class ManagePlayersView(RoleRequiredMixin, View):` + `required_role = "gestor"` → `class ManagePlayersView(GestorRequiredMixin, View):`
- Igual para `PlayerFormView`, `ResetPasswordView`, `TogglePlayerActiveView`, `TogglePaymentView`, `PrizesSettingsView`, `AuditLogView` (todas las 7 vistas del fichero).
- Borra las líneas `required_role = "gestor"`.

- [ ] **Step 3: Actualizar `competition/views.py`**

Igual: `from accounts.mixins import GestorRequiredMixin`. Reemplaza `RoleRequiredMixin` en `ManageResultsView` y `ResultOfficialView`, borra `required_role`.

- [ ] **Step 4: Actualizar el test que usaba `role="jugador"`**

En `competition/tests/test_competition_view.py` busca:

```python
u = UserFactory(must_change_password=False, role="jugador")
```

y déjalo en:

```python
u = UserFactory(must_change_password=False)
```

(el factory ya pone `is_jugador=True`).

En `pot/tests/test_views.py`, en `test_create_player_shows_temp_password`, el `data` del POST contiene `"role": "jugador"`. Bórralo (la Task 9 reescribirá el form con flags, pero por ahora el form sigue siendo el original sin `role`).

- [ ] **Step 5: Ejecutar tests**

```
pytest -x
```

Esperado: verde en `accounts/`, `competition/`, `pot/` excepto el test `test_create_player_shows_temp_password` que fallará por validación del form (lo arregla la Task 8). Anota y sigue.

- [ ] **Step 6: Commit**

```
git add accounts/mixins.py pot/views.py competition/views.py competition/tests/ pot/tests/
git commit -m "refactor: renombrar RoleRequiredMixin a GestorRequiredMixin

Usa el flag is_gestor en lugar del enum role eliminado."
```

---

## Task 5: Filtrar `standings()` por `is_jugador`

**Files:**
- Modify: `competition/services/standings.py`
- Test: `competition/tests/test_standings.py` (nuevo)

- [ ] **Step 1: Escribir test fallido**

Crea `competition/tests/test_standings.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import Prediction
from competition.services.standings import standings
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_non_jugador_user_excluded_from_standings():
    gestor_puro = UserFactory(is_jugador=False, is_gestor=True)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(days=2))
    m.result_home, m.result_away = 1, 0
    m.finished_at = timezone.now()
    m.save()
    Prediction.objects.create(player=gestor_puro, match=m, home=1, away=0, earned=3)

    rows = standings()
    assert all(r.player_id != gestor_puro.id for r in rows)


@pytest.mark.django_db
def test_jugador_with_zero_points_still_listed():
    u = UserFactory(is_jugador=True)
    rows = standings()
    assert any(r.player_id == u.id and r.pts == 0 for r in rows)
```

- [ ] **Step 2: Verificar que el primero falla**

```
pytest competition/tests/test_standings.py -x
```

Esperado: el primer test falla (`gestor_puro` sí aparece).

- [ ] **Step 3: Modificar `competition/services/standings.py`**

Localiza el queryset `Prediction.objects.filter(player__is_active=True, ...)`:

```python
.filter(player__is_active=True, player__is_jugador=True, earned__isnull=False)
```

Y el segundo bloque `User.objects.filter(is_active=True).exclude(...)`:

```python
for u in User.objects.filter(is_active=True, is_jugador=True).exclude(id__in=seen)
```

- [ ] **Step 4: Verificar que pasan los tests**

```
pytest competition/tests/test_standings.py -x
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```
git add competition/services/standings.py competition/tests/test_standings.py
git commit -m "feat: standings excluye usuarios con is_jugador=False"
```

---

## Task 6: Guard `is_jugador` en `PredictView`

**Files:**
- Modify: `competition/views.py`
- Test: `competition/tests/test_competition_view.py`

- [ ] **Step 1: Test fallido**

Añade al final de `competition/tests/test_competition_view.py`:

```python
@pytest.mark.django_db
def test_predict_forbidden_for_non_jugador(client):
    gestor_puro = GestorFactory(must_change_password=False, is_jugador=False)
    client.force_login(gestor_puro)
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 1, "away": 0})
    assert r.status_code == 403
```

- [ ] **Step 2: Verificar fallo**

```
pytest competition/tests/test_competition_view.py::test_predict_forbidden_for_non_jugador -x
```

Esperado: FAIL (responde 302).

- [ ] **Step 3: Añadir guard en `PredictView`**

En `competition/views.py`, dentro de `PredictView.post` justo después de la primera línea `m = get_object_or_404(...)`:

```python
if not request.user.is_jugador:
    raise PermissionDenied("Solo los jugadores pueden pronosticar.")
```

Y el mismo guard en `PredictView.get` antes de cargar la predicción:

```python
if not request.user.is_jugador:
    raise PermissionDenied("Solo los jugadores pueden pronosticar.")
```

- [ ] **Step 4: Verificar verde**

```
pytest competition/tests/test_competition_view.py -x
```

- [ ] **Step 5: Commit**

```
git add competition/views.py competition/tests/test_competition_view.py
git commit -m "feat: PredictView prohíbe pronosticar a no jugadores"
```

---

## Task 7: `PlayerForm` con `sede`, `puesto` y flags

**Files:**
- Modify: `pot/forms.py`
- Test: `pot/tests/test_player_form.py` (nuevo)

- [ ] **Step 1: Test fallido**

Crea `pot/tests/test_player_form.py`:

```python
import pytest

from accounts.models import User
from pot.forms import PlayerForm


@pytest.fixture(autouse=True)
def _allow_domain(monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])


@pytest.mark.django_db
def test_player_form_accepts_all_org_fields():
    form = PlayerForm(data={
        "name": "Ana López",
        "email": "ana@edisa.com",
        "dept": "nominas",
        "sede": "vigo",
        "puesto": "desarrollo",
        "is_jugador": "on",
        "is_gestor": "",
    })
    assert form.is_valid(), form.errors
    user = form.save(commit=False)
    user.set_password("x")
    user.save()
    assert user.dept == "nominas"
    assert user.sede == "vigo"
    assert user.puesto == "desarrollo"
    assert user.is_jugador is True
    assert user.is_gestor is False


@pytest.mark.django_db
def test_player_form_allows_blank_org_fields():
    form = PlayerForm(data={
        "name": "Sin Datos",
        "email": "sin@edisa.com",
        "dept": "",
        "sede": "",
        "puesto": "",
        "is_jugador": "on",
        "is_gestor": "",
    })
    assert form.is_valid(), form.errors


@pytest.mark.django_db
def test_player_form_rejects_unknown_choice():
    form = PlayerForm(data={
        "name": "X",
        "email": "x@edisa.com",
        "dept": "marketing",  # no está en choices
        "sede": "",
        "puesto": "",
        "is_jugador": "on",
        "is_gestor": "",
    })
    assert not form.is_valid()
    assert "dept" in form.errors
```

- [ ] **Step 2: Verificar fallo**

```
pytest pot/tests/test_player_form.py -x
```

- [ ] **Step 3: Reescribir `pot/forms.py`**

```python
import secrets

from django import forms

from accounts.models import User
from accounts.validators import validate_email_domain


class PlayerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "dept", "sede", "puesto", "is_jugador", "is_gestor"]

    def clean_email(self):
        email = self.cleaned_data["email"].lower().strip()
        validate_email_domain(email)
        return email


def generate_temp_password() -> str:
    return secrets.token_urlsafe(9)
```

- [ ] **Step 4: Verificar verde**

```
pytest pot/tests/test_player_form.py -x
```

- [ ] **Step 5: Commit**

```
git add pot/forms.py pot/tests/test_player_form.py
git commit -m "feat(pot): PlayerForm con sede, puesto y flags de rol"
```

---

## Task 8: `PlayerFormView` con protocolo de modal (X-Modal headers)

**Files:**
- Modify: `pot/views.py`
- Test: `pot/tests/test_views.py`

- [ ] **Step 1: Tests fallidos**

Añade al final de `pot/tests/test_views.py`:

```python
@pytest.mark.django_db
def test_player_new_get_returns_fragment_with_x_modal_header(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:player_new"), HTTP_X_MODAL="1")
    assert r.status_code == 200
    assert b"<html" not in r.content.lower()  # fragmento, no página completa
    assert b"Nuevo jugador" in r.content


@pytest.mark.django_db
def test_player_edit_post_ok_returns_x_modal_redirect(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    p = UserFactory()
    r = client.post(
        reverse("pot:player_edit", args=[p.id]),
        {
            "name": "Nuevo Nombre",
            "email": p.email,
            "dept": "",
            "sede": "",
            "puesto": "",
            "is_jugador": "on",
            "is_gestor": "",
        },
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Redirect", "").endswith("/gestion/jugadores/")


@pytest.mark.django_db
def test_player_new_post_ok_redirects_to_password_reveal(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    r = client.post(
        reverse("pot:player_new"),
        {
            "name": "Nuevo",
            "email": "nuevo@edisa.com",
            "dept": "",
            "sede": "",
            "puesto": "",
            "is_jugador": "on",
            "is_gestor": "",
        },
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    # El header apunta al password reveal de ese usuario.
    redirect = r.headers.get("X-Modal-Redirect", "")
    user = User.objects.get(email="nuevo@edisa.com")
    assert redirect == reverse("pot:player_reveal", args=[user.id])


@pytest.mark.django_db
def test_player_form_invalid_returns_x_modal_errors_header(client, monkeypatch):
    monkeypatch.setattr("accounts.validators._allowed_domains", lambda: ["edisa.com"])
    client.force_login(GestorFactory(must_change_password=False))
    r = client.post(
        reverse("pot:player_new"),
        {"name": "", "email": "no-email", "dept": "", "sede": "", "puesto": "",
         "is_jugador": "on", "is_gestor": ""},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.headers.get("X-Modal-Errors") == "1"
```

> Y **elimina** el test `test_create_player_shows_temp_password`: ahora el flujo pasa por `X-Modal-Redirect` + `player_reveal`.

- [ ] **Step 2: Verificar fallo**

```
pytest pot/tests/test_views.py -x
```

Esperado: fallan los 4 nuevos (reverse a `pot:player_reveal` no existe; headers no se devuelven).

- [ ] **Step 3: Crear vista `PasswordRevealView` y URL**

Añade en `pot/views.py` justo después de `ResetPasswordView`:

```python
class PasswordRevealView(GestorRequiredMixin, View):
    """Pantalla que muestra la contraseña temporal generada para un alta.

    Se accede vía X-Modal-Redirect tras un POST exitoso de alta. Es
    información sensible y por eso vive en una página propia, fuera del
    overlay.
    """

    def get(self, request, pk):
        user = get_object_or_404(User, pk=pk)
        temp = request.session.pop(f"temp_pw_{pk}", None)
        if not temp:
            messages.warning(request, "La contraseña ya no está disponible.")
            return redirect("pot:manage_players")
        return render(
            request,
            "pot/_password_reveal.html",
            {"player": user, "temp_password": temp},
        )
```

En `pot/urls.py` añade:

```python
path("jugadores/<int:pk>/clave/", views.PasswordRevealView.as_view(), name="player_reveal"),
```

(justo después de `player_reset`).

- [ ] **Step 4: Reescribir `PlayerFormView`**

Reemplaza la clase entera por:

```python
class PlayerFormView(GestorRequiredMixin, View):
    def _is_modal(self, request) -> bool:
        return request.headers.get("X-Modal") == "1"

    def _get_object(self, pk):
        return User.objects.get(pk=pk) if pk else None

    def _render_form(self, request, form, obj):
        return render(
            request,
            "pot/_player_modal.html",
            {"form": form, "player": obj, "modal": self._is_modal(request)},
        )

    def get(self, request, pk=None):
        obj = self._get_object(pk)
        return self._render_form(request, PlayerForm(instance=obj), obj)

    def post(self, request, pk=None):
        obj = self._get_object(pk)
        form = PlayerForm(request.POST, instance=obj)
        if not form.is_valid():
            response = self._render_form(request, form, obj)
            if self._is_modal(request):
                response["X-Modal-Errors"] = "1"
            return response

        is_new = obj is None
        if is_new:
            temp = generate_temp_password()
            user = form.save(commit=False)
            user.set_password(temp)
            user.must_change_password = True
            user.save()
            Payment.objects.get_or_create(player=user)
            AuditLog.objects.create(
                actor=request.user, action="player_created",
                target_type="user", target_id=str(user.id), payload={},
            )
            request.session[f"temp_pw_{user.id}"] = temp
            target = reverse("pot:player_reveal", args=[user.id])
        else:
            form.save()
            target = reverse("pot:manage_players")

        messages.success(request, "Jugador guardado." if not is_new else "Jugador creado.")
        if self._is_modal(request):
            response = HttpResponse(status=200)
            response["X-Modal-Redirect"] = target
            return response
        return redirect(target)
```

Y añade los imports que falten arriba del fichero:

```python
from django.http import HttpResponse
from django.urls import reverse
```

- [ ] **Step 5: Plantilla `pot/_password_reveal.html` — comprueba que extiende `base.html`**

Léelo y asegúrate de que comienza con `{% extends "base.html" %}`. Si no lo hace (era un fragmento), envuelve su contenido entre:

```
{% extends "base.html" %}
{% block main %}
...
{% endblock %}
```

- [ ] **Step 6: Verde**

```
pytest pot/tests/test_views.py pot/tests/test_player_form.py -x
```

Algunos tests de la plantilla `_player_modal.html` aún fallarán porque la plantilla todavía es la vieja — la arregla la Task 9.

- [ ] **Step 7: Commit**

```
git add pot/views.py pot/urls.py pot/tests/test_views.py templates/pot/_password_reveal.html
git commit -m "feat(pot): PlayerFormView responde con X-Modal-Redirect / X-Modal-Errors

Mueve la contraseña temporal a una pantalla propia (player_reveal)
guardada en sesión: la modal no la enseña; el cliente navega allí
mediante el header X-Modal-Redirect."
```

---

## Task 9: Plantilla `_player_modal.html` como fragmento glass

**Files:**
- Rewrite: `templates/pot/_player_modal.html`

- [ ] **Step 1: Sustituir por completo el contenido**

```html
{% load icons %}
{% if not modal %}{% extends "base.html" %}{% block main %}{% endif %}
<section class="glass pop" style="width:min(520px,100%);border-radius:28px;padding:28px;background:var(--surface-solid)">
  <header style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <div>
      <span class="eyebrow">{% if player %}Editar{% else %}Alta{% endif %}</span>
      <h2 class="display" style="margin:6px 0 0;font-size:22px">{% if player %}{{ player.name }}{% else %}Nuevo jugador{% endif %}</h2>
    </div>
    <button type="button" data-modal-close class="btn btn-ghost" style="width:38px;height:38px;padding:0;border-radius:12px">{% icon "x" width=14 %}</button>
  </header>
  <form method="post" action="{% if player %}{% url 'pot:player_edit' player.id %}{% else %}{% url 'pot:player_new' %}{% endif %}">
    {% csrf_token %}
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="field">
        <label for="id_name">Nombre completo</label>
        {{ form.name }}
        {% for e in form.name.errors %}<p style="color:var(--c-red);font-size:12px">{{ e }}</p>{% endfor %}
      </div>
      <div class="field">
        <label for="id_email">Correo corporativo (usuario)</label>
        {{ form.email }}
        {% for e in form.email.errors %}<p style="color:var(--c-red);font-size:12px">{{ e }}</p>{% endfor %}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="field"><label for="id_dept">Departamento</label>{{ form.dept }}</div>
        <div class="field"><label for="id_puesto">Puesto</label>{{ form.puesto }}</div>
      </div>
      <div class="field"><label for="id_sede">Sede</label>{{ form.sede }}</div>
      <div style="display:flex;gap:18px;padding:6px 0">
        <label class="check">{{ form.is_jugador }} Es jugador</label>
        <label class="check">{{ form.is_gestor }} Es gestor</label>
      </div>
      {% if not player %}
      <p class="mono" style="margin:0;font-size:11.5px;color:var(--text-faint);padding:10px 12px;border-radius:10px;background:var(--surface-hi)">
        Se generará una contraseña temporal que el jugador deberá cambiar al primer acceso. Sin recuperación automática: la restablece un gestor.
      </p>
      {% endif %}
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:22px">
      <button type="button" data-modal-close class="btn btn-ghost">Cancelar</button>
      <button class="btn btn-primary" type="submit">{% if player %}Guardar cambios{% else %}Crear jugador{% endif %}</button>
    </div>
  </form>
</section>
{% if not modal %}{% endblock %}{% endif %}
```

- [ ] **Step 2: Añadir clases CSS de input a los widgets del form**

En `pot/forms.py`, dentro de `PlayerForm`, sobrescribe los widgets para que apliquen `.input`:

```python
class PlayerForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "email", "dept", "sede", "puesto", "is_jugador", "is_gestor"]
        widgets = {
            "name":  forms.TextInput(attrs={"class": "input"}),
            "email": forms.EmailInput(attrs={"class": "input"}),
            "dept":   forms.Select(attrs={"class": "input"}),
            "sede":   forms.Select(attrs={"class": "input"}),
            "puesto": forms.Select(attrs={"class": "input"}),
            "is_jugador": forms.CheckboxInput(),
            "is_gestor":  forms.CheckboxInput(),
        }
```

- [ ] **Step 3: Verificar**

```
pytest pot/tests/ -x
```

Esperado: verde.

- [ ] **Step 4: Commit**

```
git add templates/pot/_player_modal.html pot/forms.py
git commit -m "feat(pot): plantilla _player_modal.html como fragmento glass

Sigue funcionando como página completa si el cliente no envía
X-Modal (fallback no-JS)."
```

---

## Task 10: Ampliar `static/js/modal.js` para POST + redirect/errores

**Files:**
- Rewrite: `static/js/modal.js`

- [ ] **Step 1: Reemplazar el módulo entero**

```js
const STATE = { wrap: null, escListener: null };

function close() {
  if (!STATE.wrap) return;
  STATE.wrap.remove();
  document.removeEventListener("keydown", STATE.escListener);
  STATE.wrap = null;
  STATE.escListener = null;
}

function mount(html) {
  close();
  const wrap = document.createElement("div");
  wrap.className = "ovl";
  wrap.innerHTML = html;
  wrap.addEventListener("click", (e) => {
    if (e.target === wrap) close();
  });
  wrap.addEventListener("click", (e) => {
    if (e.target.closest("[data-modal-close]")) close();
  });
  const form = wrap.querySelector("form");
  if (form) form.addEventListener("submit", onSubmit);
  STATE.wrap = wrap;
  STATE.escListener = (e) => { if (e.key === "Escape") close(); };
  document.addEventListener("keydown", STATE.escListener);
  document.body.appendChild(wrap);
}

async function onSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const res = await fetch(form.action, {
    method: "POST",
    body: data,
    headers: { "X-Modal": "1" },
  });
  const redirect = res.headers.get("X-Modal-Redirect");
  if (redirect) {
    window.location.assign(redirect);
    return;
  }
  if (res.headers.get("X-Modal-Errors") === "1") {
    const html = await res.text();
    mount(html);
    return;
  }
  if (res.ok) {
    close();
    window.location.reload();
  }
}

export async function openModal(url) {
  const res = await fetch(url, { headers: { "X-Modal": "1" } });
  const html = await res.text();
  mount(html);
}

export function closeModal() {
  close();
}

document.addEventListener("click", (event) => {
  const trigger = event.target.closest("[data-modal-url]");
  if (!trigger) return;
  event.preventDefault();
  openModal(trigger.dataset.modalUrl);
});
```

- [ ] **Step 2: Cargar el módulo en `templates/base.html`**

Justo después de la línea `<script type="module" src="{% static 'js/toast.js' %}"></script>` añade:

```html
<script type="module" src="{% static 'js/modal.js' %}"></script>
```

- [ ] **Step 3: Smoke test manual (anota mentalmente)**

```
python manage.py runserver
```

Logueado como gestor, visitar `/gestion/jugadores/` (después de la Task 12 el botón será data-modal-url). Por ahora, comprueba con la consola del navegador que `window` no tira errores al cargar la página.

- [ ] **Step 4: Commit**

```
git add static/js/modal.js templates/base.html
git commit -m "feat(js): modal.js soporta POST con headers X-Modal-Redirect/Errors"
```

---

## Task 11: CSS — `.ovl`, `select.input`, `.check`

**Files:**
- Modify: `static/css/styles.css`

- [ ] **Step 1: Añadir reglas al final del fichero**

```css
/* ---------------- Modal overlay ---------------- */
.ovl {
  position: fixed; inset: 0; z-index: 60;
  display: grid; place-items: center; padding: 20px;
  background: oklch(0.1 0.03 280 / 0.6);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  animation: fade .25s ease both;
}

/* Selects con look de input glass */
select.input {
  appearance: none;
  -webkit-appearance: none;
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none' stroke='%238a8aa8' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><polyline points='1 1.5 6 6.5 11 1.5'/></svg>");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
}

/* Checkboxes de los formularios glass */
.check {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: var(--text);
  cursor: pointer;
}
.check input[type="checkbox"] {
  width: 18px; height: 18px; accent-color: var(--accent);
}
```

- [ ] **Step 2: Commit**

```
git add static/css/styles.css
git commit -m "feat(css): .ovl overlay, select.input chevron, .check checkbox"
```

---

## Task 12: Lista `manage_players.html` con chips de rol y columnas

**Files:**
- Modify: `templates/pot/manage_players.html`

- [ ] **Step 1: Reemplazar el contenido**

```html
{% extends "base.html" %}
{% load icons %}
{% block main %}
<header style="display:flex;align-items:center;gap:14px;margin-bottom:16px;flex-wrap:wrap">
  <h1 class="display" style="font-size:28px;margin:0">Jugadores</h1>
  <span class="chip chip-open">{{ active_count }} activos</span>
  <span class="chip">{{ paid_count }}/{{ total_count }} pagado</span>
  <button class="btn btn-primary" style="margin-left:auto" data-modal-url="{% url 'pot:player_new' %}">
    {% icon "plus" width=14 %} Nuevo jugador
  </button>
</header>
<form method="get" style="margin-bottom:12px">
  <input class="input" type="search" name="q" value="{{ q }}" placeholder="Buscar por nombre o correo" style="max-width:360px">
</form>
<div class="glass" style="border-radius:16px;overflow:hidden">
  <div style="display:grid;grid-template-columns:2.4fr 1.6fr 0.8fr 1fr 1.1fr 90px;padding:14px;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.18em;border-bottom:1px solid var(--border)">
    <span>Jugador</span><span>Organización</span><span>Puntos</span><span>Pago</span><span>Estado</span><span></span>
  </div>
  {% for p in players %}
  <div style="display:grid;grid-template-columns:2.4fr 1.6fr 0.8fr 1fr 1.1fr 90px;padding:14px;align-items:center;border-bottom:1px solid var(--border);{% if not p.is_active %}opacity:0.5{% endif %}">
    <div>
      <div style="display:flex;align-items:center;gap:7px;flex-wrap:wrap">
        <strong>{{ p.name }}</strong>
        {% if p.is_gestor %}<span class="chip" style="padding:1px 6px;font-size:9px;color:var(--c-cyan);border-color:oklch(from var(--c-cyan) l c h / 0.4)">gestor</span>{% endif %}
        {% if not p.is_jugador %}<span class="chip" style="padding:1px 6px;font-size:9px;color:var(--text-faint)">no juega</span>{% endif %}
      </div>
      <div class="mono" style="font-size:11px;color:var(--text-faint)">{{ p.email }}</div>
    </div>
    <div style="font-size:12.5px;color:var(--text-dim);line-height:1.5">
      {{ p.get_dept_display|default:"—" }}
      {% if p.sede %} · {{ p.get_sede_display }}{% endif %}
      {% if p.puesto %} · {{ p.get_puesto_display }}{% endif %}
    </div>
    <span class="display">—</span>
    <form method="post" action="{% url 'pot:player_toggle_payment' p.id %}" style="display:flex;align-items:center;gap:6px">
      {% csrf_token %}
      <button type="submit" class="chip {% if p.payment.paid %}chip-open{% endif %}">{{ p.payment.paid|yesno:"Pagado,Pendiente,Pendiente" }}</button>
    </form>
    <span class="chip {% if p.is_active %}chip-open{% endif %}">{{ p.is_active|yesno:"Activo,Baja" }}</span>
    <div style="display:flex;gap:6px">
      <button class="btn btn-ghost" data-modal-url="{% url 'pot:player_edit' p.id %}" style="width:32px;height:32px;padding:0">{% icon "edit" width=14 %}</button>
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

- [ ] **Step 2: Smoke test manual**

```
python manage.py runserver
```

Logueado como gestor, ve a `/gestion/jugadores/`. Verifica:
- Botón "Nuevo jugador" abre overlay (no navega).
- Click en lápiz de cualquier fila abre overlay con datos.
- Esc o clic fuera cierran.
- Submit con datos válidos cierra modal y muestra lista actualizada (o navega al password reveal en caso de alta).

- [ ] **Step 3: Commit**

```
git add templates/pot/manage_players.html
git commit -m "feat(pot): manage_players abre alta/edición en modal y muestra chips de rol y organización"
```

---

## Task 13: `ProfileView` + plantilla "Mi perfil"

**Files:**
- Create: `templates/accounts/profile.html`
- Modify: `accounts/forms.py`
- Modify: `accounts/views.py`
- Modify: `accounts/urls.py`
- Test: `accounts/tests/test_profile_view.py` (nuevo)

- [ ] **Step 1: Tests fallidos**

Crea `accounts/tests/test_profile_view.py`:

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_profile_requires_login(client):
    r = client.get(reverse("accounts:profile"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_profile_get_shows_user_fields(client):
    u = UserFactory(name="Ana", sede="vigo", puesto="desarrollo")
    client.force_login(u)
    r = client.get(reverse("accounts:profile"))
    assert r.status_code == 200
    assert b"Ana" in r.content
    assert b"vigo" in r.content or b"Vigo" in r.content


@pytest.mark.django_db
def test_profile_post_updates_fields(client):
    u = UserFactory(name="Antes", sede="")
    client.force_login(u)
    r = client.post(reverse("accounts:profile"), {
        "name": "Después",
        "dept": "nominas",
        "sede": "madrid",
        "puesto": "sistemas",
    })
    assert r.status_code == 302
    u.refresh_from_db()
    assert u.name == "Después"
    assert u.dept == "nominas"
    assert u.sede == "madrid"
    assert u.puesto == "sistemas"


@pytest.mark.django_db
def test_profile_post_cannot_grant_flags(client):
    u = UserFactory(is_gestor=False, is_jugador=True)
    client.force_login(u)
    client.post(reverse("accounts:profile"), {
        "name": u.name,
        "dept": "",
        "sede": "",
        "puesto": "",
        "is_gestor": "on",      # debería ser ignorado
        "is_jugador": "",       # debería ser ignorado
        "email": "hacker@evil.com",
    })
    u.refresh_from_db()
    assert u.is_gestor is False
    assert u.is_jugador is True
    assert u.email != "hacker@evil.com"
```

- [ ] **Step 2: Verificar fallo**

```
pytest accounts/tests/test_profile_view.py -x
```

- [ ] **Step 3: Añadir `ProfileForm` al final de `accounts/forms.py`**

```python
from accounts.models import User


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "dept", "sede", "puesto"]
        widgets = {
            "name":   forms.TextInput(attrs={"class": "input"}),
            "dept":   forms.Select(attrs={"class": "input"}),
            "sede":   forms.Select(attrs={"class": "input"}),
            "puesto": forms.Select(attrs={"class": "input"}),
        }
```

(El import de `User` puede ir junto al resto si ya existe; si no, añádelo).

- [ ] **Step 4: Añadir `ProfileView` a `accounts/views.py`**

```python
from .forms import ChangePasswordForm, LoginForm, ProfileForm


class ProfileView(LoginRequiredMixin, View):
    template_name = "accounts/profile.html"

    def get(self, request):
        return render(request, self.template_name, {"form": ProfileForm(instance=request.user)})

    def post(self, request):
        form = ProfileForm(request.POST, instance=request.user)
        if form.is_valid():
            form.save()
            messages.success(request, "Perfil actualizado.")
            return redirect("accounts:profile")
        return render(request, self.template_name, {"form": form})
```

- [ ] **Step 5: Ruta en `accounts/urls.py`**

```python
path("perfil/", views.ProfileView.as_view(), name="profile"),
```

(añade dentro de `urlpatterns`).

Y revisa `accounts/middleware.py`: añade `/perfil/` a `EXEMPT`? **No** — un usuario con `must_change_password` debe cambiar la contraseña antes de poder editar el perfil; el middleware actual lo redirigirá correctamente.

- [ ] **Step 6: Crear `templates/accounts/profile.html`**

```html
{% extends "base.html" %}
{% block main %}
<section class="glass pop" style="max-width:520px;margin:6vh auto;padding:28px;border-radius:24px">
  <div class="eyebrow">TU CUENTA</div>
  <h1 class="display" style="font-size:24px;margin:6px 0 18px">Mi perfil</h1>
  <form method="post">
    {% csrf_token %}
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="field"><label>Nombre completo</label>{{ form.name }}
        {% for e in form.name.errors %}<p style="color:var(--c-red);font-size:12px">{{ e }}</p>{% endfor %}
      </div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="field"><label>Departamento</label>{{ form.dept }}</div>
        <div class="field"><label>Puesto</label>{{ form.puesto }}</div>
      </div>
      <div class="field"><label>Sede</label>{{ form.sede }}</div>
    </div>
    <div style="display:flex;gap:10px;justify-content:space-between;margin-top:22px;align-items:center">
      <a class="btn btn-ghost" href="{% url 'accounts:change_password' %}">Cambiar contraseña</a>
      <button class="btn btn-primary" type="submit">Guardar</button>
    </div>
  </form>
</section>
{% endblock %}
```

- [ ] **Step 7: Verde**

```
pytest accounts/tests/test_profile_view.py -x
```

- [ ] **Step 8: Commit**

```
git add accounts/forms.py accounts/views.py accounts/urls.py templates/accounts/profile.html accounts/tests/test_profile_view.py
git commit -m "feat(accounts): pantalla Mi perfil con edición de dept/sede/puesto

No expone email ni flags de rol: la auto-edición solo cubre los
campos organizativos y el nombre."
```

---

## Task 14: Topbar — Rankings, avatar enlazable, chips de rol

**Files:**
- Modify: `templates/partials/_topbar.html`

- [ ] **Step 1: Sustituir el bloque por completo**

```html
{% load icons %}
<header class="glass" style="border-radius:0;border-left:none;border-right:none;border-top:none;padding:12px clamp(16px,3vw,40px);display:flex;align-items:center;gap:18px;flex-shrink:0;z-index:20">
  <a href="{% url 'competicion:dashboard' %}" class="logo" style="text-decoration:none;color:inherit;font-size:17px">
    <span class="logo-mark" style="width:30px;height:30px;font-size:13px"><span>26</span></span>
    PORRA<span class="grad-text">26</span>
  </a>
  {% with ns=request.resolver_match.namespace url_name=request.resolver_match.url_name %}
  <nav style="display:flex;gap:4px;margin-left:12px">
    <a href="{% url 'competicion:dashboard' %}" class="nav-item{% if ns == 'competicion' and url_name != 'manage_results' %} is-active{% endif %}">
      {% icon "ball" width=17 height=17 %} Competición
    </a>
    <a href="{% url 'stats:dashboard' %}" class="nav-item{% if ns == 'stats' and url_name == 'dashboard' %} is-active{% endif %}">
      {% icon "chart" width=17 height=17 %} Estadísticas
    </a>
    <a href="{% url 'stats:rankings' %}" class="nav-item{% if url_name == 'rankings' %} is-active{% endif %}">
      {% icon "trophy" width=17 height=17 %} Rankings
    </a>
    {% if user.is_gestor %}
    <a href="{% url 'pot:manage_players' %}" class="nav-item{% if ns == 'pot' %} is-active{% endif %}">
      {% icon "users" width=17 height=17 %} Jugadores
    </a>
    <a href="{% url 'competicion:manage_results' %}" class="nav-item{% if url_name == 'manage_results' %} is-active{% endif %}">
      {% icon "whistle" width=17 height=17 %} Resultados
    </a>
    {% endif %}
  </nav>
  {% endwith %}
  <div style="margin-left:auto;display:flex;align-items:center;gap:12px">
    <span class="chip" style="color:var(--c-gold);border-color:oklch(from var(--c-gold) l c h / 0.35);padding:5px 11px">
      {% icon "euro" width=12 height=12 %} Bote {{ pot_total|default:0 }} €
    </span>
    <button class="btn btn-ghost" data-theme-toggle style="width:40px;height:40px;padding:0;border-radius:12px" title="Cambiar tema">
      {% icon "sun" width=18 height=18 %}
    </button>
    <a href="{% url 'accounts:profile' %}" style="display:flex;align-items:center;gap:9px;padding-left:6px;text-decoration:none;color:inherit">
      <span class="avatar" data-name="{{ user.name }}">{{ user.initials }}</span>
      <div style="line-height:1.2">
        <div style="font-size:13px;font-weight:700">{{ user.name }}</div>
        <div style="display:flex;gap:4px;margin-top:2px">
          {% if user.is_jugador %}<span class="chip" style="padding:0 6px;font-size:9px;color:var(--c-lime);border-color:oklch(from var(--c-lime) l c h / 0.4)">Jugador</span>{% endif %}
          {% if user.is_gestor %}<span class="chip" style="padding:0 6px;font-size:9px;color:var(--c-cyan);border-color:oklch(from var(--c-cyan) l c h / 0.4)">Gestor</span>{% endif %}
        </div>
      </div>
    </a>
    <form method="post" action="{% url 'accounts:logout' %}" style="display:inline">
      {% csrf_token %}
      <button class="btn btn-ghost" type="submit" style="width:38px;height:38px;padding:0;border-radius:11px" title="Salir">
        {% icon "logout" width=16 height=16 %}
      </button>
    </form>
  </div>
</header>
```

> El link `{% url 'stats:rankings' %}` aún no existe — la siguiente tarea lo añade. Si ejecutas el servidor entre Task 14 y Task 16 la página petará. Por eso encadenamos las tres tareas (servicio, vista, plantilla) y commiteamos al final.

- [ ] **Step 2: No commit todavía**

Sigue con Task 15.

---

## Task 15: Servicio `stats/services/group_standings.py`

**Files:**
- Create: `stats/services/__init__.py` (si no existe; comprobar)
- Create: `stats/services/group_standings.py`
- Test: `stats/tests/test_group_standings.py` (nuevo)

- [ ] **Step 1: Tests fallidos**

Crea `stats/tests/test_group_standings.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import Prediction
from competition.tests.factories import MatchFactory, RoundFactory
from stats.services.group_standings import group_standings


@pytest.fixture
def finished_match(db):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(days=2))
    m.result_home, m.result_away, m.finished_at = 1, 0, timezone.now()
    m.save()
    return m


@pytest.mark.django_db
def test_group_standings_sede_aggregates_totals(finished_match):
    a = UserFactory(sede="vigo", is_jugador=True)
    b = UserFactory(sede="vigo", is_jugador=True)
    c = UserFactory(sede="madrid", is_jugador=True)
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=2, away=1, earned=1)
    Prediction.objects.create(player=c, match=finished_match, home=0, away=0, earned=0)

    rows = {r.key: r for r in group_standings("sede")}
    assert rows["vigo"].total == 4
    assert rows["vigo"].players == 2
    assert rows["vigo"].avg == 2.0
    assert rows["madrid"].total == 0
    assert rows["madrid"].players == 1


@pytest.mark.django_db
def test_group_standings_includes_choices_without_members():
    UserFactory(sede="vigo", is_jugador=True)
    keys = {r.key for r in group_standings("sede")}
    assert {"ourense", "vigo", "asturias", "madrid", "barcelona", "latam"}.issubset(keys)


@pytest.mark.django_db
def test_group_standings_orphan_users_go_to_sin_asignar():
    UserFactory(sede="", is_jugador=True)
    rows = group_standings("sede")
    last = rows[-1]
    assert last.key == "__none__"
    assert last.label == "Sin asignar"
    assert last.players == 1


@pytest.mark.django_db
def test_group_standings_orders_by_avg_then_total(finished_match):
    a = UserFactory(sede="vigo", is_jugador=True)
    b = UserFactory(sede="madrid", is_jugador=True)
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=0, away=2, earned=0)

    rows = [r for r in group_standings("sede") if r.players > 0 and r.key != "__none__"]
    assert rows[0].key == "vigo"  # avg 3 > avg 0


@pytest.mark.django_db
def test_group_standings_ignores_non_jugadores(finished_match):
    invisible = UserFactory(sede="vigo", is_jugador=False)
    Prediction.objects.create(player=invisible, match=finished_match, home=1, away=0, earned=3)
    rows = {r.key: r for r in group_standings("sede")}
    assert rows["vigo"].players == 0
    assert rows["vigo"].total == 0


@pytest.mark.django_db
def test_group_standings_records_top_player(finished_match):
    a = UserFactory(sede="vigo", is_jugador=True, name="Ana")
    b = UserFactory(sede="vigo", is_jugador=True, name="Beto")
    Prediction.objects.create(player=a, match=finished_match, home=1, away=0, earned=3)
    Prediction.objects.create(player=b, match=finished_match, home=2, away=2, earned=1)
    rows = {r.key: r for r in group_standings("sede")}
    assert rows["vigo"].top_name == "Ana"
    assert rows["vigo"].top_pts == 3
```

- [ ] **Step 2: Verificar fallo**

```
pytest stats/tests/test_group_standings.py -x
```

Esperado: `ModuleNotFoundError`.

- [ ] **Step 3: Crear `stats/services/__init__.py` si no existe**

```
touch stats/services/__init__.py
```

(Solo si no existía).

- [ ] **Step 4: Crear `stats/services/group_standings.py`**

```python
from dataclasses import dataclass
from typing import Literal

from accounts.models import User
from competition.services.standings import standings


Dimension = Literal["sede", "puesto", "dept"]

CHOICES_BY_DIMENSION = {
    "sede": User.SEDE_CHOICES,
    "puesto": User.PUESTO_CHOICES,
    "dept": User.DEPT_CHOICES,
}


@dataclass
class GroupRow:
    key: str
    label: str
    players: int
    total: int
    avg: float
    top_name: str
    top_pts: int


def group_standings(dimension: Dimension) -> list[GroupRow]:
    """Agrega los standings por la dimensión organizativa indicada.

    Devuelve una fila por cada `choice` del enum (incluso si está vacía)
    y, al final, una fila "Sin asignar" con los jugadores que no tienen
    valor en ese campo.
    """
    choices = CHOICES_BY_DIMENSION[dimension]
    labels = {key: label for key, label in choices}

    standings_rows = standings()
    users = User.objects.filter(is_active=True, is_jugador=True).only(
        "id", dimension
    )
    user_group = {u.id: (getattr(u, dimension) or "__none__") for u in users}

    buckets: dict[str, list] = {key: [] for key, _ in choices}
    buckets["__none__"] = []
    for row in standings_rows:
        key = user_group.get(row.player_id)
        if key is None:
            continue
        buckets[key].append(row)

    rows: list[GroupRow] = []
    for key, _label in choices:
        rows.append(_row_for(key, labels[key], buckets[key]))
    none_rows = buckets["__none__"]
    if none_rows:
        rows.append(_row_for("__none__", "Sin asignar", none_rows))

    head = [r for r in rows if r.key != "__none__"]
    head.sort(key=lambda r: (-r.avg, -r.total, r.label.lower()))
    tail = [r for r in rows if r.key == "__none__"]
    return head + tail


def _row_for(key: str, label: str, members) -> GroupRow:
    players = len(members)
    total = sum(r.pts for r in members)
    avg = (total / players) if players else 0.0
    if members:
        top = max(members, key=lambda r: (r.pts, -r.player_id))
        top_name, top_pts = top.name, top.pts
    else:
        top_name, top_pts = "", 0
    return GroupRow(
        key=key, label=label, players=players, total=total, avg=avg,
        top_name=top_name, top_pts=top_pts,
    )
```

- [ ] **Step 5: Verde**

```
pytest stats/tests/test_group_standings.py -x
```

- [ ] **Step 6: Sigue sin commit**

La vista y la plantilla se añaden en Task 16; commiteamos todo el bloque rankings junto.

---

## Task 16: `RankingsView`, URL y plantilla

**Files:**
- Modify: `stats/views.py`
- Modify: `stats/urls.py`
- Create: `templates/stats/rankings.html`
- Test: `stats/tests/test_rankings_view.py` (nuevo)

- [ ] **Step 1: Tests fallidos**

Crea `stats/tests/test_rankings_view.py`:

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_rankings_requires_login(client):
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_rankings_default_tab_is_sede(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 200
    assert b"Sede" in r.content


@pytest.mark.django_db
def test_rankings_accepts_puesto_tab(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=puesto")
    assert r.status_code == 200
    assert b"Puesto" in r.content


@pytest.mark.django_db
def test_rankings_unknown_tab_falls_back_to_sede(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=hack")
    assert r.status_code == 200
```

- [ ] **Step 2: Verificar fallo**

```
pytest stats/tests/test_rankings_view.py -x
```

- [ ] **Step 3: Añadir vista en `stats/views.py`**

```python
from stats.services.group_standings import CHOICES_BY_DIMENSION, group_standings


class RankingsView(LoginRequiredMixin, View):
    VALID_TABS = ("sede", "puesto", "dept")
    TAB_LABELS = {"sede": "Sede", "puesto": "Puesto", "dept": "Departamento"}

    def get(self, request):
        tab = request.GET.get("tab", "sede")
        if tab not in self.VALID_TABS:
            tab = "sede"
        rows = group_standings(tab)
        my_group = getattr(request.user, tab, "") or "__none__"
        return render(request, "stats/rankings.html", {
            "tab": tab,
            "rows": rows,
            "tabs": [(k, self.TAB_LABELS[k]) for k in self.VALID_TABS],
            "my_group": my_group,
        })
```

- [ ] **Step 4: Ruta en `stats/urls.py`**

```python
path("rankings/", views.RankingsView.as_view(), name="rankings"),
```

- [ ] **Step 5: Crear `templates/stats/rankings.html`**

```html
{% extends "base.html" %}
{% load icons %}
{% block main %}
<header class="rise" style="margin-bottom:18px">
  <div class="eyebrow">MUNDIAL 2026</div>
  <h1 class="display" style="font-size:28px;margin:6px 0 4px">Rankings por equipo</h1>
  <p style="color:var(--text-dim);margin:0;max-width:560px">Compara qué sede, puesto o departamento puntúa más en la porra. Cada fila es un grupo; orden por media de puntos por jugador.</p>
</header>

<nav class="glass rise" style="display:inline-flex;gap:4px;padding:6px;border-radius:14px;margin-bottom:18px">
  {% for key, label in tabs %}
    <a href="?tab={{ key }}" class="nav-item{% if key == tab %} is-active{% endif %}" style="padding:8px 16px">{{ label }}</a>
  {% endfor %}
</nav>

<div class="glass rise" style="border-radius:22px;overflow:hidden">
  <div style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.18em;border-bottom:1px solid var(--border)">
    <span>#</span><span>Grupo</span><span>Jugadores</span><span>Total</span><span>Media</span><span>Líder</span>
  </div>
  <div class="stagger">
  {% for r in rows %}
    <div style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;align-items:center;border-bottom:1px solid var(--border);{% if r.key == my_group %}background:oklch(from var(--accent) l c h / 0.12);{% endif %}{% if r.key == '__none__' %}opacity:0.55;{% endif %}">
      <span class="mono" style="font-size:13px;color:var(--text-faint)">{{ forloop.counter }}</span>
      <strong style="font-size:14px">{{ r.label }}{% if r.key == my_group %} · tú{% endif %}</strong>
      <span class="mono" style="font-size:13px">{{ r.players }}</span>
      <span class="mono" style="font-size:13px">{{ r.total }} pts</span>
      <span class="display" style="font-size:22px">{{ r.avg|floatformat:1 }}</span>
      <div style="display:flex;align-items:center;gap:8px">
        {% if r.top_name %}
          <span class="avatar" data-name="{{ r.top_name }}" style="width:28px;height:28px;font-size:11px">{{ r.top_name|slice:":2"|upper }}</span>
          <strong style="font-size:13px">{{ r.top_name }}</strong>
          <span class="chip" style="padding:0 6px;font-size:10px">{{ r.top_pts }} pts</span>
        {% else %}
          <span style="color:var(--text-faint);font-size:12px">sin jugadores</span>
        {% endif %}
      </div>
    </div>
  {% empty %}
    <p style="padding:18px;color:var(--text-faint)">Aún no hay jugadores en esta dimensión.</p>
  {% endfor %}
  </div>
</div>
{% endblock %}
```

- [ ] **Step 6: Verde**

```
pytest -x
```

- [ ] **Step 7: Smoke test manual**

```
python manage.py runserver
```

Logueado, navega a `/stats/rankings/`. Verifica que:
- Las tres pestañas cambian el contenido.
- Tu fila (la del grupo del usuario logueado) sale resaltada.
- Fila "Sin asignar" aparece al final atenuada si hay usuarios sin sede.

- [ ] **Step 8: Commit (Tasks 14+15+16 juntas)**

```
git add templates/partials/_topbar.html stats/services/ stats/views.py stats/urls.py templates/stats/rankings.html stats/tests/
git commit -m "feat(stats): página Rankings con clasificación por sede, puesto y departamento

- group_standings agrega standings por dimensión organizativa con
  fila 'Sin asignar' para los huérfanos.
- RankingsView con tres pestañas, fallback a 'sede' ante valores
  inválidos, resalta el grupo del usuario.
- Topbar gana item 'Rankings' y avatar enlazado a Mi perfil con
  chips dinámicos según los flags de rol."
```

---

## Task 17: Actualizar `docs/DATA_MODEL.md`

**Files:**
- Modify: `docs/DATA_MODEL.md`

- [ ] **Step 1: Editar la tabla "Player (Jugador)"**

Reemplaza la fila `role` por estas dos:

```
| `is_jugador` | bool | aparece en clasificaciones y puede pronosticar |
| `is_gestor` | bool | accede a Jugadores, Resultados, Premios y Auditoría |
```

Convierte la fila `dept` en enum:

```
| `dept` | enum | `nominas` \| `gestion` \| `financiera` \| `pesca` (opcional) |
```

Añade dos filas debajo:

```
| `sede` | enum | `ourense` \| `vigo` \| `asturias` \| `madrid` \| `barcelona` \| `latam` (opcional) |
| `puesto` | enum | `desarrollo` \| `sistemas` \| `consultoria` \| `administracion` (opcional) |
```

- [ ] **Step 2: Actualizar la §5 "Reglas de autenticación"**

Sustituye el párrafo de roles:

> Dos flags independientes: `is_jugador` (Competición, Estadísticas, Rankings, Mi perfil) e `is_gestor` (todo lo anterior + Jugadores + Resultados + Premios + Auditoría). Pueden coexistir o estar ambos a `false` (usuario administrativo invisible en el juego).

- [ ] **Step 3: Añadir sección §8 "Rankings por grupo"**

Al final del documento:

```markdown
## 8. Rankings por grupo

La página Rankings agrega los puntos de la clasificación general por una de tres dimensiones organizativas (`sede`, `puesto`, `dept`). Cada fila representa un grupo con:

- **Jugadores**: número de usuarios `is_jugador=True, is_active=True` con ese valor en la dimensión.
- **Total**: suma de `earned` de sus pronósticos resueltos.
- **Media**: `Total / Jugadores`. 0 si no hay jugadores.
- **Líder**: el jugador del grupo con más puntos.

Los `choices` sin miembros aparecen igualmente (fila vacía). Una fila final "Sin asignar" agrupa a los jugadores que tengan el campo en blanco. El orden es `media desc → total desc → label asc`.
```

- [ ] **Step 4: Commit**

```
git add docs/DATA_MODEL.md
git commit -m "docs: actualizar modelo de datos con flags de rol, sede/puesto y rankings"
```

---

## Task 18: Verificación final

**Files:** ninguno; tareas de comprobación.

- [ ] **Step 1: Suite completa en verde**

```
pytest -x --tb=short
```

Esperado: TODO verde. Si algo falla, NO hagas commit final: arregla el test o el código.

- [ ] **Step 2: Lint**

```
ruff check .
ruff format --check .
```

Esperado: clean.

- [ ] **Step 3: Comprobar que no quedan referencias a `role`**

```
grep -rn "\.role\b\|role=\|'role'\|\"role\"" \
  accounts/ competition/ pot/ stats/ templates/ porra26/ \
  --include='*.py' --include='*.html' \
  | grep -v migrations | grep -v __pycache__
```

Esperado: vacío. Si aparece algo, evalúa: si es un test obsoleto, bórralo; si es código de prod, arréglalo.

- [ ] **Step 4: Smoke test manual del flujo completo**

```
python manage.py runserver
```

Como gestor (`is_gestor=True`):
1. `/gestion/jugadores/` — alta abre overlay, valida campos, crea usuario, navega a `/gestion/jugadores/<id>/clave/` con la temporal visible.
2. Editar un jugador desde la lista, cambiar sede a Vigo, guardar — vuelve a la lista actualizada.
3. `/stats/rankings/` — pestañas Sede / Puesto / Departamento, la sede Vigo refleja el cambio.

Como jugador puro (`is_gestor=False, is_jugador=True`):
4. Topbar no muestra Jugadores ni Resultados.
5. `/perfil/` — puede cambiar nombre, dept, sede, puesto. No expone email ni flags.
6. `/competicion/` — puede pronosticar.

Como gestor puro (`is_gestor=True, is_jugador=False`):
7. Aparece en "Jugadores" con chip "no juega".
8. NO aparece en la clasificación lateral de Competición.
9. NO aparece en ningún grupo de Rankings.
10. Intentar `POST /competicion/predict/<id>/` devuelve 403.

- [ ] **Step 5: Crear PR**

```
gh pr create --title "Roles separados, perfil organizativo y rankings por grupo" --body "$(cat <<'EOF'
## Summary

- Sustituye `accounts.User.role` por dos flags independientes (`is_jugador`, `is_gestor`).
- Añade enums `dept` (Nóminas, Gestión, Financiera, Pesca), `sede` (Ourense, Vigo, Asturias, Madrid, Barcelona, Latinoamérica) y `puesto` (Desarrollo, Sistemas, Consultoría, Administración).
- Convierte el alta/edición de jugadores en un overlay modal real con protocolo `X-Modal-Redirect` / `X-Modal-Errors`.
- Nueva pantalla "Mi perfil" para que cada jugador edite sus campos organizativos.
- Nueva página "Rankings" con tres pestañas: Sede / Puesto / Departamento, mostrando total y media por grupo y resaltando el grupo del usuario actual.
- Migración `accounts.0003` con backfill: superusers quedan invisibles en juego, gestores existentes conservan permisos.

## Test plan

- [ ] `pytest -x` en verde
- [ ] `ruff check .` clean
- [ ] Crear/editar jugador como gestor abre overlay; alta redirige a pantalla con contraseña temporal
- [ ] Jugador puro puede editar dept/sede/puesto en `/perfil/`
- [ ] Jugador puro NO ve items de gestor en el topbar
- [ ] Gestor puro (sin `is_jugador`) NO aparece en clasificación ni en rankings, y recibe 403 al pronosticar
- [ ] Página Rankings actualiza correctamente al cambiar la sede de un jugador
EOF
)"
```

---

## Self-review (post-redacción)

**1. Cobertura del spec.** Recorro cada sección del spec:

- Modelo de datos (§1 spec) → Tasks 1-3 ✓
- Refactor de referencias (§1 spec) → Task 4 (mixin) + Task 5 (standings) + Task 6 (predict guard) ✓
- modal.js (§2 spec) → Task 10 ✓
- PlayerFormView (§2 spec) → Task 8 ✓
- Plantilla `_player_modal.html` (§2 spec) → Task 9 ✓
- Lista `manage_players.html` (§2 spec) → Task 12 ✓
- CSS (§2 spec) → Task 11 ✓
- Mi perfil (§3 spec) → Task 13 ✓
- Topbar (§3 + §4 spec) → Task 14 ✓
- Servicio `group_standings` (§4 spec) → Task 15 ✓
- `RankingsView` + plantilla (§4 spec) → Task 16 ✓
- Tests (§5 spec) → cubiertos en las Tasks correspondientes (1, 5, 6, 7, 8, 13, 15, 16) ✓
- `DATA_MODEL.md` (§6 spec) → Task 17 ✓
- Riesgos / migración irreversible (§7 spec) → Task 3 incluye `reverse_noop` con comentario ✓

Sin huecos.

**2. Placeholders.** Buscadas las frases "TBD", "TODO", "implement later", "similar to Task" — no aparecen. Cada Task tiene código completo. La única expresión `...` es para señalar dónde inyectar el contenido envolvente de un `extends` (Task 9), que es código real.

**3. Consistencia de tipos.** Verificadas firmas:
- `group_standings(dimension)` devuelve `list[GroupRow]` (definido Task 15) y se consume desde `RankingsView` (Task 16) iterando `rows` con los atributos `key, label, players, total, avg, top_name, top_pts` — todos los usa el template.
- `CHOICES_BY_DIMENSION["sede"]` se usa en el servicio (Task 15) y deriva de `User.SEDE_CHOICES` (Task 1).
- Header `X-Modal` (request) y `X-Modal-Redirect` / `X-Modal-Errors` (response) — usados consistentemente en views (Task 8), JS (Task 10), tests (Task 8).
- URL `pot:player_reveal` definida (Task 8) y referenciada en redirect.
- `PasswordRevealView` cita el template `pot/_password_reveal.html` — ya existía en el repo; la Task 8 solo se asegura de que extienda `base.html`.

Sin inconsistencias.
