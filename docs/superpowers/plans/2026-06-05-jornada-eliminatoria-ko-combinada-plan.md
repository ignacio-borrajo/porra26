# Jornada eliminatoria KO combinada — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Sustituir el scope `round` (un anuncio por ronda KO) por un único scope `ko` (un anuncio cuando termina la Final, agregando r32+r16+qf+sf+final). Resultado: 4 jornadas totales en la porra (3 grupos + 1 KO combinada).

**Architecture:** Modelo `WinnerAnnouncement` cambia: `scope_kind` pasa de `{matchday, round, global, sede}` a `{matchday, ko, global, sede}` y se elimina la FK `scope_round`. Una migración destructiva borra anuncios `round` previos. `competition.services.standings.standings()` recibe un nuevo parámetro `round_ids` para agregar predicciones de múltiples rondas. `announcements.services.detect_after_match` deja de crear anuncios al cerrar r32/r16/qf/sf; al cerrarse la Final crea 3 simultáneos: `ko`, `sede`, `global`.

**Tech Stack:** Django 5, Python 3.12, pytest, ruff (select E F I B UP DJ).

**Spec:** `docs/superpowers/specs/2026-06-05-jornada-eliminatoria-ko-combinada-design.md`

---

## Task 1: standings() acepta round_ids

**Files:**
- Modify: `competition/services/standings.py`
- Test: `competition/tests/test_standings.py`

- [ ] **Step 1.1: Escribir tests**

Añadir al final de `competition/tests/test_standings.py`:

```python
def test_standings_round_ids_aggregates_multiple_rounds():
    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory

    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    user = UserFactory(name="Ana")
    m_grp = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_r32 = MatchFactory(round=r32, matchday=None, result_home=2, result_away=0)
    m_r16 = MatchFactory(round=r16, matchday=None, result_home=1, result_away=1)
    PredictionFactory(player=user, match=m_grp, earned=3)
    PredictionFactory(player=user, match=m_r32, earned=5)
    PredictionFactory(player=user, match=m_r16, earned=7)

    rows = {r.name: r.pts for r in standings(round_ids=["r32", "r16"])}
    assert rows["Ana"] == 12  # 5+7, sin contar grupos


def test_standings_round_id_and_round_ids_are_mutually_exclusive():
    import pytest as _pytest
    with _pytest.raises(ValueError):
        standings(round_id="groups", round_ids=["r32", "r16"])
```

- [ ] **Step 1.2: Ejecutar tests, ver fail**

```bash
pytest competition/tests/test_standings.py::test_standings_round_ids_aggregates_multiple_rounds competition/tests/test_standings.py::test_standings_round_id_and_round_ids_are_mutually_exclusive -v
```

Expected: ambos fallan (uno con `TypeError: unexpected keyword argument 'round_ids'`).

- [ ] **Step 1.3: Implementar**

En `competition/services/standings.py`, modificar la firma y la lógica de filtrado de `standings()`:

```python
def standings(
    round_id: str | None = None,
    matchday: int | None = None,
    player_ids: Iterable[int] | None = None,
    *,
    round_ids: Iterable[str] | None = None,
) -> list[StandingRow]:
    """Clasificación general, opcionalmente acotada por ronda/jornada/subconjunto de jugadores.

    Con `round_id` o `round_ids` (mutuamente excluyentes) o `matchday` solo se
    suman los puntos de las predicciones cuyo partido cae dentro del scope. Para
    esos scopes locales no se calculan `streak` ni `trend`. Con `player_ids`,
    los resultados se limitan a esos jugadores y las posiciones se recalculan
    desde 1.
    """
    if round_id is not None and round_ids is not None:
        raise ValueError("standings(): round_id y round_ids son mutuamente excluyentes")
    if player_ids is not None:
        player_ids = list(player_ids)
        if not player_ids:
            return []

    scoped = round_id is not None or round_ids is not None or matchday is not None
    qs = Prediction.objects.filter(
        player__is_active=True, player__is_jugador=True, earned__isnull=False
    )
    if round_id is not None:
        qs = qs.filter(match__round_id=round_id)
    if round_ids is not None:
        qs = qs.filter(match__round_id__in=list(round_ids))
    if matchday is not None:
        qs = qs.filter(match__matchday=matchday)
    if player_ids is not None:
        qs = qs.filter(player_id__in=player_ids)
    # ... resto sin cambios
```

- [ ] **Step 1.4: Ejecutar tests, ver pass**

```bash
pytest competition/tests/test_standings.py -v
```

Expected: todo verde incluidos los nuevos.

- [ ] **Step 1.5: Commit**

```bash
git add competition/services/standings.py competition/tests/test_standings.py
git commit -m "feat(standings): añade param round_ids para agregar varias rondas"
```

---

## Task 2: Migración y modelo WinnerAnnouncement (scope `ko`, drop scope `round`)

**Files:**
- Modify: `announcements/models.py`
- Create: `announcements/migrations/0004_drop_round_scope_add_ko.py`
- Modify: `announcements/tests/test_models.py`

- [ ] **Step 2.1: Actualizar `announcements/models.py`**

