# Spec — Modal unificado para introducir resultados oficiales

Fecha: 2026-06-02
Pantallas afectadas: `/competicion/resultados/` (gestor).

## 1. Problema

Cuando un gestor introduce el resultado de un partido desde `/competicion/resultados/`, hoy se navega a una **página completa** (`_official_modal.html` extiende `base.html`). El resultado es:

- No es una modal: no hay overlay, ni desenfoque del fondo, ni botón de cerrar.
- Los `<input type="number">` se ven distintos a la modal de pronóstico (que usa input *readonly* con botones **−/+**).
- No existe el flujo *"Guardar y siguiente"*; al confirmar se vuelve a `/competicion/resultados/` con recarga completa.
- La experiencia rompe la uniformidad con `/competicion/` (modal de pronóstico).

## 2. Objetivo

Que el gestor introduzca resultados con **exactamente la misma UX visual y de flujo** que un jugador al pronosticar:

- Modal overlay (`.ovl` + `<section class="glass pop">`).
- Mismos *steppers* **−/+** con input readonly centrado.
- Mismo bloque cabecera (eyebrow + título grande).
- Botonera idéntica: **Cancelar / Guardar resultado / Guardar y siguiente**.
- Cadena automática a través de todos los partidos pendientes de resultado.
- Cierre con ESC, click fuera o botón **×**.

## 3. Alcance

Incluido:
- Reescribir `templates/competition/_official_modal.html` como fragmento de modal (sin `extends base.html`).
- Cambiar enlaces de `manage_results.html` para que abran modal (`data-modal-url`).
- Ampliar `ResultOfficialView` (GET y POST) para soportar `chain=1`, conteo de pendientes, y headers `X-Modal-Next` / `X-Modal-Redirect`.
- Añadir helpers en `competition/services/predictions.py` (o nuevo archivo) para enumerar partidos pendientes de **resultado** (por estado, no por usuario).
- Tests: helper de pendientes, vista POST con `chain=1`, vista POST sin `chain`, GET devuelve contadores.

Fuera de alcance:
- Cambios visuales en el `match-card` o en la lista pendientes/próximos/finalizados (más allá de `data-modal-url`).
- Cambios en `_predict_modal.html`.
- Tocar el flujo de generación de PDF de cierre.

## 4. Reglas de "siguiente partido pendiente de resultado"

Un partido es **pendiente de resultado** si:
- `status` ∈ {`closed`, `live`}, es decir, ya pasó la hora de cierre de apuestas o ya empezó pero **aún no tiene resultado** (`result_home is None`).
- (No miramos `done` — esos ya están resueltos.)
- (No incluimos `upcoming` — aún no se puede finalizar de forma natural, pero no bloqueamos manualmente; el gestor puede editar desde el modal abierto si así lo desea.)

Orden de iteración: `kickoff ASC, pk ASC`.

`next_pending_result_match(after_match=None)`:
- Itera candidatos `Match.objects.filter(result_home__isnull=True)` excluyendo `after_match`.
- Devuelve el primero cuyo `status` esté en {`closed`, `live`}, según `kickoff ASC`.

`pending_result_matches_count()`:
- Cuenta candidatos cuyo `status ∈ {closed, live}`.

## 5. Cambios por archivo

### 5.1 `templates/competition/_official_modal.html` (reescritura)

