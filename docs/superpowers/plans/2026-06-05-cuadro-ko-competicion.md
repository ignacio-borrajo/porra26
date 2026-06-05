# Cuadro completo de eliminatorias — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir el grid actual del dashboard por un cuadro de eliminatorias horizontal (R32→Final) cuando la ronda activa es KO, con navegación por chips + drag-to-pan en escritorio y carrusel en móvil, sin tocar la rama de grupos.

**Architecture:** Backend detecta `is_ko_view` y monta `ko_rounds` con todos los matches KO + `feeds_into_code` anotado por partido. Frontend renderiza un canvas con 5 columnas (`.ko-col`) y una capa SVG (`.ko-connectors`) que un módulo JS (`ko-bracket.js`) calcula al cargar y al redimensionar. El filtro `slot_label` y la rama `pending_teams` de `_match_card.html` ya existen — solo se añaden data-attributes.

**Tech Stack:** Django 5 templates, vanilla JS modules (sin framework), CSS plano en `static/css/styles.css`, pytest-django.

**Spec:** `docs/superpowers/specs/2026-06-05-cuadro-ko-competicion-design.md`

---

## File Structure

**Modificar:**
- `competition/views.py` — añadir lógica `is_ko_view` + `ko_rounds` + anotación `feeds_into_code` en `CompetitionView.get`.
- `competition/tests/test_competition_view.py` — añadir 4 tests de la nueva rama.
- `templates/competition/dashboard.html` — añadir condicional para incluir el canvas o el grid actual.
- `templates/competition/_match_card.html` — añadir 3 data-attributes en cada raíz (`<div>` para `pending_teams`, `<a>` para el resto).
- `templates/partials/_round_selector.html` — añadir `data-target-round` en cada chip.
- `static/css/styles.css` — añadir reglas para `.ko-canvas`, `.ko-col`, `.ko-col-head`, `.ko-connectors`, `.ko-dots`, breakpoint móvil, y borde dashed para cards pending_teams.

**Crear:**
- `templates/competition/_ko_canvas.html` — partial nuevo con dots + canvas + 5 columnas + svg vacío.
- `static/js/ko-bracket.js` — módulo nuevo con `init`, `scrollToActiveColumn`, `setupChipNavigation`, `setupDragToPan`, `layoutConnectors`, `setupMobileDots`.

**No tocar:** `competition/models.py`, `competition/services/bracket.py`, `competition/templatetags/competition_extras.py` (todo lo necesario ya existe).

---

## Task 1: View detecta modo KO y monta `ko_rounds`

**Files:**
- Modify: `competition/views.py:14-119` (`CompetitionView.get`)
- Test: `competition/tests/test_competition_view.py` (añadir al final)

- [ ] **Step 1: Escribir test que falle (detección de modo KO)**

Añadir al final de `competition/tests/test_competition_view.py`:

```python
def test_dashboard_ko_view_flag_for_groups(client):
    """Con ronda activa `groups`, is_ko_view es False."""
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r = client.get(reverse("competicion:dashboard") + "?round=groups")
    assert r.status_code == 200
    assert r.context["is_ko_view"] is False


def test_dashboard_ko_view_flag_for_r32(client):
    """Con ronda activa `r32`, is_ko_view es True y ko_rounds tiene 5 entradas."""
    from datetime import timedelta
    from django.utils import timezone

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    rounds_data = [
        ("r32", "Dieciseisavos", "R32", 5, 2),
        ("r16", "Octavos", "R16", 7, 3),
        ("qf", "Cuartos", "QF", 10, 4),
        ("sf", "Semifinales", "SF", 15, 5),
        ("final", "Final", "FIN", 25, 6),
    ]
    for rid, label, short, pts, order in rounds_data:
        RoundFactory(id=rid, points=pts, label=label, short=short, order=order)
    # un partido por ronda para que la columna exista
    r32 = Round.objects.get(id="r32")
    MatchFactory(round=r32, bracket_code="M73", kickoff=timezone.now() + timedelta(days=10))

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    assert r.status_code == 200
    assert r.context["is_ko_view"] is True
    assert r.context["active_ko_id"] == "r32"
    assert len(r.context["ko_rounds"]) == 5
    assert [k["round"].id for k in r.context["ko_rounds"]] == ["r32", "r16", "qf", "sf", "final"]
```

