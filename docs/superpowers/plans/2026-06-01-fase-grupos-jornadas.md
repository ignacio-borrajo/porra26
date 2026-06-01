# Fase de grupos por jornadas — Plan de implementación

> **Para workers agentes:** SUB-SKILL REQUERIDO: usar `superpowers:subagent-driven-development` (recomendado) o `superpowers:executing-plans` para implementar este plan tarea a tarea. Los pasos usan sintaxis `- [ ]` para seguimiento.

**Goal:** Cargar el calendario real del Mundial 2026 (48 selecciones, 72 partidos de fase de grupos) y abrir las jornadas progresivamente: la J{N} de cada grupo está bloqueada hasta que todos los partidos de la J{N-1} hayan alcanzado su `kickoff`.

**Architecture:** Sin cambios de modelo. Un servicio `matchday_gate` decide si una jornada está abierta. Una propiedad nueva `Match.predictions_open` combina la regla existente de cierre con la puerta de jornada y es la única que usan vistas y templates de pronóstico. La UI añade un sub-selector `J1·J2·J3` dentro de la ronda `groups`. Un management command `seed_world_cup_2026` carga el calendario de forma idempotente por clave funcional `(round, group, matchday, home, away)`.

**Tech Stack:** Django 5 + Python 3.12. Tests con `pytest`, `pytest-django`, `freezegun`, factorías existentes en `competition/tests/factories.py` y `accounts/tests/factories.py`.

**Spec:** `docs/superpowers/specs/2026-06-01-fase-grupos-jornadas-design.md`.

---

## File Structure

### Archivos nuevos
- `competition/services/matchday_gate.py` — funciones `is_matchday_open()` y `previous_matchday_close_info()`.
- `competition/management/__init__.py` — paquete vacío.
- `competition/management/commands/__init__.py` — paquete vacío.
- `competition/management/commands/seed_world_cup_2026.py` — carga idempotente.
- `templates/partials/_matchday_selector.html` — sub-selector de jornada.
- `competition/tests/test_matchday_gate.py` — tests del servicio.
- `competition/tests/test_seed_command.py` — tests del comando seed.

### Archivos modificados
- `fixtures/teams.json` — 48 selecciones (16 existentes + 32 nuevas).
- `fixtures/world_cup_2026.json` — sustituir 4 placeholders por 72 partidos reales.
- `competition/models.py` — añadir `Match.predictions_open`.
- `competition/views.py` — sub-selector y default de jornada en `CompetitionView` y `ManageResultsView`; bloqueo en `PredictView`.
- `templates/competition/dashboard.html` — incluir sub-selector y banner.
- `templates/competition/_match_card.html` — chip 🔒 y enlace inerte cuando la jornada está bloqueada.
- `templates/competition/manage_results.html` — incluir sub-selector (sin gating).
- `competition/tests/test_competition_view.py` — añadir tests del sub-selector y del bloqueo.
- `competition/tests/test_prediction.py` — añadir tests de POST bloqueado por jornada.

### Convenciones del proyecto (verificadas)
- Tests con `pytest.mark.django_db`; `conftest.py` activa BD automáticamente.
- Factorías: `RoundFactory`, `TeamFactory`, `MatchFactory`, `PredictionFactory` en `competition/tests/factories.py`; `UserFactory`, `GestorFactory` en `accounts/tests/factories.py` con `must_change_password=False` pasado explícitamente.
- `Match.kickoff` siempre UTC (DB en UTC; Django `USE_TZ=True`).
- Lint: `ruff check` + `ruff format`.

---

## Datos de referencia (para el seed)

### Selecciones nuevas (32) — añadir a `fixtures/teams.json`

```json
{"model":"competition.team","pk":"RSA","fields":{"name":"Sudáfrica","flag":"🇿🇦"}},
{"model":"competition.team","pk":"KOR","fields":{"name":"Corea del Sur","flag":"🇰🇷"}},
{"model":"competition.team","pk":"CZE","fields":{"name":"Chequia","flag":"🇨🇿"}},
{"model":"competition.team","pk":"BIH","fields":{"name":"Bosnia y Herzegovina","flag":"🇧🇦"}},
{"model":"competition.team","pk":"QAT","fields":{"name":"Catar","flag":"🇶🇦"}},
{"model":"competition.team","pk":"SUI","fields":{"name":"Suiza","flag":"🇨🇭"}},
{"model":"competition.team","pk":"HAI","fields":{"name":"Haití","flag":"🇭🇹"}},
{"model":"competition.team","pk":"SCO","fields":{"name":"Escocia","flag":"🏴󠁧󠁢󠁳󠁣󠁴󠁿"}},
{"model":"competition.team","pk":"PAR","fields":{"name":"Paraguay","flag":"🇵🇾"}},
{"model":"competition.team","pk":"AUS","fields":{"name":"Australia","flag":"🇦🇺"}},
{"model":"competition.team","pk":"TUR","fields":{"name":"Turquía","flag":"🇹🇷"}},
{"model":"competition.team","pk":"CUW","fields":{"name":"Curazao","flag":"🇨🇼"}},
{"model":"competition.team","pk":"CIV","fields":{"name":"Costa de Marfil","flag":"🇨🇮"}},
{"model":"competition.team","pk":"ECU","fields":{"name":"Ecuador","flag":"🇪🇨"}},
{"model":"competition.team","pk":"SWE","fields":{"name":"Suecia","flag":"🇸🇪"}},
{"model":"competition.team","pk":"TUN","fields":{"name":"Túnez","flag":"🇹🇳"}},
{"model":"competition.team","pk":"EGY","fields":{"name":"Egipto","flag":"🇪🇬"}},
{"model":"competition.team","pk":"IRN","fields":{"name":"Irán","flag":"🇮🇷"}},
{"model":"competition.team","pk":"NZL","fields":{"name":"Nueva Zelanda","flag":"🇳🇿"}},
{"model":"competition.team","pk":"CPV","fields":{"name":"Cabo Verde","flag":"🇨🇻"}},
{"model":"competition.team","pk":"KSA","fields":{"name":"Arabia Saudí","flag":"🇸🇦"}},
{"model":"competition.team","pk":"SEN","fields":{"name":"Senegal","flag":"🇸🇳"}},
{"model":"competition.team","pk":"IRQ","fields":{"name":"Irak","flag":"🇮🇶"}},
{"model":"competition.team","pk":"NOR","fields":{"name":"Noruega","flag":"🇳🇴"}},
{"model":"competition.team","pk":"ALG","fields":{"name":"Argelia","flag":"🇩🇿"}},
{"model":"competition.team","pk":"AUT","fields":{"name":"Austria","flag":"🇦🇹"}},
{"model":"competition.team","pk":"JOR","fields":{"name":"Jordania","flag":"🇯🇴"}},
{"model":"competition.team","pk":"COD","fields":{"name":"RD Congo","flag":"🇨🇩"}},
{"model":"competition.team","pk":"UZB","fields":{"name":"Uzbekistán","flag":"🇺🇿"}},
{"model":"competition.team","pk":"COL","fields":{"name":"Colombia","flag":"🇨🇴"}},
{"model":"competition.team","pk":"GHA","fields":{"name":"Ghana","flag":"🇬🇭"}},
{"model":"competition.team","pk":"PAN","fields":{"name":"Panamá","flag":"🇵🇦"}}
```

