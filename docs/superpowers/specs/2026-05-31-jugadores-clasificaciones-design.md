# Diseño · Roles, perfil organizativo y rankings por grupo

Fecha: 2026-05-31
Estado: aprobado por el usuario, pendiente de plan de implementación.

## Contexto y motivación

Hoy `accounts.User` tiene un único campo `role` (`jugador` | `gestor`) y un `dept` libre. Esto impide:

- Distinguir a los administradores de Django (que no deben aparecer en clasificaciones ni listas de juego) de los jugadores reales.
- Tener gestores que no participen como jugadores y viceversa de forma natural.
- Agrupar a los jugadores por dimensiones organizativas (sede, puesto, departamento) y publicar rankings agregados.

Además, la gestión de jugadores tiene problemas de UX: el alta/edición se abre como página completa y no como modal, y el formulario no respeta la estética del prototipo (`design-reference/manage.jsx`).

## Alcance

1. Sustituir el campo `role` por dos flags independientes (`is_jugador`, `is_gestor`).
2. Convertir `dept` en enum y añadir dos enums nuevos: `sede` y `puesto`.
3. Permitir al propio jugador editar su perfil (nombre, departamento, sede, puesto).
4. Convertir el formulario de jugador en un overlay modal real con el estilo del prototipo.
5. Añadir una página nueva "Rankings" con tres pestañas (Sede, Puesto, Departamento) que muestre total y media de puntos por grupo.

Fuera de alcance: rediseñar la pantalla de estadísticas, premios por grupo, exportaciones, notificaciones.

## 1. Modelo de datos (`accounts.User`)

### Cambios

| Campo | Antes | Después | Notas |
|-------|-------|---------|-------|
| `role` | `CharField` (jugador/gestor) | **eliminado** | Migrado a los dos flags. |
| `is_jugador` | — | `BooleanField(default=True)` | Aparece en clasificaciones y puede pronosticar. |
| `is_gestor` | — | `BooleanField(default=False)` | Acceso a Jugadores, Resultados, Premios, Auditoría. |
| `dept` | `CharField(max_length=80, blank=True)` libre | `CharField(max_length=20, choices=DEPT_CHOICES, blank=True)` | Choices fijas; valores libres no coincidentes se vacían en la migración. |
| `sede` | — | `CharField(max_length=20, choices=SEDE_CHOICES, blank=True)` | Nuevo. |
| `puesto` | — | `CharField(max_length=20, choices=PUESTO_CHOICES, blank=True)` | Nuevo. |

### Enums

```python
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
```

Las cuatro combinaciones de flags son válidas:

| `is_jugador` | `is_gestor` | Caso |
|:---:|:---:|---|
| ✓ | ✗ | Jugador estándar. |
| ✓ | ✓ | Gestor que también juega. |
| ✗ | ✓ | Gestor puro (no participa en clasificaciones, no puede pronosticar). |
| ✗ | ✗ | Usuario administrativo / staff de Django; invisible en juego. |

### Migración (`accounts.0003_role_split_and_org_fields`)

Una sola migración con dos operaciones:

1. **Schema**: añade los tres campos nuevos y deja `dept` como `CharField(max_length=20, blank=True)` sin choices todavía.
2. **Data migration**:
   - Para cada `User`: `is_gestor = (role == 'gestor')`; `is_jugador = (not is_superuser)`. Así los superusers de Django quedan invisibles automáticamente y el resto siguen apareciendo como hasta ahora.
   - Si `dept` actual no está en `{Nóminas, Gestión, Financiera, Pesca}` (case-insensitive), se vacía. Si coincide (ignorando mayúsculas), se normaliza al `key` correspondiente (`nominas`, `gestion`, ...).
3. **Schema final**: aplica `choices` a `dept` y elimina la columna `role`.

La migración es atómica. El backfill respeta el comportamiento actual: los gestores siguen siendo gestores, todos los demás siguen siendo jugadores.

### Refactor de referencias

