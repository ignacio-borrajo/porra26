# Puntuación parametrizable por ronda — plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir al gestor configurar los puntos por marcador exacto y por 1·X·2 en cada ronda desde la página "Premios y puntos", aplicando los cambios solo a partidos sin resolver mediante un snapshot por partido.

**Architecture:** Se añade un campo `partial_points` a `Round` (default 1) y dos campos `*_points_applied` (nullable) a `Match` que actúan de snapshot del momento en que se confirma el resultado. `score()` lee los snapshots; `resolve_match()` los siembra solo si están vacíos. Todos los sitios que deducían "exacto" comparando con `round.points` pasan a comparar con `match.exact_points_applied`. La UI vive en la página de Premios (renombrada a "Premios y puntos") como tercer bloque.

**Tech Stack:** Django 5.1 + Postgres/SQLite, pytest + factory_boy, plantillas Django con estética glass propia.

**Referencia:** [`docs/superpowers/specs/2026-06-03-puntuacion-parametrizable-design.md`](../specs/2026-06-03-puntuacion-parametrizable-design.md)

---

## Convenciones

- Worktree: `.claude/worktrees/puntuacion-parametrizable` (rama `worktree-puntuacion-parametrizable`).
- Tests: `pytest <ruta>::<test_name> -v` desde la raíz del worktree.
- Migraciones: `python manage.py makemigrations` y/o crear a mano cuando se documente RunPython.
- Cada task termina con un commit. Mensajes en español, estilo del repo: `feat(scope): …`, `fix(scope): …`, `refactor(scope): …`, `test(scope): …`.

---

## Task 1 — `Round.partial_points`

**Files:**
- Modify: `competition/models.py:21-32` (clase `Round`)
- Create: `competition/migrations/0006_round_partial_points.py`
- Test: `competition/tests/test_round_model.py` (crear)

- [ ] **Step 1: Escribir test que falla**

`competition/tests/test_round_model.py`:

```python
import pytest

from competition.tests.factories import RoundFactory


@pytest.mark.django_db
def test_round_has_partial_points_default_one():
    r = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    assert r.partial_points == 1


@pytest.mark.django_db
def test_round_partial_points_can_be_customised():
    r = RoundFactory(id="final", points=20, partial_points=3, label="F", short="F", order=6)
    assert r.partial_points == 3
```

- [ ] **Step 2: Run test → falla**

```bash
pytest competition/tests/test_round_model.py -v
```

Expected: `FAIL` (`partial_points` no existe en el modelo).

- [ ] **Step 3: Añadir el campo al modelo**

En `competition/models.py`, dentro de `class Round`:

```python
class Round(models.Model):
    id = models.CharField(primary_key=True, max_length=10)
    label = models.CharField(max_length=40)
    short = models.CharField(max_length=10)
    points = models.PositiveSmallIntegerField()
    partial_points = models.PositiveSmallIntegerField(default=1)
    order = models.PositiveSmallIntegerField()

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.label
```

- [ ] **Step 4: Crear migración**

```bash
python manage.py makemigrations competition --name round_partial_points
```

Confirmar que el archivo generado es `competition/migrations/0006_round_partial_points.py` y contiene `AddField` con `default=1`.

- [ ] **Step 5: Aplicar migración y volver a correr el test**

```bash
python manage.py migrate competition
pytest competition/tests/test_round_model.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add competition/models.py competition/migrations/0006_round_partial_points.py competition/tests/test_round_model.py
git commit -m "feat(round): añadir partial_points (default 1) para puntos 1X2 por ronda"
```

---

## Task 2 — `Match.exact_points_applied` y `Match.partial_points_applied`

**Files:**
- Modify: `competition/models.py:35-89` (clase `Match`)
- Create: `competition/migrations/0007_match_points_applied.py` (a mano)
- Test: `competition/tests/test_match_model.py` (crear)

- [ ] **Step 1: Escribir test que falla**

`competition/tests/test_match_model.py`:

```python
import pytest

from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_match_points_applied_default_none():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    assert m.exact_points_applied is None
    assert m.partial_points_applied is None
```

- [ ] **Step 2: Run test → falla**

```bash
pytest competition/tests/test_match_model.py -v
```

Expected: FAIL.

- [ ] **Step 3: Añadir campos al modelo**

En `competition/models.py`, dentro de `class Match`, debajo de `result_away`:

```python
    result_home = models.PositiveSmallIntegerField(null=True, blank=True)
    result_away = models.PositiveSmallIntegerField(null=True, blank=True)
    exact_points_applied = models.PositiveSmallIntegerField(null=True, blank=True)
    partial_points_applied = models.PositiveSmallIntegerField(null=True, blank=True)
    finished_at = models.DateTimeField(null=True, blank=True)
```

- [ ] **Step 4: Crear migración a mano**

Crear `competition/migrations/0007_match_points_applied.py`:

```python
from django.db import migrations, models


def forwards_seed_applied_points(apps, schema_editor):
    Match = apps.get_model("competition", "Match")
    for m in Match.objects.filter(finished_at__isnull=False).select_related("round"):
        m.exact_points_applied = m.round.points
        m.partial_points_applied = m.round.partial_points
        m.save(update_fields=["exact_points_applied", "partial_points_applied"])


class Migration(migrations.Migration):
    dependencies = [
        ("competition", "0006_round_partial_points"),
    ]

    operations = [
        migrations.AddField(
            model_name="match",
            name="exact_points_applied",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.AddField(
            model_name="match",
            name="partial_points_applied",
            field=models.PositiveSmallIntegerField(blank=True, null=True),
        ),
        migrations.RunPython(forwards_seed_applied_points, migrations.RunPython.noop),
    ]
```

- [ ] **Step 5: Aplicar y verificar**

```bash
python manage.py migrate competition
pytest competition/tests/test_match_model.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add competition/models.py competition/migrations/0007_match_points_applied.py competition/tests/test_match_model.py
git commit -m "feat(match): snapshots exact/partial_points_applied al resolver partido"
```

---

## Task 3 — `resolve_match()` congela snapshots

**Files:**
- Modify: `competition/services/resolve.py`
- Test: `competition/tests/test_resolve.py` (extender)

- [ ] **Step 1: Escribir tests que fallan**

Añadir al final de `competition/tests/test_resolve.py`:

```python
@pytest.mark.django_db
def test_resolve_match_freezes_points_applied():
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    resolve_match(m, home=1, away=0, actor=GestorFactory())
    m.refresh_from_db()
    assert m.exact_points_applied == 3
    assert m.partial_points_applied == 1


@pytest.mark.django_db
def test_resolve_match_does_not_overwrite_existing_snapshots():
    """Si se edita un resultado después de cambiar la puntuación de la ronda,
    los snapshots ya fijados no se reescriben."""
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    m = MatchFactory(round=groups)
    actor = GestorFactory()
    resolve_match(m, home=1, away=0, actor=actor)

    groups.points = 10
    groups.partial_points = 5
    groups.save()
    m.refresh_from_db()

    resolve_match(m, home=2, away=0, actor=actor)
    m.refresh_from_db()
    assert m.exact_points_applied == 3
    assert m.partial_points_applied == 1
```

- [ ] **Step 2: Run tests → fallan**

```bash
pytest competition/tests/test_resolve.py -v
```

Expected: los dos tests nuevos FALL (`exact_points_applied` queda en None).

- [ ] **Step 3: Implementar el congelado en `resolve_match`**

Reescribir `competition/services/resolve.py`:

```python
from django.db import transaction
from django.utils import timezone

from accounts.models import AuditLog
from competition.models import Match, Prediction
from competition.services.score import score


@transaction.atomic
def resolve_match(match: Match, *, home: int, away: int, actor) -> None:
    """Confirma el resultado oficial y recalcula `earned` de los pronósticos."""
    match.result_home = home
    match.result_away = away
    match.finished_at = timezone.now()
    update_fields = ["result_home", "result_away", "finished_at"]

    if match.exact_points_applied is None:
        match.exact_points_applied = match.round.points
        match.partial_points_applied = match.round.partial_points
        update_fields += ["exact_points_applied", "partial_points_applied"]

    match.save(update_fields=update_fields)

    preds = list(
        Prediction.objects.select_for_update().filter(match=match).select_related("match__round")
    )
    for p in preds:
        p.earned = score(p, match)
    if preds:
        Prediction.objects.bulk_update(preds, ["earned"])

    AuditLog.objects.create(
        actor=actor,
        action="match_resolved",
        target_type="match",
        target_id=str(match.id),
        payload={"home": home, "away": away},
    )
```

- [ ] **Step 4: Run tests → pasan**

```bash
pytest competition/tests/test_resolve.py -v
```

Expected: PASS (incluidos los antiguos).

- [ ] **Step 5: Commit**

```bash
git add competition/services/resolve.py competition/tests/test_resolve.py
git commit -m "feat(resolve): congelar exact/partial_points_applied al resolver el partido"
```

---

## Task 4 — `score()` lee los snapshots

**Files:**
- Modify: `competition/services/score.py`
- Modify: `competition/tests/test_score.py` (extender + ajustar)

- [ ] **Step 1: Escribir tests que fallan**

Añadir al final de `competition/tests/test_score.py`:

```python
@pytest.mark.django_db
def test_score_uses_match_partial_points_applied():
    final = RoundFactory(id="final", points=20, partial_points=3, label="F", short="F", order=6)
    m = MatchFactory(
        round=final,
        result_home=2,
        result_away=1,
        exact_points_applied=20,
        partial_points_applied=3,
    )
    exact = type("P", (), {"home": 2, "away": 1})()
    partial = type("P", (), {"home": 3, "away": 1})()
    fail = type("P", (), {"home": 0, "away": 1})()
    assert score(exact, m) == 20
    assert score(partial, m) == 3
    assert score(fail, m) == 0


@pytest.mark.django_db
def test_score_partial_points_zero():
    r = RoundFactory(id="groups", points=3, partial_points=0, label="G", short="G", order=1)
    m = MatchFactory(
        round=r,
        result_home=1,
        result_away=0,
        exact_points_applied=3,
        partial_points_applied=0,
    )
    partial = type("P", (), {"home": 2, "away": 0})()
    assert score(partial, m) == 0
```

