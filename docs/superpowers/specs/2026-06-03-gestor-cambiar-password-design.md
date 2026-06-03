# Diseño — Gestor puede cambiar la contraseña de un jugador

Fecha: 2026-06-03
Autor: brainstorming con Ignacio

## Objetivo

Permitir que un usuario con `is_gestor=True` establezca la contraseña de cualquier otro usuario (y, opcionalmente, la suya propia) tecleando una contraseña concreta — no solo generando una temporal aleatoria como hace hoy `pot.views.ResetPasswordView`.

Esto cubre el caso real "el jugador llama, dicta la contraseña que quiere usar, el gestor se la pone".

## Contexto actual

- `pot/views.py::ResetPasswordView` (POST `/jugadores/<pk>/reset/`) ya existe: genera una temporal aleatoria con `generate_temp_password()`, marca `must_change_password=True`, registra `AuditLog("password_reset")` y muestra la pwd una vez en `_password_reveal.html`. **No está expuesta en la UI** de `manage_players.html` (no hay botón que la dispare). Se queda como está: este diseño no la toca.
- `accounts/forms.py::ChangePasswordForm` valida las reglas del auto-cambio: `min_length=10`, mayúscula + dígito, dos campos que coinciden, y exige `current` (contraseña actual). Su `clean()` es lo que reutilizamos como referencia para las reglas — pero no podemos usar el form tal cual porque el gestor no conoce la pwd actual del jugador.
- `docs/DATA_MODEL.md` §5: *"No hay recuperación automática de contraseña. El restablecimiento lo hace un gestor."* Sigue siendo válido tras este cambio.
- `templates/core/rules.html:252-254`: *"Sin recuperación automática. Si la olvidas, un gestor te la restablece."* Sigue siendo válido sin cambios.

## Alcance

Dentro:
- Nueva vista `SetPasswordView` para que el gestor establezca contraseña de cualquier usuario.
- Nuevo form `SetPlayerPasswordForm` (sin campo `current`).
- Nuevo modal `_password_set_modal.html`.
- Botón nuevo en la tabla de jugadores con icono `lock`.
- Helper para generar contraseñas sugeridas que **garantizan** cumplir las reglas.
- Acción de auditoría nueva: `password_set_by_manager`.
- Tests cubriendo permisos, validación, auditoría y auto-cambio del gestor.

Fuera:
- Tocar `ResetPasswordView` o `PasswordRevealView`.
- Exponer un botón de "reset temporal aleatoria" en la UI (decisión separada).
- Endurecer reglas de contraseña globales (`ChangePasswordForm` se queda igual).

## UI

### Tabla de jugadores (`templates/pot/manage_players.html`)

En la columna de acciones de cada fila, **añadir un tercer botón** entre Editar y Activar/Baja:

```html
<button class="btn btn-ghost"
        data-modal-url="{% url 'pot:player_set_password' p.id %}"
        style="width:32px;height:32px;padding:0"
        title="Cambiar contraseña">
  {% icon "lock" width=14 %}
</button>
```

Orden final en la columna: `[Editar] [Contraseña] [Activar/Baja]`.

### Modal `templates/pot/_password_set_modal.html`

Misma estructura visual que `_player_modal.html` (clase `glass pop`, header con eyebrow + título + cierre, form, footer con Cancelar/Guardar).

Contenido:

- **Eyebrow**: "Contraseña"
- **Título**: "Nueva contraseña de **{{ player.name }}**"
- **Aviso `mono` en `surface-hi`**:
  - Si `player.id != request.user.id`: *"Se forzará al jugador a cambiarla en su próximo acceso."*
  - Si `player.id == request.user.id`: *"Estás cambiando tu propia contraseña. No se te pedirá cambiarla de nuevo."*
- **Campo "Nueva contraseña"** (`name="new1"`, `type="password"`, pre-rellenado con la sugerencia)
- **Campo "Repite la contraseña"** (`name="new2"`, `type="password"`, pre-rellenado con la misma sugerencia)
- **Fila bajo los inputs** con dos botones ghost pequeños:
  - **Sugerir otra**: `type="button"`, regenera vía fetch a `GET ?suggest=1` (o un endpoint dedicado — ver más abajo) y reescribe ambos inputs.
  - **Mostrar / Ocultar**: `type="button"`, alterna `type` de los inputs entre `password` y `text`.
- **Errores**: bajo cada campo en `<p style="color:var(--c-red);font-size:12px">`, igual que el modal de jugador.
- **Footer**: Cancelar (`data-modal-close`) + **Guardar contraseña** (primary).

### Mecanismo "Sugerir otra"

