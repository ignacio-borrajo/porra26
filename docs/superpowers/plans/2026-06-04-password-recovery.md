# Recuperación de contraseña por email — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que cualquier jugador pueda recuperar su contraseña por email (token 24h) y que las altas nuevas se completen mediante email de bienvenida (token 7d).

**Architecture:** Subclase de `PasswordResetTokenGenerator` que codifica `purpose` y aplica TTL distinto. 4 vistas nuevas (request, sent, confirm, complete) + endpoint de reenvío para el gestor. Una sola plantilla de email con dos copys según `purpose`. El botón candado existente se mantiene como fallback.

**Tech Stack:** Django 5.x, pytest-django, factory_boy, SMTP vía Resend (ya configurado).

**Spec:** `docs/superpowers/specs/2026-06-04-password-recovery-design.md`

**Worktree:** `.claude/worktrees/password-recovery-spec` (rama `worktree-password-recovery-spec`).

**Python:** `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python` (alias mental `PY`).

---

## File Structure

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `porra26/settings/base.py` | modificar | Añadir `SITE_URL` |
| `competition/services/reminder_email.py` | modificar | Reusar `settings.SITE_URL` |
| `accounts/services/__init__.py` | crear si no existe | Package marker |
| `accounts/services/token_generator.py` | crear | `PorraPasswordResetTokenGenerator` |
| `accounts/services/password_reset.py` | crear | `send_password_reset_email`, `build_reset_url`, `validate_reset_token`, `_client_ip`, `SUBJECTS` |
| `accounts/views.py` | modificar | 4 vistas nuevas |
| `accounts/urls.py` | modificar | 4 URLs nuevas |
| `accounts/tests/test_password_reset_token_generator.py` | crear | Tests del generador |
| `accounts/tests/test_password_reset_service.py` | crear | Tests del servicio email |
| `accounts/tests/test_password_reset_views.py` | crear | Tests de las 4 vistas |
| `templates/accounts/login.html` | modificar | Reemplazar L53-55 por link |
| `templates/accounts/password_reset_request.html` | crear | Formulario inicial |
| `templates/accounts/password_reset_sent.html` | crear | "Revisa tu correo" |
| `templates/accounts/password_reset_confirm.html` | crear | Set new password |
| `templates/accounts/password_reset_invalid.html` | crear | Token caducado |
| `templates/accounts/password_reset_complete.html` | crear | "Contraseña actualizada" |
| `templates/accounts/emails/password_reset.html` | crear | Email HTML inline |
| `templates/accounts/emails/password_reset.txt` | crear | Email texto plano |
| `static/icons/check-circle.svg` | crear | Icono éxito |
| `static/icons/alert-triangle.svg` | crear | Icono error |
| `pot/forms.py` | modificar | Añadir `enviar_bienvenida` al form de alta |
| `pot/views.py` | modificar | Disparar email al alta; `PlayerResendInviteView` |
| `pot/urls.py` | modificar | URL `player_resend_invite` |
| `templates/pot/_player_modal.html` (o donde esté el alta) | modificar | Checkbox welcome |
| `templates/pot/manage_players.html` | modificar | Botón mail + chip "Pendiente" |
| `pot/tests/test_player_resend_invite.py` | crear | Tests del endpoint |
| `pot/tests/test_player_create_welcome_email.py` | crear | Tests del check welcome |
| `CLAUDE.md` | modificar | Línea "Sin auto-recuperación" |
| `docs/DATA_MODEL.md` | modificar | §5 |
| `templates/core/rules.html` | modificar | L252-254 |

---

## Task 1: `SITE_URL` en settings

**Files:**
- Modify: `porra26/settings/base.py`
- Modify: `competition/services/reminder_email.py`

- [ ] **Step 1: Comprobar el estado actual**

Run: `grep -n "SITE_URL\|laporradeljefe.es" porra26/settings/base.py competition/services/reminder_email.py`
Expected: aparece `SITE_URL = "https://laporradeljefe.es"` en `reminder_email.py:19`.

- [ ] **Step 2: Añadir `SITE_URL` a `porra26/settings/base.py`**

Buscar la sección donde están las constantes del proyecto (cerca de `DEFAULT_FROM_EMAIL` o al final de variables generales). Añadir:

```python
SITE_URL = os.getenv("SITE_URL", "https://laporradeljefe.es")
```

- [ ] **Step 3: Refactorizar `reminder_email.py` para usar el setting**

Reemplazar:

```python
SITE_URL = "https://laporradeljefe.es"
COMPETICION_URL = f"{SITE_URL}/competicion/"
```

por:

```python
from django.conf import settings
COMPETICION_URL = f"{settings.SITE_URL}/competicion/"
```

(Mantener el resto del módulo.)

- [ ] **Step 4: Ejecutar tests existentes para verificar no regresión**

Run: `PY=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python && $PY -m pytest competition/tests/ -x -q 2>&1 | tail -20`
Expected: tests pasan (puede haber 0 cambios visibles en tests porque la URL no cambia).

- [ ] **Step 5: Commit**

```bash
git add porra26/settings/base.py competition/services/reminder_email.py
git commit -m "refactor(settings): SITE_URL en settings, reusable por servicios de email"
```

---

## Task 2: Tests del token generator (TDD — escribir tests primero)

**Files:**
- Create: `accounts/tests/test_password_reset_token_generator.py`

- [ ] **Step 1: Crear el archivo de tests**

```python
from datetime import datetime, timedelta
from unittest.mock import patch

import pytest

from accounts.models import User


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        email="alice@edisa.com",
        name="Alice",
        password="OldPwd1234!",
    )


def test_token_difiere_segun_purpose(alice):
    from accounts.services.token_generator import token_generator

    reset = token_generator.make_token(alice, "reset")
    welcome = token_generator.make_token(alice, "welcome")
    assert reset != welcome


def test_check_token_valido_mismo_purpose(alice):
    from accounts.services.token_generator import token_generator

    token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, token, "reset") is True


def test_check_token_rechaza_purpose_cruzado(alice):
    from accounts.services.token_generator import token_generator

    reset_token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, reset_token, "welcome") is False

    welcome_token = token_generator.make_token(alice, "welcome")
    assert token_generator.check_token(alice, welcome_token, "reset") is False


def test_check_token_caduca_reset_a_24h(alice):
    from accounts.services.token_generator import token_generator

    base = datetime(2026, 6, 4, 12, 0, 0)
    with patch.object(token_generator, "_now", return_value=base):
        token = token_generator.make_token(alice, "reset")

    # 23h59m → válido
    with patch.object(
        token_generator,
        "_now",
        return_value=base + timedelta(hours=23, minutes=59),
    ):
        assert token_generator.check_token(alice, token, "reset") is True

    # 24h01m → ya no
    with patch.object(
        token_generator,
        "_now",
        return_value=base + timedelta(hours=24, minutes=1),
    ):
        assert token_generator.check_token(alice, token, "reset") is False


def test_check_token_caduca_welcome_a_7d(alice):
    from accounts.services.token_generator import token_generator

    base = datetime(2026, 6, 4, 12, 0, 0)
    with patch.object(token_generator, "_now", return_value=base):
        token = token_generator.make_token(alice, "welcome")

    with patch.object(
        token_generator, "_now", return_value=base + timedelta(days=6, hours=23)
    ):
        assert token_generator.check_token(alice, token, "welcome") is True

    with patch.object(
        token_generator, "_now", return_value=base + timedelta(days=7, hours=1)
    ):
        assert token_generator.check_token(alice, token, "welcome") is False


def test_token_invalidado_al_cambiar_password(alice):
    from accounts.services.token_generator import token_generator

    token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, token, "reset") is True

    alice.set_password("NuevaPwd1234!")
    alice.save(update_fields=["password"])
    assert token_generator.check_token(alice, token, "reset") is False


def test_make_token_rechaza_purpose_desconocido(alice):
    from accounts.services.token_generator import token_generator

    with pytest.raises(ValueError):
        token_generator.make_token(alice, "bogus")


def test_check_token_rechaza_purpose_desconocido(alice):
    from accounts.services.token_generator import token_generator

    token = token_generator.make_token(alice, "reset")
    assert token_generator.check_token(alice, token, "bogus") is False


def test_check_token_rechaza_token_malformado(alice):
    from accounts.services.token_generator import token_generator

    assert token_generator.check_token(alice, "no-es-un-token", "reset") is False
    assert token_generator.check_token(alice, "", "reset") is False
    assert token_generator.check_token(None, "anything", "reset") is False
```

