# Rediseño KO (sin auto-asignación, columnas por ronda, edición admin) — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar la auto-asignación de equipos en eliminatorias, cambiar la vista KO de bracket a columnas por ronda ordenadas por fecha, y permitir al admin editar equipos y fecha/hora de cualquier partido (con reprogramación de recordatorios).

**Architecture:** Django app `competition`. Backend en `services/` y `views.py` (class-based views), plantillas Django en `templates/competition/`, CSS en `static/css/styles.css`, JS módulo en `static/js/`. Tests con pytest (`competition/tests/`), factories con factory_boy.

**Tech Stack:** Python 3 / Django, pytest + factory_boy, HTML/CSS/JS vanilla (módulos ES), sistema de modales propio (`data-modal-url` + `js/modal.js`).

## Global Constraints

- Interfaz y textos en **español de España**; copiar el tono del prototipo. (CLAUDE.md §6)
- Fidelidad visual: paleta Mundial, tipografías Sora/Inter/Geist Mono, efecto glass, tema claro/oscuro. No introducir librerías de UI. (CLAUDE.md)
- No inventar campos/pantallas fuera de lo especificado. (CLAUDE.md "Lo que NO debes hacer")
- Rondas KO: `KO_ROUND_IDS = ("r32", "r16", "qf", "sf", "final")`. Etiquetas: Dieciseisavos · Octavos · Cuartos · Semifinales · Final.
- Estado de partido: `Match.status` ∈ `open`/`live`/`done`/`pending_teams`; `has_result` = ambos marcadores no nulos; `has_teams` = ambos equipos no nulos.
- Cada mutación de `Match` relevante deja `AuditLog` (patrón de `resolve_match`/`delete_match`).
- Ejecutar tests: `pytest <ruta> -v` desde la raíz del worktree.

---

### Task 1: Cortar la auto-asignación de equipos KO en `resolve_match`

Al confirmar un resultado ya no se debe propagar equipos al siguiente cruce.

**Files:**
- Modify: `competition/services/resolve.py:40-42` (quitar la llamada a `propagate_after_match`)
- Test: `competition/tests/test_bracket_resolver.py:213-266` (reconvertir `test_resolve_match_hooks_propagation`)

**Interfaces:**
- Consumes: `resolve_match(match, *, home, away, actor)` (sin cambios de firma).
- Produces: `resolve_match` deja de invocar `propagate_after_match`. La función `propagate_after_match` sigue existiendo en `bracket.py` (sus tests unitarios directos se conservan) pero no se llama desde producción.

- [ ] **Step 1: Reescribir el test de propagación para que exija NO propagación**

En `competition/tests/test_bracket_resolver.py`, sustituir por completo el test `test_resolve_match_hooks_propagation` (líneas 213-266) por:

```python
@pytest.mark.django_db
def test_resolve_match_does_not_propagate_teams(groups_round):
    """Confirmar un resultado NO debe rellenar equipos del siguiente cruce:
    la asignación KO es manual (los cruces automáticos estaban mal creados)."""
    from accounts.models import User
    from competition.services.resolve import resolve_match

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    ned = TeamFactory(code="NED")
    ger = TeamFactory(code="GER")
    bel = TeamFactory(code="BEL")
    por = TeamFactory(code="POR")
    _played(groups_round, "B", ned, ger, 1, 0, matchday=1)
    _played(groups_round, "B", bel, por, 0, 0, matchday=1)
    _played(groups_round, "B", ned, bel, 1, 0, matchday=2)
    _played(groups_round, "B", ger, por, 2, 0, matchday=2)
    _played(groups_round, "B", ned, por, 3, 0, matchday=3)
    _played(groups_round, "B", ger, bel, 1, 0, matchday=3)
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    last = MatchFactory(
        round=groups_round,
        group="A",
        matchday=3,
        home=esp,
        away=fra,
        kickoff=timezone.now() - timedelta(hours=1),
    )
    ko = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M75",
        kickoff=timezone.now() + timedelta(days=10),
    )

    gestor = User.objects.create(email="g@x.es", is_gestor=True, name="G", is_active=True)
    resolve_match(last, home=1, away=0, actor=gestor)

    ko.refresh_from_db()
    assert ko.home is None
    assert ko.away is None
```

- [ ] **Step 2: Ejecutar el test y verlo fallar**

Run: `pytest competition/tests/test_bracket_resolver.py::test_resolve_match_does_not_propagate_teams -v`
Expected: FAIL — `assert ko.home is None` falla porque `resolve_match` todavía propaga y asigna `ESP`.

- [ ] **Step 3: Quitar la llamada a `propagate_after_match` en `resolve_match`**

En `competition/services/resolve.py`, eliminar estas líneas (actualmente 40-42) dentro de `resolve_match`, justo antes del bloque `detect_after_match`:

```python
    from competition.services.bracket import propagate_after_match

    propagate_after_match(match)

```

El bloque siguiente queda así:

```python
    AuditLog.objects.create(
        actor=actor,
        action="match_resolved",
        target_type="match",
        target_id=str(match.id),
        payload={"home": home, "away": away},
    )

    from announcements.services import detect_after_match

    detect_after_match(match)
```

- [ ] **Step 4: Ejecutar los tests del resolver y del bracket**

Run: `pytest competition/tests/test_bracket_resolver.py competition/tests/test_resolve.py -v`
Expected: PASS (todos). Los tests unitarios directos de `propagate_after_match`/`resolve_slot` siguen pasando; el nuevo test de no-propagación pasa.

- [ ] **Step 5: Commit**

```bash
git add competition/services/resolve.py competition/tests/test_bracket_resolver.py
git commit -m "feat(ko): dejar de auto-asignar equipos al resolver un partido"
```

