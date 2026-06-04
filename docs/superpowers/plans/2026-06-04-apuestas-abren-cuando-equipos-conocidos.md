# Apuestas abren cuando se conocen los dos equipos · Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Quitar la "puerta de jornada" y permitir que cada partido sea apostable en cuanto se conocen sus dos equipos. Los partidos KO se modelan con slots que se resuelven automáticamente al confirmar resultados.

**Architecture:** `Match.home`/`Match.away` nullable + nuevos campos `home_slot`, `away_slot`, `bracket_code`. Nuevo servicio `bracket.py` (`resolve_slot`, `propagate_after_match`, `slot_label`) invocado desde `resolve_match`. Nuevo estado derivado `pending_teams` en `Match.status`. Eliminamos `matchday_gate.py` completamente. UI: tarjeta de partido con rama placeholder; sección "Cruce pendiente" para el gestor.

**Tech Stack:** Django + pytest-django (factories ya existentes), templates Django, `freezegun` para tests.

**Spec:** `docs/superpowers/specs/2026-06-04-apuestas-abren-cuando-equipos-conocidos-design.md`.

---

## Task 1: Migración del modelo `Match`

**Files:**
- Modify: `competition/models.py:36-93`
- Create: `competition/migrations/0009_match_slots_and_nullable_teams.py`

- [ ] **Step 1: Editar `Match` añadiendo slots y null=True**

En `competition/models.py`, en la clase `Match`:

```python
class Match(models.Model):
    round = models.ForeignKey(Round, on_delete=models.PROTECT, related_name="matches")
    group = models.CharField(max_length=20)
    matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    home = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="home_matches",
        null=True, blank=True,
    )
    away = models.ForeignKey(
        Team, on_delete=models.PROTECT, related_name="away_matches",
        null=True, blank=True,
    )
    home_slot = models.CharField(max_length=12, blank=True)
    away_slot = models.CharField(max_length=12, blank=True)
    bracket_code = models.CharField(max_length=12, blank=True, null=True, unique=True)
    kickoff = models.DateTimeField()
    # ... (resto idéntico)
```

- [ ] **Step 2: Generar migración**

```bash
python manage.py makemigrations competition --name match_slots_and_nullable_teams
```

Verificar que el archivo creado contiene `AlterField` para `home`/`away` y `AddField` para los tres nuevos.

- [ ] **Step 3: Aplicar migración local**

```bash
python manage.py migrate competition
```

Expected: `Applying competition.0009_match_slots_and_nullable_teams... OK`

- [ ] **Step 4: Commit**

```bash
git add competition/models.py competition/migrations/0009_match_slots_and_nullable_teams.py
git commit -m "feat(match): home/away nullable + slot fields para cuadro KO"
```

---

## Task 2: Propiedades `has_teams`, `status` y `editable` actualizadas

**Files:**
- Modify: `competition/models.py:59-92`
- Test: `competition/tests/test_match.py` (existente, añadir casos)

- [ ] **Step 1: Escribir tests fallando**

Añadir al final de `competition/tests/test_match.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.mark.django_db
def test_match_without_teams_is_pending_teams():
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    m = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=None,
        away=None,
        home_slot="1A",
        away_slot="2B",
        bracket_code="M73",
        kickoff=timezone.now() + timedelta(days=10),
    )
    assert m.has_teams is False
    assert m.status == "pending_teams"
    assert m.editable is False
    assert m.predictions_open is False


@pytest.mark.django_db
def test_match_with_only_home_is_pending_teams():
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    home = TeamFactory(code="HOM")
    m = MatchFactory(
        round=r32,
        group="R32",
        matchday=None,
        home=home,
        away=None,
        home_slot="",
        away_slot="2B",
        bracket_code="M74",
        kickoff=timezone.now() + timedelta(days=10),
    )
    assert m.has_teams is False
    assert m.status == "pending_teams"


@pytest.mark.django_db
def test_match_with_both_teams_uses_normal_status():
    grp = RoundFactory(id="groups", points=3, label="GRP", short="GRP", order=1)
    with freeze_time("2026-06-11 10:00:00", tz_offset=0):
        m = MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="ESP"),
            away=TeamFactory(code="ARG"),
            kickoff=timezone.now() + timedelta(days=1),
        )
        assert m.has_teams is True
        assert m.status == "open"
        assert m.editable is True
```

- [ ] **Step 2: Ejecutar tests (deben fallar)**

```bash
pytest competition/tests/test_match.py -k "pending_teams or with_both" -v
```

Expected: 3 FAILS (status no es "pending_teams", `has_teams` no existe).

- [ ] **Step 3: Implementar las propiedades**

En `competition/models.py`, reemplazar la sección de propiedades de `Match`:

```python
    @property
    def has_result(self) -> bool:
        return self.result_home is not None and self.result_away is not None

    @property
    def has_teams(self) -> bool:
        return self.home_id is not None and self.away_id is not None

    @property
    def status(self) -> str:
        now = timezone.now()
        if self.has_result:
            return "done"
        if not self.has_teams:
            return "pending_teams"
        close_at = self.kickoff - timedelta(hours=BET_CLOSE_HOURS)
        if now >= self.kickoff:
            return "live"
        if now >= close_at:
            return "closed"
        if close_at - now <= timedelta(hours=2):
            return "closing"
        return "open"

    @property
    def editable(self) -> bool:
        return self.has_teams and self.status in ("open", "closing")

    @property
    def predictions_open(self) -> bool:
        """True si el partido es editable. Ya no depende del gate de jornada."""
        return self.editable
```

