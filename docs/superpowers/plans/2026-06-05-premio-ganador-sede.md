# Premio al ganador final por sede — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un premio simbólico al mejor jugador de cada sede al cierre del Mundial, mostrarlo en reglas y comunicarlo con una modal "Ganadores por sede" que excluye a los del podio global.

**Architecture:** Nuevo `sede_winner_prize` en `PotSettings`. Nuevo `scope_kind="sede"` en `WinnerAnnouncement` (un único anuncio para las 6 sedes). Servicio `sede_winners()` que filtra `standings()` por sede excluyendo top 3 global. Template `_winner_modal.html` bifurcado por scope: podio 2·1·3 (existente) vs grid de 6 sedes (nuevo).

**Tech Stack:** Django, plantillas server-side, pytest, ruff. Reutiliza `announcements/`, `pot/services/prizes.py`, `competition/services/standings.py`.

---

## File Structure

**Create:**
- `pot/migrations/0007_potsettings_sede_winner_prize.py`
- `announcements/migrations/0003_winnerannouncement_sede_scope.py`
- `pot/tests/test_sede_winners.py`
- `announcements/tests/test_sede_announcement.py`

**Modify:**
- `pot/models.py` — añadir campo
- `pot/services/prizes.py` — añadir `SedeWinner` y `sede_winners()`
- `announcements/models.py` — añadir choice y constraint, extender `title`
- `announcements/services.py` — extender `_try_create` y `detect_after_match`
- `announcements/preview.py` — `build_preview_sede`
- `announcements/views.py` — `AnnouncementModalView` y `AnnouncementPreviewView` para sede
- `templates/announcements/_winner_modal.html` — bifurcación
- `static/css/styles.css` — `.winner-modal-sede-*`
- `pot/views.py:PrizesSettingsView` — parsear nuevo campo
- `templates/pot/prizes_settings.html` — input + option en preview select
- `pot/tests/test_pot_settings.py` — tests del campo
- `pot/tests/test_prizes_settings_view.py` — test del POST
- `announcements/tests/test_views.py` — tests render modal sede + preview
- `core/views.py:RulesView` — contexto
- `templates/core/rules.html` — bloque y desempate
- `core/tests/test_rules_view.py` — tests del bloque
- `docs/DATA_MODEL.md` — documentar campo y regla

---

### Task 1: Migración + modelo `PotSettings.sede_winner_prize`

**Files:**
- Modify: `pot/models.py`
- Create: `pot/migrations/0007_potsettings_sede_winner_prize.py`
- Modify: `pot/tests/test_pot_settings.py`

- [ ] **Step 1.1: Escribir test fallido**

En `pot/tests/test_pot_settings.py`, añadir al final:

```python
def test_potsettings_has_sede_winner_prize_default_zero(db):
    from decimal import Decimal
    from pot.models import PotSettings
    s = PotSettings.load()
    assert s.sede_winner_prize == Decimal("0")

def test_potsettings_sede_winner_prize_persists(db):
    from decimal import Decimal
    from pot.models import PotSettings
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("25.50")
    s.save(update_fields=["sede_winner_prize"])
    assert PotSettings.load().sede_winner_prize == Decimal("25.50")
```

- [ ] **Step 1.2: Verificar que fallan**

Run: `pytest pot/tests/test_pot_settings.py -k sede_winner_prize -v`
Expected: FAIL con `AttributeError` o `FieldError`.

- [ ] **Step 1.3: Añadir el campo al modelo**

En `pot/models.py`, dentro de `class PotSettings`, justo después de `maintenance_cost`:

```python
    maintenance_cost = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    sede_winner_prize = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0")
    )
```

- [ ] **Step 1.4: Generar migración**

Run: `python manage.py makemigrations pot --name potsettings_sede_winner_prize`

Esperado: archivo `pot/migrations/0007_potsettings_sede_winner_prize.py` con un `AddField` simple.

- [ ] **Step 1.5: Verificar que pasan los tests**

Run: `pytest pot/tests/test_pot_settings.py -v`
Expected: PASS

- [ ] **Step 1.6: Commit**

```bash
git add pot/models.py pot/migrations/0007_potsettings_sede_winner_prize.py pot/tests/test_pot_settings.py
git commit -m "feat(pot): añade sede_winner_prize a PotSettings"
```

---

### Task 2: Nuevo scope `sede` en `WinnerAnnouncement`

**Files:**
- Modify: `announcements/models.py`
- Create: `announcements/migrations/0003_winnerannouncement_sede_scope.py`
- Modify: `announcements/tests/test_models.py` (crear si no existe)

- [ ] **Step 2.1: Escribir test fallido del título y constraint**

Si no existe `announcements/tests/test_models.py`, crearlo. Añadir:

```python
import pytest
from django.db import IntegrityError
from announcements.models import WinnerAnnouncement


@pytest.mark.django_db
def test_sede_scope_title():
    ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
    assert ann.title == "¡Ganadores por sede!"


@pytest.mark.django_db
def test_sede_scope_unique():
    WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
    with pytest.raises(IntegrityError):
        WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
```

- [ ] **Step 2.2: Verificar que fallan**

Run: `pytest announcements/tests/test_models.py -v`
Expected: FAIL — `'sede'` no es un valor válido de choices.

- [ ] **Step 2.3: Añadir choice, constraint y title**

En `announcements/models.py`:

```python
class WinnerAnnouncement(models.Model):
    SCOPE_CHOICES = [
        ("matchday", "Jornada de grupos"),
        ("round", "Ronda KO"),
        ("global", "Campeón del Mundial"),
        ("sede", "Ganadores por sede"),
    ]
```

En la lista `constraints`, añadir:

```python
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="sede"),
                name="uniq_ann_sede",
            ),
```

En el método `title`, añadir antes del `return` global:

```python
        if self.scope_kind == "sede":
            return "¡Ganadores por sede!"
```

- [ ] **Step 2.4: Generar migración**

Run: `python manage.py makemigrations announcements --name winnerannouncement_sede_scope`

Esperado: archivo `announcements/migrations/0003_winnerannouncement_sede_scope.py` con `AlterField` (choices) y `AddConstraint`.

- [ ] **Step 2.5: Verificar tests**

