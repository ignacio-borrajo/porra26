# Guardar y siguiente — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Añadir un botón "Guardar y siguiente" al modal de pronóstico del jugador que, tras guardar la apuesta, abre directamente el siguiente partido pronosticable sin recargar la página.

**Architecture:** Servicio nuevo `competition/services/predictions.py` con la regla de "siguiente pendiente". `PredictView` añade `pending_count`/`has_next` al GET y maneja `chain=1` en el POST devolviendo una cabecera `X-Modal-Next` con la URL del siguiente modal. `static/js/modal.js` reconoce la cabecera y reemplaza el modal in-place.

**Tech Stack:** Django 5.1, pytest-django, freezegun, factory_boy, JS vanilla.

**Spec:** `docs/superpowers/specs/2026-06-01-guardar-y-siguiente-design.md`

---

## File structure

- **Crear** `competition/services/predictions.py` — funciones `next_pending_match(user, after_match=None)` y `pending_matches_count(user)`.
- **Crear** `competition/tests/test_next_pending.py` — tests del servicio.
- **Modificar** `competition/views.py` — `PredictView.get` añade contexto, `PredictView.post` maneja `chain=1`.
- **Crear** `competition/tests/test_predict_chain_view.py` — tests de la vista (GET + POST chain).
- **Modificar** `templates/competition/_predict_modal.html` — eyebrow con contador y botón condicional.
- **Modificar** `static/js/modal.js` — soporte de cabecera `X-Modal-Next`.

---

## Task 1: Servicio `next_pending_match` y `pending_matches_count`

**Files:**
- Create: `competition/services/predictions.py`
- Test: `competition/tests/test_next_pending.py`

- [ ] **Step 1: Escribir los tests fallidos del servicio**

Contenido completo de `competition/tests/test_next_pending.py`:

```python
from datetime import timedelta

import pytest
from django.utils import timezone
from freezegun import freeze_time

from accounts.tests.factories import UserFactory
from competition.models import Match
from competition.services.predictions import (
    next_pending_match,
    pending_matches_count,
)
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
)


def _now():
    return timezone.now()


@pytest.fixture
def grp(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_returns_none_when_no_candidates(grp):
    u = UserFactory(must_change_password=False)
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_excludes_matches_with_official_result(grp):
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    m.result_home = 1
    m.result_away = 0
    m.save()
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_excludes_matches_with_user_prediction(grp):
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    PredictionFactory(player=u, match=m, home=1, away=0)
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_includes_match_when_only_other_user_predicted(grp):
    u = UserFactory(must_change_password=False)
    other = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    PredictionFactory(player=other, match=m, home=2, away=2)
    assert next_pending_match(u) == m
    assert pending_matches_count(u) == 1


@pytest.mark.django_db
def test_excludes_closed_match(grp):
    """status='closed' (entre kickoff-2h y kickoff): no editable."""
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() + timedelta(hours=1))
    assert m.status == "closed"
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_excludes_live_match(grp):
    u = UserFactory(must_change_password=False)
    m = MatchFactory(round=grp, kickoff=_now() - timedelta(minutes=30))
    assert m.status == "live"
    assert next_pending_match(u) is None
    assert pending_matches_count(u) == 0


@pytest.mark.django_db
def test_excludes_locked_matchday(grp):
    """Jornada 2 bloqueada hasta que todos los partidos de J1 alcancen kickoff."""
    u = UserFactory(must_change_password=False)
    # J1 con un partido aún futuro → bloquea J2
    MatchFactory(round=grp, matchday=1, kickoff=_now() + timedelta(days=2))
    m2 = MatchFactory(round=grp, matchday=2, kickoff=_now() + timedelta(days=3))
    assert next_pending_match(u) != m2
    # Sigue habiendo candidato J1 si el primero también está open
    j1 = MatchFactory(round=grp, matchday=1, kickoff=_now() + timedelta(days=1))
    assert next_pending_match(u) == j1


@pytest.mark.django_db
def test_orders_by_kickoff_asc_then_pk(grp):
    u = UserFactory(must_change_password=False)
    later = MatchFactory(round=grp, kickoff=_now() + timedelta(days=2))
    earlier = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    assert next_pending_match(u) == earlier
    PredictionFactory(player=u, match=earlier, home=0, away=0)
    assert next_pending_match(u) == later


@pytest.mark.django_db
def test_after_match_excludes_given_match(grp):
    u = UserFactory(must_change_password=False)
    a = MatchFactory(round=grp, kickoff=_now() + timedelta(days=1))
    b = MatchFactory(round=grp, kickoff=_now() + timedelta(days=2))
    assert next_pending_match(u) == a
    assert next_pending_match(u, after_match=a) == b
    assert next_pending_match(u, after_match=b) == a  # a sigue candidato
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest competition/tests/test_next_pending.py -v 2>&1 | tail -20`

