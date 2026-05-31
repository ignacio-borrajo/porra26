# Mi cuenta — diseño

Fecha: 2026-05-31
Autor: brainstorming con Claude Code

## 1. Objetivo

Dar al usuario autenticado (jugador o gestor) un sitio para ver y editar sus
datos personales y para cambiar su contraseña, sin tocar los campos que son
responsabilidad del gestor.

## 2. Alcance

Sí entra:

- Página única `/mi-cuenta/`, accesible para cualquier usuario autenticado.
- Edición de `name`, `dept`, `sede`, `puesto`.
- Cambio de contraseña reutilizando la lógica existente.
- Toggle de tema visible como bloque de "Preferencias" (sin cambios de modelo).
- Acceso desde el topbar mediante click en el avatar/nombre.

No entra:

- Edición de `email`, `role`, `is_staff`, `is_active`, `must_change_password`.
- Persistencia del tema en BD.
- Auto-recuperación de contraseña olvidada (sigue siendo manual por gestor).
- Nuevas pantallas para el flujo forzado de cambio de contraseña: `/cambiar-password/` y su middleware se mantienen tal cual para el primer login.

## 3. Restricciones del proyecto

- Stack Django + plantillas server-rendered + JS vanilla. Nada de SPA ni endpoints JSON para esta feature.
- Estética glass con tokens definidos en `static/css/styles.css` y documentados en `docs/DESIGN_SPEC.md`. Textos en español de España.
- CI exige cobertura ≥ 70 % (ruff + pytest).
- Hay una sesión paralela que añade `sede` y `puesto` al modelo `User` y convierte `dept` en `CharField` con `choices=DEPT_CHOICES`. Este spec asume que esa migración aterriza antes de la implementación; los choices viven en el modelo y el form los toma de ahí (no se enumeran aquí).

## 4. Arquitectura

Todo el código vive en la app `accounts/`.

### 4.1 URL

En `accounts/urls.py`:

```python
path("mi-cuenta/", views.MyAccountView.as_view(), name="my_account"),
```

### 4.2 View

`MyAccountView(LoginRequiredMixin, View)` en `accounts/views.py`.

- `GET` → renderiza `accounts/my_account.html` con dos forms instanciados: `ProfileForm(instance=request.user)` y `ChangePasswordForm(request.user)`.
- `POST` → despacha por `request.POST.get("action")`:
  - `"profile"` → valida y guarda `ProfileForm`. En éxito: `messages.success("Datos actualizados.")` y `redirect("accounts:my_account")` (patrón post-redirect-get).
  - `"password"` → valida y guarda `ChangePasswordForm` (el existente). En éxito: `set_password(new1)`, `must_change_password = False`, `save(update_fields=["password", "must_change_password"])`, `update_session_auth_hash(request, request.user)` para no cerrar la sesión, `messages.success("Contraseña actualizada.")`, `redirect("accounts:my_account")`.
  - Otro valor o ausencia → `HttpResponseBadRequest("acción no válida")`.

En caso de form inválido se re-renderiza la misma plantilla con status 200 y el otro form se instancia limpio para que sus campos no aparezcan con errores que el usuario no provocó.

### 4.3 Forms

En `accounts/forms.py`:

- Nuevo `ProfileForm(forms.ModelForm)`:
  ```python
  class Meta:
      model = User
      fields = ["name", "dept", "sede", "puesto"]
  ```
  - `name` valida no vacío y aplica `strip` (se sobreescribe `clean_name`).
  - `dept`, `sede`, `puesto` heredan los choices del modelo y se renderizan como `<select>` automáticamente.
  - Cualquier campo extra enviado en el POST (email, role, is_staff, etc.) es ignorado por Django porque no aparece en `Meta.fields`.
- `ChangePasswordForm` se reutiliza sin cambios.

### 4.4 Template

`templates/accounts/my_account.html`, extiende `base.html`.

Layout: contenedor `max-width: 720px`, centrado, tres tarjetas `.glass` apiladas en columna con separación vertical consistente con el resto del proyecto.

- **Tarjeta 1 — Datos personales**
  - Email: chip o input deshabilitado con `value="{{ user.email }}"`, nota corta tipo "Para cambiar el email contacta con un gestor".
  - Form con `action=""`, `method="post"`, hidden `name="action" value="profile"`, CSRF, los campos de `ProfileForm`, errores debajo de cada campo, botón primario "Guardar cambios".
- **Tarjeta 2 — Seguridad**
  - Form análogo con hidden `name="action" value="password"`, CSRF, los tres campos de `ChangePasswordForm`, errores, botón "Actualizar contraseña".
- **Tarjeta 3 — Preferencias**
  - Bloque informativo con el botón `data-theme-toggle` (mismo selector que ya usa `theme.js`). No envía POST.

Mensajes globales (`django.contrib.messages`) se renderizan en el bloque estándar del `base.html`. Verificar al implementar si `base.html` ya los pinta; si no, añadirlo en su sitio para que aplique a toda la app.

### 4.5 Topbar

En `templates/partials/_topbar.html`:

- Envolver el bloque del avatar + nombre + rol en un `<a href="{% url 'accounts:my_account' %}">` con `text-decoration:none;color:inherit`.
- El `<form>` de logout queda **fuera** del enlace, como hermano, para no anidar formularios dentro de un `<a>`.
- Añadir estado activo: marcar el bloque con clase activa cuando `ns == 'accounts' and url_name == 'my_account'`. El estilo activo puede ser sutil (borde o background ligero) porque no es un nav-item de la navegación principal.

## 5. Flujo de datos y errores

### 5.1 Editar datos