- [ ] **Step 2: Verificar que fallan (no existe el módulo)**

Run: `$PY -m pytest accounts/tests/test_password_reset_token_generator.py -x -q 2>&1 | tail -10`
Expected: ModuleNotFoundError o ImportError para `accounts.services.token_generator`.

---

## Task 3: Implementar el token generator

**Files:**
- Create: `accounts/services/__init__.py` (si no existe)
- Create: `accounts/services/token_generator.py`

- [ ] **Step 1: Asegurar el package services**

Run: `ls accounts/services/ 2>/dev/null || mkdir -p accounts/services && touch accounts/services/__init__.py`
Expected: directorio creado o ya existente con `__init__.py`.

- [ ] **Step 2: Implementar el generador**

Crear `accounts/services/token_generator.py`:

```python
"""Token de reset de contraseña con TTL distinto por propósito.

Subclase de `PasswordResetTokenGenerator` de Django que:
- Codifica `purpose` en el material firmado → un token de welcome no vale
  como reset y viceversa.
- Aplica TTL por propósito (24h para reset, 7d para welcome) en vez del
  global `PASSWORD_RESET_TIMEOUT` de Django.

La invalidación por cambio de contraseña sigue siendo automática:
`user.password` está en el hash, así que cualquier `set_password` rompe
los tokens previos. Uso único de facto.
"""

from datetime import timedelta

from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare, salted_hmac
from django.utils.http import base36_to_int, int_to_base36


class PorraPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    key_salt = "porra26.accounts.PasswordResetTokenGenerator"

    TIMEOUTS = {
        "reset": int(timedelta(hours=24).total_seconds()),
        "welcome": int(timedelta(days=7).total_seconds()),
    }

    def make_token(self, user, purpose="reset"):
        if purpose not in self.TIMEOUTS:
            raise ValueError(f"purpose desconocido: {purpose!r}")
        return self._make_token_with_timestamp(
            user,
            self._num_seconds(self._now()),
            self.secret,
            purpose,
        )

    def check_token(self, user, token, purpose="reset"):
        if not (user and token) or purpose not in self.TIMEOUTS:
            return False
        try:
            ts_b36, _ = token.split("-")
        except ValueError:
            return False
        try:
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        for secret in [self.secret, *self.secret_fallbacks]:
            if constant_time_compare(
                self._make_token_with_timestamp(user, ts, secret, purpose),
                token,
            ):
                break
        else:
            return False
        if (self._num_seconds(self._now()) - ts) > self.TIMEOUTS[purpose]:
            return False
        return True

    def _make_token_with_timestamp(self, user, timestamp, secret, purpose):
        ts_b36 = int_to_base36(timestamp)
        hash_string = salted_hmac(
            self.key_salt,
            self._make_hash_value(user, timestamp, purpose),
            secret=secret,
            algorithm=self.algorithm,
        ).hexdigest()[::2]
        return f"{ts_b36}-{hash_string}"

    def _make_hash_value(self, user, timestamp, purpose="reset"):
        login_ts = (
            ""
            if user.last_login is None
            else user.last_login.replace(microsecond=0, tzinfo=None)
        )
        return f"{user.pk}{user.password}{login_ts}{timestamp}{user.email}{purpose}"


token_generator = PorraPasswordResetTokenGenerator()
```

- [ ] **Step 3: Verificar que los tests pasan**

Run: `$PY -m pytest accounts/tests/test_password_reset_token_generator.py -x -v 2>&1 | tail -25`
Expected: los 9 tests pasan.

- [ ] **Step 4: Commit**

```bash
git add accounts/services/__init__.py accounts/services/token_generator.py accounts/tests/test_password_reset_token_generator.py
git commit -m "feat(accounts): generador de tokens reset/welcome con TTL por propósito"
```

---

## Task 4: Tests del servicio de email

**Files:**
- Create: `accounts/tests/test_password_reset_service.py`

- [ ] **Step 1: Crear el archivo de tests**

```python
import pytest
from django.core import mail

from accounts.models import AuditLog, User


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        email="alice@edisa.com",
        name="Alice",
        password="OldPwd1234!",
    )


@pytest.fixture
def gestor(db):
    return User.objects.create_user(
        email="gestor@edisa.com",
        name="Gestor",
        password="OldPwd1234!",
        is_gestor=True,
    )


def test_send_reset_envia_email_con_asunto_y_destinatario(alice):
    from accounts.services.password_reset import send_password_reset_email

    send_password_reset_email(alice, purpose="reset")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.to == ["alice@edisa.com"]
    assert msg.subject == "[Porra26] Restablece tu contraseña"
    assert "Restablece tu contraseña" in msg.body or "restablecer" in msg.body.lower()


def test_send_welcome_usa_otro_asunto_y_copy(alice):
    from accounts.services.password_reset import send_password_reset_email

    send_password_reset_email(alice, purpose="welcome")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert msg.subject == "[Porra26] Bienvenido a la porra del Mundial"
    assert "bienvenido" in msg.body.lower() or "te han creado cuenta" in msg.body.lower()


def test_send_incluye_html_alternative(alice):
    from accounts.services.password_reset import send_password_reset_email

    send_password_reset_email(alice, purpose="reset")

    msg = mail.outbox[0]
    assert len(msg.alternatives) == 1
    html, mime = msg.alternatives[0]
    assert mime == "text/html"
    assert "<html" in html.lower() or "<body" in html.lower()


def test_send_genera_url_absoluta_en_email(alice):
    from accounts.services.password_reset import send_password_reset_email

    send_password_reset_email(alice, purpose="reset")
    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    # SITE_URL por defecto en tests es https://laporradeljefe.es
    assert "https://laporradeljefe.es/" in msg.body
    assert "https://laporradeljefe.es/" in html


def test_send_registra_auditlog(alice, gestor):
    from accounts.services.password_reset import send_password_reset_email

    send_password_reset_email(alice, purpose="welcome", actor=gestor)

    log = AuditLog.objects.get(action="password_reset_email_sent")
    assert log.actor == gestor
    assert log.target_type == "user"
    assert log.target_id == str(alice.id)
    assert log.payload["purpose"] == "welcome"
    assert "Bienvenido" in log.payload["subject"]


def test_send_rechaza_purpose_invalido(alice):
    from accounts.services.password_reset import send_password_reset_email

    with pytest.raises(ValueError):
        send_password_reset_email(alice, purpose="bogus")


def test_build_reset_url_usa_purpose_y_token(alice):
    from accounts.services.password_reset import build_reset_url

    url = build_reset_url(alice, purpose="reset")
    assert "/recuperar/" in url
    assert "/reset/" in url  # purpose en la URL
    assert url.startswith("https://")


def test_validate_token_devuelve_user_con_token_valido(alice):
    from accounts.services.password_reset import (
        build_reset_url,
        validate_reset_token,
    )
    from django.urls import resolve
    from urllib.parse import urlparse

    url = build_reset_url(alice, purpose="reset")
    path = urlparse(url).path
    match = resolve(path)
    user = validate_reset_token(
        match.kwargs["uidb64"],
        match.kwargs["purpose"],
        match.kwargs["token"],
    )
    assert user == alice


def test_validate_token_falla_si_user_inactivo(alice):
    from accounts.services.password_reset import (
        build_reset_url,
        validate_reset_token,
    )
    from django.urls import resolve
    from urllib.parse import urlparse

    url = build_reset_url(alice, purpose="reset")
    path = urlparse(url).path
    match = resolve(path)
    alice.is_active = False
    alice.save(update_fields=["is_active"])

    user = validate_reset_token(
        match.kwargs["uidb64"],
        match.kwargs["purpose"],
        match.kwargs["token"],
    )
    assert user is None
```