(Elimina el `from competition.services.matchday_gate import is_matchday_open` y todo el bloque siguiente.)

- [ ] **Step 4: Ejecutar tests (deben pasar)**

```bash
pytest competition/tests/test_match.py -v
```

Expected: PASS, incluyendo los 3 tests nuevos.

- [ ] **Step 5: Commit**

```bash
git add competition/models.py competition/tests/test_match.py
git commit -m "feat(match): pending_teams state + predictions_open sin gate"
```

---

## Task 3: Borrar `matchday_gate` (servicio y test)

**Files:**
- Delete: `competition/services/matchday_gate.py`
- Delete: `competition/tests/test_matchday_gate.py`
- Modify: `competition/views.py:14-74, 152-185`

- [ ] **Step 1: Borrar archivos**

```bash
git rm competition/services/matchday_gate.py competition/tests/test_matchday_gate.py
```

- [ ] **Step 2: Quitar imports y lógica de `CompetitionView`**

En `competition/views.py`, dentro de `CompetitionView.get`, sustituir el bloque que va desde:

```python
        from competition.services.matchday_gate import (
            is_matchday_open,
            previous_matchday_close_info,
        )
```

…hasta el final de la construcción de `matchday_state`/`locked_*`, por:

```python
        # matchday_state: ya no hay gate, todas las jornadas abiertas
        matchday_state = [
            {"matchday": md, "open": True, "active": md == active_md} for md in matchdays
        ]
```

Y eliminar `locked`, `locked_last_match`, `locked_last_kickoff` del contexto al renderizar la plantilla.

- [ ] **Step 3: Quitar la guarda de `PredictView.get`**

En `competition/views.py`, dentro de `PredictView.get`:

```python
        from competition.services.predictions import (
            next_pending_match,
            pending_matches_count,
        )

        if not m.has_teams:
            messages.error(
                request,
                "Este cruce aún no tiene los dos equipos definidos.",
            )
            return redirect("competicion:dashboard")
```

Es decir, sustituye el `from competition.services.matchday_gate import is_matchday_open` y el `if not is_matchday_open(...)` por la guarda `has_teams`.

- [ ] **Step 4: Ejecutar la suite completa**

```bash
pytest competition/tests/ -v
```

Expected: PASS. Si algún test fuera de `test_match.py` se rompe porque importaba `matchday_gate`, arreglarlo en el mismo commit.

- [ ] **Step 5: Commit**

```bash
git add competition/views.py
git commit -m "refactor(competicion): eliminar gate de jornada"
```

---

## Task 4: Quitar banner "Jornada bloqueada" y chip 🔒

**Files:**
- Modify: `templates/competition/dashboard.html:9-29`
- Modify: `templates/competition/_match_card.html:78-83`

- [ ] **Step 1: Editar `dashboard.html`**

Eliminar el bloque entero `{% if locked %} ... {% endif %}` (líneas 9-24 actuales) y la condición `{% if locked %};opacity:.55;pointer-events:none{% endif %}` del estilo de la grilla de partidos abiertos. La sección debe quedar como:

```html
<section>
  {% include "partials/_round_selector.html" with rounds=rounds active=active_round %}
  {% include "partials/_matchday_selector.html" %}

  {% if open_matches %}
  <h2 class="eyebrow" style="margin-top:24px">ABIERTOS · {{ open_matches|length }}</h2>
  <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
    ...
```

- [ ] **Step 2: Editar `_match_card.html`**

Eliminar el bloque del chip 🔒 (la rama `{% elif match.editable %}` que renderiza "🔒 Jornada bloqueada"):

```html
    {% elif match.editable %}
      <span class="chip" style="opacity:.7">
        🔒 Jornada bloqueada
      </span>
    {% endif %}
```

Reemplazar por simplemente cerrar el `{% endif %}` tras la rama anterior (`{% elif match.predictions_open and request.user.is_jugador %}`).

- [ ] **Step 3: Commit**

```bash
git add templates/competition/dashboard.html templates/competition/_match_card.html
git commit -m "ui(competicion): quitar banner y chip de jornada bloqueada"
```

---

## Task 5: Template filter `slot_label`

**Files:**
- Create: `competition/templatetags/__init__.py`
- Create: `competition/templatetags/competition_extras.py`
- Test: `competition/tests/test_slot_label_filter.py`

- [ ] **Step 1: Escribir tests fallando**

```python
# competition/tests/test_slot_label_filter.py
import pytest

from competition.templatetags.competition_extras import slot_label


@pytest.mark.parametrize(
    "code,expected",
    [
        ("1A", "1º Grupo A"),
        ("2B", "2º Grupo B"),
        ("3L", "3º Grupo L"),
        ("WM49", "Ganador M49"),
        ("3WG_S1", "Mejor tercero (S1)"),
        ("", "Por definir"),
        ("X9", "Por definir"),
    ],
)
def test_slot_label(code, expected):
    assert slot_label(code) == expected
```

