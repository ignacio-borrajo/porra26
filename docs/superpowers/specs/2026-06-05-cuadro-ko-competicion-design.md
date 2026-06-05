# Spec — Cuadro completo de eliminatorias en Competición

**Fecha:** 2026-06-05
**Estado:** propuesto

## Goal

Cuando la ronda activa en `competition/dashboard` es una ronda eliminatoria (`r32`, `r16`, `qf`, `sf`, `final`), reemplazar el grid actual de tarjetas por un **cuadro de eliminatorias completo** con las 5 columnas (R32 → Final), conectadas con líneas SVG y navegables tanto por chips de ronda (que hacen scroll a la columna) como por drag-to-pan con el ratón en escritorio. En móvil, el cuadro se convierte en un **carrusel de una columna por página** con swipe lateral, sin líneas.

Las rondas de **grupos** (`groups` jornadas 1/2/3) mantienen el layout actual sin cambios.

## Por qué

Hoy el dashboard solo muestra los partidos de la ronda seleccionada, lo que en KO impide ver el cuadro como un todo y entender de qué cruces salen los equipos de la ronda siguiente. El modelo ya almacena la información necesaria (`Match.bracket_code`, `Match.home_slot`, `Match.away_slot`) pero no se expone visualmente. El Mundial 2026 arranca el 2026-06-11 con grupos: hay tiempo para tenerlo listo antes de que los KO comiencen.

## Comportamiento deseado

### Detección de modo KO

- Si `active_round.id == "groups"`: vista actual sin cambios.
- Si `active_round.id` ∈ {`r32`, `r16`, `qf`, `sf`, `final`}: vista de cuadro completo.

### Selector de ronda en modo KO

- Los chips de KO mantienen su URL `?round=<id>` (deep-linking funciona: cargar `?round=qf` posiciona el canvas con la columna QF pegada al borde izquierdo).
- Si el usuario está **ya** en modo KO y pulsa otro chip KO, el navegador hace `pushState` de la URL y el JS hace `scrollIntoView({inline:'start', behavior:'smooth'})` sobre la columna destino — **sin recargar la página**. Esto se intercepta capturando el click cuando `document.querySelector('.ko-canvas')` existe y la URL destino es del mismo modo.
- Si el chip pulsado es de grupos (o se viene de grupos a KO), recarga normal.

### Estructura del cuadro

Canvas horizontal con scrollbars ocultos (`scrollbar-width: none` + `::-webkit-scrollbar { display: none }`) que contiene 5 columnas (`.ko-col[data-round=…]`) y una capa SVG superpuesta para los conectores.

```
┌── .ko-canvas (overflow-x:auto, sin barras) ─────────────────────┐
│  ┌──R32──┐    ┌──R16──┐    ┌──QF───┐    ┌──SF───┐    ┌──FINAL─┐ │
│  │ M01   │\   │       │                                        │
│  │ M02   │ \  │ M33   │\   │                                   │
│  │  ⋮    │  \ │       │ \  │ M41   │\                          │
│  │ M16   │   \│ M40   │  \ │       │ \  │ M45   │\             │
│  └───────┘    └───────┘   \│ M44   │  \ │       │ \  ┌────────┐│
│                            └───────┘   \│ M46   │  \ │ M48    ││
│                                         └───────┘    └────────┘│
└────────────────────────────────────────────────────────────────┘
```

- Cada columna `display:flex; flex-direction:column; justify-content:space-around` reparte sus cards verticalmente. La columna más alta (R32, 16 cards) define la altura del canvas; las demás se centran respecto a la anterior automáticamente.
- Cards `min-width: 280px` (mismas que el grid actual); `gap: 56px` entre columnas; `padding: 32px` lateral en el canvas.
- La capa SVG (`.ko-connectors`, `position:absolute; inset:0; pointer-events:none`) cubre todo el ancho del scroll-content.
- El leaderboard sigue como `aside` a la derecha en `380px` (sin cambios en `dashboard-grid`).

### Conectores SVG

