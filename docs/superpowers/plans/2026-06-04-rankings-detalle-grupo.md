# Rankings detalle por grupo — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans (inline) o superpowers:subagent-driven-development. Cada paso usa checkboxes (`- [ ]`).

**Spec:** `docs/superpowers/specs/2026-06-04-rankings-detalle-grupo-design.md`
**Fecha:** 2026-06-04

**Goal:** Permitir pulsar una fila de Sede/Puesto/Departamento en `/stats/rankings/` y aterrizar en una clasificación dedicada (general + por jornada + podio) restringida al grupo.

**Architecture:** Extender `standings()` con `player_ids` opcional. Extraer un helper `build_general_context` para compartir lógica entre `RankingsView` (tab general) y la nueva `GroupRankingsView`. Nueva URL `/stats/rankings/<dim>/<key>/`, nuevo template `rankings_group.html` (espejo del tab general con breadcrumb). Filas de las tablas agregadas se convierten en enlaces.

**Tech Stack:** Django 5, pytest-django, plantillas Django, HTML/CSS existentes.

**Convención:** TDD por paso. `pytest -q` debe pasar al final de cada paso. Commits estilo conventional.

---

## Paso 1 — Extender `standings()` con `player_ids`

**Files:**
- Modify: `competition/services/standings.py`
- Test: `competition/tests/test_standings.py`

- [ ] **Step 1.1: Tests primero**

Añadir al final de `competition/tests/test_standings.py`:

```python
@pytest.mark.django_db
def test_standings_player_ids_filters_to_subset():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="a@e.com")
    luis = UserFactory(name="Luis", email="l@e.com")
    zoe = UserFactory(name="Zoe", email="z@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=ana, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=luis, match=m1, home=0, away=1, earned=0)
    PredictionFactory(player=zoe, match=m1, home=1, away=0, earned=3)

    rows = standings(player_ids=[ana.id, zoe.id])
    ids = [r.player_id for r in rows]
    assert ana.id in ids
    assert zoe.id in ids
    assert luis.id not in ids


@pytest.mark.django_db
def test_standings_player_ids_recomputes_positions_from_one():
    groups = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    leader = UserFactory(name="Leader", email="lead@e.com")
    mid = UserFactory(name="Mid", email="mid@e.com")
    bottom = UserFactory(name="Bot", email="bot@e.com")
    m1 = MatchFactory(round=groups, result_home=1, result_away=0)
    PredictionFactory(player=leader, match=m1, home=1, away=0, earned=3)
    PredictionFactory(player=mid, match=m1, home=1, away=2, earned=1)
    PredictionFactory(player=bottom, match=m1, home=0, away=1, earned=0)

    rows = standings(player_ids=[mid.id, bottom.id])
    by_name = {r.name: r for r in rows}
    assert by_name["Mid"].position == 1
    assert by_name["Bot"].position == 2


@pytest.mark.django_db
def test_standings_player_ids_empty_returns_empty():
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    UserFactory(name="Ana", email="a@e.com")
    rows = standings(player_ids=[])
    assert rows == []


@pytest.mark.django_db
def test_standings_player_ids_combined_with_scope():
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    ana = UserFactory(name="Ana", email="a@e.com")
    luis = UserFactory(name="Luis", email="l@e.com")
    m_j1 = MatchFactory(round=grp, matchday=1, result_home=1, result_away=0)
    m_j2 = MatchFactory(round=grp, matchday=2, result_home=0, result_away=0)
    PredictionFactory(player=ana, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=ana, match=m_j2, home=0, away=0, earned=3)
    PredictionFactory(player=luis, match=m_j1, home=1, away=0, earned=3)
    PredictionFactory(player=luis, match=m_j2, home=0, away=0, earned=3)

    rows = standings(round_id="groups", matchday=1, player_ids=[ana.id])
    assert len(rows) == 1
    assert rows[0].name == "Ana"
    assert rows[0].pts == 3


@pytest.mark.django_db
def test_standings_player_ids_includes_zero_pts_players():
    """Jugadores del grupo sin predicciones siguen apareciendo con 0 pts."""
    RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    a = UserFactory(name="A", email="a@e.com")
    b = UserFactory(name="B", email="b@e.com")
    rows = standings(player_ids=[a.id, b.id])
    ids = {r.player_id for r in rows}
    assert ids == {a.id, b.id}
    assert all(r.pts == 0 for r in rows)
```