---

### Task 2: Ordenación de columnas KO en la vista

La vista KO deja de construir bracket (pares/feeds) y pasa a columnas ordenadas: no finalizados (por fecha asc) arriba, luego finalizados (por fecha asc).

**Files:**
- Modify: `competition/views.py:16-28` (retirar `_group_into_pairs`, añadir `_order_ko_column`)
- Modify: `competition/views.py:107-140` (rama `is_ko_view` de `CompetitionView.get`)
- Test: `competition/tests/test_competition_view.py` (añadir tests)

**Interfaces:**
- Consumes: `Match`, `Prediction`, `KO_ROUND_IDS`, `Round`.
- Produces:
  - `_order_ko_column(matches: list[Match]) -> list[Match]`: devuelve los matches ordenados por `(m.has_result, m.kickoff)` — no finalizados primero, ambos grupos por kickoff ascendente.
  - Contexto de plantilla: `ko_rounds = [{"round": Round, "matches": list[Match]}]` (sin clave `pairs`, sin `feeds_into_code`).

- [ ] **Step 1: Escribir el test de ordenación de la función pura**

Añadir al final de `competition/tests/test_competition_view.py`:

```python
@pytest.mark.django_db
def test_order_ko_column_unfinished_first_then_by_kickoff():
    from django.utils import timezone
    from datetime import timedelta

    from competition.views import _order_ko_column
    from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    now = timezone.now()
    # done (más antiguo)
    done_old = MatchFactory(round=r32, matchday=None, home=TeamFactory(), away=TeamFactory(),
                            result_home=1, result_away=0, kickoff=now - timedelta(days=3))
    # done (más reciente)
    done_new = MatchFactory(round=r32, matchday=None, home=TeamFactory(), away=TeamFactory(),
                            result_home=2, result_away=2, kickoff=now - timedelta(days=1))
    # sin finalizar, futuro lejano
    open_late = MatchFactory(round=r32, matchday=None, home=TeamFactory(), away=TeamFactory(),
                             kickoff=now + timedelta(days=5))
    # sin finalizar, futuro próximo
    open_soon = MatchFactory(round=r32, matchday=None, home=TeamFactory(), away=TeamFactory(),
                             kickoff=now + timedelta(days=2))

    ordered = _order_ko_column([done_old, done_new, open_late, open_soon])

    assert ordered == [open_soon, open_late, done_old, done_new]
```

- [ ] **Step 2: Ejecutar y verlo fallar**

Run: `pytest competition/tests/test_competition_view.py::test_order_ko_column_unfinished_first_then_by_kickoff -v`
Expected: FAIL — `ImportError: cannot import name '_order_ko_column'`.

- [ ] **Step 3: Sustituir `_group_into_pairs` por `_order_ko_column`**

En `competition/views.py`, reemplazar la función `_group_into_pairs` (líneas 16-28) por:

```python
def _order_ko_column(matches: list) -> list:
    """Ordena los partidos de una columna KO: primero los no finalizados
    (`has_result` False) y luego los finalizados, ambos por kickoff ascendente."""
    return sorted(matches, key=lambda m: (m.has_result, m.kickoff))
```

- [ ] **Step 4: Reescribir la rama `is_ko_view` de `CompetitionView.get`**

En `competition/views.py`, sustituir el bloque `ko_rounds` (líneas 107-140) por:

```python
        ko_rounds: list[dict] = []
        if is_ko_view:
            ko_matches = list(
                Match.objects.filter(round_id__in=KO_ROUND_IDS).select_related(
                    "home", "away", "round"
                )
            )
            ko_my_preds = {
                p.match_id: p
                for p in Prediction.objects.filter(player=request.user, match__in=ko_matches)
            }
            for m in ko_matches:
                m.my_pred = ko_my_preds.get(m.id)
            rounds_by_id = {r.id: r for r in rounds}
            for rid in KO_ROUND_IDS:
                r_obj = rounds_by_id.get(rid)
                if r_obj is None:
                    continue
                rmatches = _order_ko_column([m for m in ko_matches if m.round_id == rid])
                ko_rounds.append({"round": r_obj, "matches": rmatches})
```

- [ ] **Step 5: Ejecutar el test y la suite de la vista**

Run: `pytest competition/tests/test_competition_view.py -v`
Expected: PASS (incluido el nuevo test).

- [ ] **Step 6: Commit**

```bash
git add competition/views.py competition/tests/test_competition_view.py
git commit -m "feat(ko): construir columnas por ronda ordenadas por fecha en la vista"
```

---

### Task 3: Card "Por definir" para partidos sin equipos

Los partidos sin equipos dejan de mostrar etiquetas de slot ("Ganador M73", "1º Grupo A") y muestran "Por definir".

**Files:**
- Modify: `templates/competition/_match_card.html:19,24`
- Test: `competition/tests/test_match_card_render.py` (nuevo)

**Interfaces:**
- Consumes: contexto `match` con `status == "pending_teams"`.
- Produces: la card de un partido sin equipos muestra el texto literal `Por definir` en ambos lados y no muestra la etiqueta del slot.

- [ ] **Step 1: Escribir el test de render de la card pendiente**

Crear `competition/tests/test_match_card_render.py`:

```python
from datetime import timedelta

import pytest
from django.template import Context, Template
from django.utils import timezone

from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_pending_teams_card_shows_por_definir_not_slot_label():
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    m = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="WM73",
        bracket_code="M89",
        kickoff=timezone.now() + timedelta(days=10),
    )
    tpl = Template('{% include "competition/_match_card.html" with match=match %}')
    html = tpl.render(Context({"match": m, "request": None}))

    assert html.count("Por definir") >= 2
    assert "Ganador" not in html
    assert "Grupo A" not in html
```