| Archivo | Cambio |
|---|---|
| `accounts/managers.py` | `create_user` setea `is_jugador=True`; `create_superuser` setea `is_jugador=False, is_gestor=False` (admin puro fuera del juego). |
| `accounts/mixins.py` | `RoleRequiredMixin` → `GestorRequiredMixin` (sin parámetro `required_role`); chequea `request.user.is_gestor`. |
| `accounts/tests/factories.py` | Reemplaza `role = "jugador"` por `is_jugador = True`; el factory de gestor pone `is_gestor = True, is_jugador = True`. |
| `competition/views.py` `PredictView` | `if not request.user.is_jugador: raise PermissionDenied`. |
| `competition/views.py` `ManageResultsView`, `ResultOfficialView` | Hereda `GestorRequiredMixin`. |
| `competition/services/standings.py` | Filtro `is_jugador=True, is_active=True` (antes solo `is_active`). |
| `pot/forms.py` | `PlayerForm.Meta.fields = ["name", "email", "dept", "sede", "puesto", "is_jugador", "is_gestor"]`. |
| `pot/views.py` | Todas las vistas extienden `GestorRequiredMixin`. |
| `templates/partials/_topbar.html` | `{% if user.is_gestor %}` en lugar de `user.role == 'gestor'`. |
| Tests | Se actualizan asserts de `role` y se añaden casos para combinaciones de flags. |

## 2. Modal real de alta/edición de jugador

### Pieza JS reutilizable

`static/js/modal.js` (módulo nuevo, ~40 líneas):

```js
export async function openModal(url) {
  const res = await fetch(url, { headers: { "X-Modal": "1" } });
  const html = await res.text();
  mount(html);
}
export function closeModal() { /* unmount + remove listeners */ }
```

Comportamiento:

- Inyecta el HTML devuelto dentro de un `<div class="ovl">` añadido al `<body>`.
- Cierra con `Escape`, clic fuera de la tarjeta `.glass`, o submit/cancel del formulario.
- Intercepta el submit del formulario interno, hace `fetch(method=POST)` con el `FormData`:
  - Respuesta `2xx` con header `X-Modal-Redirect` → `window.location = header`.
  - Respuesta `2xx` sin redirect → cierra modal + recarga la lista (`window.location.reload()`).
  - Respuesta `200` con `X-Modal-Errors: 1` → re-monta el fragmento devuelto in-place (errores de validación).
- Activado por delegación: cualquier `<a data-modal-url>` o `<button data-modal-url>` abre la modal con esa URL.

Carga global en `base.html` (un solo `<script type="module">`).

### Vistas

`PlayerFormView` cambia mínimamente:

- GET: si el request trae `X-Modal: 1`, renderiza el fragmento sin `extends "base.html"`; si no, renderiza la página completa (fallback no-JS).
- POST nuevo jugador: responde 200 con header `X-Modal-Redirect: {url_de_password_reveal}` y body vacío. La contraseña temporal sigue mostrándose en su página propia (es información sensible y no encaja dentro de una modal).
- POST edición OK: responde 200 con header `X-Modal-Redirect: {url_manage_players}`.
- POST con errores: responde 200 con header `X-Modal-Errors: 1` y body = fragmento del formulario con los errores renderizados.

### Plantilla `templates/pot/_player_modal.html`

Fragmento (no extiende base.html):

