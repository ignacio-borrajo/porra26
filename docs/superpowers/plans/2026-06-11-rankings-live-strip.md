# Rankings live strip Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Llevar el patrón "live" (LiveScore + live_standings) del dashboard a la página de Rankings: banda superior con los partidos en juego/awaiting y sus marcadores, tablas de clasificación calculadas con `live_pts`, y auto-refresh cada 60 s.

**Architecture:**
- Backend: helper `current_live_matches()` compartido; `rankings_context.build_general_context()` y `group_standings.group_standings()` migran a `live_standings()`; `RankingsView` y `GroupRankingsView` inyectan `live_matches`, `awaiting_matches`, `has_live_matches` en el contexto.
- Frontend: nuevo partial `_live_matches_strip.html` insertado entre la nav de pestañas y el contenido en `rankings.html` y `rankings_group.html`; CSS dedicado para la banda; auto-refresh JS copiado del dashboard.

**Tech Stack:** Django 5, plantillas Django, pytest + pytest-django, CSS vanilla.

**Spec:** `docs/superpowers/specs/2026-06-11-rankings-live-strip-design.md`.

---

## Task 1: Helper `current_live_matches()`

**Files:**
- Create: `competition/services/live_view.py`
- Test: `competition/tests/test_live_view_service.py`

- [ ] **Step 1: Escribir el test que falla**

Crear `competition/tests/test_live_view_service.py` con:

```python
"""Tests para el helper current_live_matches()."""

from datetime import timedelta

import pytest
from django.utils import timezone

from competition.models import LiveScore
from competition.services.live_view import current_live_matches
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_returns_live_and_awaiting_separately():
    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)
    awaiting = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(hours=2))
    LiveScore.objects.create(
        match=awaiting, home_score=2, away_score=2, period="FT", minute=95
    )

    live_matches, awaiting_matches = current_live_matches()

    assert [m.id for m in live_matches] == [live.id]
    assert [m.id for m in awaiting_matches] == [awaiting.id]


@pytest.mark.django_db
def test_ignores_open_and_done_matches():
    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2))  # open
    done = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(days=2))
    done.result_home, done.result_away = 1, 0
    done.save()

    live_matches, awaiting_matches = current_live_matches()

    assert live_matches == []
    assert awaiting_matches == []


@pytest.mark.django_db
def test_orders_by_kickoff_ascending():
    grp = RoundFactory(id="groups", points=3, order=1)
    later = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=5))
    LiveScore.objects.create(match=later, home_score=0, away_score=0, period="1H", minute=5)
    earlier = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=80))
    LiveScore.objects.create(match=earlier, home_score=1, away_score=1, period="2H", minute=80)

    live_matches, _ = current_live_matches()

    assert [m.id for m in live_matches] == [earlier.id, later.id]


@pytest.mark.django_db
def test_returns_empty_lists_when_nothing_live():
    grp = RoundFactory(id="groups", points=3, order=1)
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2))

    live_matches, awaiting_matches = current_live_matches()

    assert live_matches == []
    assert awaiting_matches == []


@pytest.mark.django_db
def test_live_match_without_live_score_still_returned_as_live():
    """kickoff pasado pero sin LiveScore aún (cron no disparó): debe seguir
    contando como live (sin awaiting porque no hay period=FT)."""
    grp = RoundFactory(id="groups", points=3, order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=2))

    live_matches, awaiting_matches = current_live_matches()

    assert [x.id for x in live_matches] == [m.id]
    assert awaiting_matches == []
```

- [ ] **Step 2: Verificar que el test falla**

Ejecuta:

```bash
cd /Users/ignacioborrajo/Documents/GitHub/apuestas-interna
pytest competition/tests/test_live_view_service.py -v
```

Esperado: `ImportError`/`ModuleNotFoundError` sobre `competition.services.live_view`.

- [ ] **Step 3: Implementar el helper**

Crear `competition/services/live_view.py`:

```python
"""Helper para listar los partidos en juego y los pendientes de oficial.

Compartido entre el dashboard de Competición y la página de Rankings,
así no duplicamos la separación `live` vs `awaiting`.
"""

from __future__ import annotations

from django.utils import timezone

from competition.models import Match


def current_live_matches() -> tuple[list[Match], list[Match]]:
    """Devuelve `(live_matches, awaiting_matches)` ordenados por kickoff ASC.

    - `live_matches`: partidos con `status == 'live'` que NO están
      `awaiting_validation` (cron aún no ha visto FT o el live_score no es FT).
    - `awaiting_matches`: partidos con `status == 'live'` y `awaiting_validation`
      (FT en football-data pero el gestor no ha confirmado el oficial).

    Ambos quedan con `home`, `away`, `round` y `live_score` precargados.
    """
    qs = (
        Match.objects.filter(
            kickoff__lte=timezone.now(),
            result_home__isnull=True,
            result_away__isnull=True,
            home__isnull=False,
            away__isnull=False,
        )
        .select_related("home", "away", "round", "live_score")
        .order_by("kickoff")
    )
    live: list[Match] = []
    awaiting: list[Match] = []
    for m in qs:
        if m.awaiting_validation:
            awaiting.append(m)
        else:
            live.append(m)
    return live, awaiting
```

- [ ] **Step 4: Verificar que el test pasa**

```bash
pytest competition/tests/test_live_view_service.py -v
```

