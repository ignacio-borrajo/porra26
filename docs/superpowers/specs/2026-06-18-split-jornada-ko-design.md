# Split de la jornada KO en dos jornadas (Dieciseisavos + Fases Finales)

**Fecha:** 2026-06-18
**Estado:** aprobado, pendiente de plan

## Contexto y motivación

Hoy la porra tiene **4 jornadas** con premio:

- 3 de la fase de grupos (J1, J2, J3), una opción independiente por matchday.
- 1 única jornada eliminatoria («Fases Finales») que agrega **todos** los
  partidos KO: `r32 + r16 + qf + sf + final`.

Dirección pide partir esa jornada KO en **dos**, generando dos ganadores y dos
premios nuevos:

- **Dieciseisavos** → solo `round_id="r32"`.
- **Fases Finales** (redefinida) → `r16 + qf + sf + final` (ya **no** incluye R32).

Resultado: **5 jornadas** con premio (3 grupos + 2 KO), cada una con su
clasificación, su ganador, su premio y su modal de victoria.

## Decisiones de producto (cerradas)

1. **Premio:** se mantiene el importe único `PotSettings.matchday_winner_prize`
   aplicado a las 5 jornadas. **No** se añaden campos nuevos al modelo ni a la UI
   del gestor. Único efecto económico: el bote reservado a jornadas pasa de 4× a
   5× ese importe.
2. **Etiquetas:** R32 = «Dieciseisavos» (su nombre real de ronda); el resto
   conserva la etiqueta ya existente «Fases Finales».

## Alcance

### 1. `announcements` — modelo y disparo

`announcements/models.py`:

- `WinnerAnnouncement.SCOPE_CHOICES`: retirar `("ko", …)`; añadir
  `("r32", "Jornada de dieciseisavos")` y `("finals", "Jornada de fases finales")`.
- Títulos (`title` property):
  - `r32` → «¡Ganador de Dieciseisavos!» / «¡Ganadores de Dieciseisavos!» (tied).
  - `finals` → «¡Ganador de las Fases Finales!» / «¡Ganadores de las Fases Finales!».
- Constraints únicos: sustituir `uniq_ann_ko` por `uniq_ann_r32` y
  `uniq_ann_finals` (mismas condiciones `Q(scope_kind=...)`).
- `__str__`: ramas para los dos nuevos scopes.

Migración (`announcements/migrations/`):

- Schema: `AlterField` de choices + drop `uniq_ann_ko` + add `uniq_ann_r32` y
  `uniq_ann_finals`.
- Data migration defensiva e idempotente: borra cualquier fila
  `scope_kind="ko"`. A día de hoy (mitad de fase de grupos) no puede existir
  ninguna —el anuncio KO solo se creaba al resolverse la Final—, pero la
  limpieza deja el estado consistente sin requerir verificación manual.

`announcements/services.py` — `detect_after_match`:

- `groups` con `matchday` → `matchday(N)` (sin cambios).
- `r32` → `_try_create("r32")`. Como `matchday_winners` devuelve `pending`
  mientras quede algún partido del scope sin resolver, basta con intentarlo tras
  cada partido R32; solo creará el anuncio cuando el último R32 se resuelva.
- `r16 / qf / sf` → nada (esperan a la Final).
- `final` → secuencia `("finals", "sede", "global")` (sustituye a la antigua
  `("ko", "sede", "global")`), en ese orden para el feed de modales.

`announcements/preview.py`:

- `_VALID_SCOPES = {"matchday", "r32", "finals", "global"}`.
- Ramas de preview de premio para `r32` y `finals` (ambas usan
  `matchday_winner_prize`, igual que hacía `ko`).

### 2. `pot/services/prizes.py`

- Sustituir la constante/uso de `_KO_ROUND_IDS` por los dos scopes:
  - `r32` → `standings(round_id="r32")` y `Match.objects.filter(round_id="r32")`.
  - `finals` → `standings(round_ids=["r16","qf","sf","final"])` y
    `Match.objects.filter(round_id__in=["r16","qf","sf","final"])`.
- `_matches_for_scope` / `_standings_for_scope`: ramas `r32` y `finals`.
- `announcement_podium`: ramas `r32` y `finals`.
- `_prizes_by_position_for`: ambas devuelven `matchday_winner_prize` (rama
  `else` actual ya lo cubre; verificar que `r32`/`finals` caen ahí).

### 3. `stats/services/matchday_options.py` (selector de Rankings)

Partir la opción única KO en dos opciones:

- **Dieciseisavos**: `round_id="r32"`, `matchday=None`, `key="r32:_"`,
  `round_ids=None`. `fully_resolved` según los partidos R32.
- **Fases Finales**: `round_id=None`, `round_ids=["r16","qf","sf","final"]`,
  `key="finals:_"`, label «Fases Finales». `fully_resolved` agregando esos
  partidos.

`current_option` y `parse_scope_key` no necesitan cambios estructurales (operan
sobre la lista de opciones por `key`). `rankings_context.py` ya soporta ambos
modos (`round_ids is not None` vs `round_id`+`matchday`) y **no se toca**.

### 4. UI / copys / docs

- `templates/pot/prizes_settings.html`:
  - El `<option value="ko">Jornada eliminatoria</option>` del previsualizador de
    modales se parte en `<option value="r32">` (Dieciseisavos) y
    `<option value="finals">` (Fases Finales).
  - Texto «4 jornadas» → «5 jornadas».
- `templates/core/rules.html`: «4 jornadas» → «5 jornadas» y describir la
  separación R32 / resto.
- `docs/DATA_MODEL.md`: actualizar la descripción de jornadas y del premio
  `matchdayWinnerPrize` (5 jornadas; R32 separada del resto KO).

## Fuera de alcance (confirmado que NO cambia)

- **Dashboard de Competición** (`competition/views.py`, bracket KO + clasificación
  en directo): su clasificación lateral ya es por ronda/jornada del selector y no
  usa el agregado KO; no se toca. El `KO_ROUND_IDS` de `competition/views.py` es
  para pintar el bracket, no para premios.
- **Podio global** (top 3) y **premio de sede**: sin cambios.
- `rankings_context.py`: sin cambios.

## Tests (TDD)

- `pot/services/prizes.py`: `matchday_winners(("r32", None))` y
  `("finals", None)` — pending / desierto / resolved / empate; `announcement_podium`
  para ambos scopes.
- `announcements/services.py`: `detect_after_match` con R32 (dispara `r32` en
  solitario al cerrar el último R32; no antes) y con Final (dispara
  `finals → sede → global` en orden).
- `stats/services/matchday_options.py`: dos opciones KO con sus keys/labels y
  `fully_resolved` correctos.
- Actualizar todos los tests existentes que asumen el scope `"ko"`.

## Riesgos / notas

- La etiqueta «Fases Finales» ahora excluye R32; es una decisión de copy
  explícita del usuario, no un descuido.
- Mantener sincronizada la página de Reglas (regla de proyecto en memoria).
- Flujo de entrega: worktree → PR → merge → CI verde (regla de proyecto).