Run: `pytest announcements/tests/test_models.py -v`
Expected: PASS

- [ ] **Step 2.6: Commit**

```bash
git add announcements/models.py announcements/migrations/0003_winnerannouncement_sede_scope.py announcements/tests/test_models.py
git commit -m "feat(announcements): añade scope sede con UniqueConstraint"
```

---

### Task 3: Servicio `sede_winners()` con exclusión del top 3 global

**Files:**
- Modify: `pot/services/prizes.py`
- Create: `pot/tests/test_sede_winners.py`

- [ ] **Step 3.1: Escribir todos los tests TDD del servicio**

Crear `pot/tests/test_sede_winners.py`:

```python
from decimal import Decimal

import pytest

from accounts.tests.factories import UserFactory
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from pot.models import PotSettings
from pot.services.prizes import sede_winners


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.fixture
def prize_25(db):
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("25.00")
    s.save(update_fields=["sede_winner_prize"])
    return s


def _by_sede(result, key):
    return next(sw for sw in result if sw.sede_key == key)


@pytest.mark.django_db
def test_returns_six_entries_in_sede_choices_order(groups_round, prize_25):
    result = sede_winners()
    assert [sw.sede_key for sw in result] == [
        "ourense", "vigo", "asturias", "madrid", "barcelona", "latam",
    ]
    assert all(sw.status == "desierto" for sw in result)


@pytest.mark.django_db
def test_basic_two_sedes_with_clear_winners(groups_round, prize_25):
    madrid_a = UserFactory(name="MA", sede="madrid")
    vigo_a = UserFactory(name="VA", sede="vigo")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=madrid_a, match=m, earned=3)
    PredictionFactory(player=vigo_a, match=m, earned=3)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    vigo = _by_sede(result, "vigo")
    # Empate global → ambos están en top 3 → ambas sedes desiertas
    assert madrid.status == "desierto"
    assert vigo.status == "desierto"


@pytest.mark.django_db
def test_excludes_global_top3(groups_round, prize_25):
    # Ana lidera global y es de Madrid; Borja (Madrid) tiene menos pts
    # Resultado esperado: Madrid premia a Borja
    ana = UserFactory(name="Ana", sede="madrid")
    borja = UserFactory(name="Borja", sede="madrid")
    # 4 jugadores extra para llenar el top 3 global con gente que NO es Borja
    UserFactory(name="X1", sede="vigo")
    UserFactory(name="X2", sede="vigo")
    UserFactory(name="X3", sede="vigo")
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
    PredictionFactory(player=ana, match=m1, earned=3)
    PredictionFactory(player=ana, match=m2, earned=3)  # 6 pts global #1
    # Construir 2º y 3º global SIN que sean Borja
    p2 = UserFactory(name="P2", sede="barcelona")
    p3 = UserFactory(name="P3", sede="ourense")
    PredictionFactory(player=p2, match=m1, earned=3)
    PredictionFactory(player=p2, match=m2, earned=1)  # 4 pts global #2
    PredictionFactory(player=p3, match=m1, earned=3)  # 3 pts global #3
    PredictionFactory(player=borja, match=m1, earned=1)  # 1 pt
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "resolved"
    assert [u.id for u in madrid.users] == [borja.id]
    assert madrid.prize_per_user == Decimal("25.00")


@pytest.mark.django_db
def test_sede_with_all_players_in_global_top3(groups_round, prize_25):
    # Solo 3 jugadores con pts, todos de Madrid → Madrid desierta
    a = UserFactory(name="A", sede="madrid")
    b = UserFactory(name="B", sede="madrid")
    c = UserFactory(name="C", sede="madrid")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=a, match=m, earned=3)
    PredictionFactory(player=b, match=m, earned=2)
    PredictionFactory(player=c, match=m, earned=1)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "desierto"


@pytest.mark.django_db
def test_tied_inside_sede(groups_round, prize_25):
    # Cuatro jugadores. Top 3 global son tres de vigo. Dos de madrid empatados.
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    m_b = UserFactory(name="MB", sede="madrid")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=m, earned=5)
    PredictionFactory(player=v2, match=m, earned=4)
    PredictionFactory(player=v3, match=m, earned=3)
    # Empate Madrid 1 pt + sin exactos + sin aciertos extra → quedan empatados
    PredictionFactory(player=m_a, match=m, home=9, away=9, earned=1)
    PredictionFactory(player=m_b, match=m, home=9, away=9, earned=1)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "resolved"
    assert {u.id for u in madrid.users} == {m_a.id, m_b.id}
    assert madrid.prize_per_user == Decimal("12.50")  # 25 / 2


@pytest.mark.django_db
def test_user_without_sede_ignored(groups_round, prize_25):
    nohome = UserFactory(name="Nadie", sede="")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=nohome, match=m, earned=3)
    result = sede_winners()
    assert all(sw.status == "desierto" for sw in result)


@pytest.mark.django_db
def test_sede_with_no_points_returns_desierto(groups_round, prize_25):
    UserFactory(name="X", sede="madrid")
    MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    result = sede_winners()
    assert _by_sede(result, "madrid").status == "desierto"


@pytest.mark.django_db
def test_prize_zero_when_setting_zero(groups_round):
    # Sin tocar PotSettings → sede_winner_prize por defecto = 0
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=m, earned=5)
    PredictionFactory(player=v2, match=m, earned=4)
    PredictionFactory(player=v3, match=m, earned=3)
    PredictionFactory(player=m_a, match=m, earned=1)
    result = sede_winners()
    madrid = _by_sede(result, "madrid")
    assert madrid.status == "resolved"
    assert [u.id for u in madrid.users] == [m_a.id]
    assert madrid.prize_per_user == Decimal("0")
```

- [ ] **Step 3.2: Verificar que fallan**

Run: `pytest pot/tests/test_sede_winners.py -v`
Expected: FAIL con `ImportError` para `sede_winners`.

- [ ] **Step 3.3: Implementar `SedeWinner` y `sede_winners()`**

En `pot/services/prizes.py`, añadir tras `PodiumEntry`:

```python
@dataclass
class SedeWinner:
    sede_key: str
    sede_label: str
    users: list = field(default_factory=list)
    points: int = 0
    prize_per_user: Decimal = Decimal("0")
    status: str = "desierto"  # "resolved" | "desierto"
```

