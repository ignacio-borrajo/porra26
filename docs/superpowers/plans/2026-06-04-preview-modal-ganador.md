# Plan — Previsualización del modal de ganador

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir a un gestor abrir, desde "Premios y puntos", el mismo modal de ganador de jornada/fase con su propio usuario, sin persistir nada en BD ni marcar anuncios como vistos.

**Architecture:** Endpoint `GET /announcements/preview/?scope=...&tied=...` (solo gestor) que construye un `WinnerAnnouncement` en memoria, lo pasa al template `_winner_modal.html` (adaptado con flag `preview` para ocultar `data-seen-url` y sustituir el botón "Felicidades!" por uno que solo cierra), y un pequeño widget en `prizes_settings.html` que abre la URL con `openModal()`.

**Tech Stack:** Django 5, Python 3.12, pytest, ruff, plantillas server-side, `static/js/modal.js`.

---

## Archivos afectados

- **Crear:** `announcements/preview.py` (helper `build_preview`)
- **Crear:** `announcements/tests/test_preview.py` (suite TDD)
- **Modificar:** `announcements/urls.py` (añadir ruta `preview/`)
- **Modificar:** `announcements/views.py` (añadir `AnnouncementPreviewView`)
- **Modificar:** `templates/announcements/_winner_modal.html` (flag `preview`)
- **Modificar:** `static/css/announcements.css` (badge `.winner-preview-badge`)
- **Modificar:** `templates/pot/prizes_settings.html` (widget de previsualización)

Spec: `docs/superpowers/specs/2026-06-04-preview-modal-ganador-design.md`.

---

## Task 1 — URL, vista esqueleto y test de permisos

**Files:**
- Modify: `announcements/urls.py`
- Modify: `announcements/views.py`
- Test: `announcements/tests/test_preview.py`