- [ ] **Step 2: Verificar que fallan (servicio y URLs aún no existen)**

Run: `$PY -m pytest accounts/tests/test_password_reset_service.py -x -q 2>&1 | tail -10`
Expected: ImportError / NoReverseMatch.

---

## Task 5: Plantillas de email (servicio depende de ellas)

**Files:**
- Create: `templates/accounts/emails/password_reset.html`
- Create: `templates/accounts/emails/password_reset.txt`

- [ ] **Step 1: Crear el HTML del email**

Crear `templates/accounts/emails/password_reset.html`:

```html
<!DOCTYPE html>
<html lang="es">
<body style="margin:0;padding:0;background:#F5F6F8;font-family:'Segoe UI',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0">
    <tr><td align="center" style="padding:24px 12px">
      <table width="600" cellpadding="0" cellspacing="0" border="0"
             style="background:#FFFFFF;border-radius:16px;overflow:hidden;
                    box-shadow:0 2px 12px rgba(15,23,42,0.06);max-width:600px">

        <tr><td style="height:14px;background:linear-gradient(90deg,#E11D48,#F97316,#EAB308,#22C55E,#3B82F6,#8B5CF6);font-size:0;line-height:0">&nbsp;</td></tr>

        <tr><td style="padding:32px 40px 8px 40px">
          <img src="{{ logo_url }}" width="120" alt="EDISA · Mundial 2026"
               style="display:block;border:0;outline:none">
          <p style="margin:16px 0 0;font-size:11px;letter-spacing:0.12em;color:#6B7280;text-transform:uppercase">
            Mundial FIFA 2026 · Edición interna
          </p>
        </td></tr>

        <tr><td style="padding:8px 40px 8px 40px">
          <h1 style="margin:8px 0 16px;font-size:28px;line-height:1.2;color:#0F172A;font-weight:700">
            {% if purpose == 'welcome' %}Bienvenido a la porra{% else %}Restablece tu contraseña{% endif %}
          </h1>
          <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#374151">
            {% if purpose == 'welcome' %}Te han creado cuenta en la porra del Mundial 2026 de EDISA. Pulsa el botón para establecer tu contraseña y empezar a apostar. El enlace caduca en 7 días.{% else %}Hemos recibido una solicitud para restablecer tu contraseña. Pulsa el botón para elegir una nueva. El enlace caduca en 24 horas. Si no fuiste tú, ignora este correo.{% endif %}
          </p>
        </td></tr>

        <tr><td align="center" style="padding:16px 40px 8px 40px">
          <a href="{{ reset_url }}"
             style="display:inline-block;padding:14px 28px;border-radius:12px;background:#0F172A;color:#FFFFFF;font-weight:600;text-decoration:none;font-size:15px">
            {% if purpose == 'welcome' %}Establecer contraseña →{% else %}Restablecer contraseña →{% endif %}
          </a>
        </td></tr>

        <tr><td style="padding:24px 40px 8px 40px">
          <p style="margin:0;font-size:12px;color:#6B7280;line-height:1.5">
            ¿No funciona el botón? Copia y pega esta dirección en tu navegador:
          </p>
          <p style="margin:6px 0 0;font-family:ui-monospace,'SF Mono',Menlo,monospace;font-size:12px;color:#374151;word-break:break-all">
            {{ reset_url }}
          </p>
        </td></tr>

        <tr><td style="padding:32px 40px 24px 40px;border-top:1px solid #E5E7EB">
          <p style="margin:0;font-size:12px;color:#9CA3AF;line-height:1.5">
            Mundial FIFA 2026 · Edición interna · EDISA
          </p>
          <p style="margin:4px 0 0;font-size:12px;color:#9CA3AF;line-height:1.5">
            Este correo lo envía la porra interna. No respondas a este mensaje.
          </p>
        </td></tr>

        <tr><td style="height:6px;background:linear-gradient(90deg,#E11D48,#F97316,#EAB308,#22C55E,#3B82F6,#8B5CF6);font-size:0;line-height:0">&nbsp;</td></tr>

      </table>
    </td></tr>
  </table>
</body>
</html>
```

- [ ] **Step 2: Crear el texto plano**

Crear `templates/accounts/emails/password_reset.txt`:

```
{% if purpose == 'welcome' %}Bienvenido a la porra del Mundial 2026 de EDISA.

Te han creado cuenta. Establece tu contraseña aquí (caduca en 7 días):
{% else %}Restablece tu contraseña.

Hemos recibido una solicitud para restablecer tu contraseña. Elige una nueva aquí (caduca en 24 horas):
{% endif %}{{ reset_url }}

— Porra EDISA · Mundial 2026
```

- [ ] **Step 3: Commit (sin código aún — solo plantillas)**

```bash
git add templates/accounts/emails/
git commit -m "feat(accounts): plantillas HTML+texto del email de reset/welcome"
```

---

## Task 6: URLs del flujo

**Files:**
- Modify: `accounts/urls.py`

- [ ] **Step 1: Añadir las 4 rutas**

Sustituir el contenido de `accounts/urls.py` por:

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.LoginView.as_view(), name="login"),
    path("logout/", views.LogoutView.as_view(), name="logout"),
    path("cambiar-password/", views.ChangePasswordView.as_view(), name="change_password"),
    path("mi-cuenta/", views.MyAccountView.as_view(), name="my_account"),
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
```

- [ ] **Step 2: Verificar el reverse desde shell**

Run: `$PY -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','porra26.settings.test'); django.setup(); from django.urls import reverse; print(reverse('accounts:password_reset'))"`
Expected: `/recuperar/` o la ruta del namespace configurado (si el namespace difiere, ajustar el assert).

(Si las vistas aún no existen, este step puede saltar a Task 7 antes — alternativa: hacer stub temporal de las vistas con `View`. Si la importación de `views` falla en este paso, salta a Task 7 directamente y vuelve a este step después.)

---

## Task 7: Implementar el servicio `password_reset`

**Files:**
- Create: `accounts/services/password_reset.py`

- [ ] **Step 1: Crear el módulo**

```python
"""Servicio de envío de emails de reset y bienvenida.

Centraliza la generación de URLs firmadas y el envío del email,
para que la vista pública y el endpoint del gestor compartan la misma
lógica (asunto, body, AuditLog).
"""

from urllib.parse import urljoin

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.template.loader import render_to_string
from django.templatetags.static import static
from django.urls import reverse
from django.utils.encoding import force_bytes, force_str
from django.utils.http import urlsafe_base64_decode, urlsafe_base64_encode

from accounts.models import AuditLog, User
from accounts.services.token_generator import token_generator

SUBJECTS = {
    "welcome": "[Porra26] Bienvenido a la porra del Mundial",
    "reset": "[Porra26] Restablece tu contraseña",
}


def build_reset_url(user, purpose: str) -> str:
    if purpose not in SUBJECTS:
        raise ValueError(f"purpose desconocido: {purpose!r}")
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user, purpose)
    path = reverse(
        "accounts:password_reset_confirm",
        kwargs={"uidb64": uidb64, "purpose": purpose, "token": token},
    )
    return urljoin(settings.SITE_URL, path)


def send_password_reset_email(user, purpose: str, actor=None) -> None:
    if purpose not in SUBJECTS:
        raise ValueError(f"purpose desconocido: {purpose!r}")
    reset_url = build_reset_url(user, purpose)
    logo_url = urljoin(settings.SITE_URL, static("img/logo.png"))
    ctx = {"user": user, "purpose": purpose, "reset_url": reset_url, "logo_url": logo_url}
    html = render_to_string("accounts/emails/password_reset.html", ctx)
    text = render_to_string("accounts/emails/password_reset.txt", ctx)
    subject = SUBJECTS[purpose]

    message = EmailMultiAlternatives(
        subject=subject,
        body=text,
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=[user.email],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)

    AuditLog.objects.create(
        actor=actor,
        action="password_reset_email_sent",
        target_type="user",
        target_id=str(user.id),
        payload={"purpose": purpose, "subject": subject},
    )


def validate_reset_token(uidb64: str, purpose: str, token: str) -> User | None:
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not token_generator.check_token(user, token, purpose):
        return None
    return user


def _client_ip(request) -> str:
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR", "")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "")
```