Los tests previos parametrizados usan `MatchFactory(round=groups_round, result_home=..., result_away=...)`. Tras esta task, dependen del snapshot del partido — hay que ajustar el helper `_match_with_result`:

```python
def _match_with_result(groups_round, rh, ra):
    return MatchFactory(
        round=groups_round,
        result_home=rh,
        result_away=ra,
        exact_points_applied=groups_round.points,
        partial_points_applied=groups_round.partial_points,
    )
```

Y `test_score_uses_round_points` pasa a `test_score_uses_exact_points_applied` con el mismo cuerpo pero usando snapshot. Sustituir:

```python
@pytest.mark.django_db
def test_score_uses_exact_points_applied():
    final = RoundFactory(id="final", points=25, label="Final", short="FIN", order=6)
    m = MatchFactory(
        round=final,
        result_home=1,
        result_away=0,
        exact_points_applied=25,
        partial_points_applied=1,
    )
    pred = type("P", (), {"home": 1, "away": 0})()
    assert score(pred, m) == 25
```

- [ ] **Step 2: Run tests → fallan**

```bash
pytest competition/tests/test_score.py -v
```

Expected: los tests nuevos FAIL (`score` aún devuelve `1` literal en el caso parcial).

- [ ] **Step 3: Implementar `score`**

Reescribir `competition/services/score.py`:

```python
from __future__ import annotations


def _sign(x: int) -> int:
    return (x > 0) - (x < 0)


def score(pred, match) -> int | None:
    """Puntos ganados por un pronóstico tras resolver el partido."""
    if match.result_home is None or match.result_away is None:
        return None
    if pred.home == match.result_home and pred.away == match.result_away:
        return match.exact_points_applied
    if _sign(pred.home - pred.away) == _sign(match.result_home - match.result_away):
        return match.partial_points_applied
    return 0
```

- [ ] **Step 4: Run tests → pasan**

```bash
pytest competition/tests/test_score.py competition/tests/test_resolve.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add competition/services/score.py competition/tests/test_score.py
git commit -m "feat(score): leer puntos desde snapshots del Match en lugar de round.points/literal"
```

---

## Task 5 — `standings.exact_hits` cuenta contra el snapshot

**Files:**
- Modify: `competition/services/standings.py:42`
- Test: `competition/tests/test_standings.py` (crear si no existe — verificar primero)

- [ ] **Step 1: Verificar test existente y escribir test que falla**

```bash
ls competition/tests/test_standings.py 2>/dev/null || echo "no existe"
```

Si no existe, crear `competition/tests/test_standings.py`:

```python
import pytest

from accounts.tests.factories import UserFactory
from competition.services.standings import standings
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_exact_hits_uses_match_snapshot_not_current_round_points():
    """Un partido resuelto con points=3 sigue contando como exacto aunque
    ahora la ronda valga 5."""
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    u = UserFactory(is_jugador=True, is_active=True)
    m = MatchFactory(
        round=groups,
        result_home=1,
        result_away=0,
        exact_points_applied=3,
        partial_points_applied=1,
    )
    PredictionFactory(player=u, match=m, home=1, away=0, earned=3)

    # Cambia el valor actual de la ronda
    groups.points = 5
    groups.save()

    rows = standings()
    me = next(r for r in rows if r.player_id == u.id)
    assert me.exact_hits == 1
```

- [ ] **Step 2: Run test → falla**

```bash
pytest competition/tests/test_standings.py::test_exact_hits_uses_match_snapshot_not_current_round_points -v
```

Expected: FAIL (`exact_hits` da 0 porque compara con `round.points=5`).

- [ ] **Step 3: Ajustar la query**

En `competition/services/standings.py:42`, cambiar:

```python
exact_hits=Count("id", filter=Q(earned=F("match__round__points"))),
```

por:

```python
exact_hits=Count("id", filter=Q(earned=F("match__exact_points_applied"))),
```

- [ ] **Step 4: Run tests → pasan**

```bash
pytest competition/tests/test_standings.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add competition/services/standings.py competition/tests/test_standings.py
git commit -m "fix(standings): contar exactos contra exact_points_applied del Match"
```

---

## Task 6 — `kpis.donut` lee el snapshot

**Files:**
- Modify: `stats/services/kpis.py:11`
- Modify: `stats/tests/test_kpis.py` (extender + ajustar fixtures si necesario)

- [ ] **Step 1: Inspeccionar test actual**

```bash
cat stats/tests/test_kpis.py
```

