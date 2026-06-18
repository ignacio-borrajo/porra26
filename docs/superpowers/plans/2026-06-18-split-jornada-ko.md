# Split de la jornada KO en dos jornadas (Dieciseisavos + Fases Finales) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Partir la única jornada eliminatoria (que agrega todos los partidos KO) en dos jornadas independientes —«Dieciseisavos» (solo `r32`) y «Fases Finales» (`r16+qf+sf+final`)— cada una con su clasificación, ganador, premio y modal de victoria, pasando de 4 a 5 jornadas.

**Architecture:** App Django. El concepto «jornada KO» vive en tres capas: el cálculo de ganador/premio (`pot/services/prizes.py`), el disparo del modal de victoria (`announcements/`), y el selector de clasificación (`stats/services/matchday_options.py`). Se sustituye el scope único `"ko"` por dos scopes `"r32"` y `"finals"`. El premio sigue siendo el importe único `PotSettings.matchday_winner_prize` para las cinco jornadas (sin campos nuevos).

**Tech Stack:** Django 5.1, pytest / pytest-django, factory_boy. Comando de test: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest`. Lint: `ruff`.

**Spec:** `docs/superpowers/specs/2026-06-18-split-jornada-ko-design.md`

**Worktree:** ya creado en `.claude/worktrees/split-jornada-ko` (rama `worktree-split-jornada-ko`). Baseline verde (636 tests en las apps afectadas). El binario de Python del venv compartido es:
`/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python` — abreviado en el resto del plan como **`$PY`**. Antes de empezar, exporta:

```bash
PY=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python
cd /Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.claude/worktrees/split-jornada-ko
```

---

## File Structure

- `announcements/models.py` — `WinnerAnnouncement.SCOPE_CHOICES`, `title`, `__str__`, constraints únicos. **Modify.**
- `announcements/migrations/0005_split_ko_into_r32_and_finals.py` — migración de choices + constraints + limpieza defensiva. **Create.**
- `pot/services/prizes.py` — scopes `r32` y `finals` en `_matches_for_scope`, `_standings_for_scope`, `announcement_podium`. **Modify.**
- `announcements/services.py` — `detect_after_match` dispara `r32` al cerrar R32 y `finals→sede→global` al cerrar la Final. **Modify.**
- `announcements/preview.py` — `_VALID_SCOPES`. **Modify.**
- `stats/services/matchday_options.py` — dos opciones KO en el selector. **Modify.**
- `templates/pot/prizes_settings.html`, `templates/core/rules.html`, `docs/DATA_MODEL.md` — copys «4→5 jornadas» y opciones del previsualizador. **Modify.**
- Tests a actualizar/crear: `announcements/tests/test_models.py`, `announcements/tests/test_services.py`, `announcements/tests/test_integration.py`, `announcements/tests/test_preview.py`, `pot/tests/test_prizes.py`, `stats/tests/test_matchday_options.py`, `stats/tests/test_rankings_view.py`.

---

## Task 1: Modelo `WinnerAnnouncement` + migración

Sustituye el scope `"ko"` por `"r32"` y `"finals"` en choices, títulos, `__str__` y constraints únicos, con su migración.

**Files:**
- Modify: `announcements/models.py`
- Create: `announcements/migrations/0005_split_ko_into_r32_and_finals.py`
- Test: `announcements/tests/test_models.py`

- [ ] **Step 1: Reescribir los tests de `"ko"` en `test_models.py`**

En `announcements/tests/test_models.py`, **sustituye** `test_str_for_ko` (líneas 14-16) por estos dos métodos dentro de `TestWinnerAnnouncementStr`:

```python
    def test_str_for_r32(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="r32", points=42)
        assert "dieciseisavos" in str(ann).lower()

    def test_str_for_finals(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="finals", points=42)
        assert "fases finales" in str(ann).lower()
```

**Sustituye** `test_title_singular_ko` y `test_title_plural_ko` (líneas 41-47) por:

```python
    def test_title_singular_r32(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="r32", points=42, tied=False)
        assert ann.title == "¡Ganador de Dieciseisavos!"

    def test_title_plural_r32(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="r32", points=42, tied=True)
        assert ann.title == "¡Ganadores de Dieciseisavos!"

    def test_title_singular_finals(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="finals", points=42, tied=False)
        assert ann.title == "¡Ganador de las Fases Finales!"

    def test_title_plural_finals(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="finals", points=42, tied=True)
        assert ann.title == "¡Ganadores de las Fases Finales!"
```

**Sustituye** `test_uniqueness_constraint_ko` (líneas 69-72) por:

```python
    def test_uniqueness_constraint_r32(self):
        WinnerAnnouncement.objects.create(scope_kind="r32", points=42)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="r32", points=50)

    def test_uniqueness_constraint_finals(self):
        WinnerAnnouncement.objects.create(scope_kind="finals", points=42)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="finals", points=50)