Expected: ImportError o ModuleNotFoundError sobre `competition.services.predictions`.

- [ ] **Step 3: Implementar el servicio**

Contenido completo de `competition/services/predictions.py`:

```python
from __future__ import annotations

from competition.models import Match


def _candidates(user, after_match=None):
    qs = Match.objects.filter(result_home__isnull=True).exclude(
        predictions__player=user
    )
    if after_match is not None:
        qs = qs.exclude(pk=after_match.pk)
    return qs.select_related("round").order_by("kickoff", "pk")


def next_pending_match(user, after_match=None) -> Match | None:
    """Siguiente partido pronosticable por `user` sin Prediction suya.

    `predictions_open` depende de `now()` y del gate de jornada (no expresable
    en ORM puro); iteramos sobre los candidatos del ORM y filtramos en Python.
    """
    for m in _candidates(user, after_match=after_match):
        if m.predictions_open:
            return m
    return None


def pending_matches_count(user) -> int:
    return sum(1 for m in _candidates(user) if m.predictions_open)
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest competition/tests/test_next_pending.py -v 2>&1 | tail -20`

Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add competition/services/predictions.py competition/tests/test_next_pending.py
git commit -m "feat(predictions): servicio next_pending_match para encadenar apuestas"
```

---

## Task 2: `PredictView.get` añade `pending_count` y `has_next`

**Files:**
- Modify: `competition/views.py:111-128`
- Test: `competition/tests/test_predict_chain_view.py` (nuevo)

- [ ] **Step 1: Escribir los tests fallidos del GET**

Contenido inicial de `competition/tests/test_predict_chain_view.py`:

```python
from datetime import timedelta

import pytest
from django.urls import reverse
from django.utils import timezone

from accounts.tests.factories import UserFactory
from competition.tests.factories import (
    MatchFactory,
    PredictionFactory,
    RoundFactory,
)


@pytest.fixture
def grp(db):
    return RoundFactory(id="groups", points=3, label="G", short="G", order=1)


@pytest.mark.django_db
def test_get_includes_pending_count_and_has_next(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    m1 = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=2))
    r = client.get(reverse("competicion:predict", args=[m1.id]))
    assert r.status_code == 200
    assert r.context["pending_count"] == 2
    assert r.context["has_next"] is True