1. POST con `name`, `dept`, `sede`, `puesto`, `action=profile`, CSRF.
2. `ProfileForm(request.POST, instance=request.user)` valida.
3. Si inválido → re-render con errores. Status 200.
4. Si válido → `form.save()`, `AuditLog` (ver §5.3), `messages.success`, redirect a `my_account` (post-redirect-get para evitar reenvíos con F5).

### 5.2 Cambiar contraseña

1. POST con `current`, `new1`, `new2`, `action=password`, CSRF.
2. `ChangePasswordForm(request.user, request.POST)` valida: contraseña actual correcta, `new1 == new2`, min_length 10, ≥1 mayúscula, ≥1 dígito.
3. Si inválido → re-render con errores. Status 200.
4. Si válido → `set_password`, `must_change_password = False`, `update_session_auth_hash`, `AuditLog`, `messages.success`, redirect a `my_account`.

### 5.3 Auditoría

Se usa el modelo `accounts.AuditLog` ya existente.

- Edición de datos: registrar solo si `form.changed_data` no está vacío.
  - `action = "profile.update"`
  - `target_type = "user"`
  - `target_id = str(user.id)`
  - `payload = {"changed": form.changed_data}` (solo los nombres de campo, nunca valores anteriores ni nuevos para evitar PII innecesaria).
- Cambio de contraseña:
  - `action = "password.change"`
  - `target_type = "user"`
  - `target_id = str(user.id)`
  - `payload = {}` (nunca registrar contraseñas ni hashes).

### 5.4 Casos borde

- Usuario anónimo → `LoginRequiredMixin` redirige a `accounts:login`.
- Usuario con `must_change_password=True` que intenta entrar a `/mi-cuenta/` → el `ForcePasswordChangeMiddleware` lo redirige a `/cambiar-password/` antes de llegar a la view. No requiere cambios.
- POST con `action` ausente o desconocido → 400.
- POST con campos extra (email, role…) → ignorados por `ProfileForm.Meta.fields`. No hay vector de elevación de privilegios.
- Choices inválidos en `dept/sede/puesto` → el `ModelForm` produce error de campo usando los choices del modelo. No se duplica la validación.

## 6. Tests

Suite nueva: `accounts/tests/test_my_account.py`, usando pytest + pytest-django con `@pytest.mark.django_db` y `client.force_login(user)`.

### 6.1 Acceso y rendering

- `test_redirects_anonymous_to_login`
- `test_renders_for_authenticated_user_with_email_readonly` — el email aparece en la página pero su input está `disabled` o `readonly`; los inputs de `name/dept/sede/puesto` aparecen editables.

### 6.2 Editar datos

- `test_profile_post_updates_editable_fields` — POST con valores válidos; tras `user.refresh_from_db()` los cuatro campos están actualizados.
- `test_profile_post_ignores_email_and_role` — POST que añade `email="otro@x.com"` y `role="gestor"`; el User en BD conserva el email y rol originales.
- `test_profile_post_invalid_choice_shows_error` — POST con `dept="INEXISTENTE"` devuelve 200 con error visible y sin escribir en BD.
- `test_profile_post_writes_audit_log_only_when_changed` — un POST sin cambios no crea `AuditLog`; un POST con cambio sí, con `action="profile.update"` y `payload["changed"]` listando los campos modificados.

### 6.3 Cambiar contraseña

- `test_password_post_changes_password_and_keeps_session` — POST válido; `user.check_password(new1)` es `True`; un GET posterior a `/mi-cuenta/` devuelve 200 (sesión viva).
- `test_password_post_wrong_current_shows_error` — `current` errónea; password en BD intacta; error visible.
- `test_password_post_mismatch_shows_error` — `new1 != new2` produce error.
- `test_password_post_weak_rejected` — password sin mayúscula o sin dígito produce error.
- `test_password_post_resets_must_change_flag` — usuario con `must_change_password=True` cambia contraseña → flag pasa a `False`.
- `test_password_change_writes_audit_log` — se crea un `AuditLog` con `action="password.change"` y `payload == {}`.

### 6.4 Despacho por acción

- `test_post_without_action_returns_400`
- `test_post_unknown_action_returns_400`

### 6.5 Topbar (smoke)

- `test_topbar_avatar_links_to_my_account` — render del dashboard incluye un `href` apuntando a `/mi-cuenta/` dentro del bloque del avatar; el `<form>` de logout sigue fuera de ese `<a>`.

Si no existe una factoría de `User` reutilizable en `tests/`, se añade una mínima en el propio archivo (o como `pytest.fixture`).

## 7. Archivos tocados

- `accounts/urls.py` — añadir ruta `my_account`.
- `accounts/views.py` — añadir `MyAccountView`.
- `accounts/forms.py` — añadir `ProfileForm`.
- `templates/accounts/my_account.html` — nuevo.
- `templates/partials/_topbar.html` — envolver bloque del avatar con enlace, ajustar estado activo.
- `accounts/tests/test_my_account.py` — nuevo.
- (Eventual) bloque de mensajes en `templates/base.html` si no estaba ya.

## 8. Riesgos y dependencias

- **Dependencia con la sesión paralela**: la migración que añade `sede` y `puesto` y convierte `dept` en `choices` debe estar mergeada antes de implementar este spec, o el `ProfileForm` no podrá referenciar esos campos.
- **`base.html` y mensajes**: si la app aún no renderiza `django.contrib.messages` de forma global, hay que añadir el bloque en `base.html`. Verificar antes de implementar para no introducirlo por duplicado.
- **Estilos del email solo-lectura**: hay que asegurarse de que el input deshabilitado encaja con el lenguaje glass; si no, usar un chip de texto con `mono` en vez de un `<input disabled>`.