Para entender el setup. Detectar si las predicciones de prueba tienen `match.exact_points_applied` informado. Si no, los tests existentes se romperán al cambiar el código sin antes adaptar las fixtures.

- [ ] **Step 2: Escribir test que falla**

Añadir al final de `stats/tests/test_kpis.py`:

```python
@pytest.mark.django_db
def test_donut_uses_match_exact_points_applied():
    """Un acierto exacto con points=3 sigue contando como exacto aunque
    ahora la ronda valga 5."""
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from stats.services.kpis import donut

    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    u = UserFactory()
    m = MatchFactory(
        round=groups,
        result_home=2,
        result_away=1,
        exact_points_applied=3,
        partial_points_applied=1,
    )
    PredictionFactory(player=u, match=m, home=2, away=1, earned=3)

    groups.points = 5
    groups.save()

    assert donut(u.id) == {"exact": 1, "partial": 0, "fail": 0}
```

- [ ] **Step 3: Run test → falla**

```bash
pytest stats/tests/test_kpis.py::test_donut_uses_match_exact_points_applied -v
```

Expected: FAIL.

- [ ] **Step 4: Adaptar `donut`**

Reescribir `stats/services/kpis.py:9-19`:

```python
def donut(player_id: int) -> dict:
    rows = Prediction.objects.filter(player_id=player_id, earned__isnull=False).values_list(
        "earned", "match__exact_points_applied"
    )
    exact = partial = fail = 0
    for earned, exact_applied in rows:
        if exact_applied is not None and earned == exact_applied:
            exact += 1
        elif earned and earned > 0:
            partial += 1
        else:
            fail += 1
    return {"exact": exact, "partial": partial, "fail": fail}
```

- [ ] **Step 5: Asegurar fixtures del test antiguo**

Si `stats/tests/test_kpis.py` crea pronósticos resueltos sin pasar por `resolve_match()`, hay que poner `exact_points_applied` y `partial_points_applied` en los matches creados (o usar `resolve_match()` directamente). Editar el fixture conforme se descubra al correr los tests.

- [ ] **Step 6: Run tests → pasan**

```bash
pytest stats/tests/test_kpis.py -v
```

Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add stats/services/kpis.py stats/tests/test_kpis.py
git commit -m "fix(stats): donut usa exact_points_applied del Match"
```

---

## Task 7 — `MatchDetailView` usa el snapshot

**Files:**
- Modify: `competition/views.py:313-381` (`MatchDetailView`)
- Test: `competition/tests/test_views.py` o equivalente (verificar primero)

- [ ] **Step 1: Detectar test del modal de detalle**

```bash
grep -rn "MatchDetailView\|partido/.*\|detail" competition/tests/ | head -20
```

- [ ] **Step 2: Escribir test que falla**

Añadir a `competition/tests/test_detail_modal.py` (crear si no existe). Si existe ya un fichero de tests del detail, añadir allí:

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.mark.django_db
def test_detail_modal_marks_exact_via_applied_snapshot(client):
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    u = UserFactory(must_change_password=False)
    m = MatchFactory(
        round=groups,
        kickoff="2026-06-15T20:00:00Z",
        result_home=2,
        result_away=1,
        exact_points_applied=3,
        partial_points_applied=1,
    )
    PredictionFactory(player=u, match=m, home=2, away=1, earned=3)

    groups.points = 99
    groups.save()

    client.force_login(u)
    r = client.get(reverse("competicion:detail", args=[m.id]))
    assert r.status_code == 200
    # En el contexto, la fila del jugador está marcada como exacta porque
    # earned (3) == exact_points_applied (3), no porque earned == round.points (99).
    rows = r.context["rows"]
    me = next(row for row in rows if row.get("is_me"))
    assert me["exact"] is True
    assert r.context["round_points"] == 3
```

- [ ] **Step 3: Run test → falla**

```bash
pytest competition/tests/test_detail_modal.py -v
```

Expected: FAIL (compara contra `round.points=99`).

- [ ] **Step 4: Adaptar la vista**

En `competition/views.py:323-325`, cambiar:

```python
        round_points = m.round.points
```

por:

```python
        round_points = m.exact_points_applied or m.round.points
```

El resto de la vista no cambia (sigue usando `round_points` para la comparación `earned >= round_points`).

- [ ] **Step 5: Run tests → pasan**

```bash
pytest competition/tests/test_detail_modal.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add competition/views.py competition/tests/test_detail_modal.py
git commit -m "fix(detail): marcar exactos contra exact_points_applied del Match"
```

---

## Task 8 — Vista `PrizesSettingsView` acepta cambios de puntuación

**Files:**
- Modify: `pot/views.py:154-200` (`PrizesSettingsView`)
- Test: `pot/tests/test_prizes_settings_view.py` (extender)

- [ ] **Step 1: Escribir tests que fallan**

Añadir al final de `pot/tests/test_prizes_settings_view.py`:

```python
from competition.tests.factories import RoundFactory


@pytest.mark.django_db
def test_prizes_get_context_has_rounds(client):
    client.force_login(GestorFactory(must_change_password=False))
    RoundFactory(id="groups", points=3, partial_points=1, label="Fase de grupos", short="GRP", order=1)
    RoundFactory(id="final", points=20, partial_points=2, label="Final", short="FIN", order=6)
    r = client.get(reverse("pot:prizes"))
    ctx = r.context
    assert "rounds" in ctx
    ids = [round_.id for round_ in ctx["rounds"]]
    assert ids == ["groups", "final"]  # ordered by `order`


@pytest.mark.django_db
def test_prizes_get_renders_inputs_per_round(client):
    client.force_login(GestorFactory(must_change_password=False))
    RoundFactory(id="groups", points=3, partial_points=1, label="Fase de grupos", short="GRP", order=1)
    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    assert 'name="exact_groups"' in content
    assert 'name="partial_groups"' in content


@pytest.mark.django_db
def test_prizes_post_updates_round_scoring(client):
    from competition.models import Round

    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    r = client.post(
        reverse("pot:prizes"),
        {
            f"amount_{p1.id}": "0",
            "matchday_winner_prize": "0",
            "exact_groups": "5",
            "partial_groups": "2",
        },
    )
    assert r.status_code == 302
    groups.refresh_from_db()
    assert groups.points == 5
    assert groups.partial_points == 2


@pytest.mark.django_db
def test_prizes_post_ignores_invalid_scoring_values(client):
    from competition.models import Round

    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {
            f"amount_{p1.id}": "0",
            "matchday_winner_prize": "0",
            "exact_groups": "-3",
            "partial_groups": "abc",
        },
    )
    groups.refresh_from_db()
    # Valores inválidos no rompen, se ignoran.
    assert groups.points == 3
    assert groups.partial_points == 1


@pytest.mark.django_db
def test_prizes_post_writes_scoring_audit_log_when_changed(client):
    from accounts.models import AuditLog

    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    groups = RoundFactory(id="groups", points=3, partial_points=1, label="G", short="G", order=1)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {
            f"amount_{p1.id}": "0",
            "matchday_winner_prize": "0",
            "exact_groups": "5",
            "partial_groups": "1",
        },
    )
    log = AuditLog.objects.filter(action="scoring_changed").first()
    assert log is not None
    assert "groups" in log.payload
    assert log.payload["groups"] == {"exact": 5, "partial": 1}
```

- [ ] **Step 2: Run tests → fallan**

```bash
pytest pot/tests/test_prizes_settings_view.py -v
```

Expected: FAIL (no hay `rounds` en contexto, no se procesan los nuevos campos).

- [ ] **Step 3: Ampliar la vista**

Editar `pot/views.py`. Importar `Round`:

```python
from competition.models import Round
```

En `PrizesSettingsView.get`, ampliar el contexto:

```python
class PrizesSettingsView(GestorRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "pot/prizes_settings.html",
            {
                "prizes": Prize.objects.filter(scope="global").order_by("position"),
                "settings": PotSettings.load(),
                "paid_count": Payment.objects.filter(paid=True).count(),
                "rounds": Round.objects.all().order_by("order"),
            },
        )
```

Reescribir `PrizesSettingsView.post` para gestionar premios y puntuación juntos:

```python
    def post(self, request):
        from decimal import Decimal, InvalidOperation
        from django.db import transaction

        def _parse_decimal(raw):
            try:
                value = Decimal(raw)
            except (TypeError, InvalidOperation):
                return None
            return value if value >= 0 else None

        def _parse_int(raw):
            try:
                value = int(raw)
            except (TypeError, ValueError):
                return None
            return value if value >= 0 else None

        scoring_changes: dict[str, dict[str, int]] = {}

        with transaction.atomic():
            for prize in Prize.objects.filter(scope="global"):
                raw = request.POST.get(f"amount_{prize.id}")
                value = _parse_decimal(raw)
                if value is not None:
                    prize.amount = value
                    prize.save(update_fields=["amount"])

            mw_raw = request.POST.get("matchday_winner_prize")
            mw_value = _parse_decimal(mw_raw)
            if mw_value is not None:
                settings_obj = PotSettings.load()
                settings_obj.matchday_winner_prize = mw_value
                settings_obj.save(update_fields=["matchday_winner_prize"])

            for round_ in Round.objects.all():
                changes: dict[str, int] = {}
                new_exact = _parse_int(request.POST.get(f"exact_{round_.id}"))
                if new_exact is not None and new_exact != round_.points:
                    round_.points = new_exact
                    round_.save(update_fields=["points"])
                    changes["exact"] = new_exact
                new_partial = _parse_int(request.POST.get(f"partial_{round_.id}"))
                if new_partial is not None and new_partial != round_.partial_points:
                    round_.partial_points = new_partial
                    round_.save(update_fields=["partial_points"])
                    changes["partial"] = new_partial
                if changes:
                    scoring_changes[round_.id] = changes

            AuditLog.objects.create(
                actor=request.user,
                action="prize_changed",
                target_type="prize",
                target_id="*",
                payload={},
            )
            if scoring_changes:
                AuditLog.objects.create(
                    actor=request.user,
                    action="scoring_changed",
                    target_type="round",
                    target_id="*",
                    payload=scoring_changes,
                )

        messages.success(request, "Premios y puntos actualizados.")
        return redirect("pot:prizes")
```