### Calendario completo — 72 partidos

Las horas se almacenan en **UTC** (las fuentes consultadas dan los horarios en BST = UTC+1 en junio; en el comando seed los datos ya están convertidos a UTC). Cada partido lleva `round="groups"`, `group` (`A`..`L`), `matchday` (`1`..`3`).

Datos canónicos (Python tuples para usarlos en el seed; orden: `group, matchday, home, away, kickoff UTC`):

```python
MATCHES = [
    # Grupo A: MEX, RSA, KOR, CZE
    ("A", 1, "MEX", "RSA", "2026-06-11T19:00:00Z"),
    ("A", 1, "KOR", "CZE", "2026-06-12T02:00:00Z"),
    ("A", 2, "CZE", "RSA", "2026-06-18T16:00:00Z"),
    ("A", 2, "MEX", "KOR", "2026-06-19T01:00:00Z"),
    ("A", 3, "RSA", "KOR", "2026-06-25T01:00:00Z"),
    ("A", 3, "CZE", "MEX", "2026-06-25T01:00:00Z"),
    # Grupo B: CAN, BIH, QAT, SUI
    ("B", 1, "CAN", "BIH", "2026-06-12T19:00:00Z"),
    ("B", 1, "QAT", "SUI", "2026-06-13T19:00:00Z"),
    ("B", 2, "SUI", "BIH", "2026-06-18T19:00:00Z"),
    ("B", 2, "CAN", "QAT", "2026-06-18T22:00:00Z"),
    ("B", 3, "SUI", "CAN", "2026-06-24T19:00:00Z"),
    ("B", 3, "BIH", "QAT", "2026-06-24T19:00:00Z"),
    # Grupo C: BRA, MAR, HAI, SCO
    ("C", 1, "BRA", "MAR", "2026-06-13T22:00:00Z"),
    ("C", 1, "HAI", "SCO", "2026-06-14T01:00:00Z"),
    ("C", 2, "SCO", "MAR", "2026-06-19T22:00:00Z"),
    ("C", 2, "BRA", "HAI", "2026-06-20T00:30:00Z"),
    ("C", 3, "MAR", "HAI", "2026-06-24T22:00:00Z"),
    ("C", 3, "SCO", "BRA", "2026-06-24T22:00:00Z"),
    # Grupo D: USA, PAR, AUS, TUR
    ("D", 1, "USA", "PAR", "2026-06-13T01:00:00Z"),
    ("D", 1, "AUS", "TUR", "2026-06-14T04:00:00Z"),
    ("D", 2, "USA", "AUS", "2026-06-19T19:00:00Z"),
    ("D", 2, "TUR", "PAR", "2026-06-20T03:00:00Z"),
    ("D", 3, "TUR", "USA", "2026-06-26T02:00:00Z"),
    ("D", 3, "PAR", "AUS", "2026-06-26T02:00:00Z"),
    # Grupo E: GER, CUW, CIV, ECU
    ("E", 1, "GER", "CUW", "2026-06-14T17:00:00Z"),
    ("E", 1, "CIV", "ECU", "2026-06-14T23:00:00Z"),
    ("E", 2, "GER", "CIV", "2026-06-20T20:00:00Z"),
    ("E", 2, "ECU", "CUW", "2026-06-21T00:00:00Z"),
    ("E", 3, "CUW", "CIV", "2026-06-25T20:00:00Z"),
    ("E", 3, "ECU", "GER", "2026-06-25T20:00:00Z"),
    # Grupo F: NED, JPN, SWE, TUN
    ("F", 1, "NED", "JPN", "2026-06-14T20:00:00Z"),
    ("F", 1, "SWE", "TUN", "2026-06-15T02:00:00Z"),
    ("F", 2, "NED", "SWE", "2026-06-20T17:00:00Z"),
    ("F", 2, "TUN", "JPN", "2026-06-21T04:00:00Z"),
    ("F", 3, "TUN", "NED", "2026-06-25T23:00:00Z"),
    ("F", 3, "JPN", "SWE", "2026-06-25T23:00:00Z"),
    # Grupo G: BEL, EGY, IRN, NZL
    ("G", 1, "BEL", "EGY", "2026-06-15T19:00:00Z"),
    ("G", 1, "IRN", "NZL", "2026-06-16T01:00:00Z"),
    ("G", 2, "BEL", "IRN", "2026-06-21T19:00:00Z"),
    ("G", 2, "NZL", "EGY", "2026-06-22T01:00:00Z"),
    ("G", 3, "NZL", "BEL", "2026-06-27T03:00:00Z"),
    ("G", 3, "EGY", "IRN", "2026-06-27T03:00:00Z"),
    # Grupo H: ESP, CPV, KSA, URU
    ("H", 1, "ESP", "CPV", "2026-06-15T16:00:00Z"),
    ("H", 1, "KSA", "URU", "2026-06-15T22:00:00Z"),
    ("H", 2, "ESP", "KSA", "2026-06-21T16:00:00Z"),
    ("H", 2, "URU", "CPV", "2026-06-21T22:00:00Z"),
    ("H", 3, "CPV", "KSA", "2026-06-27T00:00:00Z"),
    ("H", 3, "URU", "ESP", "2026-06-27T00:00:00Z"),
    # Grupo I: FRA, SEN, IRQ, NOR
    ("I", 1, "FRA", "SEN", "2026-06-16T19:00:00Z"),
    ("I", 1, "IRQ", "NOR", "2026-06-16T22:00:00Z"),
    ("I", 2, "FRA", "IRQ", "2026-06-22T21:00:00Z"),
    ("I", 2, "NOR", "SEN", "2026-06-23T00:00:00Z"),
    ("I", 3, "NOR", "FRA", "2026-06-26T19:00:00Z"),
    ("I", 3, "SEN", "IRQ", "2026-06-26T19:00:00Z"),
    # Grupo J: ARG, ALG, AUT, JOR
    ("J", 1, "ARG", "ALG", "2026-06-17T01:00:00Z"),
    ("J", 1, "AUT", "JOR", "2026-06-17T04:00:00Z"),
    ("J", 2, "ARG", "AUT", "2026-06-22T17:00:00Z"),
    ("J", 2, "JOR", "ALG", "2026-06-23T03:00:00Z"),
    ("J", 3, "ALG", "AUT", "2026-06-28T02:00:00Z"),
    ("J", 3, "JOR", "ARG", "2026-06-28T02:00:00Z"),
    # Grupo K: POR, COD, UZB, COL
    ("K", 1, "POR", "COD", "2026-06-17T17:00:00Z"),
    ("K", 1, "UZB", "COL", "2026-06-18T02:00:00Z"),
    ("K", 2, "POR", "UZB", "2026-06-23T17:00:00Z"),
    ("K", 2, "COL", "COD", "2026-06-24T02:00:00Z"),
    ("K", 3, "COL", "POR", "2026-06-27T23:30:00Z"),
    ("K", 3, "COD", "UZB", "2026-06-27T23:30:00Z"),
    # Grupo L: ENG, CRO, GHA, PAN
    ("L", 1, "ENG", "CRO", "2026-06-17T20:00:00Z"),
    ("L", 1, "GHA", "PAN", "2026-06-17T23:00:00Z"),
    ("L", 2, "ENG", "GHA", "2026-06-23T20:00:00Z"),
    ("L", 2, "PAN", "CRO", "2026-06-23T23:00:00Z"),
    ("L", 3, "PAN", "ENG", "2026-06-27T21:00:00Z"),
    ("L", 3, "CRO", "GHA", "2026-06-27T21:00:00Z"),
]
```

