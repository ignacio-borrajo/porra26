# Recordarme (Remember Me) — Plan de Implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir que los jugadores no tengan que introducir contraseña en cada visita, con visibilidad y revocación de sesiones, e invalidación correcta en cambios de contraseña.

**Architecture:** Sesiones largas de Django opt-in (30 días con renovación por uso) más una tabla `UserSession` con metadatos (device, IP, last_seen) que desbloquea la lista "Mis sesiones" y la revocación. Invalidación robusta vía `session_auth_hash` + borrado explícito en flujos de cambio de contraseña.

**Tech Stack:** Django 5, pytest + pytest-django, `user-agents` lib, `django.contrib.humanize` para `naturaltime`, plantillas Django con tokens del prototipo (`design-reference/styles.css`).

**Spec:** `docs/superpowers/specs/2026-06-05-remember-me-design.md`

---

## File Structure

**Create:**
- `accounts/migrations/0007_usersession.py` — migración del modelo
- `accounts/services/sessions.py` — servicio `revoke_sessions` + helper `parse_device_label`
- `accounts/services/notifications.py` — email de cambio de contraseña
- `accounts/management/__init__.py` (si no existe) y `accounts/management/commands/__init__.py`
- `accounts/management/commands/prune_user_sessions.py` — limpieza periódica
- `accounts/signals.py` — signal `post_save` en User
- `accounts/tests/test_user_session_model.py`
- `accounts/tests/test_login_remember.py`
- `accounts/tests/test_session_middleware.py`
- `accounts/tests/test_user_sessions_view.py`
- `accounts/tests/test_password_invalidation.py`
- `accounts/tests/test_revoke_sessions_service.py`
- `accounts/tests/test_prune_user_sessions.py`
- `accounts/tests/test_device_label_parser.py`
- `templates/accounts/_my_sessions.html` — partial para la lista de sesiones en Mi cuenta
- `templates/accounts/emails/password_changed.txt` — body en texto
- `templates/accounts/emails/password_changed.html` — body en HTML (opcional)

**Modify:**
- `accounts/models.py` — añadir clase `UserSession`
- `accounts/forms.py` — añadir campo `remember` al `LoginForm`
- `accounts/views.py` — `LoginView.post`, `LogoutView.post`, `MyAccountView`, `ChangePasswordView.post`, `PasswordResetConfirmView.post`
- `accounts/middleware.py` — añadir `RememberMeRefreshMiddleware`
- `accounts/apps.py` — registrar signals en `ready()`
- `accounts/urls.py` — ninguno nuevo (las acciones de revocación se manejan dentro de `MyAccountView.post`)
- `templates/accounts/login.html` — checkbox + JS de detección PWA
- `templates/accounts/my_account.html` — include del partial `_my_sessions.html`
- `porra26/settings/base.py` — `INSTALLED_APPS` (humanize), `MIDDLEWARE`, `SESSION_*`
- `porra26/settings/prod.py` — `SESSION_COOKIE_SECURE = True`, `CSRF_COOKIE_SECURE = True`
- `requirements.txt` — añadir `user-agents`

---

## Task 1: Añadir dependencia `user-agents` y configuración base

**Files:**
- Modify: `requirements.txt`
- Modify: `porra26/settings/base.py`

- [ ] **Step 1: Añadir `user-agents` a requirements.txt**

Editar `requirements.txt`, añadir línea (manteniendo orden alfabético cerca de otras libs ligeras):

```text
user-agents>=2.2
```

- [ ] **Step 2: Instalar**

```bash
pip install -r requirements.txt
```

Expected: `Successfully installed user-agents-2.x.x ua-parser-x.x.x ...`

- [ ] **Step 3: Añadir `django.contrib.humanize` a INSTALLED_APPS**

En `porra26/settings/base.py`, en la lista `INSTALLED_APPS`, añadir `"django.contrib.humanize"` justo después de `"django.contrib.staticfiles"`.

- [ ] **Step 4: Añadir constantes de sesión**

En `porra26/settings/base.py`, después del bloque `SESSION_COOKIE_*` existente, añadir:

```python
SESSION_COOKIE_AGE = 30 * 24 * 3600          # 30 días, tope absoluto
SESSION_SAVE_EVERY_REQUEST = False           # usamos middleware con throttle
SESSION_EXPIRE_AT_BROWSER_CLOSE = False      # controlado por sesión vía set_expiry
```

- [ ] **Step 5: Endurecer cookies en producción**

En `porra26/settings/prod.py`, añadir al final del archivo:

```python
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
```

- [ ] **Step 6: Smoke test**

```bash
python manage.py check
```

Expected: `System check identified no issues`.

- [ ] **Step 7: Commit**

```bash
git add requirements.txt porra26/settings/base.py porra26/settings/prod.py
git commit -m "chore(accounts): preparar settings y deps para 'Recordarme'"
```

---

## Task 2: Crear modelo `UserSession`

**Files:**
- Modify: `accounts/models.py`
- Create: `accounts/migrations/0007_usersession.py` (autogen)
- Create: `accounts/tests/test_user_session_model.py`

- [ ] **Step 1: Escribir test del modelo**

`accounts/tests/test_user_session_model.py`:

```python
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def test_user_session_can_be_created_with_required_fields():
    user = UserFactory()
    us = UserSession.objects.create(
        user=user,
        session_key="abc123def456abc123def456abc123de",
        device_label="iPhone — Safari",
        last_seen_at=timezone.now(),
    )
    assert us.pk is not None
    assert us.remembered is False
    assert us.is_pwa is False
    assert us.ip_at_login is None
    assert us.user == user


def test_user_session_key_is_unique():
    import pytest
    from django.db.utils import IntegrityError

    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="dup", device_label="x", last_seen_at=timezone.now()
    )
    with pytest.raises(IntegrityError):
        UserSession.objects.create(
            user=user, session_key="dup", device_label="x", last_seen_at=timezone.now()
        )


def test_user_session_cascade_on_user_delete():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="x", device_label="d", last_seen_at=timezone.now()
    )
    user.delete()
    assert UserSession.objects.count() == 0
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_user_session_model.py -v
```

Expected: 3 errores tipo `ImportError: cannot import name 'UserSession'`.

- [ ] **Step 3: Añadir el modelo**

En `accounts/models.py`, al final del archivo (tras `_delete_avatar_file`):

```python
class UserSession(models.Model):
    user = models.ForeignKey(
        User, on_delete=models.CASCADE, related_name="sessions"
    )
    session_key = models.CharField(max_length=40, unique=True, db_index=True)
    device_label = models.CharField(max_length=80)
    user_agent_raw = models.CharField(max_length=400, blank=True)
    ip_at_login = models.GenericIPAddressField(null=True, blank=True)
    is_pwa = models.BooleanField(default=False)
    remembered = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    last_seen_at = models.DateTimeField(db_index=True)

    class Meta:
        ordering = ["-last_seen_at"]

    def __str__(self):
        return f"{self.user_id}:{self.session_key[:8]} {self.device_label}"
```