- [ ] **Step 4: Run tests → pasan**

```bash
pytest pot/tests/test_prizes_settings_view.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add pot/views.py pot/tests/test_prizes_settings_view.py
git commit -m "feat(prizes): aceptar exact/partial por ronda + auditoría scoring_changed"
```

---

## Task 9 — Plantilla `pot/prizes_settings.html`: bloque 03 · Puntuación

**Files:**
- Modify: `templates/pot/prizes_settings.html`
- Test: `pot/tests/test_prizes_settings_view.py` (los tests del Step 1 ya cubren la presencia de inputs)

- [ ] **Step 1: Modificar título y header**

Cambiar línea 3:

```django
{% block title %}Premios y puntos · PORRA 26{% endblock %}
```

Cambiar el `<h1>` (línea ~9):

```html
<h1 class="grad-text" style="font-family:Sora,sans-serif;font-weight:800;letter-spacing:-0.03em;font-size:clamp(28px,4vw,40px);margin:0;line-height:1.1">
  Premios y puntos del bote
</h1>
<p style="color:var(--text-dim);font-size:15px;margin:0">
  Define el reparto del bote y cuántos puntos vale cada acierto.
</p>
```

- [ ] **Step 2: Añadir el bloque 03 antes del `<div>` del botón submit**

Justo antes de `<div style="display:flex;justify-content:flex-end">` insertar:

```html
<section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:18px">
  <header style="display:flex;flex-direction:column;gap:4px">
    <span class="eyebrow">03 · Puntuación por ronda</span>
    <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:20px">Cuánto vale cada acierto</h2>
    <p style="color:var(--text-dim);margin:0;font-size:13px">
      Los cambios se aplican solo a los partidos cuyo resultado aún no se ha confirmado.
    </p>
  </header>

  <table class="scoring-table" style="width:100%;border-collapse:collapse">
    <thead>
      <tr style="text-align:left">
        <th style="padding:8px 0;font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.12em;font-weight:600">Ronda</th>
        <th style="padding:8px 0;font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.12em;font-weight:600">Exacto</th>
        <th style="padding:8px 0;font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.12em;font-weight:600">Solo resultado (1·X·2)</th>
      </tr>
    </thead>
    <tbody>
      {% for r in rounds %}
      <tr>
        <td style="padding:10px 0;font-weight:600">{{ r.label }}</td>
        <td style="padding:10px 0">
          <div style="display:inline-flex;align-items:center;gap:6px">
            <input class="input" type="number" min="0" step="1" inputmode="numeric"
                   id="exact_{{ r.id }}" name="exact_{{ r.id }}"
                   value="{{ r.points }}" style="width:80px">
            <span class="mono" style="font-size:12px;color:var(--text-faint)">pts</span>
          </div>
        </td>
        <td style="padding:10px 0">
          <div style="display:inline-flex;align-items:center;gap:6px">
            <input class="input" type="number" min="0" step="1" inputmode="numeric"
                   id="partial_{{ r.id }}" name="partial_{{ r.id }}"
                   value="{{ r.partial_points }}" style="width:80px">
            <span class="mono" style="font-size:12px;color:var(--text-faint)">pts</span>
          </div>
        </td>
      </tr>
      {% endfor %}
    </tbody>
  </table>
</section>
```

- [ ] **Step 3: Cambiar el texto del botón submit**

```html
<button class="btn btn-primary" type="submit">Guardar premios y puntos</button>
```

- [ ] **Step 4: Run tests del view → pasan los de UI**

```bash
pytest pot/tests/test_prizes_settings_view.py -v
```

Expected: PASS (los tests `test_prizes_get_renders_inputs_per_round` ya verifican la presencia de los inputs).

- [ ] **Step 5: Commit**

```bash
git add templates/pot/prizes_settings.html
git commit -m "feat(prizes): bloque 03 puntuación por ronda en la página"
```

---

## Task 10 — Topbar y test del enlace renombrado

**Files:**
- Modify: `templates/partials/_topbar.html:27-29`
- Modify: `pot/tests/test_topbar_premios_link.py`

- [ ] **Step 1: Actualizar el test existente al nuevo texto**

En `pot/tests/test_topbar_premios_link.py`, `test_topbar_has_premios_link_for_gestor` ya acepta "Premios" como substring. Endurecer la assertion para que valide el nuevo nombre:

```python
@pytest.mark.django_db
def test_topbar_has_premios_y_puntos_link_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("pot:prizes") in content
    assert "Premios y puntos" in content
```

(renombra el test viejo y elimina el assertion ambiguo `">Premios<"`).

- [ ] **Step 2: Run test → falla**