- [ ] **Step 2: Ejecutar y verlo fallar**

Run: `pytest competition/tests/test_match_card_render.py -v`
Expected: FAIL — el HTML contiene "1º Grupo A" y "Ganador M73" (renderiza `slot_label`), no dos "Por definir".

- [ ] **Step 3: Cambiar las etiquetas de slot por "Por definir"**

En `templates/competition/_match_card.html`, dentro del bloque `{% if st == 'pending_teams' %}`, cambiar:

Línea 19:
```html
      <strong class="team-name display">{{ match.home_slot|slot_label }}</strong>
```
por:
```html
      <strong class="team-name display">Por definir</strong>
```

Línea 24:
```html
      <strong class="team-name display">{{ match.away_slot|slot_label }}</strong>
```
por:
```html
      <strong class="team-name display">Por definir</strong>
```

- [ ] **Step 4: Ejecutar el test**

Run: `pytest competition/tests/test_match_card_render.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/competition/_match_card.html competition/tests/test_match_card_render.py
git commit -m "feat(ko): mostrar 'Por definir' en partidos sin equipos asignados"
```

---

### Task 4: Vista de columnas por ronda (template + CSS + JS)

Reemplazar el bracket (`_ko_canvas.html`, grilla, conectores SVG) por columnas planas por ronda con las cards ordenadas. Se conservan scroll horizontal, chips de navegación y arrastre-para-desplazar.

**Files:**
- Create: `templates/competition/_ko_columns.html`
- Delete: `templates/competition/_ko_canvas.html`
- Modify: `templates/competition/dashboard.html:32-35`
- Modify: `static/js/ko-bracket.js` (retirar conectores; adaptar selector)
- Modify: `static/css/styles.css:2937-3062` (reemplazar bloque bracket por columnas)

**Interfaces:**
- Consumes: contexto `ko_rounds = [{"round", "matches"}]`, `active_ko_id` (de Task 2).
- Produces: contenedor `.ko-columns[data-active-round]` con `.ko-col[data-round]` que contienen `.ko-col-body` con `_match_card.html`. JS opera sobre `.ko-columns`.

- [ ] **Step 1: Crear la plantilla de columnas**

Crear `templates/competition/_ko_columns.html`:

```html
{% load static %}
<div class="ko-columns" data-active-round="{{ active_ko_id }}">
  {% for entry in ko_rounds %}
    <section class="ko-col" data-round="{{ entry.round.id }}">
      <header class="ko-col-head">{{ entry.round.label }}</header>
      <div class="ko-col-body">
        {% for m in entry.matches %}
          {% include "competition/_match_card.html" with match=m %}
        {% empty %}
          <p class="glass" style="padding:16px;opacity:.7"><span class="mono">Sin partidos en esta ronda todavía.</span></p>
        {% endfor %}
      </div>
    </section>
  {% empty %}
    <p class="glass" style="padding:18px">No hay eliminatorias todavía.</p>
  {% endfor %}
</div>
<script type="module" src="{% static 'js/ko-bracket.js' %}"></script>
```

- [ ] **Step 2: Apuntar el dashboard a la nueva plantilla**

En `templates/competition/dashboard.html`, cambiar el include (líneas 32-35):

```html
    {% if is_ko_view %}
      <div class="comp-section comp-section--pred">
        {% include "competition/_ko_canvas.html" with ko_rounds=ko_rounds active_ko_id=active_ko_id my_preds=my_preds %}
      </div>
```
por:
```html
    {% if is_ko_view %}
      <div class="comp-section comp-section--pred">
        {% include "competition/_ko_columns.html" with ko_rounds=ko_rounds active_ko_id=active_ko_id %}
      </div>
```

- [ ] **Step 3: Borrar la plantilla antigua del bracket**

```bash
git rm templates/competition/_ko_canvas.html
```

- [ ] **Step 4: Simplificar el JS (quitar conectores, usar `.ko-columns`)**

Sustituir el contenido completo de `static/js/ko-bracket.js` por:

```javascript
const canvas = document.querySelector(".ko-columns");
if (canvas) init(canvas);

function init(canvas) {
  setupChipNavigation(canvas);
  if (isCanvasVisible(canvas)) {
    scrollToActiveColumn(canvas);
    setupDragToPan(canvas);
  }
}

function isCanvasVisible(canvas) {
  return getComputedStyle(canvas).display !== "none";
}

function scrollToActiveColumn(canvas) {
  const active = canvas.dataset.activeRound;
  if (!active) return;
  const col = canvas.querySelector(`.ko-col[data-round="${active}"]`);
  if (!col) return;
  const padLeft = parseInt(getComputedStyle(canvas).paddingLeft) || 0;
  canvas.classList.add("prevent-scroll-animation");
  canvas.scrollLeft = col.offsetLeft - padLeft;
  requestAnimationFrame(() => canvas.classList.remove("prevent-scroll-animation"));
}

function setupChipNavigation(canvas) {
  const chips = document.querySelectorAll(".round-selector .chip[data-target-round]");
  chips.forEach(chip => {
    chip.addEventListener("click", e => {
      if (!isCanvasVisible(canvas)) return;
      const target = chip.dataset.targetRound;
      if (!target) return;
      const col = canvas.querySelector(`.ko-col[data-round="${target}"]`);
      if (!col) return;
      e.preventDefault();
      col.scrollIntoView({ inline: "start", block: "nearest", behavior: "smooth" });
      history.pushState(null, "", chip.href);
    });
  });
}

function setupDragToPan(canvas) {
  let startX = 0;
  let startY = 0;
  let startScrollLeft = 0;
  let startPageY = 0;
  let active = false;

  function onMove(e) {
    if (!active) return;
    canvas.scrollLeft = startScrollLeft + (startX - e.clientX);
    window.scrollTo(window.scrollX, startPageY + (startY - e.clientY));
  }
  function onEnd() {
    if (!active) return;
    active = false;
    canvas.classList.remove("grabbing");
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onEnd);
    document.removeEventListener("pointercancel", onEnd);
  }

  canvas.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    if (e.target.closest("a, button")) return;
    active = true;
    startX = e.clientX;
    startY = e.clientY;
    startScrollLeft = canvas.scrollLeft;
    startPageY = window.scrollY;
    canvas.classList.add("grabbing");
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onEnd);
    document.addEventListener("pointercancel", onEnd);
    e.preventDefault();
  });
}
```

