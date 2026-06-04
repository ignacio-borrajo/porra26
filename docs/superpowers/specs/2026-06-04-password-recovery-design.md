# Diseño — Recuperación de contraseña por email y alta autoservicio

Fecha: 2026-06-04
Autor: brainstorming con Ignacio

## Objetivo

Que cualquier jugador pueda recuperar su contraseña sin depender del gestor, y que las altas nuevas se completen mediante un email de bienvenida (sin compartir contraseñas temporales). El gestor mantiene su botón candado como fallback.

Esto desbloquea dos cosas:

- Quita carga al gestor (resets manuales constantes).
- Permite onboarding limpio: el gestor introduce nombre + email + check "Enviar email de bienvenida" y el usuario establece su propia contraseña al primer acceso.

## Contexto actual

- `accounts/views.py`: solo hay `LoginView`, `LogoutView`, `ChangePasswordView` (auto-cambio con `current` obligatorio) y `MyAccountView`. No existe flujo de reset.
- `accounts/models.py:49`: `must_change_password = models.BooleanField(default=True)`. El middleware `accounts/middleware.py:12` redirige cualquier request autenticado con este flag a `accounts:change_password`.
- `accounts/managers.py:7-21`: `create_user` setea contraseña vía `set_password` y el callsite decide qué pasar (hoy típicamente una temporal o `"1234"` en `seed_players.py`).
- `templates/accounts/login.html:53-55`: párrafo placeholder *"¿Olvidaste tu contraseña? Pídele a un gestor que la restablezca."* — se sustituye por link al flujo nuevo.
- `templates/pot/manage_players.html:47` y `templates/pot/_password_set_modal.html`: existe el botón candado del gestor (`pot:player_set_password`) para fijar contraseña a mano. Se mantiene como fallback; este diseño no lo toca.
- `competition/services/reminder_email.py`: patrón ya establecido para emails (`EmailMultiAlternatives` con texto plano + HTML inline, `SITE_URL = "https://laporradeljefe.es"`, registro en `AuditLog`).
- SMTP saliente vía Resend con dominio propio verificado (`DEFAULT_FROM_EMAIL=PORRA 26 <bot@laporradeljefe.es>`). Sin coste extra para el volumen esperado de resets.
- `AUTH_PASSWORD_VALIDATORS` activos en `porra26/settings/base.py` (ya validan longitud, similitud y common-passwords).
- `EMAIL_DOMAIN` en settings (`edisa.com`): los usuarios solo se crean con emails de ese dominio. Lo usaremos también para descartar emails fuera de dominio sin tener que tocar `User`.
- `docs/DATA_MODEL.md` §5 y `templates/core/rules.html:252-254` documentan hoy *"Sin recuperación automática"*. Hay que actualizarlos también.
- `CLAUDE.md` "Reglas de negocio clave" dice *"Sin auto-recuperación: la contraseña la restablece un gestor"*. Hay que reescribir esa línea.

## Alcance

Dentro:

- Subclase de `PasswordResetTokenGenerator` que codifica `purpose` (`reset` | `welcome`) en el material firmado y aplica TTL distinto por propósito (24h / 7d).
- Vistas + URLs + plantillas del flujo de reset (request, sent, confirm, complete).
- Servicio `accounts/services/password_reset.py` con `send_password_reset_email(user, purpose)`, `build_reset_url(user, purpose)`, `validate_reset_token(uidb64, purpose, token)`.
- Plantilla de email (HTML inline + texto plano) reutilizable para los dos `purpose`.
- Checkbox "Enviar email de bienvenida" en el alta de jugadores (preseleccionado).
- Botón "Reenviar email" en la tabla de jugadores (icono `mail`).
- Chip ámbar "Pendiente de activar" en la fila de un jugador que aún no haya entrado.
- Sustituir el copy del login por link al flujo de reset.
- Tres eventos nuevos en `AuditLog`.
- Tests de vistas, generador de tokens y endpoint de reenvío.
- Actualizar `docs/DATA_MODEL.md`, `templates/core/rules.html` y `CLAUDE.md` para reflejar que ahora sí hay auto-recuperación.