```bash
pytest pot/tests/test_topbar_premios_link.py::test_topbar_has_premios_y_puntos_link_for_gestor -v
```

Expected: FAIL ("Premios y puntos" no está en el topbar).

- [ ] **Step 3: Cambiar el texto del enlace en `_topbar.html:27-29`**

```html
    <a href="{% url 'pot:prizes' %}" class="nav-item{% if url_name == 'prizes' %} is-active{% endif %}">
      {% icon "euro" width=17 height=17 %} Premios y puntos
    </a>
```

- [ ] **Step 4: Run tests → pasan**

```bash
pytest pot/tests/test_topbar_premios_link.py -v
```

Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add templates/partials/_topbar.html pot/tests/test_topbar_premios_link.py
git commit -m "feat(topbar): renombrar enlace 'Premios' a 'Premios y puntos'"
```

---

## Task 11 — Reglas muestra `partial_points` por ronda

**Files:**
- Modify: `templates/core/rules.html:91-107`
- Test: `core/tests/test_rules_view.py` (extender)

- [ ] **Step 1: Escribir tests que fallan**

Añadir a `core/tests/test_rules_view.py`:

```python
@pytest.mark.django_db
def test_rules_table_shows_partial_points_column(client):
    RoundFactory(id="groups", label="Fase de grupos", short="GRP", points=3, partial_points=1, order=1)
    RoundFactory(id="final", label="Final", short="FIN", points=20, partial_points=3, order=6)
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    # Encabezado de la nueva columna
    assert "1·X·2" in content
    # Valor de partial en Final aparece
    assert ">3</strong>" in content


@pytest.mark.django_db
def test_rules_does_not_claim_partial_is_always_one(client):
    RoundFactory(id="groups", label="Fase de grupos", short="GRP", points=3, partial_points=2, order=1)
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "siempre vale 1 punto" not in content
```

`RoundFactory` no aceptaba `partial_points`. Si factory_boy no lo asigna, hay que añadirlo. Editar `competition/tests/factories.py`:

```python
class RoundFactory(factory.django.DjangoModelFactory):
    class Meta:
        model = Round
        django_get_or_create = ("id",)

    id = "groups"
    label = "Fase de grupos"
    short = "GRP"
    points = 3
    partial_points = 1
    order = 1
```

(Comprobar primero si ya quedó añadido en Task 1 — si no, añadir aquí y commitear con esta task.)

- [ ] **Step 2: Run tests → fallan**

```bash
pytest core/tests/test_rules_view.py -v
```

Expected: FAIL.

- [ ] **Step 3: Modificar la tabla en `rules.html`**

En `templates/core/rules.html` líneas 91-103, sustituir:

```django
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
```

por:

```django
    <table class="rules-table">
      <thead>
        <tr>
          <th scope="col">Ronda</th>
          <th scope="col">Marcador exacto</th>
          <th scope="col">Solo resultado (1·X·2)</th>
        </tr>
      </thead>
      <tbody>
        {% for r in rounds %}
        <tr>
          <td><span class="chip" data-round="{{ r.id }}">{{ r.label }}</span></td>
          <td><strong style="font-family:Sora,sans-serif;font-weight:700;font-size:20px">{{ r.points }}</strong> <span style="font-family:'Geist Mono',monospace;color:var(--text-faint);font-size:12px">pts</span></td>
          <td><strong style="font-family:Sora,sans-serif;font-weight:700;font-size:20px">{{ r.partial_points }}</strong> <span style="font-family:'Geist Mono',monospace;color:var(--text-faint);font-size:12px">pts</span></td>
        </tr>
        {% endfor %}
      </tbody>
    </table>
```

Y reemplazar la línea 105-107:

```django
    <p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
      Acertar solo el resultado (1·X·2) siempre vale 1 punto, sea cual sea la ronda.
    </p>
```

por:

```django
    <p style="font-family:'Geist Mono',monospace;font-size:11px;color:var(--text-faint);margin:0">
      Acertar solo el resultado (1·X·2) suma los puntos indicados en la columna 1·X·2. Los valores se pueden ajustar desde "Premios y puntos".
    </p>
```

- [ ] **Step 4: Comprobar tests del modal de detalle no rotos**

El test antiguo `test_rules_renders_points_card` busca `">5</strong>"` (única coincidencia para R32 = 5 pts). Ahora podría aparecer dos veces si una ronda tiene `partial_points=5`. Verificar y ajustar el test si necesario:

```bash
pytest core/tests/test_rules_view.py -v
```

Si rompe, cambiar el test antiguo para que use un valor único (p. ej. `points=7` para `r16`, o cuente `content.count(">5</strong>") >= 1`).

- [ ] **Step 5: Run tests → pasan**

```bash
pytest core/tests/test_rules_view.py -v
```

Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add templates/core/rules.html core/tests/test_rules_view.py competition/tests/factories.py
git commit -m "feat(rules): mostrar columna 1·X·2 por ronda y quitar 'siempre vale 1 punto'"
```

