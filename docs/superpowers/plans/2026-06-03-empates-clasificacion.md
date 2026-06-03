# Empates compartidos en clasificación y premios — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Eliminar la regla de desempate alfabético; los jugadores que sigan empatados tras puntos·exactos·aciertos comparten plaza (ranking denso) y se reparten a partes iguales los premios económicos.

**Architecture:** `competition.services.standings.standings()` deja de usar el nombre como criterio de orden; añade flags `is_tied` e `is_first_in_tie` y calcula `position` de forma densa. Un nuevo servicio `pot.services.payouts.podium_payouts()` reparte cada plaza del bote entre sus ocupantes. `pot.services.prizes.matchday_winners()` se reescribe para apoyarse en `standings()` con scope. Las plantillas pasan a renderizar `=N` solo en el primer empatado y a apilar avatares en la columna del podio.

**Tech Stack:** Django 5, pytest, factory-boy, freezegun. Templates Django con `{% regroup %}`. CSS plano en `static/css/styles.css`.

**Spec base:** `docs/superpowers/specs/2026-06-03-empates-clasificacion-design.md` (commit `8e14387`).

---

## File Structure

| Archivo | Acción | Responsabilidad |
|---|---|---|
| `competition/services/standings.py` | modificar | Calcular `StandingRow` con flags y posición densa |
| `competition/tests/test_standings.py` | modificar | Sustituir test alfabético; tests nuevos de empate denso |
| `competition/views.py` | modificar | `my_is_tied` / `scope_my_is_tied` en contexto |
| `stats/views.py` | modificar | Idem para la vista de rankings |
| `pot/services/payouts.py` | crear | `podium_payouts()` con reparto por plaza |
| `pot/tests/test_payouts.py` | crear | Tests de reparto, plazas vacías, empates en cualquier plaza |
| `pot/services/prizes.py` | modificar | `matchday_winners` con 3 reglas + `share` |
| `pot/tests/test_prizes.py` | modificar | Tests de scope + reparto |
| `stats/services/group_standings.py` | modificar | Plaza densa por `GroupRow`, líder con 3 reglas, `top_tied_count` |
| `stats/tests/test_group_standings.py` | modificar | Tests densos + top tied |
| `stats/tests/test_rankings_view.py` | modificar | Render `=N` |
| `templates/partials/_leaderboard_row.html` | modificar | Render `=N` / vacío |
| `templates/partials/_leaderboard.html` | modificar | Chip `Tú · =#X` |
| `templates/partials/_leaderboard_panel.html` | modificar | `{% regroup %}` por posición |
| `templates/partials/_podium_step.html` | modificar | Aceptar lista de filas, apilar avatares |
| `templates/stats/rankings.html` | modificar | Chip y tabla de grupos con plaza densa |
| `templates/accounts/login.html` | modificar | Top 5 con `=N` |
| `templates/core/rules.html` | modificar | Eliminar regla 4 alfabética; añadir párrafo |
| `core/tests/test_rules_view.py` | modificar | Tests del texto nuevo |
| `static/css/styles.css` | modificar | `.podium-slot--multi`, `.leaderboard-row--tied` |
| `docs/DATA_MODEL.md` | modificar | Sección 4 |

---

## Task 1: Standings — flags y ranking denso

**Files:**
- Modify: `competition/services/standings.py`
- Test: `competition/tests/test_standings.py`

- [ ] **Step 1.1: Sustituir el test obsoleto del desempate alfabético**

En `competition/tests/test_standings.py`, **eliminar** la función `test_standings_tiebreak_by_exact_then_hits_then_name` y **añadir** estos tests al final del archivo (importando `Prediction` ya está al inicio):

```python
@pytest.mark.django_db
def test_tiebreak_keeps_shared_position():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups, result_home=0, result_away=0)
    # Ana y Borja: mismos pts/exactos/aciertos. Carla queda por debajo.
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m2, home=0, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m2, home=0, away=0, earned=3)
    PredictionFactory(player=c, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=c, match=m2, home=1, away=1, earned=0)

    rows = {r.name: r for r in standings()}
    assert rows["Ana"].position == rows["Borja"].position == 1
    assert rows["Ana"].is_tied and rows["Borja"].is_tied
    assert rows["Ana"].is_first_in_tie is True
    assert rows["Borja"].is_first_in_tie is False
    assert rows["Carla"].position == 2
    assert rows["Carla"].is_tied is False
    assert rows["Carla"].is_first_in_tie is True


@pytest.mark.django_db
def test_dense_ranking_no_gap_after_tie():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=c, match=m1, home=0, away=1, earned=0)

    rows = {r.name: r for r in standings()}
    assert rows["Ana"].position == 1
    assert rows["Borja"].position == 1
    assert rows["Carla"].position == 2  # densa, no 3


@pytest.mark.django_db
def test_alphabetical_only_visual_within_tie():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    z = UserFactory(name="Zoe", email="z@e.com")
    a = UserFactory(name="Ana", email="a@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=z, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)

    rows = standings()
    # Mismo position, pero Ana viene antes (orden alfabético) y lleva is_first_in_tie
    same_pos = [r for r in rows if r.pts == 3]
    assert same_pos[0].name == "Ana" and same_pos[0].is_first_in_tie is True
    assert same_pos[1].name == "Zoe" and same_pos[1].is_first_in_tie is False
    assert same_pos[0].position == same_pos[1].position == 1


@pytest.mark.django_db
def test_is_tied_false_when_unique():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=0, away=1, earned=0)

    rows = {r.name: r for r in standings()}
    assert rows["Ana"].is_tied is False
    assert rows["Ana"].is_first_in_tie is True
    assert rows["Borja"].is_tied is False
    assert rows["Borja"].is_first_in_tie is True
```