```html
<section class="glass pop" style="width:min(520px,100%);padding:28px;border-radius:24px;background:var(--surface-solid)">
  <header style="display:flex;align-items:flex-start;justify-content:space-between;gap:12px">
    <div>
      <div class="eyebrow">RESULTADO OFICIAL · {{ pending_count }} pendiente{{ pending_count|pluralize }}</div>
      <h1 class="display" style="font-size:24px;margin:4px 0 0">Marcar resultado final</h1>
    </div>
    <button type="button" data-modal-close class="btn btn-ghost" style="width:36px;height:36px;padding:0;border-radius:12px" aria-label="Cerrar">{% load icons %}{% icon "x" width=14 %}</button>
  </header>
  <form method="post" action="{% url 'competicion:official' match.id %}">
    {% csrf_token %}
    <div style="display:grid;grid-template-columns:1fr auto 1fr;align-items:center;gap:14px;margin:18px 0">
      <div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px">
          <span style="font-size:28px;line-height:1">{{ match.home.flag }}</span>
          <strong>{{ match.home.name }}</strong>
        </div>
        <div style="display:flex;align-items:center;justify-content:center;gap:10px;margin-top:12px">
          <button type="button" class="btn btn-ghost" data-step="-1" aria-label="Restar gol {{ match.home.name }}" style="width:38px;height:38px;padding:0;font-size:22px;line-height:1">−</button>
          <input name="home" type="text" inputmode="numeric" data-max="20" value="{{ match.result_home|default:0 }}" class="input" readonly style="font-size:32px;text-align:center;width:72px;cursor:default">
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
          <input name="away" type="text" inputmode="numeric" data-max="20" value="{{ match.result_away|default:0 }}" class="input" readonly style="font-size:32px;text-align:center;width:72px;cursor:default">
          <button type="button" class="btn btn-ghost" data-step="1" aria-label="Sumar gol {{ match.away.name }}" style="width:38px;height:38px;padding:0;font-size:22px;line-height:1">+</button>
        </div>
      </div>
    </div>
    <div style="display:flex;gap:10px;justify-content:flex-end;flex-wrap:wrap">
      <button class="btn btn-ghost" type="button" data-modal-close>Cancelar</button>
      {% if has_next %}
      <button class="btn btn-ghost" type="submit">Guardar resultado</button>
      <button class="btn btn-primary" type="submit" name="chain" value="1">Guardar y siguiente</button>
      {% else %}
      <button class="btn btn-primary" type="submit">Guardar resultado</button>
      {% endif %}
    </div>
  </form>
</section>
```

Notas:
- Texto del eyebrow: **"RESULTADO OFICIAL · N pendientes"** (paraleliza el "PRONÓSTICO · N pendientes").
- No se extiende `base.html`. Es un fragmento *modal-only*. Si alguien navega directo, verá el fragmento sin chrome; mismo trade-off que `_predict_modal.html`.
- Estética idéntica al modal de pronóstico (mismos estilos inline, mismo `glass pop`, mismo `surface-solid`).

### 5.2 `templates/competition/manage_results.html`

Cambiar los enlaces "Finalizar" / "Editar" para que abran modal:

```html
<a class="btn btn-primary"
   href="{% url 'competicion:official' m.id %}"
   data-modal-url="{% url 'competicion:official' m.id %}"
   style="padding:6px 12px;font-size:12px">Finalizar</a>
```

Aplica a las tres listas: `pending`, `upcoming`, `done` (donde el botón "Finalizar"/"Editar" apunte a `official`). Se mantiene el `href` como fallback (mismo patrón que `_match_card.html`).

### 5.3 `competition/views.py` — `ResultOfficialView`

**GET:**
```python
def get(self, request, match_id):
    m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
    from competition.services.predictions import (
        next_pending_result_match,
        pending_result_matches_count,
    )
    pending_count = pending_result_matches_count()
    has_next = next_pending_result_match(after_match=m) is not None
    return render(
        request,
        "competition/_official_modal.html",
        {"match": m, "pending_count": pending_count, "has_next": has_next},
    )
```

**POST:**
```python
def post(self, request, match_id):
    m = get_object_or_404(Match.objects.select_related("home", "away", "round"), pk=match_id)
    try:
        h = max(0, int(request.POST.get("home", 0)))
        a = max(0, int(request.POST.get("away", 0)))
    except ValueError:
        messages.error(request, "Marcador inválido.")
        return redirect("competicion:manage_results")
    resolve_match(m, home=h, away=a, actor=request.user)
    messages.success(request, f"Resultado confirmado · {m.home.name} {h}–{a} {m.away.name}")
    if request.POST.get("chain") == "1":
        from django.http import HttpResponse
        from django.urls import reverse
        from competition.services.predictions import next_pending_result_match
        nxt = next_pending_result_match(after_match=m)
        if nxt is not None:
            resp = HttpResponse(status=204)
            resp["X-Modal-Next"] = reverse("competicion:official", args=[nxt.id])
            return resp
        resp = HttpResponse(status=200)
        resp["X-Modal-Redirect"] = reverse("competicion:manage_results")
        return resp
    return redirect("competicion:manage_results")
```

