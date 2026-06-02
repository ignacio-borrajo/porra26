# Rankings · pestaña General — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans para ejecutar tarea a tarea con verificación tras cada bloque.

**Goal:** Añadir una pestaña `General` a `/stats/rankings/` que reutilice la clasificación general (podio + filas) de `/competicion/`, con los mismos datos y estilo.

**Architecture:** Una sola vista (`RankingsView`) decide por `?tab=` qué payload prepara. Para `general`, llama a `competition.services.standings.standings()` exactamente igual que `CompetitionView`. El template `rankings.html` bifurca en dos render-branches: el actual (tabla por grupos) y el nuevo (include `partials/_leaderboard.html` con `max-width:440px`).

**Tech Stack:** Django 5 · Pytest · plantillas Django · CSS variables ya existentes (sin reglas nuevas).

---

### Task 1: Test failing — `?tab=general` renderiza el podio

**Files:**
- Modify: `stats/tests/test_rankings_view.py`

- [ ] **Step 1: Añadir test**

```python
@pytest.mark.django_db
def test_rankings_general_tab_renders_podium(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=general")
    assert r.status_code == 200
    # El podio del partial _leaderboard.html siempre incluye el slot #1.
    assert b"podium-slot--1" in r.content


@pytest.mark.django_db
def test_rankings_default_tab_is_general(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings"))
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content
```

Y **borrar** el test obsoleto `test_rankings_default_tab_is_sede` (pasa a estar cubierto por el nuevo `test_rankings_default_tab_is_general`).

- [ ] **Step 2: Correr y verificar que fallan los dos nuevos**

Run: `python3 -m pytest stats/tests/test_rankings_view.py -q`
Expected: 2 fails (`podium-slot--1` no aparece) + 1 fail (`test_rankings_unknown_tab_falls_back_to_sede` aún asume `sede` por defecto — se arregla en el siguiente bloque al cambiar el contenido del test).

- [ ] **Step 3: Actualizar también el test de fallback**

```python
@pytest.mark.django_db
def test_rankings_unknown_tab_falls_back_to_general(client):
    client.force_login(UserFactory())
    r = client.get(reverse("stats:rankings") + "?tab=hack")
    assert r.status_code == 200
    assert b"podium-slot--1" in r.content
```

(reemplaza el `test_rankings_unknown_tab_falls_back_to_sede` existente).

---

### Task 2: Implementar el cambio en `RankingsView`

**Files:**
- Modify: `stats/views.py`

- [ ] **Step 1: Reemplazar la clase**

```python
class RankingsView(LoginRequiredMixin, View):
    VALID_TABS = ("general", "sede", "puesto", "dept")
    TAB_LABELS = {
        "general": "General",
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
            from competition.services.standings import standings
            rows = standings()[:50]
            users_by_id = User.objects.in_bulk([r.player_id for r in rows])
            my_rank = next(
                (r.position for r in rows if r.player_id == request.user.id), None
            )
            max_pts = max((r.pts for r in rows), default=0) or 1
            ctx.update(
                {
                    "standings": rows,
                    "standings_users": users_by_id,
                    "my_rank": my_rank,
                    "max_pts": max_pts,
                }
            )
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
        return render(request, "stats/rankings.html", ctx)
```

- [ ] **Step 2: Correr tests, deben fallar todavía**

Run: `python3 -m pytest stats/tests/test_rankings_view.py -q`
Expected: los nuevos siguen fallando porque el template aún no renderiza el podio.

---

### Task 3: Bifurcar el template

**Files:**
- Modify: `templates/stats/rankings.html`

- [ ] **Step 1: Reescribir el template**