- [ ] **Step 5: Reemplazar el CSS del bracket por columnas planas**

En `static/css/styles.css`, sustituir todo el bloque desde `.ko-canvas {` (línea 2937) hasta el cierre del `@media (max-width: 768px)` del bracket (línea 3062, justo antes de `/* === Banda "EN JUEGO" en Rankings === */`) por:

```css
.ko-columns {
  position: relative;
  display: flex;
  align-items: flex-start;
  gap: 24px;
  padding: 16px 4px;
  overflow-x: auto;
  overflow-y: visible;
  scroll-snap-type: x proximity;
  scroll-behavior: smooth;
  scrollbar-width: none;
  cursor: grab;
}
.ko-columns.grabbing { cursor: grabbing; }
.ko-columns.prevent-scroll-animation { scroll-behavior: auto; }
.ko-columns::-webkit-scrollbar { display: none; }

.ko-col {
  flex: 0 0 300px;
  min-width: 300px;
  scroll-snap-align: start;
}
.ko-col-head {
  position: sticky;
  top: 0;
  z-index: 2;
  background: linear-gradient(180deg, var(--bg-0) 0%, color-mix(in oklch, var(--bg-0) 55%, transparent) 80%, transparent);
  padding: 4px 6px 10px;
  font: 600 12px/1 var(--font-mono);
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-dim);
}
.ko-col-body {
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.ko-columns .team-name {
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  max-width: 100%;
}
.match-card[data-status="pending_teams"] {
  border: 1px dashed var(--border);
}

@media (max-width: 768px) {
  .ko-col {
    flex-basis: 82vw;
    min-width: 82vw;
  }
}
```

- [ ] **Step 6: Verificar que la suite completa sigue verde**

Run: `pytest competition/tests/ -v`
Expected: PASS (no debe haber referencias rotas a `_ko_canvas.html`).

- [ ] **Step 7: Verificación manual del render KO**

Run: `python manage.py collectstatic --noinput >/dev/null 2>&1; python manage.py runserver` (o el flujo habitual del proyecto) y abrir `/?round=r32`.
Expected: columnas Dieciseisavos·Octavos·Cuartos·Semifinales·Final con scroll horizontal, cards ordenadas (no finalizados arriba), chips que navegan a cada columna, arrastre para desplazar. Si no puedes levantar el server aquí, indícalo y deja la verificación para el usuario.

- [ ] **Step 8: Commit**

```bash
git add templates/competition/_ko_columns.html templates/competition/dashboard.html static/js/ko-bracket.js static/css/styles.css
git rm templates/competition/_ko_canvas.html
git commit -m "feat(ko): vista de columnas por ronda en lugar del bracket"
```

---

### Task 5: `MatchEditView` — editar equipos + fecha/hora (backend + urls)

Vista para que el gestor edite cualquier partido: equipos (permitiendo dejarlos vacíos) y kickoff. Reprograma recordatorios y valida invalidación de pronósticos. Absorbe y sustituye a `AssignTeamsView`.

**Files:**
- Modify: `competition/views.py` (retirar `AssignTeamsView`, añadir `MatchEditView`)
- Modify: `competition/urls.py:11-15` (sustituir ruta `assign_teams` por `edit`)
- Rename/Modify test: `competition/tests/test_assign_teams_view.py` → `competition/tests/test_match_edit_view.py`

**Interfaces:**
- Consumes: `Match`, `Team`, `Prediction`, `BetsReminderLog`, `AuditLog`, `GestorRequiredMixin`.
- Produces:
  - `MatchEditView` con `get(request, match_id)` → renderiza `competition/_match_edit_modal.html` (contexto `match`, `all_teams`, `has_predictions`).
  - `post(request, match_id)` → parámetros `home_code`, `away_code` (pueden ir vacíos), `date` (`YYYY-MM-DD`), `time` (`HH:MM`), `confirm_invalidate` (`"1"`), `round`, `matchday`. Redirige a `competicion:manage_results` conservando `round`/`matchday`.
  - Nombre de URL: `competicion:edit`.

- [ ] **Step 1: Escribir los tests de `MatchEditView`**

Renombrar el fichero y reemplazar su contenido. Primero:

```bash
git mv competition/tests/test_assign_teams_view.py competition/tests/test_match_edit_view.py
```

Sustituir el contenido completo de `competition/tests/test_match_edit_view.py` por:

```python
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from competition.models import BetsReminderLog, Prediction
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture
def gestor(db):
    return User.objects.create(
        email="g@example.com", is_gestor=True, name="G", is_active=True,
        must_change_password=False,
    )


@pytest.fixture
def jugador(db):
    return User.objects.create(
        email="j@example.com", is_jugador=True, name="J", is_active=True,
        must_change_password=False,
    )


@pytest.fixture
def r32(db):
    return RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)


def _ko(**kw):
    defaults = dict(
        group="R32", matchday=None, home=None, away=None,
        home_slot="1A", away_slot="2B",
        kickoff=timezone.now() + timedelta(days=10),
    )
    defaults.update(kw)
    return MatchFactory(**defaults)


@pytest.mark.django_db
def test_edit_assigns_teams_and_kickoff(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    m = _ko(round=r32, bracket_code="M73")
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ARG", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home == esp
    assert m.away == arg
    assert m.kickoff.year == 2026 and m.kickoff.month == 7 and m.kickoff.day == 15


@pytest.mark.django_db
def test_edit_allows_empty_teams(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    m = _ko(round=r32, home=esp, away=TeamFactory(code="ARG"), bracket_code="M74")
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "", "away_code": "", "date": "2026-07-16", "time": "18:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home is None and m.away is None
    assert m.status == "pending_teams"


@pytest.mark.django_db
def test_edit_rejects_same_team_both_sides(client, gestor, r32):
    TeamFactory(code="ESP")
    m = _ko(round=r32, bracket_code="M75")
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ESP", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home is None and m.away is None


@pytest.mark.django_db
def test_edit_requires_confirmation_to_invalidate_predictions(client, gestor, jugador, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    TeamFactory(code="FRA")
    m = _ko(round=r32, home=esp, away=arg, bracket_code="M76")
    Prediction.objects.create(player=jugador, match=m, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "FRA", "away_code": "ARG", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home == esp
    assert Prediction.objects.filter(match=m).count() == 1


@pytest.mark.django_db
def test_edit_invalidates_predictions_with_confirmation(client, gestor, jugador, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    m = _ko(round=r32, home=esp, away=arg, bracket_code="M77")
    Prediction.objects.create(player=jugador, match=m, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "FRA", "away_code": "ARG", "date": "2026-07-15",
         "time": "21:00", "confirm_invalidate": "1"},
    )
    assert resp.status_code == 302
    m.refresh_from_db()
    assert m.home == fra
    assert Prediction.objects.filter(match=m).count() == 0


@pytest.mark.django_db
def test_edit_future_kickoff_resets_auto_reminders(client, gestor, r32):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    m = _ko(round=r32, home=esp, away=arg, bracket_code="M78",
            kickoff=timezone.now() + timedelta(hours=1))
    BetsReminderLog.objects.create(
        match=m, kind=BetsReminderLog.KIND_T_MINUS_2H,
        sent_at=timezone.now(), pending_count=3, pending_names=["A", "B", "C"],
    )
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ARG", "date": "2026-08-01", "time": "20:00"},
    )
    assert resp.status_code == 302
    assert BetsReminderLog.objects.filter(match=m).count() == 0


@pytest.mark.django_db
def test_edit_non_gestor_forbidden(client, jugador, r32):
    TeamFactory(code="ESP")
    TeamFactory(code="ARG")
    m = _ko(round=r32, bracket_code="M79")
    client.force_login(jugador)
    resp = client.post(
        reverse("competicion:edit", args=[m.id]),
        {"home_code": "ESP", "away_code": "ARG", "date": "2026-07-15", "time": "21:00"},
    )
    assert resp.status_code in (302, 403)
    m.refresh_from_db()
    assert m.home is None
```

- [ ] **Step 2: Ejecutar y verlo fallar**

Run: `pytest competition/tests/test_match_edit_view.py -v`
Expected: FAIL — `NoReverseMatch: 'edit'` (la ruta aún no existe).

- [ ] **Step 3: Añadir `MatchEditView` y retirar `AssignTeamsView`**

En `competition/views.py`, eliminar por completo la clase `AssignTeamsView` (líneas 517-556) y añadir en su lugar:

```python
class MatchEditView(GestorRequiredMixin, View):
    """Edita cualquier partido: equipos (pueden quedar vacíos → 'Por definir')
    y fecha/hora de saque. Si al cambiar los equipos el partido ya tenía
    pronósticos, exige `confirm_invalidate=1` y los borra. Si el nuevo kickoff
    es futuro y cambió, resetea los recordatorios automáticos para que se
    reprogramen en las nuevas ventanas."""

    def get(self, request, match_id):
        from competition.models import Team

        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        return render(
            request,
            "competition/_match_edit_modal.html",
            {
                "match": m,
                "all_teams": list(Team.objects.order_by("name")),
                "has_predictions": Prediction.objects.filter(match=m).exists(),
            },
        )

    def post(self, request, match_id):
        from datetime import datetime

        from django.utils import timezone

        from accounts.models import AuditLog
        from competition.models import BetsReminderLog, Team

        m = get_object_or_404(Match, pk=match_id)
        home_code = (request.POST.get("home_code") or "").strip()
        away_code = (request.POST.get("away_code") or "").strip()
        date_str = (request.POST.get("date") or "").strip()
        time_str = (request.POST.get("time") or "").strip()

        if home_code and away_code and home_code == away_code:
            messages.error(request, "Local y visitante no pueden ser el mismo equipo.")
            return redirect(self._back_url(request))

        home = Team.objects.filter(code=home_code).first() if home_code else None
        away = Team.objects.filter(code=away_code).first() if away_code else None
        if (home_code and home is None) or (away_code and away is None):
            messages.error(request, "Equipo no encontrado.")
            return redirect(self._back_url(request))

        try:
            new_kickoff = timezone.make_aware(
                datetime.strptime(f"{date_str} {time_str}", "%Y-%m-%d %H:%M")
            )
        except ValueError:
            messages.error(request, "Fecha u hora inválidas.")
            return redirect(self._back_url(request))

        teams_changed = m.home_id != (home.id if home else None) or m.away_id != (
            away.id if away else None
        )
        existing_preds = Prediction.objects.filter(match=m).exists()
        if teams_changed and existing_preds and request.POST.get("confirm_invalidate") != "1":
            messages.error(
                request,
                "Este partido ya tiene pronósticos. Marca la casilla de confirmación "
                "para cambiar los equipos y borrar los pronósticos existentes.",
            )
            return redirect(self._back_url(request))

        if teams_changed and existing_preds:
            Prediction.objects.filter(match=m).delete()

        old_kickoff = m.kickoff
        m.home = home
        m.away = away
        m.kickoff = new_kickoff
        m.save(update_fields=["home", "away", "kickoff"])

        if new_kickoff != old_kickoff and new_kickoff > timezone.now():
            BetsReminderLog.objects.filter(
                match=m, kind__in=BetsReminderLog.AUTO_KINDS
            ).delete()

        AuditLog.objects.create(
            actor=request.user,
            action="match_edited",
            target_type="match",
            target_id=str(m.id),
            payload={
                "home": home.code if home else None,
                "away": away.code if away else None,
                "kickoff": new_kickoff.isoformat(),
            },
        )

        label = f"{home.name if home else 'Por definir'} vs {away.name if away else 'Por definir'}"
        messages.success(request, f"Partido actualizado · {label}")
        return redirect(self._back_url(request))

    @staticmethod
    def _back_url(request):
        from urllib.parse import urlencode

        from django.urls import reverse

        params = {}
        rnd = request.POST.get("round")
        md = request.POST.get("matchday")
        if rnd:
            params["round"] = rnd
        if md:
            params["matchday"] = md
        url = reverse("competicion:manage_results")
        return f"{url}?{urlencode(params)}" if params else url
```