Fuera:

- Eliminar el botón candado ni el modal `_password_set_modal.html`. Se quedan como fallback.
- Tocar el flujo de `ChangePasswordView` (auto-cambio con `current`).
- Pre-rellenar email en el formulario de reset si el usuario está logueado (no aplica: el flujo arranca desde login).
- Rate limiting del endpoint de reset (volumen ~50 usuarios; no merece la pena).
- Soportar emails fuera del dominio corporativo (intencionado: silenciar como "email no encontrado").
- Localización: el sistema es solo en español.

## Flujos

### Flujo "olvidé contraseña" (autoservicio)

1. Usuario en login pulsa link "¿Olvidaste tu contraseña?" (sustituye `templates/accounts/login.html:53-55`).
2. `accounts/recuperar/` GET → `password_reset_request.html` con un input email.
3. POST a `accounts/recuperar/`:
   - Normaliza el email a minúsculas.
   - Si pertenece a `EMAIL_DOMAIN` **y** existe un `User` con ese email **y** `is_active=True` → llama a `send_password_reset_email(user, purpose="reset")`. Crea `AuditLog("password_reset_requested", encontrado=True)`.
   - En cualquier otro caso → no envía email, pero crea `AuditLog("password_reset_requested", encontrado=False, email_intentado=...)`.
   - En ambos casos redirige a `accounts/recuperar/enviado/` con el email tecleado en sesión.
4. `password_reset_sent.html` muestra *"Si {email} está registrado, te hemos enviado un enlace. Caduca en 24 horas."*
5. Usuario abre email → CTA → `accounts/recuperar/<uidb64>/<purpose>/<token>/`.
6. `password_reset_confirm.html` muestra dos campos password (copy de reset). Validación via `AUTH_PASSWORD_VALIDATORS`.
7. POST → `set_password`, `must_change_password=False`, `update_session_auth_hash`, `AuditLog("password_reset_completed", purpose="reset")`, redirige a `accounts/recuperar/cambiada/`.
8. `password_reset_complete.html` con CTA "Ir al login".

### Flujo "email de bienvenida" (alta de usuario)

1. Gestor en `pot/manage_players` → modal de alta. Checkbox **"Enviar email de bienvenida"** (`name="enviar_bienvenida"`, default `checked`).
2. POST de alta:
   - Genera contraseña aleatoria irreproducible (`secrets.token_urlsafe(32)`).
   - `User.objects.create_user(email=..., name=..., password=random, must_change_password=True)`.
   - Si `enviar_bienvenida` está marcado: `send_password_reset_email(user, purpose="welcome")` + `AuditLog("password_reset_email_sent", purpose="welcome", actor=gestor)`.
3. Usuario abre email → CTA → mismo confirm view con `purpose=welcome`, copy distinto ("Bienvenido a la porra", "Establece tu contraseña para entrar al torneo").
4. POST → idéntico al flujo de reset salvo `AuditLog("password_reset_completed", purpose="welcome")`.

### Flujo "reenviar email" (gestor)

1. Botón mail en la fila del jugador → POST a `pot:player_resend_invite/<player_id>/`.
2. Vista del gestor decide:
   - Si `user.must_change_password=True` y `user.last_login is None` → `purpose="welcome"`.
   - En otro caso → `purpose="reset"`.
3. Llama a `send_password_reset_email(user, purpose)`. Crea `AuditLog("password_reset_email_sent", actor=gestor, purpose=...)`.
4. Devuelve toast "Email enviado a {email}".

## Backend

### `accounts/services/token_generator.py` (nuevo)

