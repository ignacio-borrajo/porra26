# Puntuación parametrizable por ronda — diseño

> **Fecha:** 2026-06-03
> **Estado:** propuesto
> **Autor:** brainstorming con Ignacio
> **Sustituye / extiende:** [2026-06-02 — Premios config y vista](2026-06-02-premios-config-y-vista-design.md)

## 1. Objetivo

Permitir al gestor configurar, por cada ronda del Mundial, **cuántos puntos vale el marcador exacto** y **cuántos vale acertar solo el resultado (1·X·2)**. La sección vive dentro de la página actual de Premios, que pasa a llamarse "Premios y puntos".

Los cambios afectan **solo a los partidos cuyo resultado aún no se ha confirmado**. Los partidos ya resueltos conservan los puntos con los que se cerraron en su momento.

## 2. Estado actual

- Los puntos por marcador exacto son fijos por ronda y están en `Round.points` (Grupos 3, R32 5, Octavos 7, Cuartos 10).
- El "1 punto" por acertar solo el resultado está **hardcodeado** en `competition/services/score.py:15` (`return 1`) y en textos visibles de la página de Reglas.
- La página `pot/prizes_settings.html` tiene dos bloques: podio final y premio por ganador de jornada. No expone puntuación.
- Varios sitios deducen "esto fue un marcador exacto" comparando `earned == round.points`:
  - `competition/services/standings.py:42` (`Q(earned=F("match__round__points"))`)
  - `stats/services/kpis.py:11-19` (donut)
  - `competition/views.py:324-337` (modal de detalle de partido)

## 3. Modelo de datos

### `Round`
Nuevo campo:

| Campo | Tipo | Default | Notas |
|-------|------|---------|-------|
| `partial_points` | `PositiveSmallIntegerField` | `1` | Puntos al acertar solo el resultado (1·X·2). |

`Round.points` queda como está; conceptualmente pasa a representar formalmente "puntos por marcador exacto". No se renombra la columna para no romper migraciones existentes y código que ya la lee.

### `Match`
Dos campos nuevos, ambos nullables:

| Campo | Tipo | Notas |
|-------|------|-------|
| `exact_points_applied` | `PositiveSmallIntegerField` (null) | Snapshot de `round.points` en el momento de resolver el partido. |
| `partial_points_applied` | `PositiveSmallIntegerField` (null) | Snapshot de `round.partial_points` en el momento de resolver el partido. |

**Justificación del snapshot.** La regla es "cambios solo a futuro". El `earned` calculado en `Prediction` ya queda fijado, pero el sistema necesita seguir sabiendo si un acierto fue "exacto" (para el donut, el ranking de exactos en la clasificación, y la marca "exacto +N pts" en el modal de detalle). Si comparamos contra `round.points` actual, un cambio posterior reclasifica los exactos viejos. Congelando los puntos en `Match` el cálculo "esto fue exacto" se mantiene correcto eternamente.

## 4. Lógica de cálculo

### `competition/services/score.py`
Se elimina el `return 1` literal. La función pasa a leer los snapshots del propio partido:

```python
def score(pred, match) -> int | None:
    if match.result_home is None or match.result_away is None:
        return None
    if pred.home == match.result_home and pred.away == match.result_away:
        return match.exact_points_applied
    if _sign(pred.home - pred.away) == _sign(match.result_home - match.result_away):
        return match.partial_points_applied
    return 0
```

Precondición: `score()` siempre se llama desde `resolve_match()`, que se encarga de garantizar que los snapshots están seteados antes (paso siguiente).

### `competition/services/resolve.py`
Antes del recálculo de `earned`, congela los puntos en el match **solo si todavía son `None`**:

```python
if match.exact_points_applied is None:
    match.exact_points_applied = match.round.points
    match.partial_points_applied = match.round.partial_points
    match.save(update_fields=[..., "exact_points_applied", "partial_points_applied"])
```

Eso preserva el contrato "solo a futuro" también cuando el gestor **edita** un resultado tras un cambio de puntuación: el segundo `resolve_match` no re-lee `Round`.

### Sitios que comparan `earned == round.points`
Pasan a comparar contra `match.exact_points_applied`:

- `competition/services/standings.py:42` → `exact_hits=Count("id", filter=Q(earned=F("match__exact_points_applied")))`.
- `stats/services/kpis.py:11` → `values_list("earned", "match__exact_points_applied")`.
- `competition/views.py:324,337` (`MatchDetailView`) → `round_points = m.exact_points_applied or m.round.points` (el fallback cubre la vista de un partido aún sin resolver, donde sigue mostrándose "vale hasta N pts").

## 5. UI

### Topbar y título
- Enlace del topbar: **"Premios"** → **"Premios y puntos"**.
- Título de la página y `<title>`: "Premios y puntos del bote · PORRA 26".
- URL sin cambios (`/premios/`).

### Plantilla `pot/prizes_settings.html`
Orden de los bloques (siguiendo la estética glass existente):

```
[stats glass]  Bote total · Por jugador · Pagos confirmados

01 · Podio final                                  (igual que hoy)
   1º [____] €   2º [____] €   3º [____] €

02 · Premio por ganador de jornada                (igual que hoy)
   [____] €

03 · Puntuación por ronda                         ← NUEVO
   Define cuántos puntos vale cada acierto en cada ronda.
   Los cambios se aplican solo a los partidos cuyo resultado
   aún no se ha confirmado.

   Ronda             Exacto    Solo resultado (1·X·2)
   Fase de grupos    [  3 ] pts   [ 1 ] pts
   Dieciseisavos     [  5 ] pts   [ 1 ] pts
   Octavos           [  7 ] pts   [ 1 ] pts
   Cuartos           [ 10 ] pts   [ 1 ] pts
   Semifinales       [ 12 ] pts   [ 1 ] pts
   Final             [ 15 ] pts   [ 1 ] pts

[Guardar premios y puntos]
```