Total: 72 partidos = 12 grupos × 6.

---

## Task 1: Ampliar `fixtures/teams.json` con las 32 selecciones nuevas

**Files:**
- Modify: `fixtures/teams.json`

- [ ] **Step 1.1: Añadir las 32 entradas al final del array**

Editar `fixtures/teams.json`. Manteniendo las 16 existentes, añadir las 32 entradas listadas arriba en *Datos de referencia → Selecciones nuevas*. El archivo final tiene 48 elementos.

- [ ] **Step 1.2: Validar que el JSON parsea**

```bash
python -c "import json; data = json.load(open('fixtures/teams.json')); print(f'{len(data)} equipos'); codes = [t['pk'] for t in data]; assert len(set(codes)) == 48, codes; print('OK')"
```

Salida esperada:
```
48 equipos
OK
```

- [ ] **Step 1.3: Commit**

```bash
git add fixtures/teams.json
git commit -m "data(teams): añadir las 32 selecciones restantes del Mundial 2026"
```

---

## Task 2: Generar `fixtures/world_cup_2026.json` con los 72 partidos

**Files:**
- Modify: `fixtures/world_cup_2026.json`

- [ ] **Step 2.1: Crear el script generador inline**

Ejecutar este snippet en una sola línea con `python -` o `python -c`. Genera el JSON a partir de la tabla `MATCHES` del header del plan y lo guarda en `fixtures/world_cup_2026.json`. (Pegar el listado completo de tuplas dentro del `MATCHES = [...]`.)

```bash
python <<'PY'
import json
MATCHES = [
    # >>> Pegar AQUÍ las 72 tuplas idénticas a las del bloque MATCHES en
    #     "Datos de referencia → Calendario completo" arriba en este plan. <<<
]
assert len(MATCHES) == 72, f"Esperaba 72, tengo {len(MATCHES)}"
groups = {}
for g, md, h, a, k in MATCHES:
    groups.setdefault(g, []).append((md, h, a))
for g, items in groups.items():
    assert len(items) == 6, f"Grupo {g} tiene {len(items)}"
    md_counts = {}
    for md, _, _ in items:
        md_counts[md] = md_counts.get(md, 0) + 1
    assert md_counts == {1: 2, 2: 2, 3: 2}, f"Grupo {g}: {md_counts}"
data = []
for i, (g, md, h, a, k) in enumerate(MATCHES, start=1):
    data.append({
        "model": "competition.match",
        "pk": i,
        "fields": {"round": "groups", "group": g, "matchday": md, "home": h, "away": a, "kickoff": k},
    })
with open("fixtures/world_cup_2026.json", "w", encoding="utf-8") as f:
    json.dump(data, f, ensure_ascii=False, indent=2)
print(f"OK: {len(data)} partidos escritos en fixtures/world_cup_2026.json")
PY
```

Salida esperada: `OK: 72 partidos escritos en fixtures/world_cup_2026.json`.

- [ ] **Step 2.2: Validar el JSON generado**

```bash
python -c "
import json
from collections import Counter
data = json.load(open('fixtures/world_cup_2026.json'))
assert len(data) == 72
groups = Counter(d['fields']['group'] for d in data)
assert set(groups) == set('ABCDEFGHIJKL'), groups
assert all(v == 6 for v in groups.values()), groups
mds = Counter((d['fields']['group'], d['fields']['matchday']) for d in data)
assert all(v == 2 for v in mds.values()), mds
print('OK: 12 grupos x 6 partidos x 3 matchdays')
"
```

Salida esperada: `OK: 12 grupos x 6 partidos x 3 matchdays`.

- [ ] **Step 2.3: Commit**

```bash
git add fixtures/world_cup_2026.json
git commit -m "data(matches): cargar los 72 partidos reales de la fase de grupos"
```

---

## Task 3: Servicio `matchday_gate` (TDD)

**Files:**
- Create: `competition/services/matchday_gate.py`
- Create: `competition/tests/test_matchday_gate.py`

- [ ] **Step 3.1: Escribir tests**

Crear `competition/tests/test_matchday_gate.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from competition.services.matchday_gate import (
    is_matchday_open,
    previous_matchday_close_info,
)
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.mark.django_db
def test_matchday_one_is_always_open():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert is_matchday_open("groups", 1) is True


@pytest.mark.django_db
def test_none_matchday_is_always_open():
    RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    assert is_matchday_open("r16", None) is True


@pytest.mark.django_db
def test_empty_previous_matchday_means_open():
    # Si no hay partidos en la J anterior, no hay nada que cerrar
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert is_matchday_open("groups", 2) is True


@pytest.mark.django_db
def test_matchday_two_blocked_while_md1_pending():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-15 10:00:00", tz_offset=0):
        # MD1 con un partido cuyo kickoff es aún en el futuro
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="AA1"),
            away=TeamFactory(code="AA2"),
            kickoff=timezone.now() + timedelta(hours=5),
        )
        assert is_matchday_open("groups", 2) is False


@pytest.mark.django_db
def test_matchday_two_open_when_all_md1_kicked_off():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-20 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="BB1"),
            away=TeamFactory(code="BB2"),
            kickoff=timezone.now() - timedelta(hours=2),
        )
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="BB3"),
            away=TeamFactory(code="BB4"),
            kickoff=timezone.now() - timedelta(minutes=1),
        )
        assert is_matchday_open("groups", 2) is True


@pytest.mark.django_db
def test_matchday_three_depends_on_md2_only():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-22 10:00:00", tz_offset=0):
        # MD1 completamente jugada en el pasado
        MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="CC1"),
            away=TeamFactory(code="CC2"),
            kickoff=timezone.now() - timedelta(days=5),
        )
        # MD2 con kickoff aún en el futuro
        MatchFactory(
            round=grp,
            matchday=2,
            home=TeamFactory(code="CC3"),
            away=TeamFactory(code="CC4"),
            kickoff=timezone.now() + timedelta(hours=2),
        )
        # MD3 no se abre porque MD2 sigue pendiente
        assert is_matchday_open("groups", 3) is False


@pytest.mark.django_db
def test_previous_matchday_close_info_returns_last_kickoff():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    with freeze_time("2026-06-15 10:00:00", tz_offset=0):
        early = MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="DD1"),
            away=TeamFactory(code="DD2"),
            kickoff=timezone.now() + timedelta(hours=1),
        )
        last = MatchFactory(
            round=grp,
            matchday=1,
            home=TeamFactory(code="DD3"),
            away=TeamFactory(code="DD4"),
            kickoff=timezone.now() + timedelta(hours=8),
        )
        match, kickoff = previous_matchday_close_info("groups", 2)
        assert match.id == last.id
        assert kickoff == last.kickoff


@pytest.mark.django_db
def test_previous_matchday_close_info_none_when_no_prev():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert previous_matchday_close_info("groups", 1) == (None, None)
    # También cuando la jornada N-1 está vacía
    assert previous_matchday_close_info("groups", 2) == (None, None)
```