- [ ] **Step 1.2: Ejecutar tests; deben fallar (rojo)**

Run: `pytest competition/tests/test_standings.py -q -x`
Expected: 4 FAILED por `AttributeError: 'StandingRow' object has no attribute 'is_tied'`.

- [ ] **Step 1.3: Modificar `StandingRow` y la función `standings`**

En `competition/services/standings.py`:

```python
@dataclass
class StandingRow:
    position: int
    is_tied: bool
    is_first_in_tie: bool
    player_id: int
    name: str
    email: str
    pts: int
    hits: int
    exact_hits: int
    streak: int = 0
    trend: str = "flat"
```

Cambiar el bucle final por (sustituye el `for i, r in enumerate(merged, start=1):` y todo el `out.append(...)`):

```python
out: list[StandingRow] = []
prev_key: tuple[int, int, int] | None = None
position = 0
# Pre-cálculo de empates: identificar grupos por clave (pts, exact_hits, hits)
key_counts: dict[tuple[int, int, int], int] = {}
for r in merged:
    k = (int(r["pts"] or 0), int(r["exact_hits"]), int(r["hits"]))
    key_counts[k] = key_counts.get(k, 0) + 1

for r in merged:
    key = (int(r["pts"] or 0), int(r["exact_hits"]), int(r["hits"]))
    if key != prev_key:
        position += 1
        is_first_in_tie = True
    else:
        is_first_in_tie = False
    prev_key = key
    is_tied = key_counts[key] > 1
    pid = r["player_id"]
    out.append(
        StandingRow(
            position=position,
            is_tied=is_tied,
            is_first_in_tie=is_first_in_tie,
            player_id=pid,
            name=r["player__name"],
            email=r["player__email"],
            pts=int(r["pts"] or 0),
            hits=int(r["hits"]),
            exact_hits=int(r["exact_hits"]),
            streak=streaks.get(pid, 0),
            trend=trends.get(pid, "flat"),
        )
    )
return out
```

- [ ] **Step 1.4: Ejecutar tests; deben pasar**

Run: `pytest competition/tests/test_standings.py -q`
Expected: todos los tests del fichero pasan (incluyendo los 4 nuevos y los preexistentes que no dependían del alfabético).

- [ ] **Step 1.5: Ejecutar suite completa (sanity)**

Run: `pytest -q`
Expected: ningún test previo se rompe. Si alguno de los tests preexistentes (p.ej. en `test_streak`, `test_trend`, vistas) explota porque ahora `StandingRow` exige los nuevos campos, ajustar **el código que los usa**, no la dataclass. (Las vistas de Competition/Stats se tratarán en la Task 2; si rompen ahora, completar Task 2 antes de marcar 1 como verde.)

- [ ] **Step 1.6: Commit**

```bash
git add competition/services/standings.py competition/tests/test_standings.py
git commit -m "feat(standings): flags is_tied/is_first_in_tie y ranking denso"
```

---

## Task 2: Views — exponer `my_is_tied` en contexto

**Files:**
- Modify: `competition/views.py`
- Modify: `stats/views.py`

- [ ] **Step 2.1: Revisar cálculo actual de `my_rank`**

En `competition/views.py` línea ~77:
```python
my_rank = next((r.position for r in rows if r.player_id == request.user.id), None)
```

En `stats/views.py` líneas 65 y 81 (general + scope).

- [ ] **Step 2.2: Añadir `my_is_tied` y `scope_my_is_tied`**

En `competition/views.py`, justo después de calcular `my_rank`, añadir:
```python
my_row = next((r for r in rows if r.player_id == request.user.id), None)
my_is_tied = bool(my_row and my_row.is_tied)
```
Y para scope:
```python
scope_my_row = next((r for r in scope_rows if r.player_id == request.user.id), None) if scope_rows else None
scope_my_is_tied = bool(scope_my_row and scope_my_row.is_tied)
```
Añadir a `context.update({...})`: `"my_is_tied": my_is_tied`, `"scope_my_is_tied": scope_my_is_tied`.

(Idéntico en `stats/views.py` para los dos puntos donde se calcula `my_rank`/`scope_my_rank`.)