```

- [ ] **Step 2: Ejecutar los tests para verlos fallar**

Run: `$PY -m pytest announcements/tests/test_models.py -q`
Expected: FAIL — los nuevos tests fallan (los títulos `r32`/`finals` no existen y la constraint única no está). El error de uniqueness saldrá como "did not raise IntegrityError" porque aún no hay constraint.

- [ ] **Step 3: Modificar el modelo**

En `announcements/models.py`, reemplaza `SCOPE_CHOICES` (líneas 8-13):

```python
    SCOPE_CHOICES = [
        ("matchday", "Jornada de grupos"),
        ("r32", "Jornada de dieciseisavos"),
        ("finals", "Jornada de fases finales"),
        ("global", "Campeón del Mundial"),
        ("sede", "Ganadores por sede"),
    ]
```

Reemplaza el bloque de `constraints` de la antigua `uniq_ann_ko` (líneas 35-39) por dos constraints:

```python
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="r32"),
                name="uniq_ann_r32",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="finals"),
                name="uniq_ann_finals",
            ),
```

Reemplaza la rama `"ko"` de `__str__` (líneas 55-56) por:

```python
        if self.scope_kind == "r32":
            return "Anuncio jornada de dieciseisavos"
        if self.scope_kind == "finals":
            return "Anuncio jornada de fases finales"
```

Reemplaza la rama `"ko"` de `title` (líneas 67-72) por:

```python
        if self.scope_kind == "r32":
            return "¡Ganadores de Dieciseisavos!" if self.tied else "¡Ganador de Dieciseisavos!"
        if self.scope_kind == "finals":
            return (
                "¡Ganadores de las Fases Finales!"
                if self.tied
                else "¡Ganador de las Fases Finales!"
            )
```

- [ ] **Step 4: Crear la migración**

Crea `announcements/migrations/0005_split_ko_into_r32_and_finals.py` con este contenido exacto:

```python
from django.db import migrations, models


def delete_ko_announcements(apps, schema_editor):
    """Defensivo e idempotente: a mitad de fase de grupos no puede existir
    ningún anuncio scope_kind="ko" (solo se creaba al resolverse la Final),
    pero limpiamos por si acaso para no dejar filas huérfanas tras el split."""
    WinnerAnnouncement = apps.get_model("announcements", "WinnerAnnouncement")
    WinnerAnnouncement.objects.filter(scope_kind="ko").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0004_drop_round_scope_add_ko"),
    ]

    operations = [
        migrations.RunPython(delete_ko_announcements, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="winnerannouncement",
            name="uniq_ann_ko",
        ),
        migrations.AlterField(
            model_name="winnerannouncement",
            name="scope_kind",
            field=models.CharField(
                choices=[
                    ("matchday", "Jornada de grupos"),
                    ("r32", "Jornada de dieciseisavos"),
                    ("finals", "Jornada de fases finales"),
                    ("global", "Campeón del Mundial"),
                    ("sede", "Ganadores por sede"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="winnerannouncement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("scope_kind", "r32")),
                fields=("scope_kind",),
                name="uniq_ann_r32",
            ),
        ),
        migrations.AddConstraint(
            model_name="winnerannouncement",
            constraint=models.UniqueConstraint(
                condition=models.Q(("scope_kind", "finals")),
                fields=("scope_kind",),
                name="uniq_ann_finals",
            ),
        ),
    ]
```

- [ ] **Step 5: Verificar que no faltan migraciones**

Run: `$PY manage.py makemigrations --check --dry-run`
Expected: "No changes detected" (o salida sin proponer nuevas migraciones para `announcements`). Si propusiera cambios, ajusta el modelo/migración hasta que coincidan.

- [ ] **Step 6: Ejecutar los tests para verlos pasar**

Run: `$PY -m pytest announcements/tests/test_models.py -q`
Expected: PASS (todos).

- [ ] **Step 7: Commit**

```bash
git add announcements/models.py announcements/migrations/0005_split_ko_into_r32_and_finals.py announcements/tests/test_models.py
git commit -m "feat(announcements): split scope ko en r32 + finals (modelo + migración)"
```

---

## Task 2: Servicio de premios `pot/services/prizes.py`

Sustituye el scope agregado `"ko"` por `"r32"` (solo `r32`) y `"finals"` (`r16+qf+sf+final`).

**Files:**
- Modify: `pot/services/prizes.py`
- Test: `pot/tests/test_prizes.py`

- [ ] **Step 1: Reescribir los tests de scope KO en `test_prizes.py`**

En `pot/tests/test_prizes.py`, **sustituye** `test_ko_only_position_1_has_prize` (líneas 220-243) por (cambia el `scope_kind` del anuncio a `"finals"`, todo lo demás igual):

```python
    @pytest.mark.django_db
    def test_finals_only_position_1_has_prize(self, db):
        r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("20")
        s.save()
        a = UserFactory(name="A")
        b = UserFactory(name="B")
        m = MatchFactory(round=r16, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=a, match=m, home=1, away=0, earned=7)
        PredictionFactory(player=b, match=m, home=2, away=1, earned=1)
        from announcements.models import WinnerAnnouncement

        ann = WinnerAnnouncement.objects.create(
            scope_kind="finals",
            points=7,
            tied=False,
            share=Decimal("20"),
        )
        ann.winners.set([a])
        entries = announcement_podium(ann)
        assert [e.position for e in entries] == [1, 2]
        assert entries[0].prize_per_user == Decimal("20")
        assert entries[1].prize_per_user == Decimal("0")
```

**Sustituye** las tres funciones de módulo `test_matchday_winners_ko_*` (líneas 294-365, hasta el final del fichero) por estas cinco:

```python
@pytest.mark.django_db
def test_matchday_winners_r32_resolved_uses_only_r32():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings
    from pot.services.prizes import matchday_winners

    pot = PotSettings.load()
    pot.matchday_winner_prize = Decimal("30.00")
    pot.save(update_fields=["matchday_winner_prize"])

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    winner = UserFactory(name="W")
    loser = UserFactory(name="L")
    m_r32 = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=winner, match=m_r32, earned=5)
    PredictionFactory(player=loser, match=m_r32, earned=0)
    # Un partido de r16 con puntos NO debe contar para el scope r32.
    m_r16 = MatchFactory(round=r16, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=loser, match=m_r16, earned=7)

    result = matchday_winners(("r32", None))
    assert result.status == "resolved"
    assert result.points == 5
    assert [u.name for u in result.winners] == ["W"]
    assert result.share == Decimal("30.00")


@pytest.mark.django_db
def test_matchday_winners_r32_pending_until_all_r32_resolved():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    user = UserFactory()
    m_done = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=user, match=m_done, earned=5)
    MatchFactory(round=r32, matchday=None, result_home=None)

    result = matchday_winners(("r32", None))
    assert result.status == "pending"