Para no complicar el JS, la solución más simple: la vista `GET` siempre devuelve el modal con la sugerencia inyectada. El botón "Sugerir otra" hace un fetch al mismo endpoint con `?suggest=1` y reemplaza el contenido del overlay (mismo patrón que el modal de alta cuando hay errores). El form mantiene su `value` con la sugerencia y el gestor edita encima si quiere.

Alternativa más simple aún (preferida): generar la sugerencia en JS en el cliente, sin round-trip. Pero entonces el helper de generación tiene que estar duplicado. **Resolución**: el primer render lo hace Python (mantiene una sola fuente de verdad para "qué cumple las reglas"); "Sugerir otra" reusa el endpoint con `?suggest=1` que devuelve un fragmento JSON `{"password": "..."}` y JS solo actualiza los `value` de los inputs. Pequeño endpoint adicional, JS mínimo.

## Backend

### Helper de generación (en `pot/forms.py`)

```python
def generate_suggested_password() -> str:
    """Devuelve una contraseña que SIEMPRE cumple las reglas del form."""
    # 12 chars: al menos 1 mayúscula, 1 minúscula, 1 dígito, resto random.
    # Implementación con `secrets.choice` desde alfabetos disjuntos y shuffle final.
```

`generate_temp_password()` se queda como está (lo usa `ResetPasswordView` y el alta).

### Form (`pot/forms.py`)

```python
class SetPlayerPasswordForm(forms.Form):
    new1 = forms.CharField(
        label="Nueva contraseña",
        min_length=10,
        widget=forms.PasswordInput(attrs={"class": "input"}, render_value=True),
    )
    new2 = forms.CharField(
        label="Repite la contraseña",
        min_length=10,
        widget=forms.PasswordInput(attrs={"class": "input"}, render_value=True),
    )

    def clean(self):
        c = super().clean()
        if c.get("new1") and c.get("new2") and c["new1"] != c["new2"]:
            raise forms.ValidationError("Las dos contraseñas no coinciden.")
        if c.get("new1"):
            pwd = c["new1"]
            if not any(ch.isupper() for ch in pwd) or not any(ch.isdigit() for ch in pwd):
                raise forms.ValidationError(
                    "La contraseña debe tener al menos una mayúscula y un dígito."
                )
        return c
```

No reusa `accounts.forms.ChangePasswordForm` porque ese exige `current`. La lógica de `clean()` es duplicada a propósito (dos validaciones distintas para dos roles distintos). Si en el futuro las reglas divergen — por ejemplo, el gestor debe usar reglas más estrictas — esto ya está separado.

### Vista (`pot/views.py`)

```python
class SetPasswordView(GestorRequiredMixin, View):
    def _is_modal(self, request) -> bool:
        return request.headers.get("X-Modal") == "1"

    def get(self, request, pk):
        player = get_object_or_404(User, pk=pk)
        if request.GET.get("suggest") == "1":
            return JsonResponse({"password": generate_suggested_password()})
        suggested = generate_suggested_password()
        form = SetPlayerPasswordForm(initial={"new1": suggested, "new2": suggested})
        return render(
            request,
            "pot/_password_set_modal.html",
            {"form": form, "player": player, "is_self": player.id == request.user.id,
             "modal": self._is_modal(request)},
        )

    def post(self, request, pk):
        player = get_object_or_404(User, pk=pk)
        form = SetPlayerPasswordForm(request.POST)
        if not form.is_valid():
            response = render(
                request,
                "pot/_password_set_modal.html",
                {"form": form, "player": player, "is_self": player.id == request.user.id,
                 "modal": self._is_modal(request)},
            )
            if self._is_modal(request):
                response["X-Modal-Errors"] = "1"
            return response

        is_self = player.id == request.user.id
        player.set_password(form.cleaned_data["new1"])
        player.must_change_password = not is_self
        player.save(update_fields=["password", "must_change_password"])
        if is_self:
            update_session_auth_hash(request, player)
        AuditLog.objects.create(
            actor=request.user,
            action="password_set_by_manager",
            target_type="user",
            target_id=str(player.id),
            payload={"self": is_self},
        )
        messages.success(request, "Contraseña actualizada.")
        target = reverse("pot:manage_players")
        if self._is_modal(request):
            response = HttpResponse(status=200)
            response["X-Modal-Redirect"] = target
            return response
        return redirect(target)
```

`PasswordInput` por defecto no re-renderiza su `value` por seguridad. En este modal **sí queremos** re-renderizarlo cuando hay errores de validación para no perder lo que tecleó el gestor. Solución: pasar `render_value=True` al widget en el form, o renderizar manualmente el `value` en la plantilla. **Decisión**: `render_value=True` en el widget del form — más simple y centralizado.