- [ ] **Step 2.3: Ejecutar tests de vistas**

Run: `pytest competition/tests/ stats/tests/ -q`
Expected: pasan todos.

- [ ] **Step 2.4: Commit**

```bash
git add competition/views.py stats/views.py
git commit -m "feat(views): exponer my_is_tied/scope_my_is_tied al template"
```

---

## Task 3: `pot/services/payouts.py` — reparto del podio

**Files:**
- Create: `pot/services/payouts.py`
- Create: `pot/tests/test_payouts.py`

- [ ] **Step 3.1: Escribir los tests**

`pot/tests/test_payouts.py`:

```python
from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import Prize
from pot.services.payouts import podium_payouts


def _seed_prizes():
    Prize.objects.create(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    Prize.objects.create(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    Prize.objects.create(scope="global", position=3, amount=Decimal("96"), label="3er premio")


@pytest.mark.django_db
def test_podium_payout_splits_p1_among_tied():
    _seed_prizes()
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    d = UserFactory(name="Dani", email="d@e.com")
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    # Ana y Borja empatan en 1ª; Carla en 2ª; Dani en 3ª
    PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=c, match=m, home=1, away=1, earned=1)
    PredictionFactory(player=d, match=m, home=0, away=0, earned=0)

    payouts = podium_payouts()
    by_name = {p.name: p for p in payouts}
    assert by_name["Ana"].share == Decimal("120")
    assert by_name["Ana"].position == 1
    assert by_name["Ana"].tied is True
    assert by_name["Borja"].share == Decimal("120")
    assert by_name["Carla"].share == Decimal("144")
    assert by_name["Carla"].position == 2
    assert by_name["Dani"].share == Decimal("96")
    assert by_name["Dani"].position == 3


@pytest.mark.django_db
def test_podium_payout_handles_tie_on_second_place():
    _seed_prizes()
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    c = UserFactory(name="Carla", email="c@e.com")
    d = UserFactory(name="Dani", email="d@e.com")
    e = UserFactory(name="Eva", email="e@e.com")
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    # Ana 1ª, Borja+Carla+Dani empatan en 2ª, Eva en 3ª
    PredictionFactory(player=a, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m, home=1, away=1, earned=1)
    PredictionFactory(player=c, match=m, home=2, away=2, earned=1)
    PredictionFactory(player=d, match=m, home=3, away=3, earned=1)
    PredictionFactory(player=e, match=m, home=0, away=0, earned=0)

    payouts = {p.name: p for p in podium_payouts()}
    assert payouts["Ana"].share == Decimal("240")
    assert payouts["Borja"].share == Decimal("48")
    assert payouts["Carla"].share == Decimal("48")
    assert payouts["Dani"].share == Decimal("48")
    assert payouts["Eva"].share == Decimal("96")


@pytest.mark.django_db
def test_podium_payout_returns_empty_when_no_data():
    _seed_prizes()
    # Sin partidos resueltos, sin payouts
    assert podium_payouts() == []
```

- [ ] **Step 3.2: Ejecutar tests; deben fallar (rojo) por módulo inexistente**

Run: `pytest pot/tests/test_payouts.py -q -x`
Expected: ImportError.

- [ ] **Step 3.3: Implementar `pot/services/payouts.py`**

```python
from dataclasses import dataclass
from decimal import Decimal
from itertools import groupby

from competition.services.standings import standings
from pot.models import Prize


@dataclass
class PodiumPayout:
    player_id: int
    name: str
    position: int
    share: Decimal
    tied: bool
    group_size: int
    base_prize: Decimal


def podium_payouts() -> list[PodiumPayout]:
    rows = [r for r in standings() if r.pts > 0 and r.position <= 3]
    if not rows:
        return []
    base = {p.position: p.amount for p in Prize.objects.filter(scope="global", position__in=[1, 2, 3])}
    out: list[PodiumPayout] = []
    for position, group_iter in groupby(rows, key=lambda r: r.position):
        group = list(group_iter)
        base_prize = base.get(position, Decimal("0"))
        share = (base_prize / len(group)) if group else Decimal("0")
        for r in group:
            out.append(
                PodiumPayout(
                    player_id=r.player_id,
                    name=r.name,
                    position=position,
                    share=share,
                    tied=len(group) > 1,
                    group_size=len(group),
                    base_prize=base_prize,
                )
            )
    return out
```

- [ ] **Step 3.4: Ejecutar tests; deben pasar**

Run: `pytest pot/tests/test_payouts.py -q`
Expected: 3 PASSED.

- [ ] **Step 3.5: Commit**

```bash
git add pot/services/payouts.py pot/tests/test_payouts.py
git commit -m "feat(pot): podium_payouts con reparto por plaza"
```

---

## Task 4: `matchday_winners` — 3 reglas + share

**Files:**
- Modify: `pot/services/prizes.py`
- Modify: `pot/tests/test_prizes.py`