- [ ] **Step 1.2: Ejecutar tests — deben fallar**

Run: `pytest competition/tests/test_standings.py -q -k "player_ids"`
Expected: 5 FAILED con `TypeError: standings() got an unexpected keyword argument 'player_ids'`.

- [ ] **Step 1.3: Implementar `player_ids` en `standings()`**

En `competition/services/standings.py`, sustituir la firma y el cuerpo relevante:

```python
from collections.abc import Iterable


def standings(
    round_id: str | None = None,
    matchday: int | None = None,
    player_ids: Iterable[int] | None = None,
) -> list[StandingRow]:
    """Clasificación general, opcionalmente acotada por ronda/jornada/subconjunto de jugadores.

    Con `round_id`/`matchday` solo se suman puntos cuyo partido cae dentro
    del scope. Con `player_ids`, los resultados se limitan a esos jugadores
    y las posiciones se recalculan desde 1.
    """
    if player_ids is not None:
        player_ids = list(player_ids)
        if not player_ids:
            return []

    scoped = round_id is not None or matchday is not None
    qs = Prediction.objects.filter(
        player__is_active=True, player__is_jugador=True, earned__isnull=False
    )
    if round_id is not None:
        qs = qs.filter(match__round_id=round_id)
    if matchday is not None:
        qs = qs.filter(match__matchday=matchday)
    if player_ids is not None:
        qs = qs.filter(player_id__in=player_ids)

    rows = list(
        qs.values("player_id", "player__name", "player__email").annotate(
            pts=Sum("earned"),
            hits=Count("id", filter=Q(earned__gt=0)),
            exact_hits=Count("id", filter=Q(earned=F("match__exact_points_applied"))),
        )
    )

    seen = {r["player_id"] for r in rows}
    extras_qs = User.objects.filter(is_active=True, is_jugador=True).exclude(id__in=seen)
    if player_ids is not None:
        extras_qs = extras_qs.filter(id__in=player_ids)
    extras = [
        {
            "player_id": u.id,
            "player__name": u.name,
            "player__email": u.email,
            "pts": 0,
            "hits": 0,
            "exact_hits": 0,
        }
        for u in extras_qs
    ]
    merged = list(rows) + extras
    # ... resto del cuerpo SIN CAMBIOS (sort + streaks/trends + assembly)
```

El resto de la función (sort por puntos, `_compute_streaks`, `_compute_trends`, assembly de `StandingRow`) queda exactamente igual. Solo se inserta el filtrado por `player_ids` en el queryset y en el padding de extras, y se añade el early-return para lista vacía.

- [ ] **Step 1.4: Ejecutar tests — deben pasar**

Run: `pytest competition/tests/test_standings.py -q`
Expected: todos los tests del módulo (los antiguos + los 5 nuevos) PASS.

- [ ] **Step 1.5: Suite completa**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 1.6: Commit**

```bash
git add competition/services/standings.py competition/tests/test_standings.py
git commit -m "feat(standings): filtrar standings por player_ids opcional"
```

---

## Paso 2 — Extraer helper `build_general_context`

**Files:**
- Create: `stats/services/rankings_context.py`
- Modify: `stats/views.py` (rama `tab == "general"` de `RankingsView`)

Refactor puro: no se cambian comportamientos, los tests existentes deben seguir verdes sin tocarse.

- [ ] **Step 2.1: Crear `stats/services/rankings_context.py`**