Al final del archivo:

```python
def sede_winners() -> list[SedeWinner]:
    """Ganadores por sede al cierre del torneo, excluyendo a los jugadores
    que ya están en el top 3 global. Devuelve un SedeWinner por cada sede
    de User.SEDE_CHOICES en su orden."""
    from accounts.models import User
    from pot.models import PotSettings

    rows = standings()
    top3_global_ids = {
        r.player_id for r in rows if r.position in (1, 2, 3) and r.pts > 0
    }
    eligible = [r for r in rows if r.pts > 0 and r.player_id not in top3_global_ids]
    users_by_id = User.objects.in_bulk([r.player_id for r in eligible])

    sede_prize = PotSettings.load().sede_winner_prize

    result: list[SedeWinner] = []
    for sede_key, sede_label in User.SEDE_CHOICES:
        sede_rows = [
            r for r in eligible
            if users_by_id.get(r.player_id) and users_by_id[r.player_id].sede == sede_key
        ]
        if not sede_rows:
            result.append(SedeWinner(sede_key=sede_key, sede_label=sede_label))
            continue
        min_pos = min(r.position for r in sede_rows)
        winners_rows = [r for r in sede_rows if r.position == min_pos]
        winners_users = [users_by_id[r.player_id] for r in winners_rows]
        n = len(winners_users)
        result.append(SedeWinner(
            sede_key=sede_key,
            sede_label=sede_label,
            users=winners_users,
            points=int(winners_rows[0].pts),
            prize_per_user=(sede_prize / n) if n else Decimal("0"),
            status="resolved",
        ))
    return result
```

> El import de `standings` ya existe arriba del archivo (`from competition.services.standings import standings`).

- [ ] **Step 3.4: Verificar que pasan**

Run: `pytest pot/tests/test_sede_winners.py -v`
Expected: PASS los 8 tests.

- [ ] **Step 3.5: Commit**

```bash
git add pot/services/prizes.py pot/tests/test_sede_winners.py
git commit -m "feat(prizes): servicio sede_winners() con exclusion top 3 global"
```

---

### Task 4: `detect_after_match` crea anuncio `sede` tras la Final

**Files:**
- Modify: `announcements/services.py`
- Create: `announcements/tests/test_sede_announcement.py`

- [ ] **Step 4.1: Escribir tests fallidos**

Crear `announcements/tests/test_sede_announcement.py`:

```python
import pytest

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement
from announcements.services import detect_after_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Grupos", short="GRP", order=1)


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.mark.django_db
def test_sede_announcement_created_after_final(groups_round, final_round):
    # Top 3 global: 3 jugadores de vigo. Ganador de madrid: m_a.
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=g_m, earned=5)
    PredictionFactory(player=v2, match=g_m, earned=4)
    PredictionFactory(player=v3, match=g_m, earned=3)
    PredictionFactory(player=m_a, match=g_m, earned=1)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=final_match, earned=20)
    created = detect_after_match(final_match)
    kinds = [a.scope_kind for a in created]
    assert "global" in kinds
    assert "sede" in kinds
    ann = WinnerAnnouncement.objects.get(scope_kind="sede")
    assert ann.points == 0
    assert ann.tied is False
    assert m_a in ann.winners.all()


@pytest.mark.django_db
def test_sede_announcement_idempotent(groups_round, final_round):
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=g_m, earned=5)
    PredictionFactory(player=v2, match=g_m, earned=4)
    PredictionFactory(player=v3, match=g_m, earned=3)
    PredictionFactory(player=m_a, match=g_m, earned=1)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=final_match, earned=20)
    detect_after_match(final_match)
    detect_after_match(final_match)  # segunda llamada
    assert WinnerAnnouncement.objects.filter(scope_kind="sede").count() == 1


@pytest.mark.django_db
def test_sede_announcement_not_created_when_all_desierto(groups_round, final_round):
    # Solo 1 jugador con pts → está en top 3 global → todas las sedes desiertas
    a = UserFactory(name="A", sede="madrid")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=a, match=g_m, earned=3)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=a, match=final_match, earned=20)
    detect_after_match(final_match)
    assert not WinnerAnnouncement.objects.filter(scope_kind="sede").exists()


@pytest.mark.django_db
def test_sede_announcement_winners_m2m_union(groups_round, final_round):
    # Dos sedes resueltas con un ganador distinto cada una
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    b_a = UserFactory(name="BA", sede="barcelona")
    g_m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=g_m, earned=5)
    PredictionFactory(player=v2, match=g_m, earned=4)
    PredictionFactory(player=v3, match=g_m, earned=3)
    PredictionFactory(player=m_a, match=g_m, earned=2)
    PredictionFactory(player=b_a, match=g_m, earned=1)
    final_match = MatchFactory(round=final_round, matchday=None, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=final_match, earned=20)
    detect_after_match(final_match)
    ann = WinnerAnnouncement.objects.get(scope_kind="sede")
    assert {u.id for u in ann.winners.all()} == {m_a.id, b_a.id}
```

- [ ] **Step 4.2: Verificar que fallan**

Run: `pytest announcements/tests/test_sede_announcement.py -v`
Expected: FAIL — no se crea ningún anuncio scope=sede.

- [ ] **Step 4.3: Extender `detect_after_match` y `_try_create`**

En `announcements/services.py`, reemplazar el bloque `if match.round_id == "final":` así:

```python
        if match.round_id == "final":
            ann_global = _try_create("global")
            if ann_global is not None:
                created.append(ann_global)
            ann_sede = _try_create("sede")
            if ann_sede is not None:
                created.append(ann_sede)
```

Reemplazar la función `_try_create` por:

```python
def _try_create(
    scope_kind: str,
    *,
    matchday: int | None = None,
    round_id: str | None = None,
) -> WinnerAnnouncement | None:
    if scope_kind == "matchday":
        filter_kwargs = {"scope_kind": "matchday", "scope_matchday": matchday}
    elif scope_kind == "round":
        filter_kwargs = {"scope_kind": "round", "scope_round_id": round_id}
    elif scope_kind == "global":
        filter_kwargs = {"scope_kind": "global"}
    elif scope_kind == "sede":
        filter_kwargs = {"scope_kind": "sede"}
    else:
        raise ValueError(scope_kind)

    if WinnerAnnouncement.objects.filter(**filter_kwargs).exists():
        return None

    if scope_kind == "sede":
        from decimal import Decimal

        from pot.services.prizes import sede_winners

        sede_results = sede_winners()
        winners_users = [u for sw in sede_results if sw.status == "resolved" for u in sw.users]
        if not winners_users:
            return None
        ann = WinnerAnnouncement.objects.create(
            scope_kind="sede",
            scope_matchday=None,
            scope_round_id=None,
            points=0,
            tied=False,
            share=Decimal("0"),
        )
        ann.winners.set(winners_users)
        return ann

    scope_key = (scope_kind, matchday if scope_kind == "matchday" else round_id if scope_kind == "round" else None)
    result = matchday_winners(scope_key)
    if result.status != "resolved":
        return None

    ann = WinnerAnnouncement.objects.create(
        scope_kind=scope_kind,
        scope_matchday=matchday,
        scope_round_id=round_id,
        points=result.points,
        tied=result.tied,
        share=result.share,
    )
    if result.winners:
        ann.winners.set(result.winners)
    return ann
```

- [ ] **Step 4.4: Verificar tests**

Run: `pytest announcements/tests/test_sede_announcement.py announcements/tests/test_services.py -v`
Expected: PASS (los 4 nuevos + los anteriores siguen pasando).

- [ ] **Step 4.5: Commit**

```bash
git add announcements/services.py announcements/tests/test_sede_announcement.py
git commit -m "feat(announcements): crea anuncio sede tras la Final"
```

---

### Task 5: Bifurcación de `_winner_modal.html` para scope=sede

**Files:**
- Modify: `templates/announcements/_winner_modal.html`

- [ ] **Step 5.1: Reescribir el cuerpo de la modal bifurcado**

Reemplazar todo el contenido de `templates/announcements/_winner_modal.html` por:

```django
<section class="glass pop winner-modal winner-modal--{{ announcement.scope_kind }}"
         role="dialog" aria-modal="true" aria-labelledby="winner-title"
         {% if preview %}
           data-preview="1"
         {% else %}
           data-announcement-id="{{ announcement.id }}"
           data-seen-url="{% url 'announcements:seen' announcement.id %}"
         {% endif %}>
  {% if preview %}<span class="winner-preview-badge">Vista previa</span>{% endif %}
  <button type="button" class="modal-x" data-modal-close aria-label="Cerrar">×</button>
  <div class="winner-trophy" aria-hidden="true">🏆</div>
  <h2 id="winner-title" class="winner-title">{{ announcement.title }}</h2>

  {% if announcement.scope_kind == "sede" %}
    <p class="winner-subtitle">Los mejores de cada sede del Mundial 2026.</p>
    <div class="winner-modal-sede-grid" role="list">
      {% for sw in sede_winners %}
        <div class="winner-modal-sede-card{% if sw.status == 'desierto' %} is-empty{% endif %}" role="listitem" data-sede="{{ sw.sede_key }}">
          <span class="winner-modal-sede-label">{{ sw.sede_label }}</span>
          {% if sw.status == "resolved" %}
            <div class="winner-modal-sede-medal" aria-hidden="true">🥇</div>
            <div class="winner-modal-sede-avatars{% if sw.users|length > 1 %} is-tied{% endif %}">
              {% for u in sw.users|slice:":2" %}
                {% include "partials/_avatar.html" with u=u size=44 %}
              {% endfor %}
              {% if sw.users|length > 2 %}
                <span class="winner-modal-sede-more" aria-label="{{ sw.users|length|add:'-2' }} más">+{{ sw.users|length|add:"-2" }}</span>
              {% endif %}
            </div>
            <div class="winner-modal-sede-name" title="{% for u in sw.users %}{{ u.name }}{% if not forloop.last %}, {% endif %}{% endfor %}">
              {% if sw.users|length > 1 %}{{ sw.users|length }} jugadores{% else %}{{ sw.users.0.name }}{% endif %}
            </div>
            {% if sw.prize_per_user > 0 %}
              <div class="winner-modal-sede-prize">
                <span class="winner-prize-amount mono">{{ sw.prize_per_user|floatformat:2 }}</span>
                {% if sw.users|length > 1 %}<span class="winner-prize-note">a cada uno</span>{% endif %}
              </div>
            {% endif %}
          {% else %}
            <div class="winner-modal-sede-empty">Desierto</div>
          {% endif %}
        </div>
      {% endfor %}
    </div>
    <p class="winner-subtitle">¡Enhorabuena a todas las sedes!</p>
  {% else %}
    <p class="winner-points">{{ announcement.points }} puntos</p>

    <div class="winner-modal-podium" role="list">
      {# Orden visual: 2º · 1º · 3º (la cima en el centro) #}
      {% for rank, entry in podium_visual %}
        <div class="winner-modal-podium-slot winner-modal-podium-slot--{{ rank }}{% if not entry %} is-empty{% endif %}"
             data-rank="{{ rank }}" role="listitem">
          {% if entry %}
            <div class="winner-modal-podium-medal" aria-hidden="true">
              {% if rank == 1 %}🥇{% elif rank == 2 %}🥈{% else %}🥉{% endif %}
            </div>
            <div class="winner-modal-podium-avatars{% if entry.users|length > 1 %} is-tied{% endif %}">
              {% for u in entry.users|slice:":2" %}
                {% include "partials/_avatar.html" with u=u size=52 %}
              {% endfor %}
              {% if entry.users|length > 2 %}
                <span class="winner-modal-podium-more" aria-label="{{ entry.users|length|add:'-2' }} más">+{{ entry.users|length|add:"-2" }}</span>
              {% endif %}
            </div>
            <div class="winner-modal-podium-name" title="{% for u in entry.users %}{{ u.name }}{% if not forloop.last %}, {% endif %}{% endfor %}">
              {% if entry.users|length > 1 %}
                {{ entry.users|length }} jugadores
              {% else %}
                {{ entry.users.0.name }}
              {% endif %}
            </div>
            {% if entry.prize_per_user > 0 %}
              <div class="winner-modal-podium-prize" aria-label="Premio: {{ entry.prize_per_user|floatformat:2 }} €">
                <span class="winner-prize-amount mono">{{ entry.prize_per_user|floatformat:2 }}</span>
                {% if entry.tied %}<span class="winner-prize-note">a cada uno</span>{% endif %}
              </div>
            {% endif %}
          {% endif %}
          <div class="winner-modal-podium-pedestal">
            <span class="winner-modal-podium-rank">{{ rank }}</span>
          </div>
        </div>
      {% endfor %}
    </div>

    <p class="winner-subtitle">
      {% if announcement.tied %}Empate en la cima. ¡Bien jugado!{% else %}¡Enhorabuena!{% endif %}
    </p>
  {% endif %}

  <div class="winner-actions">
    {% if preview %}
      <button type="button" class="btn btn-primary" data-modal-close>Cerrar vista previa</button>
    {% else %}
      <button type="button" class="btn btn-primary" data-winner-confirm>¡Felicidades!</button>
    {% endif %}
  </div>
</section>
```