- [ ] **Step 2: Ejecutar (debe fallar por ImportError)**

```bash
pytest competition/tests/test_slot_label_filter.py -v
```

Expected: FAIL.

- [ ] **Step 3: Implementar**

Crear `competition/templatetags/__init__.py` vacío.

Crear `competition/templatetags/competition_extras.py`:

```python
from __future__ import annotations

import re

from django import template

register = template.Library()

GROUP_RE = re.compile(r"^([123])([A-L])$")
WINNER_RE = re.compile(r"^W(M\d+)$")
THIRD_RE = re.compile(r"^3WG_(S\d+)$")


@register.filter(name="slot_label")
def slot_label(code: str) -> str:
    """Etiqueta legible para un código de slot. Devuelve 'Por definir' si no se reconoce."""
    if not code:
        return "Por definir"
    if m := GROUP_RE.match(code):
        pos, group = m.group(1), m.group(2)
        return f"{pos}º Grupo {group}"
    if m := WINNER_RE.match(code):
        return f"Ganador {m.group(1)}"
    if m := THIRD_RE.match(code):
        return f"Mejor tercero ({m.group(1)})"
    return "Por definir"
```

- [ ] **Step 4: Ejecutar (debe pasar)**

```bash
pytest competition/tests/test_slot_label_filter.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add competition/templatetags/ competition/tests/test_slot_label_filter.py
git commit -m "feat(templates): filter slot_label para etiquetas de cruce"
```

---

## Task 6: Tarjeta de partido para `pending_teams`

**Files:**
- Modify: `templates/competition/_match_card.html`

- [ ] **Step 1: Editar `_match_card.html`**

Añadir al principio del archivo (después de `{% load icons %}`) la carga del filter y la rama `pending_teams`. El archivo queda:

```html
{% load icons %}
{% load competition_extras %}
{% with st=match.status %}
{% if st == 'pending_teams' %}
<div class="match-card glass" style="cursor:default;opacity:.85">
  <div class="match-card-head">
    <span class="eyebrow">{% if match.group|length <= 1 %}Grupo {{ match.group }}{% else %}{{ match.group }}{% endif %}</span>
    <span class="chip chip-pending">Por definir</span>
  </div>

  <div class="match-card-teams">
    <div class="team-side">
      <span class="team-flag">🏳️</span>
      <strong class="team-name display">{{ match.home_slot|slot_label }}</strong>
    </div>
    <div class="match-score"><span class="match-vs display">VS</span></div>
    <div class="team-side">
      <span class="team-flag">🏳️</span>
      <strong class="team-name display">{{ match.away_slot|slot_label }}</strong>
    </div>
  </div>

  <div class="match-card-meta">
    {% icon "cal" width=13 height=13 %}
    <span class="mono">{{ match.kickoff|date:"D j M · H:i" }}</span>
  </div>

  <div class="match-card-foot">
    <span class="match-card-foot-info">Equipos pendientes</span>
  </div>
</div>
{% elif match.predictions_open and request.user.is_jugador %}
<a href="{% url 'competicion:predict' match.id %}" data-modal-url="{% url 'competicion:predict' match.id %}" class="match-card glass rise{% if st == 'closing' %} match-card-closing{% endif %}">
...
```

(El resto del archivo permanece igual; mantén el `{% endwith %}` final y el cierre del bloque elif/else original.)

- [ ] **Step 2: Añadir estilo `.chip-pending`**

En `static/css/styles.css` (o el archivo principal de chips), buscar `chip-closed` y añadir justo después:

```css
.chip-pending {
  color: var(--text-dim);
  border-color: oklch(from var(--text-dim) l c h / 0.4);
  opacity: 0.85;
}
```

Si no encuentras `chip-closed` directamente en CSS (puede estar inline en `_match_card.html`), añadir el estilo inline al span: `style="color:var(--text-dim);opacity:.85"`.

- [ ] **Step 3: Smoke test manual con shell**

```bash
python manage.py shell <<'EOF'
from django.template import Context, Template
from competition.models import Match, Round
# basta con verificar que el template no peta al cargar el filter
t = Template("{% load competition_extras %}{{ '1A'|slot_label }}")
print(t.render(Context({})))
EOF
```

Expected: imprime `1º Grupo A`.

- [ ] **Step 4: Commit**

```bash
git add templates/competition/_match_card.html static/css/styles.css
git commit -m "ui(match-card): rama pending_teams con placeholders"
```

---

## Task 7: Servicio `bracket.py` — resolver para 1A/2A/3A

**Files:**
- Create: `competition/services/bracket.py`
- Create: `competition/tests/test_bracket_resolver.py`

- [ ] **Step 1: Escribir tests fallando para slots de grupo**