@pytest.mark.django_db
def test_matchday_winners_finals_pending_until_all_finals_resolved():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    qf = RoundFactory(id="qf", points=10, label="QF", short="QF", order=4)
    sf = RoundFactory(id="sf", points=15, label="SF", short="SF", order=5)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory()
    for r in (r16, qf, sf):
        m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=r.points)
    MatchFactory(round=fn, matchday=None, result_home=None)

    result = matchday_winners(("finals", None))
    assert result.status == "pending"


@pytest.mark.django_db
def test_matchday_winners_finals_aggregates_r16_qf_sf_final_excluding_r32():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings
    from pot.services.prizes import matchday_winners

    pot = PotSettings.load()
    pot.matchday_winner_prize = Decimal("30.00")
    pot.save(update_fields=["matchday_winner_prize"])

    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    qf = RoundFactory(id="qf", points=10, label="QF", short="QF", order=4)
    sf = RoundFactory(id="sf", points=15, label="SF", short="SF", order=5)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)

    winner = UserFactory(name="W")
    loser = UserFactory(name="L")
    # r32 NO cuenta para finals: damos al loser muchos puntos en r32.
    m_r32 = MatchFactory(round=r32, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=loser, match=m_r32, earned=99)
    for r, pts in ((r16, 7), (qf, 10), (sf, 15), (fn, 20)):
        m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=winner, match=m, earned=pts)
        PredictionFactory(player=loser, match=m, earned=0)

    result = matchday_winners(("finals", None))
    assert result.status == "resolved"
    assert result.points == 52  # 7+10+15+20, sin el r32
    assert [u.name for u in result.winners] == ["W"]
    assert result.share == Decimal("30.00")


@pytest.mark.django_db
def test_matchday_winners_finals_excludes_groups_points():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory()
    m_grp = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_fn = MatchFactory(round=fn, matchday=None, result_home=2, result_away=1)
    PredictionFactory(player=user, match=m_grp, earned=3)
    PredictionFactory(player=user, match=m_fn, earned=20)

    result = matchday_winners(("finals", None))
    assert result.status == "resolved"
    assert result.points == 20
```

- [ ] **Step 2: Ejecutar los tests para verlos fallar**

Run: `$PY -m pytest pot/tests/test_prizes.py -q`
Expected: FAIL — `matchday_winners(("r32", …))` y `("finals", …)` lanzan `ValueError: unknown scope: r32` / `finals` (el servicio aún solo conoce `ko`).

- [ ] **Step 3: Modificar `pot/services/prizes.py`**

Reemplaza la constante `_KO_ROUND_IDS` (línea 88) por:

```python
_FINALS_ROUND_IDS = ["r16", "qf", "sf", "final"]
```

Reemplaza `_matches_for_scope` (líneas 91-99) por:

```python
def _matches_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return Match.objects.filter(round_id="groups", matchday=value)
    if kind == "r32":
        return Match.objects.filter(round_id="r32")
    if kind == "finals":
        return Match.objects.filter(round_id__in=_FINALS_ROUND_IDS)
    if kind == "global":
        return Match.objects.all()
    raise ValueError(f"unknown scope: {kind}")
```

Reemplaza `_standings_for_scope` (líneas 102-108) por:

```python
def _standings_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return standings(round_id="groups", matchday=value)
    if kind == "r32":
        return standings(round_id="r32")
    if kind == "finals":
        return standings(round_ids=_FINALS_ROUND_IDS)
    return standings()
