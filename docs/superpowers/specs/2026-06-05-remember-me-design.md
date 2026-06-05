# Recordarme (Remember Me) — Diseño

**Fecha:** 2026-06-05
**Estado:** Aprobado
**Owner:** Ignacio Borrajo
**Worktree:** `worktree-remember-me`

## 1. Objetivo

Permitir que un jugador no tenga que volver a introducir su contraseña en cada visita, manteniendo el nivel de seguridad lo más alto posible y respondiendo correctamente a cambios de contraseña y otros eventos sensibles.

## 2. Restricciones y contexto

- App **interna de empresa**, jugadores con email `@edisa.com` / `@edisa.university.com`.
- Stack: Django 5 + Postgres, sesiones server-side en `django_session`, hosting Railway, dominio público `laporradeljefe.es`.
- Auth actual: `accounts.User` (AbstractBaseUser) + `EmailBackend` + `django-axes` (rate limit por IP+email).
- Recuperación de contraseña por email autoservicio (token 24h). Bienvenida con token de 7 días.
- PWA instalable en iOS/Android.
- Hasta el final del Mundial 2026 quedan ~7 meses de uso activo.

## 3. Decisiones de diseño

### 3.1 Mecanismo

**Sesiones largas opt-in + tabla `UserSession` con metadatos.** NO se usa el patrón "cookie selector+validator" (token persistente rotativo).

Razones:
- Django ya hace lo importante: rotación de session_key en cada login, invalidación automática vía `session_auth_hash`, cookies HttpOnly/Secure/Lax.
- Una segunda cookie paralela duplica complejidad para una app interna sin gran ganancia frente al ataque marginal que cubre.
- La tabla `UserSession` desbloquea la lista de "Mis dispositivos" y el botón "Cerrar otras sesiones".

### 3.2 Activación

Checkbox `Recordarme en este dispositivo` en el login, **pre-marcado por defecto**. Si se desmarca, la sesión expira al cerrar el navegador. Si se mantiene, sesión de 30 días con renovación por uso.

### 3.3 Duración

- Sesión "recordada": 30 días desde el último uso (sliding window).
- Renovación al uso: middleware actualiza `set_expiry(30 días)` y `last_seen_at` máx. 1 vez/min/sesión (throttle vía cache).
- Sesión no recordada: `set_expiry(0)` — se cierra al cerrar el navegador.

### 3.4 Visibilidad y revocación

Lista de sesiones activas en `/mi-cuenta/`, con device label, IP de login y última actividad. Botón por sesión para cerrarla y botón global "Cerrar todas las demás sesiones". Sin step-up auth (basta click).

## 4. Modelo de datos

Nueva tabla `accounts.UserSession`:

```python
class UserSession(models.Model):
    user = ForeignKey(User, related_name="sessions", on_delete=CASCADE)
    session_key = CharField(max_length=40, unique=True, db_index=True)
    device_label = CharField(max_length=80)
    user_agent_raw = CharField(max_length=400, blank=True)
    ip_at_login = GenericIPAddressField(null=True)
    is_pwa = BooleanField(default=False)
    remembered = BooleanField(default=False)
    created_at = DateTimeField(auto_now_add=True)
    last_seen_at = DateTimeField(db_index=True)
```

Reglas:
- `session_key` es la clave canónica — coincide con `django_session.session_key`.
- `device_label` se deriva en el login con la librería `user-agents`. Ejemplos: `"iPhone — Safari"`, `"Chrome en macOS"`, `"PWA — iOS 17"`.
- `ip_at_login` es **informativa**; nunca se usa para validar la sesión (las redes móviles cambian de IP constantemente).
- `is_pwa` se detecta vía un input hidden `is_pwa=1` que el JS de la pantalla de login añade cuando `window.matchMedia('(display-mode: standalone)').matches` o `navigator.standalone`. Si no llega, default `False`.
- `last_seen_at` se actualiza por middleware, throttled.