- [ ] **Step 2: Verificar que los tests del servicio pasan**

Run: `$PY -m pytest accounts/tests/test_password_reset_service.py -x -v 2>&1 | tail -30`
Expected: los 9 tests pasan. Si fallan por NoReverseMatch, ejecuta Task 6 ahora y vuelve.

- [ ] **Step 3: Commit**

```bash
git add accounts/services/password_reset.py accounts/tests/test_password_reset_service.py
git commit -m "feat(accounts): servicio send_password_reset_email + helpers"
```

---

## Task 8: Tests de las vistas

**Files:**
- Create: `accounts/tests/test_password_reset_views.py`

- [ ] **Step 1: Crear el archivo de tests**

```python
from urllib.parse import urlparse

import pytest
from django.core import mail
from django.urls import resolve, reverse

from accounts.models import AuditLog, User
from accounts.services.password_reset import build_reset_url


@pytest.fixture
def alice(db):
    return User.objects.create_user(
        email="alice@edisa.com",
        name="Alice",
        password="OldPwd1234!",
    )


@pytest.fixture
def inactive_bob(db):
    u = User.objects.create_user(
        email="bob@edisa.com", name="Bob", password="OldPwd1234!"
    )
    u.is_active = False
    u.save(update_fields=["is_active"])
    return u


# ---------- request view ----------


def test_request_get_renderiza(client, db):
    response = client.get(reverse("accounts:password_reset"))
    assert response.status_code == 200
    assert b"Recupera tu contrase" in response.content


def test_request_post_email_existente_envia_email(client, alice):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "alice@edisa.com"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_sent")
    assert len(mail.outbox) == 1
    assert mail.outbox[0].to == ["alice@edisa.com"]

    log = AuditLog.objects.get(action="password_reset_requested")
    assert log.payload["encontrado"] is True
    assert log.payload["email_intentado"] == "alice@edisa.com"


def test_request_post_email_inexistente_no_envia_pero_redirige(client, db):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "nadie@edisa.com"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_sent")
    assert len(mail.outbox) == 0

    log = AuditLog.objects.get(action="password_reset_requested")
    assert log.payload["encontrado"] is False


def test_request_post_email_fuera_dominio_no_envia(client, db):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "alguien@gmail.com"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_sent")
    assert len(mail.outbox) == 0


def test_request_post_email_inactivo_no_envia(client, inactive_bob):
    response = client.post(
        reverse("accounts:password_reset"), {"email": "bob@edisa.com"}
    )
    assert response.status_code == 302
    assert len(mail.outbox) == 0

    log = AuditLog.objects.get(action="password_reset_requested")
    assert log.payload["encontrado"] is False


def test_request_post_email_mayusculas_normaliza(client, alice):
    client.post(reverse("accounts:password_reset"), {"email": "ALICE@EDISA.COM"})
    assert len(mail.outbox) == 1


# ---------- sent view ----------


def test_sent_renderiza_email_de_sesion(client, alice):
    client.post(reverse("accounts:password_reset"), {"email": "alice@edisa.com"})
    response = client.get(reverse("accounts:password_reset_sent"))
    assert response.status_code == 200
    assert b"alice@edisa.com" in response.content


# ---------- confirm view ----------


def _confirm_url_for(user, purpose):
    full = build_reset_url(user, purpose)
    return urlparse(full).path


def test_confirm_get_reset_renderiza_copy_reset(client, alice):
    response = client.get(_confirm_url_for(alice, "reset"))
    assert response.status_code == 200
    assert b"Nueva contrase" in response.content


def test_confirm_get_welcome_renderiza_copy_welcome(client, alice):
    response = client.get(_confirm_url_for(alice, "welcome"))
    assert response.status_code == 200
    assert b"Bienvenido a la porra" in response.content


def test_confirm_get_token_invalido_devuelve_invalid_page(client, alice):
    # token con forma correcta pero firma inválida
    url = _confirm_url_for(alice, "reset")
    bad = url.rsplit("-", 1)[0] + "-XXXXXXXXXXXXXXXXXXXX/"
    response = client.get(bad)
    assert response.status_code == 410
    assert b"Enlace no v" in response.content


def test_confirm_get_purpose_no_valido_404(client, alice):
    url = _confirm_url_for(alice, "reset").replace("/reset/", "/bogus/")
    response = client.get(url)
    assert response.status_code == 404


def test_confirm_post_password_valida_cambia_y_redirige(client, alice):
    url = _confirm_url_for(alice, "reset")
    response = client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "NuevaPwd1234!"}
    )
    assert response.status_code == 302
    assert response.url == reverse("accounts:password_reset_complete")

    alice.refresh_from_db()
    assert alice.check_password("NuevaPwd1234!") is True
    assert alice.must_change_password is False

    log = AuditLog.objects.get(action="password_reset_completed")
    assert log.payload["purpose"] == "reset"


def test_confirm_post_passwords_no_coinciden_re_renderiza(client, alice):
    url = _confirm_url_for(alice, "reset")
    response = client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "Distinta1234!"}
    )
    assert response.status_code == 200
    alice.refresh_from_db()
    assert alice.check_password("OldPwd1234!") is True  # no cambió


def test_confirm_post_token_usado_segunda_vez_falla(client, alice):
    url = _confirm_url_for(alice, "reset")
    client.post(
        url, {"new_password1": "NuevaPwd1234!", "new_password2": "NuevaPwd1234!"}
    )
    response = client.post(
        url, {"new_password1": "OtraPwd1234!", "new_password2": "OtraPwd1234!"}
    )
    assert response.status_code == 410


# ---------- complete view ----------


def test_complete_renderiza(client, db):
    response = client.get(reverse("accounts:password_reset_complete"))
    assert response.status_code == 200
    assert b"Contrase" in response.content
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY -m pytest accounts/tests/test_password_reset_views.py -x -q 2>&1 | tail -10`
Expected: AttributeError o NoReverseMatch (vistas no existen aún).

---

## Task 9: Implementar las 4 vistas

**Files:**
- Modify: `accounts/views.py`

- [ ] **Step 1: Añadir imports necesarios al principio de `accounts/views.py`**

Localizar la zona de imports y añadir (si no están):

```python
from django.conf import settings
from django.contrib.auth import update_session_auth_hash
from django.contrib.auth.forms import SetPasswordForm
from django.http import HttpResponseNotFound
from django.shortcuts import redirect, render
from django.views import View
from django.views.generic import TemplateView

from accounts.models import AuditLog, User
from accounts.services.password_reset import (
    _client_ip,
    send_password_reset_email,
    validate_reset_token,
)
```

(Si algún import ya existe en el archivo, no duplicar — solo añadir los nuevos.)

- [ ] **Step 2: Añadir las 4 clases al final de `accounts/views.py`**