```html
<section class="glass pop" style="width:min(520px,100%);border-radius:28px;padding:28px;background:var(--surface-solid)">
  <header style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <div>
      <span class="eyebrow">{% if player %}Editar{% else %}Alta{% endif %}</span>
      <h2 class="display" style="margin:6px 0 0;font-size:22px">{% if player %}{{ player.name }}{% else %}Nuevo jugador{% endif %}</h2>
    </div>
    <button type="button" data-modal-close class="btn btn-ghost" style="width:38px;height:38px;padding:0;border-radius:12px">{% icon "x" width=16 %}</button>
  </header>
  <form method="post" action="{% if player %}{% url 'pot:player_edit' player.id %}{% else %}{% url 'pot:player_new' %}{% endif %}">
    {% csrf_token %}
    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="field"><label>Nombre completo</label>{{ form.name }}</div>
      <div class="field"><label>Correo corporativo (usuario)</label>{{ form.email }}</div>
      <div style="display:grid;grid-template-columns:1fr 1fr;gap:12px">
        <div class="field"><label>Departamento</label>{{ form.dept }}</div>
        <div class="field"><label>Puesto</label>{{ form.puesto }}</div>
      </div>
      <div class="field"><label>Sede</label>{{ form.sede }}</div>
      <div style="display:flex;gap:18px;padding:10px 0">
        <label class="check"><input type="checkbox" name="is_jugador" {% if form.instance.is_jugador|default_if_none:True %}checked{% endif %}> Es jugador</label>
        <label class="check"><input type="checkbox" name="is_gestor" {% if form.instance.is_gestor %}checked{% endif %}> Es gestor</label>
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
```

### Lista `templates/pot/manage_players.html`

- El botón "Nuevo jugador" deja de ser un `<a href>` y pasa a ser `<button data-modal-url="{% url 'pot:player_new' %}">`.
- Cada icono de "Editar" pasa a `<button data-modal-url="{% url 'pot:player_edit' p.id %}">`.
- La columna "Departamento" se ensancha y muestra tres líneas pequeñas: `dept · sede · puesto` (usando los `get_<x>_display`), separadas por `·`, con texto faint si vacío.
- La columna "Jugador" añade chips inline:
  - Chip `gestor` (cian, fontSize 9) cuando `is_gestor`.
  - Chip `no juega` (faint) cuando `not is_jugador`.

### CSS adicional (`static/css/styles.css`)

```css
.ovl {
  position: fixed; inset: 0; z-index: 60;
  display: grid; place-items: center; padding: 20px;
  background: oklch(0.1 0.03 280 / 0.6);
  backdrop-filter: blur(8px);
  animation: fade .25s ease both;
}
select.input {
  appearance: none;
  /* chevron SVG inline en `currentColor`-faint, alineado al borde derecho */
  background-image: url("data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='12' height='8' viewBox='0 0 12 8' fill='none' stroke='%23888' stroke-width='1.8' stroke-linecap='round' stroke-linejoin='round'><polyline points='1 1.5 6 6.5 11 1.5'/></svg>");
  background-repeat: no-repeat;
  background-position: right 14px center;
  padding-right: 36px;
}
.check {
  display: inline-flex; align-items: center; gap: 8px;
  font-size: 13px; font-weight: 600; color: var(--text);
  cursor: pointer;
}
.check input[type="checkbox"] {
  width: 18px; height: 18px; accent-color: var(--accent);
}
```

## 3. Auto-edición del jugador ("Mi perfil")

### Vista y URL

- `accounts/views.py` `ProfileView(LoginRequiredMixin, View)`.
- `accounts/urls.py`: `path("perfil/", ProfileView.as_view(), name="profile")`.

### Form

```python
class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ["name", "dept", "sede", "puesto"]
```

No expone `email`, `is_jugador`, `is_gestor`. La contraseña se cambia desde la pantalla existente.

### Plantilla `templates/accounts/profile.html`

Tarjeta `.glass` centrada, ancho máx. 520px, con los mismos `field/input` que el resto del proyecto. Encabezado eyebrow "TU CUENTA" + título "Mi perfil". Botón secundario "Cambiar contraseña" que enlaza a `accounts:change_password`. Botón primario "Guardar". Tras guardar: toast "Perfil actualizado" + redirect al propio perfil.

### Topbar

El bloque actual del avatar + nombre + rol se envuelve en `<a href="{% url 'accounts:profile' %}">` (hoy es `<div>` plano). El texto `{{ user.role }}` debajo del nombre se sustituye por chips dinámicos: `Jugador` (lima) y/o `Gestor` (cian), según flags.

## 4. Página "Rankings"

### Navegación