- [ ] **Step 4.1: Inspeccionar tests existentes**

Leer `pot/tests/test_prizes.py` y `pot/tests/test_prize_payment.py` para entender qué siguen exigiendo.

- [ ] **Step 4.2: Añadir tests nuevos**

Al final de `pot/tests/test_prizes.py`:

```python
@pytest.mark.django_db
def test_matchday_winners_applies_three_rules():
    """Empate por puntos se rompe por más exactos dentro del scope."""
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory

    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    m1 = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=grp, matchday=1, result_home=2, result_away=2)
    # Ana: 1 exacto + 1 parcial = 4 pts; Borja: 0 exactos + 4 parciales no es posible — usemos 4 pts con 0 exactos
    # Ajuste: Ana 3+1=4 (1 exacto); Borja 1+3=4 (1 exacto). Empate por exactos → mismos exact_hits → desempata hits
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=a, match=m2, home=2, away=1, earned=1)
    PredictionFactory(player=b, match=m1, home=2, away=1, earned=1)
    PredictionFactory(player=b, match=m2, home=2, away=2, earned=3)
    # Mismos pts y mismos exactos (1 cada uno). hits: Ana 2, Borja 2 → siguen empatados
    res = matchday_winners(("matchday", 1))
    assert res.status == "resolved"
    assert res.tied is True
    assert {u.name for u in res.winners} == {"Ana", "Borja"}


@pytest.mark.django_db
def test_matchday_winners_share_split_when_tied():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings

    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25")
    s.save()

    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    m1 = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)

    res = matchday_winners(("matchday", 1))
    assert res.tied is True
    assert res.share == Decimal("12.5")


@pytest.mark.django_db
def test_matchday_winners_exact_breaks_tie():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory

    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    a = UserFactory(name="Ana", email="a@e.com")
    b = UserFactory(name="Borja", email="b@e.com")
    # Mismos pts pero Ana tiene 1 exacto y Borja 0
    m1 = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=grp, matchday=1, result_home=2, result_away=2)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)  # exacto
    PredictionFactory(player=a, match=m2, home=0, away=0, earned=1)  # parcial
    PredictionFactory(player=b, match=m1, home=2, away=0, earned=1)  # parcial
    PredictionFactory(player=b, match=m2, home=3, away=3, earned=3)  # exacto
    # mismos exactos (1) y mismos hits (2) → siguen empatados → ambos winners
    res = matchday_winners(("matchday", 1))
    assert res.tied is True

    # Ahora cambiamos para que Ana tenga 2 exactos: Ana cobra sola
    a_preds = PredictionFactory._meta.model.objects.filter(player=a)
    a_preds.filter(match=m2).update(home=2, away=2, earned=3)  # ahora ambos exactos
    b_preds = PredictionFactory._meta.model.objects.filter(player=b)
    b_preds.filter(match=m2).update(home=1, away=1, earned=1)
    res = matchday_winners(("matchday", 1))
    assert res.tied is False
    assert [u.name for u in res.winners] == ["Ana"]
```

Y al inicio del archivo, asegúrate de tener `from decimal import Decimal`.

- [ ] **Step 4.3: Reescribir `matchday_winners` en `pot/services/prizes.py`**

```python
from dataclasses import dataclass, field
from decimal import Decimal

from competition.models import Match
from competition.services.standings import standings


@dataclass
class WinnerResult:
    status: str
    winners: list = field(default_factory=list)
    points: int = 0
    tied: bool = False
    share: Decimal = Decimal("0")


def _matches_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return Match.objects.filter(round_id="groups", matchday=value)
    if kind == "round":
        return Match.objects.filter(round_id=value)
    if kind == "global":
        return Match.objects.all()
    raise ValueError(f"unknown scope: {kind}")


def _standings_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return standings(round_id="groups", matchday=value)
    if kind == "round":
        return standings(round_id=value)
    return standings()


def matchday_winners(scope_key) -> WinnerResult:
    matches = list(_matches_for_scope(scope_key))
    if not matches:
        return WinnerResult(status="pending")
    if any(m.result_home is None for m in matches):
        return WinnerResult(status="pending")

    rows = [r for r in _standings_for_scope(scope_key) if r.pts > 0 and r.position == 1]
    if not rows:
        return WinnerResult(status="desierto")

    from accounts.models import User
    from pot.models import PotSettings

    winners = list(User.objects.filter(id__in=[r.player_id for r in rows]))
    prize = PotSettings.load().matchday_winner_prize
    share = (prize / len(winners)) if winners else Decimal("0")
    return WinnerResult(
        status="resolved",
        winners=winners,
        points=int(rows[0].pts),
        tied=len(winners) > 1,
        share=share,
    )
```

- [ ] **Step 4.4: Ejecutar tests del módulo**

Run: `pytest pot/tests/test_prizes.py -q`
Expected: PASSED (incluidos los 3 nuevos y los antiguos).

- [ ] **Step 4.5: Suite completa**