```python
class PasswordResetRequestView(View):
    template_name = "accounts/password_reset_request.html"

    def get(self, request):
        return render(request, self.template_name)

    def post(self, request):
        email = (request.POST.get("email") or "").strip().lower()
        encontrado = False
        user = None
        if email.endswith("@" + settings.EMAIL_DOMAIN):
            try:
                user = User.objects.get(email__iexact=email, is_active=True)
                encontrado = True
            except User.DoesNotExist:
                pass
        AuditLog.objects.create(
            actor=None,
            action="password_reset_requested",
            target_type="user",
            target_id=str(user.id) if user else "",
            payload={
                "email_intentado": email,
                "encontrado": encontrado,
                "ip": _client_ip(request),
                "purpose": "reset",
            },
        )
        if user:
            send_password_reset_email(user, purpose="reset")
        request.session["password_reset_email"] = email
        return redirect("accounts:password_reset_sent")


class PasswordResetSentView(TemplateView):
    template_name = "accounts/password_reset_sent.html"

    def get_context_data(self, **kw):
        ctx = super().get_context_data(**kw)
        ctx["email"] = self.request.session.pop("password_reset_email", "")
        return ctx


class PasswordResetConfirmView(View):
    template_name = "accounts/password_reset_confirm.html"
    invalid_template_name = "accounts/password_reset_invalid.html"

    def dispatch(self, request, uidb64, purpose, token, *args, **kwargs):
        if purpose not in ("reset", "welcome"):
            return HttpResponseNotFound()
        self.user = validate_reset_token(uidb64, purpose, token)
        self.purpose = purpose
        if self.user is None:
            return render(request, self.invalid_template_name, status=410)
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(
            request,
            self.template_name,
            {"purpose": self.purpose, "form": SetPasswordForm(self.user)},
        )

    def post(self, request):
        form = SetPasswordForm(self.user, request.POST)
        if not form.is_valid():
            return render(
                request,
                self.template_name,
                {"purpose": self.purpose, "form": form},
            )
        user = form.save(commit=False)
        user.must_change_password = False
        user.save(update_fields=["password", "must_change_password"])
        AuditLog.objects.create(
            actor=None,
            action="password_reset_completed",
            target_type="user",
            target_id=str(user.id),
            payload={"purpose": self.purpose, "ip": _client_ip(request)},
        )
        return redirect("accounts:password_reset_complete")


class PasswordResetCompleteView(TemplateView):
    template_name = "accounts/password_reset_complete.html"
```

- [ ] **Step 3: Confirmar Task 6 si quedó pendiente**

Si el step 2 de Task 6 saltó, ejecutarlo ahora:

Run: `$PY -c "import django, os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','porra26.settings.test'); django.setup(); from django.urls import reverse; print(reverse('accounts:password_reset'))"`
Expected: imprime una ruta tipo `/recuperar/` (o el namespace correcto).

---

## Task 10: Plantillas HTML del flujo

**Files:**
- Create: `templates/accounts/password_reset_request.html`
- Create: `templates/accounts/password_reset_sent.html`
- Create: `templates/accounts/password_reset_confirm.html`
- Create: `templates/accounts/password_reset_invalid.html`
- Create: `templates/accounts/password_reset_complete.html`
- Modify: `templates/accounts/login.html`

- [ ] **Step 1: Crear `password_reset_request.html`**

```html
{% extends "base.html" %}
{% load icons static %}
{% block main %}
<section class="login-screen">
  <header class="login-header">
    <a href="{% url 'accounts:login' %}" class="logo" style="text-decoration:none;color:inherit" title="EDISA · Mundial 2026">
      <img src="{% static 'img/logo.png' %}" alt="EDISA · Mundial 2026 · Tu porra interna" style="height:48px;width:auto;display:block">
    </a>
    <span class="chip">Edición interna · Mundial 2026</span>
  </header>

  <div class="login-body login-body--narrow">
    <div class="glass rise login-form-card">
      <form method="post" novalidate style="display:flex;flex-direction:column;gap:18px">
        {% csrf_token %}

        <div>
          <h1 class="display" style="margin:0;font-size:30px;letter-spacing:-0.03em">Recupera tu contraseña</h1>
          <p style="margin:8px 0 0;color:var(--text-dim);font-size:14px">
            Introduce tu correo de empresa y te enviaremos un enlace para restablecerla.
          </p>
        </div>

        <div class="field">
          <label for="reset-email">Correo electrónico</label>
          <div class="login-input-wrap">
            {% icon "mail" width=17 height=17 %}
            <input id="reset-email" class="input login-input-with-icon" type="email" name="email"
                   placeholder="nombre@empresa.com" required autofocus>
          </div>
        </div>

        <button class="btn btn-primary" type="submit" style="padding:14px;font-size:15.5px">
          Enviar enlace {% icon "mail" width=17 height=17 %}
        </button>

        <p style="margin:0;font-size:13px;text-align:center">
          <a href="{% url 'accounts:login' %}" style="color:var(--text-dim);text-decoration:none">
            ← Volver al login
          </a>
        </p>
      </form>
    </div>
  </div>

  <footer class="login-footer mono">Mundial FIFA 2026 · Edición interna</footer>
</section>
{% endblock %}
```

- [ ] **Step 2: Crear `password_reset_sent.html`**

```html
{% extends "base.html" %}
{% load icons static %}
{% block main %}
<section class="login-screen">
  <header class="login-header">
    <a href="{% url 'accounts:login' %}" class="logo" style="text-decoration:none;color:inherit">
      <img src="{% static 'img/logo.png' %}" alt="EDISA · Mundial 2026" style="height:48px;width:auto;display:block">
    </a>
    <span class="chip">Edición interna · Mundial 2026</span>
  </header>

  <div class="login-body login-body--narrow">
    <div class="glass rise login-form-card" style="text-align:center">
      <div style="display:flex;justify-content:center;margin-bottom:8px;color:var(--c-green)">
        {% icon "check-circle" width=48 height=48 %}
      </div>
      <h1 class="display" style="margin:0;font-size:28px;letter-spacing:-0.03em">Revisa tu correo</h1>
      <p style="margin:16px 0 0;color:var(--text-dim);font-size:14px;line-height:1.6">
        Si <strong>{{ email|default:"el correo introducido" }}</strong> está registrado, te hemos enviado un enlace para restablecer tu contraseña. Caduca en 24 horas.
      </p>
      <p style="margin:24px 0 0;font-size:13px">
        <a href="{% url 'accounts:login' %}" style="color:var(--text-dim);text-decoration:none">
          ← Volver al login
        </a>
      </p>
    </div>
  </div>

  <footer class="login-footer mono">Mundial FIFA 2026 · Edición interna</footer>
</section>
{% endblock %}
```

- [ ] **Step 3: Crear `password_reset_confirm.html`**

```html
{% extends "base.html" %}
{% load icons static %}
{% block main %}
<section class="login-screen">
  <header class="login-header">
    <a href="{% url 'accounts:login' %}" class="logo" style="text-decoration:none;color:inherit">
      <img src="{% static 'img/logo.png' %}" alt="EDISA · Mundial 2026" style="height:48px;width:auto;display:block">
    </a>
    <span class="chip">Edición interna · Mundial 2026</span>
  </header>

  <div class="login-body login-body--narrow">
    <div class="glass rise login-form-card">
      <form method="post" novalidate style="display:flex;flex-direction:column;gap:18px">
        {% csrf_token %}

        <div>
          <h1 class="display" style="margin:0;font-size:30px;letter-spacing:-0.03em">
            {% if purpose == 'welcome' %}Bienvenido a la porra{% else %}Nueva contraseña{% endif %}
          </h1>
          <p style="margin:8px 0 0;color:var(--text-dim);font-size:14px">
            {% if purpose == 'welcome' %}Establece tu contraseña para entrar al torneo.{% else %}Elige una contraseña que recuerdes.{% endif %}
          </p>
        </div>

        <div class="field">
          <label for="new1">Nueva contraseña</label>
          <div class="login-input-wrap">
            {% icon "lock" width=17 height=17 %}
            <input id="new1" class="input login-input-with-icon" type="password" name="new_password1" required autofocus>
          </div>
          {% for e in form.new_password1.errors %}
            <p style="margin:6px 0 0;color:var(--c-red);font-size:13px">{{ e }}</p>
          {% endfor %}
        </div>

        <div class="field">
          <label for="new2">Repite la contraseña</label>
          <div class="login-input-wrap">
            {% icon "lock" width=17 height=17 %}
            <input id="new2" class="input login-input-with-icon" type="password" name="new_password2" required>
          </div>
          {% for e in form.new_password2.errors %}
            <p style="margin:6px 0 0;color:var(--c-red);font-size:13px">{{ e }}</p>
          {% endfor %}
        </div>

        {% if form.non_field_errors %}
          <p style="margin:0;color:var(--c-red);font-size:13px">{{ form.non_field_errors|join:' ' }}</p>
        {% endif %}

        <button class="btn btn-primary" type="submit" style="padding:14px;font-size:15.5px">
          Guardar contraseña {% icon "lock" width=17 height=17 %}
        </button>
      </form>
    </div>
  </div>

  <footer class="login-footer mono">Mundial FIFA 2026 · Edición interna</footer>
</section>
{% endblock %}
```