- [ ] **Step 3.2: Ejecutar tests para confirmar que fallan**

```bash
pytest competition/tests/test_matchday_gate.py -x
```

Esperado: ImportError o ModuleNotFoundError para `competition.services.matchday_gate`.

- [ ] **Step 3.3: Implementar el servicio**

Crear `competition/services/matchday_gate.py`:

```python
"""Puerta de jornada: abre J{N} cuando todos los partidos de J{N-1} alcanzaron su kickoff."""

from datetime import datetime

from django.utils import timezone

from competition.models import Match


def is_matchday_open(round_id: str, matchday: int | None) -> bool:
    if matchday is None or matchday <= 1:
        return True
    prev_kickoffs = list(
        Match.objects.filter(round_id=round_id, matchday=matchday - 1).values_list(
            "kickoff", flat=True
        )
    )
    if not prev_kickoffs:
        return True
    now = timezone.now()
    return all(now >= k for k in prev_kickoffs)


def previous_matchday_close_info(
    round_id: str, matchday: int | None
) -> tuple[Match | None, datetime | None]:
    """Devuelve el último partido de la jornada anterior (por kickoff) y su kickoff."""
    if matchday is None or matchday <= 1:
        return None, None
    last = (
        Match.objects.filter(round_id=round_id, matchday=matchday - 1)
        .select_related("home", "away")
        .order_by("-kickoff")
        .first()
    )
    if last is None:
        return None, None
    return last, last.kickoff
```

- [ ] **Step 3.4: Ejecutar tests y verificar que pasan**

```bash
pytest competition/tests/test_matchday_gate.py -x
```

Esperado: 8 passed.

- [ ] **Step 3.5: Commit**

```bash
git add competition/services/matchday_gate.py competition/tests/test_matchday_gate.py
git commit -m "feat(competition): servicio matchday_gate para apertura progresiva de jornadas"
```

---

## Task 4: Propiedad `Match.predictions_open` (TDD)

**Files:**
- Modify: `competition/models.py`
- Modify: `competition/tests/test_match.py`

- [ ] **Step 4.1: Añadir tests a `competition/tests/test_match.py`**

Añadir al final del archivo:

```python


@pytest.fixture
def setup_two_md(db):
    grp = Round.objects.create(id="groups", label="Grupos", short="GRP", points=3, order=1)
    a = Team.objects.create(code="T1A", name="A1", flag="🏳️")
    b = Team.objects.create(code="T1B", name="B1", flag="🏳️")
    c = Team.objects.create(code="T2A", name="A2", flag="🏳️")
    d = Team.objects.create(code="T2B", name="B2", flag="🏳️")
    return grp, (a, b), (c, d)


@pytest.mark.django_db
def test_predictions_open_md1_when_editable(setup_two_md):
    grp, (a, b), _ = setup_two_md
    with freeze_time("2026-06-10 10:00:00", tz_offset=0):
        m = Match.objects.create(
            round=grp, group="A", matchday=1, home=a, away=b,
            kickoff=timezone.now() + timedelta(days=1),
        )
        assert m.editable is True
        assert m.predictions_open is True


@pytest.mark.django_db
def test_predictions_open_md2_blocked_by_gate(setup_two_md):
    grp, (a, b), (c, d) = setup_two_md
    with freeze_time("2026-06-10 10:00:00", tz_offset=0):
        # MD1 con kickoff todavía en el futuro
        Match.objects.create(
            round=grp, group="A", matchday=1, home=a, away=b,
            kickoff=timezone.now() + timedelta(hours=10),
        )
        m2 = Match.objects.create(
            round=grp, group="A", matchday=2, home=c, away=d,
            kickoff=timezone.now() + timedelta(days=8),
        )
        assert m2.editable is True
        assert m2.predictions_open is False  # bloqueado por gate


@pytest.mark.django_db
def test_predictions_open_false_when_not_editable(setup_two_md):
    grp, (a, b), _ = setup_two_md
    with freeze_time("2026-06-10 10:00:00", tz_offset=0):
        # Partido en directo: no editable
        m = Match.objects.create(
            round=grp, group="A", matchday=1, home=a, away=b,
            kickoff=timezone.now() - timedelta(minutes=10),
        )
        assert m.editable is False
        assert m.predictions_open is False
```

- [ ] **Step 4.2: Ejecutar tests para confirmar que fallan**

```bash
pytest competition/tests/test_match.py -x
```

Esperado: AttributeError sobre `predictions_open`.

- [ ] **Step 4.3: Añadir la propiedad al modelo**

En `competition/models.py`, dentro de `class Match`, debajo de la propiedad `editable`:

```python
    @property
    def predictions_open(self) -> bool:
        """True solo si el partido es editable Y su jornada está desbloqueada."""
        if not self.editable:
            return False
        from competition.services.matchday_gate import is_matchday_open

        return is_matchday_open(self.round_id, self.matchday)
```

(Import dentro de la propiedad para evitar ciclo entre `models.py` y `services/matchday_gate.py`, que a su vez importa `Match`.)

- [ ] **Step 4.4: Ejecutar tests y verificar que pasan**

```bash
pytest competition/tests/test_match.py -x
```

Esperado: todos los tests previos + 3 nuevos passed.

- [ ] **Step 4.5: Commit**

```bash
git add competition/models.py competition/tests/test_match.py
git commit -m "feat(competition): Match.predictions_open combina editable con puerta de jornada"
```

---

## Task 5: Bloquear `PredictView` por jornada cerrada

**Files:**
- Modify: `competition/views.py`
- Modify: `competition/tests/test_prediction.py`

- [ ] **Step 5.1: Añadir test de bloqueo por jornada al final de `competition/tests/test_prediction.py`**

```python


@pytest.mark.django_db
def test_predict_post_rejected_when_matchday_locked(client, setup):
    from datetime import timedelta
    from django.urls import reverse
    from django.utils import timezone
    from freezegun import freeze_time

    from competition.tests.factories import MatchFactory, TeamFactory

    u, m = setup  # m está en jornada 1
    client.force_login(u)
    # Construimos un partido de J2 con jornada anterior pendiente
    with freeze_time("2026-06-09 10:00:00", tz_offset=0):
        m.kickoff = timezone.now() + timedelta(days=2)  # J1 todavía en el futuro
        m.save()
        m2 = MatchFactory(
            round=m.round,
            group="A",
            matchday=2,
            home=TeamFactory(code="X1"),
            away=TeamFactory(code="X2"),
            kickoff=timezone.now() + timedelta(days=10),
        )
        r = client.post(reverse("competicion:predict", args=[m2.id]), {"home": 1, "away": 0})
        assert r.status_code == 403
        assert not m2.predictions.filter(player=u).exists()
```

