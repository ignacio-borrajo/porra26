# Plan — Colapsar empates múltiples en el podio

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cuando 3+ jugadores comparten un puesto del podio (1º/2º/3º), reemplazar la lista vertical de avatares por un bloque colapsado "Varios (N)" con popover hover+click que muestra a todos los empatados. Aplica a la sidebar de `/competicion/` y a las dos columnas de `/rankings/?tab=general`.

**Architecture:** Cambio puramente front-end. Toda la lógica vive en `templates/partials/_podium_step.html` (que recibe la lista `rows` agrupada por posición desde `_leaderboard_panel.html`). El umbral se decide con `rows|length >= 3`. CSS nuevo bajo `static/css/styles.css`. JS mínimo (~25 líneas) en `static/js/podium-tied.js` cargado desde `base.html`.

**Tech Stack:** Django 5, Python 3.12, pytest, ruff, plantillas server-side, CSS3, JS vanilla.

Spec: `docs/superpowers/specs/2026-06-04-podio-empate-varios-design.md`.

---

## Archivos afectados

- **Modificar:** `templates/partials/_podium_step.html`
- **Modificar:** `static/css/styles.css`
- **Crear:** `static/js/podium-tied.js`
- **Modificar:** `templates/base.html`
- **Crear:** `competition/tests/test_podium_tied.py`

---

## Task 1 — Tests rojos del template colapsado

**Files:**
- Test (new): `competition/tests/test_podium_tied.py`

- [ ] **Paso 1: Crear el test file con 4 tests que renderizan `_leaderboard_panel.html` con datos sintéticos.**

```python
from django.template.loader import render_to_string

from competition.services.standings import StandingRow


def _row(player_id: int, name: str, position: int = 1, pts: int = 30):
    return StandingRow(
        position=position,
        is_tied=True,
        is_first_in_tie=(player_id == 1),
        player_id=player_id,
        name=name,
        email=f"{name.lower()}@x.com",
        pts=pts,
        hits=0,
        exact_hits=0,
    )


def _users(rows):
    class U:
        def __init__(self, id, name):
            self.id = id
            self.first_name = name
            self.last_name = ""
            self.email = f"{name.lower()}@x.com"
            self.avatar = None
    return {r.player_id: U(r.player_id, r.name) for r in rows}


def test_podium_renders_collapsed_with_three_or_more_ties():
    rows = [_row(i, n) for i, n in [(1, "Ana"), (2, "Borja"), (3, "Carla")]]
    html = render_to_string(
        "partials/_leaderboard_panel.html",
        {"rows": rows, "users": _users(rows), "me": None, "max_pts": 30},
    )
    assert "Varios (3)" in html
    assert 'class="podium-tied' in html


def test_podium_two_ties_still_renders_avatars_stacked():
    rows = [_row(i, n) for i, n in [(1, "Ana"), (2, "Borja")]]
    html = render_to_string(
        "partials/_leaderboard_panel.html",
        {"rows": rows, "users": _users(rows), "me": None, "max_pts": 30},
    )
    assert "Varios (" not in html
    assert "Ana" in html and "Borja" in html


def test_podium_tooltip_lists_all_tied_names():
    rows = [_row(i, n) for i, n in [(1, "Ana"), (2, "Borja"), (3, "Carla"), (4, "Dani")]]
    html = render_to_string(
        "partials/_leaderboard_panel.html",
        {"rows": rows, "users": _users(rows), "me": None, "max_pts": 30},
    )
    assert "podium-tied__tooltip" in html
    for name in ("Ana", "Borja", "Carla", "Dani"):
        assert name in html


def test_podium_tied_is_me_class_applied_when_user_in_group():
    rows = [_row(i, n) for i, n in [(1, "Ana"), (2, "Borja"), (3, "Carla")]]
    me = type("Me", (), {"id": 2})()
    html = render_to_string(
        "partials/_leaderboard_panel.html",
        {"rows": rows, "users": _users(rows), "me": me, "max_pts": 30},
    )
    assert "podium-tied is-me" in html or 'class="podium-tied is-me' in html
```