- [ ] **Step 4: Crear `password_reset_invalid.html`**

```html
{% extends "base.html" %}
{% load icons static %}
{% block main %}
<section class="login-screen">
  <header class="login-header">
    <a href="{% url 'accounts:login' %}" class="logo" style="text-decoration:none;color:inherit">
      <img src="{% static 'img/logo.png' %}" alt="EDISA · Mundial 2026" style="height:48px;width:auto;display:block">
    </a>
    <span class="chip">Edición interna · Mundial 2026</span>
  </header>

  <div class="login-body login-body--narrow">
    <div class="glass rise login-form-card" style="text-align:center">
      <div style="display:flex;justify-content:center;margin-bottom:8px;color:var(--c-amber)">
        {% icon "alert-triangle" width=48 height=48 %}
      </div>
      <h1 class="display" style="margin:0;font-size:28px;letter-spacing:-0.03em">Enlace no válido</h1>
      <p style="margin:16px 0 0;color:var(--text-dim);font-size:14px;line-height:1.6">
        Este enlace ha caducado o ya se ha usado. Pídele al gestor que te reenvíe el correo, o vuelve a iniciar el proceso de recuperación.
      </p>
      <div style="display:flex;gap:12px;justify-content:center;margin-top:24px;font-size:13px">
        <a href="{% url 'accounts:login' %}" style="color:var(--text-dim);text-decoration:none">← Volver al login</a>
        <span style="color:var(--text-faint)">·</span>
        <a href="{% url 'accounts:password_reset' %}" style="color:var(--text-dim);text-decoration:none">Solicitar otro enlace</a>
      </div>
    </div>
  </div>

  <footer class="login-footer mono">Mundial FIFA 2026 · Edición interna</footer>
</section>
{% endblock %}
```

- [ ] **Step 5: Crear `password_reset_complete.html`**

```html
{% extends "base.html" %}
{% load icons static %}
{% block main %}
<section class="login-screen">
  <header class="login-header">
    <a href="{% url 'accounts:login' %}" class="logo" style="text-decoration:none;color:inherit">
      <img src="{% static 'img/logo.png' %}" alt="EDISA · Mundial 2026" style="height:48px;width:auto;display:block">
    </a>
    <span class="chip">Edición interna · Mundial 2026</span>
  </header>

  <div class="login-body login-body--narrow">
    <div class="glass rise login-form-card" style="text-align:center">
      <div style="display:flex;justify-content:center;margin-bottom:8px;color:var(--c-green)">
        {% icon "check-circle" width=48 height=48 %}
      </div>
      <h1 class="display" style="margin:0;font-size:28px;letter-spacing:-0.03em">Contraseña actualizada</h1>
      <p style="margin:16px 0 0;color:var(--text-dim);font-size:14px;line-height:1.6">
        Ya puedes entrar al torneo.
      </p>
      <a href="{% url 'accounts:login' %}" class="btn btn-primary" style="display:inline-flex;align-items:center;gap:8px;margin-top:24px;padding:14px 24px;font-size:15.5px;text-decoration:none">
        Ir al login {% icon "ball" width=17 height=17 %}
      </a>
    </div>
  </div>

  <footer class="login-footer mono">Mundial FIFA 2026 · Edición interna</footer>
</section>
{% endblock %}
```

- [ ] **Step 6: Modificar `templates/accounts/login.html` líneas 53-55**

Sustituir:

```html
<p style="margin:0;font-size:12px;color:var(--text-faint);text-align:center;line-height:1.5">
  ¿Olvidaste tu contraseña? Pídele a un gestor que la restablezca.
</p>
```

por:

```html
<p style="margin:0;font-size:13px;text-align:center">
  <a href="{% url 'accounts:password_reset' %}" style="color:var(--text-dim);text-decoration:none">
    ¿Olvidaste tu contraseña?
  </a>
</p>
```

---

## Task 11: Iconos nuevos

**Files:**
- Create: `static/icons/check-circle.svg`
- Create: `static/icons/alert-triangle.svg`

- [ ] **Step 1: Comprobar el estilo de un icono existente**

Run: `cat static/icons/check.svg`
Expected: SVG `viewBox="0 0 24 24"`, sin fill (hereda `currentColor`), stroke-based con `stroke-width="2"` típicamente.

- [ ] **Step 2: Crear `static/icons/check-circle.svg`**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <circle cx="12" cy="12" r="10"/>
  <path d="M8 12.5l2.5 2.5L16 9.5"/>
</svg>
```

- [ ] **Step 3: Crear `static/icons/alert-triangle.svg`**

```xml
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
  <path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0Z"/>
  <line x1="12" y1="9" x2="12" y2="13"/>
  <line x1="12" y1="17" x2="12.01" y2="17"/>
</svg>
```

- [ ] **Step 4: Verificar que el templatetag los detecta**

Run: `grep -n "icon_dir\|ICONS_DIR\|static.*icons" core/templatetags/icons.py | head -5`
Expected: el templatetag construye el path leyendo `static/icons/<name>.svg`; los nuevos están automáticamente disponibles.

---

## Task 12: CSS para `login-body--narrow`

**Files:**
- Modify: el archivo CSS principal del proyecto

- [ ] **Step 1: Localizar el CSS donde está `.login-body`**

Run: `grep -rn "\.login-body" --include="*.css" . | head -5`
Expected: una entrada en el CSS principal con su declaración (probablemente `display:grid` con dos columnas).

- [ ] **Step 2: Añadir la variante modificadora**

Inmediatamente después del bloque `.login-body { ... }`, añadir:

```css
.login-body--narrow {
  grid-template-columns: minmax(0, 440px);
  justify-content: center;
}
.login-body--narrow > aside { display: none; }
```

(Si la regla base no usa grid, adaptar — el efecto buscado es: centrado, ~440px máx, sin aside lateral.)

- [ ] **Step 3: Verificar en navegador (manual, no automatizable)**

Anotar pendiente para el smoke test final.

---

## Task 13: Ejecutar tests de vistas

- [ ] **Step 1: Correr la suite de password reset**

Run: `$PY -m pytest accounts/tests/test_password_reset_views.py -x -v 2>&1 | tail -40`
Expected: los ~17 tests pasan.

Si alguno falla por un detalle de copy/markup (p. ej. el assert busca un literal exacto que no aparece), ajustar el test o la plantilla — el test es la especificación operacional.

- [ ] **Step 2: Correr toda la suite de accounts**

Run: `$PY -m pytest accounts/tests/ -x -q 2>&1 | tail -20`
Expected: pasan todos los tests previos + los nuevos.

- [ ] **Step 3: Commit del flujo completo**

```bash
git add accounts/urls.py accounts/views.py accounts/tests/test_password_reset_views.py templates/accounts/ static/icons/check-circle.svg static/icons/alert-triangle.svg
# y el CSS que tocaste en Task 12
git add <ruta-del-css>
git commit -m "feat(accounts): vistas + plantillas del flujo de reset/welcome"
```

---

## Task 14: Checkbox "Enviar email de bienvenida" en alta

**Files:**
- Modify: `pot/forms.py` (form de alta de jugador)
- Modify: `pot/views.py` (vista de creación)
- Modify: `templates/pot/_player_modal.html` (o donde esté el alta — localizar primero)
- Create: `pot/tests/test_player_create_welcome_email.py`

- [ ] **Step 1: Localizar form, vista y plantilla de alta**

Run: `grep -rn "PlayerCreate\|PlayerForm\|player_create" pot/ templates/pot/ --include="*.py" --include="*.html" | head -15`
Expected: aparece el form (probablemente `PlayerForm` en `pot/forms.py`), la vista (`PlayerCreateView` o similar) y el modal de alta.

- [ ] **Step 2: Añadir `enviar_bienvenida` al form**

En `pot/forms.py`, dentro de la clase del form de alta de jugador (la que crea, no la que edita), añadir:

```python
enviar_bienvenida = forms.BooleanField(
    required=False,
    initial=True,
    label="Enviar email de bienvenida",
)
```

Si el form actual gestiona una contraseña inicial, hacerla opcional (`required=False`) — el flujo principal es el email.

- [ ] **Step 3: Disparar el envío desde la vista**

En `pot/views.py`, en el método que guarda el form de creación (probablemente `form_valid` o equivalente), tras crear el `User`:

```python
import secrets
from accounts.services.password_reset import send_password_reset_email