```python
# competition/tests/test_bracket_resolver.py
from datetime import timedelta

import pytest
from django.utils import timezone

from competition.models import Match
from competition.services.bracket import resolve_slot
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="GRP", short="GRP", order=1)


def _played(round_, group, home, away, hg, ag, matchday=1, **kw):
    """Crea un Match ya con resultado oficial."""
    return MatchFactory(
        round=round_,
        group=group,
        matchday=matchday,
        home=home,
        away=away,
        result_home=hg,
        result_away=ag,
        finished_at=timezone.now(),
        kickoff=timezone.now() - timedelta(days=1),
        exact_points_applied=round_.points,
        partial_points_applied=round_.partial_points,
        **kw,
    )


@pytest.mark.django_db
def test_resolve_1a_returns_leader_when_group_complete(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    # ESP gana sus 3 partidos → líder claro
    _played(groups_round, "A", esp, arg, 2, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 1, matchday=1)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 2, 1, matchday=2)
    _played(groups_round, "A", esp, bra, 3, 0, matchday=3)
    _played(groups_round, "A", arg, fra, 0, 0, matchday=3)
    assert resolve_slot("1A") == esp


@pytest.mark.django_db
def test_resolve_1a_returns_none_when_group_incomplete(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    _played(groups_round, "A", esp, arg, 2, 0, matchday=1)
    _played(groups_round, "A", fra, bra, 1, 1, matchday=1)
    # faltan partidos
    MatchFactory(
        round=groups_round, group="A", matchday=2, home=esp, away=fra,
        kickoff=timezone.now() + timedelta(days=1),
    )
    assert resolve_slot("1A") is None


@pytest.mark.django_db
def test_resolve_2a_returns_runner_up(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    # ESP: 9pts, ARG: 6pts, FRA: 3pts, BRA: 0pts
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=3)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=3)
    assert resolve_slot("2A") == arg


@pytest.mark.django_db
def test_resolve_3a_returns_third_place(groups_round):
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=3)
    _played(groups_round, "A", fra, bra, 1, 0, matchday=3)
    assert resolve_slot("3A") == fra


@pytest.mark.django_db
def test_resolve_unknown_slot_returns_none():
    assert resolve_slot("XYZ") is None
    assert resolve_slot("") is None
```

- [ ] **Step 2: Ejecutar (deben fallar)**

```bash
pytest competition/tests/test_bracket_resolver.py -v
```

Expected: FAIL (módulo no existe).

- [ ] **Step 3: Implementar `bracket.py`**

Crear `competition/services/bracket.py`:

```python
"""Resolver de slots del cuadro: traduce códigos como '1A', '2C', 'WM49'
al equipo concreto que ocupa esa posición en este momento."""

from __future__ import annotations

import re
from dataclasses import dataclass

from competition.models import Match, Team

GROUP_RE = re.compile(r"^([123])([A-L])$")
WINNER_RE = re.compile(r"^WM(\d+)$")


@dataclass(frozen=True)
class GroupRow:
    team: Team
    pts: int
    gd: int
    gf: int


def _group_standings(group: str) -> list[GroupRow] | None:
    """Calcula la clasificación del grupo. Devuelve None si quedan partidos
    sin resolver."""
    matches = list(
        Match.objects.filter(round_id="groups", group=group).select_related("home", "away")
    )
    if not matches:
        return None
    if any(not m.has_result for m in matches):
        return None

    stats: dict[int, dict] = {}
    for m in matches:
        for team, gf, ga in ((m.home, m.result_home, m.result_away),
                             (m.away, m.result_away, m.result_home)):
            s = stats.setdefault(team.code, {"team": team, "pts": 0, "gd": 0, "gf": 0})
            s["gf"] += gf
            s["gd"] += gf - ga
            if gf > ga:
                s["pts"] += 3
            elif gf == ga:
                s["pts"] += 1

    rows = [GroupRow(team=s["team"], pts=s["pts"], gd=s["gd"], gf=s["gf"]) for s in stats.values()]
    rows.sort(key=lambda r: (-r.pts, -r.gd, -r.gf, r.team.code))
    return rows


def resolve_slot(code: str) -> Team | None:
    """Equipo concreto al que apunta el código, o None si no es determinable aún."""
    if not code:
        return None
    if m := GROUP_RE.match(code):
        pos = int(m.group(1))
        group = m.group(2)
        standings = _group_standings(group)
        if standings is None or len(standings) < pos:
            return None
        return standings[pos - 1].team
    if m := WINNER_RE.match(code):
        bracket_code = f"M{m.group(1)}"
        match = Match.objects.filter(bracket_code=bracket_code).first()
        if match is None or not match.has_result:
            return None
        if match.result_home == match.result_away:
            return None  # empate 90': el gestor lo decide
        return match.home if match.result_home > match.result_away else match.away
    return None
```

- [ ] **Step 4: Ejecutar (deben pasar)**

```bash
pytest competition/tests/test_bracket_resolver.py -v
```

Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add competition/services/bracket.py competition/tests/test_bracket_resolver.py
git commit -m "feat(bracket): resolve_slot para 1A/2A/3A y WMnn"
```

---

## Task 8: Resolver para `WMnn` (tests + extender)

**Files:**
- Modify: `competition/tests/test_bracket_resolver.py`

- [ ] **Step 1: Añadir tests para `WMnn`**

Al final de `test_bracket_resolver.py`:

```python
@pytest.mark.django_db
def test_resolve_wm_returns_winner_in_90(groups_round):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    _played(r32, "R32", esp, arg, 2, 1, matchday=None, bracket_code="M49")
    assert resolve_slot("WM49") == esp