---

## Task 12 — Documentación

**Files:**
- Modify: `docs/DATA_MODEL.md` §2 (sistema de puntuación)
- Modify: `CLAUDE.md` (reglas de negocio clave)

- [ ] **Step 1: Actualizar `docs/DATA_MODEL.md`**

En la sección §2 "Sistema de puntuación":

- Sustituir el pseudocódigo:

```
si pronóstico.home == resultado.home Y pronóstico.away == resultado.away:
    earned = round.points              // MARCADOR EXACTO → puntos completos de la ronda
sino si signo(pron.home − pron.away) == signo(res.home − res.away):
    earned = 1                         // ACIERTA SOLO EL RESULTADO (1·X·2) → 1 punto
sino:
    earned = 0                         // FALLO
```

por:

```
si pronóstico.home == resultado.home Y pronóstico.away == resultado.away:
    earned = match.exact_points_applied      // MARCADOR EXACTO
sino si signo(pron.home − pron.away) == signo(res.home − res.away):
    earned = match.partial_points_applied    // ACIERTA SOLO EL RESULTADO (1·X·2)
sino:
    earned = 0                                // FALLO
```

- Sustituir la nota:

> Acertar solo el resultado siempre vale **1 punto**, independientemente de la ronda.

por:

> Tanto los puntos por marcador exacto como los puntos por 1·X·2 son parametrizables por ronda desde "Premios y puntos". Al resolver un partido se congela un snapshot (`exact_points_applied`, `partial_points_applied`) en el propio `Match`: los cambios posteriores en la tabla de puntos no afectan a partidos ya resueltos.

- Añadir filas/anotación de partial en la tabla "Puntos por ronda":

| Ronda | Exacto | 1·X·2 |
|-------|--------|-------|
| Fase de grupos | 3 | 1 |
| Dieciseisavos  | 5 | 1 |
| Octavos        | 7 | 1 |
| Cuartos        | 10 | 1 |
| Semifinales    | por definir | 1 |
| Final          | por definir | 1 |

(Valores por defecto; el gestor los puede ajustar en cualquier momento.)

- [ ] **Step 2: Actualizar `CLAUDE.md` §"Reglas de negocio clave"**

Sustituir la primera bullet:

> - **Puntuación:** marcador exacto → puntos completos del partido; acertar solo el resultado (1/X/2) → 1 punto; fallar → 0.

por:

> - **Puntuación:** marcador exacto → puntos del partido (parametrizable por ronda); acertar solo el resultado (1/X/2) → puntos parciales (parametrizable, default 1); fallar → 0. Los puntos se congelan en cada `Match` al resolverse, los cambios solo aplican a partidos sin resolver.

- [ ] **Step 3: Commit**

```bash
git add docs/DATA_MODEL.md CLAUDE.md
git commit -m "docs: puntuación parametrizable y snapshot en Match"
```

---

## Task 13 — Verificación end-to-end

**Files:** ninguno

- [ ] **Step 1: Suite completa**

```bash
pytest -q
```

Expected: 0 failures. Si falla algún test ajeno al cambio (p. ej. fixtures de stats que no setean `exact_points_applied`), revisarlo y arreglarlo en este paso. Posibles puntos calientes:
- `stats/tests/test_history.py` y `stats/tests/test_view.py` si construyen `Prediction` resueltas sin pasar por `resolve_match`.
- Test antiguos que comparan `">5</strong>"` en la página de reglas — ajustados ya en Task 11 si rompieron.

- [ ] **Step 2: Smoke manual (opcional)**

Levantar el dev server y probar el flujo:

```bash
python manage.py runserver
```

Como gestor:
1. Ir a `/premios/`.
2. Cambiar `Cuartos · Exacto` de 10 a 8 y `Partial` de 1 a 2.
3. Guardar → mensaje "Premios y puntos actualizados.".
4. Ir a `/reglas/` → la tabla refleja los nuevos valores y no hay "siempre vale 1 punto".
5. Ir a `/auditoria/` → existe entrada `scoring_changed` con payload `{cuartos: {exact: 8, partial: 2}}`.

- [ ] **Step 3: Commit final si quedó algún ajuste**

```bash
git status
```

Si está limpio, no hacer commit. Si hay cambios pendientes, agrupar con `chore: ajustes post-verificación` o equivalente.

---

## Self-review checklist (ya cubierto)

- ✅ **Spec coverage:** cada sección de la spec tiene su task (modelo §3 → tasks 1-2; lógica §4 → tasks 3-7; UI Premios §5 → tasks 8-10; UI Reglas §5 → task 11; migraciones §6 → tasks 1-2; tests §7 → tasks 1-11; docs §8 → task 12).
- ✅ **Placeholders:** no quedan TBD/TODO/"similar a otra task" — cada step muestra el código real.
- ✅ **Consistencia de nombres:** `exact_points_applied` y `partial_points_applied` aparecen igual en todas las tasks; `scoring_changed` es el único nombre de la acción de auditoría.