- Un `<path>` por cada par de hermanos que feeds-into el mismo cruce de la ronda siguiente, en forma de L doble:
  ```
     card A (centro Y derecha) ─┐
                                ├─── card destino (centro Y izquierda)
     card B (centro Y derecha) ─┘
  ```
- Coordenadas calculadas desde `getBoundingClientRect()` de cada card relativo al canvas (corrigiendo `scrollLeft` y `scrollTop`).
- `data-status` en cada path derivado del estado del partido destino:
  - `pending_teams` → `stroke: var(--line-muted)`, `stroke-dasharray: 4 6`
  - `open` / `live` → `stroke: var(--line)`, sólido
  - `done` → `stroke: var(--accent)`, `opacity: .85`
- Cuando el partido destino está `done`: solo la rama del **ganador** queda con stroke `--accent`; la del perdedor pasa a `opacity: .25`.

### Cards de slot pendiente (`pending_teams`)

**Ya implementado en `_match_card.html`.** La rama `if st == 'pending_teams'` actual usa el filtro de plantilla `slot_label` (definido en `competition/templatetags/competition_extras.py`) que ya cubre los patrones `"1A"`/`"2B"` → `"1º Grupo A"`, `"WM37"` → `"Ganador M37"`, `"3WG_S1"` → `"Mejor tercero (S1)"`, vacío/desconocido → `"Por definir"`. Se renderiza con bandera 🏳️, opacidad `.85`, sin enlace.

Lo único que se añade es el atributo `data-status="pending_teams"` en la raíz para que el borde dashed se aplique vía CSS (`article.match-card[data-status="pending_teams"]`).

### Navegación

**Chips de ronda** (escritorio y móvil):
- Click → `element.scrollIntoView({inline:'start', block:'nearest', behavior:'smooth'})` sobre `.ko-col[data-round="<id>"]`.
- En móvil con scroll-snap activo, el snap pega la columna al borde izquierdo.

**Drag-to-pan** (solo `@media (pointer:fine)`):
- Listener `pointerdown` sobre `.ko-canvas` con guard `e.target === canvas` (o un elemento "fondo" sin tarjeta) para no robar clicks de las cards.
- En `pointermove` actualiza `canvas.scrollLeft = startScrollLeft + (startX - e.clientX)`.
- `setPointerCapture` durante el drag.
- Cursor: `grab` por defecto, `grabbing` durante el drag.

**Scroll-snap** (escritorio y móvil):
- Canvas: `scroll-snap-type: x mandatory`.
- Columnas: `scroll-snap-align: start`.

**Posición inicial:**
- Al cargar con una ronda KO activa, antes del primer paint: `canvas.scrollLeft = activeColumn.offsetLeft - parseInt(padding)`. Se aplica con `requestAnimationFrame` y una clase `prevent-scroll-animation` que desactiva temporalmente `scroll-behavior: smooth`.

### Móvil (`@media (max-width: 768px)`)

- `.ko-col { min-width: 100%; padding: 12px 16px; }` → una columna por viewport.
- `svg.ko-connectors { display: none; }` → sin líneas en móvil.
- Indicador de página: 5 puntitos (`· · · · ·` con el activo `●`) encima del canvas, sincronizado con `scrollLeft` (un `IntersectionObserver` sobre las columnas marca cuál está activa).
- Sin drag-to-pan (el `@media (pointer:fine)` lo desactiva). Swipe nativo del navegador hace el trabajo.
- El leaderboard sigue colapsando debajo del bloque (como hoy con `.dashboard-grid` collapsing a 1 columna).

### Estilos por estado de card (sin cambios respecto al grid actual)

`_match_card.html` ya pinta los estados `open` (chip cyan), `live` (chip verde animado), `done` (chip neutro con marcador). Se reusan tal cual.

## Arquitectura

### Sin cambios en modelos ni servicios

El filtro de plantilla `slot_label` (en `competition/templatetags/competition_extras.py`) ya existe y cubre todos los patrones que necesitamos. No se añaden properties nuevas a `Match` ni helpers nuevos a `competition/services/bracket.py`.