@pytest.mark.django_db
def test_resolve_wm_returns_none_on_draw(groups_round):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    _played(r32, "R32", esp, arg, 1, 1, matchday=None, bracket_code="M50")
    assert resolve_slot("WM50") is None


@pytest.mark.django_db
def test_resolve_wm_returns_none_when_no_result(groups_round):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    MatchFactory(
        round=r32, group="R32", matchday=None,
        home=TeamFactory(code="ESP"), away=TeamFactory(code="ARG"),
        bracket_code="M51",
        kickoff=timezone.now() + timedelta(days=1),
    )
    assert resolve_slot("WM51") is None


@pytest.mark.django_db
def test_resolve_wm_unknown_code():
    assert resolve_slot("WM999") is None
```

- [ ] **Step 2: Ejecutar (deben pasar — implementación ya hecha en Task 7)**

```bash
pytest competition/tests/test_bracket_resolver.py -v
```

Expected: 9 PASS.

- [ ] **Step 3: Commit**

```bash
git add competition/tests/test_bracket_resolver.py
git commit -m "test(bracket): casos WMnn (ganador 90', empate, sin resultado)"
```

---

## Task 9: `propagate_after_match` + hook en `resolve_match`

**Files:**
- Modify: `competition/services/bracket.py`
- Modify: `competition/services/resolve.py:9-43`
- Modify: `competition/tests/test_bracket_resolver.py`

- [ ] **Step 1: Escribir test fallando**

Añadir al final de `test_bracket_resolver.py`:

```python
from competition.services.bracket import propagate_after_match
from competition.services.resolve import resolve_match


@pytest.mark.django_db
def test_propagate_fills_r32_when_group_a_closes(groups_round):
    """Al cerrar el grupo A, el R32 que dependía de 1A/2B se rellena."""
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    bra = TeamFactory(code="BRA")
    # Grupo B ya cerrado (para que 2B exista)
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
    # Grupo A: faltan 1 partido por confirmar
    _played(groups_round, "A", esp, arg, 1, 0, matchday=1)
    _played(groups_round, "A", arg, fra, 2, 0, matchday=2)
    _played(groups_round, "A", esp, fra, 1, 0, matchday=2)
    _played(groups_round, "A", arg, bra, 3, 0, matchday=3)
    _played(groups_round, "A", esp, bra, 2, 0, matchday=3)
    last = MatchFactory(
        round=groups_round, group="A", matchday=3, home=fra, away=bra,
        kickoff=timezone.now() - timedelta(hours=1),
    )

    # R32 con slot 1A vs 2B, ambos slots resolvibles solo cuando ambos grupos cierren
    ko = MatchFactory(
        round=r32, group="R32", matchday=None,
        home=None, away=None,
        home_slot="1A", away_slot="2B",
        bracket_code="M73",
        kickoff=timezone.now() + timedelta(days=10),
    )

    # Cerramos el último partido del grupo A
    from accounts.models import User
    actor = User.objects.create(email="g@example.com", is_gestor=True, name="G")
    resolve_match(last, home=1, away=0, actor=actor)

    ko.refresh_from_db()
    assert ko.home == esp
    assert ko.away == ger  # 2º del grupo B


@pytest.mark.django_db
def test_propagate_is_idempotent_does_not_overwrite(groups_round):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    custom = TeamFactory(code="ZZZ")
    ko = MatchFactory(
        round=r32, group="R32", matchday=None,
        home=custom, away=None,
        home_slot="1A", away_slot="",
        bracket_code="M74",
        kickoff=timezone.now() + timedelta(days=10),
    )
    # Forzamos que 1A resolvería a ESP, pero el gestor ya puso ZZZ.
    Match.objects.filter(pk=ko.pk).update(home=custom)
    propagate_after_match(ko)
    ko.refresh_from_db()
    assert ko.home == custom  # no se sobrescribe
```

- [ ] **Step 2: Ejecutar (deben fallar)**

```bash
pytest competition/tests/test_bracket_resolver.py -k propagate -v
```

Expected: FAIL.

- [ ] **Step 3: Añadir `propagate_after_match` a `bracket.py`**

Al final de `competition/services/bracket.py`:

```python
def propagate_after_match(match: Match) -> list[Match]:
    """Rellena home/away en todos los partidos cuyos slots queden resolvibles
    tras resolver `match`. Idempotente: solo escribe donde está a None."""
    candidates = list(
        Match.objects.filter(home__isnull=True).exclude(home_slot="")
    ) + list(
        Match.objects.filter(away__isnull=True).exclude(away_slot="")
    )
    # Dedup
    seen: dict[int, Match] = {m.pk: m for m in candidates}
    updated: list[Match] = []
    for m in seen.values():
        update_fields: list[str] = []
        if m.home_id is None and m.home_slot:
            team = resolve_slot(m.home_slot)
            if team is not None:
                m.home = team
                update_fields.append("home")
        if m.away_id is None and m.away_slot:
            team = resolve_slot(m.away_slot)
            if team is not None:
                m.away = team
                update_fields.append("away")
        if update_fields:
            m.save(update_fields=update_fields)
            updated.append(m)
    return updated