Asegurarse de que `Round` y `MatchFactory` estén en los imports (`from competition.models import Round` ya debería estar; si no, añadirlo).

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
source .venv/bin/activate
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_dashboard_ko_view_flag_for_groups competition/tests/test_competition_view.py::test_dashboard_ko_view_flag_for_r32 -v
```

Esperado: FAIL con `KeyError: 'is_ko_view'` (la clave no existe en el contexto).

- [ ] **Step 3: Implementar `is_ko_view` y `ko_rounds` en el view**

En `competition/views.py`, dentro de `CompetitionView.get`, justo antes del bloque `matchdays = sorted(…)` (línea ~19), añadir:

```python
KO_ROUND_IDS = ("r32", "r16", "qf", "sf", "final")
is_ko_view = active_id in KO_ROUND_IDS
```

Y dentro del bloque, después de calcular `matches`, antes del `return render(...)`, añadir:

```python
ko_rounds = []
if is_ko_view:
    ko_qs = (
        Match.objects.filter(round_id__in=KO_ROUND_IDS)
        .select_related("home", "away", "round")
        .order_by("round__order", "kickoff", "bracket_code")
    )
    ko_matches = list(ko_qs)
    rounds_by_id = {r.id: r for r in rounds}
    for rid in KO_ROUND_IDS:
        r_obj = rounds_by_id.get(rid)
        if r_obj is None:
            continue
        ko_rounds.append({
            "round": r_obj,
            "matches": [m for m in ko_matches if m.round_id == rid],
        })
```

En el `return render(...)`, añadir al contexto:

```python
"is_ko_view": is_ko_view,
"ko_rounds": ko_rounds,
"active_ko_id": active_id if is_ko_view else None,
```

- [ ] **Step 4: Ejecutar tests para verificar que pasan**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_dashboard_ko_view_flag_for_groups competition/tests/test_competition_view.py::test_dashboard_ko_view_flag_for_r32 -v
```

Esperado: PASS.

Ejecutar también la suite completa de `test_competition_view.py` para no romper nada:

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py -v
```

Esperado: todos PASS.

- [ ] **Step 5: Commit**

```bash
git add competition/views.py competition/tests/test_competition_view.py
git commit -m "feat(competition): detecta modo KO en dashboard view (ko_rounds, active_ko_id)"
```

---

## Task 2: Anotar `feeds_into_code` en cada KO match

**Files:**
- Modify: `competition/views.py` (dentro del `if is_ko_view` añadido en Task 1)
- Test: `competition/tests/test_competition_view.py`

- [ ] **Step 1: Escribir test que falle**

Añadir al final de `test_competition_view.py`:

```python
def test_dashboard_ko_matches_have_feeds_into_code(client):
    """Cada match KO lleva feeds_into_code anotado: M73(R32) -> M89(R16), Final -> None."""
    from datetime import timedelta
    from django.utils import timezone

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)
    RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)
    final = RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)

    MatchFactory(
        round=r32,
        bracket_code="M73",
        kickoff=timezone.now() + timedelta(days=10),
    )
    MatchFactory(
        round=r16,
        bracket_code="M89",
        home=None,
        away=None,
        home_slot="WM73",
        away_slot="WM74",
        kickoff=timezone.now() + timedelta(days=15),
    )
    MatchFactory(
        round=final,
        bracket_code="M104",
        home=None,
        away=None,
        home_slot="WM101",
        away_slot="WM102",
        kickoff=timezone.now() + timedelta(days=30),
    )

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    assert r.status_code == 200
    matches_by_code = {
        m.bracket_code: m
        for entry in r.context["ko_rounds"]
        for m in entry["matches"]
    }
    assert matches_by_code["M73"].feeds_into_code == "M89"
    assert matches_by_code["M104"].feeds_into_code is None
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_dashboard_ko_matches_have_feeds_into_code -v
```

Esperado: FAIL con `AttributeError: 'Match' object has no attribute 'feeds_into_code'`.

- [ ] **Step 3: Implementar la anotación**

En `competition/views.py`, dentro del bloque `if is_ko_view:` añadido en Task 1, después de `ko_matches = list(ko_qs)` y antes del loop que llena `ko_rounds`:

```python
# Construir mapa numero_bracket -> bracket_code destino para anotar feeds_into_code.
feeds_map: dict[str, str | None] = {}
for m in ko_matches:
    for slot in (m.home_slot, m.away_slot):
        if slot.startswith("WM") and m.bracket_code:
            feeds_map[slot[2:]] = m.bracket_code