`feeds_into_code` se calcula puntualmente en el view como anotación en cada match (NO es property del modelo): el view recolecta todos los KO matches, construye `{numero_bracket: bracket_code_destino}` recorriendo `home_slot`/`away_slot` que empiecen por `WM`, y anota `match.feeds_into_code` en memoria. Sin queries extra ni N+1.

### Cambios en `competition/views.py`

`DashboardView.get_context_data` decide:

```python
KO_ROUND_IDS = ("r32", "r16", "qf", "sf", "final")
is_ko_view = active_round.id in KO_ROUND_IDS

if is_ko_view:
    ko_matches = list(
        Match.objects
        .filter(round_id__in=KO_ROUND_IDS)
        .select_related("home", "away", "round")
        .order_by("round__order", "kickoff", "bracket_code")
    )
    # Construir mapa WM<n> -> bracket_code destino (para feeds_into sin N+1)
    feeds = {}
    for m in ko_matches:
        for slot in (m.home_slot, m.away_slot):
            if slot.startswith("WM"):
                feeds[slot[2:]] = m.bracket_code  # "37" -> "M45" por ejemplo
    for m in ko_matches:
        m.feeds_into_code = feeds.get(m.bracket_code.removeprefix("M")) if m.bracket_code else None

    ko_rounds = []
    for rid in KO_ROUND_IDS:
        r = next((m.round for m in ko_matches if m.round_id == rid), None)
        if r is None:
            continue
        ko_rounds.append({
            "round": r,
            "matches": [m for m in ko_matches if m.round_id == rid],
        })

    ctx["ko_rounds"] = ko_rounds
    ctx["active_ko_id"] = active_round.id

ctx["is_ko_view"] = is_ko_view
```

En modo KO no se calculan `open_matches`/`live_matches`/`done_matches` (no se usan).

### Cambios en `templates/competition/dashboard.html`

Una sola rama condicional:

```django
{% if is_ko_view %}
  {% include "competition/_ko_canvas.html" with ko_rounds=ko_rounds active_ko_id=active_ko_id my_preds=my_preds %}
{% else %}
  {# código actual de grupos: ABIERTOS / EN JUEGO / FINALIZADOS #}
{% endif %}
```

### Nuevo `templates/competition/_ko_canvas.html`

```django
{# Indicador móvil #}
<div class="ko-dots" aria-hidden="true">
  {% for r in ko_rounds %}
    <span data-round="{{ r.round.id }}" {% if r.round.id == active_ko_id %}class="active"{% endif %}></span>
  {% endfor %}
</div>

<div class="ko-canvas" data-active-round="{{ active_ko_id }}">
  {% for r in ko_rounds %}
    <section class="ko-col" data-round="{{ r.round.id }}">
      <header class="ko-col-head">{{ r.round.label }}</header>
      {% for m in r.matches %}
        {% include "competition/_match_card.html" with match=m my_preds=my_preds ko_mode=True %}
      {% endfor %}
    </section>
  {% endfor %}
  <svg class="ko-connectors" aria-hidden="true"></svg>
</div>
```

### Cambios en `templates/competition/_match_card.html`

Únicamente añadir 3 data-attributes a las raíces `<div class="match-card …">` y `<a class="match-card …">` (ambas ramas, `pending_teams` y el resto):

- `data-bracket-code="{{ match.bracket_code|default:'' }}"`
- `data-feeds-into="{{ match.feeds_into_code|default:'' }}"`
- `data-status="{{ st }}"`

El JS los lee para dibujar los conectores. No cambia el contenido visible de las cards.

### Cambios en `templates/partials/_round_selector.html`

Añadir `data-target-round="{{ r.id }}"` a cada chip. El JS lo usa para resolver scroll target.

### Nuevo `static/js/ko-bracket.js`