```

- [ ] **Step 4: Hook en `resolve_match`**

En `competition/services/resolve.py`, al final del bloque `@transaction.atomic def resolve_match(...)`, antes del `detect_after_match`:

```python
    from competition.services.bracket import propagate_after_match

    propagate_after_match(match)
```

Queda como:

```python
    AuditLog.objects.create(
        actor=actor,
        action="match_resolved",
        target_type="match",
        target_id=str(match.id),
        payload={"home": home, "away": away},
    )

    from competition.services.bracket import propagate_after_match

    propagate_after_match(match)

    from announcements.services import detect_after_match

    detect_after_match(match)
```

- [ ] **Step 5: Ejecutar tests**

```bash
pytest competition/tests/test_bracket_resolver.py -v
```

Expected: PASS, incluyendo los 2 nuevos.

- [ ] **Step 6: Commit**

```bash
git add competition/services/bracket.py competition/services/resolve.py competition/tests/test_bracket_resolver.py
git commit -m "feat(bracket): propagate_after_match + hook en resolve_match"
```

---

## Task 10: Vista de asignación manual de equipos (`AssignTeamsView`)

**Files:**
- Modify: `competition/views.py`
- Modify: `competition/urls.py`
- Modify: `templates/competition/manage_results.html`
- Test: `competition/tests/test_assign_teams_view.py`

- [ ] **Step 1: Escribir tests fallando**

```python
# competition/tests/test_assign_teams_view.py
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.models import User
from competition.models import Match, Prediction
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture
def gestor(db):
    return User.objects.create(email="g@example.com", is_gestor=True, name="G", is_active=True)


@pytest.fixture
def jugador(db):
    return User.objects.create(
        email="j@example.com", is_jugador=True, name="J", is_active=True
    )


@pytest.mark.django_db
def test_assign_teams_initial(client, gestor):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    ko = MatchFactory(
        round=r32, group="R32", matchday=None,
        home=None, away=None, home_slot="1A", away_slot="2B",
        bracket_code="M73", kickoff=timezone.now() + timedelta(days=10),
    )
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "ESP", "away_code": "ARG"},
    )
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home == esp
    assert ko.away == arg


@pytest.mark.django_db
def test_assign_teams_correction_invalidates_predictions(client, gestor, jugador):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    ko = MatchFactory(
        round=r32, group="R32", matchday=None,
        home=esp, away=arg, home_slot="1A", away_slot="2B",
        bracket_code="M74", kickoff=timezone.now() + timedelta(days=10),
    )
    Prediction.objects.create(player=jugador, match=ko, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "FRA", "away_code": "ARG", "confirm_invalidate": "1"},
    )
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home == fra
    assert Prediction.objects.filter(match=ko).count() == 0


@pytest.mark.django_db
def test_assign_teams_correction_requires_confirmation(client, gestor, jugador):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    esp = TeamFactory(code="ESP")
    arg = TeamFactory(code="ARG")
    fra = TeamFactory(code="FRA")
    ko = MatchFactory(
        round=r32, group="R32", matchday=None,
        home=esp, away=arg, home_slot="1A", away_slot="2B",
        bracket_code="M75", kickoff=timezone.now() + timedelta(days=10),
    )
    Prediction.objects.create(player=jugador, match=ko, home=2, away=1)
    client.force_login(gestor)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "FRA", "away_code": "ARG"},
    )
    # Sin confirm_invalidate, redirige con error y no toca nada
    assert resp.status_code == 302
    ko.refresh_from_db()
    assert ko.home == esp
    assert Prediction.objects.filter(match=ko).count() == 1


@pytest.mark.django_db
def test_assign_teams_non_gestor_forbidden(client, jugador):
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    ko = MatchFactory(
        round=r32, group="R32", matchday=None,
        home=None, away=None, home_slot="1A", away_slot="2B",
        bracket_code="M76", kickoff=timezone.now() + timedelta(days=10),
    )
    client.force_login(jugador)
    resp = client.post(
        reverse("competicion:assign_teams", args=[ko.id]),
        {"home_code": "ESP", "away_code": "ARG"},
    )
    assert resp.status_code in (302, 403)  # mixin redirige o forbidea
```

- [ ] **Step 2: Ejecutar (deben fallar)**

```bash
pytest competition/tests/test_assign_teams_view.py -v
```

Expected: FAIL (url no existe).

- [ ] **Step 3: Implementar la vista**

Añadir a `competition/views.py` al final:

```python
class AssignTeamsView(GestorRequiredMixin, View):
    """Permite al gestor asignar o corregir los dos equipos de un cruce KO.
    Si el partido ya tenía equipos asignados y hay pronósticos guardados,
    requiere `confirm_invalidate=1` y borra los pronósticos existentes."""

    def post(self, request, match_id):
        m = get_object_or_404(Match, pk=match_id)
        from competition.models import Team

        home_code = (request.POST.get("home_code") or "").strip()
        away_code = (request.POST.get("away_code") or "").strip()
        if not home_code or not away_code or home_code == away_code:
            messages.error(request, "Selecciona dos equipos distintos.")
            return redirect("competicion:manage_results")

        home = Team.objects.filter(code=home_code).first()
        away = Team.objects.filter(code=away_code).first()
        if home is None or away is None:
            messages.error(request, "Equipo no encontrado.")
            return redirect("competicion:manage_results")

        was_assigned = m.has_teams
        existing_preds = Prediction.objects.filter(match=m).exists()

        if was_assigned and existing_preds and request.POST.get("confirm_invalidate") != "1":
            messages.error(
                request,
                "Este cruce ya tiene pronósticos. Marca la casilla de confirmación "
                "para sobrescribir los equipos y borrar los pronósticos existentes.",
            )
            return redirect("competicion:manage_results")

        if was_assigned and existing_preds:
            Prediction.objects.filter(match=m).delete()

        m.home = home
        m.away = away
        m.save(update_fields=["home", "away"])
        messages.success(
            request,
            f"Cruce actualizado · {home.name} vs {away.name}",
        )
        return redirect("competicion:manage_results")