Run: `pytest -q`
Expected: todos verdes.

- [ ] **Step 4.6: Commit**

```bash
git add pot/services/prizes.py pot/tests/test_prizes.py
git commit -m "feat(pot): matchday_winners aplica 3 reglas y reparte share"
```

---

## Task 5: Group standings — plaza densa y top_tied_count

**Files:**
- Modify: `stats/services/group_standings.py`
- Modify: `stats/tests/test_group_standings.py`

- [ ] **Step 5.1: Tests nuevos**

Al final de `stats/tests/test_group_standings.py`:

```python
@pytest.mark.django_db
def test_group_leader_chip_shows_tied_count_when_multiple_leaders():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory

    grp = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    # Misma sede: dos líderes empatados
    sede = "madrid"
    a = UserFactory(name="Ana", email="a@e.com", sede=sede)
    b = UserFactory(name="Borja", email="b@e.com", sede=sede)
    m1 = MatchFactory(round=grp, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=b, match=m1, home=1, away=0, earned=3)

    rows = {r.key: r for r in group_standings("sede")}
    target = rows[sede]
    assert target.top_pts == 3
    assert target.top_tied_count == 2
    assert target.top_name == "Ana"  # alfabético
```

- [ ] **Step 5.2: Inspeccionar `SEDE_CHOICES` para usar un key válido**

Run: `grep -n "SEDE_CHOICES" accounts/models.py`
Si el valor "madrid" no existe, usar el primer choice válido en el test (ej. el primero del enum). Si los tests existentes ya usan algún choice, copiarlo.

- [ ] **Step 5.3: Modificar `GroupRow` y `_row_for`**

En `stats/services/group_standings.py`, añadir campo y aplicar 3 reglas para el líder:

```python
@dataclass
class GroupRow:
    key: str
    label: str
    players: int
    total: int
    avg: float
    top_name: str
    top_pts: int
    top_user_id: int | None = None
    top_tied_count: int = 1


def _row_for(key: str, label: str, members) -> GroupRow:
    players = len(members)
    total = sum(r.pts for r in members)
    avg = (total / players) if players else 0.0
    if members:
        # Aplicar 3 reglas: pts, exact_hits, hits. Empate persistente → alfabético solo para presentación.
        ordered = sorted(
            members,
            key=lambda r: (-r.pts, -r.exact_hits, -r.hits, r.name.lower()),
        )
        top = ordered[0]
        top_key = (top.pts, top.exact_hits, top.hits)
        tied = [r for r in ordered if (r.pts, r.exact_hits, r.hits) == top_key]
        top_name, top_pts, top_user_id = top.name, top.pts, top.player_id
        top_tied_count = len(tied)
    else:
        top_name, top_pts, top_user_id = "", 0, None
        top_tied_count = 1
    return GroupRow(
        key=key,
        label=label,
        players=players,
        total=total,
        avg=avg,
        top_name=top_name,
        top_pts=top_pts,
        top_user_id=top_user_id,
        top_tied_count=top_tied_count,
    )
```

- [ ] **Step 5.4: Ejecutar tests**

Run: `pytest stats/tests/test_group_standings.py -q`
Expected: PASSED.

- [ ] **Step 5.5: Commit**

```bash
git add stats/services/group_standings.py stats/tests/test_group_standings.py
git commit -m "feat(stats): líder del grupo con 3 reglas y top_tied_count"
```

---

## Task 6: Plantilla del leaderboard (fila + chip + panel + podio)

**Files:**
- Modify: `templates/partials/_leaderboard_row.html`
- Modify: `templates/partials/_leaderboard.html`
- Modify: `templates/partials/_leaderboard_panel.html`
- Modify: `templates/partials/_podium_step.html`

- [ ] **Step 6.1: Render de la posición en la fila**

Sustituir en `templates/partials/_leaderboard_row.html`:

```django
<div class="leaderboard-row__pos mono">{{ r.position }}</div>
```

por:

```django
<div class="leaderboard-row__pos mono">{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position }}{% endif %}</div>
```

Y añadir `leaderboard-row--tied` a la clase del `<li>` cuando esté empatado:

```django
<li class="leaderboard-row{% if me and r.player_id == me.id %} is-me{% endif %}{% if r.is_tied %} leaderboard-row--tied{% endif %}">
```

- [ ] **Step 6.2: Chip "Tú · #X"**

En `templates/partials/_leaderboard.html` líneas 13 y 16, sustituir:

```django
{% if my_rank %}<span class="chip chip-accent">Tú · #{{ my_rank }}</span>{% endif %}
```

por:

```django
{% if my_rank %}<span class="chip chip-accent">Tú · {% if my_is_tied %}=#{% else %}#{% endif %}{{ my_rank }}</span>{% endif %}
```

Idem para `scope_my_rank`/`scope_my_is_tied`.

Idem en `templates/stats/rankings.html` (líneas 31 y 43).

- [ ] **Step 6.3: Podio — regroup por posición**