- [ ] **Step 4: Sustituir la ruta en `urls.py`**

En `competition/urls.py`, reemplazar el bloque de `assign_teams` (líneas 11-15):

```python
    path(
        "resultados/<int:match_id>/equipos/",
        views.AssignTeamsView.as_view(),
        name="assign_teams",
    ),
```
por:
```python
    path(
        "resultados/<int:match_id>/editar/",
        views.MatchEditView.as_view(),
        name="edit",
    ),
```

- [ ] **Step 5: Ejecutar los tests de la vista**

Run: `pytest competition/tests/test_match_edit_view.py -v`
Expected: PASS (los 7 tests).

- [ ] **Step 6: Commit**

```bash
git add competition/views.py competition/urls.py competition/tests/test_match_edit_view.py
git commit -m "feat(admin): MatchEditView para editar equipos y fecha/hora de cualquier partido"
```

---

### Task 6: Modal de edición + botón "Editar" en Resultados

Añadir la plantilla del modal y los botones "Editar" en `manage_results.html`; sustituir el formulario inline de asignación de equipos.

**Files:**
- Create: `templates/competition/_match_edit_modal.html`
- Modify: `templates/competition/manage_results.html` (bloque `pending_teams` y filas de `pending`/`upcoming`/`done`)

**Interfaces:**
- Consumes: `competicion:edit` (GET modal, POST guardar) de Task 5.
- Produces: modal con selects de equipos + inputs de fecha/hora + checkbox de confirmación; abre vía `data-modal-url`.

- [ ] **Step 1: Crear el modal de edición**

Crear `templates/competition/_match_edit_modal.html`:

```html
{% load icons %}
<section class="glass pop" style="width:min(560px,100%);padding:28px;border-radius:24px;background:var(--surface-solid)">
  <header style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
    <div>
      <div class="eyebrow">{{ match.round.short }}{% if match.bracket_code %} · {{ match.bracket_code }}{% endif %}</div>
      <h1 class="display" style="font-size:24px;margin:4px 0 0">Editar partido</h1>
    </div>
    <button type="button" data-modal-close class="btn btn-ghost" style="width:36px;height:36px;padding:0;border-radius:12px" aria-label="Cerrar">{% icon "x" width=14 %}</button>
  </header>
  <form method="post" action="{% url 'competicion:edit' match.id %}" style="margin-top:16px;display:flex;flex-direction:column;gap:14px">
    {% csrf_token %}
    <input type="hidden" name="round" value="{{ match.round_id }}">
    {% if match.matchday %}<input type="hidden" name="matchday" value="{{ match.matchday }}">{% endif %}

    <label style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">Local</span>
      <select name="home_code" class="input">
        <option value="">Por definir…</option>
        {% for t in all_teams %}<option value="{{ t.code }}"{% if match.home_id == t.code %} selected{% endif %}>{{ t.flag }} {{ t.name }}</option>{% endfor %}
      </select>
    </label>

    <label style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">Visitante</span>
      <select name="away_code" class="input">
        <option value="">Por definir…</option>
        {% for t in all_teams %}<option value="{{ t.code }}"{% if match.away_id == t.code %} selected{% endif %}>{{ t.flag }} {{ t.name }}</option>{% endfor %}
      </select>
    </label>

    <div style="display:flex;gap:12px;flex-wrap:wrap">
      <label style="display:flex;flex-direction:column;gap:4px;flex:1;min-width:150px">
        <span class="eyebrow">Fecha</span>
        <input type="date" name="date" class="input" value="{{ match.kickoff|date:'Y-m-d' }}" required>
      </label>
      <label style="display:flex;flex-direction:column;gap:4px;flex:1;min-width:120px">
        <span class="eyebrow">Hora</span>
        <input type="time" name="time" class="input" value="{{ match.kickoff|date:'H:i' }}" required>
      </label>
    </div>

    {% if has_predictions %}
    <label style="display:flex;gap:8px;align-items:flex-start;font-size:13px;color:var(--text-dim)">
      <input type="checkbox" name="confirm_invalidate" value="1" style="margin-top:2px">
      <span>Este partido tiene pronósticos. Si cambio los equipos, confirmo que se <strong>borrarán</strong> los pronósticos existentes.</span>
    </label>
    {% endif %}

    <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap;margin-top:4px">
      <button class="btn btn-ghost" type="button" data-modal-close>Cancelar</button>
      <button class="btn btn-primary" type="submit">Guardar cambios</button>
    </div>
  </form>
</section>
```