```js
// Módulo iniciado en _ko_canvas.html via <script type="module" src="…/ko-bracket.js" defer>

const canvas = document.querySelector(".ko-canvas");
if (canvas) init(canvas);

function init(canvas) {
  scrollToActiveColumn(canvas);
  setupChipNavigation(canvas);
  if (matchMedia("(pointer:fine)").matches) setupDragToPan(canvas);
  setupConnectors(canvas);
  setupMobileDots(canvas);
  window.addEventListener("resize", debounceRAF(() => layoutConnectors(canvas)));
}

function scrollToActiveColumn(canvas) {
  const active = canvas.dataset.activeRound;
  const col = canvas.querySelector(`.ko-col[data-round="${active}"]`);
  if (!col) return;
  canvas.classList.add("prevent-scroll-animation");
  canvas.scrollLeft = col.offsetLeft - parseInt(getComputedStyle(canvas).paddingLeft);
  requestAnimationFrame(() => canvas.classList.remove("prevent-scroll-animation"));
}

function setupChipNavigation(canvas) {
  document.querySelectorAll(".round-selector .chip[data-target-round]").forEach(chip => {
    chip.addEventListener("click", e => {
      const target = chip.dataset.targetRound;
      const col = canvas.querySelector(`.ko-col[data-round="${target}"]`);
      if (!col) return;  // ronda no KO → recarga normal
      e.preventDefault();
      col.scrollIntoView({ inline: "start", block: "nearest", behavior: "smooth" });
      history.pushState(null, "", chip.href);
    });
  });
}

function setupDragToPan(canvas) {
  let startX = 0, startScrollLeft = 0, dragging = false;
  canvas.addEventListener("pointerdown", e => {
    if (e.target.closest("article.match-card")) return;
    dragging = true;
    startX = e.clientX;
    startScrollLeft = canvas.scrollLeft;
    canvas.setPointerCapture(e.pointerId);
    canvas.classList.add("grabbing");
  });
  canvas.addEventListener("pointermove", e => {
    if (!dragging) return;
    canvas.scrollLeft = startScrollLeft + (startX - e.clientX);
  });
  ["pointerup", "pointercancel"].forEach(ev =>
    canvas.addEventListener(ev, () => { dragging = false; canvas.classList.remove("grabbing"); })
  );
}

function setupConnectors(canvas) {
  layoutConnectors(canvas);
  const ro = new ResizeObserver(debounceRAF(() => layoutConnectors(canvas)));
  ro.observe(canvas);
}

function layoutConnectors(canvas) {
  const svg = canvas.querySelector(".ko-connectors");
  if (!svg) return;
  const cards = [...canvas.querySelectorAll("article.match-card[data-bracket-code]")];
  const byCode = new Map(cards.map(c => [c.dataset.bracketCode, c]));
  const canvasRect = canvas.getBoundingClientRect();
  const offsetX = canvas.scrollLeft;
  const offsetY = canvas.scrollTop;
  svg.setAttribute("viewBox", `0 0 ${canvas.scrollWidth} ${canvas.scrollHeight}`);
  svg.style.width = canvas.scrollWidth + "px";
  svg.style.height = canvas.scrollHeight + "px";
  // Agrupar cards por feeds_into destino
  const groups = new Map();
  for (const card of cards) {
    const dest = card.dataset.feedsInto;
    if (!dest) continue;
    if (!groups.has(dest)) groups.set(dest, []);
    groups.get(dest).push(card);
  }
  const paths = [];
  for (const [destCode, siblings] of groups) {
    const dest = byCode.get(destCode);
    if (!dest || siblings.length !== 2) continue;
    const [a, b] = siblings.sort((x, y) =>
      x.getBoundingClientRect().top - y.getBoundingClientRect().top
    );
    const aR = relRect(a, canvasRect, offsetX, offsetY);
    const bR = relRect(b, canvasRect, offsetX, offsetY);
    const dR = relRect(dest, canvasRect, offsetX, offsetY);
    const midX = (Math.max(aR.right, bR.right) + dR.left) / 2;
    const aY = aR.top + aR.height / 2;
    const bY = bR.top + bR.height / 2;
    const dY = dR.top + dR.height / 2;
    const status = dest.dataset.status || "open";
    paths.push(
      `<path d="M${aR.right},${aY} H${midX} V${dY} H${dR.left}" data-status="${status}" />` +
      `<path d="M${bR.right},${bY} H${midX} V${dY} H${dR.left}" data-status="${status}" />`
    );
  }
  svg.innerHTML = paths.join("");
}

function relRect(el, canvasRect, offsetX, offsetY) {
  const r = el.getBoundingClientRect();
  return {
    left: r.left - canvasRect.left + offsetX,
    right: r.right - canvasRect.left + offsetX,
    top: r.top - canvasRect.top + offsetY,
    bottom: r.bottom - canvasRect.top + offsetY,
    width: r.width,
    height: r.height,
  };
}

function setupMobileDots(canvas) {
  const dots = document.querySelector(".ko-dots");
  if (!dots) return;
  const cols = canvas.querySelectorAll(".ko-col[data-round]");
  const io = new IntersectionObserver(entries => {
    for (const en of entries) {
      if (en.isIntersecting && en.intersectionRatio >= 0.5) {
        const code = en.target.dataset.round;
        dots.querySelectorAll("span").forEach(s =>
          s.classList.toggle("active", s.dataset.round === code)
        );
      }
    }
  }, { root: canvas, threshold: [0.5] });
  cols.forEach(c => io.observe(c));
}

function debounceRAF(fn) {
  let raf;
  return (...args) => {
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => fn(...args));
  };
}
```