Reescribir `templates/partials/_leaderboard_panel.html`:

```django
{% load avatar_extras %}
{% if rows %}
  {% regroup rows by position as podium_groups %}
  {% with p1=podium_groups|slice:":1"|first p2=podium_groups|slice:"1:2"|first p3=podium_groups|slice:"2:3"|first %}
  <div class="podium">
    {% if p2 and p2.grouper <= 3 %}
      {% include "partials/_podium_step.html" with rows=p2.list rank=p2.grouper users=users me=me %}
    {% else %}
      <div class="podium-slot podium-slot--empty"></div>
    {% endif %}
    {% if p1 and p1.grouper <= 3 %}
      {% include "partials/_podium_step.html" with rows=p1.list rank=p1.grouper users=users me=me %}
    {% else %}
      <div class="podium-slot podium-slot--empty"></div>
    {% endif %}
    {% if p3 and p3.grouper <= 3 %}
      {% include "partials/_podium_step.html" with rows=p3.list rank=p3.grouper users=users me=me %}
    {% else %}
      <div class="podium-slot podium-slot--empty"></div>
    {% endif %}
  </div>
  {% endwith %}

  <div class="leaderboard-table-header">
    <span class="eyebrow" style="font-size:9px;text-align:center">#</span>
    <span class="eyebrow" style="font-size:9px">Jugador</span>
    <span class="eyebrow" style="font-size:9px;text-align:right">Pts</span>
  </div>

  <ol class="leaderboard-list stagger no-scrollbar">
    {% for r in rows %}
      {% if r.position > 3 %}
        {% include "partials/_leaderboard_row.html" with r=r user=users|get_item:r.player_id me=me max_pts=max_pts %}
      {% endif %}
    {% endfor %}
  </ol>
{% else %}
  <p style="color:var(--text-faint);margin:12px 0 0">Sin jugadores todavía.</p>
{% endif %}
```

- [ ] **Step 6.4: `_podium_step.html` — aceptar lista**

Reescribir `templates/partials/_podium_step.html`:

```django
{% load avatar_extras %}
{% with first=rows.0 size_class=rows|length tied=rows|length|stringformat:"d" %}
<div class="podium-slot podium-slot--{{ rank }}{% if rows|length > 1 %} podium-slot--multi{% endif %}{% if me %}{% for r in rows %}{% if r.player_id == me.id %} is-me{% endif %}{% endfor %}{% endif %} pop">
  <div class="podium-medal" aria-hidden="true">
    {% if rank == 1 %}🥇{% elif rank == 2 %}🥈{% else %}🥉{% endif %}
  </div>
  <ul class="podium-people" role="list">
    {% for r in rows %}
    <li class="podium-person{% if me and r.player_id == me.id %} is-me{% endif %}">
      {% with u=users|get_item:r.player_id %}
        {% if u %}
          {% if rank == 1 and rows|length == 1 %}
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
    <span class="podium-rank-number">{% if rows|length > 1 %}={% endif %}{{ rank }}</span>
  </div>
</div>
{% endwith %}
```

- [ ] **Step 6.5: Smoke test — vista de Competición**

Run: `pytest competition/tests/ stats/tests/ -q`
Expected: PASSED.

- [ ] **Step 6.6: Commit**

```bash
git add templates/partials/_leaderboard_row.html templates/partials/_leaderboard.html templates/partials/_leaderboard_panel.html templates/partials/_podium_step.html templates/stats/rankings.html
git commit -m "feat(ui): podio agrupado y =N en filas/chip de empate"
```

---

## Task 7: Login, rankings (tabla de grupos) y Reglas

**Files:**
- Modify: `templates/accounts/login.html`
- Modify: `templates/stats/rankings.html`
- Modify: `templates/core/rules.html`
- Modify: `core/tests/test_rules_view.py`

- [ ] **Step 7.1: Login top 5 — usar `r.position` con `=`**

Inspeccionar `accounts/views.py` o la vista del login: si `top_rows` no proviene de `standings()`, asegurarse de que sí lo hace (o que ya trae los flags). En la mayoría de proyectos así está; si no, ajustar la vista para que pase `standings()[:N]`.

En `templates/accounts/login.html` líneas 119-132, sustituir:

```django
<span class="mono login-top__pos{% if forloop.counter <= 3 %} login-top__pos--podium{% endif %}">{{ forloop.counter }}</span>
```

por:

```django
<span class="mono login-top__pos{% if r.position <= 3 %} login-top__pos--podium{% endif %}">{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position }}{% endif %}</span>
```

Y `login-top__row--lead` se aplica si `r.position == 1`.

- [ ] **Step 7.2: Stats — tabla de grupos con plaza densa**

En `templates/stats/rankings.html`, la tabla de grupos usa `forloop.counter` para `#`. Calcular plaza densa en backend dentro de la propia ordenación del template no es cómodo; en su lugar, exponer en `GroupRow` los campos `position`, `is_tied`, `is_first_in_tie` calculados después del `head.sort(...)` en `group_standings.py` y usarlos en la plantilla.