- [ ] **Step 4: Generar migración**

```bash
python manage.py makemigrations accounts
```

Expected: `Migrations for 'accounts': accounts/migrations/0007_usersession.py - Create model UserSession`.

- [ ] **Step 5: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_user_session_model.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add accounts/models.py accounts/migrations/0007_usersession.py accounts/tests/test_user_session_model.py
git commit -m "feat(accounts): modelo UserSession para metadatos de sesión activa"
```

---

## Task 3: Helper `parse_device_label`

**Files:**
- Create: `accounts/services/sessions.py`
- Create: `accounts/tests/test_device_label_parser.py`

- [ ] **Step 1: Escribir tests del parser**

`accounts/tests/test_device_label_parser.py`:

```python
from accounts.services.sessions import parse_device_label


def test_iphone_safari():
    ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    assert "iPhone" in parse_device_label(ua)
    assert "Safari" in parse_device_label(ua)


def test_chrome_macos():
    ua = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
    label = parse_device_label(ua)
    assert "Chrome" in label
    assert "Mac" in label or "macOS" in label


def test_edge_windows():
    ua = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
    label = parse_device_label(ua)
    assert "Edge" in label or "Edg" in label
    assert "Windows" in label


def test_empty_user_agent_returns_fallback():
    assert parse_device_label("") == "Dispositivo desconocido"


def test_extremely_long_ua_truncated_safely():
    label = parse_device_label("x" * 5000)
    assert len(label) <= 80
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_device_label_parser.py -v
```

Expected: `ModuleNotFoundError: No module named 'accounts.services.sessions'`.

- [ ] **Step 3: Implementar parser**

`accounts/services/sessions.py`:

```python
from user_agents import parse as parse_user_agent

UNKNOWN_DEVICE_LABEL = "Dispositivo desconocido"


def parse_device_label(user_agent_raw: str) -> str:
    """Devuelve una etiqueta legible del dispositivo, máx. 80 chars.

    Ejemplos:
      'iPhone — Safari'
      'Chrome en macOS'
      'Edge en Windows'
    """
    if not user_agent_raw:
        return UNKNOWN_DEVICE_LABEL
    try:
        ua = parse_user_agent(user_agent_raw[:1000])
    except Exception:
        return UNKNOWN_DEVICE_LABEL

    browser = ua.browser.family or ""
    os_family = ua.os.family or ""
    device = ua.device.family or ""

    if ua.is_mobile or ua.is_tablet:
        if device and device != "Other":
            label = f"{device} — {browser}".strip(" —")
        else:
            label = f"{os_family} — {browser}".strip(" —")
    else:
        label = f"{browser} en {os_family}".strip(" en")

    label = label or UNKNOWN_DEVICE_LABEL
    return label[:80]
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_device_label_parser.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add accounts/services/sessions.py accounts/tests/test_device_label_parser.py
git commit -m "feat(accounts): parser de device_label desde User-Agent"
```

---

## Task 4: Servicio `revoke_sessions`

**Files:**
- Modify: `accounts/services/sessions.py`
- Create: `accounts/tests/test_revoke_sessions_service.py`

- [ ] **Step 1: Escribir tests**

`accounts/tests/test_revoke_sessions_service.py`:

```python
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.utils import timezone

from accounts.models import AuditLog, UserSession
from accounts.services.sessions import revoke_sessions
from accounts.tests.factories import UserFactory


def _create_session(session_key: str):
    Session.objects.create(
        session_key=session_key,
        session_data="",
        expire_date=timezone.now() + timedelta(days=30),
    )


def test_revoke_sessions_deletes_session_and_user_session():
    user = UserFactory()
    _create_session("aaaaaaaa")
    UserSession.objects.create(
        user=user, session_key="aaaaaaaa", device_label="d", last_seen_at=timezone.now()
    )

    deleted = revoke_sessions(
        user=user, session_keys=["aaaaaaaa"], actor=user, reason="test"
    )

    assert deleted == 1
    assert not Session.objects.filter(session_key="aaaaaaaa").exists()
    assert not UserSession.objects.filter(session_key="aaaaaaaa").exists()


def test_revoke_sessions_creates_audit_log():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="x", device_label="d", last_seen_at=timezone.now()
    )

    revoke_sessions(user=user, session_keys=["x"], actor=user, reason="password_change")

    log = AuditLog.objects.get(action="sessions.revoked", target_id=str(user.id))
    assert log.payload == {"count": 1, "reason": "password_change"}
    assert log.actor == user


def test_revoke_sessions_with_empty_list_is_noop():
    user = UserFactory()
    assert revoke_sessions(user=user, session_keys=[], actor=user) == 0
    assert AuditLog.objects.filter(action="sessions.revoked").count() == 0


def test_revoke_sessions_only_touches_own_user():
    a = UserFactory()
    b = UserFactory()
    UserSession.objects.create(user=a, session_key="a", device_label="d", last_seen_at=timezone.now())
    UserSession.objects.create(user=b, session_key="b", device_label="d", last_seen_at=timezone.now())

    revoke_sessions(user=a, session_keys=["a", "b"], actor=a)

    assert UserSession.objects.filter(user=b).count() == 1


def test_revoke_sessions_idempotent():
    user = UserFactory()
    UserSession.objects.create(user=user, session_key="x", device_label="d", last_seen_at=timezone.now())
    revoke_sessions(user=user, session_keys=["x"], actor=user)
    # Second call: nothing to delete, but should not crash
    assert revoke_sessions(user=user, session_keys=["x"], actor=user) == 0
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_revoke_sessions_service.py -v
```

Expected: 5 errores `ImportError: cannot import name 'revoke_sessions'`.

- [ ] **Step 3: Implementar el servicio**

Añadir al final de `accounts/services/sessions.py`:

```python
from collections.abc import Iterable

from django.contrib.sessions.models import Session
from django.db import transaction

from accounts.models import AuditLog, UserSession


@transaction.atomic
def revoke_sessions(
    *,
    user,
    session_keys: Iterable[str],
    actor=None,
    reason: str = "manual",
) -> int:
    """Revoca sesiones del usuario indicado.

    Borra primero la Session real (la cookie deja de valer) y luego la
    UserSession asociada. Registra una sola entrada de AuditLog con el
    count y la razón. Devuelve nº de UserSession borradas.
    """
    keys = list(session_keys)
    if not keys:
        return 0
    Session.objects.filter(session_key__in=keys).delete()
    deleted, _ = UserSession.objects.filter(user=user, session_key__in=keys).delete()
    AuditLog.objects.create(
        actor=actor,
        action="sessions.revoked",
        target_type="user",
        target_id=str(user.id),
        payload={"count": deleted, "reason": reason},
    )
    return deleted
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_revoke_sessions_service.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add accounts/services/sessions.py accounts/tests/test_revoke_sessions_service.py
git commit -m "feat(accounts): servicio revoke_sessions con auditoría"
```

---

## Task 5: Campo `remember` en `LoginForm`

**Files:**
- Modify: `accounts/forms.py`

- [ ] **Step 1: Escribir test del form**

Crear `accounts/tests/test_login_remember.py` (lo iremos rellenando en tasks siguientes):

```python
from accounts.forms import LoginForm