> Importante: el podio actual queda intacto (mismas clases CSS), solo se envuelve en `{% else %}`.

- [ ] **Step 5.2: Commit**

```bash
git add templates/announcements/_winner_modal.html
git commit -m "feat(winner-modal): bifurca template por scope=sede"
```

---

### Task 6: CSS `.winner-modal-sede-*`

**Files:**
- Modify: `static/css/styles.css`

- [ ] **Step 6.1: Añadir bloque CSS al final de la sección de winner-modal**

Buscar la última regla `.winner-modal-podium-*` (alrededor de la línea 1980-2010) y añadir inmediatamente después:

```css
/* Grid de "Ganadores por sede" */
.winner-modal-sede-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
  margin: 18px 0 14px;
}
.winner-modal-sede-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 14px 10px 16px;
  border-radius: var(--r-md);
  background: oklch(1 0 0 / 0.05);
  border: 1px solid oklch(1 0 0 / 0.12);
  min-width: 0;
  position: relative;
}
.winner-modal-sede-card.is-empty {
  opacity: 0.55;
  background: oklch(1 0 0 / 0.02);
}
.winner-modal-sede-label {
  font-family: 'Geist Mono', monospace;
  font-size: 10px;
  letter-spacing: 0.14em;
  text-transform: uppercase;
  color: var(--text-faint);
}
.winner-modal-sede-medal {
  font-size: 24px;
  line-height: 1;
  filter: drop-shadow(0 4px 10px var(--c-gold));
}
.winner-modal-sede-avatars {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 4px;
  min-width: 0;
}
.winner-modal-sede-avatars .avatar {
  width: 44px;
  height: 44px;
  font-size: 16px;
  flex: 0 0 auto;
  box-shadow: 0 6px 16px -8px var(--c-gold);
}
.winner-modal-sede-avatars.is-tied .avatar:not(:first-child) {
  margin-left: -12px;
  border: 2px solid var(--surface-solid);
}
.winner-modal-sede-more {
  display: inline-grid;
  place-items: center;
  min-width: 24px;
  height: 24px;
  padding: 0 6px;
  border-radius: 999px;
  background: oklch(1 0 0 / 0.08);
  border: 1px solid oklch(1 0 0 / 0.18);
  color: var(--text-dim);
  font-family: 'Geist Mono', monospace;
  font-size: 10px;
  font-weight: 600;
}
.winner-modal-sede-name {
  font-weight: 700;
  font-size: 12px;
  color: var(--text);
  text-align: center;
  max-width: 100%;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.winner-modal-sede-prize {
  display: inline-flex;
  align-items: baseline;
  gap: 4px;
  padding: 4px 8px;
  border-radius: 999px;
  background: linear-gradient(
    135deg,
    oklch(from var(--c-gold) l c h / 0.28),
    oklch(from var(--c-gold) l c h / 0.06)
  );
  border: 1px solid oklch(from var(--c-gold) l c h / 0.50);
  white-space: nowrap;
}
.winner-modal-sede-prize .winner-prize-amount {
  font-family: 'Sora', system-ui, sans-serif;
  font-weight: 800;
  font-size: 14px;
  color: var(--c-gold);
  line-height: 1;
}
.winner-modal-sede-prize .winner-prize-amount::after {
  content: " €";
  font-size: 0.7em;
  opacity: 0.85;
}
.winner-modal-sede-empty {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  letter-spacing: 0.12em;
  text-transform: uppercase;
  color: var(--text-faint);
  margin-top: 14px;
}
@media (max-width: 640px) {
  .winner-modal-sede-grid { grid-template-columns: repeat(2, 1fr); }
}
@media (max-width: 360px) {
  .winner-modal-sede-grid { grid-template-columns: 1fr; }
}
```

- [ ] **Step 6.2: Commit**

```bash
git add static/css/styles.css
git commit -m "feat(winner-modal): estilos del grid de sedes"
```

---

### Task 7: `AnnouncementModalView` bifurca contexto + tests de render

**Files:**
- Modify: `announcements/views.py`
- Modify: `announcements/tests/test_views.py`

- [ ] **Step 7.1: Escribir tests fallidos**

En `announcements/tests/test_views.py`, añadir al final:

```python
@pytest.mark.django_db
def test_modal_renders_sede_grid(client, settings):
    from decimal import Decimal
    from accounts.tests.factories import UserFactory, GestorFactory
    from announcements.models import WinnerAnnouncement
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings

    gestor = GestorFactory()
    client.force_login(gestor)
    rd = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    v1 = UserFactory(name="V1", sede="vigo")
    v2 = UserFactory(name="V2", sede="vigo")
    v3 = UserFactory(name="V3", sede="vigo")
    m_a = UserFactory(name="MA", sede="madrid")
    m = MatchFactory(round=rd, matchday=1, result_home=1, result_away=0)
    PredictionFactory(player=v1, match=m, earned=5)
    PredictionFactory(player=v2, match=m, earned=4)
    PredictionFactory(player=v3, match=m, earned=3)
    PredictionFactory(player=m_a, match=m, earned=2)
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("25.00")
    s.save(update_fields=["sede_winner_prize"])
    ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
    r = client.get(f"/anuncios/{ann.id}/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "winner-modal-sede-grid" in body
    # Las 6 sedes están presentes
    for key in ["ourense", "vigo", "asturias", "madrid", "barcelona", "latam"]:
        assert f'data-sede="{key}"' in body
    # Madrid resuelta con MA y 25.00 €
    assert "MA" in body
    assert "25.00" in body
    # Sedes desiertas: ourense, vigo, asturias, barcelona, latam → todas con "Desierto" salvo madrid
    assert body.count("Desierto") == 5


@pytest.mark.django_db
def test_modal_sede_card_desierto_state(client):
    from accounts.tests.factories import GestorFactory
    from announcements.models import WinnerAnnouncement

    client.force_login(GestorFactory())
    ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
    r = client.get(f"/anuncios/{ann.id}/")
    body = r.content.decode()
    assert body.count("Desierto") == 6
    assert "is-empty" in body
```