Esperado: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add competition/services/live_view.py competition/tests/test_live_view_service.py
git commit -m "feat(live): helper current_live_matches() compartido entre dashboard y rankings"
```

---

## Task 2: Migrar `build_general_context()` a `live_standings()`

**Files:**
- Modify: `stats/services/rankings_context.py`
- Test: `stats/tests/test_rankings_context_live.py` (nuevo)

- [ ] **Step 1: Escribir el test que falla**

Crear `stats/tests/test_rankings_context_live.py`:

```python
"""Tests para que build_general_context() use puntos live."""

from datetime import timedelta

import pytest
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore
from competition.tests.factories import MatchFactory, PredictionFactory, RoundFactory
from stats.services.rankings_context import build_general_context


@pytest.mark.django_db
def test_general_standings_include_live_points():
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice")
    bob = UserFactory(name="Bob")

    # Partido live con marcador 2-1: Alice acierta exacto, Bob no.
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=2, away_score=1, period="2H", minute=70)
    PredictionFactory(player=alice, match=m, home=2, away=1)
    PredictionFactory(player=bob, match=m, home=0, away=0)

    ctx = build_general_context(alice, requested_scope_key=None)

    rows_by_player = {r.player_id: r for r in ctx["standings"]}
    assert rows_by_player[alice.id].pts == grp.points
    assert rows_by_player[bob.id].pts == 0


@pytest.mark.django_db
def test_scope_standings_include_live_points():
    """El scope (jornada/ronda) también suma puntos hipotéticos."""
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice")

    m = MatchFactory(
        round=grp, matchday=1, kickoff=timezone.now() - timedelta(minutes=10)
    )
    LiveScore.objects.create(match=m, home_score=1, away_score=0, period="1H", minute=20)
    PredictionFactory(player=alice, match=m, home=1, away=0)

    ctx = build_general_context(alice, requested_scope_key="groups:1")

    scope_rows_by_player = {r.player_id: r for r in ctx["scope_standings"]}
    assert scope_rows_by_player[alice.id].pts == grp.points


@pytest.mark.django_db
def test_no_live_matches_keeps_standings_unchanged():
    """Sin LiveScore, live_pts == pts → comportamiento idéntico al antiguo."""
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice")
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(hours=2))
    PredictionFactory(player=alice, match=m, home=1, away=0)

    ctx = build_general_context(alice, requested_scope_key=None)

    assert all(r.pts == 0 for r in ctx["standings"])
```

- [ ] **Step 2: Verificar que el test falla**

```bash
pytest stats/tests/test_rankings_context_live.py -v
```

Esperado: los dos primeros tests fallan (`alice_row.pts == 0` en lugar de 3); el tercero pasa.

- [ ] **Step 3: Implementar el cambio**

Modificar `stats/services/rankings_context.py`. Sustituye solo:

a) El import:

```python
from competition.services.standings import standings
```

por:

```python
from competition.services.live_standings import live_standings
```

b) Las dos llamadas a `standings(...)` quedan como `live_standings(...)`.

c) Añadir, justo después de cada llamada, el "trick" de aplanar live_pts sobre pts (mismo patrón que `competition/views.py:80-95`).

El archivo completo queda así:

```python
from collections.abc import Iterable

from accounts.models import User
from competition.services.live_standings import live_standings
from stats.services.matchday_options import current_option, matchday_options, parse_scope_key


def build_general_context(
    user,
    requested_scope_key: str | None,
    *,
    player_ids: Iterable[int] | None = None,
) -> dict:
    """Contexto compartido entre el tab General de Rankings y el detalle por grupo.

    Devuelve el dict con `standings`, `scope_standings`, `md_options`, etc.
    Si `player_ids` está presente, las clasificaciones quedan limitadas a
    esos jugadores y las posiciones se recalculan desde 1 dentro del grupo.

    Las dos clasificaciones usan `live_standings()`: en `r.pts` ya viene la
    mezcla "oficial + hipotético" para que las tablas se vean en directo
    cuando hay partidos en juego.
    """
    player_ids_list = list(player_ids) if player_ids is not None else None

    rows = live_standings(player_ids=player_ids_list)
    for r in rows:
        r.pts = r.live_pts
    has_points = bool(rows) and rows[0].pts > 0
    my_row = next((r for r in rows if r.player_id == user.id), None)
    my_rank = my_row.position if my_row and has_points else None
    my_is_tied = bool(my_row and my_row.is_tied and has_points)
    max_pts = max((r.pts for r in rows), default=0) or 1

    md_opts = matchday_options()
    requested = parse_scope_key(requested_scope_key, md_opts)
    current = current_option(md_opts)
    scope = requested or current
    for o in md_opts:
        o.is_active = scope is not None and o.key == scope.key

    scope_rows: list = []
    scope_my_rank = None
    scope_my_is_tied = False
    scope_max_pts = 1
    scope_label = None
    if scope is not None:
        if scope.round_ids is not None:
            scope_rows = live_standings(
                round_ids=scope.round_ids,
                player_ids=player_ids_list,
            )
        else:
            scope_rows = live_standings(
                round_id=scope.round_id,
                matchday=scope.matchday,
                player_ids=player_ids_list,
            )
        for r in scope_rows:
            r.pts = r.live_pts
        scope_has_points = bool(scope_rows) and scope_rows[0].pts > 0
        scope_my_row = next((r for r in scope_rows if r.player_id == user.id), None)
        scope_my_rank = scope_my_row.position if scope_my_row and scope_has_points else None
        scope_my_is_tied = bool(scope_my_row and scope_my_row.is_tied and scope_has_points)
        scope_max_pts = max((r.pts for r in scope_rows), default=0) or 1
        scope_label = scope.label

    all_ids = {r.player_id for r in rows} | {r.player_id for r in scope_rows}
    users_by_id = User.objects.in_bulk(all_ids)
    return {
        "standings": rows,
        "standings_users": users_by_id,
        "my_rank": my_rank,
        "my_is_tied": my_is_tied,
        "max_pts": max_pts,
        "scope_standings": scope_rows,
        "scope_my_rank": scope_my_rank,
        "scope_my_is_tied": scope_my_is_tied,
        "scope_max_pts": scope_max_pts,
        "scope_label": scope_label,
        "md_options": md_opts,
    }