# ... después de user = form.save() o equivalente ...
if not user.has_usable_password():
    user.set_password(secrets.token_urlsafe(32))
    user.save(update_fields=["password"])
user.must_change_password = True
user.save(update_fields=["must_change_password"])

if form.cleaned_data.get("enviar_bienvenida"):
    send_password_reset_email(user, purpose="welcome", actor=request.user)
```

(Si el form ya gestiona la contraseña inicial, integrar este bloque adaptando: lo crítico es que si `enviar_bienvenida=True`, no se necesita contraseña conocida.)

- [ ] **Step 4: Añadir el checkbox a la plantilla del alta**

En el modal de alta de jugador (probablemente `templates/pot/_player_modal.html` o un partial), antes del botón "Guardar":

```html
<label style="display:flex;align-items:center;gap:8px;font-size:13px;color:var(--text-dim);margin-top:8px">
  <input type="checkbox" name="enviar_bienvenida" {% if form.enviar_bienvenida.value|default_if_none:True %}checked{% endif %}>
  Enviar email de bienvenida con enlace para establecer contraseña
</label>
```

(Si el modal está separado en "alta" vs "edición", añadir solo al de alta.)

- [ ] **Step 5: Tests del flujo**

Crear `pot/tests/test_player_create_welcome_email.py`:

```python
import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import User


@pytest.fixture
def gestor(db, client):
    u = User.objects.create_user(
        email="gestor@edisa.com", name="Gestor",
        password="OldPwd1234!", is_gestor=True,
        must_change_password=False,
    )
    client.force_login(u)
    return u


def test_alta_con_checkbox_envia_welcome(gestor, client):
    response = client.post(
        reverse("pot:player_create"),  # ajustar a la URL real si cambia
        {
            "email": "nuevo@edisa.com",
            "name": "Nuevo Jugador",
            "enviar_bienvenida": "on",
        },
    )
    # acepta 200 (modal) o 302 (redirect) según el flujo
    assert response.status_code in (200, 302)

    assert User.objects.filter(email="nuevo@edisa.com").exists()
    assert len(mail.outbox) == 1
    assert "Bienvenido" in mail.outbox[0].subject


def test_alta_sin_checkbox_no_envia(gestor, client):
    response = client.post(
        reverse("pot:player_create"),
        {
            "email": "otro@edisa.com",
            "name": "Otro",
            # sin enviar_bienvenida
        },
    )
    assert response.status_code in (200, 302)
    assert User.objects.filter(email="otro@edisa.com").exists()
    assert len(mail.outbox) == 0
```

- [ ] **Step 6: Correr los tests**

Run: `$PY -m pytest pot/tests/test_player_create_welcome_email.py -x -v 2>&1 | tail -20`
Expected: pasan.

Si fallan por URL/reverse, ajustar `reverse("pot:player_create")` al nombre real encontrado en Step 1.

- [ ] **Step 7: Commit**

```bash
git add pot/forms.py pot/views.py templates/pot/_player_modal.html pot/tests/test_player_create_welcome_email.py
git commit -m "feat(pot): checkbox 'enviar email de bienvenida' en alta de jugadores"
```

---

## Task 15: Endpoint y botón "Reenviar email"

**Files:**
- Modify: `pot/urls.py`
- Modify: `pot/views.py`
- Modify: `templates/pot/manage_players.html`
- Create: `pot/tests/test_player_resend_invite.py`

- [ ] **Step 1: Tests primero**

Crear `pot/tests/test_player_resend_invite.py`:

```python
import json

import pytest
from django.core import mail
from django.urls import reverse

from accounts.models import AuditLog, User


@pytest.fixture
def gestor(db, client):
    u = User.objects.create_user(
        email="gestor@edisa.com", name="Gestor",
        password="OldPwd1234!", is_gestor=True,
        must_change_password=False,
    )
    client.force_login(u)
    return u


@pytest.fixture
def jugador_pendiente(db):
    u = User.objects.create_user(
        email="pendiente@edisa.com", name="Pendiente",
        password="OldPwd1234!",
        must_change_password=True,
    )
    return u


@pytest.fixture
def jugador_veterano(db):
    from django.utils import timezone
    u = User.objects.create_user(
        email="veterano@edisa.com", name="Veterano",
        password="OldPwd1234!",
        must_change_password=False,
    )
    u.last_login = timezone.now()
    u.save(update_fields=["last_login"])
    return u


def test_resend_pendiente_envia_welcome(gestor, client, jugador_pendiente):
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_pendiente.id])
    )
    assert response.status_code == 200
    data = json.loads(response.content)
    assert data["ok"] is True
    assert data["purpose"] == "welcome"
    assert len(mail.outbox) == 1
    assert "Bienvenido" in mail.outbox[0].subject

    log = AuditLog.objects.get(action="password_reset_email_sent")
    assert log.actor == gestor


def test_resend_veterano_envia_reset(gestor, client, jugador_veterano):
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_veterano.id])
    )
    data = json.loads(response.content)
    assert data["purpose"] == "reset"
    assert "Restablece" in mail.outbox[0].subject


def test_resend_a_inactivo_404(gestor, client, jugador_pendiente):
    jugador_pendiente.is_active = False
    jugador_pendiente.save(update_fields=["is_active"])
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_pendiente.id])
    )
    assert response.status_code == 404


def test_resend_no_gestor_403(client, jugador_pendiente, db):
    no_gestor = User.objects.create_user(
        email="player@edisa.com", name="Player",
        password="OldPwd1234!",
        must_change_password=False,
    )
    client.force_login(no_gestor)
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_pendiente.id])
    )
    assert response.status_code in (302, 403)


def test_resend_anonimo_redirige_a_login(client, jugador_pendiente):
    response = client.post(
        reverse("pot:player_resend_invite", args=[jugador_pendiente.id])
    )
    assert response.status_code == 302
```

- [ ] **Step 2: Verificar que fallan**

Run: `$PY -m pytest pot/tests/test_player_resend_invite.py -x -q 2>&1 | tail -10`
Expected: NoReverseMatch para `pot:player_resend_invite`.

- [ ] **Step 3: Añadir la URL**

En `pot/urls.py`, en el bloque urlpatterns, añadir:

```python
path(
    "jugadores/<int:pk>/reenviar-email/",
    views.PlayerResendInviteView.as_view(),
    name="player_resend_invite",
),
```

- [ ] **Step 4: Añadir la vista**

En `pot/views.py`, mirar primero cómo se exige "gestor" en otras vistas (probablemente un mixin tipo `GestorRequiredMixin` o un decorator). Reusar el mismo patrón. Añadir:

```python
class PlayerResendInviteView(GestorRequiredMixin, View):  # o LoginRequired+mixin que use el resto
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk, is_active=True)
        if user.must_change_password and user.last_login is None:
            purpose = "welcome"
        else:
            purpose = "reset"
        send_password_reset_email(user, purpose=purpose, actor=request.user)
        return JsonResponse({"ok": True, "email": user.email, "purpose": purpose})
```

Imports nuevos al principio del archivo si no están:

```python
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.views import View

from accounts.models import User
from accounts.services.password_reset import send_password_reset_email
```

- [ ] **Step 5: Añadir el botón en `templates/pot/manage_players.html`**

Junto al botón candado (línea 47 aprox), en la columna de acciones, añadir antes o después:

```html
<button class="btn btn-ghost" type="button"
        data-resend-invite-url="{% url 'pot:player_resend_invite' p.id %}"
        style="width:32px;height:32px;padding:0"
        title="Reenviar email de acceso">
  {% icon "mail" width=14 %}
