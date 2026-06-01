# Guardar y siguiente — diseño

Fecha: 2026-06-01
Estado: aprobado por el usuario para implementación

## Contexto

En el flujo actual de **pronóstico** del jugador, al pulsar sobre un partido se abre el modal `_predict_modal.html` (servido por `PredictView`). Tiene dos botones: *Cancelar* y *Guardar pronóstico*. Al guardar, el modal se cierra y la página se recarga, devolviendo al jugador al dashboard. Para apostar varios partidos seguidos hay que volver al listado y abrir cada modal manualmente.

Los usuarios piden una opción que, tras guardar, **abra directamente el siguiente partido pendiente de pronosticar**.

## Decisiones acordadas

- **Alcance:** flujo del jugador (`PredictView`), no del gestor de resultados.
- **"Pendiente" significa:** partido con `predictions_open == True` (editable + jornada desbloqueada) y **sin** `Prediction` previa del jugador autenticado.
- **Orden del siguiente:** `kickoff` ascendente (el más próximo a cerrar va antes). Desempate por `pk` para determinismo.
- **Alcance global:** se buscan pendientes en todas las rondas y jornadas, no solo en la jornada filtrada en pantalla.
- **Fin de cola:** cuando no quedan pendientes, se cierra el modal, se vuelve al dashboard y se muestra un toast `"¡Has apostado todos los partidos disponibles!"`.
- **UX último pendiente:** si en el partido actual no hay siguiente, el botón "Guardar y siguiente" no se renderiza; solo queda "Guardar pronóstico" como acción primaria.
- **Indicador de progreso:** eyebrow del modal con `PRONÓSTICO · {N} pendientes`, donde `N` incluye el partido actual si aún no tiene apuesta.
- **Arquitectura:** servidor calcula el siguiente; el modal se sustituye in-place mediante una cabecera HTTP nueva (`X-Modal-Next`).

## Componentes y responsabilidades

### `competition/services/predictions.py` (nuevo)

Encapsula la regla del "siguiente pendiente" para poder testarla aislada de la vista.

```python
def next_pending_match(user, after_match=None) -> Match | None:
    """Devuelve el siguiente partido pronosticable por `user` sin Prediction suya.
    Excluye `after_match` si se pasa. Orden: kickoff asc, pk asc.
    `predictions_open` se evalúa en Python (depende de `now()` y del gate de jornada).
    """

def pending_matches_count(user) -> int:
    """Total de partidos pronosticables por `user` sin Prediction suya."""
```

### `competition.views.PredictView`

- **GET**: añade al contexto `pending_count` y `has_next`.
  - `pending_count = pending_matches_count(request.user)`.
  - `has_next = next_pending_match(request.user, after_match=m) is not None`.
- **POST**: tras `update_or_create` de la `Prediction`, si `request.POST.get("chain") == "1"`:
  - Si hay siguiente, responde 200 con cuerpo vacío y cabeceras:
    - `X-Modal-Next: /pronosticar/<next.id>/`
  - Si no hay siguiente, añade `messages.success("¡Has apostado todos los partidos disponibles!")` y responde con `X-Modal-Redirect: /` (URL del dashboard).
  - Si no hay `chain`, comportamiento idéntico al actual.

### `templates/competition/_predict_modal.html`

- Eyebrow: `PRONÓSTICO · {{ pending_count }} pendiente{{ pending_count|pluralize }}`.
- Botonera condicional:
  - Si `has_next`: *Cancelar* (ghost) · *Guardar pronóstico* (ghost) · *Guardar y siguiente* (primary, `name="chain" value="1"`).
  - Si no: *Cancelar* (ghost) · *Guardar pronóstico* (primary). Sin botón de chain.

### `static/js/modal.js`

En `onSubmit`, comprobar primero `X-Modal-Next`:

```js
const next = res.headers.get("X-Modal-Next");
if (next) { await openModal(next); return; }
```

Resto del flujo (X-Modal-Redirect, X-Modal-Errors, reload) intacto.

## Data flow

### GET `/pronosticar/<id>/`