- [ ] **Step 5.2: Ejecutar tests para confirmar que fallan**

```bash
pytest competition/tests/test_prediction.py::test_predict_post_rejected_when_matchday_locked -x
```

Esperado: AssertionError (devuelve 302 porque la vista no chequea la puerta).

- [ ] **Step 5.3: Actualizar `PredictView` en `competition/views.py`**

Reemplazar la clase `PredictView` completa por:

```python
class PredictView(LoginRequiredMixin, View):
    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not request.user.is_jugador:
            raise PermissionDenied("Solo los jugadores pueden pronosticar.")
        if not m.editable:
            messages.error(request, "Las apuestas para este partido están cerradas.")
            return redirect("competicion:dashboard")
        from competition.services.matchday_gate import is_matchday_open

        if not is_matchday_open(m.round_id, m.matchday):
            messages.error(
                request,
                f"La J{m.matchday} se desbloqueará cuando termine la J{m.matchday - 1}.",
            )
            return redirect("competicion:dashboard")
        pred = Prediction.objects.filter(player=request.user, match=m).first()
        return render(request, "competition/_predict_modal.html", {"match": m, "pred": pred})

    def post(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not request.user.is_jugador:
            raise PermissionDenied("Solo los jugadores pueden pronosticar.")
        if not m.predictions_open:
            raise PermissionDenied("Apuestas cerradas o jornada bloqueada.")
        try:
            h = max(0, int(request.POST.get("home", 0)))
            a = max(0, int(request.POST.get("away", 0)))
        except ValueError:
            messages.error(request, "Marcador inválido.")
            return redirect("competicion:dashboard")
        Prediction.objects.update_or_create(
            player=request.user, match=m, defaults={"home": h, "away": a}
        )
        messages.success(request, f"Pronóstico guardado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect("competicion:dashboard")
```

- [ ] **Step 5.4: Ejecutar tests y verificar que pasan**

```bash
pytest competition/tests/test_prediction.py competition/tests/test_competition_view.py -x
```

Esperado: todos passed (los previos siguen pasando, el nuevo pasa).

- [ ] **Step 5.5: Commit**

```bash
git add competition/views.py competition/tests/test_prediction.py
git commit -m "feat(competition): PredictView bloquea pronósticos de jornadas no desbloqueadas"
```

---

## Task 6: Sub-selector de jornada en `CompetitionView`

**Files:**
- Modify: `competition/views.py`
- Modify: `competition/tests/test_competition_view.py`

- [ ] **Step 6.1: Añadir tests al final de `competition/tests/test_competition_view.py`**

```python


@pytest.mark.django_db
def test_dashboard_shows_matchday_subselector_for_groups(client):
    from datetime import timedelta
    from django.utils import timezone

    from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    for md in (1, 2, 3):
        MatchFactory(
            round=grp,
            matchday=md,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=timezone.now() + timedelta(days=md),
        )
    r = client.get(reverse("competicion:dashboard") + "?round=groups")
    body = r.content.decode()
    assert "J1" in body
    assert "J2" in body
    assert "J3" in body


@pytest.mark.django_db
def test_dashboard_filters_by_matchday(client):
    from datetime import timedelta
    from django.utils import timezone

    from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    j1_home = TeamFactory(code="J1H", name="J1HomeTeam")
    j2_home = TeamFactory(code="J2H", name="J2HomeTeam")
    MatchFactory(
        round=grp, matchday=1, home=j1_home, away=TeamFactory(),
        kickoff=timezone.now() + timedelta(days=1),
    )
    MatchFactory(
        round=grp, matchday=2, home=j2_home, away=TeamFactory(),
        kickoff=timezone.now() + timedelta(days=8),
    )
    r = client.get(reverse("competicion:dashboard") + "?round=groups&matchday=1")
    body = r.content.decode()
    assert "J1HomeTeam" in body
    assert "J2HomeTeam" not in body


@pytest.mark.django_db
def test_dashboard_shows_locked_banner_for_blocked_matchday(client):
    from datetime import timedelta
    from django.utils import timezone
    from freezegun import freeze_time

    from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory

    u = UserFactory(must_change_password=False)
    client.force_login(u)
    grp = RoundFactory(id="groups", points=3, label="Grupos", short="G", order=1)
    with freeze_time("2026-06-09 10:00:00", tz_offset=0):
        MatchFactory(
            round=grp, matchday=1, home=TeamFactory(), away=TeamFactory(),
            kickoff=timezone.now() + timedelta(days=2),
        )
        MatchFactory(
            round=grp, matchday=2, home=TeamFactory(), away=TeamFactory(),
            kickoff=timezone.now() + timedelta(days=9),
        )
        r = client.get(reverse("competicion:dashboard") + "?round=groups&matchday=2")
        body = r.content.decode()
        assert "bloqueada" in body.lower() or "se desbloquea" in body.lower()
```

- [ ] **Step 6.2: Ejecutar tests para confirmar que fallan**

```bash
pytest competition/tests/test_competition_view.py -x -k matchday
```

Esperado: fallan los 3.

- [ ] **Step 6.3: Actualizar `CompetitionView.get` en `competition/views.py`**

Reemplazar la clase `CompetitionView` completa por:

```python
class CompetitionView(LoginRequiredMixin, View):
    def get(self, request):
        from competition.services.matchday_gate import (
            is_matchday_open,
            previous_matchday_close_info,
        )

        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")

        # Detectar si la ronda activa usa jornadas
        matchdays = sorted(
            Match.objects.filter(round_id=active_id, matchday__isnull=False)
            .values_list("matchday", flat=True)
            .distinct()
        )
        active_md = None
        if matchdays:
            requested = request.GET.get("matchday")
            if requested and requested.isdigit() and int(requested) in matchdays:
                active_md = int(requested)
            else:
                active_md = _default_matchday(active_id, matchdays)

        match_qs = Match.objects.filter(round_id=active_id).select_related(
            "home", "away", "round"
        )
        if active_md is not None:
            match_qs = match_qs.filter(matchday=active_md)
        matches = list(match_qs.order_by("kickoff"))

        my_preds = {
            p.match_id: p
            for p in Prediction.objects.filter(player=request.user, match__in=matches)
        }
        open_matches, live_matches, done_matches = [], [], []
        for m in matches:
            m.my_pred = my_preds.get(m.id)
            st = m.status
            if st == "live":
                live_matches.append(m)
            elif st == "done":
                done_matches.append(m)
            else:
                open_matches.append(m)

        matchday_state = []
        locked = False
        locked_last_match = None
        locked_last_kickoff = None
        if active_md is not None:
            for md in matchdays:
                matchday_state.append(
                    {"matchday": md, "open": is_matchday_open(active_id, md), "active": md == active_md}
                )
            locked = not is_matchday_open(active_id, active_md)
            if locked:
                locked_last_match, locked_last_kickoff = previous_matchday_close_info(
                    active_id, active_md
                )

        return render(
            request,
            "competition/dashboard.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "matchdays": matchdays,
                "active_matchday": active_md,
                "matchday_state": matchday_state,
                "locked": locked,
                "locked_last_match": locked_last_match,
                "locked_last_kickoff": locked_last_kickoff,
                "open_matches": open_matches,
                "live_matches": live_matches,
                "done_matches": done_matches,
                "standings": standings()[:50],
            },
        )


def _default_matchday(round_id: str, matchdays: list[int]) -> int:
    """Jornada por defecto: la primera con algún partido activo (no done); si no, la última."""
    if not matchdays:
        return 1
    for md in matchdays:
        any_active = (
            Match.objects.filter(round_id=round_id, matchday=md)
            .filter(result_home__isnull=True)
            .exists()
        )
        if any_active:
            return md
    return matchdays[-1]
```

