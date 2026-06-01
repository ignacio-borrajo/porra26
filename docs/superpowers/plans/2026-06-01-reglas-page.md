# Página de Reglas — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir una página interna `/reglas/` que documente para los jugadores cómo funciona la porra, accesible desde la topbar, con valores leídos del modelo (puntos por ronda, bote, premios) y la copia coherente con `docs/DATA_MODEL.md`.

**Architecture:** Vista Django CBV en la app `core`, plantilla en `templates/core/rules.html` que extiende `base.html`, valores dinámicos del context (`Round`, `PotSettings`, `Prize`) y constantes (`BET_CLOSE_HOURS`, `RULES_UPDATED_AT`). Componentes visuales reutilizan `.glass`, `.chip`, `.eyebrow`, `.grad-text`, tokens existentes y un icono nuevo `book.svg`. Compromiso de mantenimiento: cuando cambien las reglas reales, esta página acompaña.

**Tech Stack:** Django 5, pytest-django, factory_boy, freezegun, plantillas Django + CSS de la app, SVG inline para el timeline.

**Spec:** `docs/superpowers/specs/2026-06-01-reglas-page-design.md` (lectura previa obligatoria).

---

## Mapa de archivos

| Archivo | Acción | Responsabilidad |
|---------|--------|------------------|
| `competition/models.py` | Modificar | Extraer `BET_CLOSE_HOURS = 2` y usarlo en la lógica de cierre (línea 63). |
| `porra26/settings/base.py` | Modificar | Añadir `RULES_UPDATED_AT = date(2026, 6, 1)`. |
| `core/views.py` | Modificar | Añadir `RulesView` (LoginRequiredMixin + TemplateView). |
| `core/urls.py` | Crear | URL `path("", RulesView.as_view(), name="rules")`. |
| `porra26/urls.py` | Modificar | Registrar `core.urls` bajo `path("reglas/", ..., namespace="core")`. |
| `static/icons/book.svg` | Crear | Icono libro abierto, trazo `currentColor`, mismo estilo que el set. |
| `templates/partials/_topbar.html` | Modificar | Añadir enlace "Reglas" con icono `book`. |
| `templates/core/rules.html` | Crear | Plantilla con hero + 5 cards + pie. |
| `static/css/styles.css` | Modificar (append) | Clases `.rules-timeline`, `.rules-example-card`, `.rules-medal` y media queries. |
| `core/tests/test_rules_view.py` | Crear | Tests de vista, contexto y contenido. |
| `core/tests/test_topbar.py` | Crear | Test de que el enlace "Reglas" aparece en topbar. |
| `competition/tests/test_bet_close_hours.py` | Crear | Test de que `BET_CLOSE_HOURS` está expuesta y vale 2 (regresión). |

---

## Task 1: Extraer `BET_CLOSE_HOURS` en `competition/models.py`

**Files:**
- Modify: `competition/models.py:1-70` (añadir constante arriba y reemplazar literal en línea 63).
- Test: `competition/tests/test_bet_close_hours.py` (crear).

- [ ] **Step 1: Escribir test que falla**

Crear `competition/tests/test_bet_close_hours.py`:

```python
from datetime import timedelta

from competition.models import BET_CLOSE_HOURS


def test_bet_close_hours_is_two():
    assert BET_CLOSE_HOURS == 2


def test_bet_close_hours_can_build_timedelta():
    assert timedelta(hours=BET_CLOSE_HOURS) == timedelta(hours=2)
```

- [ ] **Step 2: Ejecutar el test y confirmar que falla**

Run: `pytest competition/tests/test_bet_close_hours.py -v`
Expected: FAIL con `ImportError: cannot import name 'BET_CLOSE_HOURS' from 'competition.models'`.

- [ ] **Step 3: Añadir la constante y usarla en la lógica de cierre**

Editar `competition/models.py`. Bajo los imports añadir:

```python
BET_CLOSE_HOURS = 2
```

En el método `status` (línea 63 aprox.) cambiar:

```python
close_at = self.kickoff - timedelta(hours=2)
```

por:

```python
close_at = self.kickoff - timedelta(hours=BET_CLOSE_HOURS)
```

**No tocar la línea 68** (`if close_at - now <= timedelta(hours=2):` — define la ventana del estado `closing`, regla distinta).

- [ ] **Step 4: Ejecutar test nuevo y la suite de competition**

Run:
```
pytest competition/tests/test_bet_close_hours.py competition/tests/test_matchday_gate.py -v
```
Expected: PASS en todo.

- [ ] **Step 5: Commit**

```bash
git add competition/models.py competition/tests/test_bet_close_hours.py
git commit -m "refactor(competition): extraer BET_CLOSE_HOURS para reutilizar en página de reglas"
```