def test_login_form_has_remember_field_initial_true():
    form = LoginForm()
    assert "remember" in form.fields
    assert form.fields["remember"].required is False
    assert form.fields["remember"].initial is True


def test_login_form_accepts_remember_off():
    form = LoginForm(data={"email": "x@edisa.com", "password": "p", "remember": ""})
    form.is_valid()  # no nos importa la validez total aquí
    assert form.cleaned_data.get("remember", False) is False


def test_login_form_accepts_remember_on():
    form = LoginForm(data={"email": "x@edisa.com", "password": "p", "remember": "1"})
    form.is_valid()
    assert form.cleaned_data.get("remember") is True
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_login_remember.py::test_login_form_has_remember_field_initial_true -v
```

Expected: `KeyError: 'remember'`.

- [ ] **Step 3: Añadir campo al form**

Editar `accounts/forms.py`. En la clase `LoginForm`, justo después del campo `password`:

```python
    remember = forms.BooleanField(
        label="Recordarme en este dispositivo",
        required=False,
        initial=True,
    )
```

- [ ] **Step 4: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_login_remember.py -v
```

Expected: 3 passed.

- [ ] **Step 5: Commit**

```bash
git add accounts/forms.py accounts/tests/test_login_remember.py
git commit -m "feat(accounts): campo 'remember' en LoginForm"
```

---

## Task 6: `LoginView` crea `UserSession` y respeta `remember`

**Files:**
- Modify: `accounts/views.py`
- Modify: `accounts/tests/test_login_remember.py`

- [ ] **Step 1: Ampliar tests**

Añadir al final de `accounts/tests/test_login_remember.py`:

```python
from django.urls import reverse

from accounts.models import AuditLog, UserSession
from accounts.tests.factories import UserFactory


def test_login_with_remember_sets_30_day_expiry_and_creates_user_session(client):
    user = UserFactory(email="x@edisa.com", password="Secret123")
    resp = client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123", "remember": "1"},
    )
    assert resp.status_code == 302

    session = client.session
    # 30 días = 2_592_000 segundos. Tolerancia ±60s.
    assert 30 * 24 * 3600 - 60 <= session.get_expiry_age() <= 30 * 24 * 3600 + 60

    us = UserSession.objects.get(user=user)
    assert us.session_key == session.session_key
    assert us.remembered is True


def test_login_without_remember_uses_browser_session_and_marks_not_remembered(client):
    UserFactory(email="x@edisa.com", password="Secret123")
    resp = client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123"},  # no remember
    )
    assert resp.status_code == 302
    assert client.session.get_expire_at_browser_close() is True
    us = UserSession.objects.get(session_key=client.session.session_key)
    assert us.remembered is False


def test_login_with_is_pwa_marks_user_session(client):
    UserFactory(email="x@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123", "remember": "1", "is_pwa": "1"},
    )
    us = UserSession.objects.get(session_key=client.session.session_key)
    assert us.is_pwa is True


def test_failed_login_does_not_create_user_session(client):
    UserFactory(email="x@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "WRONG"},
    )
    assert UserSession.objects.count() == 0


def test_login_records_audit_log(client):
    user = UserFactory(email="x@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "x@edisa.com", "password": "Secret123", "remember": "1"},
    )
    log = AuditLog.objects.get(action="login", target_id=str(user.id))
    assert log.payload["remembered"] is True
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_login_remember.py -v -k "not_login_form"
```

Expected: fallos sobre `UserSession.DoesNotExist` y expectativas de `session.get_expiry_age()`.

- [ ] **Step 3: Helper `_client_ip` reutilizable**

Verificar que `accounts/services/password_reset.py` ya expone `_client_ip`. Sí lo hace (lo importamos en `views.py`). En el siguiente paso lo reutilizamos.

- [ ] **Step 4: Modificar `LoginView.post`**

En `accounts/views.py`, importar:

```python
from django.utils import timezone

from .models import AuditLog, User, UserSession
from .services.sessions import parse_device_label
```

Reemplazar el cuerpo de `LoginView.post` por:

```python
def post(self, request):
    form = LoginForm(request.POST)
    if form.is_valid():
        user = form.get_user(request)
        if user is not None:
            login(request, user)
            remembered = bool(form.cleaned_data.get("remember"))
            if remembered:
                request.session.set_expiry(30 * 24 * 3600)
            else:
                request.session.set_expiry(0)

            is_pwa = request.POST.get("is_pwa") == "1"
            ua_raw = request.META.get("HTTP_USER_AGENT", "")[:400]
            UserSession.objects.create(
                user=user,
                session_key=request.session.session_key,
                device_label=parse_device_label(ua_raw),
                user_agent_raw=ua_raw,
                ip_at_login=_client_ip(request),
                is_pwa=is_pwa,
                remembered=remembered,
                last_seen_at=timezone.now(),
            )
            AuditLog.objects.create(
                actor=user,
                action="login",
                target_type="user",
                target_id=str(user.id),
                payload={
                    "remembered": remembered,
                    "is_pwa": is_pwa,
                    "ip": _client_ip(request),
                },
            )

            if user.must_change_password:
                return redirect("accounts:change_password")
            return redirect("competicion:dashboard")
        messages.error(request, "Correo o contraseña incorrectos.")
    return render(request, self.template_name, {"form": form, **self._info_context()})
```

- [ ] **Step 5: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_login_remember.py -v
```

Expected: 8 passed.

- [ ] **Step 6: Commit**

```bash
git add accounts/views.py accounts/tests/test_login_remember.py
git commit -m "feat(accounts): LoginView crea UserSession y aplica 'remember'"
```

---

## Task 7: Detección PWA en login template

**Files:**
- Modify: `templates/accounts/login.html`

- [ ] **Step 1: Añadir checkbox y JS de detección PWA**

En `templates/accounts/login.html`, insertar antes del `<button class="btn btn-primary" type="submit"...>`:

```html
<label class="login-remember" style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text-dim);user-select:none;cursor:pointer">
  <input type="checkbox" name="remember" value="1" {% if form.remember.value|default:True %}checked{% endif %} style="width:16px;height:16px;cursor:pointer">
  <span>Recordarme en este dispositivo</span>