- [ ] **Paso 2: Ejecutar pytest → los 4 tests fallan.**

Run: `python -m pytest competition/tests/test_podium_tied.py -v`
Esperado: 4 failures (el primero porque "Varios (3)" no está; los siguientes por las clases nuevas).

---

## Task 2 — Implementar la rama colapsada en `_podium_step.html`

**Files:**
- Modify: `templates/partials/_podium_step.html`

- [ ] **Paso 1: Reescribir el template con dos ramas.**

```django
{% load icons avatar_extras %}
{% with first=rows.0 multi=rows|length %}
{% if multi < 3 %}
<div class="podium-slot podium-slot--{{ rank }}{% if multi > 1 %} podium-slot--multi{% endif %} pop">
  <div class="podium-medal" aria-hidden="true">
    {% if rank == 1 %}🥇{% elif rank == 2 %}🥈{% else %}🥉{% endif %}
  </div>
  <ul class="podium-people" role="list">
    {% for r in rows %}
    <li class="podium-person{% if me and r.player_id == me.id %} is-me{% endif %}">
      {% with u=users|get_item:r.player_id %}
        {% if u %}
          {% if rank == 1 and multi == 1 %}
            {% include "partials/_avatar.html" with u=u size=50 %}
          {% else %}
            {% include "partials/_avatar.html" with u=u size=42 %}
          {% endif %}
        {% endif %}
      {% endwith %}
      <span class="podium-name display{% if me and r.player_id == me.id %} is-me{% endif %}" title="{{ r.name }}">
        {% if me and r.player_id == me.id %}Tú{% else %}{{ r.name }}{% endif %}
      </span>
    </li>
    {% endfor %}
  </ul>
  <div class="podium-pts mono grad-text">{{ first.pts }}</div>
  <div class="podium-pedestal podium-pedestal--{{ rank }}">
    <span class="podium-rank-number">{% if multi > 1 %}={% endif %}{{ rank }}</span>
  </div>
</div>
{% else %}
{# Rama colapsada: 3+ empatados #}
{% with me_in_group=False %}
  {% if me %}
    {% for r in rows %}{% if r.player_id == me.id %}{% with me_in_group=True %}{% endwith %}{% endif %}{% endfor %}
  {% endif %}
{% endwith %}
<div class="podium-slot podium-slot--{{ rank }} podium-slot--collapsed pop">
  <div class="podium-medal" aria-hidden="true">
    {% if rank == 1 %}🥇{% elif rank == 2 %}🥈{% else %}🥉{% endif %}
  </div>
  <button type="button"
          class="podium-tied{% for r in rows %}{% if me and r.player_id == me.id %} is-me{% endif %}{% endfor %}"
          aria-haspopup="dialog"
          aria-expanded="false"
          aria-label="Ver {{ multi }} jugadores empatados en {{ rank }}º">
    <span class="podium-tied__icon" aria-hidden="true">{% icon "users" width=22 height=22 %}</span>
    <span class="podium-tied__label display">Varios ({{ multi }})</span>
    <div class="podium-tied__tooltip" role="dialog" aria-label="Empatados en {{ rank }}º">
      <div class="podium-tied__head eyebrow">Empatados en ={{ rank }}º · {{ first.pts }} pts</div>
      <ul class="podium-tied__list no-scrollbar">
        {% for r in rows %}
        <li class="podium-tied__item{% if me and r.player_id == me.id %} is-me{% endif %}">
          {% with u=users|get_item:r.player_id %}
            {% if u %}{% include "partials/_avatar.html" with u=u size=22 %}{% endif %}
          {% endwith %}
          <span>{% if me and r.player_id == me.id %}Tú{% else %}{{ r.name }}{% endif %}</span>
        </li>
        {% endfor %}
      </ul>
    </div>
  </button>
  <div class="podium-pts mono grad-text">{{ first.pts }}</div>
  <div class="podium-pedestal podium-pedestal--{{ rank }}">
    <span class="podium-rank-number">={{ rank }}</span>
  </div>
</div>
{% endif %}
{% endwith %}
```