---

## Task 2: Añadir `RULES_UPDATED_AT` a settings

**Files:**
- Modify: `porra26/settings/base.py` (añadir constante al final del fichero).
- Test: `core/tests/test_rules_view.py` cubrirá el uso en Task 3.

- [ ] **Step 1: Añadir la constante en `settings/base.py`**

Localizar el final del fichero y añadir:

```python
from datetime import date

# Fecha de la última publicación del reglamento (página /reglas/).
# Actualizar a mano cuando se cambien las reglas de la porra.
RULES_UPDATED_AT = date(2026, 6, 1)
```

Si ya existe un import de `date`/`datetime` arriba, mover el import allí.

- [ ] **Step 2: Verificar que Django carga sin error**

Run: `python manage.py check`
Expected: `System check identified no issues (0 silenced).`

- [ ] **Step 3: Commit**

```bash
git add porra26/settings/base.py
git commit -m "feat(settings): RULES_UPDATED_AT para la página de reglas"
```

---

## Task 3: Crear `RulesView`, URL y test de vista

**Files:**
- Modify: `core/views.py`
- Create: `core/urls.py`
- Modify: `porra26/urls.py`
- Create: `core/tests/test_rules_view.py`

- [ ] **Step 1: Escribir test que falla**

Crear `core/tests/test_rules_view.py`:

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from competition.tests.factories import RoundFactory
from pot.models import PotSettings