```python
from decimal import Decimal

from django.db import models
from django.db.models import Q, UniqueConstraint


class WinnerAnnouncement(models.Model):
    SCOPE_CHOICES = [
        ("matchday", "Jornada de grupos"),
        ("ko", "Jornada eliminatoria"),
        ("global", "Campeón del Mundial"),
        ("sede", "Ganadores por sede"),
    ]

    scope_kind = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    scope_matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    points = models.PositiveIntegerField()
    tied = models.BooleanField(default=False)
    share = models.DecimalField(max_digits=8, decimal_places=2, default=Decimal("0"))
    winners = models.ManyToManyField(
        "accounts.User",
        related_name="winning_announcements",
        blank=True,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            UniqueConstraint(
                fields=["scope_kind", "scope_matchday"],
                condition=Q(scope_kind="matchday"),
                name="uniq_ann_matchday",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="ko"),
                name="uniq_ann_ko",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="global"),
                name="uniq_ann_global",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="sede"),
                name="uniq_ann_sede",
            ),
        ]

    def __str__(self):
        if self.scope_kind == "matchday":
            return f"Anuncio jornada {self.scope_matchday}"
        if self.scope_kind == "ko":
            return "Anuncio jornada eliminatoria"
        if self.scope_kind == "sede":
            return "Anuncio ganadores por sede"
        return "Anuncio campeón del Mundial"

    @property
    def title(self) -> str:
        if self.scope_kind == "matchday":
            if self.tied:
                return f"¡Ganadores de la Jornada {self.scope_matchday}!"
            return f"¡Ganador de la Jornada {self.scope_matchday}!"
        if self.scope_kind == "ko":
            return "¡Ganadores de las eliminatorias!" if self.tied else "¡Ganador de las eliminatorias!"
        if self.scope_kind == "sede":
            return "¡Ganadores por sede!"
        return "¡Campeones del Mundial!" if self.tied else "¡Campeón del Mundial!"


class WinnerAnnouncementSeen(models.Model):
    announcement = models.ForeignKey(
        WinnerAnnouncement,
        on_delete=models.CASCADE,
        related_name="seen_by",
    )
    user = models.ForeignKey(
        "accounts.User",
        on_delete=models.CASCADE,
        related_name="seen_announcements",
    )
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [UniqueConstraint(fields=["announcement", "user"], name="uniq_seen_per_user")]
        indexes = [models.Index(fields=["user", "announcement"])]

    def __str__(self):
        return f"Seen({self.user_id} → {self.announcement_id})"
```

Nota: el campo `scope_round` queda eliminado.

- [ ] **Step 2.2: Generar la migración con Django**

```bash
python manage.py makemigrations announcements --name drop_round_scope_add_ko
```

- [ ] **Step 2.3: Editar la migración generada**

Abrir `announcements/migrations/0004_drop_round_scope_add_ko.py`. Antes de las operaciones que Django generó (RemoveConstraint + RemoveField + AlterField + AddConstraint), añadir una operación `RunPython` que borre los anuncios `scope_kind="round"`. Resultado esperado:

```python
from django.db import migrations, models
from django.db.models import Q


def delete_round_announcements(apps, schema_editor):
    WinnerAnnouncement = apps.get_model("announcements", "WinnerAnnouncement")
    WinnerAnnouncement.objects.filter(scope_kind="round").delete()


class Migration(migrations.Migration):
    dependencies = [
        ("announcements", "0003_winnerannouncement_sede_scope"),
    ]

    operations = [
        migrations.RunPython(delete_round_announcements, migrations.RunPython.noop),
        migrations.RemoveConstraint(
            model_name="winnerannouncement",
            name="uniq_ann_round",
        ),
        migrations.RemoveField(
            model_name="winnerannouncement",
            name="scope_round",
        ),
        migrations.AlterField(
            model_name="winnerannouncement",
            name="scope_kind",
            field=models.CharField(
                choices=[
                    ("matchday", "Jornada de grupos"),
                    ("ko", "Jornada eliminatoria"),
                    ("global", "Campeón del Mundial"),
                    ("sede", "Ganadores por sede"),
                ],
                max_length=10,
            ),
        ),
        migrations.AddConstraint(
            model_name="winnerannouncement",
            constraint=models.UniqueConstraint(
                condition=Q(scope_kind="ko"),
                fields=("scope_kind",),
                name="uniq_ann_ko",
            ),
        ),
    ]
```

Si Django generó las operaciones en otro orden, reordenar para coincidir.

- [ ] **Step 2.4: Reescribir `announcements/tests/test_models.py` completo**

Sobrescribe el archivo con:

```python
import pytest
from django.db import IntegrityError

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen


@pytest.mark.django_db
class TestWinnerAnnouncementStr:
    def test_str_for_matchday(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=9)
        assert "2" in str(ann)

    def test_str_for_ko(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="ko", points=42)
        assert "eliminatoria" in str(ann)

    def test_str_for_global(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=50)
        assert "Mundial" in str(ann)

    def test_str_for_sede(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
        assert "sede" in str(ann).lower()


@pytest.mark.django_db
class TestWinnerAnnouncementTitle:
    def test_title_singular_matchday(self):
        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=1, points=8, tied=False
        )
        assert ann.title == "¡Ganador de la Jornada 1!"

    def test_title_plural_matchday(self):
        ann = WinnerAnnouncement.objects.create(
            scope_kind="matchday", scope_matchday=3, points=8, tied=True
        )
        assert ann.title == "¡Ganadores de la Jornada 3!"

    def test_title_singular_ko(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="ko", points=42, tied=False)
        assert ann.title == "¡Ganador de las eliminatorias!"

    def test_title_plural_ko(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="ko", points=42, tied=True)
        assert ann.title == "¡Ganadores de las eliminatorias!"

    def test_title_singular_global(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=99, tied=False)
        assert ann.title == "¡Campeón del Mundial!"

    def test_title_plural_global(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="global", points=99, tied=True)
        assert ann.title == "¡Campeones del Mundial!"

    def test_title_sede(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
        assert ann.title == "¡Ganadores por sede!"


@pytest.mark.django_db
class TestUniquenessConstraints:
    def test_uniqueness_constraint_matchday(self):
        WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=10)

    def test_uniqueness_constraint_ko(self):
        WinnerAnnouncement.objects.create(scope_kind="ko", points=42)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="ko", points=50)

    def test_uniqueness_constraint_global(self):
        WinnerAnnouncement.objects.create(scope_kind="global", points=99)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="global", points=100)

    def test_uniqueness_constraint_sede(self):
        WinnerAnnouncement.objects.create(scope_kind="sede", points=0)
        with pytest.raises(IntegrityError):
            WinnerAnnouncement.objects.create(scope_kind="sede", points=0)

    def test_different_matchdays_allowed(self):
        WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=2, points=10)
        assert WinnerAnnouncement.objects.filter(scope_kind="matchday").count() == 2


@pytest.mark.django_db
class TestSeenUniqueness:
    def test_seen_uniqueness_per_user(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        user = UserFactory()
        WinnerAnnouncementSeen.objects.create(announcement=ann, user=user)
        with pytest.raises(IntegrityError):
            WinnerAnnouncementSeen.objects.create(announcement=ann, user=user)

    def test_seen_allows_multiple_users(self):
        ann = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=8)
        u1 = UserFactory()
        u2 = UserFactory()
        WinnerAnnouncementSeen.objects.create(announcement=ann, user=u1)
        WinnerAnnouncementSeen.objects.create(announcement=ann, user=u2)
        assert WinnerAnnouncementSeen.objects.filter(announcement=ann).count() == 2
```

- [ ] **Step 2.5: Ejecutar tests del módulo**

```bash
pytest announcements/tests/test_models.py -v
```

Expected: PASS (16 tests aprox).

- [ ] **Step 2.6: Commit**

```bash
git add announcements/models.py announcements/migrations/0004_drop_round_scope_add_ko.py announcements/tests/test_models.py
git commit -m "feat(announcements): sustituye scope round por ko en WinnerAnnouncement"
```

---

## Task 3: pot.services.prizes — añadir scope `ko`

**Files:**
- Modify: `pot/services/prizes.py`
- Modify: `pot/tests/test_prizes.py`

- [ ] **Step 3.1: Escribir tests**

Añadir al final de `pot/tests/test_prizes.py`:

```python
@pytest.mark.django_db
def test_matchday_winners_ko_pending_until_all_ko_resolved():
    from decimal import Decimal

    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.services.prizes import matchday_winners

    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    qf = RoundFactory(id="qf", points=10, label="QF", short="QF", order=4)
    sf = RoundFactory(id="sf", points=15, label="SF", short="SF", order=5)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)
    user = UserFactory()
    # Crea un partido por ronda KO
    for r in (r32, r16, qf, sf):
        m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=r.points)
    # La Final está pendiente
    m_final = MatchFactory(round=fn, matchday=None, result_home=None)
    PredictionFactory(player=user, match=m_final, home=1, away=0, earned=None)

    result = matchday_winners(("ko", None))
    assert result.status == "pending"


@pytest.mark.django_db
def test_matchday_winners_ko_aggregates_all_ko_including_final():
    from decimal import Decimal

    from accounts.tests.factories import UserFactory
    from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
    from pot.models import PotSettings
    from pot.services.prizes import matchday_winners

    pot = PotSettings.load()
    pot.matchday_winner_prize = Decimal("30.00")
    pot.save(update_fields=["matchday_winner_prize"])

    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    r32 = RoundFactory(id="r32", points=5, label="R32", short="R32", order=2)
    r16 = RoundFactory(id="r16", points=7, label="R16", short="R16", order=3)
    qf = RoundFactory(id="qf", points=10, label="QF", short="QF", order=4)
    sf = RoundFactory(id="sf", points=15, label="SF", short="SF", order=5)
    fn = RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)

    winner = UserFactory(name="W")
    loser = UserFactory(name="L")
    rounds_with_pts = [(r32, 5), (r16, 7), (qf, 10), (sf, 15), (fn, 20)]
    for r, pts in rounds_with_pts:
        m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=winner, match=m, earned=pts)
        PredictionFactory(player=loser, match=m, earned=0)

    result = matchday_winners(("ko", None))
    assert result.status == "resolved"
    assert result.points == 5 + 7 + 10 + 15 + 20  # 57
    assert [u.name for u in result.winners] == ["W"]
    assert result.share == Decimal("30.00")


@pytest.mark.django_db
def test_matchday_winners_ko_excludes_groups_points():
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

    result = matchday_winners(("ko", None))
    # Sólo cuenta la Final: 20 puntos. Los 3 de grupos no entran al scope ko.
    assert result.status == "resolved"
    assert result.points == 20
```

- [ ] **Step 3.2: Ejecutar tests, ver fail**

```bash
pytest pot/tests/test_prizes.py -k "ko" -v
```

Expected: 3 fallos (`ValueError: unknown scope: ko`).

- [ ] **Step 3.3: Implementar cambios en `pot/services/prizes.py`**