```python
from datetime import timedelta
from django.conf import settings
from django.contrib.auth.tokens import PasswordResetTokenGenerator
from django.utils.crypto import constant_time_compare
from django.utils.http import base36_to_int


class PorraPasswordResetTokenGenerator(PasswordResetTokenGenerator):
    """Token de reset/welcome con TTL por propósito.

    Cambios vs la base de Django:
    - `make_token(user, purpose)` y `check_token(user, token, purpose)` aceptan
      el propósito y lo incluyen en el material firmado (`_make_hash_value`).
      Así un token de welcome **no es válido** como reset y viceversa.
    - `check_token` usa el TTL de TIMEOUTS[purpose] en vez del global
      `PASSWORD_RESET_TIMEOUT` de Django.
    """

    TIMEOUTS = {
        "reset": timedelta(hours=24),
        "welcome": timedelta(days=7),
    }
    KEY_SALT = "porra26.accounts.PasswordResetTokenGenerator"

    def _make_hash_value(self, user, timestamp, purpose="reset"):
        return f"{user.pk}{user.password}{user.last_login or ''}{timestamp}{purpose}"

    def make_token(self, user, purpose="reset"):
        if purpose not in self.TIMEOUTS:
            raise ValueError(f"purpose desconocido: {purpose!r}")
        return self._make_token_with_timestamp(
            user, self._num_seconds(self._now()), purpose
        )

    def _make_token_with_timestamp(self, user, timestamp, purpose="reset"):
        # mismo formato base36-ts + hash, con purpose en el hash_value
        ts_b36 = int_to_base36(timestamp)
        hash_string = salted_hmac(
            self.KEY_SALT,
            self._make_hash_value(user, timestamp, purpose),
            secret=self.secret,
            algorithm=self.algorithm,
        ).hexdigest()[::2]
        return f"{ts_b36}-{hash_string}"

    def check_token(self, user, token, purpose="reset"):
        if not (user and token) or purpose not in self.TIMEOUTS:
            return False
        try:
            ts_b36, _ = token.split("-")
            ts = base36_to_int(ts_b36)
        except ValueError:
            return False
        if not constant_time_compare(
            self._make_token_with_timestamp(user, ts, purpose), token
        ):
            return False
        # TTL por propósito
        age = self._num_seconds(self._now()) - ts
        if age > self.TIMEOUTS[purpose].total_seconds():
            return False
        return True


token_generator = PorraPasswordResetTokenGenerator()
```

Notas de implementación:

- La invalidación por cambio de contraseña sigue funcionando: `user.password` está en el hash, así que cualquier `set_password` rompe los tokens previos. Uso único de facto.
- `user.last_login or ''` evita que un usuario recién creado (con `last_login=None`) rompa el hash.
- `KEY_SALT` distinto al de Django (`PasswordResetTokenGenerator.key_salt`) por higiene: nuestros tokens no son intercambiables con los de la base.

### `accounts/services/password_reset.py` (nuevo)

```python
def build_reset_url(user, purpose: str) -> str:
    uidb64 = urlsafe_base64_encode(force_bytes(user.pk))
    token = token_generator.make_token(user, purpose)
    path = reverse("accounts:password_reset_confirm",
                   kwargs={"uidb64": uidb64, "purpose": purpose, "token": token})
    return f"{settings.SITE_URL}{path}"


def send_password_reset_email(user, purpose: str, actor=None) -> None:
    """Envía email de reset/welcome a `user.email`.

    - `actor`: gestor que dispara el reenvío (alta o botón mail). `None` en autoservicio.
    - Crea AuditLog `password_reset_email_sent`.
    - Propaga excepciones SMTP.
    """
    if purpose not in ("reset", "welcome"):
        raise ValueError(f"purpose desconocido: {purpose!r}")
    reset_url = build_reset_url(user, purpose)
    subject = SUBJECTS[purpose]
    html = render_to_string("accounts/emails/password_reset.html",
                            {"user": user, "purpose": purpose, "reset_url": reset_url})
    text = render_to_string("accounts/emails/password_reset.txt",
                            {"user": user, "purpose": purpose, "reset_url": reset_url})
    message = EmailMultiAlternatives(
        subject=subject, body=text,
        from_email=settings.DEFAULT_FROM_EMAIL, to=[user.email],
    )
    message.attach_alternative(html, "text/html")
    message.send(fail_silently=False)
    AuditLog.objects.create(
        actor=actor, action="password_reset_email_sent",
        target_type="user", target_id=str(user.id),
        payload={"purpose": purpose, "subject": subject},
    )


SUBJECTS = {
    "welcome": "[Porra26] Bienvenido a la porra del Mundial",
    "reset": "[Porra26] Restablece tu contraseña",
}


def validate_reset_token(uidb64: str, purpose: str, token: str) -> User | None:
    """Devuelve el usuario si todo cuadra, None si no."""
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid, is_active=True)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        return None
    if not token_generator.check_token(user, token, purpose):
        return None
    return user
```