1. Validaciones existentes (rol jugador, `editable`, jornada desbloqueada).
2. `pred = Prediction.objects.filter(player, match).first()`.
3. `pending_count = pending_matches_count(user)`.
4. `has_next = next_pending_match(user, after_match=m) is not None`.
5. Render `_predict_modal.html` con `match`, `pred`, `pending_count`, `has_next`.

### POST `/pronosticar/<id>/` con `chain=1`

1. Validaciones existentes (`predictions_open`, parseo de marcador → si inválido, `X-Modal-Errors: 1` con la plantilla; no se avanza).
2. `Prediction.objects.update_or_create(player=user, match=m, defaults={"home": h, "away": a})`.
3. `nxt = next_pending_match(user, after_match=m)`.
4. Si `nxt`: respuesta `HttpResponse(status=204)` con `X-Modal-Next: reverse("competicion:predict", args=[nxt.id])`.
5. Si no `nxt`: `messages.success(...)`, respuesta con `X-Modal-Redirect: reverse("competicion:dashboard")`.

### POST `/pronosticar/<id>/` sin `chain`

Comportamiento actual: `update_or_create` + `messages.success` + `redirect("competicion:dashboard")` (el JS detecta `res.ok` y recarga). Sin regresión.

## Edge cases

- **Marcador inválido con `chain=1`**: respuesta `X-Modal-Errors: 1` con la misma plantilla y errores; no se guarda ni se avanza.
- **Apuestas cerradas entre GET y POST**: `PermissionDenied` (comportamiento actual). No se guarda.
- **Otro dispositivo del usuario ya apostó el siguiente**: el servicio lo excluye y devuelve el siguiente real (o `None`).
- **Empate de `kickoff`**: orden secundario por `pk`.
- **Solo queda el actual**: GET ya envía `has_next=False`, el botón no se renderiza; no es posible llegar a un POST con `chain=1` sin siguiente salvo carrera (otro dispositivo apostó después de cargar el modal). En ese caso `nxt` será `None` y caemos al toast final, que es razonable.
- **Usuario sin rol jugador**: bloqueado por la check `is_jugador` existente.

## Testing

TDD: servicios primero, luego vista.

### `competition/tests/test_next_pending.py`

- `next_pending_match` devuelve `None` cuando no hay candidatos.
- Excluye partidos con resultado (`done`).
- Excluye partidos cuya jornada está bloqueada por el gate.
- Excluye partidos `closed`/`live` (no editables).
- Excluye partidos con `Prediction` previa del mismo usuario.
- No excluye partidos donde otros usuarios sí han apostado.
- `after_match=m` excluye `m` aunque cumpla el resto.
- Ordena por `kickoff` ascendente, desempate por `pk`.
- `pending_matches_count` cuenta exactamente los mismos candidatos sin `after_match`.

### `competition/tests/test_predict_chain_view.py`

- GET incluye `pending_count` y `has_next` correctos en el contexto.
- POST con `chain=1` y siguiente disponible: status 200 + `X-Modal-Next` apuntando al modal del siguiente. `Prediction` creada o actualizada.
- POST con `chain=1` y sin siguiente: `X-Modal-Redirect` al dashboard. Mensaje de éxito en `messages`.
- POST sin `chain`: redirect normal al dashboard. Sin regresión.
- POST con marcador inválido y `chain=1`: `X-Modal-Errors: 1`. Sin avance ni cambios.

### Verificación manual

Tras los tests, ejecutar el proyecto y comprobar en navegador:
1. Abrir modal de un partido sin apuesta, contador correcto, pulsar "Guardar y siguiente", el modal se sustituye por el siguiente sin recarga.
2. Encadenar hasta el último, comprobar que el botón desaparece y que al guardar se vuelve al dashboard con el toast.
3. Marcador inválido con `chain=1` no avanza.

## Fuera de alcance

- Cambios en el flujo del gestor de resultados (`ResultOfficialView` / `manage_results.html`).
- Cola pre-cargada en cliente.
- Indicador de progreso "X de Y" (queda como mejora futura si se pide).
- Cambios visuales más allá del eyebrow y la nueva botonera.