```

- [ ] **Step 4: Añadir la ruta**

En `competition/urls.py`:

```python
urlpatterns = [
    path("", views.CompetitionView.as_view(), name="dashboard"),
    path("pronosticar/<int:match_id>/", views.PredictView.as_view(), name="predict"),
    path("partido/<int:match_id>/", views.MatchDetailView.as_view(), name="detail"),
    path("resultados/", views.ManageResultsView.as_view(), name="manage_results"),
    path("resultados/<int:match_id>/", views.ResultOfficialView.as_view(), name="official"),
    path(
        "resultados/<int:match_id>/equipos/",
        views.AssignTeamsView.as_view(),
        name="assign_teams",
    ),
    path("api/teams/", include(("competition.api.urls", "api"), namespace="api")),
]
```

- [ ] **Step 5: Ejecutar tests**

```bash
pytest competition/tests/test_assign_teams_view.py -v
```

Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add competition/views.py competition/urls.py competition/tests/test_assign_teams_view.py
git commit -m "feat(gestor): AssignTeamsView para asignar/corregir cruces KO"
```

---

## Task 11: Sección "Cruce pendiente" en manage_results

**Files:**
- Modify: `competition/views.py` (ManageResultsView)
- Modify: `templates/competition/manage_results.html`

- [ ] **Step 1: Pasar lista de equipos al contexto**

En `competition/views.py`, dentro de `ManageResultsView.get`, antes del `return render`:

```python
        from competition.models import Team

        all_teams = list(Team.objects.order_by("name"))
        pending_teams_matches = [m for m in ms if not m.has_teams]
```

Añadir al diccionario de contexto:

```python
                "all_teams": all_teams,
                "pending_teams_matches": pending_teams_matches,
```

Y filtrar `upcoming` para que no incluya los `pending_teams` (los partidos sin equipos no van en "Próximos"):

```python
        pending, upcoming, done = [], [], []
        for m in ms:
            st = m.status
            if st == "done":
                done.append(m)
            elif st in ("live", "closed"):
                pending.append(m)
            elif st == "pending_teams":
                continue  # van en pending_teams_matches
            else:
                upcoming.append(m)
```

- [ ] **Step 2: Añadir sección en `manage_results.html`**

Localizar dónde se renderiza "Próximos" y añadir justo encima:

```html
{% if pending_teams_matches %}
<h2 class="eyebrow" style="margin-top:24px">CRUCE PENDIENTE · {{ pending_teams_matches|length }}</h2>
<div class="stagger" style="display:flex;flex-direction:column;gap:14px">
  {% for m in pending_teams_matches %}
  <form method="post" action="{% url 'competicion:assign_teams' m.id %}"
        class="glass" style="padding:14px 16px;border-radius:14px;display:flex;flex-wrap:wrap;gap:10px;align-items:center">
    {% csrf_token %}
    <div style="min-width:200px">
      <span class="eyebrow">{{ m.round.short }} · {{ m.bracket_code }}</span>
      <p style="margin:2px 0 0">
        {{ m.home_slot|slot_label }} vs {{ m.away_slot|slot_label }}
      </p>
      <p class="mono" style="margin:0;font-size:11px;color:var(--text-faint)">
        {{ m.kickoff|date:"D j M · H:i" }}
      </p>
    </div>
    <select name="home_code" class="input" required>
      <option value="">Local…</option>
      {% for t in all_teams %}<option value="{{ t.code }}"{% if m.home and m.home.code == t.code %} selected{% endif %}>{{ t.flag }} {{ t.name }}</option>{% endfor %}
    </select>
    <select name="away_code" class="input" required>
      <option value="">Visitante…</option>
      {% for t in all_teams %}<option value="{{ t.code }}"{% if m.away and m.away.code == t.code %} selected{% endif %}>{{ t.flag }} {{ t.name }}</option>{% endfor %}
    </select>
    <button class="btn btn-primary" type="submit">Asignar equipos</button>
  </form>
  {% endfor %}
</div>
{% endif %}
```

(Cargar el filter al inicio del archivo si no está: `{% load competition_extras %}`.)

- [ ] **Step 3: Smoke test**

```bash
pytest competition/tests/ -v
```

Expected: PASS. No tocamos lógica de pending/upcoming/done, solo añadimos una sección.

- [ ] **Step 4: Commit**