```django
{% extends "base.html" %}
{% load icons avatar_extras %}
{% block main %}
<header class="rise" style="margin-bottom:18px">
  <div class="eyebrow">MUNDIAL 2026</div>
  <h1 class="display" style="font-size:28px;margin:6px 0 4px">Rankings</h1>
  <p style="color:var(--text-dim);margin:0;max-width:560px">
    {% if tab == "general" %}
      Clasificación general · top 50 jugadores. Misma vista que la barra lateral de Competición.
    {% else %}
      Compara qué sede, puesto o departamento puntúa más en la porra. Cada fila es un grupo; orden por media de puntos por jugador.
    {% endif %}
  </p>
</header>

<nav class="glass rise" style="display:inline-flex;gap:4px;padding:6px;border-radius:14px;margin-bottom:18px">
  {% for key, label in tabs %}
    <a href="?tab={{ key }}" class="nav-item{% if key == tab %} is-active{% endif %}" style="padding:8px 16px">{{ label }}</a>
  {% endfor %}
</nav>

{% if tab == "general" %}
  <div style="max-width:440px">
    {% include "partials/_leaderboard.html" with rows=standings me=request.user users=standings_users my_rank=my_rank max_pts=max_pts %}
  </div>
{% else %}
  <div class="glass rise table-scroll" style="border-radius:22px">
    <div class="table-row" style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;font-size:11px;color:var(--text-faint);text-transform:uppercase;letter-spacing:0.18em;border-bottom:1px solid var(--border)">
      <span>#</span><span>Grupo</span><span>Jugadores</span><span>Total</span><span>Media</span><span>Líder</span>
    </div>
    <div class="stagger">
    {% for r in rows %}
      <div class="table-row" style="display:grid;grid-template-columns:60px 1fr 100px 110px 110px 1.6fr;padding:14px 18px;align-items:center;border-bottom:1px solid var(--border);{% if r.key == my_group %}background:oklch(from var(--accent) l c h / 0.12);{% endif %}{% if r.key == '__none__' %}opacity:0.55;{% endif %}">
        <span class="mono" style="font-size:13px;color:var(--text-faint)">{{ forloop.counter }}</span>
        <strong style="font-size:14px">{{ r.label }}{% if r.key == my_group %} · tú{% endif %}</strong>
        <span class="mono" style="font-size:13px">{{ r.players }}</span>
        <span class="mono" style="font-size:13px">{{ r.total }} pts</span>
        <span class="display" style="font-size:22px">{{ r.avg|floatformat:1 }}</span>
        <div style="display:flex;align-items:center;gap:8px">
          {% if r.top_name %}
            {% include "partials/_avatar.html" with u=top_users|get_item:r.top_user_id size=28 %}
            <strong style="font-size:13px">{{ r.top_name }}</strong>
            <span class="chip" style="padding:0 6px;font-size:10px">{{ r.top_pts }} pts</span>
          {% else %}
            <span style="color:var(--text-faint);font-size:12px">sin jugadores</span>
          {% endif %}
        </div>
      </div>
    {% empty %}
      <p style="padding:18px;color:var(--text-faint)">Aún no hay jugadores en esta dimensión.</p>
    {% endfor %}
    </div>
  </div>
{% endif %}
{% endblock %}
```

- [ ] **Step 2: Correr tests**

Run: `python3 -m pytest stats/tests/test_rankings_view.py -q`
Expected: PASS (los 4 tests: requires_login, default→general, accepts puesto, fallback→general, plus el nuevo de podio).

---

### Task 4: Asegurar que no rompemos los tests de otras apps

- [ ] **Step 1: Suite completa de stats + competition**

Run: `python3 -m pytest stats competition -q`
Expected: PASS en todos.

- [ ] **Step 2: Suite completa**

Run: `python3 -m pytest -q`
Expected: PASS en todos.

---

### Task 5: Verificación manual

- [ ] **Step 1: Arrancar servidor**

Run: `python3 manage.py runserver` (en otra terminal o background)

- [ ] **Step 2: Visitar `/stats/rankings/`**

Comprobar:
- Por defecto se ve el podio + filas, idéntico visualmente al sidebar de `/competicion/`.
- Las 4 pestañas (General · Sede · Puesto · Departamento) se ven y la activa lleva `is-active`.
- Click en cada pestaña: cambia el contenido sin romper el layout.
- En modo claro y modo oscuro el aspecto coincide con `/competicion/`.

- [ ] **Step 3: Detener servidor**

---

### Task 6: Commit

- [ ] **Step 1: Verificación previa al commit**

```bash
git status
git diff --stat
```

- [ ] **Step 2: Stagear y commitear con mensaje en el estilo del repo**

```bash
git add stats/views.py stats/tests/test_rankings_view.py templates/stats/rankings.html \
        docs/superpowers/plans/2026-06-02-rankings-general-tab.md \
        docs/superpowers/specs/2026-06-02-rankings-general-tab.md
git commit -m "$(cat <<'EOF'
feat(rankings): pestaña General con la clasificación de /competicion/

Reutiliza el partial _leaderboard.html (podio + filas) dentro de
/stats/rankings/ como cuarta pestaña, por defecto. Misma fuente de datos
(standings()) y mismo CSS, sin reglas nuevas. Por defecto la pestaña
General sustituye a Sede como vista inicial.
EOF
)"
```

---

### Task 7: Subir a GitHub

- [ ] **Step 1: Pushear**

```bash
git push -u origin HEAD
```

- [ ] **Step 2: Reportar resultado al usuario**

URL del branch + resumen breve.