- [ ] **Paso 1: Crear `announcements/tests/test_preview.py` con el primer test (rojo).**

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
class TestPreviewPermissions:
    def test_redirects_player_to_dashboard(self, client):
        client.force_login(UserFactory(is_gestor=False))
        res = client.get(reverse("announcements:preview"))
        assert res.status_code == 302
        assert reverse("competicion:dashboard") in res.headers["Location"]

    def test_gestor_gets_200(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview"))
        assert res.status_code == 200
```

- [ ] **Paso 2: Ejecutar el test → tiene que fallar por `NoReverseMatch`.**

Run: `python -m pytest announcements/tests/test_preview.py -v`
Esperado: ERROR `Reverse for 'announcements:preview' not found`.

- [ ] **Paso 3: Añadir la ruta en `announcements/urls.py`.**

Reemplazar el bloque `urlpatterns` para que quede así:

```python
from django.urls import path

from .views import AnnouncementModalView, AnnouncementPreviewView, AnnouncementSeenView

app_name = "announcements"

urlpatterns = [
    path("preview/", AnnouncementPreviewView.as_view(), name="preview"),
    path("<int:pk>/", AnnouncementModalView.as_view(), name="modal"),
    path("<int:pk>/seen", AnnouncementSeenView.as_view(), name="seen"),
]
```

- [ ] **Paso 4: Añadir la vista mínima en `announcements/views.py`.**

Justo bajo los imports existentes y antes de las otras vistas, añadir:

```python
from accounts.mixins import GestorRequiredMixin
```

Al final del archivo añadir:

```python
class AnnouncementPreviewView(GestorRequiredMixin, View):
    def get(self, request):
        return HttpResponse("preview")
```

- [ ] **Paso 5: Ejecutar tests → ambos pasan.**

Run: `python -m pytest announcements/tests/test_preview.py -v`
Esperado: 2 passed.

- [ ] **Paso 6: Commit.**

```bash
git add announcements/urls.py announcements/views.py announcements/tests/test_preview.py
git commit -m "feat(announcements): URL /preview/ y vista gated por gestor"
```

---

## Task 2 — Helper `build_preview` + render del modal

**Files:**
- Create: `announcements/preview.py`
- Modify: `announcements/views.py`
- Test: `announcements/tests/test_preview.py`

- [ ] **Paso 1: Ampliar `test_preview.py` con tests del helper y del render (rojo).**

Añadir al final del archivo:

```python
from decimal import Decimal

from announcements.models import WinnerAnnouncement, WinnerAnnouncementSeen
from announcements.preview import build_preview
from competition.tests.factories import RoundFactory
from pot.models import PotSettings


@pytest.mark.django_db
class TestBuildPreview:
    def test_matchday_single_uses_current_user(self):
        gestor = GestorFactory(name="Iñaki")
        ann, winners = build_preview("matchday", tied=False, current_user=gestor)
        assert ann.pk is None
        assert ann.scope_kind == "matchday"
        assert ann.scope_matchday == 1
        assert ann.tied is False
        assert winners == [gestor]

    def test_matchday_tied_picks_a_second_user(self):
        gestor = GestorFactory(name="Iñaki")
        other = UserFactory(name="Ana")
        ann, winners = build_preview("matchday", tied=True, current_user=gestor)
        assert ann.tied is True
        assert gestor in winners and other in winners
        assert len(winners) == 2

    def test_tied_falls_back_to_single_when_no_other_user(self):
        gestor = GestorFactory(name="Iñaki")
        ann, winners = build_preview("matchday", tied=True, current_user=gestor)
        assert winners == [gestor]
        assert ann.tied is False

    def test_round_uses_first_ko_round(self):
        RoundFactory(id="groups", label="Fase de grupos", short="GRP", order=1)
        r16 = RoundFactory(id="r16", label="Octavos", short="R16", points=7, order=3)
        gestor = GestorFactory()
        ann, _ = build_preview("round", tied=False, current_user=gestor)
        assert ann.scope_kind == "round"
        assert ann.scope_round_id == r16.id
        assert ann.title == "¡Ganador de Octavos!"

    def test_global(self):
        gestor = GestorFactory()
        ann, _ = build_preview("global", tied=False, current_user=gestor)
        assert ann.scope_kind == "global"
        assert ann.title == "¡Campeón del Mundial!"

    def test_share_uses_pot_settings_single(self):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("50")
        s.save()
        gestor = GestorFactory()
        ann, _ = build_preview("matchday", tied=False, current_user=gestor)
        assert ann.share == Decimal("50")

    def test_share_uses_pot_settings_split_when_tied(self):
        s = PotSettings.load()
        s.matchday_winner_prize = Decimal("50")
        s.save()
        gestor = GestorFactory()
        UserFactory(name="Ana")
        ann, _ = build_preview("matchday", tied=True, current_user=gestor)
        assert ann.share == Decimal("25")


@pytest.mark.django_db
class TestPreviewView:
    def test_renders_current_user_and_no_seen_url(self, client):
        gestor = GestorFactory(name="Iñaki Demo")
        client.force_login(gestor)
        res = client.get(reverse("announcements:preview") + "?scope=matchday&tied=0")
        assert res.status_code == 200
        html = res.content.decode()
        assert "Iñaki Demo" in html
        assert "data-seen-url" not in html
        assert "Vista previa" in html

    def test_tied_renders_two_winners_and_split_copy(self, client):
        gestor = GestorFactory(name="Iñaki Demo")
        UserFactory(name="Ana Demo")
        client.force_login(gestor)
        res = client.get(reverse("announcements:preview") + "?scope=matchday&tied=1")
        assert res.status_code == 200
        html = res.content.decode()
        assert "Iñaki Demo" in html
        assert "Ana Demo" in html
        assert "Empate en la cima" in html

    def test_round_title(self, client):
        RoundFactory(id="groups", label="Fase de grupos", short="GRP", order=1)
        RoundFactory(id="r16", label="Octavos", short="R16", points=7, order=3)
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=round&tied=0")
        assert "¡Ganador de Octavos!" in res.content.decode()

    def test_global_title(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=global&tied=0")
        assert "¡Campeón del Mundial!" in res.content.decode()

    def test_unknown_scope_returns_404(self, client):
        client.force_login(GestorFactory())
        res = client.get(reverse("announcements:preview") + "?scope=bogus")
        assert res.status_code == 404

    def test_does_not_persist_announcements(self, client):
        client.force_login(GestorFactory())
        before_ann = WinnerAnnouncement.objects.count()
        before_seen = WinnerAnnouncementSeen.objects.count()
        client.get(reverse("announcements:preview") + "?scope=matchday&tied=0")
        client.get(reverse("announcements:preview") + "?scope=global&tied=1")
        assert WinnerAnnouncement.objects.count() == before_ann
        assert WinnerAnnouncementSeen.objects.count() == before_seen
```

- [ ] **Paso 2: Ejecutar → rojo.**

Run: `python -m pytest announcements/tests/test_preview.py -v`
Esperado: ImportError de `announcements.preview` y/o 200 sin contenido esperado.

- [ ] **Paso 3: Crear `announcements/preview.py`.**

```python
from decimal import Decimal

from django.http import Http404

from accounts.models import User
from announcements.models import WinnerAnnouncement
from competition.models import Round
from pot.models import PotSettings

_VALID_SCOPES = {"matchday", "round", "global"}


def build_preview(scope: str, *, tied: bool, current_user) -> tuple[WinnerAnnouncement, list]:
    if scope not in _VALID_SCOPES:
        raise Http404(f"scope inválido: {scope}")

    ann = WinnerAnnouncement(scope_kind=scope, points=12)

    if scope == "matchday":
        ann.scope_matchday = 1
    elif scope == "round":
        ko_round = Round.objects.exclude(id="groups").order_by("order").first()
        if ko_round is None:
            ko_round = Round.objects.order_by("order").first()
        if ko_round is not None:
            ann.scope_round = ko_round

    winners = [current_user]
    if tied:
        other = User.objects.exclude(pk=current_user.pk).order_by("name").first()
        if other is not None:
            winners.append(other)
    ann.tied = len(winners) > 1

    base = PotSettings.load().matchday_winner_prize
    ann.share = (base / len(winners)) if winners else Decimal("0")

    return ann, winners
```

- [ ] **Paso 4: Conectar la vista en `announcements/views.py`.**

Sustituir la `AnnouncementPreviewView` puesta como stub por:

```python
class AnnouncementPreviewView(GestorRequiredMixin, View):
    def get(self, request):
        scope = request.GET.get("scope", "matchday")
        tied = request.GET.get("tied") == "1"
        ann, winners = build_preview(scope, tied=tied, current_user=request.user)
        return render(
            request,
            "announcements/_winner_modal.html",
            {"announcement": ann, "preview": True, "preview_winners": winners},
        )
```

Añadir al import de la misma vista:

```python
from .preview import build_preview
```

Quitar el `HttpResponse` del stub si quedó suelto (la línea `return HttpResponse("preview")` debe desaparecer).

- [ ] **Paso 5: Ejecutar tests del helper → verde, pero tests del view siguen rojos (template aún no soporta `preview`).**

Run: `python -m pytest announcements/tests/test_preview.py::TestBuildPreview -v`
Esperado: 7 passed.

Run: `python -m pytest announcements/tests/test_preview.py::TestPreviewView -v`
Esperado: varios fallos por `data-seen-url` presente y/o ausencia de "Vista previa" y/o crash en `{% url 'announcements:seen' announcement.id %}` con `pk=None`.

(Esto deja la siguiente tarea como puramente de template.)

- [ ] **Paso 6: Commit.**

```bash
git add announcements/preview.py announcements/views.py announcements/tests/test_preview.py
git commit -m "feat(announcements): build_preview y vista que arma el modal en memoria"
```

---

## Task 3 — Plantilla del modal con flag `preview`

**Files:**
- Modify: `templates/announcements/_winner_modal.html`
- Modify: `static/css/announcements.css`

- [ ] **Paso 1: Reescribir `templates/announcements/_winner_modal.html` con las dos ramas.**

Contenido completo del archivo:

```django
<section class="glass pop winner-modal"
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
  <p class="winner-points">{{ announcement.points }} puntos</p>
  {% if announcement.share %}
    <p class="winner-share">
      {% if announcement.tied %}
        Cada uno se lleva <strong>{{ announcement.share|floatformat:2 }} €</strong>
      {% else %}
        Se lleva <strong>{{ announcement.share|floatformat:2 }} €</strong>
      {% endif %}
    </p>
  {% endif %}
  <div class="winner-list">
    {% if preview %}
      {% for w in preview_winners %}
        <div class="winner-card">
          {% include "partials/_avatar.html" with u=w size=64 %}
          <div class="winner-name">{{ w.name }}</div>
        </div>
      {% endfor %}
    {% else %}
      {% for w in announcement.winners.all %}
        <div class="winner-card">
          {% include "partials/_avatar.html" with u=w size=64 %}
          <div class="winner-name">{{ w.name }}</div>
        </div>
      {% endfor %}
    {% endif %}
  </div>
  <p class="winner-subtitle">
    {% if announcement.tied %}Empate en la cima. ¡Bien jugado!{% else %}¡Enhorabuena!{% endif %}
  </p>
  <div class="winner-actions">
    {% if preview %}
      <button type="button" class="btn btn-primary" data-modal-close>Cerrar vista previa</button>
    {% else %}
      <button type="button" class="btn btn-primary" data-winner-confirm>¡Felicidades!</button>
    {% endif %}
  </div>
</section>
```

- [ ] **Paso 2: Añadir CSS para la etiqueta de vista previa.**

Buscar `static/css/announcements.css` y al final del archivo añadir:

```css
.winner-preview-badge {
  position: absolute;
  top: 14px;
  left: 14px;
  padding: 4px 10px;
  border-radius: 999px;
  background: rgba(255, 255, 255, 0.08);
  border: 1px solid rgba(255, 255, 255, 0.18);
  color: var(--text-dim);
  font-family: "Geist Mono", monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
}
```

Si `static/css/announcements.css` no existe, crearlo con solo ese bloque y verificar que se incluya. (Comprobar con `grep -rn "announcements.css" templates static` para localizar el `<link>`. Si no hay link, añadirlo a `templates/base.html` siguiendo el patrón de otros `static/css/*.css`.)

- [ ] **Paso 3: Ejecutar tests de preview.**

Run: `python -m pytest announcements/tests/test_preview.py -v`
Esperado: 14 passed.

- [ ] **Paso 4: Ejecutar tests del flujo real para confirmar no-regresión.**

Run: `python -m pytest announcements/tests/ -v`
Esperado: todos pasan (preview + modal real + services).

- [ ] **Paso 5: Commit.**

```bash
git add templates/announcements/_winner_modal.html static/css/announcements.css
git commit -m "feat(announcements): _winner_modal soporta flag preview con badge"
```

---

## Task 4 — Widget de previsualización en "Premios y puntos"

**Files:**
- Modify: `templates/pot/prizes_settings.html`

- [ ] **Paso 1: Localizar el cierre de la sección "02 · Por jornada" (la `<section class="glass prizes-matchday-card">` con el campo `matchday_winner_prize`) e insertar inmediatamente después, todavía dentro del mismo `<div class="prizes-config stagger">` pero FUERA del `<form method="post">`, una nueva sección.**

El form actual abarca todas las secciones 01..04 hasta el botón "Guardar premios y puntos". El widget de previsualización debe quedar **fuera** de ese form para que sus inputs no se envíen al guardar. Estrategia: añadir la sección justo **después** del `</form>`, antes del `</div>` que cierra `prizes-config`.

Insertar este bloque entre `</form>` y `</div>` finales:

```django
{% if request.user.is_gestor %}
<section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:14px">
  <header style="display:flex;flex-direction:column;gap:4px">
    <span class="eyebrow">Herramientas · vista previa</span>
    <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:20px">Previsualizar modal de ganador</h2>
    <p style="color:var(--text-dim);margin:0;font-size:13px">
      Abre el modal de celebración con tu usuario como ganador. No marca nada ni avisa a nadie.
    </p>
  </header>
  <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end">
    <label style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">Tipo</span>
      <select id="preview-scope" class="input">
        <option value="matchday">Jornada de grupos</option>
        <option value="round">Ronda eliminatoria</option>
        <option value="global">Campeón del Mundial</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">Modo</span>
      <select id="preview-tied" class="input">
        <option value="0">Ganador único</option>
        <option value="1">Empate (2 ganadores)</option>
      </select>
    </label>
    <button type="button" class="btn btn-primary" id="preview-open">Previsualizar</button>
  </div>
</section>
{% endif %}
```

Y al final del archivo (después del `{% endblock %}` de `main`), añadir el bloque de scripts:

```django
{% block scripts %}
{% if request.user.is_gestor %}
{% load static %}
<script type="module">
  import { openModal } from "{% static 'js/modal.js' %}";
  const btn = document.getElementById("preview-open");
  if (btn) {
    btn.addEventListener("click", () => {
      const scope = document.getElementById("preview-scope").value;
      const tied = document.getElementById("preview-tied").value;
      openModal(`{% url 'announcements:preview' %}?scope=${scope}&tied=${tied}`);
    });
  }
</script>
{% endif %}
{% endblock %}
```

- [ ] **Paso 2: Verificar que `prizes_settings.html` ya carga `{% load static %}` arriba o que el segundo `{% load static %}` no rompe (Django permite redeclararlo).** Si el bloque `scripts` ya existía en el archivo, fusionar contenido en lugar de duplicar el bloque.

Comprobación rápida:

Run: `grep -n "load static\|block scripts" templates/pot/prizes_settings.html`

- [ ] **Paso 3: Smoke test manual.**

Run: `python manage.py runserver` (dejar corriendo).
Acciones:
1. Login con un usuario gestor.
2. Ir a `/pot/prizes/`.
3. Verificar que aparece la sección "Previsualizar modal de ganador".
4. Probar las 6 combinaciones (3 scopes × 2 modos). Para cada una:
   - El modal aparece con animación y confetti.
   - Aparece la etiqueta "VISTA PREVIA".
   - El botón "Cerrar vista previa" cierra el modal y NO crea fila en `WinnerAnnouncement` (verificar con `python manage.py shell -c "from announcements.models import WinnerAnnouncement; print(WinnerAnnouncement.objects.count())"`).
5. Acceder a `/pot/prizes/` como jugador no gestor → la sección no aparece.

- [ ] **Paso 4: Commit.**

```bash
git add templates/pot/prizes_settings.html
git commit -m "feat(pot): widget gestor para previsualizar modal de ganador"
```

---

## Task 5 — Lint, suite completa, push, PR y merge

**Files:** ninguno, solo CI/Git.

- [ ] **Paso 1: Ruff format + lint.**

Run: `ruff format announcements/ templates/announcements/ && ruff check announcements/`
Esperado: All checks passed!

- [ ] **Paso 2: Suite completa.**

Run: `python -m pytest -q`
Esperado: todos los tests verdes (incluyendo announcements, pot, competition).

- [ ] **Paso 3: Push y PR.**

```bash
git push -u origin <nombre-de-la-rama>
gh pr create --title "feat(announcements): previsualización del modal de ganador" --body "$(cat <<'EOF'
## Summary
- Endpoint `/announcements/preview/?scope=...&tied=...` (solo gestor) que arma un `WinnerAnnouncement` en memoria con el usuario actual.
- Plantilla `_winner_modal.html` soporta flag `preview` (oculta `data-seen-url`, sustituye el botón, muestra badge "Vista previa").
- Widget en `/pot/prizes/` con dos selects + botón "Previsualizar".

## Test plan
- [x] `pytest announcements/tests/test_preview.py` (14 tests)
- [x] `pytest announcements/tests/` (no regresión del modal real)
- [x] `pytest -q` (suite completa)
- [x] Smoke manual: 6 variantes (matchday/round/global × único/empate) abren el modal correcto sin persistir nada
- [x] No gestor en `/pot/prizes/` no ve el widget
EOF
)"
```

- [ ] **Paso 4: Merge y limpieza.**

```bash
gh pr merge --squash --delete-branch
git checkout main
git pull --ff-only
```

- [ ] **Paso 5: Verificar.**

Run: `git log --oneline -3`
Esperado: ver el commit de merge en `main`.

---

## Verificación final contra el spec

- §3 Endpoint con `scope` y `tied` → Task 1, 2.
- §3 `_winner_modal.html` con `preview` (sin `data-seen-url`, botón de cierre, badge) → Task 3.
- §3 Widget en `prizes_settings.html` con dos selects → Task 4.
- §6 Tests TDD 1–8 → cubiertos por `TestPreviewPermissions`, `TestBuildPreview`, `TestPreviewView` en Task 1 y Task 2.
- §5 Edge "solo el propio gestor en BD" → `test_tied_falls_back_to_single_when_no_other_user`.
- §5 Edge "no hay rondas KO en BD" → cubierto por el fallback a `Round.objects.first()` en `build_preview`; no se prueba explícitamente pero el código es de bajo riesgo (rama defensiva).
- §5 No persistencia → `test_does_not_persist_announcements`.
- §5 Share derivado de PotSettings → `test_share_uses_pot_settings_*`.