```python
from collections.abc import Iterable

from accounts.models import User
from competition.services.standings import standings
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
    """
    player_ids_list = list(player_ids) if player_ids is not None else None

    rows = standings(player_ids=player_ids_list)[:50]
    my_row = next((r for r in rows if r.player_id == user.id), None)
    my_rank = my_row.position if my_row else None
    my_is_tied = bool(my_row and my_row.is_tied)
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
        scope_rows = standings(
            round_id=scope.round_id,
            matchday=scope.matchday,
            player_ids=player_ids_list,
        )[:50]
        scope_my_row = next((r for r in scope_rows if r.player_id == user.id), None)
        scope_my_rank = scope_my_row.position if scope_my_row else None
        scope_my_is_tied = bool(scope_my_row and scope_my_row.is_tied)
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

- [ ] **Step 2.2: Sustituir bloque en `stats/views.py`**

En `RankingsView.get`, sustituir el bloque completo `if tab == "general":` (líneas ~63-109) por:

```python
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
```

Y añadir el import al principio del fichero:

```python
from stats.services.rankings_context import build_general_context
```

Quitar los imports que dejen de usarse en `stats/views.py`:
- `from stats.services.matchday_options import current_option, matchday_options, parse_scope_key` ya no es necesario aquí (lo usa el nuevo helper).
- `standings` puede quedarse o irse según si se usa en otra vista del módulo; verificar y eliminar si queda huérfano.

- [ ] **Step 2.3: Suite completa**

Run: `pytest -q`
Expected: 0 failed (los tests antiguos de rankings deben seguir verdes — esto valida que el refactor preserva comportamiento).

- [ ] **Step 2.4: Commit**

```bash
git add stats/services/rankings_context.py stats/views.py
git commit -m "refactor(stats): extraer build_general_context para reuso entre vistas"
```

---

## Paso 3 — URL + `GroupRankingsView` (404s y skeleton)

**Files:**
- Modify: `stats/urls.py`
- Modify: `stats/views.py`
- Test: `stats/tests/test_rankings_view.py`

- [ ] **Step 3.1: Tests primero (404s)**

Añadir al final de `stats/tests/test_rankings_view.py`:

```python
@pytest.mark.django_db
def test_rankings_group_invalid_dim_returns_404(client):
    client.force_login(UserFactory())
    r = client.get("/stats/rankings/foo/bar/")
    assert r.status_code == 404


@pytest.mark.django_db
def test_rankings_group_invalid_key_returns_404(client):
    client.force_login(UserFactory())
    r = client.get("/stats/rankings/sede/atlantis/")
    assert r.status_code == 404


@pytest.mark.django_db
def test_rankings_group_requires_login(client):
    r = client.get("/stats/rankings/sede/madrid/")
    assert r.status_code == 302
```

- [ ] **Step 3.2: Ejecutar tests — deben fallar**

Run: `pytest stats/tests/test_rankings_view.py -q -k "rankings_group"`
Expected: 3 FAILED (la URL no existe → 404 de Django, pero el login redirect tampoco aplica → revisar; en cualquier caso, no pasa el test específico).

- [ ] **Step 3.3: Añadir URL**

En `stats/urls.py`:

```python
urlpatterns = [
    path("", views.StatsView.as_view(), name="dashboard"),
    path("chart-data.json", views.ChartDataView.as_view(), name="chart_data"),
    path("rankings/", views.RankingsView.as_view(), name="rankings"),
    path(
        "rankings/<slug:dim>/<slug:key>/",
        views.GroupRankingsView.as_view(),
        name="rankings_group",
    ),
]
```

- [ ] **Step 3.4: Implementar `GroupRankingsView` skeleton**

Al final de `stats/views.py`:

```python
from django.http import Http404

from stats.services.group_standings import CHOICES_BY_DIMENSION