### `accounts/views.py` — vistas nuevas

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
            actor=None, action="password_reset_requested",
            target_type="user", target_id=str(user.id) if user else "",
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

    def dispatch(self, request, uidb64, purpose, token, *args, **kwargs):
        if purpose not in ("reset", "welcome"):
            return HttpResponseNotFound()
        self.user = validate_reset_token(uidb64, purpose, token)
        self.purpose = purpose
        if self.user is None:
            return render(request, "accounts/password_reset_invalid.html",
                          status=410)  # Gone
        return super().dispatch(request, *args, **kwargs)

    def get(self, request):
        return render(request, self.template_name, {
            "purpose": self.purpose, "form": SetPasswordForm(self.user),
        })

    def post(self, request):
        form = SetPasswordForm(self.user, request.POST)
        if not form.is_valid():
            return render(request, self.template_name,
                          {"purpose": self.purpose, "form": form})
        self.user.set_password(form.cleaned_data["new_password1"])
        self.user.must_change_password = False
        self.user.save(update_fields=["password", "must_change_password"])
        AuditLog.objects.create(
            actor=None, action="password_reset_completed",
            target_type="user", target_id=str(self.user.id),
            payload={"purpose": self.purpose, "ip": _client_ip(request)},
        )
        # Sin login automático: redirige al login con el email pre-llenado
        return redirect("accounts:password_reset_complete")


class PasswordResetCompleteView(TemplateView):
    template_name = "accounts/password_reset_complete.html"
```

`SetPasswordForm` es el de `django.contrib.auth.forms` (dos campos, valida con `AUTH_PASSWORD_VALIDATORS` y comprueba que coinciden).

### `accounts/urls.py`

```python
path("recuperar/", views.PasswordResetRequestView.as_view(), name="password_reset"),
path("recuperar/enviado/", views.PasswordResetSentView.as_view(), name="password_reset_sent"),
path("recuperar/<uidb64>/<str:purpose>/<token>/",
     views.PasswordResetConfirmView.as_view(), name="password_reset_confirm"),
path("recuperar/cambiada/", views.PasswordResetCompleteView.as_view(), name="password_reset_complete"),
```

### `pot/views.py` — alta de jugadores

Localizar el endpoint `pot:player_create` (o equivalente). Tras crear el `User`:

```python
if form.cleaned_data.get("enviar_bienvenida"):
    send_password_reset_email(user, purpose="welcome", actor=request.user)
```

El form ganará `enviar_bienvenida = forms.BooleanField(initial=True, required=False, label="Enviar email de bienvenida")`. Si el campo viejo de "contraseña inicial" existía, queda como opcional (solo aplica si el check no está marcado).

### `pot/views.py` — nuevo endpoint `player_resend_invite`

```python
class PlayerResendInviteView(LoginRequiredMixin, GestorRequiredMixin, View):
    def post(self, request, pk):
        user = get_object_or_404(User, pk=pk, is_active=True)
        if user.must_change_password and user.last_login is None:
            purpose = "welcome"
        else:
            purpose = "reset"
        send_password_reset_email(user, purpose=purpose, actor=request.user)
        return JsonResponse({"ok": True, "email": user.email, "purpose": purpose})
