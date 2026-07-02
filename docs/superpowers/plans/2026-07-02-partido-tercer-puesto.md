# Partido por el 3.er y 4.º puesto — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir el partido por el 3.er/4.º puesto del Mundial 2026, que se muestra en la columna de la Final, vale lo mismo que la Final y computa para la clasificación general y para la jornada "Fases Finales".

**Architecture:** El partido cuelga de la ronda `final` (no se crea ronda nueva). Como `final` ya está en todas las listas de ámbito (`KO_ROUND_IDS`, `FINALS_ROUND_IDS`, `_FINALS_ROUND_IDS`, `stats`, `resolve`), el resultado computa donde debe sin tocar esa lógica y los puntos son una única fuente de verdad. El grueso del cambio es dato en el fixture; el único código Python es un patrón nuevo en `slot_label` para "Perdedor MNN".

**Tech Stack:** Django, pytest / pytest-django, factory_boy, fixtures JSON, comando de management `seed_world_cup_2026`.

## Global Constraints

- Interfaz y textos en **español de España** (copia literal del prototipo).
- El partido debe valer **lo mismo que la Final**: mismo `Round.points` (ronda `final`), sin duplicar el valor.
- El seed `seed_world_cup_2026` es **idempotente por `bracket_code`** y **no poda KO**.
- Los equipos KO se asignan **a mano** (no hay auto-asignación).
- Codificación de ficheros: preservar la existente. `world_cup_2026.json` es UTF-8 (contiene banderas emoji y `º`); mantenerlo UTF-8, sin BOM.

---

### Task 1: Etiqueta de slot "Perdedor MNN"

**Files:**
- Modify: `competition/templatetags/competition_extras.py`
- Test: `competition/tests/test_slot_label_filter.py`

**Interfaces:**
- Produces: `slot_label("LM101") == "Perdedor M101"` (filtro de plantilla ya existente, se amplía).

- [ ] **Step 1: Añadir los casos que fallan al parametrize del test**

En `competition/tests/test_slot_label_filter.py`, añadir estas dos filas a la lista de `@pytest.mark.parametrize`:

```python
        ("LM101", "Perdedor M101"),
        ("LM102", "Perdedor M102"),
```

- [ ] **Step 2: Ejecutar el test y ver que falla**

Run: `python -m pytest competition/tests/test_slot_label_filter.py -q`
Expected: FAIL — `LM101` devuelve "Por definir" en lugar de "Perdedor M101".

- [ ] **Step 3: Implementar el patrón de perdedor**

En `competition/templatetags/competition_extras.py`, junto a los otros regex (tras `WINNER_RE`):

```python
LOSER_RE = re.compile(r"^L(M\d+)$")
```

Y dentro de `slot_label`, tras la rama de `WINNER_RE` y antes de `THIRD_RE`:

```python
    if m := LOSER_RE.match(code):
        return f"Perdedor {m.group(1)}"
```

- [ ] **Step 4: Ejecutar el test y ver que pasa**

Run: `python -m pytest competition/tests/test_slot_label_filter.py -q`
Expected: PASS (todas las filas, incluidas `LM101`/`LM102`).

- [ ] **Step 5: Commit**

```bash
git add competition/templatetags/competition_extras.py competition/tests/test_slot_label_filter.py
git commit -m "feat(ko): slot_label reconoce perdedores de semifinal (Perdedor MNN)"
```

---

### Task 2: Partido M104 en el fixture + seed

**Files:**
- Modify: `fixtures/world_cup_2026.json` (tras el objeto `pk: 103`, el último del array)
- Modify: `competition/management/commands/seed_world_cup_2026.py` (docstring línea 1 y `help` línea ~25)
- Test: `competition/tests/test_seed_command.py`

**Interfaces:**
- Consumes: `slot_label` de la Task 1 (para el render legible; no se usa en este test).
- Produces: un `Match` con `bracket_code="M104"`, `round_id="final"`, `group="3.º y 4.º puesto"`, `home_slot="LM101"`, `away_slot="LM102"`, equipos `None`. Tras el seed hay **32** partidos KO y **2** en la ronda `final`.

- [ ] **Step 1: Actualizar los tests de conteo existentes (fallarán) y añadir el nuevo**

En `competition/tests/test_seed_command.py`:

En `test_seed_creates_31_ko_matches_with_slots_and_null_teams`, renombrar y actualizar los conteos:

```python
@pytest.mark.django_db
def test_seed_creates_32_ko_matches_with_slots_and_null_teams():
    call_command("seed_world_cup_2026")
    ko = Match.objects.exclude(round_id="groups")
    assert ko.count() == 32
    # Cada cruce KO arranca sin equipos y con ambos slots no vacíos
    for m in ko:
        assert m.home_id is None
        assert m.away_id is None
        assert m.bracket_code is not None and m.bracket_code != ""
        assert m.home_slot != ""
        assert m.away_slot != ""
    # Distribución por ronda (la ronda `final` incluye la Final y el 3.er puesto)
    assert ko.filter(round_id="r32").count() == 16
    assert ko.filter(round_id="r16").count() == 8
    assert ko.filter(round_id="qf").count() == 4
    assert ko.filter(round_id="sf").count() == 2
    assert ko.filter(round_id="final").count() == 2
```

En `test_seed_is_idempotent`, cambiar el conteo final:

```python
    assert Match.objects.exclude(round_id="groups").count() == 32
```

Añadir un test nuevo al final del fichero:

```python
@pytest.mark.django_db
def test_seed_creates_third_place_match():
    call_command("seed_world_cup_2026")
    third = Match.objects.get(bracket_code="M104")
    assert third.round_id == "final"
    assert third.group == "3.º y 4.º puesto"
    assert third.home_slot == "LM101"
    assert third.away_slot == "LM102"
    assert third.home_id is None and third.away_id is None
    # Se juega antes que la Final (M103)
    final = Match.objects.get(bracket_code="M103")
    assert third.kickoff < final.kickoff
```

- [ ] **Step 2: Ejecutar los tests de seed y ver que fallan**

Run: `python -m pytest competition/tests/test_seed_command.py -q`
Expected: FAIL — `M104` no existe todavía (los conteos siguen dando 31 / final=1 y `Match.DoesNotExist` en el test nuevo).

- [ ] **Step 3: Añadir M104 al fixture**

En `fixtures/world_cup_2026.json`, dentro del array, tras el objeto con `"pk": 103` (el último, la Final) y antes del `]` de cierre, añadir una coma al `}` del objeto 103 y luego:

```json
  {
    "model": "competition.match",
    "pk": 104,
    "fields": {
      "round": "final",
      "group": "3.º y 4.º puesto",
      "matchday": null,
      "home": null,
      "away": null,
      "home_slot": "LM101",
      "away_slot": "LM102",
      "bracket_code": "M104",
      "kickoff": "2026-07-18T19:00:00Z"
    }
  }
```

- [ ] **Step 4: Actualizar los conteos en el docstring y el help del comando**

En `competition/management/commands/seed_world_cup_2026.py`:

Línea 1 (docstring):
```python
"""Carga el calendario del Mundial 2026: 48 selecciones + 72 partidos de grupos + 32 KO.
```

`help` (~línea 25):
```python
    help = "Carga el calendario del Mundial 2026 (48 equipos + 72 grupos + 32 KO)."
```

- [ ] **Step 5: Ejecutar los tests de seed y ver que pasan**

Run: `python -m pytest competition/tests/test_seed_command.py -q`
Expected: PASS (conteos 32 / final=2 y el test nuevo del 3.er puesto).

- [ ] **Step 6: Commit**

```bash
git add fixtures/world_cup_2026.json competition/management/commands/seed_world_cup_2026.py competition/tests/test_seed_command.py
git commit -m "feat(ko): partido por el 3.er y 4.º puesto en el calendario (M104)"
```

---

### Task 3: Regresión — el 3.er puesto computa en general y en Fases Finales

**Files:**
- Test: `competition/tests/test_standings.py`

**Interfaces:**
- Consumes: `standings()` y `standings(round_ids=("r16","qf","sf","final"))` de `competition/services/standings.py`; `MatchFactory`/`PredictionFactory` de `competition/tests/factories.py`.
- Produces: garantía de que un acierto del 3.er puesto (ronda `final`) suma en la general y en el ámbito Fases Finales.

- [ ] **Step 1: Escribir el test de regresión**

Añadir a `competition/tests/test_standings.py` (usa los mismos factories que el resto del fichero; ajustar el import de `PredictionFactory` si el fichero ya lo importa):

```python
@pytest.mark.django_db
def test_third_place_match_counts_in_general_and_finals_scope():
    from accounts.tests.factories import UserFactory
    from competition.services.standings import standings
    from competition.tests.factories import (
        MatchFactory,
        PredictionFactory,
        RoundFactory,
    )

    final_round = RoundFactory(id="final", label="Final", short="FIN", points=25, order=6)
    player = UserFactory(name="Ana", is_jugador=True)
    # Partido del 3.er puesto: misma ronda `final`, sin matchday, resuelto.
    third = MatchFactory(
        round=final_round,
        group="3.º y 4.º puesto",
        matchday=None,
        bracket_code="M104",
        result_home=2,
        result_away=1,
    )
    PredictionFactory(player=player, match=third, earned=25)

    general = {r.player_id: r.pts for r in standings()}
    assert general[player.id] == 25

    finals = {
        r.player_id: r.pts
        for r in standings(round_ids=("r16", "qf", "sf", "final"))
    }
    assert finals[player.id] == 25
```