class GroupRankingsView(LoginRequiredMixin, View):
    VALID_DIMS = ("sede", "puesto", "dept")

    def get(self, request, dim: str, key: str):
        if dim not in self.VALID_DIMS:
            raise Http404("Dimensión desconocida")
        labels = dict(CHOICES_BY_DIMENSION[dim])
        if key not in labels:
            raise Http404("Grupo desconocido")
        player_ids = list(
            User.objects.filter(is_active=True, is_jugador=True, **{dim: key})
            .values_list("id", flat=True)
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
        return render(request, "stats/rankings_group.html", ctx)
```

(Nota: en Step 3.4 el template aún no existe; los tests de 3.1 no comprueban render, solo statuses. El render fallaría sin el template, pero como los 404 se levantan antes y el redirect de login también es antes, los 3 tests pasan. El test que renderiza el template viene en el Paso 4.)

- [ ] **Step 3.5: Ejecutar tests**

Run: `pytest stats/tests/test_rankings_view.py -q -k "rankings_group"`
Expected: 3 PASS.

- [ ] **Step 3.6: Commit**

```bash
git add stats/urls.py stats/views.py stats/tests/test_rankings_view.py
git commit -m "feat(rankings): URL y vista esqueleto para detalle de grupo"
```

---

## Paso 4 — Template `rankings_group.html` + tests de contenido

**Files:**
- Create: `templates/stats/rankings_group.html`
- Test: `stats/tests/test_rankings_view.py`

- [ ] **Step 4.1: Tests primero (render + contenido)**

Añadir a `stats/tests/test_rankings_view.py`:

```python
@pytest.mark.django_db
def test_rankings_group_empty_group_returns_200(client):
    client.force_login(UserFactory(sede=""))
    r = client.get("/stats/rankings/sede/barcelona/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "Barcelona" in body
    assert "Aún no hay jugadores" in body


@pytest.mark.django_db
def test_rankings_group_renders_podium_for_group_members(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    madrid_top = UserFactory(name="MaTop", email="mt@e.com", sede="madrid")
    madrid_mid = UserFactory(name="MaMid", email="mm@e.com", sede="madrid")
    other = UserFactory(name="Other", email="o@e.com", sede="vigo")
    PredictionFactory(player=madrid_top, match=m, home=1, away=0, earned=3)
    PredictionFactory(player=madrid_mid, match=m, home=1, away=2, earned=1)
    PredictionFactory(player=other, match=m, home=1, away=0, earned=3)

    client.force_login(madrid_top)
    r = client.get("/stats/rankings/sede/madrid/")
    assert r.status_code == 200
    body = r.content.decode()
    assert "podium-slot--1" in body
    assert "MaTop" in body
    # El jugador fuera del grupo NO aparece
    assert "Other" not in body


@pytest.mark.django_db
def test_rankings_group_breadcrumb_links_back_to_tab(client):
    client.force_login(UserFactory(puesto="desarrollo"))
    r = client.get("/stats/rankings/puesto/desarrollo/")
    assert r.status_code == 200
    body = r.content.decode()
    assert 'href="/stats/rankings/?tab=puesto"' in body
    assert "Desarrollo" in body


@pytest.mark.django_db
def test_rankings_group_chip_present_when_user_in_group(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    me = UserFactory(name="Me", email="me@e.com", sede="madrid")
    PredictionFactory(player=me, match=m, home=1, away=0, earned=3)
    client.force_login(me)
    r = client.get("/stats/rankings/sede/madrid/")
    assert "Tú · " in r.content.decode()


@pytest.mark.django_db
def test_rankings_group_chip_absent_when_user_not_in_group(client):
    grp = RoundFactory(id="groups", points=3, label="G", short="G", order=1)
    m = MatchFactory(round=grp, result_home=1, result_away=0)
    madrid_user = UserFactory(name="Mad", email="m@e.com", sede="madrid")
    me_vigo = UserFactory(name="Me", email="me@e.com", sede="vigo")
    PredictionFactory(player=madrid_user, match=m, home=1, away=0, earned=3)
    client.force_login(me_vigo)
    r = client.get("/stats/rankings/sede/madrid/")
    assert "Tú · " not in r.content.decode()
```

- [ ] **Step 4.2: Ejecutar tests — deben fallar**

Run: `pytest stats/tests/test_rankings_view.py -q -k "rankings_group"`
Expected: los 5 nuevos FAILED con `TemplateDoesNotExist: stats/rankings_group.html`.

- [ ] **Step 4.3: Crear template**

Crear `templates/stats/rankings_group.html`:

```django
{% extends "base.html" %}
{% load icons avatar_extras %}
{% block main %}
<header class="rise" style="margin-bottom:18px">
  <div class="eyebrow">
    <a href="{% url 'stats:rankings' %}?tab={{ dim }}" style="color:inherit;text-decoration:none">← Rankings</a>
    · {{ dim_label }}
  </div>
  <h1 class="display" style="font-size:28px;margin:6px 0 4px">{{ group_label }}</h1>
  <p style="color:var(--text-dim);margin:0;max-width:560px">
    Clasificación general y por jornada de {{ group_label }} · {{ player_count }} jugador{{ player_count|pluralize:"es" }}.
  </p>
</header>

{% if player_count == 0 %}
  <section class="glass rise" style="padding:24px;border-radius:22px">
    <p style="color:var(--text-faint);margin:0">Aún no hay jugadores en {{ group_label }}.</p>
  </section>
{% else %}
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
          <a href="?scope={{ o.key }}"
             class="chip rankings-md-selector__item{% if o.is_active %} chip-open is-active{% endif %}"
             style="text-decoration:none">
            {{ o.label }}
          </a>
        {% endfor %}
      </nav>
      {% endif %}
    </div>
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 4.4: Ejecutar tests — deben pasar**

Run: `pytest stats/tests/test_rankings_view.py -q -k "rankings_group"`
Expected: los 8 tests del grupo PASS (3 del Paso 3 + 5 nuevos).

- [ ] **Step 4.5: Commit**

```bash
git add templates/stats/rankings_group.html stats/tests/test_rankings_view.py
git commit -m "feat(rankings): template rankings_group con breadcrumb y vacío explícito"
```

---

## Paso 5 — Filas clicables en `rankings.html`

**Files:**
- Modify: `templates/stats/rankings.html`
- Test: `stats/tests/test_rankings_view.py`

- [ ] **Step 5.1: Tests primero**

```python
@pytest.mark.django_db
def test_rankings_sede_tab_rows_are_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=sede")
    body = r.content.decode()
    # Cada choice de SEDE_CHOICES debería tener un enlace a su detalle
    assert 'href="/stats/rankings/sede/madrid/"' in body
    assert 'href="/stats/rankings/sede/vigo/"' in body


@pytest.mark.django_db
def test_rankings_puesto_tab_rows_are_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=puesto")
    body = r.content.decode()
    assert 'href="/stats/rankings/puesto/desarrollo/"' in body


@pytest.mark.django_db
def test_rankings_dept_tab_rows_are_links(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=dept")
    body = r.content.decode()
    assert 'href="/stats/rankings/dept/nominas/"' in body


@pytest.mark.django_db
def test_rankings_unassigned_row_is_not_a_link(client):
    # Crear un jugador sin sede para forzar la fila __none__
    UserFactory(email="orphan@e.com", sede="")
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=sede")
    body = r.content.decode()
    assert "Sin asignar" in body
    assert 'href="/stats/rankings/sede/__none__/"' not in body
```

- [ ] **Step 5.2: Ejecutar tests — deben fallar**

Run: `pytest stats/tests/test_rankings_view.py -q -k "rows_are_links or unassigned"`
Expected: 3 FAILED (no hay `href`), 1 PASS (`unassigned_row_is_not_a_link` ya pasa si la fila es `<div>`).

- [ ] **Step 5.3: Modificar `templates/stats/rankings.html`**

Sustituir el bloque del `{% for r in rows %}` del else (la tabla de grupos) por una versión que distingue entre filas reales y la fila `__none__`:

```django
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
```

- [ ] **Step 5.4: Ejecutar tests**

Run: `pytest stats/tests/test_rankings_view.py -q -k "rows_are_links or unassigned"`
Expected: 4 PASS.

- [ ] **Step 5.5: Suite completa**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 5.6: Commit**

```bash
git add templates/stats/rankings.html stats/tests/test_rankings_view.py
git commit -m "feat(rankings): filas Sede/Puesto/Dept clicables al detalle de grupo"
```

---

## Paso 6 — Lint y verificación final

- [ ] **Step 6.1: Ruff**

Run: `ruff check . && ruff format --check .`
Expected: ✓ sin errores. Si los hay, `ruff format .` y `ruff check --fix .`.

- [ ] **Step 6.2: Tests completos**

Run: `pytest -q`
Expected: 0 failed.

- [ ] **Step 6.3: Si hubo cambios de ruff, commit**

```bash
git add -u
git commit -m "chore: ruff format"
```

(Si no hubo cambios, saltar.)

- [ ] **Step 6.4: Resumen del log**

Run: `git log --oneline main..HEAD`
Expected: 4-6 commits limpios (1 por paso + opcional ruff).

---

## Cobertura de la spec

- ✅ Spec §1 (URL/nav): Paso 3 (URL), Paso 5 (filas clicables).
- ✅ Spec §2 (`standings(player_ids=...)`): Paso 1.
- ✅ Spec §3 (`GroupRankingsView`): Paso 3 (esqueleto) + Paso 4 (integración con template).
- ✅ Spec §4 (template `rankings_group.html` con breadcrumb + estado vacío): Paso 4.
- ✅ Spec §5 (helper `build_general_context`): Paso 2.
- ✅ Spec Verificación (tests 1-10): repartidos en Pasos 1, 3, 4 y 5.
- ⚠️ Spec Verificación manual: no automatizable; queda para QA tras merge.