`_match_card.html` también necesita `data-status="{{ match.status }}"` en el `<article>` para que los conectores derivados puedan colorearse.

### Cambios en `static/css/styles.css`

```css
.ko-canvas {
  position: relative;
  display: flex;
  gap: 56px;
  padding: 32px;
  overflow-x: auto;
  overflow-y: visible;
  scroll-snap-type: x mandatory;
  scroll-behavior: smooth;
  scrollbar-width: none;
  cursor: grab;
}
.ko-canvas.grabbing { cursor: grabbing; }
.ko-canvas.prevent-scroll-animation { scroll-behavior: auto; }
.ko-canvas::-webkit-scrollbar { display: none; }

.ko-col {
  display: flex;
  flex-direction: column;
  justify-content: space-around;
  gap: 14px;
  min-width: 280px;
  scroll-snap-align: start;
}
.ko-col-head {
  position: sticky;
  top: 0;
  background: var(--bg);
  padding: 4px 6px;
  font: 600 12px/1 var(--font-mono);
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-muted);
}

.ko-connectors { position: absolute; inset: 0; pointer-events: none; }
.ko-connectors path { fill: none; stroke-width: 2; }
.ko-connectors path[data-status="pending_teams"] { stroke: var(--line-muted); stroke-dasharray: 4 6; }
.ko-connectors path[data-status="open"],
.ko-connectors path[data-status="live"]         { stroke: var(--line); }
.ko-connectors path[data-status="done"]         { stroke: var(--accent); opacity: .85; }

.ko-dots {
  display: none;
  justify-content: center;
  gap: 6px;
  padding: 8px 0;
}
.ko-dots span {
  width: 6px; height: 6px; border-radius: 50%;
  background: var(--line-muted);
}
.ko-dots span.active { background: var(--accent); width: 8px; height: 8px; }

.match-card[data-status="pending_teams"] {
  border-style: dashed;
  border-color: var(--line-muted);
}

@media (max-width: 768px) {
  .ko-canvas { gap: 0; padding: 12px 0; }
  .ko-col { min-width: 100%; padding: 0 16px; }
  .ko-connectors { display: none; }
  .ko-dots { display: flex; }
}
```

(Las variables `--line`, `--line-muted`, `--accent`, `--bg`, `--text-muted`, `--font-mono`, `--font-display` ya existen en el tema actual; si alguna no, usar fallback equivalente.)

## Tests

### Backend (`competition/tests/`)

