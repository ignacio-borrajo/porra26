# Toggle de orden en vista de Jornadas — Por fecha / Por grupos

Fecha: 2026-06-06 (v2: 2026-06-06)
Estado: aprobado

## Motivación

En la pantalla de Competición, dentro de la ronda **Grupos**, los partidos se listan agrupados por estado (Abiertos / En juego / Finalizados) y dentro de cada bloque ordenados por kickoff. Esta vista es buena para "qué viene ahora", pero pierde el sentido competitivo de la fase de grupos: a veces el jugador piensa "¿cómo va el Grupo C?" y no "¿qué se juega esta tarde?".

Añadir un toggle **Por fecha / Por grupos** permite alternar entre las dos lecturas sin perder ninguna funcionalidad.

## Alcance

**Aplica a:** la ronda **Grupos** (`round_id="groups"`) dentro de la vista de Competición (`CompetitionView`, `templates/competition/dashboard.html`).

**No aplica a:**
- Rondas KO (`r32`, `r16`, `qf`, `sf`, `final`) — esas rondas renderizan `_ko_canvas.html` (bracket), no la lista de cards. El toggle no se muestra en KO.
- Otras vistas que reutilicen `_match_card.html` (manage_results, etc.). El toggle se incluye explícitamente en `dashboard.html`, no en el partial de card.

El **selector de jornadas** (J1/J2/J3) sigue activo en ambos modos del toggle. El toggle solo afecta a la agrupación de las cards dentro de la jornada seleccionada.

## Comportamiento

Ambos modos comparten estructura: dentro de cada bloque de estado (ABIERTOS / EN JUEGO / FINALIZADOS) se inyectan **sub-headers** que agrupan visualmente las cards. Solo cambia la clave de agrupación.

### Modo "Por fecha" (default)

- Sub-headers por día con formato "Viernes 12 junio" (`Intl.DateTimeFormat('es-ES', { weekday, day, month })`).
- Dentro de cada sub-grupo, cards ordenadas por `kickoff` ascendente.

### Modo "Por grupos"

- Sub-headers "Grupo A", "Grupo B", …, "Grupo L" alfabéticamente.
- Dentro de cada sub-grupo, cards ordenadas por `kickoff` ascendente.
- Empate de grupo (mismo grupo en el mismo bloque de estado) → desempate por `kickoff` ascendente.

### Persistencia

- Clave `localStorage`: `porra26:matchesOrder`, valores `"date"` (default) o `"group"`.
- Si no hay valor guardado o el valor es desconocido → se asume `"date"`.
- El cambio es **puramente en cliente**, sin recarga ni round-trip al servidor.

### Visibilidad del toggle

El toggle se renderiza si y solo si:
- `active_round == "groups"` (no se pinta en KO).
- Hay al menos un partido visible en la jornada activa (no se pinta en pantalla vacía).

## UI

Segmented control glass con dos botones `chip`. En **PC** queda en la misma fila que el selector de jornada (J1/J2/J3), empujado a la derecha con `margin-left:auto`. En **móvil** baja a la línea inferior gracias a `flex-wrap`.

```
[Grupos · 3p] [Octavos · 7p] ...
[J1] [J2] [J3]                  [● Por fecha · Por grupos]

ABIERTOS · 4
Viernes 12 junio
┌ … ┐ ┌ … ┐
Sábado 13 junio
┌ … ┐ ┌ … ┐

EN JUEGO · 1
Domingo 14 junio
┌ … ┐
```

Dos `<button>` con `aria-pressed="true|false"` y `data-order="date|group"`. El activo lleva `chip-open` (mismo tratamiento que J1 activo). El contenedor padre lleva clase `matches-order-toggle`.

## Implementación

Cambios mínimos, sub-headers construidos en cliente para no duplicar HTML server-side.

### Templates

- **`templates/competition/_match_card.html`**: añadir atributos `data-group` y `data-kickoff` (ISO 8601, `kickoff|date:'c'`) al elemento raíz de cada card.
- **`templates/partials/_matches_order_toggle.html`** (nuevo): markup del segmented control sin margen propio.
- **`templates/partials/_matchday_selector.html`**: quitar `margin-top:10px` (lo asume el wrapper).
- **`templates/competition/manage_results.html`**: envolver el include del matchday_selector con un `<div style="margin-top:10px">` para preservar el espaciado original.
- **`templates/competition/dashboard.html`**: wrap del matchday_selector + toggle en un `<div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap;margin-top:10px">`. Toggle dentro de un sub-div con `margin-left:auto`.

### JS

- **`static/js/matches-order.js`** (nuevo, módulo ES):
  1. Al cargar el DOM, lee `localStorage.getItem('porra26:matchesOrder')` (default `"date"`).
  2. Para cada `.matches-grid`: vacía el contenedor y reinserta cards intercaladas con `<h3 class="eyebrow matches-subgroup-header">` (con `grid-column:1/-1` para abarcar toda la fila del grid auto-fill). La clave de agrupación y la etiqueta se calculan según el modo:
     - `date`: clave `YYYY-MM-DD` (slice del ISO), etiqueta `Intl.DateTimeFormat('es-ES', { weekday, day, month })` con primera letra capitalizada.
     - `group`: clave `1{letra}` para grupos de 1 char (A→L) y `2{...}` para etiquetas largas, etiqueta `Grupo {letra}` o la propia etiqueta si es larga.
  3. Bindea click en los dos botones del toggle → guarda en localStorage y vuelve a aplicar el modo.
  4. El módulo se carga desde `dashboard.html` con `<script type="module" src="{% static 'js/matches-order.js' %}">` solo cuando `not is_ko_view`.

Si el navegador no soporta localStorage o falla por modo privado, el módulo cae a "date" silenciosamente.

### CSS

- Reutilizar clases existentes (`glass`, `chip`, `chip-open`, `eyebrow`). Los sub-headers usan `.eyebrow` + estilos inline (`grid-column:1/-1;margin:10px 0 -2px;font-size:11px;opacity:.7`).
- No se introduce hoja de estilos nueva.

## Accesibilidad

- `<nav aria-label="Orden de los partidos">` envolviendo los botones.
- Botones con `aria-pressed="true|false"`.
- Los sub-headers son `<h3>`, navegables por screen reader como puntos de orientación adicionales dentro de cada bloque de estado.

## Lo que NO entra

- Mini-tabla de clasificación del grupo dentro de la card (idea futura, requiere standings en vivo).
- Vista "todas las jornadas mezcladas" (otro feature).
- Animación de reordenado (FLIP/morph).
- Persistencia por usuario en backend. Cookie/localStorage por dispositivo es suficiente.
- Toggle en otras vistas (manage_results, KO, etc.).

## Tests

- **Unit (Django)**: tests existentes verifican que `data-group`, ambos `data-order` y `matches-order.js` aparecen en el render de Grupos, y que ninguno aparece en KO. No se añade lógica nueva en backend.
- **Manual**: en `?round=groups&matchday=1`, alternar el toggle y comprobar que aparecen los sub-headers correctos en cada modo y que el estado persiste tras recargar.