```

Reemplaza la rama `"ko"` de `announcement_podium` (líneas 57-62) por:

```python
    if announcement.scope_kind == "matchday":
        rows = standings(round_id="groups", matchday=announcement.scope_matchday)
    elif announcement.scope_kind == "r32":
        rows = standings(round_id="r32")
    elif announcement.scope_kind == "finals":
        rows = standings(round_ids=_FINALS_ROUND_IDS)
    else:
        rows = standings()
```

(Nota: `_prizes_by_position_for` no cambia: solo `"global"` es especial; `r32` y `finals` caen en el `else` que devuelve `matchday_winner_prize`. Esto requiere que `_FINALS_ROUND_IDS` esté definida **antes** de `announcement_podium`; muévela al inicio del módulo, justo después de los imports, o déjala donde estaba y comprueba que `announcement_podium` la referencia sin error — en Python una función referencia variables globales en tiempo de llamada, así que basta con que exista al ejecutarse. Mantén la definición existente en su posición renombrada.)

- [ ] **Step 4: Ejecutar los tests para verlos pasar**

Run: `$PY -m pytest pot/tests/test_prizes.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add pot/services/prizes.py pot/tests/test_prizes.py
git commit -m "feat(pot): scopes de premio r32 y finals en lugar de ko"
```

---

## Task 3: Disparo de modales `announcements/services.py`

`detect_after_match`: R32 dispara `r32` al cerrarse el último partido R32; la Final dispara `finals→sede→global`.

**Files:**
- Modify: `announcements/services.py`
- Test: `announcements/tests/test_services.py`, `announcements/tests/test_integration.py`

- [ ] **Step 1: Reescribir los tests de scope KO en `test_services.py`**

En `announcements/tests/test_services.py`, **sustituye** la clase `TestKoSilentRounds` (líneas 72-87) por:

```python
@pytest.mark.django_db
class TestR32Scope:
    def test_no_announcement_until_last_r32_resolved(self, r32_round):
        user = UserFactory()
        m_done = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m_done, earned=5)
        MatchFactory(round=r32_round, matchday=None, result_home=None)
        created = detect_after_match(m_done)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0

    def test_r32_announcement_created_when_last_r32_resolved(self, r32_round):
        user = UserFactory(name="Ganadora")
        m1 = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        m2 = MatchFactory(round=r32_round, matchday=None, result_home=2, result_away=0)
        PredictionFactory(player=user, match=m1, earned=5)
        PredictionFactory(player=user, match=m2, earned=5)
        created = detect_after_match(m2)
        assert len(created) == 1
        assert created[0].scope_kind == "r32"
        assert created[0].points == 10
        assert list(created[0].winners.all()) == [user]


@pytest.mark.django_db
class TestFinalsSilentRounds:
    def test_resolving_r16_creates_no_announcement(self, r16_round):
        user = UserFactory()
        m = MatchFactory(round=r16_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=7)
        created = detect_after_match(m)
        assert created == []

    def test_resolving_sf_creates_no_announcement(self, sf_round):
        user = UserFactory()
        m = MatchFactory(round=sf_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=15)
        created = detect_after_match(m)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0
```

En la clase `TestFinalTriggers`, **sustituye** `test_final_creates_ko_sede_global_in_order` (línea 119) cambiando la aserción:

```python
        assert kinds == ["finals", "sede", "global"]
```

y renómbralo a `test_final_creates_finals_sede_global_in_order`.

**Sustituye** `test_final_ko_aggregates_all_ko_including_final_points` (líneas 121-138) por (ahora `finals` excluye r32 → 7+10+15+20 = 52):

```python
    def test_final_finals_aggregates_r16_qf_sf_final_points(
        self, r32_round, r16_round, qf_round, sf_round, final_round
    ):
        winner = UserFactory(name="W", sede="madrid")
        # r32 NO cuenta para la jornada finals.
        m_r32 = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=winner, match=m_r32, earned=5)
        for r, pts in (
            (r16_round, 7),
            (qf_round, 10),
            (sf_round, 15),
        ):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=winner, match=m, earned=pts)
        m_final = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=winner, match=m_final, earned=20)

        created = detect_after_match(m_final)
        finals = next(a for a in created if a.scope_kind == "finals")
        assert finals.points == 52  # 7+10+15+20, sin el r32
```

- [ ] **Step 2: Actualizar `test_integration.py`**

En `announcements/tests/test_integration.py` línea 73, cambia:

```python
    assert kinds == ["finals", "global", "sede"]
```

(`sorted(["finals","sede","global"])` → `["finals","global","sede"]`.) Renombra la función `test_resolve_final_creates_ko_sede_global` a `test_resolve_final_creates_finals_sede_global`.

- [ ] **Step 3: Ejecutar los tests para verlos fallar**

Run: `$PY -m pytest announcements/tests/test_services.py announcements/tests/test_integration.py -q`
Expected: FAIL — al resolver el último R32 no se crea anuncio (servicio aún ignora r32) y al resolver la Final se crea `ko` en vez de `finals`.

- [ ] **Step 4: Modificar `announcements/services.py`**

Reemplaza el cuerpo de `detect_after_match` desde el `if`/`elif` (líneas 21-33) por:

```python
    created: list[WinnerAnnouncement] = []

    if match.round_id == "groups" and match.matchday is not None:
        ann = _try_create("matchday", matchday=match.matchday)
        if ann is not None:
            created.append(ann)
    elif match.round_id == "r32":
        ann = _try_create("r32")
        if ann is not None:
            created.append(ann)
    elif match.round_id == "final":
        for kind in ("finals", "sede", "global"):
            ann = _try_create(kind)
            if ann is not None:
                created.append(ann)

    return created