- [ ] **Step 7.2: Verificar que fallan**

Run: `pytest announcements/tests/test_views.py -k "sede" -v`
Expected: FAIL — la vista no bifurca aún por scope=sede; el template fallaría al renderizar.

- [ ] **Step 7.3: Bifurcar `AnnouncementModalView.get()`**

En `announcements/views.py`, reemplazar la clase `AnnouncementModalView` por:

```python
class AnnouncementModalView(LoginRequiredMixin, View):
    def get(self, request, pk):
        ann = get_object_or_404(
            WinnerAnnouncement.objects.prefetch_related("winners").select_related("scope_round"),
            pk=pk,
        )
        if ann.scope_kind == "sede":
            from pot.services.prizes import sede_winners

            return render(
                request,
                "announcements/_winner_modal.html",
                {"announcement": ann, "sede_winners": sede_winners()},
            )
        podium = announcement_podium(ann)
        return render(
            request,
            "announcements/_winner_modal.html",
            {
                "announcement": ann,
                "podium": podium,
                "podium_visual": _podium_visual_order(podium),
            },
        )
```

- [ ] **Step 7.4: Verificar tests**

Run: `pytest announcements/tests/test_views.py -v`
Expected: PASS.

- [ ] **Step 7.5: Commit**

```bash
git add announcements/views.py announcements/tests/test_views.py
git commit -m "feat(announcements): AnnouncementModalView renderiza grid de sedes"
```

---

### Task 8: Preview sede para gestor

**Files:**
- Modify: `announcements/preview.py`
- Modify: `announcements/views.py`
- Modify: `announcements/tests/test_preview.py`

- [ ] **Step 8.1: Tests fallidos**

En `announcements/tests/test_preview.py`, añadir:

```python
@pytest.mark.django_db
def test_preview_sede_for_gestor(client):
    from decimal import Decimal
    from accounts.tests.factories import GestorFactory, UserFactory
    from pot.models import PotSettings

    UserFactory(name="A", sede="madrid")
    UserFactory(name="B", sede="vigo")
    s = PotSettings.load()
    s.sede_winner_prize = Decimal("30.00")
    s.save(update_fields=["sede_winner_prize"])
    client.force_login(GestorFactory(sede="barcelona"))
    r = client.get("/anuncios/preview/?scope=sede")
    assert r.status_code == 200
    body = r.content.decode()
    assert "winner-modal-sede-grid" in body
    assert "Vista previa" in body


@pytest.mark.django_db
def test_preview_sede_forbidden_for_jugador(client):
    from accounts.tests.factories import UserFactory

    client.force_login(UserFactory())
    r = client.get("/anuncios/preview/?scope=sede")
    assert r.status_code in (302, 403)  # GestorRequiredMixin redirige o prohíbe
```

- [ ] **Step 8.2: Verificar que fallan**

Run: `pytest announcements/tests/test_preview.py -k sede -v`
Expected: FAIL.

- [ ] **Step 8.3: Añadir `build_preview_sede`**

En `announcements/preview.py`, añadir al final:

```python
def build_preview_sede(*, current_user) -> tuple[WinnerAnnouncement, list]:
    """Construye un anuncio sintético + grid de SedeWinner para previsualizar
    la modal de sede. Para sedes con al menos un jugador real (excluyendo
    current_user para mostrar también un estado 'resolved' realista), usa
    al primer jugador como ganador. Sedes sin jugadores → estado 'desierto'."""
    from pot.services.prizes import SedeWinner
    from pot.models import PotSettings

    ann = WinnerAnnouncement(scope_kind="sede", points=0)

    sede_prize = PotSettings.load().sede_winner_prize
    sede_winners_preview: list[SedeWinner] = []
    for sede_key, sede_label in User.SEDE_CHOICES:
        first = User.objects.filter(sede=sede_key).order_by("name").first()
        if first is None:
            sede_winners_preview.append(SedeWinner(sede_key=sede_key, sede_label=sede_label))
            continue
        sede_winners_preview.append(SedeWinner(
            sede_key=sede_key,
            sede_label=sede_label,
            users=[first],
            points=0,
            prize_per_user=sede_prize,
            status="resolved",
        ))
    return ann, sede_winners_preview
```

- [ ] **Step 8.4: Extender `AnnouncementPreviewView`**

En `announcements/views.py`, en la clase `AnnouncementPreviewView.get()`, reemplazar el cuerpo por:

```python
    def get(self, request):
        scope = request.GET.get("scope", "matchday")
        if scope == "sede":
            from .preview import build_preview_sede

            ann, sede_winners_preview = build_preview_sede(current_user=request.user)
            return render(
                request,
                "announcements/_winner_modal.html",
                {
                    "announcement": ann,
                    "preview": True,
                    "sede_winners": sede_winners_preview,
                },
            )
        tied = request.GET.get("tied") == "1"
        ann, winners = build_preview(scope, tied=tied, current_user=request.user)
        podium = build_preview_podium(scope, tied=tied, current_user=request.user)
        return render(
            request,
            "announcements/_winner_modal.html",
            {
                "announcement": ann,
                "preview": True,
                "preview_winners": winners,
                "podium": podium,
                "podium_visual": _podium_visual_order(podium),
            },
        )
```

- [ ] **Step 8.5: Verificar tests**

Run: `pytest announcements/tests/test_preview.py -v`
Expected: PASS.

- [ ] **Step 8.6: Commit**