## 5. Flujo de login

Cambios en `accounts/forms.py:LoginForm`:
- Añadir `remember = BooleanField(required=False, initial=True)`. El `initial=True` deja el checkbox pre-marcado en el render del template.

Cambios en `accounts/views.py:LoginView.post`:
- Tras `login(request, user)`:
  - Si `cleaned_data["remember"]`: `request.session.set_expiry(30 * 24 * 3600)`.
  - Si no: `request.session.set_expiry(0)`.
- Crear `UserSession` con `session_key`, `device_label`, `user_agent_raw`, `ip_at_login`, `is_pwa` (de `request.POST["is_pwa"] == "1"`), `remembered`, `last_seen_at=now`.
- Registrar `AuditLog(action="login", payload={"remembered", "is_pwa", "ip"})`.

## 6. Middleware de refresh

Nuevo `accounts.middleware.RememberMeRefreshMiddleware`, registrado tras `ForcePasswordChangeMiddleware`.

Pseudocódigo:

```python
def __call__(self, request):
    response = self.get_response(request)
    if not request.user.is_authenticated or not request.session.session_key:
        return response
    cache_key = f"session_touch:{request.session.session_key}"
    if cache.get(cache_key):
        return response
    cache.set(cache_key, 1, timeout=60)
    try:
        us = UserSession.objects.get(session_key=request.session.session_key)
    except UserSession.DoesNotExist:
        return response
    if us.remembered:
        request.session.set_expiry(30 * 24 * 3600)
    UserSession.objects.filter(pk=us.pk).update(last_seen_at=timezone.now())
    return response
```

Throttle vía `django.core.cache` con `LocMemCache` (default) o Redis si está disponible. El throttle no requiere consistencia perfecta — un over-write por minuto y worker es aceptable.

## 7. Logout

`LogoutView.post` borra primero la `UserSession` correspondiente y después llama a `logout()`:

```python
if request.user.is_authenticated and request.session.session_key:
    UserSession.objects.filter(session_key=request.session.session_key).delete()
logout(request)
```

## 8. Servicio central `revoke_sessions`

`accounts/services/sessions.py`:

```python
def revoke_sessions(*, user, session_keys, actor=None, reason="manual") -> int:
    if not session_keys:
        return 0
    keys = list(session_keys)
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

Borra primero la `Session` real (la cookie deja de valer inmediatamente) y luego la `UserSession`.

## 9. Vista "Mis sesiones"

En `MyAccountView`, tercer bloque tras "Perfil" y "Contraseña". Contexto añadido:

```python
sessions = UserSession.objects.filter(user=request.user).order_by("-last_seen_at")
current_session_key = request.session.session_key
```

Acciones `POST` nuevas:
- `action="revoke_session"` + `session_key`: revoca **una** sesión. Rechaza si la `session_key` es la actual (HTTP 400) o no pertenece al usuario.
- `action="revoke_others"`: revoca todas excepto la actual.

UI: lista vertical de mini-cards *glass*, una por sesión. Cada fila muestra:
- Emoji device (📱 iPhone/Android, 💻 macOS, 🖥 Windows/Linux).
- `device_label` con sufijo `(PWA)` si `is_pwa`.
- Badge `[ESTA SESIÓN]` si es la actual.
- IP y `last_seen_at` con `naturaltime` (requiere `django.contrib.humanize`).
- Botón `[Cerrar]` *ghost danger* (no en la sesión actual).

Al final: botón global `[Cerrar todas las demás sesiones]` si hay >1 sesión.

Estética según `design-reference/styles.css`. Sin tokens nuevos.

## 10. Invalidación en cambios de contraseña

### 10.1 Cambio voluntario (Mi cuenta)

`MyAccountView._post_password` tras `set_password` y `update_session_auth_hash`:

```python
others = list(
    UserSession.objects.filter(user=request.user)
    .exclude(session_key=request.session.session_key)
    .values_list("session_key", flat=True)
)
revoke_sessions(user=request.user, session_keys=others, actor=request.user,
                reason="password_change")