```

Actualiza el docstring de `detect_after_match` (líneas 12-20) para reflejar la nueva lógica:

```python
    """Llamado tras resolve_match(). Crea (idempotentemente) los anuncios de
    ganador del scope al que pertenece el partido recién resuelto, si ese scope
    acaba de cerrarse. Devuelve los anuncios creados en esta llamada (0..N).

    Reglas:
    - Fase de grupos: 1 anuncio matchday(N) si la jornada N acaba de cerrar.
    - r32: 1 anuncio "r32" cuando el último partido de dieciseisavos se resuelve.
    - r16/qf/sf: ningún anuncio (esperan a que la Final cierre la jornada finals).
    - final: 3 anuncios (finals → sede → global) en ese orden, para que el feed
      de modales muestre la jornada finals primero, luego sede y por último el
      campeón del Mundial (climax).
    """
```

En `_try_create`, actualiza la rama de scopes válidos (línea 43):

```python
    elif scope_kind in ("r32", "finals", "global", "sede"):
        filter_kwargs = {"scope_kind": scope_kind}
```

- [ ] **Step 5: Ejecutar los tests para verlos pasar**

Run: `$PY -m pytest announcements/tests/test_services.py announcements/tests/test_integration.py -q`
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add announcements/services.py announcements/tests/test_services.py announcements/tests/test_integration.py
git commit -m "feat(announcements): r32 dispara su modal; final dispara finals+sede+global"
```

---

## Task 4: Previsualización `announcements/preview.py`

Habilita los scopes `r32` y `finals` en el previsualizador del gestor.

**Files:**
- Modify: `announcements/preview.py`
- Test: `announcements/tests/test_preview.py`

- [ ] **Step 1: Reescribir los tests de scope KO en `test_preview.py`**

En `announcements/tests/test_preview.py`, **sustituye** `test_ko_builds_announcement_without_extra_state` (líneas 51-57) por:

```python
    def test_r32_builds_announcement_without_extra_state(self):
        gestor = GestorFactory()
        ann, winners = build_preview("r32", tied=False, current_user=gestor)
        assert ann.scope_kind == "r32"
        assert ann.scope_matchday is None
        assert ann.title == "¡Ganador de Dieciseisavos!"
        assert winners == [gestor]

    def test_finals_builds_announcement_without_extra_state(self):
        gestor = GestorFactory()
        ann, winners = build_preview("finals", tied=False, current_user=gestor)
        assert ann.scope_kind == "finals"
        assert ann.scope_matchday is None
        assert ann.title == "¡Ganador de las Fases Finales!"
        assert winners == [gestor]
```

**Sustituye** `test_ko_title` (líneas 106-109) por:

```python
    def test_r32_title(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=r32&tied=0")
        assert "¡Ganador de Dieciseisavos!" in res.content.decode()

    def test_finals_title(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=finals&tied=0")
        assert "¡Ganador de las Fases Finales!" in res.content.decode()
```

- [ ] **Step 2: Ejecutar los tests para verlos fallar**

Run: `$PY -m pytest announcements/tests/test_preview.py -q`
Expected: FAIL — `build_preview("r32"/"finals")` lanza `Http404` (scopes no válidos).

- [ ] **Step 3: Modificar `announcements/preview.py`**

Reemplaza la línea 10:

```python
_VALID_SCOPES = {"matchday", "r32", "finals", "global"}
```

Actualiza el comentario de la línea 21 dentro de `build_preview`:

```python
    # scope r32 / finals: un único anuncio por torneo, sin estado adicional.
```

(`_preview_prize_for_position` no cambia: `r32` y `finals` caen en `position == 1 → matchday_winner_prize`.)

- [ ] **Step 4: Ejecutar los tests para verlos pasar**

Run: `$PY -m pytest announcements/tests/test_preview.py -q`
Expected: PASS (todos).

- [ ] **Step 5: Commit**

```bash
git add announcements/preview.py announcements/tests/test_preview.py
git commit -m "feat(announcements): previsualización de modales r32 y finals"
```

---

## Task 5: Selector de Rankings `stats/services/matchday_options.py`

Parte la opción única «Fases Finales» en «Dieciseisavos» (`r32`) + «Fases Finales» (`r16+qf+sf+final`).

**Files:**
- Modify: `stats/services/matchday_options.py`
- Test: `stats/tests/test_matchday_options.py`, `stats/tests/test_rankings_view.py`

- [ ] **Step 1: Reescribir `test_matchday_options.py`**

Reemplaza el import (líneas 7-11):

```python
from stats.services.matchday_options import (
    FINALS_SCOPE_KEY,
    FINALS_SCOPE_LABEL,
    R32_SCOPE_KEY,
    R32_SCOPE_LABEL,
    matchday_options,
)
```