Nota: El `{% with me_in_group=False %}` pegado a `{% for %}` no funciona en Django (las variables `{% with %}` no escapan del bloque). Implementación pragmática: usar `{% for %}` dentro del `class="podium-tied …"` para inyectar la clase `is-me` directamente (como hace el código de arriba), eliminando el bloque `me_in_group`. Aceptable porque el `for` se ejecuta dentro del atributo y como mucho añade `is-me` una vez (los IDs son únicos).

- [ ] **Paso 2: Limpiar la implementación quitando el `{% with me_in_group %}` muerto.**

Versión final del bloque colapsado (sin el `with me_in_group`):

```django
<button type="button"
        class="podium-tied{% for r in rows %}{% if me and r.player_id == me.id %} is-me{% endif %}{% endfor %}"
        aria-haspopup="dialog"
        aria-expanded="false"
        aria-label="Ver {{ multi }} jugadores empatados en {{ rank }}º">
```

- [ ] **Paso 3: Ejecutar pytest → los 4 tests deberían pasar.**

Run: `python -m pytest competition/tests/test_podium_tied.py -v`
Esperado: 4 passed.

Si el test de `is-me` falla por espaciado (`podium-tied is-me` vs `podium-tied  is-me`), ajustar el aserción del test para usar `'podium-tied' in html and 'is-me' in html` en la línea del button.

---

## Task 3 — CSS del bloque y popover

**Files:**
- Modify: `static/css/styles.css`

- [ ] **Paso 1: Localizar el bloque `Podio top-3` (línea ~1086) y añadir al final del bloque (antes de la sección `.leaderboard-table-header`) las reglas nuevas.**

```css
/* Slot colapsado para 3+ empatados */
.podium-slot--collapsed { position: relative; }

.podium-tied {
  position: relative;
  display: inline-flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px dashed var(--border-hi);
  border-radius: 14px;
  padding: 10px 14px;
  cursor: pointer;
  color: var(--text);
  font: inherit;
  transition: border-color .15s, background .15s, transform .15s;
}
.podium-tied:hover,
.podium-tied:focus-visible {
  outline: none;
  border-color: oklch(from var(--accent) l c h / 0.55);
  background: oklch(from var(--accent) l c h / 0.06);
}
.podium-tied.is-me {
  color: var(--accent);
  border-color: oklch(from var(--accent) l c h / 0.55);
}

.podium-tied__icon { display: inline-flex; opacity: 0.85; }
.podium-tied__label { font-size: 13px; font-weight: 700; line-height: 1.1; }

.podium-tied__tooltip {
  position: absolute;
  left: 50%;
  top: calc(100% + 8px);
  transform: translateX(-50%) translateY(-4px);
  min-width: 200px;
  max-width: 260px;
  max-height: 320px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--surface, oklch(from var(--bg) calc(l + 0.04) c h));
  backdrop-filter: blur(14px) saturate(140%);
  -webkit-backdrop-filter: blur(14px) saturate(140%);
  border: 1px solid var(--border-hi);
  box-shadow: 0 18px 40px -22px oklch(0 0 0 / 0.55);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity .15s, transform .15s, visibility .15s;
  z-index: 5;
  text-align: left;
}
.podium-tied:hover .podium-tied__tooltip,
.podium-tied:focus-within .podium-tied__tooltip,
.podium-tied[data-open="true"] .podium-tied__tooltip {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: translateX(-50%) translateY(0);
}

.podium-tied__head { padding-bottom: 6px; border-bottom: 1px solid var(--border); margin-bottom: 6px; font-size: 10px; }
.podium-tied__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.podium-tied__item { display: flex; align-items: center; gap: 8px; font-size: 13px; color: var(--text); }
.podium-tied__item.is-me { color: var(--accent); font-weight: 700; }
```

- [ ] **Paso 2: Verificar que `--border-hi`, `--accent`, `--bg`, `--border` y `--text` están definidos.**