Sustituir `_matches_for_scope`, `_standings_for_scope` y `announcement_podium` para que manejen `ko` y dejen de manejar `round`:

```python
def _matches_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return Match.objects.filter(round_id="groups", matchday=value)
    if kind == "ko":
        return Match.objects.exclude(round_id="groups")
    if kind == "global":
        return Match.objects.all()
    raise ValueError(f"unknown scope: {kind}")


_KO_ROUND_IDS = ["r32", "r16", "qf", "sf", "final"]


def _standings_for_scope(scope_key):
    kind, value = scope_key
    if kind == "matchday":
        return standings(round_id="groups", matchday=value)
    if kind == "ko":
        return standings(round_ids=_KO_ROUND_IDS)
    return standings()
```

Y en `announcement_podium`:

```python
def announcement_podium(announcement) -> list["PodiumEntry"]:
    # ... docstring ...
    from itertools import groupby

    from accounts.models import User

    if announcement.scope_kind == "matchday":
        rows = standings(round_id="groups", matchday=announcement.scope_matchday)
    elif announcement.scope_kind == "ko":
        rows = standings(round_ids=_KO_ROUND_IDS)
    else:
        rows = standings()
    # ... resto sin cambios
```

- [ ] **Step 3.4: Ejecutar tests, ver pass**

```bash
pytest pot/tests/test_prizes.py -v
```

Expected: PASS (incluye los 3 nuevos).

- [ ] **Step 3.5: Commit**

```bash
git add pot/services/prizes.py pot/tests/test_prizes.py
git commit -m "feat(prizes): añade scope ko que agrega los 5 rounds eliminatorios"
```

---

## Task 4: announcements.services — nueva regla de dispatch

**Files:**
- Modify: `announcements/services.py`
- Modify: `announcements/tests/test_services.py`
- Modify: `announcements/tests/test_integration.py`

- [ ] **Step 4.1: Reescribir `announcements/services.py`**

```python
from competition.models import Match
from pot.services.prizes import matchday_winners

from .models import WinnerAnnouncement


def detect_after_match(match: Match) -> list[WinnerAnnouncement]:
    """Llamado tras resolve_match(). Crea (idempotentemente) los anuncios de
    ganador del scope al que pertenece el partido recién resuelto, si ese scope
    acaba de cerrarse. Devuelve los anuncios creados en esta llamada (0..N).

    Reglas:
    - Cualquier partido de la fase de grupos: 1 anuncio matchday(N) si la
      jornada N acaba de cerrar.
    - r32/r16/qf/sf: ningún anuncio (esperan a que la Final cierre la jornada
      eliminatoria entera).
    - final: 3 anuncios simultáneos (ko → sede → global) en ese orden, para
      que el feed de modales muestre la jornada KO primero, luego sede y por
      último el campeón del Mundial (climax).
    """
    created: list[WinnerAnnouncement] = []

    if match.round_id == "groups" and match.matchday is not None:
        ann = _try_create("matchday", matchday=match.matchday)
        if ann is not None:
            created.append(ann)
    elif match.round_id == "final":
        for kind in ("ko", "sede", "global"):
            ann = _try_create(kind)
            if ann is not None:
                created.append(ann)

    return created


def _try_create(
    scope_kind: str,
    *,
    matchday: int | None = None,
) -> WinnerAnnouncement | None:
    if scope_kind == "matchday":
        filter_kwargs = {"scope_kind": "matchday", "scope_matchday": matchday}
    elif scope_kind in ("ko", "global", "sede"):
        filter_kwargs = {"scope_kind": scope_kind}
    else:
        raise ValueError(scope_kind)

    if WinnerAnnouncement.objects.filter(**filter_kwargs).exists():
        return None

    if scope_kind == "sede":
        from decimal import Decimal

        from pot.services.prizes import sede_winners

        if Match.objects.filter(round_id="final", result_home__isnull=True).exists():
            return None
        sede_results = sede_winners()
        winners_users = [u for sw in sede_results if sw.status == "resolved" for u in sw.users]
        if not winners_users:
            return None
        ann = WinnerAnnouncement.objects.create(
            scope_kind="sede",
            scope_matchday=None,
            points=0,
            tied=False,
            share=Decimal("0"),
        )
        ann.winners.set(winners_users)
        return ann

    scope_key = (
        scope_kind,
        matchday if scope_kind == "matchday" else None,
    )
    result = matchday_winners(scope_key)
    if result.status != "resolved":
        return None

    ann = WinnerAnnouncement.objects.create(
        scope_kind=scope_kind,
        scope_matchday=matchday,
        points=result.points,
        tied=result.tied,
        share=result.share,
    )
    if result.winners:
        ann.winners.set(result.winners)
    return ann
```

- [ ] **Step 4.2: Reescribir `announcements/tests/test_services.py`**

Sobrescribir el archivo con:

```python
import pytest

from accounts.tests.factories import UserFactory
from announcements.models import WinnerAnnouncement
from announcements.services import detect_after_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.fixture
def r32_round(db):
    return RoundFactory(id="r32", points=5, label="Dieciseisavos", short="R32", order=2)


@pytest.fixture
def r16_round(db):
    return RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)


@pytest.fixture
def qf_round(db):
    return RoundFactory(id="qf", points=10, label="Cuartos", short="QF", order=4)


@pytest.fixture
def sf_round(db):
    return RoundFactory(id="sf", points=15, label="Semifinales", short="SF", order=5)


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.mark.django_db
class TestMatchdayScope:
    def test_no_announcement_when_matchday_incomplete(self, groups_round):
        m_open = MatchFactory(round=groups_round, matchday=1, result_home=None)
        MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        created = detect_after_match(m_open)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0

    def test_announcement_created_when_last_matchday_match_resolved(self, groups_round):
        user = UserFactory(name="Ganadora")
        m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        m2 = MatchFactory(round=groups_round, matchday=1, result_home=2, result_away=2)
        PredictionFactory(player=user, match=m1, earned=3)
        PredictionFactory(player=user, match=m2, earned=1)
        created = detect_after_match(m2)
        assert len(created) == 1
        ann = created[0]
        assert ann.scope_kind == "matchday"
        assert ann.scope_matchday == 1
        assert ann.points == 4
        assert list(ann.winners.all()) == [user]

    def test_announcement_idempotent_on_second_call(self, groups_round):
        user = UserFactory()
        m = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=3)
        first = detect_after_match(m)
        second = detect_after_match(m)
        assert len(first) == 1
        assert second == []


@pytest.mark.django_db
class TestKoSilentRounds:
    def test_resolving_r32_creates_no_announcement(self, r32_round):
        user = UserFactory()
        m = MatchFactory(round=r32_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=5)
        created = detect_after_match(m)
        assert created == []

    def test_resolving_sf_creates_no_announcement(self, sf_round):
        user = UserFactory()
        m = MatchFactory(round=sf_round, matchday=None, result_home=1, result_away=0)
        PredictionFactory(player=user, match=m, earned=15)
        created = detect_after_match(m)
        assert created == []
        assert WinnerAnnouncement.objects.count() == 0


@pytest.mark.django_db
class TestFinalTriggers:
    def test_final_creates_ko_sede_global_in_order(
        self, groups_round, r32_round, r16_round, qf_round, sf_round, final_round
    ):
        winner = UserFactory(name="W", sede="madrid")
        other = UserFactory(name="O", sede="vigo")
        # Un partido por ronda KO con marcador resuelto y predicciones puntuadas
        for r, pts in (
            (r32_round, 5),
            (r16_round, 7),
            (qf_round, 10),
            (sf_round, 15),
        ):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=winner, match=m, earned=pts)
            PredictionFactory(player=other, match=m, earned=0)
        m_final = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=winner, match=m_final, earned=20)
        PredictionFactory(player=other, match=m_final, earned=0)

        created = detect_after_match(m_final)
        kinds = [a.scope_kind for a in created]
        assert kinds == ["ko", "sede", "global"]

    def test_final_ko_aggregates_all_ko_including_final_points(
        self, r32_round, r16_round, qf_round, sf_round, final_round
    ):
        winner = UserFactory(name="W", sede="madrid")
        for r, pts in (
            (r32_round, 5),
            (r16_round, 7),
            (qf_round, 10),
            (sf_round, 15),
        ):
            m = MatchFactory(round=r, matchday=None, result_home=1, result_away=0)
            PredictionFactory(player=winner, match=m, earned=pts)
        m_final = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=winner, match=m_final, earned=20)

        created = detect_after_match(m_final)
        ko = next(a for a in created if a.scope_kind == "ko")
        assert ko.points == 57  # 5+7+10+15+20

    def test_final_idempotent(self, final_round):
        user = UserFactory(name="W", sede="madrid")
        m = MatchFactory(round=final_round, matchday=None, result_home=2, result_away=1)
        PredictionFactory(player=user, match=m, earned=20)
        first = detect_after_match(m)
        second = detect_after_match(m)
        assert len(first) >= 1
        assert second == []
```

- [ ] **Step 4.3: Actualizar `announcements/tests/test_integration.py`**

Sobrescribir el archivo con:

```python
import pytest

from accounts.tests.factories import GestorFactory, UserFactory
from announcements.models import WinnerAnnouncement
from competition.services.resolve import resolve_match
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory


@pytest.fixture
def groups_round(db):
    return RoundFactory(id="groups", points=3, label="Fase de grupos", short="GRP", order=1)


@pytest.fixture
def r16_round(db):
    return RoundFactory(id="r16", points=7, label="Octavos", short="R16", order=3)


@pytest.fixture
def final_round(db):
    return RoundFactory(id="final", points=20, label="Final", short="FIN", order=6)


@pytest.fixture
def gestor():
    return GestorFactory()


@pytest.mark.django_db
def test_resolve_last_match_of_matchday_creates_announcement(groups_round, gestor):
    user = UserFactory()
    other = UserFactory()
    m1 = MatchFactory(round=groups_round, matchday=1, result_home=1, result_away=0)
    m2 = MatchFactory(round=groups_round, matchday=1)
    PredictionFactory(player=user, match=m1, earned=3)
    PredictionFactory(player=user, match=m2, home=2, away=2)
    PredictionFactory(player=other, match=m1, earned=0)
    PredictionFactory(player=other, match=m2, home=0, away=0)

    resolve_match(m2, home=2, away=2, actor=gestor)

    anns = WinnerAnnouncement.objects.filter(scope_kind="matchday", scope_matchday=1)
    assert anns.count() == 1
    assert list(anns.first().winners.values_list("id", flat=True)) == [user.id]


@pytest.mark.django_db
def test_resolving_ko_round_creates_no_announcement(r16_round, gestor):
    user = UserFactory()
    m = MatchFactory(round=r16_round, matchday=None)
    PredictionFactory(player=user, match=m, home=1, away=0)
    resolve_match(m, home=1, away=0, actor=gestor)
    assert WinnerAnnouncement.objects.count() == 0


@pytest.mark.django_db
def test_resolve_final_creates_ko_sede_global(final_round, gestor):
    user = UserFactory(name="W", sede="madrid")
    other = UserFactory(name="O", sede="vigo")
    m = MatchFactory(round=final_round, matchday=None)
    PredictionFactory(player=user, match=m, home=2, away=1)
    PredictionFactory(player=other, match=m, home=0, away=0)

    resolve_match(m, home=2, away=1, actor=gestor)

    kinds = sorted(WinnerAnnouncement.objects.values_list("scope_kind", flat=True))
    assert kinds == ["global", "ko", "sede"]
```