**Sustituye** `test_matchday_options_collapses_ko_rounds_into_fases_finales` (líneas 31-64) por:

```python
@pytest.mark.django_db
def test_matchday_options_splits_ko_into_r32_and_fases_finales():
    grp = RoundFactory(id="groups", label="Grupos", short="G", order=1)
    r32 = RoundFactory(id="r32", label="Dieciseisavos", short="R32", order=2)
    r16 = RoundFactory(id="r16", label="Octavos", short="R16", order=3)
    qf = RoundFactory(id="qf", label="Cuartos", short="QF", order=4)
    sf = RoundFactory(id="sf", label="Semifinales", short="SF", order=5)
    final = RoundFactory(id="final", label="Final", short="F", order=6)
    now = timezone.now()
    MatchFactory(
        round=grp,
        matchday=1,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=1),
    )
    for i, rnd in enumerate((r32, r16, qf, sf, final), start=10):
        MatchFactory(
            round=rnd,
            matchday=None,
            home=TeamFactory(),
            away=TeamFactory(),
            kickoff=now + timedelta(days=i),
        )

    options = matchday_options()
    labels = [o.label for o in options]
    assert labels == ["Jornada 1", R32_SCOPE_LABEL, FINALS_SCOPE_LABEL]

    r32_opt = next(o for o in options if o.key == R32_SCOPE_KEY)
    assert r32_opt.label == R32_SCOPE_LABEL
    assert r32_opt.round_id == "r32"
    assert r32_opt.round_ids is None
    assert r32_opt.matchday is None

    fases = options[-1]
    assert fases.key == FINALS_SCOPE_KEY
    assert fases.round_ids == ["r16", "qf", "sf", "final"]
    assert fases.round_id is None
    assert fases.matchday is None
```

**Sustituye** `test_matchday_options_fases_finales_fully_resolved_only_when_all_ko_done` (líneas 67-91) por (ahora el final pertenece a finals; r32 ya no cuenta para «Fases Finales»):

```python
@pytest.mark.django_db
def test_matchday_options_fases_finales_fully_resolved_only_when_all_finals_done():
    r16 = RoundFactory(id="r16", label="Octavos", short="R16", order=3)
    final = RoundFactory(id="final", label="Final", short="F", order=6)
    now = timezone.now()
    MatchFactory(
        round=r16,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    MatchFactory(
        round=final,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now + timedelta(days=2),
    )

    fases = matchday_options()[-1]
    assert fases.label == FINALS_SCOPE_LABEL
    assert fases.fully_resolved is False
```

- [ ] **Step 2: Actualizar `test_rankings_view.py`**

En `stats/tests/test_rankings_view.py`:

Localiza el bloque de aserciones de las líneas 130-135 y reemplázalo por:

```python
    assert "Jornada 1" in body
    assert "Dieciseisavos" in body
    assert "Fases Finales" in body
    # Octavos/cuartos/semis/final NO se muestran como opciones independientes.
    assert "Octavos" not in body
    assert "scope=r32:_" in body
    assert "scope=finals:_" in body
```

**Sustituye** la función `test_rankings_scope_ko_sums_points_across_ko_rounds` (líneas ~138-176) por una que use solo rondas de la jornada finals (r16+final, excluyendo r32):

```python
@pytest.mark.django_db
def test_rankings_scope_finals_sums_points_across_finals_rounds(client):
    ana = UserFactory(name="Ana", email="ana@e.com", must_change_password=False)
    client.force_login(ana)
    r16 = RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)
    final = RoundFactory(id="final", points=20, label="Final", short="F", order=6)
    now = timezone.now()
    m_r16 = MatchFactory(
        round=r16,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=2),
        result_home=1,
        result_away=0,
    )
    m_final = MatchFactory(
        round=final,
        matchday=None,
        home=TeamFactory(),
        away=TeamFactory(),
        kickoff=now - timedelta(days=1),
        result_home=2,
        result_away=2,
    )
    PredictionFactory(player=ana, match=m_r16, home=1, away=0, earned=5)
    PredictionFactory(player=ana, match=m_final, home=2, away=2, earned=20)

    r = client.get(reverse("stats:rankings") + "?tab=general&scope=finals:_")
    assert r.status_code == 200
    body = r.content.decode()
    assert "scope=finals:_" in body
    assert "Fases Finales" in body
    assert "25" in body
```

- [ ] **Step 3: Ejecutar los tests para verlos fallar**

Run: `$PY -m pytest stats/tests/test_matchday_options.py stats/tests/test_rankings_view.py -q`
Expected: FAIL — `ImportError` de las constantes nuevas y/o el selector aún produce una sola opción «Fases Finales».

- [ ] **Step 4: Modificar `stats/services/matchday_options.py`**

Reemplaza las constantes de cabecera (líneas 7-9) por:

```python
FINALS_ROUND_IDS: tuple[str, ...] = ("r16", "qf", "sf", "final")
R32_SCOPE_KEY = "r32:_"
R32_SCOPE_LABEL = "Dieciseisavos"
FINALS_SCOPE_KEY = "finals:_"
FINALS_SCOPE_LABEL = "Fases Finales"
```