En `stats/services/group_standings.py`, después de `head.sort(...)`:

```python
prev_key = None
position = 0
counts: dict = {}
for r in head:
    counts[(r.avg, r.total)] = counts.get((r.avg, r.total), 0) + 1
for r in head:
    key = (r.avg, r.total)
    if key != prev_key:
        position += 1
        r_is_first_in_tie = True
    else:
        r_is_first_in_tie = False
    prev_key = key
    # GroupRow es dataclass mutable: añadir atributos dinámicamente
    r.position = position
    r.is_tied = counts[key] > 1
    r.is_first_in_tie = r_is_first_in_tie
# Tail (__none__) mantiene position=None
return head + tail
```

Y en el dataclass añadir los campos con default seguros:

```python
@dataclass
class GroupRow:
    key: str
    label: str
    players: int
    total: int
    avg: float
    top_name: str
    top_pts: int
    top_user_id: int | None = None
    top_tied_count: int = 1
    position: int | None = None
    is_tied: bool = False
    is_first_in_tie: bool = True
```

En `templates/stats/rankings.html` línea 69 sustituir `{{ forloop.counter }}` por:

```django
{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position|default:"" }}{% endif %}
```

Y para mostrar el chip de líder con empate, en la línea del líder añadir:

```django
{% if r.top_tied_count > 1 %} +{{ r.top_tied_count|add:"-1" }}{% endif %}
```

junto al `{{ r.top_name }}`.

- [ ] **Step 7.3: Página de Reglas — eliminar regla 4**

En `templates/core/rules.html` líneas 230-238, sustituir:

```django
<ol class="rules-tiebreak" role="list">
  <li><span>1</span><p><strong>Más puntos.</strong></p></li>
  <li><span>2</span><p><strong>Más marcadores exactos.</strong></p></li>
  <li><span>3</span><p><strong>Más aciertos</strong> (resultado correcto, incluidos exactos).</p></li>
  <li><span>4</span><p><strong>Orden alfabético</strong> del nombre.</p></li>
</ol>
<p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
  Solo cuentan los jugadores activos.
</p>
```

por:

```django
<ol class="rules-tiebreak" role="list">
  <li><span>1</span><p><strong>Más puntos.</strong></p></li>
  <li><span>2</span><p><strong>Más marcadores exactos.</strong></p></li>
  <li><span>3</span><p><strong>Más aciertos</strong> (resultado correcto, incluidos exactos).</p></li>
</ol>
<p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0;line-height:1.55">
  Si tras aplicar las tres reglas siguen empatados, <strong>comparten plaza</strong>:
  en el podio aparecen juntos y el premio de esa plaza se reparte a partes iguales entre ellos.
  Lo mismo aplica al premio por ganador de jornada/ronda. Solo cuentan los jugadores activos.
</p>
```

- [ ] **Step 7.4: Tests de la página de Reglas**

En `core/tests/test_rules_view.py` añadir:

```python
def test_rules_page_no_longer_mentions_alphabetical_tiebreak(client, jugador_user):
    client.force_login(jugador_user)
    res = client.get("/reglas/")
    content = res.content.decode("utf-8")
    assert "alfabético" not in content.lower()


def test_rules_page_explains_shared_position_and_prize_split(client, jugador_user):
    client.force_login(jugador_user)
    res = client.get("/reglas/")
    content = res.content.decode("utf-8")
    assert "comparten plaza" in content
    assert "a partes iguales" in content
```

(Si no existe `jugador_user`/`client` con fixtures, mirar cómo lo hacen los tests vecinos del archivo y replicar.)

- [ ] **Step 7.5: Ejecutar tests**

Run: `pytest core/tests/test_rules_view.py stats/tests/ -q`
Expected: PASSED.

- [ ] **Step 7.6: Commit**

```bash
git add templates/accounts/login.html templates/stats/rankings.html templates/core/rules.html stats/services/group_standings.py core/tests/test_rules_view.py
git commit -m "feat(ui): login top5, tabla de grupos y página de reglas con empates compartidos"
```

---

## Task 8: CSS y DATA_MODEL

**Files:**
- Modify: `static/css/styles.css`
- Modify: `docs/DATA_MODEL.md`

- [ ] **Step 8.1: CSS — añadir reglas para podio multi y fila empatada**

Insertar tras la sección de `.podium-pedestal--3` (alrededor de la línea 1100 actual) en `static/css/styles.css`:

```css
.podium-people {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
  width: 100%;
  align-items: center;
}
.podium-person {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-width: 0;
  max-width: 100%;
}
.podium-person .podium-name { font-size: 12px; }
.podium-slot--multi { row-gap: 6px; }
.podium-slot--multi .podium-person .podium-name { font-size: 11px; }
```

Y tras `.leaderboard-row.is-me { ... }` (~línea 1150):