```

La sesión actual sobrevive (mejor UX). Mensaje: `"Contraseña actualizada. Se han cerrado tus otras sesiones."` solo si `others` no está vacío.

### 10.2 Reset por email

`PasswordResetConfirmView.post` tras `form.save()`:

```python
all_keys = list(UserSession.objects.filter(user=user).values_list("session_key", flat=True))
revoke_sessions(user=user, session_keys=all_keys, actor=None,
                reason="password_reset_email")
```

Aquí se cierran **todas** las sesiones, incluidas las que pudiera tener un atacante.

### 10.3 Cambio forzado (`ChangePasswordView`)

Mismo trato que 10.1. En la práctica casi no hay sesiones "otras" porque es primer login, pero el código es idéntico.

### 10.4 Cambios desde admin Django

Signal `post_save` en `User` con `"password" in update_fields`:

```python
@receiver(post_save, sender=User)
def _wipe_sessions_on_password_change(sender, instance, **kwargs):
    update_fields = kwargs.get("update_fields") or set()
    if "password" in update_fields:
        UserSession.objects.filter(user=instance).delete()
```

`session_auth_hash` se encarga de invalidar las `Session` reales; el signal solo limpia las `UserSession` huérfanas.

### 10.5 `session_auth_hash` — defensa en profundidad

Aunque la revocación manual falle (excepción, race), `AuthenticationMiddleware` invalida cualquier sesión cuyo `session_auth_hash` no coincida con el actual. Como el hash se deriva de `password`, cualquier cambio en contraseña invalida automáticamente las sesiones viejas en el siguiente request.

`update_session_auth_hash(request, user)` se sigue llamando tras `set_password` en los flujos 10.1 y 10.3 para mantener viva la sesión actual.

## 11. Email de notificación de cambio de contraseña

En los tres flujos de cambio (voluntario, reset, forzado), enviar email al usuario:

- Sender: `PASSWORD_RESET_FROM_EMAIL` (ya existe).
- Asunto: `"Tu contraseña en La Porra del Jefe se ha cambiado"`.
- Cuerpo: fecha del cambio, enlace a recuperación si no fue él, contacto al gestor.

Reusa plantilla `accounts/templates/accounts/emails/_layout.html` (si no existe, se extrae del email de reset actual).

## 12. Limpieza periódica

Management command `accounts/management/commands/prune_user_sessions.py`:

- Borra `UserSession` cuya `session_key` ya no esté en `django_session`.
- Borra `UserSession` con `last_seen_at > 35 días` (margen sobre los 30 reales).
- Reporta count borrado.

Programado en cron diario (Railway scheduled job — pendiente de configurar en `railway.toml` o tabla de crons).

## 13. Settings

`porra26/settings/base.py`:

```python
SESSION_COOKIE_AGE = 30 * 24 * 3600
SESSION_SAVE_EVERY_REQUEST = False  # usamos middleware con throttle
SESSION_EXPIRE_AT_BROWSER_CLOSE = False  # lo controlamos por sesión
```

`porra26/settings/prod.py`:

```python
SESSION_COOKIE_SECURE = True  # requiere HTTPS — Railway lo sirve por defecto
```

`INSTALLED_APPS`: añadir `django.contrib.humanize`.

`MIDDLEWARE`: añadir `accounts.middleware.RememberMeRefreshMiddleware` tras `ForcePasswordChangeMiddleware`.

`requirements.txt`: añadir `user-agents` (~50KB, sin deps extra).

## 14. Cookies

Confirmar/asegurar:
- `SESSION_COOKIE_HTTPONLY = True` ✓ ya configurado
- `SESSION_COOKIE_SAMESITE = "Lax"` ✓ ya configurado
- `SESSION_COOKIE_SECURE = True` en producción (cambio nuevo)
- `CSRF_COOKIE_SECURE = True` en producción (verificar)

## 15. Tests

`accounts/tests/`:

- **`test_login_remember.py`**: form + view, expiración correcta según checkbox, creación de `UserSession`, AuditLog `login`, `is_pwa` desde POST.
- **`test_session_middleware.py`**: sliding window solo para `remembered=True`, actualización de `last_seen_at`, throttle de 60s, robustez ante sesiones huérfanas y requests anónimos.
- **`test_user_sessions_view.py`**: GET muestra solo sesiones propias, sesión actual marcada, `revoke_session` valida ownership y rechaza la propia, `revoke_others` cubre el resto, AuditLog registrado.
- **`test_password_invalidation.py`**: cambio voluntario cierra otras y mantiene actual; reset por email cierra todas; cambio forzado equivalente al voluntario; signal `post_save` borra `UserSession` en cambios desde admin.
- **`test_revoke_sessions_service.py`**: atomicidad, count correcto, AuditLog con `reason`, idempotencia, no-op con lista vacía.
- **`test_prune_user_sessions.py`**: borra huérfanas y antiguas, no toca válidas, reporta count.

## 16. Auditoría

`AuditLog` recibe entradas para:
- `login` (payload: `remembered`, `is_pwa`, `ip`).
- `sessions.revoked` (payload: `count`, `reason`).
- `password.change` (ya existe).
- `password_reset_completed` (ya existe).

No se hace una entrada por sesión revocada en cascada — una sola con `count=N`.

## 17. Riesgos aceptados

| Riesgo | Mitigación |
|---|---|
| Cookie de sesión robada (XSS, sniffing) | HttpOnly+Secure+SameSite=Lax. CSP estricto (verificar fuera de scope). Sin detección activa. |
| Robo detectado por el usuario | Lista "Mis sesiones" + botón cerrar. Cambio de contraseña invalida todo el resto. |
| Equipo compartido | Checkbox "Recordarme" desmarcable; al desmarcarlo, sesión termina al cerrar navegador. |
| Rotación de IP móvil | `ip_at_login` solo informativa, nunca validativa. |
| `UserSession` huérfanas | Cron `prune_user_sessions` + signal en `User.password`. |
| Race de `last_seen_at` | Throttle por session_key, `UPDATE` por PK, overwrites irrelevantes. |
| Login en PWA y luego en Safari del mismo dispositivo | Son sesiones distintas (cookies distintas); cada una con su flag `is_pwa` al login. |
| Reinicio de workers limpia el cache del throttle | El siguiente request por sesión tras restart sí actualiza DB; coste marginal. |

## 18. Fuera de scope

- 2FA / TOTP.
- SSO corporativo (Azure AD, Google Workspace).
- Selector+validator pattern con detección de robo por reuse.
- Step-up auth para operaciones sensibles.
- Geolocalización por IP en "Mis sesiones".
- Cambio de email en perfil (no existe hoy; cuando se añada deberá invocar `revoke_sessions` igual que un reset).

## 19. Plan de release

1. Worktree: `worktree-remember-me` desde `origin/main`.
2. Implementación por commits atómicos según `docs/superpowers/plans/`.
3. Tests verdes en CI.
4. PR contra `main`.
5. Merge → Railway despliega automáticamente desde `main`.
6. Smoke test en `laporradeljefe.es`: login con checkbox marcado, ver "Mis sesiones", revocar otra sesión, cambiar contraseña verifica que cierra otras.

## 20. Métricas de éxito

- Tras 7 días desde el deploy: ≥80% de logins con `remembered=True`.
- Ningún ticket de "no puedo entrar tras cambiar contraseña" causado por el flujo nuevo.
- Cron `prune_user_sessions` deja la tabla `UserSession` en cardinalidad estable (≈ usuarios × dispositivos activos).