Run: `grep -n "^  --border-hi\|^  --accent\|^  --bg:\|^  --border:\|^  --text:" static/css/styles.css | head`
Si alguna variable no existe, ajustar con el valor real del proyecto (mirar `:root`).

---

## Task 4 — JS toggle del popover

**Files:**
- Create: `static/js/podium-tied.js`
- Modify: `templates/base.html`

- [ ] **Paso 1: Crear el script.**

```js
(function () {
  const SEL = '.podium-tied';
  function closeAll(except) {
    document.querySelectorAll(`${SEL}[data-open="true"]`).forEach((el) => {
      if (el !== except) {
        el.removeAttribute('data-open');
        el.setAttribute('aria-expanded', 'false');
      }
    });
  }
  document.addEventListener('click', (e) => {
    const btn = e.target.closest(SEL);
    if (btn) {
      const open = btn.getAttribute('data-open') === 'true';
      closeAll(open ? null : btn);
      if (open) {
        btn.removeAttribute('data-open');
        btn.setAttribute('aria-expanded', 'false');
      } else {
        btn.setAttribute('data-open', 'true');
        btn.setAttribute('aria-expanded', 'true');
      }
      return;
    }
    if (!e.target.closest('.podium-tied__tooltip')) closeAll(null);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAll(null);
  });
})();
```

- [ ] **Paso 2: Incluir el script en `templates/base.html`.**

Justo antes de `</body>`, junto al resto de `<script>` que el proyecto ya carga:

```django
<script defer src="{% static 'js/podium-tied.js' %}"></script>
```

Si `base.html` ya carga otros scripts JS desde `static/js/`, seguir el mismo patrón (orden y atributos).

---

## Task 5 — Verificación manual con servidor

- [ ] **Paso 1: Arrancar el servidor.**

Run: `python manage.py runserver`

- [ ] **Paso 2: Asegurar fixture o seed con ≥3 empatados.**

Las fixtures de `fixtures/` suelen incluir un estado inicial con muchos jugadores a 0 puntos. Si no, hacer un seed rápido manualmente desde el admin o con shell.

- [ ] **Paso 3: Comprobar las dos pantallas.**

- `/competicion/` → sidebar derecha "Clasificación". Mirar el podio.
- `/rankings/?tab=general` → ambas columnas (General y Jornada).

- [ ] **Paso 4: Verificar interacciones.**

- Hover sobre "Varios (N)" → aparece el popover.
- Click → se queda fijo aunque se quite el ratón.
- Click fuera → cierra.
- Esc → cierra.
- Tema claro y oscuro: contraste y colores OK.
- Viewport móvil (DevTools < 480px): popover no se sale del viewport, click funciona.

---

## Task 6 — Lint y commit

- [ ] **Paso 1: Ruff format e import sort.**

Run: `ruff format . && ruff check --fix .`

- [ ] **Paso 2: Pytest del módulo afectado y suite mínima.**

Run: `python -m pytest competition/tests/test_podium_tied.py -v`
Run: `python -m pytest competition/ stats/ -q`

- [ ] **Paso 3: Commit en la rama del worktree.**

```
git add templates/partials/_podium_step.html \
        static/css/styles.css \
        static/js/podium-tied.js \
        templates/base.html \
        competition/tests/test_podium_tied.py \
        docs/superpowers/specs/2026-06-04-podio-empate-varios-design.md \
        docs/superpowers/plans/2026-06-04-podio-empate-varios.md
git commit -m "feat(podio): colapsar 3+ empatados con popover hover+click"
```

Sin push (el usuario lo decide después).

---

## Notas y riesgos

- **Compatibilidad backdrop-filter**: Safari iOS necesita `-webkit-backdrop-filter`. Ya incluido.
- **`oklch(from ...)`**: relative color syntax. Chrome 119+, Safari 16.4+, Firefox 128+. El resto del CSS del proyecto ya lo usa, así que no hay regresión.
- **Solo template**: si el día de mañana la lista de empatados cambia su contrato (`rows` deja de ser una lista por posición), el cambio rompe. La cobertura por test cubre eso.
- **Sin migración de datos** ni dependencias nuevas.