- Un único formulario que envía premios + puntuación juntos.
- Inputs nuevos: `name="exact_<round_id>"` y `name="partial_<round_id>"`. Tipo `number`, `min="0"`, `step="1"`, `inputmode="numeric"`.
- Auditoría: además del `prize_changed` existente, se registra **una sola** entrada `scoring_changed` con payload `{round_id: {exact, partial}}` listando solo las rondas que cambiaron de valor.

### Vista `PrizesSettingsView.post` (`pot/views.py`)
Se amplía el handler dentro del mismo `transaction.atomic`:

1. Itera `Round.objects.all()`. Por cada round:
   - Parsea `exact_<id>` y `partial_<id>` como `int >= 0` (helper `_parse_int`). Si alguno es inválido, ignora **ese campo** (no rompe el resto, mismo patrón que premios).
   - Si el valor parseado difiere del actual, actualiza el round (`update_fields=["points"]` o `["partial_points"]`) y registra el cambio en un dict para auditar.
2. Si hay cambios, crea un `AuditLog` con `action="scoring_changed"` y payload con los rounds modificados.
3. Mensaje de éxito unificado: "Premios y puntos actualizados.".

### Contexto adicional
`PrizesSettingsView.get` pasa `rounds = Round.objects.all().order_by("order")` al template.

### Página de Reglas (`core/views.py` + `templates/core/rules.html`)
- La tabla "Cuánto se gana en cada partido" pasa a 3 columnas: **Ronda · Exacto · 1·X·2**. Cada fila lee `r.points` y `r.partial_points`.
- Los tres chips de ejemplo (+3 pts exacto, +1 pt, 0 pts) **siguen con valores fijos** — son ilustrativos del concepto, no la verdad operativa. Se añade un microtexto bajo la tabla: *"Los valores arriba son los actuales — los puede ajustar un gestor."*
- Se reemplaza la línea hardcodeada "Acertar solo el resultado (1·X·2) siempre vale 1 punto, sea cual sea la ronda" por: *"Acertar solo el resultado (1·X·2) suma los puntos indicados en la columna 1·X·2."*

## 6. Migraciones

### `competition/0006_round_partial_points.py`
- `AddField` `Round.partial_points` con `default=1`. Las 6 rondas existentes quedan en `1`, que es el comportamiento actual. No requiere `RunPython`.

### `competition/0007_match_points_applied.py`
- `AddField` `Match.exact_points_applied` (null=True).
- `AddField` `Match.partial_points_applied` (null=True).
- `RunPython` que recorre `Match.objects.filter(finished_at__isnull=False).select_related("round")` y, para cada uno, fija:
  - `exact_points_applied = match.round.points`
  - `partial_points_applied = match.round.partial_points`  (= 1 tras la migración anterior)
- `reverse_code = migrations.RunPython.noop` (los campos se eliminan con `RemoveField`).

Tras la migración, todos los partidos ya resueltos tienen sus snapshots correctos. Los partidos pendientes los reciben en su próximo `resolve_match`.

## 7. Tests

### Nuevos / extendidos

- `competition/tests/test_score.py`
  - Round con `points=5, partial_points=2`: exacto → 5, parcial → 2, fallo → 0.
  - Round con `partial_points=0`: parcial → 0, exacto sigue funcionando.

- `competition/tests/test_resolve.py` (extender)
  - Tras `resolve_match`: `match.exact_points_applied == round.points` y `partial_points_applied == round.partial_points`.
  - Caso "edición tras cambio de puntuación": resolver un partido con `points=3`, cambiar `round.points=10`, volver a `resolve_match` (corrección del resultado) → los snapshots siguen siendo `3, 1`, los `earned` se recalculan con esos valores.

- `competition/tests/test_standings.py` (si existe; si no, se añade un caso mínimo)
  - `exact_hits` cuenta correctamente cuando el partido se resolvió con `points=3` y ahora `round.points=5`.

- `stats/tests/test_kpis.py` (extender)
  - Donut: el partido viejo con `earned=3` y snapshot `exact_points_applied=3` sigue contando como `exact`, aunque `round.points` actual sea 5.

- `pot/tests/test_prizes_view.py` (extender o crear si no existe)
  - POST con `exact_groups=4&partial_groups=2`: actualiza Round.
  - POST con valores negativos o no numéricos: se ignoran sin romper, no se audita la fila inválida.
  - Auditoría `scoring_changed` solo cuando algún valor realmente cambia.
  - Solo gestor accede.

- `core/tests/test_rules.py` (extender)
  - El render incluye `partial_points` de cada ronda en la tabla.

## 8. Documentación

- `docs/DATA_MODEL.md` §2: actualizar la descripción del cálculo y la tabla de puntos para reflejar que ambos componentes son parametrizables y que se persisten snapshots en `Match`.
- `CLAUDE.md` §"Reglas de negocio clave": añadir una línea: "Los puntos por exacto y por 1X2 son parametrizables por ronda desde Premios y puntos."

## 9. Lo que NO entra en este alcance

- Granularidad por jornada de grupos (mantenemos 6 entradas por ronda; J1/J2/J3 comparten valores).
- Pestaña / página independiente "Puntuación".
- Recalcular puntos del histórico al cambiar la tabla (acordado: solo a futuro).
- Cambios en el correo de cierre, en el PDF de cierre, o en el ranking (no dependen de los puntos; solo reflejan lo ya calculado).