@pytest.mark.django_db
def test_get_has_next_false_when_only_current_pending(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.get(reverse("competicion:predict", args=[m.id]))
    assert r.status_code == 200
    assert r.context["pending_count"] == 1
    assert r.context["has_next"] is False
```

- [ ] **Step 2: Ejecutar los tests para verificar que fallan**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest competition/tests/test_predict_chain_view.py -v 2>&1 | tail -15`

Expected: 2 tests fallan con KeyError sobre `pending_count` o `has_next`.

- [ ] **Step 3: Actualizar `PredictView.get`**

En `competition/views.py`, sustituir el cuerpo del método `get` de `PredictView` por:

```python
    def get(self, request, match_id):
        m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
        if not request.user.is_jugador:
            raise PermissionDenied("Solo los jugadores pueden pronosticar.")
        if not m.editable:
            messages.error(request, "Las apuestas para este partido están cerradas.")
            return redirect("competicion:dashboard")
        from competition.services.matchday_gate import is_matchday_open
        from competition.services.predictions import (
            next_pending_match,
            pending_matches_count,
        )

        if not is_matchday_open(m.round_id, m.matchday):
            messages.error(
                request,
                f"La Jornada {m.matchday} se desbloqueará cuando termine la Jornada {m.matchday - 1}.",
            )
            return redirect("competicion:dashboard")
        pred = Prediction.objects.filter(player=request.user, match=m).first()
        pending_count = pending_matches_count(request.user)
        has_next = next_pending_match(request.user, after_match=m) is not None
        return render(
            request,
            "competition/_predict_modal.html",
            {
                "match": m,
                "pred": pred,
                "pending_count": pending_count,
                "has_next": has_next,
            },
        )
```

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest competition/tests/test_predict_chain_view.py -v 2>&1 | tail -15`

Expected: 2 passed.

- [ ] **Step 5: Commit**

```bash
git add competition/views.py competition/tests/test_predict_chain_view.py
git commit -m "feat(predict): inyecta pending_count y has_next al modal"
```

---

## Task 3: `PredictView.post` maneja `chain=1`

**Files:**
- Modify: `competition/views.py:130-146`
- Test: `competition/tests/test_predict_chain_view.py` (añadir casos)

- [ ] **Step 1: Añadir tests fallidos del POST**

Añadir al final de `competition/tests/test_predict_chain_view.py`:

```python
@pytest.mark.django_db
def test_post_without_chain_redirects_as_before(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    m = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(reverse("competicion:predict", args=[m.id]), {"home": 2, "away": 1})
    assert r.status_code == 302
    assert r["Location"] == reverse("competicion:dashboard")
    assert m.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_post_with_chain_and_next_returns_modal_next_header(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    current = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    nxt = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=2))
    r = client.post(
        reverse("competicion:predict", args=[current.id]),
        {"home": 2, "away": 1, "chain": "1"},
    )
    assert r.status_code == 204
    assert r["X-Modal-Next"] == reverse("competicion:predict", args=[nxt.id])
    assert current.predictions.filter(player=u, home=2, away=1).exists()


@pytest.mark.django_db
def test_post_with_chain_and_no_next_redirects_to_dashboard(client, grp):
    u = UserFactory(must_change_password=False)
    client.force_login(u)
    only = MatchFactory(round=grp, kickoff=timezone.now() + timedelta(days=1))
    r = client.post(
        reverse("competicion:predict", args=[only.id]),
        {"home": 1, "away": 0, "chain": "1"},
    )
    assert r.status_code == 200
    assert r["X-Modal-Redirect"] == reverse("competicion:dashboard")
    assert only.predictions.filter(player=u, home=1, away=0).exists()
    msgs = [m.message for m in r.wsgi_request._messages]
    assert any("Has apostado todos" in s or "todos los partidos" in s for s in msgs)
```

Nota: si `_messages` no es accesible así en el setup del proyecto, usar `django.contrib.messages.get_messages(r.wsgi_request)`.

- [ ] **Step 2: Ejecutar los tests para verificar que los nuevos fallan**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest competition/tests/test_predict_chain_view.py -v 2>&1 | tail -25`

Expected: 3 nuevos tests fallan (status code o cabecera incorrecta). Los del GET siguen pasando.

- [ ] **Step 3: Actualizar `PredictView.post`**

En `competition/views.py`, sustituir el método `post` de `PredictView` por:

```python
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
        if request.POST.get("chain") == "1":
            from django.http import HttpResponse

            from competition.services.predictions import next_pending_match

            nxt = next_pending_match(request.user, after_match=m)
            if nxt is not None:
                resp = HttpResponse(status=204)
                resp["X-Modal-Next"] = reverse(
                    "competicion:predict", args=[nxt.id]
                )
                return resp
            messages.success(
                request, "¡Has apostado todos los partidos disponibles!"
            )
            resp = HttpResponse(status=200)
            resp["X-Modal-Redirect"] = reverse("competicion:dashboard")
            return resp
        messages.success(request, f"Pronóstico guardado · {m.home.name} {h}–{a} {m.away.name}")
        return redirect("competicion:dashboard")
```

Y en los imports al inicio de `competition/views.py` añadir `reverse` si no está:

```python
from django.urls import reverse
```

(Verifica si ya está importado; añádelo solo si falta.)

- [ ] **Step 4: Ejecutar los tests para verificar que pasan**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest competition/tests/test_predict_chain_view.py -v 2>&1 | tail -25`

Expected: 5 passed (2 GET + 3 POST).

- [ ] **Step 5: Ejecutar toda la suite para descartar regresiones**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest -q 2>&1 | tail -10`

Expected: todas pasan.

- [ ] **Step 6: Commit**

```bash
git add competition/views.py competition/tests/test_predict_chain_view.py
git commit -m "feat(predict): chain=1 devuelve X-Modal-Next o redirect final"
```

---

## Task 4: Plantilla `_predict_modal.html` con contador y botón nuevo

**Files:**
- Modify: `templates/competition/_predict_modal.html`

- [ ] **Step 1: Reemplazar la plantilla**

Contenido completo de `templates/competition/_predict_modal.html`:

```html
<section class="glass pop" style="width:min(520px,100%);padding:28px;border-radius:24px;background:var(--surface-solid)">
  <div class="eyebrow">PRONÓSTICO · {{ pending_count }} pendiente{{ pending_count|pluralize }}</div>
  <h1 class="display" style="font-size:24px">¿Cómo va a quedar?</h1>
  <form method="post" action="{% url 'competicion:predict' match.id %}">
    {% csrf_token %}
    <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:14px;margin:18px 0">
      <div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px">
          <span style="font-size:28px;line-height:1">{{ match.home.flag }}</span>
          <strong>{{ match.home.name }}</strong>
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-top:12px">
          <button type="button" class="btn btn-ghost" data-step="-1" aria-label="Restar gol {{ match.home.name }}" style="width:38px;height:38px;padding:0;font-size:22px;line-height:1">−</button>
          <input name="home" type="text" inputmode="numeric" data-max="20" value="{{ pred.home|default:0 }}" class="input" readonly style="font-size:32px;text-align:center;width:72px;cursor:default">
          <button type="button" class="btn btn-ghost" data-step="1" aria-label="Sumar gol {{ match.home.name }}" style="width:38px;height:38px;padding:0;font-size:22px;line-height:1">+</button>
        </div>
      </div>
      <div class="display" style="font-size:30px">:</div>
      <div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px">
          <span style="font-size:28px;line-height:1">{{ match.away.flag }}</span>
          <strong>{{ match.away.name }}</strong>
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-top:12px">
          <button type="button" class="btn btn-ghost" data-step="-1" aria-label="Restar gol {{ match.away.name }}" style="width:38px;height:38px;padding:0;font-size:22px;line-height:1">−</button>
          <input name="away" type="text" inputmode="numeric" data-max="20" value="{{ pred.away|default:0 }}" class="input" readonly style="font-size:32px;text-align:center;width:72px;cursor:default">
          <button type="button" class="btn btn-ghost" data-step="1" aria-label="Sumar gol {{ match.away.name }}" style="width:38px;height:38px;padding:0;font-size:22px;line-height:1">+</button>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap">
      <button class="btn btn-ghost" type="button" data-modal-close>Cancelar</button>
      {% if has_next %}
      <button class="btn btn-ghost" type="submit">Guardar pronóstico</button>
      <button class="btn btn-primary" type="submit" name="chain" value="1">Guardar y siguiente</button>
      {% else %}
      <button class="btn btn-primary" type="submit">Guardar pronóstico</button>
      {% endif %}
    </div>
  </form>
</section>
```

- [ ] **Step 2: Ejecutar la suite para asegurar que no hay regresiones en tests que renderizan la plantilla**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest -q 2>&1 | tail -10`

Expected: todas pasan.

- [ ] **Step 3: Commit**

```bash
git add templates/competition/_predict_modal.html
git commit -m "feat(predict): eyebrow con contador y botón 'Guardar y siguiente'"
```

---

## Task 5: `modal.js` reconoce `X-Modal-Next`

**Files:**
- Modify: `static/js/modal.js:30-53`

- [ ] **Step 1: Modificar `onSubmit`**

Sustituir la función `onSubmit` en `static/js/modal.js` por:

```js
async function onSubmit(event) {
  event.preventDefault();
  const form = event.currentTarget;
  const data = new FormData(form);
  const submitter = event.submitter;
  if (submitter && submitter.name) {
    data.append(submitter.name, submitter.value || "");
  }
  const res = await fetch(form.action, {
    method: "POST",
    body: data,
    headers: { "X-Modal": "1" },
  });
  const next = res.headers.get("X-Modal-Next");
  if (next) {
    await openModal(next);
    return;
  }
  const redirect = res.headers.get("X-Modal-Redirect");
  if (redirect) {
    window.location.assign(redirect);
    return;
  }
  if (res.headers.get("X-Modal-Errors") === "1") {
    const html = await res.text();
    mount(html);
    return;
  }
  if (res.ok) {
    close();
    window.location.reload();
  }
}
```

Nota: el `FormData(form)` por defecto no incluye el `name=value` del submitter. Lo añadimos explícitamente con `event.submitter` para que `chain=1` viaje al servidor.

- [ ] **Step 2: Ejecutar la suite para asegurar que no hay regresiones**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest -q 2>&1 | tail -10`

Expected: todas pasan.

- [ ] **Step 3: Commit**

```bash
git add static/js/modal.js
git commit -m "feat(modal): soporta X-Modal-Next y propaga submitter name/value"
```

---

## Task 6: Verificación manual + commit final si hace falta

**Files:** ninguno (verificación)

- [ ] **Step 1: Arrancar el servidor**

Run: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python manage.py runserver` en background.

- [ ] **Step 2: Verificación en navegador**

Iniciar sesión como un jugador (factories/fixtures del proyecto deben permitirlo, o usar `python manage.py shell` para crear uno) y validar:

1. Abrir el dashboard. Hacer click sobre un partido apostable que no tenga predicción todavía.
2. Modal aparece con eyebrow `PRONÓSTICO · N pendientes`.
3. Botones visibles: *Cancelar*, *Guardar pronóstico* (ghost), *Guardar y siguiente* (primary).
4. Pulsar *Guardar y siguiente* → el modal se sustituye sin recarga por el siguiente partido. Contador decrece.
5. Repetir hasta el último. En el último modal, el botón *Guardar y siguiente* NO aparece — solo *Guardar pronóstico* primario.
6. Al guardar el último, vuelve al dashboard con toast `¡Has apostado todos los partidos disponibles!`.

- [ ] **Step 3: Parar el servidor**

Matar el proceso del paso 1.

- [ ] **Step 4: Si la verificación fue limpia, no hay commit adicional**

Si en pasos 1-2 se necesitó algún ajuste, commitealo con un mensaje descriptivo.

---

## Notas finales

- `competition/views.py` ya importa `redirect`, `get_object_or_404`, etc. — `reverse` puede no estar; verifica imports al hacer Task 3 Step 3.
- Los tests usan `freezegun` solo si el contexto temporal es crítico; los casos planteados aquí usan `timezone.now() + timedelta(days=N)` para garantizar status `open` sin necesidad de congelar el tiempo.
- Estado `closed` para tests: `kickoff = now + 1h` (entre kickoff-2h y kickoff). Estado `live`: `kickoff = now - 30min`.
- Si Django añade soporte futuro de `Match.status` como campo persistido el servicio se simplificaría a una sola query; mientras tanto, iterar es aceptable (decenas de partidos).