- [ ] **Step 2: Sustituir el bloque `pending_teams` en `manage_results.html`**

En `templates/competition/manage_results.html`, reemplazar el bloque completo `{% if pending_teams_matches %} ... {% endif %}` (líneas 9-36) por:

```html
{% if pending_teams_matches %}
<h2 class="eyebrow" style="margin-top:18px">CRUCE PENDIENTE · {{ pending_teams_matches|length }}</h2>
<div class="table-scroll" style="display:flex;flex-direction:column;gap:10px">
  {% for m in pending_teams_matches %}
  <div class="glass" style="padding:12px 14px;border-radius:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center">
    <div style="min-width:220px;display:flex;flex-direction:column;gap:2px;flex:1">
      <span class="eyebrow">{{ m.round.short }}{% if m.bracket_code %} · {{ m.bracket_code }}{% endif %}</span>
      <strong>Por definir vs Por definir</strong>
      <span class="mono" style="font-size:11px;color:var(--text-faint)">{{ m.kickoff|date:"D j M · H:i" }}</span>
    </div>
    <a class="btn btn-primary" href="{% url 'competicion:edit' m.id %}" data-modal-url="{% url 'competicion:edit' m.id %}" style="padding:6px 14px;font-size:13px">Editar</a>
    {% include "competition/_delete_match_form.html" %}
  </div>
  {% endfor %}
</div>
{% endif %}
```

- [ ] **Step 3: Añadir botón "Editar" en la fila de "PENDIENTES DE FINALIZAR"**

En `templates/competition/manage_results.html`, en el bloque `{% if pending %}`, dentro de la fila (antes de `{% include "competition/_delete_match_form.html" %}` de la línea 51), añadir:

```html
    <a class="btn btn-ghost" href="{% url 'competicion:edit' m.id %}" data-modal-url="{% url 'competicion:edit' m.id %}" style="padding:6px 12px;font-size:12px">Editar</a>
```

- [ ] **Step 4: Añadir botón "Editar" en la fila de "PRÓXIMOS"**

En el bloque `{% if upcoming %}`, dentro de la fila (antes del `{% include "competition/_delete_match_form.html" %}` de la línea 75), añadir:

```html
    <a class="btn btn-ghost" href="{% url 'competicion:edit' m.id %}" data-modal-url="{% url 'competicion:edit' m.id %}" style="padding:6px 12px;font-size:12px">Editar partido</a>
```

- [ ] **Step 5: Cambiar el botón "Editar" de "FINALIZADOS" para que edite el partido**

En el bloque `{% if done %}`, la fila tiene hoy un enlace "Editar" que abre el modal de resultado (`competicion:official`, línea 94). Añadir junto a él un botón para editar equipos/fecha (deja el de resultado intacto, renombrándolo a "Editar resultado"):

Reemplazar la línea 94:
```html
    <a class="btn btn-ghost" href="{% url 'competicion:official' m.id %}" data-modal-url="{% url 'competicion:official' m.id %}" style="padding:6px 12px;font-size:12px">Editar</a>
```
por:
```html
    <a class="btn btn-ghost" href="{% url 'competicion:official' m.id %}" data-modal-url="{% url 'competicion:official' m.id %}" style="padding:6px 12px;font-size:12px">Editar resultado</a>
    <a class="btn btn-ghost" href="{% url 'competicion:edit' m.id %}" data-modal-url="{% url 'competicion:edit' m.id %}" style="padding:6px 12px;font-size:12px">Editar partido</a>
```

- [ ] **Step 6: Verificar que no quedan referencias a `assign_teams`**

Run: `grep -rn "assign_teams" templates/ competition/ ; echo "---fin---"`
Expected: sin resultados salvo `---fin---`. Si aparece alguno, sustituirlo por `competicion:edit`.

- [ ] **Step 7: Ejecutar tests que renderizan `manage_results`**

Run: `pytest competition/tests/test_manage_results_reminders.py competition/tests/test_match_edit_view.py -v`
Expected: PASS.

- [ ] **Step 8: Commit**

```bash
git add templates/competition/_match_edit_modal.html templates/competition/manage_results.html
git commit -m "feat(admin): modal y botones 'Editar partido' en la pantalla de Resultados"
```

---

### Task 7: Management command `reset_ko_assignments`

Limpieza puntual: nulifica equipos y borra pronósticos de los cruces KO sin resultado oficial (creados mal en producción).

**Files:**
- Create: `competition/management/commands/reset_ko_assignments.py`
- Test: `competition/tests/test_reset_ko_assignments_command.py` (nuevo)

**Interfaces:**
- Consumes: `Match`, `Prediction`.
- Produces: comando `reset_ko_assignments` con flag `--dry-run`. Afecta a partidos con `round_id in KO_ROUND_IDS` que NO estén finalizados y tengan algún equipo asignado: pone `home=None`, `away=None` y borra sus `Prediction`.

- [ ] **Step 1: Escribir el test del comando**

Crear `competition/tests/test_reset_ko_assignments_command.py`:

```python
from datetime import timedelta

import pytest
from django.core.management import call_command
from django.utils import timezone

from competition.models import Prediction
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
    TeamFactory,
)


@pytest.fixture
def r32(db):
    return RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)


@pytest.mark.django_db
def test_reset_nulls_unfinished_ko_and_deletes_predictions(r32):
    ko = MatchFactory(
        round=r32, matchday=None,
        home=TeamFactory(code="ESP"), away=TeamFactory(code="ARG"),
        kickoff=timezone.now() + timedelta(days=5),
    )
    PredictionFactory(match=ko, home=1, away=0)

    call_command("reset_ko_assignments")

    ko.refresh_from_db()
    assert ko.home is None and ko.away is None
    assert Prediction.objects.filter(match=ko).count() == 0


@pytest.mark.django_db
def test_reset_leaves_finished_ko_untouched(r32):
    done = MatchFactory(
        round=r32, matchday=None,
        home=TeamFactory(code="FRA"), away=TeamFactory(code="BRA"),
        result_home=2, result_away=1,
        kickoff=timezone.now() - timedelta(days=1),
    )
    PredictionFactory(match=done, home=2, away=1)

    call_command("reset_ko_assignments")

    done.refresh_from_db()
    assert done.home is not None and done.away is not None
    assert Prediction.objects.filter(match=done).count() == 1


@pytest.mark.django_db
def test_reset_dry_run_changes_nothing(r32):
    ko = MatchFactory(
        round=r32, matchday=None,
        home=TeamFactory(code="ESP"), away=TeamFactory(code="ARG"),
        kickoff=timezone.now() + timedelta(days=5),
    )
    PredictionFactory(match=ko, home=1, away=0)

    call_command("reset_ko_assignments", "--dry-run")

    ko.refresh_from_db()
    assert ko.home is not None and ko.away is not None
    assert Prediction.objects.filter(match=ko).count() == 1


@pytest.mark.django_db
def test_reset_ignores_group_matches(r32):
    groups = RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)
    gm = MatchFactory(
        round=groups, matchday=1,
        home=TeamFactory(code="ESP"), away=TeamFactory(code="ARG"),
        kickoff=timezone.now() + timedelta(days=1),
    )

    call_command("reset_ko_assignments")

    gm.refresh_from_db()
    assert gm.home is not None and gm.away is not None
```

- [ ] **Step 2: Ejecutar y verlo fallar**

Run: `pytest competition/tests/test_reset_ko_assignments_command.py -v`
Expected: FAIL — `CommandError: Unknown command 'reset_ko_assignments'`.

- [ ] **Step 3: Implementar el comando**

Crear `competition/management/commands/reset_ko_assignments.py`:

```python
from django.core.management.base import BaseCommand
from django.db.models import Q

from competition.models import Match, Prediction

KO_ROUND_IDS = ("r32", "r16", "qf", "sf", "final")


class Command(BaseCommand):
    help = (
        "Nulifica los equipos y borra los pronósticos de los cruces de "
        "eliminatoria SIN resultado oficial. Sirve para limpiar los cruces "
        "creados/auto-asignados de forma incorrecta. Usa --dry-run para "
        "previsualizar sin escribir."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Lista lo que se haría sin modificar la base de datos.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]

        # No finalizados: excluimos los que tienen ambos marcadores.
        unfinished_ko = Match.objects.filter(round_id__in=KO_ROUND_IDS).exclude(
            result_home__isnull=False, result_away__isnull=False
        )
        affected = unfinished_ko.filter(Q(home__isnull=False) | Q(away__isnull=False))
        affected_ids = list(affected.values_list("id", flat=True))
        pred_count = Prediction.objects.filter(match_id__in=affected_ids).count()

        if dry_run:
            self.stdout.write(
                f"[dry-run] {len(affected_ids)} cruce(s) KO se nulificarían y "
                f"{pred_count} pronóstico(s) se borrarían."
            )
            return

        Prediction.objects.filter(match_id__in=affected_ids).delete()
        Match.objects.filter(id__in=affected_ids).update(home=None, away=None)
        self.stdout.write(
            self.style.SUCCESS(
                f"Reseteados {len(affected_ids)} cruce(s) KO y borrados "
                f"{pred_count} pronóstico(s)."
            )
        )
```

- [ ] **Step 4: Ejecutar los tests del comando**

Run: `pytest competition/tests/test_reset_ko_assignments_command.py -v`
Expected: PASS (los 4 tests).

- [ ] **Step 5: Commit**

```bash
git add competition/management/commands/reset_ko_assignments.py competition/tests/test_reset_ko_assignments_command.py
git commit -m "feat(ko): comando reset_ko_assignments para limpiar cruces mal creados"
```

---

### Task 8: Verificación final e integración

- [ ] **Step 1: Suite completa**

Run: `pytest -q`
Expected: toda la suite en verde. Si algún test ajeno referencia `assign_teams`, `_ko_canvas.html`, `pairs` o `feeds_into_code`, actualizarlo a la nueva API (columnas / `competicion:edit`).

- [ ] **Step 2: Lint/format del proyecto (si aplica)**

Run: el comando de lint/format habitual del repo (p. ej. `ruff check .` y `ruff format --check .` si existen; consultar `pyproject.toml`).
Expected: sin errores. Corregir lo que marque.

- [ ] **Step 3: Verificación manual (o delegada al usuario)**

Comprobar en la app:
- `/?round=r32` … `/?round=final`: columnas por ronda, orden correcto, chips y arrastre.
- Resultados → "Editar partido" en un cruce: asignar equipos + fecha/hora, guardar; el partido aparece en su columna con el nuevo horario.
- Editar equipos de un partido con pronósticos: pide confirmación; con la casilla marcada, los borra.
- Resolver un partido de grupos: el siguiente cruce KO permanece "Por definir".

Si no puedes levantar el servidor en este entorno, indícalo y deja esta verificación para el usuario.