```

URL: `path("jugadores/<int:pk>/reenviar-email/", views.PlayerResendInviteView.as_view(), name="player_resend_invite")`.

### `SITE_URL` — promoción a settings

`competition/services/reminder_email.py:19` define `SITE_URL = "https://laporradeljefe.es"`. Lo movemos a `porra26/settings/base.py` como `SITE_URL = os.getenv("SITE_URL", "https://laporradeljefe.es")` y lo reusamos en `password_reset.py` y `reminder_email.py`.

## Plantillas

Todas extienden `base.html` y usan `.login-screen` para heredar layout.

### `templates/accounts/password_reset_request.html`

- Header (logo + chip "Edición interna · Mundial 2026") idéntico al login.
- Card `.glass.rise.login-form-card` centrada (~440px de ancho — añadiremos `.login-body--narrow` modificadora que vacía el grid del `aside`).
- `h1.display`: "Recupera tu contraseña"
- Párrafo dim: "Introduce tu correo de empresa y te enviaremos un enlace para restablecerla."
- Campo email con icono `mail` (mismo widget `login-input-with-icon` que el login).
- Botón primario "Enviar enlace" con icono `mail` derecha.
- Link discreto al pie: "← Volver al login".

### `templates/accounts/password_reset_sent.html`

- Icono grande `check-circle` (`var(--c-green)`).
- `h1`: "Revisa tu correo"
- Texto: "Si **{{ email }}** está registrado, te hemos enviado un enlace para restablecer tu contraseña. Caduca en 24 horas."
- Link "← Volver al login".

### `templates/accounts/password_reset_confirm.html`

- Variante según `purpose`:
  - `reset`: `h1` = "Nueva contraseña", subtítulo "Elige una contraseña que recuerdes."
  - `welcome`: `h1` = "Bienvenido a la porra", subtítulo "Establece tu contraseña para entrar al torneo."
- Dos campos password con icono `lock`.
- Errores debajo (`var(--c-red)`).
- Botón primario "Guardar contraseña" con icono `lock`.

### `templates/accounts/password_reset_invalid.html`

- Icono `alert-triangle` (`var(--c-amber)`).
- `h1`: "Enlace no válido"
- Texto: "Este enlace ha caducado o ya se ha usado. Pídele al gestor que te reenvíe el correo, o vuelve a iniciar el flujo de recuperación."
- Dos links: "← Volver al login" y "Solicitar otro enlace" (→ `password_reset`).

### `templates/accounts/password_reset_complete.html`

- Icono `check-circle` grande, `var(--c-green)`.
- `h1`: "Contraseña actualizada"
- Texto: "Ya puedes entrar al torneo."
- Botón primario "Ir al login" con icono `ball`.

### `templates/accounts/login.html:53-55` — cambio

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

### `templates/pot/manage_players.html` — botón mail

Junto al candado, antes de Activar/Baja:

```html
<button class="btn btn-ghost"
        data-resend-invite-url="{% url 'pot:player_resend_invite' p.id %}"
        style="width:32px;height:32px;padding:0"
        title="Reenviar email de acceso">
  {% icon "mail" width=14 %}