for m in ko_matches:
    if m.bracket_code and m.bracket_code.startswith("M"):
        m.feeds_into_code = feeds_map.get(m.bracket_code[1:])
    else:
        m.feeds_into_code = None
```

- [ ] **Step 4: Ejecutar test para verificar que pasa**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_dashboard_ko_matches_have_feeds_into_code -v
```

Esperado: PASS.

- [ ] **Step 5: Commit**

```bash
git add competition/views.py competition/tests/test_competition_view.py
git commit -m "feat(competition): anota feeds_into_code en cada KO match para dibujar conectores"
```

---

## Task 3: Template — condicional + partial `_ko_canvas.html`

**Files:**
- Modify: `templates/competition/dashboard.html`
- Create: `templates/competition/_ko_canvas.html`
- Test: `competition/tests/test_competition_view.py`

- [ ] **Step 1: Escribir test que falle (template muestra canvas)**

Añadir al final de `test_competition_view.py`:

```python
def test_dashboard_ko_template_renders_canvas(client):
    """En modo KO, el HTML contiene .ko-canvas con 5 columnas y un svg connectors."""
    from datetime import timedelta
    from django.utils import timezone

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)
    RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)
    RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)
    MatchFactory(round=r32, bracket_code="M73", kickoff=timezone.now() + timedelta(days=10))

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    html = r.content.decode("utf-8")
    assert 'class="ko-canvas"' in html or "ko-canvas" in html
    assert html.count('class="ko-col"') == 5
    assert "ko-connectors" in html
    assert 'data-active-round="r32"' in html
```

- [ ] **Step 2: Ejecutar test para verificar que falla**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_dashboard_ko_template_renders_canvas -v
```

Esperado: FAIL con assertion error (el HTML no contiene `ko-canvas`).

- [ ] **Step 3: Crear `templates/competition/_ko_canvas.html`**

Contenido completo del nuevo archivo:

```django
{% load static %}
<div class="ko-dots" aria-hidden="true">
  {% for entry in ko_rounds %}
    <span data-round="{{ entry.round.id }}"{% if entry.round.id == active_ko_id %} class="active"{% endif %}></span>
  {% endfor %}
</div>

<div class="ko-canvas" data-active-round="{{ active_ko_id }}">
  {% for entry in ko_rounds %}
    <section class="ko-col" data-round="{{ entry.round.id }}">
      <header class="ko-col-head">{{ entry.round.label }}</header>
      {% for m in entry.matches %}
        {% include "competition/_match_card.html" with match=m my_preds=my_preds %}
      {% empty %}
        <div class="match-card glass" style="opacity:.4;padding:18px;text-align:center">
          <span class="mono">Sin cruces aún</span>
        </div>
      {% endfor %}
    </section>
  {% endfor %}
  <svg class="ko-connectors" aria-hidden="true"></svg>
</div>

<script type="module" src="{% static 'js/ko-bracket.js' %}"></script>
```

- [ ] **Step 4: Modificar `templates/competition/dashboard.html`**

Reemplazar las líneas 9-29 actuales (el bloque `{% if open_matches %}…{% if not open_matches and not live_matches and not done_matches %}…{% endif %}`) por:

```django
    {% if is_ko_view %}
      {% include "competition/_ko_canvas.html" with ko_rounds=ko_rounds active_ko_id=active_ko_id my_preds=my_preds %}
    {% else %}
      {% if open_matches %}
      <h2 class="eyebrow" style="margin-top:24px">ABIERTOS · {{ open_matches|length }}</h2>
      <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
        {% for m in open_matches %}{% include "competition/_match_card.html" with match=m my_preds=my_preds %}{% endfor %}
      </div>
      {% endif %}
      {% if live_matches %}
      <h2 class="eyebrow" style="margin-top:24px">EN JUEGO · {{ live_matches|length }}</h2>
      <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
        {% for m in live_matches %}{% include "competition/_match_card.html" with match=m my_preds=my_preds %}{% endfor %}
      </div>
      {% endif %}
      {% if done_matches %}
      <h2 class="eyebrow" style="margin-top:24px">FINALIZADOS · {{ done_matches|length }}</h2>
      <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
        {% for m in done_matches %}{% include "competition/_match_card.html" with match=m my_preds=my_preds %}{% endfor %}
      </div>
      {% endif %}
      {% if not open_matches and not live_matches and not done_matches %}
      <p class="glass" style="padding:18px;margin-top:18px">No hay partidos en esta ronda todavía.</p>
      {% endif %}
    {% endif %}