</label>
```

Al final del bloque `<form>`, justo antes del cierre `</form>`, añadir:

```html
<script>
  (function() {
    var isStandalone = window.matchMedia('(display-mode: standalone)').matches
      || window.navigator.standalone === true;
    if (isStandalone) {
      var form = document.currentScript.closest('form');
      var hidden = document.createElement('input');
      hidden.type = 'hidden';
      hidden.name = 'is_pwa';
      hidden.value = '1';
      form.appendChild(hidden);
    }
  })();
</script>
```

- [ ] **Step 2: Smoke test manual**

```bash
python manage.py runserver
```

Abre `http://127.0.0.1:8000/`. Verifica:
1. Checkbox visible, pre-marcado.
2. View source: no debe romper el HTML.

Detén el servidor (Ctrl+C).

- [ ] **Step 3: Commit**

```bash
git add templates/accounts/login.html
git commit -m "feat(login): checkbox 'Recordarme' y detección PWA"
```

---

## Task 8: Middleware `RememberMeRefreshMiddleware`

**Files:**
- Modify: `accounts/middleware.py`
- Modify: `porra26/settings/base.py`
- Create: `accounts/tests/test_session_middleware.py`

- [ ] **Step 1: Escribir tests**

`accounts/tests/test_session_middleware.py`:

```python
from datetime import timedelta

from django.core.cache import cache
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def _login(client, user):
    client.post(
        reverse("accounts:login"),
        {"email": user.email, "password": "Secret123", "remember": "1"},
    )


def test_middleware_updates_last_seen_for_authenticated_request(client):
    user = UserFactory(email="a@edisa.com", password="Secret123")
    _login(client, user)
    us = UserSession.objects.get(user=user)
    old = us.last_seen_at
    # Avanzar el reloj manualmente forzando refresh: invalidar throttle
    cache.clear()
    UserSession.objects.filter(pk=us.pk).update(last_seen_at=old - timedelta(minutes=5))

    client.get(reverse("competicion:dashboard"))

    us.refresh_from_db()
    assert us.last_seen_at > old - timedelta(minutes=5)


def test_middleware_renews_expiry_only_when_remembered(client):
    user = UserFactory(email="b@edisa.com", password="Secret123")
    # Login SIN remember
    client.post(
        reverse("accounts:login"),
        {"email": "b@edisa.com", "password": "Secret123"},
    )
    cache.clear()
    client.get(reverse("competicion:dashboard"))
    assert client.session.get_expire_at_browser_close() is True


def test_middleware_throttle_avoids_double_db_hit(client):
    user = UserFactory(email="c@edisa.com", password="Secret123")
    _login(client, user)
    us = UserSession.objects.get(user=user)

    # Primera request gastó el slot; la siguiente NO debe actualizar.
    UserSession.objects.filter(pk=us.pk).update(
        last_seen_at=timezone.now() - timedelta(hours=1)
    )
    client.get(reverse("competicion:dashboard"))
    us.refresh_from_db()
    # Debe seguir sin actualizar porque el throttle está activo.
    assert us.last_seen_at < timezone.now() - timedelta(minutes=30)


def test_middleware_skips_anonymous_requests(client):
    cache.clear()
    resp = client.get(reverse("accounts:login"))
    assert resp.status_code == 200  # no 500


def test_middleware_safe_with_orphan_session(client):
    user = UserFactory(email="d@edisa.com", password="Secret123")
    _login(client, user)
    UserSession.objects.filter(user=user).delete()  # huérfana en sesión
    cache.clear()
    resp = client.get(reverse("competicion:dashboard"))
    assert resp.status_code == 200
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_session_middleware.py -v
```

Expected: tests fallan porque el middleware nuevo todavía no existe (la lógica de update no se dispara).

- [ ] **Step 3: Implementar el middleware**

En `accounts/middleware.py`, añadir al final:

```python
from django.core.cache import cache
from django.utils import timezone

from accounts.models import UserSession


class RememberMeRefreshMiddleware:
    """Renueva 'sliding window' la expiración de sesiones recordadas y
    actualiza last_seen_at en UserSession. Throttle de 60s por sesión
    para no martillear DB."""

    THROTTLE_SECONDS = 60
    REMEMBERED_EXPIRY = 30 * 24 * 3600

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)
        if not getattr(request, "user", None) or not request.user.is_authenticated:
            return response
        session_key = request.session.session_key
        if not session_key:
            return response

        cache_key = f"session_touch:{session_key}"
        if cache.get(cache_key):
            return response
        cache.set(cache_key, 1, timeout=self.THROTTLE_SECONDS)

        try:
            us = UserSession.objects.get(session_key=session_key)
        except UserSession.DoesNotExist:
            return response

        if us.remembered:
            request.session.set_expiry(self.REMEMBERED_EXPIRY)

        UserSession.objects.filter(pk=us.pk).update(last_seen_at=timezone.now())
        return response
```

- [ ] **Step 4: Registrar el middleware en settings**

En `porra26/settings/base.py`, en la lista `MIDDLEWARE`, añadir justo después de `"accounts.middleware.ForcePasswordChangeMiddleware"`:

```python
"accounts.middleware.RememberMeRefreshMiddleware",
```

- [ ] **Step 5: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_session_middleware.py -v
```

Expected: 5 passed.

- [ ] **Step 6: Commit**

```bash
git add accounts/middleware.py porra26/settings/base.py accounts/tests/test_session_middleware.py
git commit -m "feat(accounts): middleware de sliding window y last_seen"
```

---

## Task 9: `LogoutView` borra `UserSession` y signal de invalidación al cambio de password

**Files:**
- Modify: `accounts/views.py`
- Create: `accounts/signals.py`
- Modify: `accounts/apps.py`
- Create: `accounts/tests/test_password_invalidation.py` (parcial; resto en tareas 11–12)

- [ ] **Step 1: Test del logout**

Añadir a `accounts/tests/test_login_remember.py`:

```python
def test_logout_removes_user_session(client):
    user = UserFactory(email="lo@edisa.com", password="Secret123")
    client.post(
        reverse("accounts:login"),
        {"email": "lo@edisa.com", "password": "Secret123", "remember": "1"},
    )
    assert UserSession.objects.filter(user=user).count() == 1
    client.post(reverse("accounts:logout"))
    assert UserSession.objects.filter(user=user).count() == 0
```

- [ ] **Step 2: Test del signal**

Crear `accounts/tests/test_password_invalidation.py`:

```python
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def test_admin_password_change_wipes_user_sessions():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="k1", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=user, session_key="k2", device_label="d", last_seen_at=timezone.now()
    )
    user.set_password("NewPass123")
    user.save(update_fields=["password"])
    assert UserSession.objects.filter(user=user).count() == 0
```

- [ ] **Step 3: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_login_remember.py::test_logout_removes_user_session accounts/tests/test_password_invalidation.py -v
```

Expected: ambos fallan.

- [ ] **Step 4: Modificar `LogoutView`**

En `accounts/views.py`, reemplazar el cuerpo de `LogoutView.post`:

```python
def post(self, request):
    if request.user.is_authenticated and request.session.session_key:
        UserSession.objects.filter(session_key=request.session.session_key).delete()
    logout(request)
    return redirect("accounts:login")
```

- [ ] **Step 5: Crear signal**

`accounts/signals.py`:

```python
from django.db.models.signals import post_save
from django.dispatch import receiver

from .models import User, UserSession


@receiver(post_save, sender=User)
def wipe_user_sessions_on_password_change(sender, instance, **kwargs):
    update_fields = kwargs.get("update_fields") or set()
    if update_fields and "password" in update_fields:
        UserSession.objects.filter(user=instance).delete()
```

- [ ] **Step 6: Registrar signal en `apps.py`**

Leer `accounts/apps.py` (si tiene `default_auto_field` solo, hay que añadir `ready`). Reemplazar/añadir:

```python
from django.apps import AppConfig


class AccountsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "accounts"

    def ready(self):
        from . import signals  # noqa: F401
```

- [ ] **Step 7: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_login_remember.py::test_logout_removes_user_session accounts/tests/test_password_invalidation.py -v
```

Expected: 2 passed.

- [ ] **Step 8: Commit**

```bash
git add accounts/views.py accounts/signals.py accounts/apps.py accounts/tests/test_login_remember.py accounts/tests/test_password_invalidation.py
git commit -m "feat(accounts): logout limpia UserSession y signal invalida en cambio de password"
```

---

## Task 10: Vista "Mis sesiones" (GET) en `MyAccountView`

**Files:**
- Modify: `accounts/views.py`
- Create: `templates/accounts/_my_sessions.html`
- Modify: `templates/accounts/my_account.html`
- Create: `accounts/tests/test_user_sessions_view.py`

- [ ] **Step 1: Escribir test del GET**

`accounts/tests/test_user_sessions_view.py`:

```python
from django.urls import reverse
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def _login(client, user, password="Secret123"):
    client.post(reverse("accounts:login"), {"email": user.email, "password": password, "remember": "1"})


def test_my_account_lists_user_sessions(client):
    user = UserFactory(email="ms@edisa.com", password="Secret123")
    _login(client, user)
    UserSession.objects.create(
        user=user, session_key="other-key-12345", device_label="iPhone — Safari",
        last_seen_at=timezone.now(), remembered=True,
    )
    resp = client.get(reverse("accounts:my_account"))
    assert resp.status_code == 200
    body = resp.content.decode()
    assert "iPhone" in body
    assert "ESTA SESIÓN" in body  # sesión activa marcada


def test_my_account_does_not_list_other_users_sessions(client):
    me = UserFactory(email="me@edisa.com", password="Secret123")
    other = UserFactory(email="other@edisa.com", password="Secret123")
    _login(client, me)
    UserSession.objects.create(
        user=other, session_key="other-session", device_label="Edge en Windows",
        last_seen_at=timezone.now(),
    )
    resp = client.get(reverse("accounts:my_account"))
    body = resp.content.decode()
    assert "Edge en Windows" not in body
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_user_sessions_view.py -v
```

Expected: AssertionError porque no se renderiza la sección.

- [ ] **Step 3: Ampliar `MyAccountView._render`**

En `accounts/views.py`, en `MyAccountView._render`, ampliar el dict del context:

```python
def _render(self, request, profile_form=None, password_form=None, status=200):
    sessions = (
        UserSession.objects.filter(user=request.user).order_by("-last_seen_at")
    )
    return render(
        request,
        self.template_name,
        {
            "profile_form": profile_form or ProfileForm(instance=request.user),
            "password_form": password_form or ChangePasswordForm(request.user),
            "user_sessions": sessions,
            "current_session_key": request.session.session_key,
        },
        status=status,
    )
```

- [ ] **Step 4: Crear partial de la lista**

`templates/accounts/_my_sessions.html`:

```html
{% load humanize %}
<section class="glass" style="padding:24px;display:flex;flex-direction:column;gap:14px">
  <header>
    <h2 class="display" style="margin:0;font-size:20px">Mis sesiones</h2>
    <p style="margin:4px 0 0;color:var(--text-dim);font-size:13px">
      Dispositivos donde tienes abierta la app ahora mismo.
    </p>
  </header>

  <ul style="list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:10px">
    {% for s in user_sessions %}
      <li class="session-row" style="display:flex;flex-direction:column;gap:6px;padding:12px;border-radius:12px;background:rgba(255,255,255,.04)">
        <div style="display:flex;align-items:center;gap:10px;flex-wrap:wrap">
          <span style="font-size:18px">
            {% if 'iPhone' in s.device_label or 'Android' in s.device_label %}📱
            {% elif 'Mac' in s.device_label %}💻
            {% else %}🖥{% endif %}
          </span>
          <strong>{{ s.device_label }}{% if s.is_pwa %} (PWA){% endif %}</strong>
          {% if s.session_key == current_session_key %}
            <span class="chip" style="font-size:11px">ESTA SESIÓN</span>
          {% endif %}
        </div>
        <div style="color:var(--text-dim);font-size:12px">
          {% if s.ip_at_login %}IP {{ s.ip_at_login }} · {% endif %}
          activa {{ s.last_seen_at|naturaltime }}
        </div>
        {% if s.session_key != current_session_key %}
          <form method="post" style="margin:0">
            {% csrf_token %}
            <input type="hidden" name="action" value="revoke_session">
            <input type="hidden" name="session_key" value="{{ s.session_key }}">
            <button type="submit" class="btn" style="color:var(--c-red);background:transparent;border:1px solid rgba(255,80,80,.4);font-size:12px;padding:6px 10px;align-self:flex-start">Cerrar</button>
          </form>
        {% endif %}
      </li>
    {% endfor %}
  </ul>

  {% if user_sessions|length > 1 %}
    <form method="post" style="margin:0">
      {% csrf_token %}
      <input type="hidden" name="action" value="revoke_others">
      <button type="submit" class="btn" style="color:var(--c-red);background:transparent;border:1px solid rgba(255,80,80,.4);font-size:13px;padding:8px 12px;align-self:flex-start">
        Cerrar todas las demás sesiones
      </button>
    </form>
  {% endif %}
</section>
```

- [ ] **Step 5: Incluir el partial en `my_account.html`**

Leer `templates/accounts/my_account.html`. Justo antes del cierre del bloque principal (después de las dos secciones de Perfil y Contraseña), añadir:

```html
{% include "accounts/_my_sessions.html" %}
```

- [ ] **Step 6: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_user_sessions_view.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Commit**

```bash
git add accounts/views.py templates/accounts/_my_sessions.html templates/accounts/my_account.html accounts/tests/test_user_sessions_view.py
git commit -m "feat(accounts): lista 'Mis sesiones' en Mi cuenta"
```

---

## Task 11: Acciones `revoke_session` y `revoke_others`

**Files:**
- Modify: `accounts/views.py`
- Modify: `accounts/tests/test_user_sessions_view.py`

- [ ] **Step 1: Tests de revocación**

Añadir a `accounts/tests/test_user_sessions_view.py`:

```python
from datetime import timedelta