1. `test_competition_view.py` (ampliar):
   - Con ronda activa `groups` jornada 1 → contexto trae `is_ko_view=False` y `open_matches/...` igual que hoy.
   - Con ronda activa `r32` → contexto trae `is_ko_view=True`, `ko_rounds` con 5 entradas (r32/r16/qf/sf/final), `active_ko_id="r32"`.
   - Con ronda activa `final` → `active_ko_id="final"`.
   - Cada match en `ko_rounds` tiene `feeds_into_code` anotado: un partido de R32 con `bracket_code="M73"` cuyo ganador alimenta el `home_slot="WM73"` de un partido R16 con `bracket_code="M89"` → `feeds_into_code == "M89"`. Final → `None`.

### Frontend / template

2. `test_dashboard_ko_template.py` (snapshot ligero):
   - Renderizar dashboard con `is_ko_view=True` → output contiene `.ko-canvas`, 5 `.ko-col`, y un `<svg class="ko-connectors">`.
   - Cards de cruces sin equipos en KO → contienen el texto resuelto por `slot_label` (ej. "1º Grupo A", "Ganador M73") y atributos `data-status="pending_teams"`, `data-bracket-code="M<N>"`.

No se añaden tests E2E del JS — el comportamiento del bracket se valida manualmente en el plan de verificación.

## Verificación manual

1. **Escritorio** (Chrome): cargar `/competition/?round=<id-de-r32>`, comprobar que las 5 columnas son visibles con scroll horizontal interno, las líneas SVG conectan correctamente cada par de hermanos, drag-to-pan funciona en el fondo del canvas y no roba clicks de las cards.
2. Pulsar chip "Cuartos" → scroll suave hasta que la columna QF queda pegada al borde izquierdo, URL actualizada a `?round=<qf-id>` sin recarga.
3. Marcar uno de los partidos de R32 como `done` (vía gestor) → conector del partido R32 → R16 cambia a `--accent` y la rama del perdedor del cruce R32 baja a `opacity: .25`. La card de R16 sigue siendo `pending_teams` hasta que la otra rama del cruce también esté `done`.
4. Cambiar de ronda KO a ronda de grupos → recarga normal, vuelve al grid de hoy.
5. **Móvil** (DevTools ≤ 768px o iPhone real): canvas pasa a una columna por viewport, swipe lateral cambia de ronda, indicador de puntos refleja la ronda activa, sin líneas SVG. Pulsar chip de ronda → snap a esa página.
6. Deep-link: cargar `/competition/?round=<qf-id>` directo en móvil → arranca con la columna QF visible.

## Out of scope

- Zoom in/out del bracket.
- Animación de "ganador subiendo a la siguiente ronda" cuando se resuelve un partido.
- Comparar tu bracket con el de otro jugador (overlay de pronósticos rivales).
- Mini-mapa.
- Pronósticos sobre cruces con equipos pendientes (mantener el comportamiento actual: no se permite pronosticar hasta que `has_teams=True`).

## Notas de migración / datos

- Ninguna migración de base de datos.
- No hay flag de despliegue: el comportamiento es 100% derivado de `Round.code`. Si alguna ronda KO no existe en la base (caso poco probable porque ya están sembradas), la columna correspondiente simplemente no se renderiza.

## Riesgos

1. **Coordenadas SVG con cards de altura variable.** Mitigado por `ResizeObserver` sobre el canvas y recálculo en `resize`. Si alguna card cambia su altura durante drag, las líneas pueden quedar momentáneamente fuera de sitio hasta el siguiente RAF — aceptable.
2. **Performance con 31 partidos KO + SVG.** 31 cards y 30 paths SVG no es nada. No se prevé impacto.
3. **Conflicto entre drag-to-pan y los modales de pronóstico.** Mitigado por el guard `e.target.closest("article.match-card")` que descarta el inicio del drag si el click empieza dentro de una card.
4. **Móvil con `Final` (una sola card).** La columna ocupa la pantalla entera con la card sola centrada — el indicador de puntos sigue funcionando correctamente.