Reemplaza el docstring de `matchday_options` (líneas 23-28) por:

```python
    """Opciones del selector de jornada para Rankings.

    La porra tiene 5 jornadas: las tres de la fase de grupos (cada una como
    opción independiente), «Dieciseisavos» (solo R32) y «Fases Finales», que
    agrupa el resto de eliminatorias (R16, cuartos, semis y final).
    """
```

Reemplaza el cuerpo del bucle y el bloque de cierre (líneas 40-79) por:

```python
    options: list[MatchdayOption] = []
    finals_combos: list[dict] = []
    for c in combos:
        if c["round_id"] in FINALS_ROUND_IDS:
            finals_combos.append(c)
            continue
        rnd = rounds_by_id.get(c["round_id"])
        round_label = rnd.label if rnd else c["round_id"]
        md = c["matchday"]
        if md is not None:
            if c["round_id"] == "groups":
                label = f"Jornada {md}"
            else:
                label = f"{round_label} · J{md}"
        elif c["round_id"] == "r32":
            label = R32_SCOPE_LABEL
        else:
            label = round_label
        options.append(
            MatchdayOption(
                round_id=c["round_id"],
                matchday=md,
                label=label,
                key=f"{c['round_id']}:{md if md is not None else '_'}",
                fully_resolved=c["resolved"] == c["total"],
            )
        )

    if finals_combos:
        total = sum(c["total"] for c in finals_combos)
        resolved = sum(c["resolved"] for c in finals_combos)
        options.append(
            MatchdayOption(
                round_id=None,
                matchday=None,
                label=FINALS_SCOPE_LABEL,
                key=FINALS_SCOPE_KEY,
                fully_resolved=total > 0 and resolved == total,
                round_ids=list(FINALS_ROUND_IDS),
            )
        )
    return options
```

(`r32` ahora cae en la rama genérica con `key="r32:_"` y `label="Dieciseisavos"`; el orden cronológico del query `order_by("min_kickoff")` lo coloca tras los grupos y antes de «Fases Finales», que se anexa al final.)

- [ ] **Step 5: Ejecutar los tests para verlos pasar**

Run: `$PY -m pytest stats/tests/test_matchday_options.py stats/tests/test_rankings_view.py -q`
Expected: PASS (todos).

- [ ] **Step 6: Commit**

```bash
git add stats/services/matchday_options.py stats/tests/test_matchday_options.py stats/tests/test_rankings_view.py
git commit -m "feat(stats): selector de Rankings con Dieciseisavos + Fases Finales separadas"
```

---

## Task 6: Copys de UI y documentación

Actualiza textos «4 → 5 jornadas», las opciones del previsualizador del gestor y el modelo de datos. Sin lógica nueva; verificación por render y revisión.

**Files:**
- Modify: `templates/pot/prizes_settings.html`
- Modify: `templates/core/rules.html`
- Modify: `docs/DATA_MODEL.md`

- [ ] **Step 1: `templates/pot/prizes_settings.html` — opciones del previsualizador**

Reemplaza la línea `<option value="ko">Jornada eliminatoria</option>` (línea 194) por:

```html
          <option value="r32">Jornada de dieciseisavos</option>
          <option value="finals">Jornada de fases finales</option>
```

- [ ] **Step 2: `templates/pot/prizes_settings.html` — copy de la tarjeta «Por jornada»**

Reemplaza el `<p>` de las líneas 66-73 por:

```html
        <p style="color:var(--text-dim);margin:0;font-size:13px">
          Hay <strong>5 jornadas</strong> en total y cada una entrega este premio al jugador
          con más puntos en ella. Las tres primeras son las de la fase de grupos (1ª, 2ª y 3ª).
          La cuarta es <strong>Dieciseisavos</strong> (la ronda R32). La quinta es
          <strong>Fases Finales</strong>: octavos, cuartos, semifinales <strong>y la Final</strong>
          cuentan todos juntos como una sola jornada. La Final no entrega premio aparte (su
          ganador cobra a través del podio), pero sus puntos sí suman para decidir al ganador
          de la jornada de Fases Finales.
        </p>
```

- [ ] **Step 3: `templates/core/rules.html` — copy del premio por jornada**

Reemplaza el `<p>` de las líneas 220-227 por:

```html
        <p>
          Hay 5 jornadas en total y cada una entrega este premio al jugador con más
          puntos en ella. Las tres primeras son las de la fase de grupos (1ª, 2ª y 3ª).
          La cuarta es Dieciseisavos (la ronda R32). La quinta es Fases Finales:
          octavos, cuartos, semifinales y la Final cuentan todos juntos como una sola
          jornada. La Final no entrega premio aparte (su ganador cobra como campeón del
          Mundial en el podio), pero sus puntos sí suman para decidir al ganador de la
          jornada de Fases Finales.
        </p>
```

- [ ] **Step 4: `docs/DATA_MODEL.md` — actualizar descripciones de jornadas/premios**

Reemplaza la fila `matchdayWinnerPrize` (línea 79) por:

```markdown
| `matchdayWinnerPrize` | Decimal | importe único que cobra el ganador de cada jornada. Hay **5 jornadas**: las 3 de la fase de grupos (1ª, 2ª, 3ª), **Dieciseisavos** (solo r32) y **Fases Finales** (r16+qf+sf+final). La Final no entrega premio aparte pero sus puntos sí suman al scope Fases Finales |
```

Reemplaza el bloque de las líneas 86-91 por:

```markdown
> El modelo `Prize` solo se usa para el podio final (top 3). Las filas con scope `matchday` o `round` quedaron retiradas en favor de `matchdayWinnerPrize` en PotSettings — un único importe para todas las jornadas.

> **Premio por ganador de jornada.** Hay **5 jornadas** en total. El importe `matchdayWinnerPrize` se entrega:
> - **3 veces durante la fase de grupos** (una por cada jornada: 1ª, 2ª, 3ª) — al jugador con más puntos en esa jornada.
> - **1 vez al cerrarse Dieciseisavos** (jornada `r32`) — al jugador con más puntos sumando solo los partidos de R32. El cálculo usa `standings(round_id="r32")`.
> - **1 vez al cierre del torneo** como premio de la jornada **Fases Finales**, que agrega los puntos de r16+qf+sf+final **incluida la Final**. El cálculo usa `standings(round_ids=["r16","qf","sf","final"])`.
> - **La Final NO genera premio de jornada propio**: su ganador cobra a través del podio (P1), pero sus puntos sí cuentan para la jornada Fases Finales.
```

En la línea 158, reemplaza el inciso sobre la jornada eliminatoria por:

```markdown
El premio por ganador de jornada (las tres de grupos, Dieciseisavos que agrega los 16 partidos de R32, y Fases Finales que agrega los 15 partidos r16+qf+sf+final incluida la Final) se decide aplicando las mismas reglas dentro del scope; si tras las tres siguen empatados, los empatados se reparten el importe a partes iguales.
```

- [ ] **Step 5: Verificar render del previsualizador (smoke)**

Run:

```bash
$PY -m pytest pot/tests -q -k "prizes_settings or settings_view or prizes_view" 2>/dev/null; \
$PY -c "import django,os; os.environ.setdefault('DJANGO_SETTINGS_MODULE','porra26.settings.test'); django.setup(); from django.template.loader import get_template; get_template('pot/prizes_settings.html'); get_template('core/rules.html'); print('templates parse OK')"
```

Expected: "templates parse OK" (y, si existen tests de la vista de premios, que pasen). Comprueba visualmente que ya no queda ningún `value="ko"` ni «4 jornadas`:

```bash
grep -rn "value=\"ko\"\|4 jornadas\|Jornada eliminatoria" templates/ docs/DATA_MODEL.md || echo "sin referencias antiguas"
```

Expected: "sin referencias antiguas".

- [ ] **Step 6: Commit**

```bash
git add templates/pot/prizes_settings.html templates/core/rules.html docs/DATA_MODEL.md
git commit -m "docs(ui): copys de 5 jornadas y previsualizador con r32 + finals"
```

---

## Task 7: Verificación global, lint y cierre

**Files:** ninguno nuevo.

- [ ] **Step 1: Suite completa de las apps afectadas**

Run: `$PY -m pytest announcements pot stats competition -q`
Expected: PASS, 0 failures (debería superar el baseline de 636 al añadir tests nuevos).

- [ ] **Step 2: Suite completa del proyecto**

Run: `$PY -m pytest -q`
Expected: PASS, 0 failures. Si algún test fuera de las apps afectadas referencia `"ko"` / `ko:_`, actualízalo siguiendo los mismos patrones (scope `finals`, key `finals:_`) y vuelve a ejecutar.

- [ ] **Step 3: Migraciones íntegras**

Run: `$PY manage.py makemigrations --check --dry-run`
Expected: "No changes detected".

- [ ] **Step 4: Lint**

Run: `$PY -m ruff check announcements pot stats`
Expected: "All checks passed!" (o sin errores). Corrige lo que aparezca y reejecuta.

- [ ] **Step 5: Búsqueda final de residuos de `"ko"`**

Run:

```bash
grep -rn "scope_kind=\"ko\"\|(\"ko\"\|'ko'\|ko:_\|KO_SCOPE\|_KO_ROUND_IDS\|eliminatoria" \
  announcements pot stats competition templates docs/DATA_MODEL.md --include="*.py" --include="*.html" --include="*.md" \
  | grep -v "docs/superpowers/plans" || echo "limpio"
```

Expected: "limpio" (las referencias en `docs/superpowers/plans/` antiguos son histórico y no se tocan).

- [ ] **Step 6: Commit final si hubo ajustes**

```bash
git add -A && git commit -m "chore: ajustes finales del split de jornada KO" || echo "nada que commitear"
```

---

## Notas de cierre

- Tras completar las tareas, usar `superpowers:finishing-a-development-branch` para abrir PR contra `main` (flujo del proyecto: worktree → PR → merge → CI verde). Railway despliega desde `main`.
- Recordatorio de memoria de proyecto: la página de Reglas debe quedar sincronizada — ya cubierto en Task 6.