Nuevo item en `templates/partials/_topbar.html`, entre *Estadísticas* y los items de gestor, visible para todos los autenticados:

```html
<a href="{% url 'stats:rankings' %}" class="nav-item{% if url_name == 'rankings' %} is-active{% endif %}">
  {% icon "trophy" width=17 height=17 %} Rankings
</a>
```

### Servicio `stats/services/group_standings.py`

```python
@dataclass
class GroupRow:
    key: str         # 'ourense' | '__none__' para "Sin asignar"
    label: str       # 'Ourense' | 'Sin asignar'
    players: int     # nº de jugadores activos+is_jugador en el grupo
    total: int       # suma de earned
    avg: float       # total / players, 0 si players==0
    top_name: str    # líder del grupo (vacío si no hay)
    top_pts: int

DIMENSIONS = {
    "sede":   ("sede",   SEDE_CHOICES),
    "puesto": ("puesto", PUESTO_CHOICES),
    "dept":   ("dept",   DEPT_CHOICES),
}

def group_standings(dimension: str) -> list[GroupRow]:
    """Agrega standings por la dimensión organizativa indicada."""
```

Implementación:

1. Recupera la lista completa de `standings()` ya filtrada por `is_jugador=True, is_active=True` y carga `User` con los tres campos (`only`) en un dict `{user_id: user}`.
2. Recorre standings una sola vez agrupando por `getattr(user, dimension) or "__none__"` y acumulando `total`, contando jugadores y guardando el primero (mayor `pts`) como líder.
3. Garantiza una entrada por cada `choice` aunque tenga 0 jugadores (visible pero atenuada).
4. La fila `__none__` ("Sin asignar") siempre va al final, con `opacity:0.55`.
5. Orden: `(-avg, -total, label.lower())`.

Coste: una query agregada del standings (ya existe) + una query `User.objects.in_bulk` para los jugadores. O(n) en jugadores. Sin N+1.

### Vista `RankingsView(LoginRequiredMixin)`

```python
class RankingsView(LoginRequiredMixin, View):
    VALID_TABS = {"sede", "puesto", "dept"}

    def get(self, request):
        tab = request.GET.get("tab", "sede")
        if tab not in self.VALID_TABS:
            tab = "sede"
        rows = group_standings(tab)
        my_group = getattr(request.user, tab, "") or "__none__"
        return render(request, "stats/rankings.html", {
            "tab": tab,
            "rows": rows,
            "my_group": my_group,
        })
```

URL: `path("rankings/", RankingsView.as_view(), name="rankings")` en `stats/urls.py` (URL final: `/estadisticas/rankings/`).

### Plantilla `templates/stats/rankings.html`

```
header rise:
  eyebrow "MUNDIAL 2026"
  h1 "Rankings por equipo"
  subtítulo: "Compara qué sede, puesto o departamento puntúa más en la porra."

tabs rise (.glass pill bar):
  <a tab=sede>   Sede
  <a tab=puesto> Puesto
  <a tab=dept>   Departamento
  (chip activo con degradado de acento)

glass card (radio 22, overflow hidden):
  cabecera grid (60px 1fr 100px 110px 110px 1.6fr):
    #  ·  Grupo  ·  Jugadores  ·  Total  ·  Media  ·  Líder
  filas stagger (mismas columnas):
    <li class="row {% if r.key == my_group %}row-me{% endif %} {% if r.key == '__none__' %}row-none{% endif %}">
      chip posición (1=oro, 2=plata, 3=bronce, resto ghost)
      <strong>{{ r.label }}</strong>
      <span class="mono">{{ r.players }}</span>
      <span class="mono">{{ r.total }} pts</span>
      <span class="display" style="font-size:22px">{{ r.avg|floatformat:1 }}</span>
      <div> avatar pequeño + nombre líder + chip mono "N pts" </div>

  empty state si no hay jugadores en ninguna dimensión.
```

Reglas visuales:

- `row-me`: `background: oklch(from var(--accent) l c h / 0.12)`.
- `row-none`: `opacity: 0.55`.
- El podio (top 3) usa los colores `--c-gold`, `--c-cyan`, `--c-pink` en el chip de posición, manteniendo la estética multicolor del prototipo.
- En tema claro se reutilizan los tokens existentes — no hay color hardcodeado.

## 5. Tests

- `accounts/tests/test_user_model.py`: combinaciones de flags, defaults, migración de `role`.
- `accounts/tests/test_profile_view.py`: ProfileView GET/POST, no permite cambiar email ni flags.
- `pot/tests/test_player_form.py`: validación de los nuevos campos, defaults sensatos de los flags.
- `pot/tests/test_modal_views.py`: GET con `X-Modal: 1` devuelve fragmento; POST devuelve `X-Modal-Redirect`; POST inválido devuelve `X-Modal-Errors`.
- `competition/tests/test_standings.py`: que un user con `is_jugador=False` no aparece, aunque tenga predicciones.
- `competition/tests/test_predict_view.py`: que un gestor puro (`is_jugador=False`) recibe 403 al intentar pronosticar.
- `stats/tests/test_group_standings.py`: agregaciones correctas (suma, media, líder), `Sin asignar` agrupa los huérfanos, orden estable, choices sin miembros aparecen vacíos.
- `stats/tests/test_rankings_view.py`: las tres tabs, fallback a "sede", highlight de `my_group`.

## 6. Resumen de archivos

| Archivo | Acción |
|---|---|
| `accounts/models.py` | modificar |
| `accounts/managers.py` | modificar |
| `accounts/mixins.py` | modificar (renombrar mixin) |
| `accounts/forms.py` | añadir `ProfileForm` |
| `accounts/views.py` | añadir `ProfileView` |
| `accounts/urls.py` | añadir ruta perfil |
| `accounts/migrations/0003_role_split_and_org_fields.py` | **nuevo** |
| `accounts/tests/*` | actualizar y ampliar |
| `pot/forms.py` | nuevos campos |
| `pot/views.py` | extender `GestorRequiredMixin`, responder headers de modal |
| `pot/tests/*` | actualizar y ampliar |
| `templates/pot/manage_players.html` | botón modal, chips, columna |
| `templates/pot/_player_modal.html` | reescribir como fragmento |
| `templates/accounts/profile.html` | **nuevo** |
| `templates/partials/_topbar.html` | item Rankings, avatar enlazable, chips de rol |
| `templates/stats/rankings.html` | **nuevo** |
| `competition/services/standings.py` | filtro `is_jugador` |
| `competition/views.py` `PredictView` | guard `is_jugador` |
| `stats/services/group_standings.py` | **nuevo** |
| `stats/views.py` | añadir `RankingsView` |
| `stats/urls.py` | añadir ruta rankings |
| `stats/tests/*` | nuevos tests |
| `static/js/modal.js` | **nuevo** |
| `static/css/styles.css` | `.ovl`, `select.input`, `.check` |
| `docs/DATA_MODEL.md` | actualizar tabla Player y reglas de auth/roles |

Sin nuevas dependencias. Una sola migración. Sin htmx ni librerías de UI.

## 7. Riesgos y mitigaciones

- **Pérdida de valores libres en `dept`**: los valores que no encajen con las nuevas choices se vacían. Asumido (el usuario validó que pasamos a enum); queda registrado en el changelog de la migración.
- **Usuarios sin Sede/Puesto en rankings**: aparecen en la fila "Sin asignar" para no perder visibilidad. El propio jugador los puede rellenar desde "Mi perfil".
- **Compatibilidad sin JS**: las vistas de modal siguen funcionando como página completa si el cliente no carga `modal.js` (fallback a `extends "base.html"` cuando no llega el header `X-Modal: 1`). Hoy el proyecto ya carga JS para el tema y los toasts, así que el caso "sin JS" es marginal pero está cubierto.
- **Migración no reversible**: la operación de borrar `role` es irreversible en producción. La migración incluye `RunPython.noop` como `reverse_code` con un comentario explicando que no se restaura el valor original.