- [ ] **Step 2: Ejecutar el test**

Run: `python -m pytest competition/tests/test_standings.py::test_third_place_match_counts_in_general_and_finals_scope -q`
Expected: PASS (el comportamiento ya funciona vía ronda `final`; el test lo blinda).

Si falla por `UserFactory`/`PredictionFactory` no exportados desde `competition/tests/factories.py`, importarlos desde donde el resto de `test_standings.py` los toma (revisar los imports al principio del fichero y reutilizar los mismos).

- [ ] **Step 3: Commit**

```bash
git add competition/tests/test_standings.py
git commit -m "test(ko): el 3.er puesto suma en general y en Fases Finales"
```

---

### Task 4: Regresión — anuncios esperan a que Final y 3.er puesto estén resueltos

**Files:**
- Test: `announcements/tests/test_services.py`

**Interfaces:**
- Consumes: `detect_after_match` de `announcements/services.py`; fixtures `r16_round`, `qf_round`, `sf_round`, `final_round` y factories `MatchFactory`/`PredictionFactory`/`UserFactory` ya usados en el fichero.
- Produces: garantía de que `finals`/`global` no se anuncian hasta que **ambos** partidos de la ronda `final` (Final y 3.er puesto) estén resueltos.

- [ ] **Step 1: Escribir el test de gating**

Añadir dentro de la misma clase de tests de `announcements/tests/test_services.py` donde vive `test_final_creates_finals_sede_global_in_order` (mismo estilo y fixtures):

```python
    def test_finals_waits_for_third_place_match(
        self, r16_round, qf_round, sf_round, final_round
    ):
        from competition.models import Match

        winner = UserFactory(name="W", sede="madrid")
        for r, pts in ((r16_round, 7), (qf_round, 10), (sf_round, 15)):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=winner, match=m, earned=pts)
        # 3.er puesto (ronda final) SIN resolver todavía.
        third = MatchFactory(
            round=final_round,
            group="3.º y 4.º puesto",
            bracket_code="M104",
            matchday=None,
            result_home=None,
            result_away=None,
        )
        m_final = MatchFactory(
            round=final_round, matchday=None, result_home=2, result_away=1
        )
        PredictionFactory(player=winner, match=m_final, earned=20)

        # La Final está resuelta pero el 3.er puesto no: nada de finals/global.
        created = detect_after_match(m_final)
        assert created == []

        # Al resolver el 3.er puesto se cierra el ámbito y saltan los anuncios.
        third.result_home, third.result_away = 1, 0
        third.save(update_fields=["result_home", "result_away"])
        PredictionFactory(player=winner, match=third, earned=20)
        created = detect_after_match(third)
        kinds = [a.scope_kind for a in created]
        assert "finals" in kinds
        assert "global" in kinds
```

- [ ] **Step 2: Ejecutar el test**

Run: `python -m pytest announcements/tests/test_services.py::TestDetectAfterMatch::test_finals_waits_for_third_place_match -q`
Expected: PASS.

Nota: el nombre exacto de la clase debe copiarse del que ya usa `test_final_creates_finals_sede_global_in_order` en ese fichero (colocar el método nuevo dentro de la misma clase). Si el método `earned` de `PredictionFactory` requiere `exact_points_applied` en el match para el conteo, seguir el mismo patrón que los tests vecinos de la clase.

- [ ] **Step 3: Commit**

```bash
git add announcements/tests/test_services.py
git commit -m "test(ko): anuncios de finals/global esperan al 3.er puesto"
```

---

### Task 5: Suite completa + formato

**Files:** ninguno nuevo (verificación).

- [ ] **Step 1: Ejecutar la suite completa**

Run: `python -m pytest -q`
Expected: PASS (sin regresiones; en especial `competition/tests/test_seed_command.py`, `test_slot_label_filter.py`, `test_standings.py`, `announcements/tests/test_services.py`).

- [ ] **Step 2: Formato/lint**

Run: `ruff format . && ruff check .`
Expected: sin cambios pendientes ni errores.

- [ ] **Step 3: Commit si `ruff format` cambió algo**

```bash
git add -A
git commit -m "style: ruff format tras el partido del 3.er puesto"
```

---

## Notas de despliegue (fuera de los tests, para el cierre)

- Producción crea `M104` re-ejecutando `python manage.py seed_world_cup_2026` (idempotente, no poda KO). Confirmar que el proceso de release ejecuta el seed, o ejecutarlo manualmente tras el deploy.
- El gestor asigna a mano los perdedores de semifinales a `M104` cuando se conozcan (mismo flujo que el resto de cruces KO).