- [ ] **Step 6.4: Ejecutar tests del view**

```bash
pytest competition/tests/test_competition_view.py -x
```

Esperado: todos passed. Si el test `test_dashboard_shows_locked_banner_for_blocked_matchday` falla todavía es por el template; lo abordamos en la siguiente tarea.

- [ ] **Step 6.5: Commit**

```bash
git add competition/views.py competition/tests/test_competition_view.py
git commit -m "feat(competition): sub-selector de jornada y default en CompetitionView"
```

---

## Task 7: Template `_matchday_selector.html` + banner + tarjetas atenuadas

**Files:**
- Create: `templates/partials/_matchday_selector.html`
- Modify: `templates/competition/dashboard.html`
- Modify: `templates/competition/_match_card.html`

- [ ] **Step 7.1: Crear el sub-selector**

Crear `templates/partials/_matchday_selector.html`:

```html
{% if matchdays %}
<nav class="glass" style="display:flex;gap:6px;padding:8px;border-radius:14px;margin-top:10px" aria-label="Jornadas">
  {% for s in matchday_state %}
  <a href="?round={{ active_round }}&matchday={{ s.matchday }}"
     class="chip {% if s.active %}chip-open{% endif %}"
     style="text-decoration:none;{% if not s.open %}opacity:.55{% endif %}"
     {% if not s.open %}aria-disabled="true" title="Jornada bloqueada"{% endif %}>
    {% if not s.open %}🔒 {% endif %}J{{ s.matchday }}
  </a>
  {% endfor %}
</nav>
{% endif %}
```

- [ ] **Step 7.2: Actualizar `templates/competition/dashboard.html`**

Reemplazar el contenido completo por:

```html
{% extends "base.html" %}
{% block main %}
<div style="display:grid;grid-template-columns:1fr 380px;gap:24px">
  <section>
    {% include "partials/_round_selector.html" with rounds=rounds active=active_round %}
    {% include "partials/_matchday_selector.html" %}

    {% if locked %}
    <div class="glass" style="padding:14px 16px;margin-top:14px;border-radius:14px;border:1px dashed var(--accent)">
      <strong>🔒 Jornada J{{ active_matchday }} bloqueada</strong>
      {% if locked_last_match and locked_last_kickoff %}
      <p style="margin:4px 0 0;color:var(--text-dim);font-size:13px">
        Se desbloqueará cuando termine la J{{ active_matchday|add:"-1" }}
        (último partido: <strong>{{ locked_last_match.home.name }} vs {{ locked_last_match.away.name }}</strong>
        el <span class="mono">{{ locked_last_kickoff|date:"D j M · H:i" }}</span>).
      </p>
      {% else %}
      <p style="margin:4px 0 0;color:var(--text-dim);font-size:13px">
        Se desbloqueará cuando termine la J{{ active_matchday|add:"-1" }}.
      </p>
      {% endif %}
    </div>
    {% endif %}

    {% if open_matches %}
    <h2 class="eyebrow" style="margin-top:24px">ABIERTOS · {{ open_matches|length }}</h2>
    <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px{% if locked %};opacity:.55;pointer-events:none{% endif %}">
      {% for m in open_matches %}{% include "competition/_match_card.html" with match=m my_preds=my_preds locked=locked %}{% endfor %}
    </div>
    {% endif %}
    {% if live_matches %}
    <h2 class="eyebrow" style="margin-top:24px">EN JUEGO · {{ live_matches|length }}</h2>
    <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
      {% for m in live_matches %}{% include "competition/_match_card.html" with match=m my_preds=my_preds locked=locked %}{% endfor %}
    </div>
    {% endif %}
    {% if done_matches %}
    <h2 class="eyebrow" style="margin-top:24px">FINALIZADOS · {{ done_matches|length }}</h2>
    <div class="stagger" style="display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:14px">
      {% for m in done_matches %}{% include "competition/_match_card.html" with match=m my_preds=my_preds locked=locked %}{% endfor %}
    </div>
    {% endif %}
    {% if not open_matches and not live_matches and not done_matches %}
    <p class="glass" style="padding:18px;margin-top:18px">No hay partidos en esta ronda todavía.</p>
    {% endif %}
  </section>
  <aside>{% include "partials/_leaderboard.html" with rows=standings me=request.user %}</aside>
</div>
{% endblock %}
```

- [ ] **Step 7.3: Actualizar `templates/competition/_match_card.html` para reflejar el bloqueo**

Modificar el bloque `{% if match.editable %}` al principio del `<a>` por:

```django
{% load icons %}
{% with st=match.status %}
{% if match.predictions_open %}
<a href="{% url 'competicion:predict' match.id %}" data-modal-url="{% url 'competicion:predict' match.id %}" class="match-card glass rise{% if st == 'closing' %} match-card-closing{% endif %}">
{% elif match.editable %}
<a class="match-card glass rise" style="cursor:not-allowed">
{% else %}
<a href="{% url 'competicion:detail' match.id %}" data-modal-url="{% url 'competicion:detail' match.id %}" class="match-card glass rise{% if st == 'live' %} match-card-live{% endif %}">
{% endif %}
```

Y en el bloque `match-card-foot`, reemplazar la rama final `{% elif match.editable %}` por:

```django
    {% elif match.predictions_open %}
      <span class="chip chip-accent">
        {% icon "edit" width=11 height=11 %} Pronosticar
      </span>
    {% elif match.editable %}
      <span class="chip" style="opacity:.7">
        🔒 Jornada bloqueada
      </span>
    {% endif %}
```

(El resto del archivo se mantiene igual.)

- [ ] **Step 7.4: Ejecutar todos los tests**

```bash
pytest competition/tests/ -x
```

Esperado: todos passed (incluido `test_dashboard_shows_locked_banner_for_blocked_matchday`).

- [ ] **Step 7.5: Commit**

```bash
git add templates/partials/_matchday_selector.html templates/competition/dashboard.html templates/competition/_match_card.html
git commit -m "feat(ui): sub-selector de jornada, banner de bloqueo y chip 🔒 en tarjetas"
```

---

## Task 8: Sub-selector de jornada en `ManageResultsView` (sin gating)

**Files:**
- Modify: `competition/views.py`
- Modify: `templates/competition/manage_results.html`

- [ ] **Step 8.1: Actualizar `ManageResultsView.get` en `competition/views.py`**

Reemplazar la clase `ManageResultsView` completa por:

```python
class ManageResultsView(GestorRequiredMixin, View):
    def get(self, request):
        rounds = list(Round.objects.all())
        active_id = request.GET.get("round", rounds[0].id if rounds else "groups")
        matchdays = sorted(
            Match.objects.filter(round_id=active_id, matchday__isnull=False)
            .values_list("matchday", flat=True)
            .distinct()
        )
        active_md = None
        if matchdays:
            requested = request.GET.get("matchday")
            if requested and requested.isdigit() and int(requested) in matchdays:
                active_md = int(requested)
            else:
                active_md = _default_matchday(active_id, matchdays)

        match_qs = Match.objects.filter(round_id=active_id).select_related(
            "home", "away", "round"
        )
        if active_md is not None:
            match_qs = match_qs.filter(matchday=active_md)
        ms = list(match_qs.order_by("kickoff"))

        # Estado puramente informativo en esta vista; el gestor no está bloqueado
        matchday_state = [
            {"matchday": md, "open": True, "active": md == active_md} for md in matchdays
        ]

        pending, upcoming, done = [], [], []
        for m in ms:
            st = m.status
            if st == "done":
                done.append(m)
            elif st in ("live", "closed"):
                pending.append(m)
            else:
                upcoming.append(m)
        return render(
            request,
            "competition/manage_results.html",
            {
                "rounds": rounds,
                "active_round": active_id,
                "matchdays": matchdays,
                "active_matchday": active_md,
                "matchday_state": matchday_state,
                "pending": pending,
                "upcoming": upcoming,
                "done": done,
            },
        )
```

- [ ] **Step 8.2: Actualizar `templates/competition/manage_results.html`**

Después de la línea con `{% include "partials/_round_selector.html" ... %}`, añadir:

```django
{% include "partials/_matchday_selector.html" %}
```

- [ ] **Step 8.3: Ejecutar tests**

```bash
pytest competition/tests/test_competition_view.py -x
```

Esperado: todos passed.

- [ ] **Step 8.4: Commit**

```bash
git add competition/views.py templates/competition/manage_results.html
git commit -m "feat(competition): sub-selector de jornada en panel de Resultados (sin gating)"
```

---

## Task 9: Management command `seed_world_cup_2026` (TDD)

**Files:**
- Create: `competition/management/__init__.py`
- Create: `competition/management/commands/__init__.py`
- Create: `competition/management/commands/seed_world_cup_2026.py`
- Create: `competition/tests/test_seed_command.py`

- [ ] **Step 9.1: Crear los `__init__.py` vacíos**

```bash
touch competition/management/__init__.py competition/management/commands/__init__.py
```

- [ ] **Step 9.2: Escribir tests del comando**

Crear `competition/tests/test_seed_command.py`:

```python
import json

import pytest
from django.core.management import call_command

from competition.models import Match, Prediction, Round, Team
from competition.tests.factories import MatchFactory, RoundFactory, TeamFactory


@pytest.fixture(autouse=True)
def _rounds(db):
    """El comando exige que la ronda 'groups' exista."""
    RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.mark.django_db
def test_seed_creates_48_teams_and_72_matches():
    call_command("seed_world_cup_2026")
    assert Team.objects.count() == 48
    assert Match.objects.filter(round_id="groups").count() == 72
    # 24 por jornada
    for md in (1, 2, 3):
        assert Match.objects.filter(round_id="groups", matchday=md).count() == 24


@pytest.mark.django_db
def test_seed_is_idempotent():
    call_command("seed_world_cup_2026")
    Match.objects.count()
    call_command("seed_world_cup_2026")
    assert Team.objects.count() == 48
    assert Match.objects.filter(round_id="groups").count() == 72


@pytest.mark.django_db
def test_seed_preserves_existing_predictions(django_user_model):
    user = django_user_model.objects.create_user(
        email="a@edisa.com", password="x", name="Ana", is_jugador=True
    )
    call_command("seed_world_cup_2026")
    match = Match.objects.filter(round_id="groups", matchday=1).first()
    Prediction.objects.create(player=user, match=match, home=2, away=1)
    # Re-ejecutar: no se borra
    call_command("seed_world_cup_2026")
    assert Prediction.objects.filter(player=user, match=match).count() == 1


@pytest.mark.django_db
def test_seed_prune_deletes_orphans():
    # Partido huérfano: con códigos que no existen en el calendario real
    foreign_a = TeamFactory(code="ZZA", name="Aliens", flag="🛸")
    foreign_b = TeamFactory(code="ZZB", name="Bots", flag="🤖")
    grp = Round.objects.get(id="groups")
    MatchFactory(round=grp, group="Z", matchday=1, home=foreign_a, away=foreign_b)
    call_command("seed_world_cup_2026", "--prune")
    assert not Match.objects.filter(group="Z").exists()
    # Pero los reales sí quedan
    assert Match.objects.filter(round_id="groups").count() == 72


@pytest.mark.django_db
def test_seed_keeps_orphans_without_prune():
    foreign_a = TeamFactory(code="ZZA", name="Aliens", flag="🛸")
    foreign_b = TeamFactory(code="ZZB", name="Bots", flag="🤖")
    grp = Round.objects.get(id="groups")
    MatchFactory(round=grp, group="Z", matchday=1, home=foreign_a, away=foreign_b)
    call_command("seed_world_cup_2026")
    assert Match.objects.filter(group="Z").exists()
```

- [ ] **Step 9.3: Ejecutar tests para confirmar que fallan**

```bash
pytest competition/tests/test_seed_command.py -x
```

Esperado: `CommandError: Unknown command 'seed_world_cup_2026'`.

- [ ] **Step 9.4: Implementar el comando**

Crear `competition/management/commands/seed_world_cup_2026.py`:

```python
"""Carga el calendario del Mundial 2026: 48 selecciones + 72 partidos de fase de grupos.

Idempotente. Clave funcional de un partido: (round, group, matchday, home, away).
Las selecciones se identifican por su `code`. Con --prune borra partidos en `groups`
que no estén en el calendario canónico (junto a sus pronósticos).
"""

import json
from datetime import datetime
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.utils import timezone

from competition.models import Match, Round, Team

FIXTURES_DIR = Path(__file__).resolve().parents[3] / "fixtures"


class Command(BaseCommand):
    help = "Carga el calendario del Mundial 2026 (48 equipos + 72 partidos de grupos)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--prune",
            action="store_true",
            help="Borra partidos de 'groups' que no estén en el calendario canónico.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Muestra qué haría sin tocar la BD.",
        )

    @transaction.atomic
    def handle(self, *, prune: bool, dry_run: bool, **opts):
        if not Round.objects.filter(id="groups").exists():
            raise CommandError(
                "Falta la ronda 'groups'. Carga primero fixtures/rounds.json: "
                "python manage.py loaddata fixtures/rounds.json"
            )

        teams = _load_json("teams.json")
        matches = _load_json("world_cup_2026.json")

        created_t, updated_t = 0, 0
        for entry in teams:
            code = entry["pk"]
            fields = entry["fields"]
            obj, created = Team.objects.update_or_create(
                code=code, defaults={"name": fields["name"], "flag": fields["flag"]}
            )
            if created:
                created_t += 1
            else:
                updated_t += 1

        created_m, updated_m, unchanged_m = 0, 0, 0
        canonical_keys = set()
        for entry in matches:
            f = entry["fields"]
            key = (f["round"], f["group"], f["matchday"], f["home"], f["away"])
            canonical_keys.add(key)
            kickoff = _parse_dt(f["kickoff"])
            obj, created = Match.objects.update_or_create(
                round_id=f["round"],
                group=f["group"],
                matchday=f["matchday"],
                home_id=f["home"],
                away_id=f["away"],
                defaults={"kickoff": kickoff},
            )
            if created:
                created_m += 1
            elif obj.kickoff != kickoff:
                # update_or_create ya guardó; sólo contar como actualizado
                updated_m += 1
            else:
                unchanged_m += 1

        orphans = []
        for m in Match.objects.filter(round_id="groups").select_related("home", "away"):
            key = (m.round_id, m.group, m.matchday, m.home_id, m.away_id)
            if key not in canonical_keys:
                orphans.append(m)

        pruned = 0
        if orphans:
            if prune:
                for o in orphans:
                    o.delete()
                    pruned += 1
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"{len(orphans)} partido(s) huérfano(s) en 'groups' (no en fixture). "
                        "Ejecuta con --prune para borrarlos."
                    )
                )

        if dry_run:
            transaction.set_rollback(True)
            self.stdout.write(self.style.NOTICE("DRY RUN — sin cambios persistidos"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Equipos: +{created_t} creados, ~{updated_t} actualizados (total {Team.objects.count()}).\n"
                f"Partidos: +{created_m} creados, ~{updated_m} actualizados, ={unchanged_m} sin cambios "
                f"(total {Match.objects.filter(round_id='groups').count()}).\n"
                f"Huérfanos: {len(orphans)} ({'borrados' if prune else 'intactos'}, pruned={pruned})."
            )
        )


def _load_json(filename: str):
    path = FIXTURES_DIR / filename
    if not path.exists():
        raise CommandError(f"No existe el fixture: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


def _parse_dt(value: str) -> datetime:
    # Acepta "2026-06-11T19:00:00Z"
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    dt = datetime.fromisoformat(value)
    if timezone.is_naive(dt):
        dt = timezone.make_aware(dt, timezone.utc)
    return dt
```

- [ ] **Step 9.5: Ejecutar tests del comando**

```bash
pytest competition/tests/test_seed_command.py -x
```

Esperado: 5 passed.

- [ ] **Step 9.6: Commit**

```bash
git add competition/management/__init__.py competition/management/commands/__init__.py competition/management/commands/seed_world_cup_2026.py competition/tests/test_seed_command.py
git commit -m "feat(competition): comando seed_world_cup_2026 idempotente con --prune"
```

---

## Task 10: Cargar el calendario en la BD de desarrollo

**Files:**
- Modify: `db.sqlite3` (en ejecución, no se versiona)

- [ ] **Step 10.1: Backup del SQLite actual**

```bash
cp db.sqlite3 db.sqlite3.bak
```

- [ ] **Step 10.2: Ejecutar el seed con --prune**

```bash
python manage.py seed_world_cup_2026 --prune
```

Salida esperada (ejemplo):
```
Equipos: +32 creados, ~16 actualizados (total 48).
Partidos: +72 creados, ~0 actualizados, =0 sin cambios (total 72).
Huérfanos: 4 (borrados, pruned=4).
```

- [ ] **Step 10.3: Verificar contenido**

```bash
python manage.py shell -c "
from competition.models import Team, Match
print('Teams:', Team.objects.count())
print('Matches:', Match.objects.count())
print('Matches per matchday:')
for md in (1, 2, 3):
    print(f'  J{md}: {Match.objects.filter(round_id=\"groups\", matchday=md).count()}')
print('Groups:', sorted(set(Match.objects.values_list(\"group\", flat=True))))
"
```

Salida esperada:
```
Teams: 48
Matches: 72
Matches per matchday:
  J1: 24
  J2: 24
  J3: 24
Groups: ['A', 'B', 'C', 'D', 'E', 'F', 'G', 'H', 'I', 'J', 'K', 'L']
```

- [ ] **Step 10.4: Confirmar visualmente en la UI (opcional)**

Si tienes el servidor en marcha:
```bash
python manage.py runserver
```
Abrir `http://localhost:8000/competicion/`. Comprobar:
- Sub-selector `J1 · J2 · J3` visible.
- J1 abierta (24 partidos). J2 y J3 atenuadas con banner.
- Al intentar entrar en un partido de J2 desde la URL: redirección al dashboard con mensaje "se desbloqueará...".

(No se versiona el `db.sqlite3`; este paso es local.)

---

## Task 11: Verificación final y lint

**Files:**
- N/A

- [ ] **Step 11.1: Suite de tests completa**

```bash
pytest -x
```

Esperado: todos passed. Si falla algo no relacionado, anotar y proseguir; si falla algo de competición, volver atrás.

- [ ] **Step 11.2: Lint**

```bash
ruff check . && ruff format --check .
```

Esperado: sin errores. Si hay autoformat pendiente: `ruff format .` y commit del format.

- [ ] **Step 11.3: Smoke test final con freezegun**

```bash
pytest competition/tests/test_matchday_gate.py competition/tests/test_prediction.py competition/tests/test_seed_command.py -v
```

Esperado: tests del gate, del POST bloqueado por jornada y del seed todos passed.

- [ ] **Step 11.4: Commit de tareas pendientes (si las hay)**

```bash
git status
```

Si todo limpio, este plan se cierra.

---

## Criterios de aceptación (del spec §9)

- [x] `python manage.py seed_world_cup_2026 --prune` deja la BD con 48 selecciones y 72 partidos (24+24+24).
- [x] Jugador en Competición ve sub-selector J1·J2·J3 solo en `groups`; J1 abierta, J2/J3 atenuadas con banner.
- [x] POST a `/competicion/pronosticar/<match_id>/` para J2 con J1 pendiente: 403.
- [x] Bajo freezegun avanzando el reloj tras el último kickoff de J1, J2 abre y acepta pronósticos.
- [x] Tests previos pasan + nuevos tests del gate, vista, seed y POST bloqueado.
- [x] Pantalla de gestor (Resultados) muestra sub-selector pero no bloquea.

---

## Notas para el ejecutor

- **El proyecto NO usa migraciones nuevas** para esta funcionalidad: el campo `Match.matchday` ya existe y la nueva propiedad `Match.predictions_open` no toca el esquema.
- **El import lazy** de `is_matchday_open` dentro de `Match.predictions_open` es deliberado: evita un ciclo `models → services/matchday_gate → models`.
- Si en el `seed` necesitas borrar `db.sqlite3` para empezar desde cero: `rm db.sqlite3 && python manage.py migrate && python manage.py loaddata fixtures/rounds.json && python manage.py createsuperuser` antes de `seed_world_cup_2026 --prune`.
- **Cuidado con la edición de `_match_card.html`**: el archivo es delicado, asegúrate de no romper los chips de estado existentes ni la renderización de marcador final.