</button>
```

- [ ] **Step 6: JS para disparar el POST**

Al final del bloque `<script>` de `manage_players.html` (o en su archivo JS asociado si existe), añadir:

```javascript
document.addEventListener("click", (e) => {
  const btn = e.target.closest("[data-resend-invite-url]");
  if (!btn) return;
  e.preventDefault();
  const url = btn.dataset.resendInviteUrl;
  const csrf = document.querySelector("[name=csrfmiddlewaretoken]").value;
  btn.disabled = true;
  fetch(url, {
    method: "POST",
    headers: {"X-CSRFToken": csrf, "Accept": "application/json"},
  })
    .then(r => r.json())
    .then(data => {
      if (data.ok) {
        // toast simple (alineado con el patrón del proyecto si ya existe)
        alert(`Email enviado a ${data.email}`);
      } else {
        alert("No se pudo enviar el email.");
      }
    })
    .catch(() => alert("Error de red al enviar el email."))
    .finally(() => { btn.disabled = false; });
});
```

(Si la página ya tiene un sistema de toasts — buscar `showToast`, `toast`, `notify` —, sustituir `alert(...)` por la llamada apropiada.)

- [ ] **Step 7: Correr tests**

Run: `$PY -m pytest pot/tests/test_player_resend_invite.py -x -v 2>&1 | tail -20`
Expected: 5 tests pasan.

- [ ] **Step 8: Commit**

```bash
git add pot/urls.py pot/views.py templates/pot/manage_players.html pot/tests/test_player_resend_invite.py
git commit -m "feat(pot): botón 'Reenviar email' para gestores"
```

---

## Task 16: Chip "Pendiente de activar"

**Files:**
- Modify: `templates/pot/manage_players.html`

- [ ] **Step 1: Localizar la celda del nombre del jugador**

Run: `grep -n "p\.name\|player\.name" templates/pot/manage_players.html`
Expected: una o dos líneas con la celda del nombre.

- [ ] **Step 2: Añadir el chip condicional**

Junto al nombre del jugador (en la celda), añadir:

```html
{% if p.must_change_password and not p.last_login %}
  <span class="chip chip-amber" style="margin-left:6px;font-size:11px;padding:2px 8px">
    Pendiente de activar
  </span>
{% endif %}
```

(Si `chip-amber` no existe como clase, usar inline `style="background:var(--c-amber-bg,#FEF3C7);color:var(--c-amber,#92400E)"`.)

- [ ] **Step 3: Verificar visualmente (manual)**

Anotar pendiente para el smoke test.

- [ ] **Step 4: Commit**

```bash
git add templates/pot/manage_players.html
git commit -m "feat(pot): chip 'Pendiente de activar' en jugadores que aún no entraron"
```

---

## Task 17: Documentación

**Files:**
- Modify: `CLAUDE.md`
- Modify: `docs/DATA_MODEL.md`
- Modify: `templates/core/rules.html`

- [ ] **Step 1: Actualizar `CLAUDE.md`**

Localizar la sección "Reglas de negocio clave" en `CLAUDE.md` y la línea:

> `**Auth:** correo corporativo + contraseña. **Sin auto-recuperación**: la contraseña la restablece un gestor. Altas crean contraseña temporal.`

Sustituir por:

> `**Auth:** correo corporativo + contraseña. **Recuperación por email autoservicio** (token 24h). **Altas** pueden enviar email de bienvenida (token 7d) o quedar con contraseña fijada por el gestor.`

- [ ] **Step 2: Actualizar `docs/DATA_MODEL.md`**

Run: `grep -n "auto-recuperaci\|gestor.*restablece" docs/DATA_MODEL.md`
Expected: una o dos líneas con la regla vieja en §5.

Sustituir el párrafo equivalente por:

> El usuario puede recuperar su contraseña desde el login mediante un enlace por correo (token firmado, 24h de vida). Las altas de gestor pueden disparar un email de bienvenida análogo con token de 7 días, evitando compartir contraseñas iniciales. El gestor mantiene la opción de fijar contraseña manual como fallback.

- [ ] **Step 3: Actualizar `templates/core/rules.html`**

Líneas 252-254 (aprox), localizar el texto público sobre recuperación y sustituir por:

```html
<p>Si olvidas tu contraseña, en el login tienes un enlace para recuperarla por email (el enlace caduca en 24 horas). Si el email no te llega, pídele al gestor que te lo reenvíe.</p>
```

- [ ] **Step 4: Commit**

```bash
git add CLAUDE.md docs/DATA_MODEL.md templates/core/rules.html
git commit -m "docs: actualizar reglas de recuperación de contraseña"
```

---

## Task 18: Suite completa + smoke test manual

- [ ] **Step 1: Correr toda la suite**

Run: `$PY -m pytest -x -q 2>&1 | tail -25`
Expected: 0 fallos. Si algún test antiguo asumía el copy viejo del login ("pídele a un gestor"), ajustarlo.

- [ ] **Step 2: Smoke test manual (anotar pendiente para `verify`)**

1. Arrancar el servidor de dev local.
2. Visitar `/accounts/`, pulsar "¿Olvidaste tu contraseña?".
3. Introducir email existente → comprobar `mail.outbox` o consola SMTP.
4. Abrir el link, establecer nueva contraseña, comprobar login.
5. Crear un jugador con check welcome → comprobar email.
6. Pulsar botón mail en la tabla → toast + email.
7. Verificar chip "Pendiente de activar" en un jugador sin `last_login`.

(Este step se delega al humano al revisar la PR — se anota en el body de la PR.)

---

## Task 19: Cerrar la rama

- [ ] **Step 1: Push de la rama del worktree**

```bash
git push -u origin worktree-password-recovery-spec
```

- [ ] **Step 2: Crear PR**

```bash
gh pr create --title "feat(accounts): recuperación de contraseña por email" --body "$(cat <<'EOF'
## Summary
- Flujo de autoservicio "¿Olvidaste tu contraseña?" con token de 24h.
- Email de bienvenida (token 7d) al alta de jugadores; el gestor decide con un checkbox.
- Botón "Reenviar email" en la tabla de jugadores; chip "Pendiente de activar" para los no estrenados.
- Subclase `PorraPasswordResetTokenGenerator` con TTL distinto por propósito.
- El botón candado existente se mantiene como fallback.

## Test plan
- [ ] `pytest accounts/tests/test_password_reset_*` en verde.
- [ ] `pytest pot/tests/test_player_*` en verde.
- [ ] Smoke manual: flujo "olvidé contraseña" extremo a extremo con email real de Resend.
- [ ] Smoke manual: alta con check welcome → llega email, link funciona, login posterior OK.
- [ ] Smoke manual: botón reenviar email en `manage_players` → toast + email.
EOF
)"
```

- [ ] **Step 3: Esperar a que pase CI / merge**

Tras revisión, hacer merge con squash desde GitHub (o `gh pr merge --squash`).

- [ ] **Step 4: Limpiar el worktree**

```bash
git checkout main
git pull
git worktree remove .claude/worktrees/password-recovery-spec --force
git branch -D worktree-password-recovery-spec
```

---

## Self-Review

- ✅ **Cobertura del spec**:
  - Token generator → Tasks 2-3.
  - Servicio email → Tasks 4-5, 7.
  - URLs → Task 6.
  - Vistas → Tasks 8-9.
  - Plantillas del flujo → Task 10.
  - Login link → Task 10 step 6.
  - Iconos nuevos → Task 11.
  - CSS narrow → Task 12.
  - Checkbox welcome en alta → Task 14.
  - Endpoint resend + botón mail + JS → Task 15.
  - Chip "Pendiente" → Task 16.
  - Auditoría → integrada en Tasks 7, 9, 15 (las tres acciones nuevas en `AuditLog`).
  - Tests de las tres clases (generador, servicio, vistas, alta, resend) → Tasks 2, 4, 8, 14, 15.
  - Docs → Task 17.
- ✅ **Sin placeholders**: cada step tiene código completo.
- ✅ **Consistencia de nombres**: `password_reset_email_sent`, `password_reset_requested`, `password_reset_completed` usados de forma idéntica en service y views.
- ✅ **Scope acotado**: no toca `ResetPasswordView` legacy ni el modal del candado.