</button>
```

Pequeño JS en la página (mismo patrón que ya existe para los modales) que captura el click, hace POST con CSRF al endpoint y muestra un toast.

### Chip "Pendiente de activar"

En la celda del nombre del jugador, si `p.must_change_password and not p.last_login`:

```html
<span class="chip chip-amber" style="margin-left:6px;font-size:11px">Pendiente de activar</span>
```

## Email

### `templates/accounts/emails/password_reset.html`

Layout en `<table>` 600px centrada, estilos inline en cada elemento. Una sola plantilla; el copy cambia según `purpose`.

Estructura:

```html
<!DOCTYPE html>
<html lang="es"><body style="margin:0;padding:0;background:#F5F6F8;font-family:'Segoe UI',system-ui,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" border="0"><tr><td align="center" style="padding:24px 12px">
    <table width="600" cellpadding="0" cellspacing="0" border="0"
           style="background:#FFFFFF;border-radius:16px;overflow:hidden;
                  box-shadow:0 2px 12px rgba(15,23,42,0.06)">

      <!-- Banda superior multicolor 14px -->
      <tr><td style="height:14px;background:linear-gradient(90deg,#E11D48,#F97316,#EAB308,#22C55E,#3B82F6,#8B5CF6);"></td></tr>

      <!-- Cabecera -->
      <tr><td style="padding:32px 40px 8px 40px">
        <img src="https://laporradeljefe.es/static/img/logo.png" width="120" alt="EDISA · Mundial 2026"
             style="display:block;border:0;outline:none">
        <p style="margin:16px 0 0;font-size:11px;letter-spacing:0.12em;color:#6B7280;text-transform:uppercase">
          Mundial FIFA 2026 · Edición interna
        </p>
      </td></tr>

      <!-- Cuerpo -->
      <tr><td style="padding:8px 40px 8px 40px">
        <h1 style="margin:8px 0 16px;font-size:28px;line-height:1.2;color:#0F172A;font-weight:700">
          {% if purpose == 'welcome' %}Bienvenido a la porra{% else %}Restablece tu contraseña{% endif %}
        </h1>
        <p style="margin:0 0 16px;font-size:15px;line-height:1.6;color:#374151">
          {% if purpose == 'welcome' %}
            Te han creado cuenta en la porra del Mundial 2026 de EDISA. Pulsa el botón para establecer tu contraseña y empezar a apostar. El enlace caduca en 7 días.
          {% else %}
            Hemos recibido una solicitud para restablecer tu contraseña. Pulsa el botón para elegir una nueva. El enlace caduca en 24 horas. Si no fuiste tú, ignora este correo.
          {% endif %}
        </p>
      </td></tr>

      <!-- CTA -->
      <tr><td align="center" style="padding:16px 40px 8px 40px">
        <a href="{{ reset_url }}"
           style="display:inline-block;padding:14px 28px;border-radius:12px;
                  background:#0F172A;color:#FFFFFF;font-weight:600;
                  text-decoration:none;font-size:15px">
          {% if purpose == 'welcome' %}Establecer contraseña →{% else %}Restablecer contraseña →{% endif %}
        </a>
      </td></tr>

      <!-- Fallback link -->
      <tr><td style="padding:24px 40px 8px 40px">
        <p style="margin:0;font-size:12px;color:#6B7280;line-height:1.5">
          ¿No funciona el botón? Copia y pega esta dirección en tu navegador:
        </p>
        <p style="margin:6px 0 0;font-family:ui-monospace,'SF Mono',monospace;
                  font-size:12px;color:#374151;word-break:break-all">
          {{ reset_url }}
        </p>
      </td></tr>

      <!-- Footer -->
      <tr><td style="padding:32px 40px 24px 40px;border-top:1px solid #E5E7EB;margin-top:24px">
        <p style="margin:24px 0 0;font-size:12px;color:#9CA3AF;line-height:1.5">
          Mundial FIFA 2026 · Edición interna · EDISA
        </p>
        <p style="margin:4px 0 0;font-size:12px;color:#9CA3AF;line-height:1.5">
          Este correo lo envía la porra interna. No respondas a este mensaje.
        </p>
      </td></tr>

      <!-- Banda inferior 6px -->
      <tr><td style="height:6px;background:linear-gradient(90deg,#E11D48,#F97316,#EAB308,#22C55E,#3B82F6,#8B5CF6);"></td></tr>

    </table>
  </td></tr></table>
</body></html>
```

### `templates/accounts/emails/password_reset.txt`

```
{% if purpose == 'welcome' %}Bienvenido a la porra del Mundial 2026 de EDISA.