Comportamiento idéntico a `PredictView` (chain + headers `X-Modal-*`).

### 5.4 `competition/services/predictions.py`

Añadir:
```python
def _result_candidates(after_match=None):
    qs = Match.objects.filter(result_home__isnull=True).select_related("round")
    if after_match is not None:
        qs = qs.exclude(pk=after_match.pk)
    return qs.order_by("kickoff", "pk")


def next_pending_result_match(after_match=None) -> Match | None:
    for m in _result_candidates(after_match=after_match):
        if m.status in ("closed", "live"):
            return m
    return None


def pending_result_matches_count() -> int:
    return sum(1 for m in _result_candidates() if m.status in ("closed", "live"))
```

(Misma forma que `next_pending_match` / `pending_matches_count` para predicciones.)

## 6. Tests

Archivo nuevo `competition/tests/test_official_modal.py`:

1. `test_next_pending_result_match_returns_first_closed_or_live`
   - Setup: 1 partido `open` (kickoff > now+3h), 1 partido `closed` (kickoff entre now y now-2h, sin result), 1 `live` (kickoff < now, sin result), 1 `done` (con result).
   - Assert: devuelve el más antiguo por kickoff con estado closed/live.

2. `test_next_pending_result_match_skips_after_match`
   - 2 partidos `closed`. `after_match` = primero → devuelve segundo.

3. `test_pending_result_matches_count_counts_only_closed_live`
   - 2 closed, 1 live, 1 done, 1 open → 3.

4. `test_official_get_includes_pending_count_and_has_next` (vista, gestor logueado)
   - Setup con 2 partidos `closed`; GET `/competicion/resultados/<id1>/` → 200, contexto con `pending_count == 2`, `has_next == True`, render del fragmento (no `<html>`).

5. `test_official_post_chain_returns_x_modal_next`
   - 2 partidos `closed`; POST a `/competicion/resultados/<id1>/` con `home=2&away=1&chain=1` → 204, header `X-Modal-Next` apunta al `<id2>`. Y `id1` queda con resultado y `earned` recalculado.

6. `test_official_post_chain_no_more_redirects`
   - 1 partido `closed`; POST `chain=1` → 200 con `X-Modal-Redirect=/competicion/resultados/`.

7. `test_official_post_without_chain_redirects` (regresión)
   - POST sin chain → 302 a `manage_results`.

8. `test_manage_results_finalize_link_uses_modal_url` (smoke)
   - GET de la lista → HTML contiene `data-modal-url` apuntando al `official` del partido pendiente.

## 7. Riesgos / consideraciones

- **Fragmento sin base** en navegación directa (sin JS, copy-paste de URL): la página queda sin chrome. Mismo trade-off existente en `_predict_modal.html`. Aceptamos por uniformidad.
- **Race condition al hacer chain** si otro gestor ya resolvió el siguiente partido entre el GET y el POST: el siguiente modal abrirá un partido ya resuelto (igual válido, ya que la vista soporta edición). No es bloqueante.
- **`resolve_match` ya es idempotente** en cuanto a edición: actualiza `result_home/away` y `finished_at`. Re-resolver desde el modal mantiene el comportamiento actual de "Editar".
- **PDFs de cierre y reportes Teams** no se ven afectados — `resolve_match` se sigue invocando.
- El test del template (`data-modal-url`) usa búsqueda por substring; no es frágil porque ya hay otros tests con asserts similares.

## 8. Definition of Done

1. Al pulsar "Finalizar" desde `/competicion/resultados/`, se abre una modal con el mismo look & feel que el modal de pronóstico.
2. Botones **−/+** funcionan (vía `modal.js` ya existente).
3. ESC / click fuera / botón × cierran la modal.
4. "Guardar y siguiente" abre la siguiente modal sin recarga.
5. Cuando no quedan pendientes, redirige a `/competicion/resultados/`.
6. Tests pasan (`pytest competition/tests/test_official_modal.py`).
7. La vista funcional ya existente de jugador no cambia.