```

- [ ] **Step 5: Ejecutar test para verificar que pasa**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_dashboard_ko_template_renders_canvas -v
```

Esperado: PASS.

Ejecutar la suite entera de competition para no romper nada:

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/ -v
```

Esperado: todos PASS salvo `test_closing_email_service.py::test_send_creates_email_with_pdf_attachment` (failing también en main, no relacionado).

- [ ] **Step 6: Commit**

```bash
git add templates/competition/dashboard.html templates/competition/_ko_canvas.html competition/tests/test_competition_view.py
git commit -m "feat(competition): renderiza canvas de bracket cuando la ronda es eliminatoria"
```

---

## Task 4: data-attributes en `_match_card.html` y `_round_selector.html`

**Files:**
- Modify: `templates/competition/_match_card.html`
- Modify: `templates/partials/_round_selector.html`
- Test: `competition/tests/test_competition_view.py`

- [ ] **Step 1: Escribir test que falle**

Añadir al final de `test_competition_view.py`:

```python
def test_match_card_has_bracket_data_attributes_in_ko(client):
    """Cada card KO incluye data-bracket-code, data-feeds-into y data-status."""
    from datetime import timedelta
    from django.utils import timezone

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)
    RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)
    RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)
    MatchFactory(round=r32, bracket_code="M73", kickoff=timezone.now() + timedelta(days=10))
    MatchFactory(
        round=r16,
        bracket_code="M89",
        home=None,
        away=None,
        home_slot="WM73",
        away_slot="WM74",
        kickoff=timezone.now() + timedelta(days=15),
    )

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    html = r.content.decode("utf-8")
    assert 'data-bracket-code="M73"' in html
    assert 'data-feeds-into="M89"' in html
    assert 'data-status="open"' in html
    assert 'data-bracket-code="M89"' in html
    assert 'data-status="pending_teams"' in html


def test_round_selector_chips_have_target_round(client):
    """Los chips llevan data-target-round con el id de la ronda."""
    from datetime import timedelta
    from django.utils import timezone

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)
    r32 = RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)
    MatchFactory(round=r32, bracket_code="M73", kickoff=timezone.now() + timedelta(days=10))

    r = client.get(reverse("competicion:dashboard") + "?round=r32")
    html = r.content.decode("utf-8")
    assert 'data-target-round="r32"' in html
    assert 'data-target-round="groups"' in html
```

- [ ] **Step 2: Ejecutar tests para verificar que fallan**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py::test_match_card_has_bracket_data_attributes_in_ko competition/tests/test_competition_view.py::test_round_selector_chips_have_target_round -v
```

Esperado: FAIL ambos (los atributos no existen).

- [ ] **Step 3: Modificar `templates/competition/_match_card.html`**

Cambiar la línea 5 (rama `pending_teams`) de:

```django
<div class="match-card glass" style="cursor:default;opacity:.85">
```

a:

```django
<div class="match-card glass"
     data-bracket-code="{{ match.bracket_code|default:'' }}"
     data-feeds-into="{{ match.feeds_into_code|default:'' }}"
     data-status="{{ st }}"
     style="cursor:default;opacity:.85">
```

Cambiar las líneas 31-35 (las tres alternativas para la rama normal: `<a href=...>`, `<a class=...>`, `<a href=...>`) añadiendo en cada `<a>` los mismos data-attributes. Sustituir:

```django
{% if match.predictions_open and request.user.is_jugador %}
<a href="{% url 'competicion:predict' match.id %}" data-modal-url="{% url 'competicion:predict' match.id %}" class="match-card glass rise">
{% elif match.editable %}
<a class="match-card glass rise" style="cursor:not-allowed">
{% else %}
<a href="{% url 'competicion:detail' match.id %}" data-modal-url="{% url 'competicion:detail' match.id %}" class="match-card glass rise{% if st == 'live' %} match-card-live{% endif %}">
{% endif %}
```

Por:

```django
{% if match.predictions_open and request.user.is_jugador %}
<a href="{% url 'competicion:predict' match.id %}"
   data-modal-url="{% url 'competicion:predict' match.id %}"
   data-bracket-code="{{ match.bracket_code|default:'' }}"
   data-feeds-into="{{ match.feeds_into_code|default:'' }}"
   data-status="{{ st }}"
   class="match-card glass rise">
{% elif match.editable %}
<a class="match-card glass rise"
   data-bracket-code="{{ match.bracket_code|default:'' }}"
   data-feeds-into="{{ match.feeds_into_code|default:'' }}"
   data-status="{{ st }}"
   style="cursor:not-allowed">
{% else %}
<a href="{% url 'competicion:detail' match.id %}"
   data-modal-url="{% url 'competicion:detail' match.id %}"
   data-bracket-code="{{ match.bracket_code|default:'' }}"
   data-feeds-into="{{ match.feeds_into_code|default:'' }}"
   data-status="{{ st }}"
   class="match-card glass rise{% if st == 'live' %} match-card-live{% endif %}">
{% endif %}
```

- [ ] **Step 4: Modificar `templates/partials/_round_selector.html`**

Cambiar:

```django
<a href="?round={{ r.id }}" class="chip {% if r.id == active %}chip-open{% endif %}" style="text-decoration:none">
```

Por:

```django
<a href="?round={{ r.id }}"
   data-target-round="{{ r.id }}"
   class="chip {% if r.id == active %}chip-open{% endif %}"
   style="text-decoration:none">
```

- [ ] **Step 5: Ejecutar tests para verificar que pasan**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest competition/tests/test_competition_view.py -v
```

Esperado: todos PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/competition/_match_card.html templates/partials/_round_selector.html competition/tests/test_competition_view.py
git commit -m "feat(competition): añade data-attrs de bracket al match card y target-round a los chips"
```

---

## Task 5: CSS — canvas, columnas, conectores, dots, breakpoint móvil

**Files:**
- Modify: `static/css/styles.css` (añadir al final)

- [ ] **Step 1: Añadir bloque CSS al final de `static/css/styles.css`**

```css
/* ============================================================
   Cuadro de eliminatorias (KO bracket)
   ============================================================ */
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
  min-height: 720px;
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
  z-index: 2;
  background: linear-gradient(180deg, rgba(11,16,32,.92), rgba(11,16,32,.55) 80%, transparent);
  padding: 4px 6px 10px;
  font: 600 12px/1 var(--font-mono, monospace);
  letter-spacing: .08em;
  text-transform: uppercase;
  color: var(--text-dim, #9aa3b2);
}

.ko-connectors {
  position: absolute;
  inset: 0;
  pointer-events: none;
  z-index: 1;
}
.ko-connectors path { fill: none; stroke-width: 2; }
.ko-connectors path[data-status="pending_teams"] {
  stroke: var(--line-muted, rgba(255,255,255,.18));
  stroke-dasharray: 4 6;
}
.ko-connectors path[data-status="open"],
.ko-connectors path[data-status="live"] {
  stroke: var(--line, rgba(255,255,255,.32));
}
.ko-connectors path[data-status="done"] {
  stroke: var(--accent, #5ee0a8);
  opacity: .85;
}

.ko-dots {
  display: none;
  justify-content: center;
  gap: 6px;
  padding: 8px 0;
}
.ko-dots span {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: var(--line-muted, rgba(255,255,255,.22));
  transition: background .2s ease, width .2s ease, height .2s ease;
}
.ko-dots span.active {
  background: var(--accent, #5ee0a8);
  width: 8px;
  height: 8px;
}

.match-card[data-status="pending_teams"] {
  border: 1px dashed var(--line-muted, rgba(255,255,255,.25));
}

@media (max-width: 768px) {
  .ko-canvas {
    gap: 0;
    padding: 12px 0;
    min-height: auto;
  }
  .ko-col { min-width: 100%; padding: 0 16px; }
  .ko-connectors { display: none; }
  .ko-dots { display: flex; }
}
```

- [ ] **Step 2: Verificación rápida (no se rompe sintaxis CSS)**

Recargar mentalmente o, si hay un linter de CSS configurado, ejecutarlo. No hay tests automatizados de CSS en el proyecto.

```bash
# Si existe alguna utilidad de CSS lint en el repo:
grep -rn "stylelint\|prettier" package.json 2>/dev/null
# Si no, saltarse.
```

- [ ] **Step 3: Commit**