### URL (`pot/urls.py`)

```python
path("jugadores/<int:pk>/contrasena/",
     views.SetPasswordView.as_view(),
     name="player_set_password"),
```

## Auditoría

| Acción | Cuándo | Notas |
|--------|--------|-------|
| `password.change` | Usuario cambia su propia pwd vía `MyAccountView` | Ya existe |
| `password_reset` | Gestor genera temporal aleatoria vía `ResetPasswordView` | Ya existe |
| **`password_set_by_manager`** | **Gestor establece pwd concreta vía `SetPasswordView`** | **Nueva.** `payload={"self": bool}` para distinguir auto-cambio |

## Permisos y casos borde

- `GestorRequiredMixin` cubre el acceso. Un no-gestor recibe lo que ya devuelva el mixin (redirect/403, consistente con las otras vistas del módulo `pot`).
- **Auto-cambio del gestor**: permitido. `must_change_password=False` y `update_session_auth_hash` para no cerrarle la sesión.
- **Gestor cambia pwd de otro gestor**: permitido sin distinción especial. La auditoría queda registrada.
- **POST a pk inexistente**: 404 por `get_object_or_404`.
- **GET con `?suggest=1`**: devuelve solo JSON, ignora el `pk` salvo para el permiso (sigue requiriendo `GestorRequiredMixin` y un `pk` válido).
- **Sin CSRF**: el form POST lleva `{% csrf_token %}` como el resto de modales.

## Tests (`pot/tests/test_set_password.py`)

1. **`test_get_requires_gestor`**: jugador no-gestor recibe redirect/403.
2. **`test_get_renders_modal_with_suggestion`**: GET como gestor devuelve modal; los inputs `new1`/`new2` traen un valor pre-rellenado que cumple las reglas (≥10, upper, digit).
3. **`test_get_suggest_returns_json`**: `GET ?suggest=1` devuelve `application/json` con una pwd que cumple las reglas.
4. **`test_post_valid_changes_password`**: POST válido → `check_password` cambia, `must_change_password=True`, queda 1 `AuditLog` con `action="password_set_by_manager"` y `payload={"self": False}`.
5. **`test_post_self_does_not_force_change`**: POST del gestor sobre su propio pk → `must_change_password=False`, sesión sigue activa (verificar con `client.get` a otra vista protegida tras el POST), auditoría con `payload={"self": True}`.
6. **`test_post_mismatch_passwords`**: pwds distintas → modal re-renderizado con error, `X-Modal-Errors: 1`, pwd del usuario NO cambia.
7. **`test_post_no_uppercase`**: pwd `abcdefghij1` (10 chars, dígito, sin mayúscula) → error.
8. **`test_post_short`**: pwd con 9 chars → error de `min_length`.
9. **`test_post_redirects_via_x_modal_redirect`**: respuesta tras éxito incluye `X-Modal-Redirect: /pot/jugadores/`.

## Cambios fuera del código

- **Página de Reglas (`templates/core/rules.html`)**: revisar y confirmar que el copy actual sigue siendo cierto. Spoiler: lo es — "un gestor te la restablece" cubre tanto el reset aleatorio como el set personalizado. **No requiere cambios.**
- **`docs/DATA_MODEL.md` §5**: igual, no requiere cambios.
- **`docs/PLAN.md`**: si hay una fase de "gestión de jugadores", añadir mención. (Verificar al implementar.)

## Archivos afectados (resumen)

| Archivo | Acción |
|---------|--------|
| `pot/urls.py` | + 1 ruta |
| `pot/views.py` | + 1 vista (`SetPasswordView`) |
| `pot/forms.py` | + 1 form, + 1 helper `generate_suggested_password` |
| `templates/pot/manage_players.html` | + 1 botón en columna acciones |
| `templates/pot/_password_set_modal.html` | nuevo |
| `pot/tests/test_set_password.py` | nuevo |
| `docs/PLAN.md` | verificar y, si procede, añadir línea |

## Decisiones tomadas durante el brainstorming

- Contraseña personalizada (no solo reset aleatorio).
- Forzar `must_change_password` para terceros; no forzarlo si el gestor se cambia la suya.
- Acción separada en la tabla de jugadores (no embebida en el modal de Editar).
- Misma política de reglas que el auto-cambio (≥10, mayúscula, dígito).
- Pre-rellenar el modal con una sugerencia que ya cumple las reglas; permitir regenerarla.
- Auditoría con acción nueva `password_set_by_manager` (distinta de `password_reset`).