Te han creado cuenta. Establece tu contraseña aquí (caduca en 7 días):
{% else %}Restablece tu contraseña.

Hemos recibido una solicitud para restablecer tu contraseña. Elige una nueva aquí (caduca en 24 horas):
{% endif %}{{ reset_url }}

— Porra EDISA · Mundial 2026
```

## Auditoría

Tres acciones nuevas en `AuditLog`:

| `action` | `actor` | `target_type` / `target_id` | `payload` |
|---|---|---|---|
| `password_reset_requested` | `None` | `user` / id o vacío | `{email_intentado, encontrado, ip, purpose:"reset"}` |
| `password_reset_email_sent` | gestor en welcome/reenvío, `None` en autoservicio | `user` / id | `{purpose, subject}` |
| `password_reset_completed` | `None` | `user` / id | `{purpose, ip}` |

`_client_ip(request)` lee `HTTP_X_FORWARDED_FOR` (primer hop) o `REMOTE_ADDR`. Si ya existe un helper similar en el repo lo reusamos; si no, vive en `accounts/services/password_reset.py`.

## Tests

Carpeta `accounts/tests/` ya existe. Ficheros nuevos:

### `accounts/tests/test_password_reset_views.py`

- GET `password_reset` renderiza.
- POST email existente `@edisa.com` activo → redirige a sent, 1 email enviado, `AuditLog` requested(found=True) y email_sent.
- POST email existente pero `is_active=False` → redirige a sent, **0 emails**, `AuditLog` requested(found=False) (no enumera).
- POST email fuera de `EMAIL_DOMAIN` → idem (sin distinguir).
- POST email no existente → idem.
- GET `password_reset_confirm` con token válido reset → renderiza form con `purpose=reset` en contexto.
- GET con token válido welcome → renderiza con `purpose=welcome`.
- GET con token caducado (reset >24h, welcome >7d) → `password_reset_invalid.html` con 410.
- GET con `purpose` URL distinto al codificado en token → 410.
- GET con `purpose` URL no válido → 404.
- POST con passwords válidas → set_password, must_change_password=False, AuditLog completed, redirige a complete.
- POST con passwords que no coinciden → re-renderiza con error.
- POST con password que falla validators → idem.
- POST con token ya usado (segunda vez) → 410 (porque user.password cambió e invalida el hash).
- GET `password_reset_complete` renderiza.

### `accounts/tests/test_password_reset_token_generator.py`

- `make_token(user, "reset")` ≠ `make_token(user, "welcome")` para el mismo timestamp.
- `check_token(user, reset_token, "reset") is True`.
- `check_token(user, reset_token, "welcome") is False` (cross-purpose).
- `check_token(user, welcome_token, "reset") is False`.
- Con `freeze_time` a >24h del make → `check_token(..., "reset") is False`, `check_token(..., "welcome") is True`.
- Con `freeze_time` a >7d → ambos `False`.
- `user.set_password(...)` invalida tokens previos (con misma `purpose`).
- `make_token(user, "bogus")` lanza `ValueError`.

### `accounts/tests/test_password_reset_email_service.py`

- `send_password_reset_email(user, "reset")` envía 1 email con asunto `[Porra26] Restablece tu contraseña`, body texto con `reset_url`, alternative HTML.
- `purpose="welcome"` produce asunto `[Porra26] Bienvenido…` y copy welcome en HTML.
- `to=[user.email]` (no a `TEAMS_DESTINATION_EMAIL`).
- `from_email=DEFAULT_FROM_EMAIL`.
- Crea `AuditLog` con `actor` pasado.
- `purpose="bogus"` lanza `ValueError`.

### `pot/tests/test_player_resend_invite.py`

- Solo accesible a gestores (403 a jugador, 302 a login si anónimo).
- POST a un user con `must_change_password=True, last_login is None` → manda welcome.
- POST a un user con `last_login` ya establecido → manda reset.
- POST a un user inactivo → 404.
- `AuditLog` con `actor=request.user` (el gestor).

### `pot/tests/test_player_create_envia_bienvenida.py` (o extender un test existente)

- POST de alta con `enviar_bienvenida=on` → user creado + 1 email welcome enviado.
- POST sin el check → user creado + 0 emails.

### Tests existentes a tocar

- Si hay un `test_login_view.py` que asserta el copy *"Pídele a un gestor"*, actualizarlo a buscar el link `password_reset`.
- `seed_players` no cambia.

## Cambios documentales

- `CLAUDE.md` "Reglas de negocio clave":
  - Antes: *"Sin auto-recuperación: la contraseña la restablece un gestor. Altas crean contraseña temporal."*
  - Después: *"Recuperación por email autoservicio (token 24h). Altas pueden enviar email de bienvenida (token 7d) o quedar con contraseña fijada por el gestor."*
- `docs/DATA_MODEL.md` §5: análoga reescritura.
- `templates/core/rules.html:252-254`: actualizar texto público a *"Si olvidas tu contraseña, en el login tienes un enlace para recuperarla por email."*

## Configuración nueva

Ninguna variable de entorno obligatoria nueva. `SITE_URL` opcional (default a `https://laporradeljefe.es`). Los timeouts viven en el código (`PorraPasswordResetTokenGenerator.TIMEOUTS`); cambiarlos es un commit explícito.