```bash
git add announcements/preview.py announcements/views.py announcements/tests/test_preview.py
git commit -m "feat(announcements): preview de la modal scope=sede para el gestor"
```

---

### Task 9: Pantalla "Premios y puntos" — campo + preview

**Files:**
- Modify: `pot/views.py:PrizesSettingsView`
- Modify: `templates/pot/prizes_settings.html`
- Modify: `pot/tests/test_prizes_settings_view.py`

- [ ] **Step 9.1: Test fallido del POST**

En `pot/tests/test_prizes_settings_view.py`, añadir al final:

```python
@pytest.mark.django_db
def test_post_updates_sede_winner_prize(client, settings):
    from decimal import Decimal
    from accounts.tests.factories import GestorFactory
    from pot.models import PotSettings

    client.force_login(GestorFactory())
    r = client.post(
        "/pot/premios-y-puntos/",
        data={"sede_winner_prize": "40.00"},
    )
    assert r.status_code in (200, 302)
    assert PotSettings.load().sede_winner_prize == Decimal("40.00")


@pytest.mark.django_db
def test_post_rejects_negative_sede_winner_prize(client, settings):
    from decimal import Decimal
    from accounts.tests.factories import GestorFactory
    from pot.models import PotSettings

    s = PotSettings.load()
    s.sede_winner_prize = Decimal("10.00")
    s.save(update_fields=["sede_winner_prize"])
    client.force_login(GestorFactory())
    client.post("/pot/premios-y-puntos/", data={"sede_winner_prize": "-1"})
    # No cambia: queda en 10.00 (mismo trato que matchday_winner_prize)
    assert PotSettings.load().sede_winner_prize == Decimal("10.00")
```

> Si la URL real es distinta a `/pot/premios-y-puntos/`, sustitúyela. Verificar con `python manage.py show_urls | grep -i prize` o leyendo `pot/urls.py`.

- [ ] **Step 9.2: Verificar que fallan**

Run: `pytest pot/tests/test_prizes_settings_view.py -k sede -v`
Expected: FAIL.

- [ ] **Step 9.3: Extender `PrizesSettingsView.post()`**

En `pot/views.py`, dentro de la transacción atómica en `PrizesSettingsView.post`, añadir tras el bloque de `maintenance_cost` (línea ~235):

```python
            sw_raw = request.POST.get("sede_winner_prize")
            sw_value = _parse_decimal(sw_raw)
            if sw_value is not None:
                settings_obj.sede_winner_prize = sw_value
                settings_obj.save(update_fields=["sede_winner_prize"])
```

- [ ] **Step 9.4: Añadir input en el template**

En `templates/pot/prizes_settings.html`, justo después del bloque del input `matchday_winner_prize` (búsquedalo por `id="matchday_winner_prize"`), añadir un nuevo bloque análogo:

```django
      <label class="prizes-matchday-label" for="sede_winner_prize">Premio por ganador de sede</label>
      <div class="prizes-matchday-input">
        <input type="number" min="0" step="0.01"
               id="sede_winner_prize" name="sede_winner_prize"
               value="{{ settings.sede_winner_prize|floatformat:'-2' }}">
        <span class="prizes-matchday-unit">€</span>
      </div>
      <p class="prizes-help">
        Importe que cobra el mejor jugador de cada sede al cierre del Mundial,
        excluyendo a los tres del podio global.
      </p>
```

> Si la estructura visual circundante usa diferentes wrappers (revisa el bloque de `matchday_winner_prize` arriba), replica exactamente esa estructura.

Y en el `<select id="preview-scope">` (línea ~166), añadir tras `global`:

```django
          <option value="sede">Ganadores por sede</option>
```

Adicionalmente, en el script de preview (línea ~196), modificar para que si scope === "sede", omita el parámetro `tied`:

```js
    btn.addEventListener("click", () => {
      const scope = document.getElementById("preview-scope").value;
      const tied = document.getElementById("preview-tied").value;
      const url = scope === "sede"
        ? `{% url 'announcements:preview' %}?scope=sede`
        : `{% url 'announcements:preview' %}?scope=${scope}&tied=${tied}`;
      openModal(url);
    });
```

- [ ] **Step 9.5: Verificar tests**

Run: `pytest pot/tests/test_prizes_settings_view.py -v`
Expected: PASS.

- [ ] **Step 9.6: Commit**

```bash
git add pot/views.py templates/pot/prizes_settings.html pot/tests/test_prizes_settings_view.py
git commit -m "feat(pot): premios y puntos editan sede_winner_prize + preview sede"
```

---

### Task 10: Página de reglas

**Files:**
- Modify: `core/views.py:RulesView`
- Modify: `templates/core/rules.html`
- Modify: `core/tests/test_rules_view.py`

- [ ] **Step 10.1: Tests fallidos**

En `core/tests/test_rules_view.py`, añadir:

```python
@pytest.mark.django_db
def test_rules_shows_sede_prize_block(client):
    from decimal import Decimal
    from accounts.tests.factories import UserFactory
    from pot.models import PotSettings

    s = PotSettings.load()
    s.sede_winner_prize = Decimal("30.00")
    s.save(update_fields=["sede_winner_prize"])
    client.force_login(UserFactory())
    r = client.get("/reglas/")
    body = r.content.decode()
    assert "Premio por ganador de sede" in body
    assert "30,00" in body or "30.00" in body
    assert "no esté en el podio global" in body or "no está en el podio global" in body


@pytest.mark.django_db
def test_rules_hides_sede_prize_block_when_zero(client):
    from accounts.tests.factories import UserFactory
    from pot.models import PotSettings

    s = PotSettings.load()
    s.sede_winner_prize = 0
    s.save(update_fields=["sede_winner_prize"])
    client.force_login(UserFactory())
    r = client.get("/reglas/")
    body = r.content.decode()
    assert "Premio por ganador de sede" not in body
```

> Verifica la URL real de reglas (`grep -rn 'rules' core/urls.py`). Si no es `/reglas/`, sustituye.

- [ ] **Step 10.2: Verificar que fallan**

Run: `pytest core/tests/test_rules_view.py -k sede -v`
Expected: FAIL.

- [ ] **Step 10.3: Extender `RulesView`**

En `core/views.py`:

```python
        ctx["sede_winner_prize"] = pot_settings.sede_winner_prize
```

(añadir en `get_context_data` junto a las otras claves de pot_settings).

- [ ] **Step 10.4: Añadir bloque en el template**

En `templates/core/rules.html`, justo después del bloque `{% if matchday_winner_prize ... %}...{% endif %}` (líneas 217-226), añadir:

```django
    {% if sede_winner_prize and sede_winner_prize > 0 %}
    <div class="rules-matchday-prize">
      <div class="rules-matchday-prize-icon">{% icon "flag" width=22 height=22 aria_hidden="true" %}</div>
      <div class="rules-matchday-prize-body">
        <span class="eyebrow">Premio por ganador de sede</span>
        <strong>{{ sede_winner_prize|floatformat:"-2" }} €</strong>
        <p>
          Al cierre del Mundial, el mejor jugador de cada sede (Ourense, Vigo, Asturias, Madrid,
          Barcelona y Latinoamérica) se lleva este premio. Si alguien ya está entre los tres
          primeros del podio final, el premio de su sede pasa al siguiente mejor de esa sede
          que no esté en el podio global.
        </p>
      </div>
    </div>
    {% endif %}
```

> Si el icono `flag` no existe en el set, usar `trophy` (ya en uso). Comprobar `templates/partials/_icon.html` o donde estén definidos los SVG.

En la sección "04 · Desempate" (línea ~254), extender el último párrafo:

Reemplazar:

```django
      Lo mismo aplica al premio por ganador de jornada/ronda. Solo cuentan los jugadores activos.
```

por:

```django
      Lo mismo aplica al premio por ganador de jornada/ronda y al premio por ganador de sede.
      Solo cuentan los jugadores activos.
```

- [ ] **Step 10.5: Verificar tests**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS.

- [ ] **Step 10.6: Commit**

```bash
git add core/views.py templates/core/rules.html core/tests/test_rules_view.py
git commit -m "feat(reglas): bloque premio por ganador de sede + regla exclusion"
```

---

### Task 11: Documentar en `docs/DATA_MODEL.md`

**Files:**
- Modify: `docs/DATA_MODEL.md`

- [ ] **Step 11.1: Añadir documentación**

Localizar la sección de `PotSettings` y la tabla de premios. Añadir:

- En la lista de campos de `PotSettings`, una fila:
  ```
  | `sede_winner_prize` | Decimal | Importe que cobra el mejor jugador de cada sede al cierre del Mundial. |
  ```
- En la sección de reglas de premios/desempates, un párrafo:

  ```
  **Premio por ganador de sede:** al cierre del Mundial, cada sede premia al mejor de
  sus jugadores **que no esté entre los tres primeros del podio global**. Si todos los
  jugadores con puntos de una sede ya están en el top 3 global, esa sede queda desierta.
  En caso de empate dentro de la sede (tras las tres reglas de desempate), los empatados
  comparten plaza y el premio se divide a partes iguales.
  ```

- [ ] **Step 11.2: Commit**

```bash
git add docs/DATA_MODEL.md
git commit -m "docs(data-model): premio por ganador de sede y regla exclusion"
```

---

### Task 12: Verificación final

**Files:** ninguno (verificación)

- [ ] **Step 12.1: Lint + format**

Run: `ruff check . && ruff format --check .`
Expected: sin errores. Si los hay, corregir y volver a correr.

- [ ] **Step 12.2: Suite completa**

Run: `pytest -q`
Expected: todos los tests verdes (especialmente los nuevos: `test_sede_winners.py`, `test_sede_announcement.py`, además de los de `test_views.py`, `test_preview.py`, `test_rules_view.py`, `test_pot_settings.py`, `test_prizes_settings_view.py`).

- [ ] **Step 12.3: Verificación manual de la modal**

Run: `python manage.py runserver`

Como gestor:
1. Abrir `/pot/premios-y-puntos/` (o la URL real). Poner `sede_winner_prize = 30`.
2. Pulsar el botón de preview con scope = "Ganadores por sede".
3. Verificar visualmente: grid de 6 sedes, tarjetas con avatares para sedes con jugadores, "Desierto" para sedes vacías, importe 30 €.
4. Abrir `/reglas/` y comprobar el bloque "Premio por ganador de sede" con la cifra y el copy de exclusión.

- [ ] **Step 12.4: PR**

```bash
git push -u origin worktree-winner-modal-podio-visual
gh pr create --title "feat: premio al ganador final por sede" --body "$(cat <<'EOF'
## Summary
- Añade `PotSettings.sede_winner_prize` (cifra única, configurable en "Premios y puntos").
- Nuevo `WinnerAnnouncement` scope `sede` que se dispara tras la Final.
- Servicio `sede_winners()` que excluye del cálculo al top 3 del podio global.
- Modal "Ganadores por sede" con grid de 6 sedes (mismo lenguaje visual del podio).
- Bloque en la página de Reglas explicando el premio y la regla de exclusión.

## Test plan
- [ ] Suite verde (`pytest`).
- [ ] Lint verde (`ruff check . && ruff format --check .`).
- [ ] Vista previa de la modal sede como gestor.
- [ ] Página de reglas muestra el bloque con `sede_winner_prize > 0` y lo oculta con `0`.
EOF
)"
```

---

## Self-Review

- **Spec coverage:** los §1-§15 del spec se cubren así: §5.1 → T1; §5.2 + §6.2 (parcial) → T2; §6.1 → T3; §7 → T4; §8.3 + §8.4 → T5; §8.4 (CSS) → T6; §8.1 → T7; §8.2 → T8; §10 → T9; §9 → T10; §11 → T11; §12 → todas las tareas (los tests están repartidos en T1-T10) y la verificación final en T12.
- **Placeholders:** ninguno; cada paso muestra el código exacto.
- **Type consistency:** `SedeWinner` se define una vez en T3 y se importa en T4, T7, T8 con los mismos atributos (`sede_key`, `sede_label`, `users`, `points`, `prize_per_user`, `status`).
- **Migrations numbers:** `pot/0007_*` (siguiente tras `0006_potsettings_maintenance_cost.py`); `announcements/0003_*` (siguiente tras `0002_winnerannouncement_share.py`). Verificado contra `ls` en el contexto inicial.