```

- [ ] **Step 4: Verificar que pasan los tests nuevos**

```bash
pytest stats/tests/test_rankings_context_live.py -v
```

Esperado: 3 passed.

- [ ] **Step 5: Verificar que los tests existentes siguen pasando**

```bash
pytest stats/ competition/tests/test_live_standings.py -v
```

Esperado: todos pasan. Si algún test antiguo asume que la tabla NO mueve por live, hay que actualizarlo (en ese caso, ajustar el test para introducir partidos sin LiveScore).

- [ ] **Step 6: Commit**

```bash
git add stats/services/rankings_context.py stats/tests/test_rankings_context_live.py
git commit -m "feat(rankings): tabla General y scope usan live_standings()"
```

---

## Task 3: Migrar `group_standings()` a `live_standings()`

**Files:**
- Modify: `stats/services/group_standings.py`
- Test: `stats/tests/test_group_standings.py` (añadir cases)

- [ ] **Step 1: Escribir los tests nuevos**

Añadir al final de `stats/tests/test_group_standings.py`:

```python
from competition.models import LiveScore


@pytest.mark.django_db
def test_group_standings_includes_live_points_in_total():
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(sede="vigo", is_jugador=True)
    UserFactory(sede="vigo", is_jugador=True)  # bob sin predicción

    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=2, away_score=1, period="2H", minute=70)
    Prediction.objects.create(player=alice, match=m, home=2, away=1)

    rows = {r.key: r for r in group_standings("sede")}

    # Alice suma 3 hipotéticos → vigo tiene total=3, avg=1.5.
    assert rows["vigo"].total == 3
    assert rows["vigo"].avg == 1.5


@pytest.mark.django_db
def test_group_standings_top_pts_reflects_live():
    grp = RoundFactory(id="groups", points=3, partial_points=1, order=1)
    alice = UserFactory(name="Alice", sede="vigo", is_jugador=True)

    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=1, away_score=0, period="1H", minute=20)
    Prediction.objects.create(player=alice, match=m, home=1, away=0)

    rows = {r.key: r for r in group_standings("sede")}

    assert rows["vigo"].top_pts == 3
    assert rows["vigo"].top_name == "Alice"
```

- [ ] **Step 2: Verificar que los tests nuevos fallan**

```bash
pytest stats/tests/test_group_standings.py::test_group_standings_includes_live_points_in_total \
       stats/tests/test_group_standings.py::test_group_standings_top_pts_reflects_live -v
```

Esperado: ambos fallan (`total == 0`, `top_pts == 0`).

- [ ] **Step 3: Implementar el cambio**

Modificar `stats/services/group_standings.py`. Cambiar:

```python
from competition.services.standings import standings
```

por:

```python
from competition.services.live_standings import live_standings
```

Y dentro de `group_standings()`, sustituir:

```python
    standings_rows = standings()
```

por:

```python
    standings_rows = live_standings()
    for r in standings_rows:
        r.pts = r.live_pts