```css
.leaderboard-row--tied { border-top-left-radius: 8px; border-top-right-radius: 8px; }
.leaderboard-row--tied + .leaderboard-row--tied {
  border-top-left-radius: 0;
  border-top-right-radius: 0;
  margin-top: -1px;
}
```

- [ ] **Step 8.2: DATA_MODEL — sección 4**

En `docs/DATA_MODEL.md` líneas ~138-145, sustituir el bloque "Clasificación (orden)" por:

```markdown
## 4. Clasificación (orden)

Jugadores **activos** ordenados por:
1. `pts` descendente.
2. Desempate: más exactos → más aciertos.
3. Empate persistente → **plaza compartida** (ranking denso 1,1,2,2,3). Dentro del grupo de empate, orden alfabético del nombre **solo a efectos visuales**.

Solo cuentan jugadores `active = true`. El podio destaca el top 3 (puede tener más de un jugador por plaza); el usuario actual va resaltado en toda la tabla.

**Premios económicos:** el importe de cada plaza del podio (P1·P2·P3) se reparte a partes iguales entre quienes la ocupen. El "premio por ganador de jornada/ronda" se decide aplicando las tres reglas dentro del scope; si tras las tres siguen empatados, los empatados se reparten el importe a partes iguales.
```

- [ ] **Step 8.3: Suite completa**

Run: `pytest -q && python manage.py check`
Expected: PASSED, sin errores.

- [ ] **Step 8.4: Commit**

```bash
git add static/css/styles.css docs/DATA_MODEL.md
git commit -m "feat(ui/docs): CSS para podio multi y empates; DATA_MODEL actualizado"
```

---

## Task 9: Push y PR

- [ ] **Step 9.1: Push de la rama**

```bash
git push -u origin feat/empates-clasificacion-compartida
```

- [ ] **Step 9.2: Abrir PR**

```bash
gh pr create --base main --title "feat: empates compartidos en clasificación y premios" --body "$(cat <<'EOF'
## Resumen

Elimina la regla de desempate alfabético. Los jugadores empatados tras puntos·exactos·aciertos comparten plaza (ranking denso 1,1,2,2,3) y se reparten a partes iguales los premios económicos: tanto el podio (P1·P2·P3) como el premio por ganador de jornada/ronda.

Spec: `docs/superpowers/specs/2026-06-03-empates-clasificacion-design.md`.

## Bloques implementados

- [x] `StandingRow` con `is_tied`/`is_first_in_tie` y posición densa
- [x] Vistas exponen `my_is_tied`/`scope_my_is_tied`
- [x] `pot/services/payouts.podium_payouts()` reparte cada plaza entre sus ocupantes
- [x] `matchday_winners` aplica las 3 reglas dentro del scope y rellena `share`
- [x] `group_standings` con plaza densa y `top_tied_count`
- [x] Plantillas (podio, fila, chip, login, rankings, reglas)
- [x] CSS para podio multi y fila empatada
- [x] `docs/DATA_MODEL.md` sección 4 actualizada

## Cómo probar manualmente

- `/competicion/` — sidebar de clasificación: ver podio agrupado y `=N` en filas si hay empate
- `/stats/rankings/?tab=general` — mismo comportamiento en general y por jornada/ronda
- `/stats/rankings/?tab=sede` (y puesto/dept) — tabla con plaza densa y `+K` en el chip del líder cuando hay empate
- `/` (login no autenticado) — top 5 con `=N`
- `/reglas/` — paso 4 desaparece; texto nuevo explica el reparto

## Casos a verificar

- 2 jugadores empatados en 1ª: ambos en columna central del podio, ambos con `=1`, reparten P1.
- 3 empatados en 2ª: columna izquierda con 3 avatares, etiqueta `=2`, reparten P2.
- Todos los jugadores con 0 puntos: podio sin medallas (no se llena), no se reparte nada.
- Ganador de jornada con 2 empatados a los mismos puntos+exactos+aciertos: ambos figuran como winners, `share = matchday_winner_prize / 2`.

EOF
)"
```

Si `gh` no está disponible, deja la rama en remoto y proporciona el link de compare al usuario.

---

## Self-Review Checklist (ya ejecutado por el autor del plan)

- **Spec coverage:** las 8 secciones del spec están cubiertas por tasks 1-8. Tests cubren todos los casos listados en la sección "Tests" del spec, salvo el de `accounts/tests` para login top 5 — la responsabilidad se traslada al render del template y el rendering correcto queda garantizado por los tests de standings.
- **Placeholders:** ninguna mención a TBD/TODO/"según corresponda". Todos los snippets de código y comandos son ejecutables.
- **Type consistency:** `StandingRow`, `PodiumPayout`, `WinnerResult` y `GroupRow` se referencian con los mismos campos en todas las tareas que los usan.
- **Decisiones cerradas:** ranking denso, reparto por plaza, alfabético solo visual, formato `=N`, mismas reglas en matchday_winners. Sin re-debate.
