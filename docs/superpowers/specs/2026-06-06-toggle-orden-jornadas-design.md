# Toggle de orden en vista de Jornadas — Por fecha / Por grupos

Fecha: 2026-06-06
Estado: aprobado

## Motivación

En la pantalla de Competición, dentro de la ronda **Grupos**, los partidos se listan agrupados por estado (Abiertos / En juego / Finalizados) y dentro de cada bloque ordenados por kickoff. Esta vista es buena para "qué viene ahora", pero pierde el sentido competitivo de la fase de grupos: a veces el jugador piensa "¿cómo va el Grupo C?" y no "¿qué se juega esta tarde?".

Añadir un toggle **Por fecha / Por grupos** permite alternar entre las dos lecturas sin perder ninguna funcionalidad.

## Alcance

**Aplica a:** la ronda **Grupos** (`round_id="groups"`) dentro de la vista de Competición (`CompetitionView`, `templates/competition/dashboard.html`).

**No aplica a:**
- Rondas KO (`r32`, `r16`, `qf`, `sf`, `final`) — esas rondas renderizan `_ko_canvas.html` (bracket), no la lista de cards. El toggle no se muestra en KO.
- Otras vistas que reutilicen `_match_card.html` (manage_results, etc.). El toggle se incluye explícitamente en `dashboard.html`, no en el partial de card.

El **selector de jornadas** (J1/J2/J3) sigue activo en ambos modos del toggle. El toggle solo afecta al orden de las cards dentro de la jornada seleccionada.

## Comportamiento

### Modo "Por fecha" (default)

Idéntico al comportamiento actual:
- Tres bloques con header eyebrow: ABIERTOS · N, EN JUEGO · N, FINALIZADOS · N.
- Dentro de cada bloque, cards ordenadas por `kickoff` ascendente.

### Modo "Por grupos"

- Se mantienen los tres bloques de estado con sus headers eyebrow (ABIERTOS / EN JUEGO / FINALIZADOS).
- Dentro de cada bloque, las cards se ordenan **alfabéticamente por grupo** (A, B, C, …, L).
- Empate de grupo (mismo grupo en el mismo bloque de estado) → desempate por `kickoff` ascendente.
- Cada card sigue siendo el `match-card` actual, sin cambios visuales internos — su propio eyebrow ya muestra "Grupo X".

### Persistencia

- Clave `localStorage`: `porra26.matchesOrder`, valores `"date"` (default) o `"group"`.
- Si no hay valor guardado o el valor es desconocido → se asume `"date"`.
- El cambio es **puramente en cliente**, sin recarga ni round-trip al servidor.

### Visibilidad del toggle

El toggle se renderiza si y solo si:
- `active_round == "groups"` (no se pinta en KO).
- Hay al menos un partido visible en la jornada activa (no se pinta en pantalla vacía).

## UI

Segmented control en estilo glass, alineado a la derecha encima del primer bloque de partidos. Misma estética que los chips existentes (clases `chip` / `chip-open`).

```
[Grupos · 3p] [Octavos · 7p] ...
[J1] [J2] [J3]

                              ┌────────────────────────┐
                              │ ● Por fecha │ Por grupos │
                              └────────────────────────┘

ABIERTOS · 4
┌ … ┐ ┌ … ┐ ┌ … ┐ ┌ … ┐

EN JUEGO · 1
┌ … ┐

FINALIZADOS · 7
┌ … ┐ ┌ … ┐ ┌ … ┐ ...
```

Dos `<button>` con `aria-pressed="true|false"` y `data-order="date|group"`. El activo lleva `chip-open` (mismo tratamiento que J1 activo). El contenedor padre lleva clase `matches-order-toggle`.

## Implementación

Cambios mínimos, todo cliente.

### Templates

- **`templates/competition/_match_card.html`**: añadir atributos `data-group` y `data-kickoff` al elemento raíz de cada card (tanto en la rama `pending_teams` como en la rama normal). `data-kickoff` usa `kickoff|date:'c'` (ISO 8601) para `localeCompare` lexicográfico fiable.
- **`templates/partials/_matches_order_toggle.html`** (nuevo): markup del segmented control.
- **`templates/competition/dashboard.html`**: incluir el toggle condicional justo después del selector de jornada y solo si `not is_ko_view` y hay partidos.

### JS

- **`static/js/matches-order.js`** (nuevo, módulo ES):
  1. Al cargar el DOM:
     - Lee `localStorage.getItem('porra26.matchesOrder')`. Si es `"group"`, aplica el reordenado.
     - Sincroniza el estado visual del toggle (`aria-pressed` y clase activa).
  2. Bindea click en los dos botones; cada click:
     - Guarda en localStorage.
     - Actualiza `aria-pressed` / clase activa.
     - Reordena los hijos de cada `.matches-grid` (clase nueva añadida a los `<div class="stagger">` que contienen las cards de partidos).
  3. La función de reordenado:
     - `date`: ordena por `data-kickoff` ascendente.
     - `group`: ordena por `data-group` ASCII case-insensitive, desempate por `data-kickoff`.
     - Re-inserta los nodos en el contenedor con `appendChild` en orden (no recrea).
  4. El módulo se carga desde `dashboard.html` con `<script type="module" src="{% static 'js/matches-order.js' %}">` dentro del bloque `{% block scripts %}`, solo cuando `not is_ko_view`.

Si el navegador no soporta localStorage o falla por modo privado, el módulo cae a "date" silenciosamente.

### CSS

- Reutilizar clases existentes (`glass`, `chip`, `chip-open`, `mono`). Pequeños ajustes inline o en un bloque de estilos del partial para centrar/espaciar el control. No se introduce hoja de estilos nueva.
- En móvil el toggle queda centrado, con ancho 100% si hace falta (`flex-wrap`).

## Accesibilidad

- `<nav aria-label="Orden de los partidos">` envolviendo los botones.
- `role="tablist"` en el nav y `role="tab"` + `aria-selected` en cada botón (o `aria-pressed` si tratamos como toggle puro — usaremos `aria-pressed` por simplicidad, no hay panel asociado distinto).
- El reorden no necesita anuncio explícito a screen reader; los headers de estado siguen siendo el punto de orientación.

## Lo que NO entra

- Mini-tabla de clasificación del grupo dentro de la card (idea futura, requiere standing en vivo del grupo).
- Vista "todas las jornadas mezcladas" (otro feature).
- Animación de reordenado (FLIP/morph). Si lo necesitamos más adelante, no rompe nada de esta entrega.
- Persistencia por usuario en backend. Cookie/localStorage por dispositivo es suficiente.
- Toggle en otras vistas (manage_results, KO, etc.).

## Tests

- **Unit (Django)**: no requeridos para nueva lógica de backend — no la hay. Verificar que `dashboard.html` sigue renderizando sin errores en los casos: groups con partidos, groups sin partidos, KO. Ya hay tests del dashboard que cubren render básico; añadir una aserción mínima de que `data-group` aparece en el HTML cuando hay partidos.
- **Manual**: en `?round=groups&matchday=1`, alternar el toggle y comprobar que el orden cambia y persiste tras recargar.