```bash
git add competition/views.py templates/competition/manage_results.html
git commit -m "ui(gestor): sección Cruce pendiente en manage_results"
```

---

## Task 12: Actualizar `docs/DATA_MODEL.md` y página de Reglas

**Files:**
- Modify: `docs/DATA_MODEL.md:123-135`
- Modify: `templates/core/rules.html:125-180`

- [ ] **Step 1: `docs/DATA_MODEL.md`**

En la sección §3 "Estados del partido (derivados)", añadir antes de la fila `open`:

```markdown
| `pending_teams` | uno de los equipos no asignado (`home` o `away` a null) | tarjeta con placeholders ("1º Grupo A"), no apostable |
```

Y reemplazar el primer párrafo de §3 (sobre el `closeAt`) por:

```markdown
Calculados a partir de `kickoff`, el momento actual, el resultado y la asignación de equipos. Las apuestas de un partido se abren cuando se conocen los dos equipos (en grupos: desde el día 1; en KO: al cerrar la ronda anterior) y se cierran 2 horas antes del saque (`closeAt = kickoff − 2h`).
```

Y borrar (si existiera) cualquier referencia a "puerta de jornada" o gate.

- [ ] **Step 2: `templates/core/rules.html`**

Buscar el header "02 · Cuándo cierran las apuestas" y añadir, justo después del párrafo inicial, un sub-bloque corto:

```html
    <p style="margin:0;color:var(--text-dim)">
      Las apuestas de un partido se abren en cuanto se conocen los dos equipos. Los partidos de la fase de grupos están todos abiertos desde el día 1; los cruces de las rondas eliminatorias aparecen como <em>Por definir</em> hasta que la ronda anterior los determine.
    </p>
```

(Localización exacta: dentro de `<section>` "02 · Cuándo cierran las apuestas", después de la `<header>`. Mantener todo lo demás de esa sección.)

- [ ] **Step 3: Commit**

```bash
git add docs/DATA_MODEL.md templates/core/rules.html
git commit -m "docs(reglas): apertura por equipos conocidos + estado pending_teams"
```

---

## Task 13: Verificación final + lint + push

- [ ] **Step 1: Ruff format/check**

```bash
ruff format competition/ && ruff check competition/
```

Expected: sin errores.

- [ ] **Step 2: Suite completa**

```bash
pytest -x -q
```

Expected: todos los tests PASS.

- [ ] **Step 3: Migración aplicable desde cero**

```bash
python manage.py migrate --plan | tail -20
```

Verificar que `0009_match_slots_and_nullable_teams` está en el plan.

- [ ] **Step 4: Commit cualquier ajuste de lint**

Si ruff format modificó algo:

```bash
git add -u
git commit -m "chore: ruff format"
```

- [ ] **Step 5: Push y abrir PR**

```bash
git push -u origin worktree-spec-apuestas-equipos-conocidos
gh pr create --title "feat(competicion): apuestas abren cuando se conocen los dos equipos" --body "$(cat <<'EOF'
## Summary
- Elimina la puerta de jornada en grupos: los 72 partidos quedan abiertos desde el día 1.
- Añade modelo de slots (`home_slot`, `away_slot`, `bracket_code`) y nullable `home`/`away` para soportar partidos KO con equipos pendientes.
- Nuevo estado derivado `Match.status == "pending_teams"` con tarjeta-placeholder ("1º Grupo A") no apostable.
- Servicio `competition/services/bracket.py` con `resolve_slot` (1A/2A/3A, WMnn) + `propagate_after_match` invocado desde `resolve_match`.
- Vista nueva `AssignTeamsView` y sección "Cruce pendiente" en *Resultados* para asignar/corregir equipos manualmente.
- `docs/DATA_MODEL.md` y `templates/core/rules.html` actualizados.

Spec: `docs/superpowers/specs/2026-06-04-apuestas-abren-cuando-equipos-conocidos-design.md`
Plan: `docs/superpowers/plans/2026-06-04-apuestas-abren-cuando-equipos-conocidos.md`

## Test plan
- [x] `pytest -x -q` (toda la suite)
- [x] `ruff check competition/`
- [ ] Manual: crear un partido KO con slots `1A`/`2B` y confirmar que aparece como "Por definir" en el dashboard
- [ ] Manual: cerrar todos los partidos de los grupos A y B → el cruce se autorellena
- [ ] Manual: gestor cambia un equipo asignado → confirmar que pide la casilla de invalidación y borra pronósticos
EOF
)"
```

Expected: PR creado, URL devuelta.

---

## Fuera de scope de este plan (anotado en la spec)

- **Fixture KO real (M73..M104)**: la spec lo lista pero requiere datos FIFA oficiales (calendario, sedes, mapeo grupo → cruce, tabla de mejores terceros). El framework queda listo; cuando el gestor tenga los datos, se carga un fixture aparte sin tocar código.
- **Resolver de mejores terceros (`3WG_S{n}`)**: depende de la tabla FIFA 2026. Por ahora `resolve_slot` devuelve `None` para esos códigos y el gestor los asigna manualmente desde "Cruce pendiente".
- **Prórroga/penaltis en KO**: si los 90' acaban empate, `WMnn` devuelve `None` y el gestor asigna el cruce siguiente.