- [ ] **Step 4.4: Ejecutar tests**

```bash
pytest announcements/tests/test_services.py announcements/tests/test_integration.py -v
```

Expected: PASS.

- [ ] **Step 4.5: Commit**

```bash
git add announcements/services.py announcements/tests/test_services.py announcements/tests/test_integration.py
git commit -m "feat(announcements): dispatch ko+sede+global tras la Final, KO intermedios en silencio"
```

---

## Task 5: Preview de scope `ko`

**Files:**
- Modify: `announcements/preview.py`
- Modify: `announcements/tests/test_preview.py`

- [ ] **Step 5.1: Actualizar `announcements/preview.py`**

Reemplazar `_VALID_SCOPES` y la rama `round` en `build_preview`:

```python
_VALID_SCOPES = {"matchday", "ko", "global"}


def build_preview(scope: str, *, tied: bool, current_user) -> tuple[WinnerAnnouncement, list]:
    if scope not in _VALID_SCOPES:
        raise Http404(f"scope inválido: {scope}")

    ann = WinnerAnnouncement(scope_kind=scope, points=12)

    if scope == "matchday":
        ann.scope_matchday = 1
    # scope == "ko" no necesita estado adicional (un único anuncio global por torneo)

    winners = [current_user]
    if tied:
        other = User.objects.exclude(pk=current_user.pk).order_by("name").first()
        if other is not None:
            winners.append(other)
    ann.tied = len(winners) > 1

    base = _preview_prize_for_position(scope, 1)
    ann.share = (base / len(winners)) if winners else Decimal("0")

    return ann, winners
```

Eliminar el import `from competition.models import Round` si ya no se usa.

`_preview_prize_for_position`: misma lógica (ya devuelve `matchday_winner_prize` para cualquier scope que no sea `global`), no requiere cambios.

- [ ] **Step 5.2: Actualizar `announcements/tests/test_preview.py`**

Reemplazar el bloque del scope `round` por uno equivalente para `ko`:

```python
    def test_ko_builds_announcement_without_extra_state(self):
        gestor = GestorFactory()
        ann, winners = build_preview("ko", tied=False, current_user=gestor)
        assert ann.scope_kind == "ko"
        assert ann.scope_matchday is None
        assert ann.title == "¡Ganador de las eliminatorias!"
        assert winners == [gestor]
```

Y en `TestPreviewView`, sustituir `test_round_title` por:

```python
    def test_ko_title(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=ko&tied=0")
        assert "¡Ganador de las eliminatorias!" in res.content.decode()
```

Eliminar el test `test_round_uses_first_ko_round` (ya no aplica).

- [ ] **Step 5.3: Ejecutar tests**

```bash
pytest announcements/tests/test_preview.py -v
```

Expected: PASS.

- [ ] **Step 5.4: Commit**

```bash
git add announcements/preview.py announcements/tests/test_preview.py
git commit -m "feat(announcements): preview de scope ko, retira scope round"
```

---

## Task 6: Vistas — quitar select_related("scope_round")

**Files:**
- Modify: `announcements/views.py`

- [ ] **Step 6.1: Editar `announcements/views.py:27`**

Sustituir:

```python
            WinnerAnnouncement.objects.prefetch_related("winners").select_related("scope_round"),
```

por:

```python
            WinnerAnnouncement.objects.prefetch_related("winners"),
```

- [ ] **Step 6.2: Ejecutar tests de vistas**

```bash
pytest announcements/tests/test_views.py -v
```

Expected: PASS.

- [ ] **Step 6.3: Commit**

```bash
git add announcements/views.py
git commit -m "chore(announcements): retira select_related obsoleto de scope_round"
```

---

## Task 7: Plantillas — dropdown de preview y copy de reglas

**Files:**
- Modify: `templates/pot/prizes_settings.html`
- Modify: `templates/core/rules.html`

- [ ] **Step 7.1: Dropdown de preview en `templates/pot/prizes_settings.html`**

Sustituir las líneas 191-192:

```html
          <option value="matchday">Jornada de grupos</option>
          <option value="round">Ronda eliminatoria</option>
```

por:

```html
          <option value="matchday">Jornada de grupos</option>
          <option value="ko">Jornada eliminatoria</option>
```

- [ ] **Step 7.2: Copy del bloque "Premio por ganador de jornada" en `templates/pot/prizes_settings.html` (líneas 62-83)**

Reemplazar el `<section>` actual por:

```html
    <section class="glass prizes-matchday-card" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:18px">
      <header style="display:flex;flex-direction:column;gap:4px">
        <span class="eyebrow">02 · Por jornada</span>
        <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:20px">Premio por ganador de jornada</h2>
        <p style="color:var(--text-dim);margin:0;font-size:13px">
          Hay <strong>4 jornadas</strong> en total y cada una entrega este premio al jugador con
          más puntos en ella. Las tres primeras son las de la fase de grupos (1ª, 2ª y 3ª). La
          cuarta es la <strong>jornada eliminatoria</strong>: dieciseisavos, octavos, cuartos,
          semifinales <strong>y la Final</strong> cuentan todos juntos como una sola jornada. La
          Final no entrega premio aparte (su ganador cobra a través del podio), pero sus puntos
          sí suman para decidir al ganador de la jornada eliminatoria.
        </p>
      </header>

      <div class="prizes-matchday-row">
        <div class="prizes-matchday-icon">{% icon "trophy" width=28 height=28 %}</div>
        <label class="prizes-matchday-label" for="matchday_winner_prize">Importe por jornada</label>
        <div class="prizes-matchday-input">
          <input class="input" type="number" min="0" step="0.01" inputmode="decimal"
                 id="matchday_winner_prize" name="matchday_winner_prize"
                 value="{{ settings.matchday_winner_prize|floatformat:'-2' }}">
          <span class="mono">€</span>
        </div>
      </div>
    </section>
```

- [ ] **Step 7.3: Copy de "Premio por ganador de jornada" en `templates/core/rules.html` (líneas 213-227)**

Reemplazar el `<div class="rules-matchday-prize">` por:

```html
    {% if matchday_winner_prize and matchday_winner_prize > 0 %}
    <div class="rules-matchday-prize">
      <div class="rules-matchday-prize-icon">{% icon "trophy" width=22 height=22 aria_hidden="true" %}</div>
      <div class="rules-matchday-prize-body">
        <span class="eyebrow">Premio por ganador de jornada</span>
        <strong>{{ matchday_winner_prize|floatformat:"-2" }} €</strong>
        <p>
          Hay <strong>4 jornadas</strong> en total y cada una entrega este premio al jugador con
          más puntos en ella. Las tres primeras son las de la fase de grupos (1ª, 2ª y 3ª). La
          cuarta es la <strong>jornada eliminatoria</strong>: dieciseisavos, octavos, cuartos,
          semifinales <strong>y la Final</strong> cuentan todos juntos como una sola jornada. La
          Final no entrega premio aparte (su ganador cobra como campeón del Mundial en el podio),
          pero sus puntos sí suman para decidir al ganador de la jornada eliminatoria.
        </p>
      </div>
    </div>
    {% endif %}
```