```

`_row_for()` no se toca: ya lee `r.pts`.

- [ ] **Step 4: Verificar que pasan los tests nuevos**

```bash
pytest stats/tests/test_group_standings.py -v
```

Esperado: todos los tests del fichero (incluyendo los nuevos) en verde.

- [ ] **Step 5: Commit**

```bash
git add stats/services/group_standings.py stats/tests/test_group_standings.py
git commit -m "feat(rankings): tablas Sede/Puesto/Dept agregan con live_pts"
```

---

## Task 4: `RankingsView` y `GroupRankingsView` inyectan los matches live

**Files:**
- Modify: `stats/views.py`
- Test: `stats/tests/test_rankings_view_live.py` (nuevo)

- [ ] **Step 1: Escribir los tests que fallan**

Crear `stats/tests/test_rankings_view_live.py`:

```python
"""Tests para que las vistas de Rankings inyecten partidos live al contexto."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_rankings_context_includes_live_matches(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)

    res = client.get(reverse("stats:rankings"))

    assert res.status_code == 200
    assert [m.id for m in res.context["live_matches"]] == [live.id]
    assert res.context["awaiting_matches"] == []
    assert res.context["has_live_matches"] is True


@pytest.mark.django_db
def test_rankings_context_has_live_matches_false_when_none(client):
    user = UserFactory()
    client.force_login(user)
    RoundFactory(id="groups", points=3, order=1)

    res = client.get(reverse("stats:rankings"))

    assert res.context["live_matches"] == []
    assert res.context["awaiting_matches"] == []
    assert res.context["has_live_matches"] is False


@pytest.mark.django_db
@pytest.mark.parametrize("tab", ["general", "sede", "puesto", "dept"])
def test_rankings_live_context_present_in_all_tabs(client, tab):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=1, away_score=0, period="1H", minute=20)

    res = client.get(reverse("stats:rankings"), {"tab": tab})

    assert res.status_code == 200
    assert [m.id for m in res.context["live_matches"]] == [live.id]
    assert res.context["has_live_matches"] is True


@pytest.mark.django_db
def test_group_rankings_context_includes_live_matches(client):
    user = UserFactory(sede="vigo")
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    live = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=live, home_score=2, away_score=2, period="2H", minute=80)

    res = client.get(reverse("stats:rankings_group", kwargs={"dim": "sede", "key": "vigo"}))

    assert res.status_code == 200
    assert [m.id for m in res.context["live_matches"]] == [live.id]
    assert res.context["has_live_matches"] is True
```

- [ ] **Step 2: Verificar que los tests fallan**

```bash
pytest stats/tests/test_rankings_view_live.py -v
```

Esperado: todos fallan con `KeyError` sobre `live_matches` o similar.

- [ ] **Step 3: Implementar el cambio en `stats/views.py`**

Añadir al import block:

```python
from competition.services.live_view import current_live_matches
```

Crear un helper privado y usarlo en ambas vistas. El módulo `stats/views.py` queda así (solo se modifican `RankingsView` y `GroupRankingsView` — el resto se mantiene):

```python
from django.contrib.auth.mixins import LoginRequiredMixin
from django.http import Http404, HttpResponse, JsonResponse
from django.shortcuts import render
from django.views import View

from accounts.models import User
from competition.services.live_view import current_live_matches
from stats.services.group_standings import CHOICES_BY_DIMENSION, group_standings
from stats.services.history import per_player_history
from stats.services.history_matrix import build_matrix
from stats.services.history_xlsx import render_xlsx
from stats.services.kpis import donut, kpis
from stats.services.rankings_context import build_general_context


def _live_context() -> dict:
    """Bloque común para inyectar partidos en juego en las vistas de Rankings."""
    live_matches, awaiting_matches = current_live_matches()
    return {
        "live_matches": live_matches,
        "awaiting_matches": awaiting_matches,
        "has_live_matches": bool(live_matches) or bool(awaiting_matches),
    }


class StatsView(LoginRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "stats/stats.html",
            {
                "kpis": kpis(request.user),
                "donut": donut(request.user.id),
            },
        )


class ChartDataView(LoginRequiredMixin, View):
    def get(self, request):
        h = per_player_history()
        users = User.objects.in_bulk(list(h.keys()))
        players = {
            pid: {
                "name": u.name,
                "initials": u.initials,
                "hue": (ord(str(pid)[-1]) * 47) % 360,
                "avatar_url": u.avatar.url if u.avatar else None,
            }
            for pid, u in users.items()
        }
        return JsonResponse({"history": h, "me": request.user.id, "players": players})


class RankingsView(LoginRequiredMixin, View):
    VALID_TABS = ("general", "sede", "puesto", "dept")
    TAB_LABELS = {
        "general": "Clasificación",
        "sede": "Sede",
        "puesto": "Puesto",
        "dept": "Departamento",
    }

    def get(self, request):
        tab = request.GET.get("tab", "general")
        if tab not in self.VALID_TABS:
            tab = "general"
        ctx = {
            "tab": tab,
            "tabs": [(k, self.TAB_LABELS[k]) for k in self.VALID_TABS],
        }
        if tab == "general":
            ctx.update(build_general_context(request.user, request.GET.get("scope")))
        else:
            rows = group_standings(tab)
            my_group = getattr(request.user, tab, "") or "__none__"
            top_ids = [r.top_user_id for r in rows if r.top_user_id]
            top_users = User.objects.in_bulk(top_ids) if top_ids else {}
            ctx.update(
                {
                    "rows": rows,
                    "my_group": my_group,
                    "top_users": top_users,
                }
            )
        ctx.update(_live_context())
        return render(request, "stats/rankings.html", ctx)


class HistoryView(LoginRequiredMixin, View):
    def get(self, request):
        return render(request, "stats/historico.html", {"matrix": build_matrix()})


class HistoryExportView(LoginRequiredMixin, View):
    def get(self, request):
        content = render_xlsx(build_matrix())
        response = HttpResponse(
            content,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        response["Content-Disposition"] = 'attachment; filename="historico-porra-26.xlsx"'
        return response


class GroupRankingsView(LoginRequiredMixin, View):
    VALID_DIMS = ("sede", "puesto", "dept")

    def get(self, request, dim: str, key: str):
        if dim not in self.VALID_DIMS:
            raise Http404("Dimensión desconocida")
        labels = dict(CHOICES_BY_DIMENSION[dim])
        if key not in labels:
            raise Http404("Grupo desconocido")
        player_ids = list(
            User.objects.filter(is_active=True, is_jugador=True, **{dim: key}).values_list(
                "id", flat=True
            )
        )
        ctx = build_general_context(request.user, request.GET.get("scope"), player_ids=player_ids)
        ctx.update(
            {
                "dim": dim,
                "dim_label": RankingsView.TAB_LABELS[dim],
                "group_label": labels[key],
                "group_key": key,
                "player_count": len(player_ids),
            }
        )
        ctx.update(_live_context())
        return render(request, "stats/rankings_group.html", ctx)
```

- [ ] **Step 4: Verificar que pasan los tests nuevos**

```bash
pytest stats/tests/test_rankings_view_live.py -v
```

Esperado: 6 passed (test parametrizado con 4 tabs + 2 sueltos).

- [ ] **Step 5: Commit**

```bash
git add stats/views.py stats/tests/test_rankings_view_live.py
git commit -m "feat(rankings): vistas inyectan live_matches/awaiting_matches al contexto"
```

---

## Task 5: Partial `_live_matches_strip.html`

**Files:**
- Create: `templates/partials/_live_matches_strip.html`

(Sin test directo — se cubre en Task 6 con un render-test sobre `rankings.html`.)

- [ ] **Step 1: Crear el partial**

`templates/partials/_live_matches_strip.html`:

```django
{% load competition_extras %}
{# Banda superior con los partidos en juego y los pendientes de oficial.
   Espera del contexto: live_matches, awaiting_matches.
   Siempre se renderiza; si no hay nada, muestra un placeholder. #}
<section class="glass rise live-strip" aria-label="Partidos en juego">
  <header class="live-strip__head">
    <span class="eyebrow">EN JUEGO{% with total=live_matches|length|add:awaiting_matches|length %}{% if total %} · {{ total }}{% endif %}{% endwith %}</span>
  </header>

  {% if live_matches or awaiting_matches %}
    <ul class="live-strip__list">
      {% for m in live_matches %}
        <li class="live-strip__chip{% if not m.live_score %} live-strip__chip--pending{% endif %}">
          <div class="live-strip__teams">
            <span class="live-strip__team">
              <span class="team-flag">{{ m.home.flag }}</span>
              <strong class="live-strip__code mono">{{ m.home.code }}</strong>
            </span>
            {% if m.live_score %}
              <span class="live-strip__score">
                <span class="score-bubble">{{ m.live_score.home_score }}</span>
                <span class="score-sep live-colon">:</span>
                <span class="score-bubble">{{ m.live_score.away_score }}</span>
              </span>
            {% else %}
              <span class="match-vs display">VS</span>
            {% endif %}
            <span class="live-strip__team">
              <span class="team-flag">{{ m.away.flag }}</span>
              <strong class="live-strip__code mono">{{ m.away.code }}</strong>
            </span>
          </div>
          <span class="live-strip__foot mono">
            {% if m.live_score %}
              {% if m.live_score.period == "HT" %}Descanso
              {% elif m.live_score.period == "ET" %}Prórroga{% if m.live_score.minute %} {{ m.live_score.minute }}'{% endif %}
              {% elif m.live_score.period == "PEN" %}Penaltis
              {% elif m.live_score.period == "1H" %}1ª parte{% if m.live_score.minute %} {{ m.live_score.minute }}'{% endif %}
              {% elif m.live_score.period == "2H" %}2ª parte{% if m.live_score.minute %} {{ m.live_score.minute }}'{% endif %}
              {% else %}{{ m.live_score.get_period_display }}{% endif %}
            {% else %}
              Esperando marcador
            {% endif %}
          </span>
        </li>
      {% endfor %}
      {% for m in awaiting_matches %}
        <li class="live-strip__chip live-strip__chip--awaiting">
          <div class="live-strip__teams">
            <span class="live-strip__team">
              <span class="team-flag">{{ m.home.flag }}</span>
              <strong class="live-strip__code mono">{{ m.home.code }}</strong>
            </span>
            <span class="live-strip__score">
              <span class="score-bubble">{{ m.live_score.home_score }}</span>
              <span class="score-sep">:</span>
              <span class="score-bubble">{{ m.live_score.away_score }}</span>
            </span>
            <span class="live-strip__team">
              <span class="team-flag">{{ m.away.flag }}</span>
              <strong class="live-strip__code mono">{{ m.away.code }}</strong>
            </span>
          </div>
          <span class="live-strip__foot mono">Pendiente oficial</span>
        </li>
      {% endfor %}
    </ul>
  {% else %}
    <p class="live-strip__empty">No hay partidos en juego ahora mismo.</p>
  {% endif %}
</section>
```

> Nota a quien implemente: las secuencias `ª` y `ó` arriba son escapes de markdown — en el archivo `.html` deben aparecer como caracteres reales (`ª`, `ó`). Comprueba el archivo tras grabarlo y arregla si tu editor los escapó.

- [ ] **Step 2: Commit**

```bash
git add templates/partials/_live_matches_strip.html
git commit -m "feat(rankings): partial live_matches_strip con chips de partido"
```

---

## Task 6: Integrar la banda + auto-refresh en `rankings.html`

**Files:**
- Modify: `templates/stats/rankings.html`
- Test: `stats/tests/test_rankings_template.py` (nuevo)

- [ ] **Step 1: Escribir los tests que fallan**

Crear `stats/tests/test_rankings_template.py`:

```python
"""Tests de render para la banda de partidos en juego en Rankings."""

from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.models import LiveScore, Team
from competition.tests.factories import MatchFactory, RoundFactory


@pytest.mark.django_db
def test_live_strip_renders_match_with_score(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    home = Team.objects.create(code="ESP", name="España", flag="🇪🇸")
    away = Team.objects.create(code="FRA", name="Francia", flag="🇫🇷")
    m = MatchFactory(round=grp, home=home, away=away, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=2, away_score=1, period="2H", minute=70)

    res = client.get(reverse("stats:rankings"))
    html = res.content.decode()

    assert "live-strip" in html
    assert "EN JUEGO" in html
    assert "ESP" in html and "FRA" in html
    assert ">2<" in html and ">1<" in html  # los score-bubbles


@pytest.mark.django_db
def test_live_strip_renders_empty_placeholder(client):
    user = UserFactory()
    client.force_login(user)
    RoundFactory(id="groups", points=3, order=1)

    res = client.get(reverse("stats:rankings"))

    assert "No hay partidos en juego ahora mismo." in res.content.decode()


@pytest.mark.django_db
def test_live_strip_renders_awaiting_chip(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    home = Team.objects.create(code="ARG", name="Argentina", flag="🇦🇷")
    away = Team.objects.create(code="BRA", name="Brasil", flag="🇧🇷")
    m = MatchFactory(round=grp, home=home, away=away, kickoff=timezone.now() - timedelta(hours=2))
    LiveScore.objects.create(match=m, home_score=1, away_score=1, period="FT", minute=95)

    res = client.get(reverse("stats:rankings"))
    html = res.content.decode()

    assert "live-strip__chip--awaiting" in html
    assert "Pendiente oficial" in html


@pytest.mark.django_db
def test_autorefresh_script_only_when_live(client):
    user = UserFactory()
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    m = MatchFactory(round=grp, kickoff=timezone.now() - timedelta(minutes=10))
    LiveScore.objects.create(match=m, home_score=0, away_score=0, period="1H", minute=5)

    res_live = client.get(reverse("stats:rankings"))
    assert b"live-autorefresh" in res_live.content

    m.delete()  # ya no quedan live
    res_calm = client.get(reverse("stats:rankings"))
    assert b"live-autorefresh" not in res_calm.content
```

- [ ] **Step 2: Verificar que fallan**

```bash
pytest stats/tests/test_rankings_template.py -v
```

Esperado: todos fallan (no se renderiza la banda ni el script).

- [ ] **Step 3: Modificar `templates/stats/rankings.html`**

Insertar el partial justo después del bloque `<nav class="glass rise rankings-tabs">...</nav>` y añadir el bloque de scripts al final. El archivo completo queda así:

```django
{% extends "base.html" %}
{% load icons avatar_extras %}
{% block main %}
<header class="rise rankings-header">
  <div>
    <div class="eyebrow">MUNDIAL 2026</div>
    <h1 class="display rankings-title">Rankings</h1>
  </div>
  <a class="chip" href="{% url 'stats:historico' %}">Histórico →</a>
</header>

<nav class="glass rise rankings-tabs">
  {% for key, label in tabs %}
    <a href="?tab={{ key }}" class="nav-item rankings-tabs__item{% if key == tab %} is-active{% endif %}">{{ label }}</a>
  {% endfor %}
</nav>

{% include "partials/_live_matches_strip.html" %}

{% if tab == "general" %}
  <div class="rankings-clas">
    <div class="rankings-clas__col">
      <section class="glass leaderboard rankings-clas__board">
        <header class="leaderboard-header">
          <div style="display:flex;align-items:center;gap:9px">
            {% icon "trophy" width=18 height=18 %}
            <h2 class="display" style="font-size:16px;margin:0">General</h2>
          </div>
          {% if my_rank %}<span class="chip chip-accent">Tú · {% if my_is_tied %}=#{% else %}#{% endif %}{{ my_rank }}</span>{% endif %}
        </header>
        {% include "partials/_leaderboard_panel.html" with rows=standings users=standings_users me=request.user max_pts=max_pts %}
      </section>
    </div>
    <div class="rankings-clas__col rankings-clas__col--scope">
      <section class="glass leaderboard rankings-clas__board">
        <header class="leaderboard-header">
          <div style="display:flex;align-items:center;gap:9px">
            {% icon "trophy" width=18 height=18 %}
            <h2 class="display" style="font-size:16px;margin:0">{{ scope_label|default:"Jornada" }}</h2>
          </div>
          {% if scope_my_rank %}<span class="chip chip-accent">Tú · {% if scope_my_is_tied %}=#{% else %}#{% endif %}{{ scope_my_rank }}</span>{% endif %}
        </header>
        {% include "partials/_leaderboard_panel.html" with rows=scope_standings users=standings_users me=request.user max_pts=scope_max_pts %}
      </section>
      {% if md_options %}
      <nav class="rankings-md-selector glass" aria-label="Selector de jornadas">
        <span class="eyebrow" style="font-size:9px;padding:0 4px 4px">Jornadas</span>
        {% for o in md_options %}
          <a href="?tab=general&scope={{ o.key }}"
             class="chip rankings-md-selector__item{% if o.is_active %} chip-open is-active{% endif %}"
             style="text-decoration:none">
            {{ o.label }}
          </a>
        {% endfor %}
      </nav>
      {% endif %}
    </div>
  </div>
{% else %}
  <div class="glass rise table-scroll" style="border-radius:22px">
    <div class="table-row" style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.18em;border-bottom:1px solid var(--border)">
      <span>#</span><span>Grupo</span><span>Jugadores</span><span>Total</span><span>Media</span><span>Líder</span>
    </div>
    <div class="stagger">
    {% for r in rows %}
      {% if r.key == "__none__" %}
      <div class="table-row" style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;align-items:center;border-bottom:1px solid var(--border);opacity:0.55;">
        <span class="mono" style="font-size:13px;color:var(--text-faint)">{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position|default_if_none:"" }}{% endif %}</span>
        <strong style="font-size:14px">{{ r.label }}</strong>
        <span class="mono" style="font-size:13px">{{ r.players }}</span>
        <span class="mono" style="font-size:13px">{{ r.total }} pts</span>
        <span class="display" style="font-size:22px">{{ r.avg|floatformat:1 }}</span>
        <div style="display:flex;align-items:center;gap:8px">
          {% if r.top_name %}
            {% include "partials/_avatar.html" with u=top_users|get_item:r.top_user_id size=28 %}
            <strong style="font-size:13px">{{ r.top_name }}{% if r.top_tied_count > 1 %} +{{ r.top_tied_count|add:"-1" }}{% endif %}</strong>
            <span class="chip" style="padding:0 6px;font-size:10px">{{ r.top_pts }} pts</span>
          {% else %}
            <span style="color:var(--text-faint);font-size:12px">sin jugadores</span>
          {% endif %}
        </div>
      </div>
      {% else %}
      <a href="{% url 'stats:rankings_group' dim=tab key=r.key %}" class="table-row" style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;align-items:center;border-bottom:1px solid var(--border);text-decoration:none;color:inherit;{% if r.key == my_group %}background:oklch(from var(--accent) l c h / 0.12);{% endif %}">
        <span class="mono" style="font-size:13px;color:var(--text-faint)">{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position|default_if_none:"" }}{% endif %}</span>
        <strong style="font-size:14px">{{ r.label }}{% if r.key == my_group %} · tú{% endif %}</strong>
        <span class="mono" style="font-size:13px">{{ r.players }}</span>
        <span class="mono" style="font-size:13px">{{ r.total }} pts</span>
        <span class="display" style="font-size:22px">{{ r.avg|floatformat:1 }}</span>
        <div style="display:flex;align-items:center;gap:8px">
          {% if r.top_name %}
            {% include "partials/_avatar.html" with u=top_users|get_item:r.top_user_id size=28 %}
            <strong style="font-size:13px">{{ r.top_name }}{% if r.top_tied_count > 1 %} +{{ r.top_tied_count|add:"-1" }}{% endif %}</strong>
            <span class="chip" style="padding:0 6px;font-size:10px">{{ r.top_pts }} pts</span>
          {% else %}
            <span style="color:var(--text-faint);font-size:12px">sin jugadores</span>
          {% endif %}
        </div>
      </a>
      {% endif %}
    {% empty %}
      <p style="padding:18px;color:var(--text-faint)">Aún no hay jugadores en esta dimensión.</p>
    {% endfor %}
    </div>
  </div>
{% endif %}
{% endblock %}

{% block scripts %}
{% if has_live_matches %}
<script id="live-autorefresh" type="module">
  // Recarga la página cada 60s cuando hay partidos en juego para que el
  // marcador parcial y la clasificación live se vean al vuelo. Pausa si el
  // usuario tiene un modal abierto o la pestaña está oculta.
  const INTERVAL_MS = 60_000;
  setInterval(() => {
    if (document.hidden) return;
    if (document.querySelector(".ovl")) return;
    window.location.reload();
  }, INTERVAL_MS);
</script>
{% endif %}
{% endblock %}
```

- [ ] **Step 4: Verificar que pasan los tests**

```bash
pytest stats/tests/test_rankings_template.py -v
```

Esperado: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add templates/stats/rankings.html stats/tests/test_rankings_template.py
git commit -m "feat(rankings): banda partidos en juego + auto-refresh en rankings.html"
```

---

## Task 7: Banda + auto-refresh en `rankings_group.html`

**Files:**
- Read first: `templates/stats/rankings_group.html`
- Modify: `templates/stats/rankings_group.html`
- Test: añadir un caso en `stats/tests/test_rankings_template.py`

- [ ] **Step 1: Añadir un test que cubre el detalle de grupo**

Añadir al final de `stats/tests/test_rankings_template.py`:

```python
@pytest.mark.django_db
def test_group_detail_renders_live_strip(client):
    user = UserFactory(sede="vigo")
    client.force_login(user)

    grp = RoundFactory(id="groups", points=3, order=1)
    home = Team.objects.create(code="POR", name="Portugal", flag="🇵🇹")
    away = Team.objects.create(code="GER", name="Alemania", flag="🇩🇪")
    m = MatchFactory(round=grp, home=home, away=away, kickoff=timezone.now() - timedelta(minutes=15))
    LiveScore.objects.create(match=m, home_score=1, away_score=2, period="2H", minute=65)

    res = client.get(reverse("stats:rankings_group", kwargs={"dim": "sede", "key": "vigo"}))
    html = res.content.decode()

    assert "live-strip" in html
    assert "POR" in html and "GER" in html
    assert b"live-autorefresh" in res.content
```

- [ ] **Step 2: Verificar que falla**

```bash
pytest stats/tests/test_rankings_template.py::test_group_detail_renders_live_strip -v
```

- [ ] **Step 3: Leer el template actual**

```bash
cat templates/stats/rankings_group.html
```

Necesitas saber dónde insertar el `{% include %}` y cómo está el `{% block scripts %}` (si existe).

- [ ] **Step 4: Modificar `templates/stats/rankings_group.html`**

Insertar `{% include "partials/_live_matches_strip.html" %}` justo después de la cabecera/breadcrumb (antes del bloque principal de contenido). Añadir al final del template:

```django
{% block scripts %}
{% if has_live_matches %}
<script id="live-autorefresh" type="module">
  const INTERVAL_MS = 60_000;
  setInterval(() => {
    if (document.hidden) return;
    if (document.querySelector(".ovl")) return;
    window.location.reload();
  }, INTERVAL_MS);
</script>
{% endif %}
{% endblock %}
```

Si el template ya tiene `{% block scripts %}`, añadir el `{% if has_live_matches %}...{% endif %}` dentro respetando el resto del bloque.

- [ ] **Step 5: Verificar que pasa**

```bash
pytest stats/tests/test_rankings_template.py::test_group_detail_renders_live_strip -v
```

- [ ] **Step 6: Commit**

```bash
git add templates/stats/rankings_group.html stats/tests/test_rankings_template.py
git commit -m "feat(rankings): banda live + auto-refresh en detalle de grupo"
```

---

## Task 8: CSS para `.live-strip`

**Files:**
- Modify: `static/css/styles.css`

(Sin tests automatizados — verificación manual al final.)

- [ ] **Step 1: Localizar dónde insertar las reglas**

Las reglas relacionadas con marcadores y chips de partido están entre las líneas ~290 y ~400. Añadimos un bloque cohesivo al final del archivo, marcado con un comentario para que sea fácil encontrarlo.

- [ ] **Step 2: Añadir el CSS**

Append al final de `static/css/styles.css`:

```css
/* === Banda "EN JUEGO" en Rankings ===================================== */
.live-strip {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 14px 18px;
  margin: 16px 0;
  border-radius: 22px;
}
.live-strip__head { display: flex; align-items: center; justify-content: space-between; }
.live-strip__list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 12px;
  overflow-x: auto;
  scroll-snap-type: x mandatory;
  -webkit-overflow-scrolling: touch;
}
.live-strip__chip {
  flex: 0 0 auto;
  scroll-snap-align: start;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  padding: 10px 14px;
  border-radius: 16px;
  background: oklch(from var(--accent) l c h / 0.06);
  border: 1px solid var(--border);
  min-width: 220px;
}
.live-strip__chip--awaiting {
  background: oklch(from var(--c-yellow) l c h / 0.08);
  border-color: oklch(from var(--c-yellow) l c h / 0.4);
}
.live-strip__chip--pending {
  background: transparent;
  border-style: dashed;
}
.live-strip__teams { display: flex; align-items: center; gap: 10px; }
.live-strip__team { display: flex; align-items: center; gap: 6px; }
.live-strip__team .team-flag { font-size: 22px; }
.live-strip__code { font-size: 13px; letter-spacing: 0.05em; }
.live-strip__score { display: flex; align-items: center; gap: 4px; }
.live-strip__score .score-bubble {
  min-width: 30px;
  height: 36px;
  font-size: 18px;
  padding: 0 6px;
}
.live-strip__foot { font-size: 11px; color: var(--text-dim); letter-spacing: 0.04em; }
.live-strip__chip--awaiting .live-strip__foot { color: var(--c-yellow); }
.live-strip__empty { margin: 0; color: var(--text-faint); font-size: 13px; }
```

- [ ] **Step 3: Verificación manual rápida**

Lanzar el servidor:

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python manage.py runserver
```

Abrir `http://localhost:8000/stats/rankings/` con un superuser. Sin partidos live, la banda debe verse con su placeholder. Cambiar entre las 4 pestañas (`?tab=sede`, etc.) y verificar que la banda aparece en todas.

Para probar con datos:

```bash
DJANGO_SETTINGS_MODULE=porra26.settings.dev python manage.py shell -c "
from django.utils import timezone
from datetime import timedelta
from competition.models import Match, LiveScore
m = Match.objects.filter(kickoff__lte=timezone.now(), result_home__isnull=True).first()
if m:
    LiveScore.objects.update_or_create(match=m, defaults=dict(home_score=2, away_score=1, period='2H', minute=70))
    print('LiveScore creado en', m)
else:
    print('No hay candidato — pon kickoff de un Match en el pasado a mano y vuelve a correr')
"
```

Recargar la página y comprobar que aparece el chip con el marcador.

- [ ] **Step 4: Commit**

```bash
git add static/css/styles.css
git commit -m "feat(rankings): estilos para la banda live-strip"
```

---

## Task 9: Smoke test final + PR

- [ ] **Step 1: Ejecutar TODA la suite**

```bash
pytest -x
```

Esperado: todo verde. Si algún test antiguo falla porque suponía `standings()` (oficial) en stats, ajustarlo: típicamente borrar el `LiveScore` que se haya colado en el test, o pasar a comparar `live_pts` explícitamente.

- [ ] **Step 2: `ruff` para confirmar estilo**

```bash
ruff check . && ruff format --check .
```

Si hay errores, `ruff format .` y volver a hacer `git add`+`commit -m "style: ruff format"`.

- [ ] **Step 3: Push de la rama y abrir PR**

```bash
git push -u origin <rama-actual>
gh pr create --title "feat(rankings): banda partidos en juego + tablas live" --body "$(cat <<'EOF'
## Summary
- Banda superior con partidos en juego (marcador parcial) y "pendiente oficial" en todas las pestañas de Rankings y en el detalle por grupo.
- Las tablas General, Scope (jornada), Sede, Puesto y Departamento se calculan con \`live_standings()\`: las posiciones reflejan en directo los marcadores parciales.
- Auto-refresh 60s (con guards \`document.hidden\`/\`.ovl\`) cuando hay partidos live o awaiting.

Spec: \`docs/superpowers/specs/2026-06-11-rankings-live-strip-design.md\`.
Plan: \`docs/superpowers/plans/2026-06-11-rankings-live-strip.md\`.

## Test plan
- [x] Tests unitarios y de vista para helper + servicios + plantillas.
- [ ] Smoke manual: abrir /stats/rankings/?tab=general|sede|puesto|dept con y sin LiveScore.
- [ ] Smoke manual: chip awaiting al setear LiveScore.period='FT'.
- [ ] Smoke manual: auto-refresh tras 60s, pausado con modal abierto.
EOF
)"
```

- [ ] **Step 4: Esperar CI verde y mergear**

Una vez verde, `gh pr merge --squash --delete-branch` (o hacerlo desde la UI). Railway despliega desde main.

---

## Resumen de verificación

| Capa | Cómo se verifica |
|------|------------------|
| Helper `current_live_matches` | `pytest competition/tests/test_live_view_service.py` |
| `rankings_context` live | `pytest stats/tests/test_rankings_context_live.py` |
| `group_standings` live | `pytest stats/tests/test_group_standings.py` |
| Vistas inyectan contexto | `pytest stats/tests/test_rankings_view_live.py` |
| Plantillas renderizan banda | `pytest stats/tests/test_rankings_template.py` |
| CSS | smoke manual |
| Regresión general | `pytest -x` |