@pytest.mark.django_db
def test_rules_redirects_anonymous(client):
    r = client.get(reverse("core:rules"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_rules_renders_for_authenticated(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_rules_context_has_required_keys(client):
    RoundFactory(id="groups", label="Fase de grupos", short="GRP", points=3, order=1)
    PotSettings.load()  # asegura instancia
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    ctx = r.context
    assert "rounds" in ctx and list(ctx["rounds"])  # no vacío
    assert "pot_per_player" in ctx
    assert "pot_prizes" in ctx
    assert ctx["bet_close_hours"] == 2
    assert "rules_updated_at" in ctx
```

- [ ] **Step 2: Ejecutar y confirmar fallo**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: FAIL con `NoReverseMatch` para `core:rules`.

- [ ] **Step 3: Implementar la vista**

Reemplazar el contenido de `core/views.py` por:

```python
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import TemplateView

from competition.models import BET_CLOSE_HOURS, Round
from pot.models import PotSettings, Prize


class RulesView(LoginRequiredMixin, TemplateView):
    template_name = "core/rules.html"

    def get_context_data(self, **kwargs):
        ctx = super().get_context_data(**kwargs)
        ctx["rounds"] = Round.objects.all()
        ctx["pot_per_player"] = PotSettings.load().per_player
        ctx["pot_prizes"] = Prize.objects.filter(scope="global").order_by("position")
        ctx["bet_close_hours"] = BET_CLOSE_HOURS
        ctx["rules_updated_at"] = settings.RULES_UPDATED_AT
        return ctx
```

- [ ] **Step 4: Crear `core/urls.py`**

```python
from django.urls import path

from . import views

urlpatterns = [
    path("", views.RulesView.as_view(), name="rules"),
]
```

- [ ] **Step 5: Registrar en `porra26/urls.py`**

Editar `porra26/urls.py` para añadir la línea de `core`:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("competicion/", include(("competition.urls", "competicion"), namespace="competicion")),
    path("stats/", include(("stats.urls", "stats"), namespace="stats")),
    path("gestion/", include(("pot.urls", "pot"), namespace="pot")),
    path("reglas/", include(("core.urls", "core"), namespace="core")),
]
```

- [ ] **Step 6: Crear plantilla mínima para que la vista responda 200**

Crear `templates/core/rules.html`:

```django
{% extends "base.html" %}
{% block title %}Reglas · PORRA 26{% endblock %}
{% block main %}
<div style="max-width:880px;margin:0 auto">
  <h1>Reglas</h1>
</div>
{% endblock %}
```

- [ ] **Step 7: Ejecutar y verificar tests verdes**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS en los tres tests.

- [ ] **Step 8: Commit**

```bash
git add core/views.py core/urls.py porra26/urls.py templates/core/rules.html core/tests/test_rules_view.py
git commit -m "feat(core): RulesView con auth, URL /reglas/ y plantilla mínima"
```

---

## Task 4: Icono `book` y enlace en topbar

**Files:**
- Create: `static/icons/book.svg`
- Modify: `templates/partials/_topbar.html`
- Create: `core/tests/test_topbar.py`

- [ ] **Step 1: Escribir test de topbar que falla**

Crear `core/tests/test_topbar.py`:

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory


@pytest.mark.django_db
def test_topbar_has_rules_link(client):
    client.force_login(UserFactory())
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("core:rules") in content
    assert "Reglas" in content


@pytest.mark.django_db
def test_rules_active_class_on_rules_page(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    href = reverse("core:rules")
    # El enlace activo lleva clase is-active. Comprobamos que ambos coinciden en la cadena.
    assert f'href="{href}" class="nav-item is-active"' in content or \
           f'href="{href}"' in content and "is-active" in content
```

- [ ] **Step 2: Ejecutar y confirmar fallo**

Run: `pytest core/tests/test_topbar.py -v`
Expected: FAIL (el enlace no está en la topbar todavía).

- [ ] **Step 3: Crear `static/icons/book.svg`**

Contenido exacto (mismo estilo del set):

```xml
<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round">
  <path d="M4 5a2 2 0 0 1 2-2h5v17H6a2 2 0 0 1-2-2z"/>
  <path d="M20 5a2 2 0 0 0-2-2h-5v17h5a2 2 0 0 0 2-2z"/>
  <path d="M11 20l1-1 1 1"/>
</svg>
```

- [ ] **Step 4: Añadir enlace en `templates/partials/_topbar.html`**

Editar el bloque de navegación (entre el enlace de Rankings y el de Jugadores). Cambiar:

```django
<a href="{% url 'stats:rankings' %}" class="nav-item{% if url_name == 'rankings' %} is-active{% endif %}">
  {% icon "trophy" width=17 height=17 %} Rankings
</a>
{% if user.is_gestor %}
```

a:

```django
<a href="{% url 'stats:rankings' %}" class="nav-item{% if url_name == 'rankings' %} is-active{% endif %}">
  {% icon "trophy" width=17 height=17 %} Rankings
</a>
<a href="{% url 'core:rules' %}" class="nav-item{% if ns == 'core' and url_name == 'rules' %} is-active{% endif %}">
  {% icon "book" width=17 height=17 %} Reglas
</a>
{% if user.is_gestor %}
```

- [ ] **Step 5: Ejecutar tests**

Run: `pytest core/tests/test_topbar.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add static/icons/book.svg templates/partials/_topbar.html core/tests/test_topbar.py
git commit -m "feat(ui): enlace Reglas en topbar con icono libro"
```

---

## Task 5: Hero + Card 1 "Sistema de puntos"

**Files:**
- Modify: `templates/core/rules.html`
- Modify: `core/tests/test_rules_view.py` (añadir asserciones de contenido).

- [ ] **Step 1: Escribir asserciones que fallan**

Añadir al final de `core/tests/test_rules_view.py`:

```python
@pytest.mark.django_db
def test_rules_renders_points_card(client):
    RoundFactory(id="groups", label="Fase de grupos", short="GRP", points=3, order=1)
    RoundFactory(id="r32", label="Dieciseisavos", short="R32", points=5, order=2)
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Cómo funciona la porra" in content
    assert "Sistema de puntos" in content
    # Ejemplos
    assert "Marcador exacto" in content
    assert "Solo el resultado" in content
    assert "Fallo" in content
    # Tabla de rondas con puntos
    assert "Fase de grupos" in content
    assert "Dieciseisavos" in content
    assert "+3 pts" in content or ">3<" in content
```

- [ ] **Step 2: Ejecutar y confirmar fallo**

Run: `pytest core/tests/test_rules_view.py::test_rules_renders_points_card -v`
Expected: FAIL.

- [ ] **Step 3: Reescribir `templates/core/rules.html` con hero + Card 1**

```django
{% extends "base.html" %}
{% load icons %}
{% block title %}Reglas · PORRA 26{% endblock %}
{% block main %}
{# Mantener sincronizado con docs/DATA_MODEL.md §2, §3, §5 — cambios de reglas se reflejan también aquí. #}
<div style="max-width:880px;margin:0 auto;display:flex;flex-direction:column;gap:24px">

  <header class="stagger" style="display:flex;flex-direction:column;gap:8px">
    <span class="eyebrow">MUNDIAL 2026 · REGLAS</span>
    <h1 style="font-family:Sora,sans-serif;font-weight:800;letter-spacing:-0.03em;font-size:clamp(32px,4vw,44px);margin:0">
      Cómo funciona la porra
    </h1>
    <p style="color:var(--text-dim);font-size:16px;margin:0">
      Todo lo que necesitas saber para jugar — y para no quedarte fuera del bote.
    </p>
  </header>

  <section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:18px">
    <header style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">01 · Sistema de puntos</span>
      <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:22px">Cuánto se gana en cada partido</h2>
      <p style="color:var(--text-dim);margin:0">Cada partido te da puntos según lo cerca que estés del resultado.</p>
    </header>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));gap:12px">
      {# Ejemplo 1: Marcador exacto #}
      <article class="rules-example-card" data-variant="exact">
        <header class="eyebrow" style="color:var(--c-lime)">Marcador exacto</header>
        <div class="rules-example-score">
          <span>🇪🇸 España</span><strong>2 — 1</strong><span>Argentina 🇦🇷</span>
        </div>
        <p>Tu apuesta: <strong>2-1</strong></p>
        <span class="chip" style="color:var(--c-lime);border-color:oklch(from var(--c-lime) l c h / 0.4)">+3 pts · exacto</span>
      </article>
      {# Ejemplo 2: Solo el resultado #}
      <article class="rules-example-card" data-variant="partial">
        <header class="eyebrow" style="color:var(--c-cyan)">Solo el resultado</header>
        <div class="rules-example-score">
          <span>🇪🇸 España</span><strong>3 — 2</strong><span>Argentina 🇦🇷</span>
        </div>
        <p>Tu apuesta: <strong>2-1</strong></p>
        <span class="chip" style="color:var(--c-cyan);border-color:oklch(from var(--c-cyan) l c h / 0.4)">+1 pt</span>
      </article>
      {# Ejemplo 3: Fallo #}
      <article class="rules-example-card" data-variant="miss">
        <header class="eyebrow" style="color:var(--text-faint)">Fallo</header>
        <div class="rules-example-score">
          <span>🇪🇸 España</span><strong>1 — 2</strong><span>Argentina 🇦🇷</span>
        </div>
        <p>Tu apuesta: <strong>2-1</strong></p>
        <span class="chip">0 pts</span>
      </article>
    </div>

    <table class="rules-table">
      <thead>
        <tr><th scope="col">Ronda</th><th scope="col">Puntos por marcador exacto</th></tr>
      </thead>
      <tbody>
        {% for r in rounds %}
        <tr>
          <td><span class="chip" data-round="{{ r.id }}">{{ r.label }}</span></td>
          <td><strong style="font-family:Sora,sans-serif;font-weight:700;font-size:20px">{{ r.points }}</strong> <span style="font-family:'Geist Mono',monospace;color:var(--text-faint);font-size:12px">pts</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>

    <p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
      Acertar solo el resultado (1·X·2) siempre vale 1 punto, sea cual sea la ronda.
    </p>
  </section>

</div>
{% endblock %}
```

- [ ] **Step 4: Ejecutar y verificar PASS**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS en todos los tests, incluido `test_rules_renders_points_card`.

- [ ] **Step 5: Commit**

```bash
git add templates/core/rules.html core/tests/test_rules_view.py
git commit -m "feat(rules): hero y card 'Sistema de puntos' con ejemplos y tabla por ronda"
```

---

## Task 6: Card 2 "Cuándo cierran las apuestas" — frase + timeline + mini estados

**Files:**
- Modify: `templates/core/rules.html` (añadir sección tras la Card 1).
- Modify: `core/tests/test_rules_view.py` (añadir asserciones).

- [ ] **Step 1: Escribir asserciones que fallan**

Añadir a `core/tests/test_rules_view.py`:

```python
@pytest.mark.django_db
def test_rules_renders_close_card(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Las apuestas cierran" in content
    assert "2 horas antes del saque" in content
    # Estados del timeline
    for label in ("Abierto", "Cerrando", "Cerrado", "En juego", "Final"):
        assert label in content
    # Mini ejemplos de partido por estado: cuenta atrás, marcador en vivo y final
    assert "01:23:45" in content   # cuenta atrás del estado closing
    assert "1 — 0" in content       # marcador en vivo
    assert "2 — 1" in content       # marcador final
```

- [ ] **Step 2: Ejecutar y confirmar fallo**

Run: `pytest core/tests/test_rules_view.py::test_rules_renders_close_card -v`
Expected: FAIL.

- [ ] **Step 3: Añadir la Card 2 al template**

En `templates/core/rules.html`, antes del `</div>` final (cierre del wrapper de 880 px), insertar:

```django
  <section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:20px">
    <header style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">02 · Cuándo cierran las apuestas</span>
      <h2 class="grad-text" style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:clamp(22px,3vw,28px);line-height:1.2">
        Las apuestas cierran {{ bet_close_hours }} horas antes del saque.
      </h2>
    </header>

    <ol class="rules-timeline" role="list" aria-label="Estados del partido a lo largo del tiempo">
      <li data-state="open">
        <span class="chip" style="color:var(--c-lime);border-color:oklch(from var(--c-lime) l c h / 0.4)">Abierto</span>
        <span class="rules-timeline-hint">apuestas abiertas</span>
      </li>
      <li data-state="closing">
        <span class="chip" style="color:var(--c-yellow);border-color:oklch(from var(--c-yellow) l c h / 0.4)">Cerrando</span>
        <span class="rules-timeline-hint">cuenta atrás</span>
      </li>
      <li data-state="closed" data-anchor="close">
        <span class="chip">Cerrado</span>
        <span class="rules-timeline-hint">kickoff − {{ bet_close_hours }}h</span>
      </li>
      <li data-state="live" data-anchor="kickoff">
        <span class="chip" style="color:var(--c-red);border-color:oklch(from var(--c-red) l c h / 0.4)">En juego</span>
        <span class="rules-timeline-hint">kickoff</span>
      </li>
      <li data-state="done">
        <span class="chip" style="color:var(--c-cyan);border-color:oklch(from var(--c-cyan) l c h / 0.4)">Final</span>
        <span class="rules-timeline-hint">resultado oficial</span>
      </li>
    </ol>

    <div class="rules-state-grid">
      <article class="rules-state-card" data-state="open">
        <header><span class="chip" style="color:var(--c-lime);border-color:oklch(from var(--c-lime) l c h / 0.4)">Abierto</span></header>
        <div class="rules-state-score"><span>🇪🇸</span><strong>VS</strong><span>🇦🇷</span></div>
        <p>Cierra en 6 h</p>
      </article>
      <article class="rules-state-card" data-state="closing">
        <header><span class="chip" style="color:var(--c-yellow);border-color:oklch(from var(--c-yellow) l c h / 0.4)">Cerrando</span></header>
        <div class="rules-state-score"><span>🇪🇸</span><strong>VS</strong><span>🇦🇷</span></div>
        <p style="font-family:'Geist Mono',monospace;color:var(--c-yellow)">01:23:45</p>
      </article>
      <article class="rules-state-card" data-state="live">
        <header><span class="chip" style="color:var(--c-red);border-color:oklch(from var(--c-red) l c h / 0.4)">En juego</span></header>
        <div class="rules-state-score"><span>🇪🇸</span><strong>1 — 0</strong><span>🇦🇷</span></div>
        <p>Apuestas cerradas</p>
      </article>
      <article class="rules-state-card" data-state="done">
        <header><span class="chip" style="color:var(--c-cyan);border-color:oklch(from var(--c-cyan) l c h / 0.4)">Final</span></header>
        <div class="rules-state-score"><span>🇪🇸</span><strong>2 — 1</strong><span>🇦🇷</span></div>
        <p>Tu apuesta 2-1 · +3 pts</p>
      </article>
    </div>

    <p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
      Una vez cerradas no podrás crear ni editar tu pronóstico — ni siquiera tras el pitido inicial.
    </p>
  </section>
```

- [ ] **Step 4: Ejecutar y verificar PASS**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS en todos.

- [ ] **Step 5: Commit**

```bash
git add templates/core/rules.html core/tests/test_rules_view.py
git commit -m "feat(rules): card 'Cuándo cierran las apuestas' con timeline y mini estados"
```

---

## Task 7: Card 3 "El bote y los premios"

**Files:**
- Modify: `templates/core/rules.html`
- Modify: `core/tests/test_rules_view.py`

- [ ] **Step 1: Escribir asserciones que fallan**

Añadir al fichero de tests:

```python
from decimal import Decimal

from pot.tests.factories import PrizeFactory


@pytest.mark.django_db
def test_rules_renders_pot_card(client):
    PrizeFactory(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    PrizeFactory(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    PrizeFactory(scope="global", position=3, amount=Decimal("96"), label="3er premio")
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "El bote y los premios" in content
    assert "240" in content
    assert "144" in content
    assert "96" in content
```

- [ ] **Step 2: Ejecutar y confirmar fallo**

Run: `pytest core/tests/test_rules_view.py::test_rules_renders_pot_card -v`
Expected: FAIL.

- [ ] **Step 3: Añadir la Card 3 al template**

Antes del `</div>` final del wrapper, añadir:

```django
  <section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:18px">
    <header style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">03 · El bote y los premios</span>
      <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:22px">El bote y los premios</h2>
    </header>

    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px">
      <div class="glass" style="padding:14px 16px;border-radius:var(--r-md);display:flex;flex-direction:column;gap:4px">
        <strong style="font-family:Sora,sans-serif;font-size:28px">{{ pot_per_player|floatformat:"-2" }} €</strong>
        <span style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.12em">Aportación por jugador</span>
      </div>
      <div class="glass" style="padding:14px 16px;border-radius:var(--r-md);display:flex;flex-direction:column;gap:4px">
        <strong style="font-family:Sora,sans-serif;font-size:28px;color:var(--c-gold)">{{ pot_total|default:0 }} €</strong>
        <span style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.12em">Bote total</span>
      </div>
      <div class="glass" style="padding:14px 16px;border-radius:var(--r-md);display:flex;flex-direction:column;gap:4px">
        <strong style="font-family:Sora,sans-serif;font-size:28px">3</strong>
        <span style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.12em">Premios al final del torneo</span>
      </div>
    </div>

    <ul class="rules-medals" role="list">
      {% for prize in pot_prizes %}
      <li data-position="{{ prize.position }}">
        <span class="rules-medal-badge">{{ prize.position }}º</span>
        <strong>{{ prize.amount|floatformat:"-2" }} €</strong>
        <span class="rules-medal-label">{{ prize.label }}</span>
      </li>
      {% empty %}
      <li data-position="1"><span class="rules-medal-badge">1º</span><strong>—</strong></li>
      <li data-position="2"><span class="rules-medal-badge">2º</span><strong>—</strong></li>
      <li data-position="3"><span class="rules-medal-badge">3º</span><strong>—</strong></li>
      {% endfor %}
    </ul>

    <p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
      El gestor marca quién ha pagado — solo los jugadores con el pago confirmado entran en el bote.
    </p>
  </section>
```

- [ ] **Step 4: Ejecutar y verificar PASS**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/core/rules.html core/tests/test_rules_view.py
git commit -m "feat(rules): card 'El bote y los premios' con valores dinámicos"
```

---

## Task 8: Cards 4 "Desempate" y 5 "Acceso" + pie

**Files:**
- Modify: `templates/core/rules.html`
- Modify: `core/tests/test_rules_view.py`

- [ ] **Step 1: Escribir asserciones que fallan**

```python
@pytest.mark.django_db
def test_rules_renders_tiebreak_and_access(client):
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Cómo se decide quién gana" in content
    assert "Más puntos" in content
    assert "Más marcadores exactos" in content
    assert "Acceso a la app" in content
    assert "Sin recuperación automática" in content
    assert "Última actualización del reglamento" in content
```

- [ ] **Step 2: Ejecutar y confirmar fallo**

Run: `pytest core/tests/test_rules_view.py::test_rules_renders_tiebreak_and_access -v`
Expected: FAIL.

- [ ] **Step 3: Añadir Cards 4 y 5 + pie al template**

Antes del `</div>` final, insertar:

```django
  <section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:14px">
    <header style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">04 · Desempate</span>
      <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:22px">Cómo se decide quién gana</h2>
    </header>
    <ol class="rules-tiebreak" role="list">
      <li><span>1</span><p><strong>Más puntos.</strong></p></li>
      <li><span>2</span><p><strong>Más marcadores exactos.</strong></p></li>
      <li><span>3</span><p><strong>Más aciertos</strong> (resultado correcto, incluidos exactos).</p></li>
      <li><span>4</span><p><strong>Orden alfabético</strong> del nombre.</p></li>
    </ol>
    <p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
      Solo cuentan los jugadores activos.
    </p>
  </section>

  <section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:14px">
    <header style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">05 · Acceso</span>
      <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:22px">Acceso a la app</h2>
    </header>
    <ul class="rules-access" role="list">
      <li>
        {% icon "mail" width=18 height=18 %}
        <div>
          <strong>Correo corporativo + contraseña.</strong>
          <p>Tu usuario es tu email de empresa.</p>
        </div>
      </li>
      <li>
        {% icon "lock" width=18 height=18 %}
        <div>
          <strong>Sin recuperación automática.</strong>
          <p>Si la olvidas, un gestor te la restablece.</p>
        </div>
      </li>
      <li>
        {% icon "check" width=18 height=18 %}
        <div>
          <strong>Primera vez.</strong>
          <p>Te pediremos cambiar la contraseña temporal antes de seguir.</p>
        </div>
      </li>
    </ul>
  </section>

  <footer style="font-family:'Geist Mono',monospace;font-size:12px;color:var(--text-faint);text-align:center;padding:8px 0 24px">
    Última actualización del reglamento: {{ rules_updated_at|date:"j F Y" }}. Si algo cambia te lo comunicaremos por aquí.
  </footer>
```

- [ ] **Step 4: Ejecutar y verificar PASS**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS en todos los tests.

- [ ] **Step 5: Commit**

```bash
git add templates/core/rules.html core/tests/test_rules_view.py
git commit -m "feat(rules): cards de desempate, acceso y pie con fecha de actualización"
```

---

## Task 9: CSS para timeline, ejemplos y medallas (responsive)

**Files:**
- Modify: `static/css/styles.css` (append al final del fichero).

- [ ] **Step 1: Añadir bloque de estilos al final de `static/css/styles.css`**

```css
/* ============================================================
   Página /reglas/ — estilos específicos
   ============================================================ */

.rules-example-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 14px 16px;
  border-radius: var(--r-md);
  background: var(--surface-hi);
  border: 1px solid var(--border);
}
.rules-example-card[data-variant="exact"] {
  border-color: oklch(from var(--c-lime) l c h / 0.4);
}
.rules-example-card[data-variant="partial"] {
  border-color: oklch(from var(--c-cyan) l c h / 0.4);
}
.rules-example-card[data-variant="miss"] {
  opacity: 0.85;
}
.rules-example-score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
  font-family: 'Geist Mono', monospace;
  font-size: 14px;
}
.rules-example-score strong {
  font-family: Sora, sans-serif;
  font-size: 22px;
  letter-spacing: -0.02em;
}
.rules-example-card p {
  margin: 0;
  color: var(--text-dim);
  font-size: 13px;
}

.rules-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 14px;
}
.rules-table th,
.rules-table td {
  text-align: left;
  padding: 10px 8px;
  border-bottom: 1px solid var(--border);
}
.rules-table thead th {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-faint);
  font-weight: 500;
}
.rules-table .chip[data-round="groups"] { color: var(--c-lime); border-color: oklch(from var(--c-lime) l c h / 0.4); }
.rules-table .chip[data-round="r32"]    { color: var(--c-cyan); border-color: oklch(from var(--c-cyan) l c h / 0.4); }
.rules-table .chip[data-round="r16"]    { color: var(--c-yellow); border-color: oklch(from var(--c-yellow) l c h / 0.4); }
.rules-table .chip[data-round="qf"]     { color: var(--c-gold); border-color: oklch(from var(--c-gold) l c h / 0.4); }
.rules-table .chip[data-round="sf"],
.rules-table .chip[data-round="final"]  { color: var(--c-pink); border-color: oklch(from var(--c-pink) l c h / 0.4); }

.rules-timeline {
  list-style: none;
  margin: 0;
  padding: 16px 8px;
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 8px;
  position: relative;
  background:
    linear-gradient(90deg,
      oklch(from var(--c-lime) l c h / 0.6) 0%,
      oklch(from var(--c-yellow) l c h / 0.6) 35%,
      oklch(from var(--text-faint) l c h / 0.5) 55%,
      oklch(from var(--c-red) l c h / 0.6) 75%,
      oklch(from var(--c-cyan) l c h / 0.6) 100%) 0 50% / 100% 2px no-repeat;
}
.rules-timeline li {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  text-align: center;
}
.rules-timeline-hint {
  font-family: 'Geist Mono', monospace;
  font-size: 10px;
  color: var(--text-faint);
}

.rules-state-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
  gap: 10px;
}
.rules-state-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px;
  border-radius: var(--r-md);
  background: var(--surface-hi);
  border: 1px solid var(--border);
}
.rules-state-card[data-state="live"] {
  border-color: oklch(from var(--c-red) l c h / 0.4);
}
.rules-state-card[data-state="done"] {
  border-color: oklch(from var(--c-cyan) l c h / 0.4);
}
.rules-state-score {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 8px;
}
.rules-state-score strong {
  font-family: Sora, sans-serif;
  font-size: 20px;
  letter-spacing: -0.02em;
}
.rules-state-card p {
  margin: 0;
  font-size: 12px;
  color: var(--text-dim);
}

.rules-medals {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 10px;
}
.rules-medals li {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  padding: 12px;
  border-radius: var(--r-md);
  border: 1px solid var(--border);
  background: var(--surface-hi);
}
.rules-medals li[data-position="1"] { border-color: oklch(from var(--c-gold) l c h / 0.55); }
.rules-medals li[data-position="2"] { border-color: oklch(from var(--text-dim) l c h / 0.45); }
.rules-medals li[data-position="3"] { border-color: oklch(from var(--c-yellow) l c h / 0.45); }
.rules-medal-badge {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  color: var(--text-faint);
}
.rules-medals strong {
  font-family: Sora, sans-serif;
  font-size: 24px;
}
.rules-medal-label {
  font-size: 12px;
  color: var(--text-dim);
}

.rules-tiebreak {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}
.rules-tiebreak li {
  display: flex;
  align-items: center;
  gap: 12px;
}
.rules-tiebreak li > span {
  font-family: Sora, sans-serif;
  font-weight: 800;
  font-size: 20px;
  width: 28px;
  text-align: center;
  color: var(--accent);
}
.rules-tiebreak li > p { margin: 0; }

.rules-access {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 12px;
}
.rules-access li {
  display: flex;
  align-items: flex-start;
  gap: 12px;
}
.rules-access li svg {
  flex-shrink: 0;
  margin-top: 2px;
  color: var(--accent);
}
.rules-access strong { display: block; }
.rules-access p {
  margin: 2px 0 0;
  color: var(--text-dim);
  font-size: 13px;
}

@media (max-width: 920px) {
  .rules-timeline {
    grid-template-columns: 1fr;
    background:
      linear-gradient(180deg,
        oklch(from var(--c-lime) l c h / 0.6) 0%,
        oklch(from var(--c-yellow) l c h / 0.6) 35%,
        oklch(from var(--text-faint) l c h / 0.5) 55%,
        oklch(from var(--c-red) l c h / 0.6) 75%,
        oklch(from var(--c-cyan) l c h / 0.6) 100%) 50% 0 / 2px 100% no-repeat;
    padding: 12px 8px 12px 24px;
  }
  .rules-timeline li {
    flex-direction: row;
    justify-content: flex-start;
    gap: 12px;
    text-align: left;
  }
  .rules-medals { grid-template-columns: 1fr; }
}

@media (max-width: 560px) {
  .rules-example-score { flex-direction: column; gap: 4px; }
}
```

- [ ] **Step 2: Recargar la app y confirmar que renderiza sin errores de CSS**

Run: `python manage.py check`
Expected: sin errores.

- [ ] **Step 3: Commit**

```bash
git add static/css/styles.css
git commit -m "style(rules): estilos específicos de la página de reglas (timeline, ejemplos, medallas)"
```

---

## Task 10: Verificación visual y comprobación cruzada

**Files:** ninguno, paso manual + corrección si hace falta.

- [ ] **Step 1: Arrancar el servidor de desarrollo**

Run en una terminal aparte:
```bash
python manage.py runserver
```

- [ ] **Step 2: Cargar la página y validar visualmente**

Visitar `http://localhost:8000/reglas/` (logueado). Comprobar:
1. Topbar muestra "Reglas" entre Rankings y Jugadores; activo (degradado de acento) en esta página.
2. Hero, las 5 cards y el pie aparecen en este orden.
3. Las tres mini-tarjetas-ejemplo tienen el borde de color correcto (lima/cian/atenuado).
4. La tabla de rondas pinta los puntos reales (`Round.points`) con el chip de color por ronda.
5. La frase "Las apuestas cierran 2 horas antes del saque." se muestra con el degradado de la app.
6. El timeline de estados pinta los cinco hitos sobre la línea de degradado.
7. Los importes del bote vienen del modelo: `pot_per_player`, `pot_total` y los `Prize` globales con sus medallas.
8. El pie muestra la fecha en formato "1 junio 2026".

- [ ] **Step 3: Probar tema claro**

Pulsar el botón sol/luna en topbar. Confirmar que la página queda legible (texto sobre superficies claras, chips conservan color).

- [ ] **Step 4: Probar responsive**

Reducir la ventana del navegador a ~375 px. Confirmar:
- Hero, cards y mini-cards pasan a una columna.
- Timeline pasa a vertical.
- Medallas apilan.

- [ ] **Step 5: Ejecutar la suite entera**

Run: `pytest`
Expected: todos los tests verdes (incluida `competition/tests/test_matchday_gate.py`, ya estable tras el refactor de Task 1).

- [ ] **Step 6: Comprobar el comentario de sincronización**

Confirmar que `templates/core/rules.html` empieza por:
```django
{# Mantener sincronizado con docs/DATA_MODEL.md §2, §3, §5 — cambios de reglas se reflejan también aquí. #}
```
Si no, añadirlo justo después de `{% block main %}`.

- [ ] **Step 7: Commit final si hubo correcciones**

Si los pasos 2-6 dispararon ajustes en plantilla o CSS:

```bash
git add templates/core/rules.html static/css/styles.css
git commit -m "fix(rules): ajustes de verificación visual (tema, responsive)"
```

---

## Self-review checklist (para el ejecutor)

Antes de cerrar el plan, verificar:

- [ ] La página renderiza con datos reales (no mock) — `Round`, `PotSettings`, `Prize`.
- [ ] El enlace "Reglas" aparece en la topbar y se marca `is-active` en `/reglas/`.
- [ ] `BET_CLOSE_HOURS` solo se usa para el cálculo de `close_at` (línea 63 antigua); la ventana del estado `closing` (línea 68) sigue como literal.
- [ ] La copia coincide con `docs/DATA_MODEL.md` (puntos por ronda, ventana de 2 h, auth sin recuperación automática, desempate).
- [ ] `RULES_UPDATED_AT` está en `settings/base.py` y se renderiza en el pie.
- [ ] `static/icons/book.svg` añadido y servido en la topbar.
- [ ] Sin warnings en `python manage.py check` y suite completa de tests en verde.