(El texto de desempate en línea 274 ya quedó correcto tras PR #45; no tocar.)

- [ ] **Step 7.4: Ejecutar tests de la vista de reglas y de premios**

```bash
pytest core/tests/test_rules_view.py pot/tests/test_prizes_settings_view.py -v
```

Expected: PASS.

- [ ] **Step 7.5: Commit**

```bash
git add templates/core/rules.html templates/pot/prizes_settings.html
git commit -m "feat(reglas): copy de premio por jornada con la regla unificada (3 grupos + 1 KO)"
```

---

## Task 8: `docs/DATA_MODEL.md`

**Files:**
- Modify: `docs/DATA_MODEL.md`

- [ ] **Step 8.1: Actualizar la fila `matchdayWinnerPrize` (línea 79)**

Reemplazar:

```
| `matchdayWinnerPrize` | Decimal | importe único que cobra el ganador de cada jornada. Cuentan como jornada la 1ª, 2ª y 3ª de la fase de grupos y cada una de las rondas eliminatorias salvo la Final (dieciseisavos, octavos, cuartos y semifinales) — 7 jornadas en total |
```

por:

```
| `matchdayWinnerPrize` | Decimal | importe único que cobra el ganador de cada jornada. Hay 4 jornadas: las 3 de la fase de grupos (1ª, 2ª, 3ª) y una única jornada eliminatoria que agrega TODOS los partidos KO incluida la Final (r32+r16+qf+sf+final). La Final no entrega premio aparte pero sus puntos sí suman al scope KO |
```

- [ ] **Step 8.2: Reescribir el bloque de notas (líneas 86-91)**

Reemplazar las dos notas (`> El modelo Prize...` y `> **Premio por ganador de jornada.**`) por:

```markdown
> El modelo `Prize` solo se usa para el podio final (top 3). Las filas con scope `matchday` o `round` quedaron retiradas en favor de `matchdayWinnerPrize` en PotSettings — un único importe para todas las jornadas.

> **Premio por ganador de jornada.** Hay **4 jornadas** en total. El importe `matchdayWinnerPrize` se entrega:
> - **3 veces durante la fase de grupos** (una por cada jornada: 1ª, 2ª, 3ª) — al jugador con más puntos en esa jornada.
> - **1 vez al cierre del torneo** como premio de la **jornada eliminatoria**, que agrega los puntos de TODOS los partidos KO **incluida la Final** (r32 + r16 + qf + sf + final). El cálculo del scope KO usa `standings(round_ids=["r32","r16","qf","sf","final"])`.
> - **La Final NO genera premio de jornada propio**: su ganador cobra a través del podio (P1), pero sus puntos sí cuentan para la jornada eliminatoria.
> El servicio `announcements.services.detect_after_match` crea los anuncios `ko`, `sede` y `global` simultáneamente cuando se resuelve la Final, en ese orden de aparición.
```

- [ ] **Step 8.3: Actualizar línea 158 (sección de desempate "Premios económicos")**

Reemplazar:

```
**Premios económicos.** El importe de cada plaza del podio (P1·P2·P3) se reparte a partes iguales entre quienes la ocupen. El premio por ganador de jornada (las tres de grupos y las cuatro eliminatorias —dieciseisavos, octavos, cuartos, semifinales—; **no la Final**) se decide aplicando las mismas reglas dentro del scope; si tras las tres siguen empatados, los empatados se reparten el importe a partes iguales.
```

por:

```
**Premios económicos.** El importe de cada plaza del podio (P1·P2·P3) se reparte a partes iguales entre quienes la ocupen. El premio por ganador de jornada (las tres de grupos y la única jornada eliminatoria que agrega los 31 partidos KO incluida la Final) se decide aplicando las mismas reglas dentro del scope; si tras las tres siguen empatados, los empatados se reparten el importe a partes iguales.
```

- [ ] **Step 8.4: Commit**

```bash
git add docs/DATA_MODEL.md
git commit -m "docs(data-model): describe scope ko y la jornada eliminatoria unificada"
```

---

## Task 9: Verificación final — suite completa + ruff + push + PR + merge

**Files:** todo el repo

- [ ] **Step 9.1: Ejecutar la suite completa**

```bash
pytest -q
```

Expected: 100% PASS (suite ~619 tests + nuevos).

- [ ] **Step 9.2: Ejecutar ruff**

```bash
ruff check .
```

Expected: no findings. Si los hay, corregirlos (`ruff check . --fix` para los safe) y commit aparte.

- [ ] **Step 9.3: Comprobar que no quedan referencias al scope retirado**

```bash
grep -rn "scope_round\|scope_kind.*round\|\"round\".*scope" announcements/ pot/ templates/ docs/DATA_MODEL.md --include="*.py" --include="*.html" --include="*.md" | grep -v "docs/superpowers/" | grep -v "migrations/0001" | grep -v "migrations/0004"
```

Expected: vacío. La migración inicial (0001) sí menciona `scope_round`; eso es historia y es esperado.

- [ ] **Step 9.4: Push y PR**

```bash
git push -u origin worktree-jornada-eliminatoria-ko-combinada
gh pr create --title "feat(porra): jornada eliminatoria KO combinada (4 jornadas en total)" \
  --body-file - <<'EOF'
## Summary

Implementa correctamente la regla del bote: **4 jornadas en total**.
- Grupos J1, J2, J3 → 3 premios (sin cambios).
- **Jornada eliminatoria** = todos los partidos KO incluida la Final (r32+r16+qf+sf+final) → 1 premio.
- Final sigue sin entregar premio propio (cobra por el podio), pero sus puntos sí cuentan para la jornada KO.

## Cambios técnicos

- `WinnerAnnouncement`: scope `round` retirado del modelo, scope `ko` añadido (con `UniqueConstraint` global). Campo `scope_round` eliminado.
- Migración `0004` destructiva: borra anuncios `scope=round` existentes, drop FK, alter choices, add constraint.
- `competition.services.standings.standings()`: nuevo parámetro `round_ids` para agregar por varias rondas.
- `pot.services.prizes`: scope `ko` agrega r32+r16+qf+sf+final.
- `announcements.services.detect_after_match`: las rondas KO intermedias dejan de disparar anuncios; tras la Final salen 3 simultáneos (`ko` → `sede` → `global`).
- `announcements.preview`: scope `round` retirado, `ko` añadido.
- Copy de `templates/core/rules.html`, `templates/pot/prizes_settings.html` y `docs/DATA_MODEL.md` alineados con la regla unificada.

## Test plan

- [x] `pytest -q` → 100% PASS
- [x] `ruff check .` → limpio
- [ ] Visual `/reglas/` → tarjeta "Premio por ganador de jornada" con la nueva copy de 4 jornadas
- [ ] Visual `/premios/` → bloque "02 · Por jornada" y dropdown de preview con opción "Jornada eliminatoria"
- [ ] Preview manual del modal ko desde `/premios/` → título "¡Ganador de las eliminatorias!"

## Spec

- `docs/superpowers/specs/2026-06-05-jornada-eliminatoria-ko-combinada-design.md`
EOF
```

- [ ] **Step 9.5: Vigilar CI y mergear cuando esté verde**

```bash
gh pr checks --watch
PR=$(gh pr view --json number -q .number)
gh pr merge $PR --squash
git push origin --delete worktree-jornada-eliminatoria-ko-combinada || true
```

Verificar: `gh pr view $PR --json state -q .state` → `MERGED`.

---

## Notas

- **Orden de commits**: tasks pequeños y atómicos. Un task = un commit. Si algún test falla por interacción cruzada al ejecutar la suite completa, el orden de los tasks 2→3→4 (modelo → prizes → service) minimiza el ventana de incoherencia.
- **Migración**: Django puede generar las operaciones en distinto orden tras `makemigrations`. Reordenar manualmente para que `RunPython` vaya primero, después `RemoveConstraint`, después `RemoveField`, después `AlterField`, y finalmente `AddConstraint`.
- **CLAUDE.md**: nada de mocks de DB en tests (los tests siguen `@pytest.mark.django_db`), nada de "TODO" en código, copy en español de España.