## Migraciones

Ninguna. No se añade ningún campo a `User`; `must_change_password` ya existe y se reusa.

## Riesgos y decisiones de seguridad

- **Anti-enumeración**: el flujo nunca revela si un email existe. Tanto el AuditLog interno como la respuesta del servidor son indistinguibles a ojos del cliente entre "email no existe", "email fuera de dominio" e "email existe". Solo difieren en si se manda el email (lo cual el atacante no puede observar).
- **TTL distinto por propósito**: el `purpose` está codificado en el token y en la URL, validado en ambos lados. Un atacante no puede "alargar" un token reset a 7d.
- **Uso único de facto**: el `user.password` participa en el hash del token. Tras `set_password`, los tokens previos quedan inválidos. No hace falta tabla `used_tokens`.
- **Invalidación de sesiones tras reset**: `update_session_auth_hash` no aplica porque tras el reset el usuario no está logueado todavía. La regeneración del hash de password ya invalida cualquier sesión activa que tuviera en otro navegador.
- **Sin rate limit**: aceptable para 50 usuarios internos. Si en el futuro se abre el sistema, conviene meter `django-ratelimit` al endpoint POST de `password_reset`.
- **Bounce de email**: si Resend marca el email como hard bounce (dirección inválida), el `AuditLog` queda con `password_reset_email_sent` aunque el usuario no lo reciba. El log de Resend (panel web) es la fuente de verdad para deliverability.

## Cómo probarlo en local / staging

1. Configurar `DEFAULT_FROM_EMAIL` y credenciales SMTP de Resend en `.env`.
2. Crear un user de prueba con `python manage.py createsuperuser` o `seed_players`.
3. Flujo welcome: desde `pot/manage_players` dar de alta un jugador con email real del dominio → comprobar que llega el email, abrirlo, establecer contraseña, loguear.
4. Flujo reset: pulsar "¿Olvidaste tu contraseña?" en login, meter el email, comprobar email, cambiar contraseña, loguear.
5. Verificar `AuditLog` en admin: las tres acciones nuevas con sus payloads.
6. Probar token caducado: en `shell` hacer `make_token` y modificar `TIMEOUTS["reset"]` a `timedelta(seconds=1)`, esperar, intentar usar → 410.

## Fuera de alcance, posibles iteraciones futuras

- Rate limit en `password_reset` POST si el sistema se abre fuera de EDISA.
- Dashboard de "usuarios pendientes de activar" con botón masivo de reenvío.
- Personalización del email de bienvenida con un par de tips para apostar.
- Soporte de WebAuthn / passkeys (descartado por scope; sigue con email + contraseña).