from django.contrib.sessions.models import Session


def _create_session(session_key):
    Session.objects.create(
        session_key=session_key,
        session_data="",
        expire_date=timezone.now() + timedelta(days=30),
    )


def test_revoke_session_action_kills_specific_session(client):
    user = UserFactory(email="rs@edisa.com", password="Secret123")
    _login(client, user)
    _create_session("kill-this")
    UserSession.objects.create(
        user=user, session_key="kill-this", device_label="d", last_seen_at=timezone.now()
    )

    resp = client.post(
        reverse("accounts:my_account"),
        {"action": "revoke_session", "session_key": "kill-this"},
    )
    assert resp.status_code == 302
    assert not UserSession.objects.filter(session_key="kill-this").exists()


def test_revoke_session_rejects_current_session(client):
    user = UserFactory(email="rsc@edisa.com", password="Secret123")
    _login(client, user)
    current = client.session.session_key
    resp = client.post(
        reverse("accounts:my_account"),
        {"action": "revoke_session", "session_key": current},
    )
    assert resp.status_code == 400


def test_revoke_session_rejects_other_users_session(client):
    me = UserFactory(email="me@edisa.com", password="Secret123")
    other = UserFactory(email="o@edisa.com", password="Secret123")
    _login(client, me)
    UserSession.objects.create(
        user=other, session_key="other-key", device_label="d", last_seen_at=timezone.now()
    )
    resp = client.post(
        reverse("accounts:my_account"),
        {"action": "revoke_session", "session_key": "other-key"},
    )
    # Sigue valiendo, pero no debe haberla borrado
    assert UserSession.objects.filter(session_key="other-key").exists()