```bash
git add static/css/styles.css
git commit -m "feat(competition): estilos del bracket KO (canvas, columnas, conectores, dots)"
```

---

## Task 6: JS — módulo base con `init`, scroll inicial y nav por chips

**Files:**
- Create: `static/js/ko-bracket.js`

- [ ] **Step 1: Crear `static/js/ko-bracket.js` con el esqueleto + dos features**

Contenido completo:

```javascript
const canvas = document.querySelector(".ko-canvas");
if (canvas) init(canvas);

function init(canvas) {
  scrollToActiveColumn(canvas);
  setupChipNavigation(canvas);
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
      const target = chip.dataset.targetRound;
      if (!target) return;
      const col = canvas.querySelector(`.ko-col[data-round="${target}"]`);
      if (!col) return; // ronda destino no está en el canvas (p.ej. groups) -> recarga normal
      e.preventDefault();
      col.scrollIntoView({ inline: "start", block: "nearest", behavior: "smooth" });
      history.pushState(null, "", chip.href);
    });
  });
}
```

- [ ] **Step 2: Verificación manual (rápida)**

Arrancar el servidor:

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python manage.py runserver
```

Abrir `http://localhost:8000/competition/?round=r32` (requiere haber semillado el Mundial; si no está, el canvas aparecerá pero sin columnas pobladas — basta con que la página cargue sin errores en consola).

Esperado:
- Sin errores en la consola JS.
- Si hay datos: pulsar el chip "Cuartos" hace scroll suave y la URL pasa a `?round=qf` sin recarga.

Parar el servidor (Ctrl+C).

- [ ] **Step 3: Commit**

```bash
git add static/js/ko-bracket.js
git commit -m "feat(competition): JS base del bracket (scroll inicial + nav por chips)"
```

---

## Task 7: JS — drag-to-pan en escritorio

**Files:**
- Modify: `static/js/ko-bracket.js`

- [ ] **Step 1: Añadir función `setupDragToPan` y llamada en `init`**

En `static/js/ko-bracket.js`, cambiar `init` a:

```javascript
function init(canvas) {
  scrollToActiveColumn(canvas);
  setupChipNavigation(canvas);
  if (matchMedia("(pointer:fine)").matches) setupDragToPan(canvas);
}
```

Añadir al final del archivo:

```javascript
function setupDragToPan(canvas) {
  let startX = 0;
  let startScrollLeft = 0;
  let dragging = false;

  canvas.addEventListener("pointerdown", e => {
    // No iniciar drag si el click empieza dentro de una card (preserva click navegacional)
    if (e.target.closest(".match-card")) return;
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
  const end = () => {
    dragging = false;
    canvas.classList.remove("grabbing");
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
}
```

- [ ] **Step 2: Verificación manual**

Levantar el servidor y abrir `?round=r32` en Chrome (pointer fine). Hacer click + drag sobre el fondo del canvas (no sobre una card) y comprobar que el bracket scrollea horizontalmente, y que un click corto sobre una card sigue abriendo el modal.

- [ ] **Step 3: Commit**

```bash
git add static/js/ko-bracket.js
git commit -m "feat(competition): drag-to-pan en el canvas del bracket en escritorio"
```

---

## Task 8: JS — conectores SVG

**Files:**
- Modify: `static/js/ko-bracket.js`

- [ ] **Step 1: Añadir funciones de layout de conectores**

En `static/js/ko-bracket.js`, cambiar `init` a:

```javascript
function init(canvas) {
  scrollToActiveColumn(canvas);
  setupChipNavigation(canvas);
  if (matchMedia("(pointer:fine)").matches) setupDragToPan(canvas);
  setupConnectors(canvas);
  window.addEventListener("resize", debounceRAF(() => layoutConnectors(canvas)));
}
```

Añadir al final del archivo:

```javascript
function setupConnectors(canvas) {
  layoutConnectors(canvas);
  const ro = new ResizeObserver(debounceRAF(() => layoutConnectors(canvas)));
  ro.observe(canvas);
  canvas.querySelectorAll(".ko-col").forEach(col => ro.observe(col));
}

function layoutConnectors(canvas) {
  const svg = canvas.querySelector(".ko-connectors");
  if (!svg) return;
  if (getComputedStyle(svg).display === "none") {
    svg.innerHTML = "";
    return;
  }
  const cards = [...canvas.querySelectorAll(".match-card[data-bracket-code]")].filter(c => c.dataset.bracketCode);
  const byCode = new Map(cards.map(c => [c.dataset.bracketCode, c]));
  const canvasRect = canvas.getBoundingClientRect();
  const offsetX = canvas.scrollLeft;
  const offsetY = canvas.scrollTop;
  const w = canvas.scrollWidth;
  const h = canvas.scrollHeight;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);

  const groups = new Map();
  for (const card of cards) {
    const dest = card.dataset.feedsInto;
    if (!dest) continue;
    if (!groups.has(dest)) groups.set(dest, []);
    groups.get(dest).push(card);
  }

  const ns = "http://www.w3.org/2000/svg";
  svg.innerHTML = "";
  for (const [destCode, siblings] of groups) {
    const dest = byCode.get(destCode);
    if (!dest || siblings.length === 0) continue;
    const sorted = siblings
      .map(c => ({ card: c, rect: rel(c, canvasRect, offsetX, offsetY) }))
      .sort((a, b) => a.rect.top - b.rect.top);
    const destRect = rel(dest, canvasRect, offsetX, offsetY);
    const destY = destRect.top + destRect.height / 2;
    const midX = (Math.max(...sorted.map(s => s.rect.right)) + destRect.left) / 2;
    const status = dest.dataset.status || "open";
    for (const s of sorted) {
      const y = s.rect.top + s.rect.height / 2;
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", `M ${s.rect.right} ${y} H ${midX} V ${destY} H ${destRect.left}`);
      path.setAttribute("data-status", status);
      svg.appendChild(path);
    }
  }
}

function rel(el, canvasRect, offsetX, offsetY) {
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

function debounceRAF(fn) {
  let raf;
  return (...args) => {
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => fn(...args));
  };
}
```

- [ ] **Step 2: Verificación manual**

Levantar el servidor y abrir `?round=r32`. Comprobar:
- Las líneas SVG aparecen conectando cada par de cards hermanas con su destino.
- Las líneas hacia partidos `pending_teams` salen punteadas y gris.
- Las líneas hacia partidos `done` salen sólidas en color accent.
- Al redimensionar la ventana, las líneas se recalculan correctamente.
- En móvil (DevTools ≤ 768px) las líneas desaparecen.

- [ ] **Step 3: Commit**

```bash
git add static/js/ko-bracket.js
git commit -m "feat(competition): dibuja conectores SVG entre cruces hermanos del bracket"
```

---

## Task 9: JS — indicador de puntos en móvil

**Files:**
- Modify: `static/js/ko-bracket.js`

- [ ] **Step 1: Añadir `setupMobileDots`**

En `static/js/ko-bracket.js`, cambiar `init` a:

```javascript
function init(canvas) {
  scrollToActiveColumn(canvas);
  setupChipNavigation(canvas);
  if (matchMedia("(pointer:fine)").matches) setupDragToPan(canvas);
  setupConnectors(canvas);
  setupMobileDots(canvas);
  window.addEventListener("resize", debounceRAF(() => layoutConnectors(canvas)));
}
```

Añadir al final:

```javascript
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
```

- [ ] **Step 2: Verificación manual móvil**

DevTools en modo responsive ≤ 768px (iPhone 13 por ejemplo). Abrir `?round=qf`. Comprobar:
- Solo una columna ocupa la pantalla.
- Swipe lateral cambia de ronda con snap.
- El punto activo en `.ko-dots` corresponde a la columna visible.

- [ ] **Step 3: Commit**

```bash
git add static/js/ko-bracket.js
git commit -m "feat(competition): indicador de puntos en móvil sincronizado con la columna visible"
```

---

## Task 10: Verificación full-stack y PR

- [ ] **Step 1: Suite completa de tests**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python -m pytest -q
```

Esperado: todos PASS salvo `test_closing_email_service.py::test_send_creates_email_with_pdf_attachment` (preexistente, ya falla en main).

- [ ] **Step 2: Sembrar Mundial y verificar el flujo end-to-end manualmente**

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python manage.py migrate
DJANGO_SETTINGS_MODULE=porra26.settings.dev python manage.py loaddata fixtures/rounds.json fixtures/teams.json fixtures/world_cup_2026.json
DJANGO_SETTINGS_MODULE=porra26.settings.dev python manage.py runserver
```