def test_revoke_others_kills_all_other_sessions(client):
    user = UserFactory(email="ro@edisa.com", password="Secret123")
    _login(client, user)
    for k in ["k1", "k2", "k3"]:
        UserSession.objects.create(
            user=user, session_key=k, device_label="d", last_seen_at=timezone.now()
        )
    resp = client.post(reverse("accounts:my_account"), {"action": "revoke_others"})
    assert resp.status_code == 302
    remaining = list(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
    assert remaining == [client.session.session_key]
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_user_sessions_view.py -v -k "revoke"
```

Expected: fallos porque las acciones todavía no se manejan.

- [ ] **Step 3: Implementar dispatch en `MyAccountView.post`**

En `accounts/views.py`, dentro de `MyAccountView`, el método `post` actualmente:

```python
def post(self, request):
    action = request.POST.get("action")
    if action == "profile":
        return self._post_profile(request)
    if action == "password":
        return self._post_password(request)
    return HttpResponseBadRequest("acción no válida")
```

Sustituir por:

```python
def post(self, request):
    action = request.POST.get("action")
    if action == "profile":
        return self._post_profile(request)
    if action == "password":
        return self._post_password(request)
    if action == "revoke_session":
        return self._post_revoke_session(request)
    if action == "revoke_others":
        return self._post_revoke_others(request)
    return HttpResponseBadRequest("acción no válida")
```

Y añadir los dos handlers al final de la clase:

```python
def _post_revoke_session(self, request):
    target = (request.POST.get("session_key") or "").strip()
    if not target or target == request.session.session_key:
        return HttpResponseBadRequest("sesión no válida")
    # Filtrar por user evita borrar sesiones ajenas aunque sepamos la session_key.
    keys = list(
        UserSession.objects.filter(user=request.user, session_key=target)
        .values_list("session_key", flat=True)
    )
    if keys:
        revoke_sessions(
            user=request.user,
            session_keys=keys,
            actor=request.user,
            reason="user_revoke",
        )
        messages.success(request, "Sesión cerrada.")
    return redirect("accounts:my_account")


def _post_revoke_others(self, request):
    others = list(
        UserSession.objects.filter(user=request.user)
        .exclude(session_key=request.session.session_key)
        .values_list("session_key", flat=True)
    )
    if others:
        n = revoke_sessions(
            user=request.user,
            session_keys=others,
            actor=request.user,
            reason="user_revoke_others",
        )
        messages.success(
            request,
            f"Se han cerrado {n} sesion{'es' if n != 1 else ''}.",
        )
    return redirect("accounts:my_account")
```

Importar arriba: `from .services.sessions import parse_device_label, revoke_sessions`.

- [ ] **Step 4: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_user_sessions_view.py -v
```

Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add accounts/views.py accounts/tests/test_user_sessions_view.py
git commit -m "feat(accounts): acciones revoke_session y revoke_others"
```

---

## Task 12: Invalidación en cambios de contraseña (voluntario, forzado, reset)

**Files:**
- Modify: `accounts/views.py`
- Modify: `accounts/tests/test_password_invalidation.py`

- [ ] **Step 1: Tests de invalidación**

Añadir a `accounts/tests/test_password_invalidation.py`:

```python
from django.urls import reverse
from django.utils import timezone

from accounts.services.password_reset import send_password_reset_email
from accounts.tests.factories import UserFactory


def _login(client, user, password="Secret123"):
    client.post(reverse("accounts:login"), {"email": user.email, "password": password, "remember": "1"})


def test_voluntary_password_change_kills_other_sessions_but_keeps_current(client):
    user = UserFactory(email="vp@edisa.com", password="Secret123")
    _login(client, user)
    current_key = client.session.session_key
    UserSession.objects.create(
        user=user, session_key="other-1", device_label="d", last_seen_at=timezone.now()
    )
    UserSession.objects.create(
        user=user, session_key="other-2", device_label="d", last_seen_at=timezone.now()
    )

    resp = client.post(
        reverse("accounts:my_account"),
        {
            "action": "password",
            "current": "Secret123",
            "new1": "NewPass123",
            "new2": "NewPass123",
        },
    )
    assert resp.status_code == 302
    remaining = list(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
    assert remaining == [current_key]


def test_forced_password_change_kills_other_sessions(client):
    user = UserFactory(email="fp@edisa.com", password="Secret123")
    user.must_change_password = True
    user.save(update_fields=["must_change_password"])
    _login(client, user)
    UserSession.objects.create(
        user=user, session_key="other", device_label="d", last_seen_at=timezone.now()
    )

    client.post(
        reverse("accounts:change_password"),
        {"current": "Secret123", "new1": "NewPass123", "new2": "NewPass123"},
    )
    assert not UserSession.objects.filter(session_key="other").exists()


def test_email_reset_kills_all_sessions(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = UserFactory(email="er@edisa.com", password="Secret123")
    _login(client, user)
    current_key = client.session.session_key

    # Generar token real
    send_password_reset_email(user, purpose="reset")

    # Localizar URL del email
    from django.core import mail
    body = mail.outbox[-1].body
    # extraer URL /recuperar/<uid>/reset/<token>/
    import re
    match = re.search(r"(/recuperar/[^\s]+/reset/[^\s]+/)", body)
    assert match, body
    confirm_url = match.group(1)

    # Cliente nuevo (anónimo) para usar el link
    from django.test import Client
    anon = Client()
    resp = anon.post(confirm_url, {"new_password1": "NewPass123", "new_password2": "NewPass123"})
    assert resp.status_code == 302

    # Todas las UserSession del usuario deben haberse borrado
    assert UserSession.objects.filter(user=user).count() == 0
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_password_invalidation.py -v
```

Expected: los 3 nuevos fallan.

- [ ] **Step 3: Modificar `MyAccountView._post_password`**

En `accounts/views.py`, dentro de `_post_password`, justo después de `update_session_auth_hash(request, request.user)` y antes del `AuditLog.objects.create`, añadir:

```python
others = list(
    UserSession.objects.filter(user=request.user)
    .exclude(session_key=request.session.session_key)
    .values_list("session_key", flat=True)
)
revoke_sessions(
    user=request.user,
    session_keys=others,
    actor=request.user,
    reason="password_change",
)
```

Y cambiar el mensaje:

```python
if others:
    messages.success(request, f"Contraseña actualizada. Se han cerrado {len(others)} otra{'s' if len(others) != 1 else ''} sesion{'es' if len(others) != 1 else ''}.")
else:
    messages.success(request, "Contraseña actualizada.")
```

- [ ] **Step 4: Modificar `ChangePasswordView.post`**

Mismo patrón, justo tras `update_session_auth_hash(request, request.user)`:

```python
others = list(
    UserSession.objects.filter(user=request.user)
    .exclude(session_key=request.session.session_key)
    .values_list("session_key", flat=True)
)
revoke_sessions(
    user=request.user,
    session_keys=others,
    actor=request.user,
    reason="password_change_forced",
)
```

- [ ] **Step 5: Modificar `PasswordResetConfirmView.post`**

Tras `user.save(update_fields=["must_change_password"])` y antes del `AuditLog.objects.create`:

```python
all_keys = list(
    UserSession.objects.filter(user=user).values_list("session_key", flat=True)
)
revoke_sessions(
    user=user,
    session_keys=all_keys,
    actor=None,
    reason="password_reset_email",
)
```

- [ ] **Step 6: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_password_invalidation.py -v
```

Expected: 4 passed.

- [ ] **Step 7: Commit**

```bash
git add accounts/views.py accounts/tests/test_password_invalidation.py
git commit -m "feat(accounts): invalidar sesiones en cambios de contraseña"
```

---

## Task 13: Email de notificación tras cambio de contraseña

**Files:**
- Create: `accounts/services/notifications.py`
- Create: `templates/accounts/emails/password_changed.txt`
- Modify: `accounts/views.py`
- Modify: `accounts/tests/test_password_invalidation.py`

- [ ] **Step 1: Test de envío de email**

Añadir a `accounts/tests/test_password_invalidation.py`:

```python
def test_voluntary_password_change_sends_notification_email(client, settings):
    settings.EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
    user = UserFactory(email="np@edisa.com", password="Secret123")
    _login(client, user)
    from django.core import mail
    mail.outbox = []

    client.post(
        reverse("accounts:my_account"),
        {"action": "password", "current": "Secret123", "new1": "NewPass123", "new2": "NewPass123"},
    )
    assert len(mail.outbox) == 1
    assert "contraseña" in mail.outbox[0].subject.lower()
    assert mail.outbox[0].to == ["np@edisa.com"]
```

- [ ] **Step 2: Ejecutar test — debe fallar**

```bash
pytest accounts/tests/test_password_invalidation.py::test_voluntary_password_change_sends_notification_email -v
```

Expected: `assert len(mail.outbox) == 1` falla (0).

- [ ] **Step 3: Crear plantilla del email**

`templates/accounts/emails/password_changed.txt`:

```
Hola {{ user.name }},

Tu contraseña en La Porra del Jefe se ha cambiado el {{ when|date:"d/m/Y H:i" }}.

Si has sido tú, no tienes que hacer nada.
Si no has sido tú, recupera el acceso inmediatamente en:
{{ reset_url }}

Y avisa al gestor para que revise la actividad de tu cuenta.

— El Jefe
```

- [ ] **Step 4: Servicio de notificación**

`accounts/services/notifications.py`:

```python
from django.conf import settings
from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone


def send_password_changed_email(user) -> None:
    """Avisa al usuario de que su contraseña se ha cambiado."""
    reset_url = settings.SITE_URL.rstrip("/") + reverse("accounts:password_reset")
    body = render_to_string(
        "accounts/emails/password_changed.txt",
        {"user": user, "when": timezone.localtime(), "reset_url": reset_url},
    )
    send_mail(
        subject="Tu contraseña en La Porra del Jefe se ha cambiado",
        message=body,
        from_email=settings.PASSWORD_RESET_FROM_EMAIL,
        recipient_list=[user.email],
        fail_silently=True,
    )
```

`fail_silently=True` evita que un fallo de SMTP rompa el flujo de cambio de contraseña; el log de Django lo recogerá.

- [ ] **Step 5: Llamar al servicio en los 3 flujos**

En `accounts/views.py`, importar:

```python
from .services.notifications import send_password_changed_email
```

Añadir `send_password_changed_email(request.user)` tras el `revoke_sessions` en:
- `MyAccountView._post_password`
- `ChangePasswordView.post`

Y `send_password_changed_email(user)` tras el `revoke_sessions` en `PasswordResetConfirmView.post`.

- [ ] **Step 6: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_password_invalidation.py -v
```

Expected: todos pasan.

- [ ] **Step 7: Commit**

```bash
git add accounts/services/notifications.py templates/accounts/emails/password_changed.txt accounts/views.py accounts/tests/test_password_invalidation.py
git commit -m "feat(accounts): email de notificación tras cambio de contraseña"
```

---

## Task 14: Management command `prune_user_sessions`

**Files:**
- Create: `accounts/management/__init__.py` (si no existe)
- Create: `accounts/management/commands/__init__.py` (si no existe)
- Create: `accounts/management/commands/prune_user_sessions.py`
- Create: `accounts/tests/test_prune_user_sessions.py`

- [ ] **Step 1: Tests del command**

`accounts/tests/test_prune_user_sessions.py`:

```python
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management import call_command
from django.utils import timezone

from accounts.models import UserSession
from accounts.tests.factories import UserFactory


def _create_session(key, expire_in_days=30):
    Session.objects.create(
        session_key=key,
        session_data="",
        expire_date=timezone.now() + timedelta(days=expire_in_days),
    )


def test_prune_removes_orphans_without_session():
    user = UserFactory()
    UserSession.objects.create(
        user=user, session_key="orphan", device_label="d", last_seen_at=timezone.now()
    )
    call_command("prune_user_sessions")
    assert not UserSession.objects.filter(session_key="orphan").exists()


def test_prune_removes_stale_user_sessions():
    user = UserFactory()
    _create_session("ok")
    UserSession.objects.create(
        user=user,
        session_key="ok",
        device_label="d",
        last_seen_at=timezone.now() - timedelta(days=40),
    )
    call_command("prune_user_sessions")
    assert not UserSession.objects.filter(session_key="ok").exists()


def test_prune_keeps_valid_user_sessions():
    user = UserFactory()
    _create_session("good")
    UserSession.objects.create(
        user=user,
        session_key="good",
        device_label="d",
        last_seen_at=timezone.now() - timedelta(days=2),
    )
    call_command("prune_user_sessions")
    assert UserSession.objects.filter(session_key="good").exists()
```

- [ ] **Step 2: Ejecutar tests — deben fallar**

```bash
pytest accounts/tests/test_prune_user_sessions.py -v
```

Expected: `CommandError: Unknown command 'prune_user_sessions'`.

- [ ] **Step 3: Crear paquetes `management/commands`**

```bash
mkdir -p accounts/management/commands
touch accounts/management/__init__.py
touch accounts/management/commands/__init__.py
```

- [ ] **Step 4: Implementar el command**

`accounts/management/commands/prune_user_sessions.py`:

```python
from datetime import timedelta

from django.contrib.sessions.models import Session
from django.core.management.base import BaseCommand
from django.utils import timezone

from accounts.models import UserSession

STALE_THRESHOLD_DAYS = 35


class Command(BaseCommand):
    help = "Borra UserSession huérfanas (sin Session real) o con last_seen_at > 35 días."

    def handle(self, *args, **options):
        active_keys = set(Session.objects.values_list("session_key", flat=True))
        cutoff = timezone.now() - timedelta(days=STALE_THRESHOLD_DAYS)

        orphan_qs = UserSession.objects.exclude(session_key__in=active_keys)
        stale_qs = UserSession.objects.filter(last_seen_at__lt=cutoff)

        # Combinar pks para una sola pasada (evita doble delete sobre la misma fila)
        pks = set(orphan_qs.values_list("pk", flat=True)) | set(stale_qs.values_list("pk", flat=True))
        deleted, _ = UserSession.objects.filter(pk__in=pks).delete()

        self.stdout.write(self.style.SUCCESS(f"Pruned {deleted} UserSession rows."))
```

- [ ] **Step 5: Ejecutar tests — deben pasar**

```bash
pytest accounts/tests/test_prune_user_sessions.py -v
```

Expected: 3 passed.

- [ ] **Step 6: Commit**

```bash
git add accounts/management/__init__.py accounts/management/commands/__init__.py accounts/management/commands/prune_user_sessions.py accounts/tests/test_prune_user_sessions.py
git commit -m "feat(accounts): management command prune_user_sessions"
```

---

## Task 15: Suite final, lint y smoke test manual

**Files:** (sin cambios de código nuevos salvo arreglos)

- [ ] **Step 1: Ejecutar la suite completa**

```bash
pytest -x
```

Expected: all green.

- [ ] **Step 2: Lint**

```bash
ruff check accounts porra26
```

Expected: `All checks passed!`. Si falla, arreglar y volver a correr.

- [ ] **Step 3: Smoke test manual**

```bash
python manage.py migrate
python manage.py runserver
```

Abre `http://127.0.0.1:8000/` y verifica:

1. Login con checkbox **marcado** → entra al dashboard.
2. Ir a `/mi-cuenta/`. Debe aparecer sección "Mis sesiones" con la sesión actual marcada `[ESTA SESIÓN]`.
3. Crear una segunda sesión: abrir incógnito, login con el mismo usuario. Volver a la sesión original, refrescar `/mi-cuenta/`: debe verse la nueva sesión con botón "Cerrar".
4. Pulsar "Cerrar" en la otra sesión → en incógnito, refrescar y debe redirigir a login.
5. Cambiar contraseña desde "Mi cuenta" con dos sesiones abiertas: la otra debe quedar cerrada al refrescar.

Detén el servidor.

- [ ] **Step 4: Commit (si lint metió cambios)**

```bash
git status
# Si hay cambios:
git add -A
git commit -m "chore: lint fixes"
```

---

## Task 16: PR y merge

**Files:** ninguno.

- [ ] **Step 1: Push del branch**

```bash
git push -u origin worktree-remember-me
```

- [ ] **Step 2: Crear PR**

```bash
gh pr create --title "feat(auth): 'Recordarme' seguro con gestión de sesiones" --body "$(cat <<'EOF'
## Summary
- Checkbox 'Recordarme' en login (pre-marcado). Sesión de 30 días con renovación por uso si está activo; expira al cerrar navegador si se desmarca.
- Tabla `UserSession` con metadatos por sesión (device, IP de login, last_seen, is_pwa).
- Sección 'Mis sesiones' en `/mi-cuenta/` con lista de dispositivos y botones de revocación (individual y "cerrar todas las demás").
- Invalidación robusta de sesiones en los tres flujos de cambio de contraseña: voluntario (mantiene la sesión actual), reset por email (cierra TODAS), forzado. Signal `post_save` cubre cambios desde el admin.
- Email de notificación al usuario cuando se le cambia la contraseña.
- Management command `prune_user_sessions` para limpieza periódica.

Spec: `docs/superpowers/specs/2026-06-05-remember-me-design.md`
Plan: `docs/superpowers/plans/2026-06-05-remember-me.md`

## Test plan
- [x] Suite completa pytest verde
- [x] Lint ruff verde
- [ ] Smoke manual (ver paso 15.3 del plan)
- [ ] Tras merge: configurar cron en Railway para `python manage.py prune_user_sessions` diario
EOF
)"
```

- [ ] **Step 3: Esperar CI**

```bash
gh pr checks --watch
```

- [ ] **Step 4: Merge**

```bash
PR_NUMBER=$(gh pr view --json number -q .number)
gh pr merge "$PR_NUMBER" --squash --delete-branch
```

- [ ] **Step 5: Verificar deploy en Railway**

Railway auto-despliega desde `main`. Esperar 2-3 minutos y verificar `https://laporradeljefe.es/` carga, hacer login con `remember` marcado y comprobar `/mi-cuenta/` muestra la sección.

---

## Notas finales

- El cron de Railway para `prune_user_sessions` queda como tarea operacional fuera de este PR: la feature funciona sin él (la tabla crece despacio).
- Si en el futuro se añade cambio de email, **debe** llamar a `revoke_sessions` con todas las keys, igual que el reset por email.
- `SESSION_COOKIE_SECURE = True` solo aplica en `prod.py` para no romper dev local sin HTTPS.