Crear un jugador (vía shell) y navegar a `/competition/?round=r32`. Comprobar la lista de la sección "Verificación manual" del spec:

1. 5 columnas visibles, scroll horizontal interno sin barras.
2. Drag-to-pan en el fondo del canvas; click en card abre el modal.
3. Chip "Cuartos" → scroll suave a la columna QF pegada al borde izquierdo, URL `?round=qf` sin recarga.
4. Resolver un partido R32 vía gestor → al recargar, el conector R32→R16 cambia de stroke.
5. Cambiar a `?round=groups` → recarga, vista del grid actual sin canvas.
6. Móvil (DevTools): una columna por viewport, dots sincronizados, sin líneas SVG.
7. Deep-link `?round=qf` → arranca con la columna QF pegada al borde.

- [ ] **Step 3: Push y crear PR**

```bash
git push -u origin worktree-ko-bracket-competicion
gh pr create --base main --title "feat(competition): cuadro completo de eliminatorias con bracket navegable" --body "$(cat <<'EOF'
## Summary
- Reemplaza el grid de tarjetas del dashboard de Competición por un canvas de bracket cuando la ronda activa es eliminatoria (R32 → Final). La rama de grupos queda intacta.
- Navegación: chips de ronda hacen scroll-snap a la columna correspondiente sin recargar. En escritorio se añade drag-to-pan sobre el fondo del canvas. En móvil cada ronda es una página completa con swipe e indicador de puntos.
- Conectores SVG entre cruces hermanos, coloreados según el estado del partido destino (pendiente / abierto / live / finalizado).

## Test plan
- [x] Backend: 5 tests nuevos en `test_competition_view.py` (modo KO, ko_rounds, feeds_into_code, data-attrs, target-round).
- [ ] Manual escritorio: scroll, chip → scrollIntoView, drag-to-pan, conectores correctos al resolver partidos.
- [ ] Manual móvil ≤ 768px: una columna por viewport, dots sincronizados, sin líneas SVG.
- [ ] Deep-link `?round=qf` arranca con la columna QF pegada al borde izquierdo.

Spec: `docs/superpowers/specs/2026-06-05-cuadro-ko-competicion-design.md`
EOF
)"
```

- [ ] **Step 4: Esperar a que CI pase y mergear**

```bash
gh pr checks --watch
gh pr merge --squash --auto
```

Tras el merge, Railway desplegará a `laporradeljefe.es` desde main automáticamente.

---

## Self-Review

**Spec coverage:**
- "Detección de modo KO": Task 1 ✓
- "Selector de ronda en modo KO" (chip scrollIntoView + pushState): Task 4 (data-attr) + Task 6 (handler) ✓
- "Estructura del cuadro" (.ko-canvas, .ko-col, svg overlay): Task 3 + Task 5 ✓
- "Conectores SVG" (path doble L, colores por estado): Task 8 + Task 5 ✓
- "Cards de slot pendiente": ya existente en `_match_card.html` + Task 4 (data-status) + Task 5 (borde dashed) ✓
- "Navegación: chips, drag, scroll-snap, posición inicial": Task 5 (scroll-snap CSS) + Task 6 (scroll inicial + chips) + Task 7 (drag) ✓
- "Móvil ≤ 768px": Task 5 (media query) + Task 9 (dots) ✓
- "Cambios en views.py" (ko_rounds, feeds_into_code, active_ko_id): Task 1 + Task 2 ✓
- "Cambios en dashboard.html" (condicional): Task 3 ✓
- "_ko_canvas.html (nuevo)": Task 3 ✓
- "_match_card.html (data-attrs)": Task 4 ✓
- "_round_selector.html (data-target-round)": Task 4 ✓
- "ko-bracket.js (nuevo)": Tasks 6, 7, 8, 9 ✓
- "CSS styles.css": Task 5 ✓

**Placeholders:** Ninguno. Todos los pasos llevan código exacto o comandos exactos.

**Type consistency:** `is_ko_view`, `ko_rounds`, `active_ko_id`, `feeds_into_code`, `KO_ROUND_IDS` se usan con el mismo nombre en todas las tasks. Nombres de funciones JS (`init`, `scrollToActiveColumn`, `setupChipNavigation`, `setupDragToPan`, `setupConnectors`, `layoutConnectors`, `setupMobileDots`, `rel`, `debounceRAF`) son consistentes entre Task 6, 7, 8, 9.
