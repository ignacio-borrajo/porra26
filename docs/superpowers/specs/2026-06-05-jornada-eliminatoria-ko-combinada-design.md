# Spec — Premio por ganador de jornada eliminatoria (KO combinada)

**Fecha:** 2026-06-05
**Estado:** propuesto

## Goal

Implementar correctamente la regla del bote: hay **4 jornadas** en total y cada una entrega un premio al jugador con más puntos. Las tres primeras son las jornadas de la fase de grupos (1ª, 2ª, 3ª). La cuarta es una **jornada eliminatoria** que agrupa **TODOS** los partidos KO incluida la Final (dieciseisavos, octavos, cuartos, semifinales y Final). La Final no entrega premio aparte: su ganador cobra el del campeón del Mundial en el podio, pero **sus puntos sí cuentan** para decidir el ganador de la jornada eliminatoria.

## Por qué

La regla siempre fue ésa, pero la implementación actual la traduce mal: `announcements/services.py::detect_after_match` crea un anuncio de `scope_kind="round"` cada vez que se cierra una ronda eliminatoria, generando 4 premios de KO (dieciseisavos → octavos → cuartos → semifinales) en lugar de uno solo combinado. El copy de la página de Reglas también lo describía mal. El Mundial 2026 todavía no ha empezado (arranca el 2026-06-11), así que aún no hay anuncios reales emitidos y el cambio se puede hacer sin migración compatible-hacia-atrás.

## Comportamiento deseado

### Eventos de cierre y anuncios

| Partido recién resuelto | Anuncios creados |
|--|--|
| Cualquier partido de `groups`, jornada N (cuando se resuelve el último de esa jornada) | 1 anuncio `matchday` (matchday=N) |
| Cualquier partido de `r32`/`r16`/`qf`/`sf` | **ninguno** |
| El partido `final` (cuando se resuelve) | 3 anuncios simultáneos: `ko` + `sede` + `global` |

El anuncio `ko` se computa sobre la suma de puntos de **todos los partidos KO incluida la Final** (r32 + r16 + qf + sf + final, 31 partidos en el bracket del Mundial 2026).

### Importes

- `ko`: mismo importe que las jornadas de grupos → `PotSettings.matchday_winner_prize`.
- Empates en la jornada eliminatoria: misma regla que las jornadas de grupos (pts → exactos → aciertos; si tras las tres siguen empatados, comparten plaza y el importe se reparte a partes iguales).
- Si en la jornada eliminatoria **nadie suma puntos** (todos fallan los 31 partidos KO), el anuncio queda "desierto" — no se crea (mismo comportamiento actual para `matchday_winners` con todos a 0).

### Modal de ganador

- Título (single): `¡Ganador de las eliminatorias!`
- Título (tied): `¡Ganadores de las eliminatorias!`
- Layout: idéntico al modal actual de scope `round` (no necesita rediseño visual).
- Orden de aparición cuando hay 3 modales encolados al cerrarse la Final: `ko` → `sede` → `global` (climax al final).

### Scope eliminado

El scope `round` queda completamente retirado del modelo: se quita de `SCOPE_CHOICES`, se elimina la FK `scope_round`, se borra la `UniqueConstraint` `uniq_ann_round`, y se borran todos los anuncios `scope_kind="round"` existentes en cualquier DB (dev/test/prod — prod no tiene ninguno porque el Mundial no ha empezado).

## Arquitectura

### 1. `announcements.models.WinnerAnnouncement`

- `SCOPE_CHOICES`: quitar `("round", "Ronda KO")`, añadir `("ko", "Jornada eliminatoria")`. Resultado:
  ```python
  SCOPE_CHOICES = [
      ("matchday", "Jornada de grupos"),
      ("ko", "Jornada eliminatoria"),
      ("global", "Campeón del Mundial"),
      ("sede", "Ganadores por sede"),
  ]
  ```
- Eliminar el campo `scope_round = ForeignKey("competition.Round", ...)`.
- `Meta.constraints`: quitar `uniq_ann_round`; añadir
  ```python
  UniqueConstraint(
      fields=["scope_kind"],
      condition=Q(scope_kind="ko"),
      name="uniq_ann_ko",
  )
  ```
- `__str__`: rama `"ko"` devuelve `"Anuncio jornada eliminatoria"`.
- `title` (property): rama `"ko"` devuelve `"¡Ganadores de las eliminatorias!"` si `tied` else `"¡Ganador de las eliminatorias!"`.

### 2. `announcements.services.detect_after_match`

```python
def detect_after_match(match: Match) -> list[WinnerAnnouncement]:
    created: list[WinnerAnnouncement] = []
    if match.round_id == "groups" and match.matchday is not None:
        ann = _try_create("matchday", matchday=match.matchday)
        if ann is not None:
            created.append(ann)
    elif match.round_id == "final":
        # La Final cierra a la vez la jornada KO, el ganador del Mundial y los premios sede.
        # Orden de creación → orden de aparición en el modal feed (climax al final):
        # ko → sede → global.
        for ann in (
            _try_create("ko"),
            _try_create("sede"),
            _try_create("global"),
        ):
            if ann is not None:
                created.append(ann)
    # r32/r16/qf/sf: no se crea nada, esperan a que la Final cierre la jornada KO.
    return created
```

### 3. `announcements.services._try_create`

- Quitar la rama `scope_kind == "round"` (y el parámetro `round_id`).
- Añadir rama `scope_kind == "ko"`:
  - `filter_kwargs = {"scope_kind": "ko"}` (idempotencia: ya existe → return None).
  - Gating: igual que `sede`, requiere que la Final esté resuelta antes de calcular ganador.
  - Calcula vía `matchday_winners(("ko", None))`.
  - Crea con `scope_matchday=None`.
- Quitar `scope_round_id` de todos los `create()` calls.

### 4. `competition.services.standings.standings()`

- Añadir parámetro keyword-only `round_ids: list[str] | None = None`.
- Si `round_ids` no es `None`, filtrar `qs = qs.filter(match__round_id__in=round_ids)`.
- `round_id` y `round_ids` son mutuamente excluyentes — si se pasan los dos, raise `ValueError`.
- `scoped` debe ser `True` si cualquiera de `round_id`, `round_ids` o `matchday` está presente (sin streak/trend).

### 5. `pot.services.prizes`

- `_matches_for_scope(("ko", None))` → `Match.objects.exclude(round_id="groups")` (más simple que enumerar las cinco rondas KO, y se mantiene correcto si en el futuro alguien retoca los `id` de ronda).
- `_standings_for_scope(("ko", None))` → `standings(round_ids=["r32","r16","qf","sf","final"])`.
- `announcement_podium(announcement)`: añadir rama `ko` → `standings(round_ids=["r32","r16","qf","sf","final"])`. Quitar rama `round`.
- Quitar las ramas `kind == "round"` de `_matches_for_scope` y `_standings_for_scope`.

### 6. `announcements.preview`

- `_VALID_SCOPES`: `{"matchday", "ko", "global"}` (quitar `"round"`).
- En `build_preview`, sustituir la rama `scope == "round"` por `scope == "ko"`:
  ```python
  elif scope == "ko":
      pass  # no necesita scope_matchday ni scope_round
  ```
- `_preview_prize_for_position`: rama `position == 1 and scope in ("matchday","ko")` → `matchday_winner_prize`. Rama `global` sin cambios.
- `build_preview_podium`: la firma sigue tomando `scope`; la lógica funciona con `ko` sin cambios adicionales (sólo invoca `_preview_prize_for_position`).

### 7. `announcements.views.WinnerAnnouncementListView` (y demás)

- Quitar `select_related("scope_round")` de los queryset — el campo deja de existir.

### 8. `templates/pot/prizes_settings.html`

Bloque de preview (líneas 187-204): sustituir `<option value="round">Ronda eliminatoria</option>` por `<option value="ko">Jornada eliminatoria</option>`.

### 9. Copy

`templates/core/rules.html` (líneas 213-227, 274) y `templates/pot/prizes_settings.html` (líneas 62-83): reescribir el cuerpo del bloque "Premio por ganador de jornada". Texto propuesto:

> **Premio por ganador de jornada**
> Hay **4 jornadas** en total y cada una entrega un premio al jugador con más puntos en ella. Las tres primeras son las de la fase de grupos (1ª, 2ª y 3ª). La cuarta es la **jornada eliminatoria**: dieciseisavos, octavos, cuartos, semifinales **y la Final** cuentan todos juntos como una sola jornada. La Final no entrega premio aparte (su ganador cobra como campeón del Mundial en el podio), pero sus puntos sí suman para decidir al ganador de la jornada eliminatoria.

Sección de desempate `templates/core/rules.html:274`: `"Lo mismo aplica al premio por ganador de jornada y al premio por ganador de sede."` (ya estaba bien tras PR #45; se mantiene).

`docs/DATA_MODEL.md` (líneas 79, 86, 88-91, 158): reescribir alineado con el nuevo modelo. Anotar explícitamente que `matchdayWinnerPrize` se entrega 4 veces en total (3 grupos + 1 KO).

## Migración

Una sola migración nueva en `announcements/migrations/0004_drop_round_scope.py` con operaciones en este orden:

1. `RunPython(forward=delete_round_announcements, reverse=migrations.RunPython.noop)` donde `delete_round_announcements` es una función a nivel de módulo que hace `apps.get_model("announcements", "WinnerAnnouncement").objects.filter(scope_kind="round").delete()` — borrar anuncios `round` existentes (dev/test cleanup; prod no tiene ninguno). Función nombrada (no lambda) por compatibilidad con `makemigrations` y serialización.
2. `RemoveConstraint(model_name="winnerannouncement", name="uniq_ann_round")`.
3. `RemoveField(model_name="winnerannouncement", name="scope_round")`.
4. `AlterField(model_name="winnerannouncement", name="scope_kind", field=models.CharField(choices=[("matchday","Jornada de grupos"),("ko","Jornada eliminatoria"),("global","Campeón del Mundial"),("sede","Ganadores por sede")], max_length=10))`.
5. `AddConstraint(model_name="winnerannouncement", constraint=UniqueConstraint(fields=("scope_kind",), condition=Q(scope_kind="ko"), name="uniq_ann_ko"))`.

Reverse de la migración: noop para los datos (los anuncios borrados no se pueden reconstruir) y restauración manual de los campos/constraints si hiciera falta downgrade. Aceptable porque el cambio es destructivo intencionado.

## Testing

### Nuevos tests

- `competition/tests/test_standings.py::test_standings_round_ids_filters_matches` — verifica que `standings(round_ids=[...])` agrega solo predicciones de partidos en esas rondas.
- `competition/tests/test_standings.py::test_standings_round_id_and_round_ids_mutually_exclusive` — `ValueError` si se pasan ambos.
- `announcements/tests/test_models.py::test_ko_announcement_title_singular_and_plural` — `tied=False` → `"¡Ganador de las eliminatorias!"`, `tied=True` → `"¡Ganadores de las eliminatorias!"`.
- `announcements/tests/test_models.py::test_only_one_ko_announcement_allowed` — el segundo `create(scope_kind="ko")` levanta `IntegrityError`.
- `pot/tests/test_prizes.py::test_matchday_winners_ko_aggregates_all_ko_rounds_including_final` — fixture con al menos un partido por ronda KO (r32, r16, qf, sf, final); tras resolverlos, el ganador es el que más puntos suma agregando todas las rondas KO incluida la Final.
- `pot/tests/test_prizes.py::test_matchday_winners_ko_pending_until_final_resolved` — si la Final no está resuelta, devuelve `pending` aunque r32+r16+qf+sf lo estén.
- `announcements/tests/test_services.py::test_detect_after_ko_round_creates_no_announcement` — resolver el último partido de r32/r16/qf/sf no crea anuncio.
- `announcements/tests/test_services.py::test_detect_after_final_creates_ko_sede_global` — resolver la Final crea exactamente 3 anuncios (`ko`, `sede`, `global`) en ese orden.
- `announcements/tests/test_services.py::test_detect_after_final_ko_idempotent` — segunda llamada a `detect_after_match(final)` no duplica el anuncio `ko`.
- `announcements/tests/test_preview.py::test_preview_ko_scope_builds_announcement` — `build_preview("ko", tied=False, current_user=u)` devuelve `WinnerAnnouncement` válido sin tocar BD.

### Tests a actualizar

- `announcements/tests/test_services.py` (líneas 100-128 aprox): los tests que esperaban un anuncio `round` al cerrar una ronda KO se reescriben con la nueva regla (KO → ningún anuncio hasta la Final; Final → 3 anuncios).
- `announcements/tests/test_integration.py`: el flujo completo del Mundial debe producir 7 anuncios totales (3 matchday + 1 ko + 1 sede + 1 global + posibles previews) → ajustar contadores.
- `announcements/tests/test_models.py`: quitar los tests específicos de `scope_round` y `uniq_ann_round`.
- `announcements/tests/test_preview.py`: el test que crea preview de `round` se sustituye por uno de `ko`.

### Cobertura mínima

`pytest -q` debe pasar al 100% antes de PR. Especialmente los módulos `announcements/`, `pot/`, `competition/services/`.

## Fuera de scope

- No se redefine el sistema de puntos por ronda (`Round.points`, `Round.partial_points`): cada partido sigue puntuando según su ronda; lo único que cambia es **cómo se agrupan los puntos para decidir ganador de jornada**.
- No se cambia el modal global (P1/P2/P3 del Mundial) ni el modal de sede.
- No se añade indicador de progreso intermedio en la página de Reglas o Estadísticas — la jornada KO se mantiene en silencio hasta cerrarse.
- No se renombra el campo `PotSettings.matchday_winner_prize` (aunque conceptualmente cubre las 4 jornadas, el nombre actual sigue siendo razonable y renombrar arrastraría migraciones, vistas, tests… YAGNI).

## Riesgos y mitigaciones

- **Borrado destructivo de anuncios `round` existentes.** El Mundial no ha empezado, ningún anuncio real en prod. Dev/test pueden tener restos de seed/fixtures; los tests se actualizan a la nueva regla, así que regenerar fixtures es trivial.
- **Cambio de orden de aparición del feed de modales tras la Final.** Hoy un gestor vería: global + sede. Mañana verá: ko + sede + global. Coherente con "el campeón del Mundial es el clímax".
- **`standings(round_ids=...)` puede degradar performance** si se llama en bucle. Solo se invoca en `_standings_for_scope(("ko", None))` que se ejecuta una vez por cierre, y dentro de `announcement_podium` (al renderizar el modal). Aceptable.

## Open questions

Ninguna. Decisiones tomadas en el brainstorming:

- Final incluida en cálculo KO → sí.
- Modal dispara al resolverse la Final junto con global/sede → sí.
- Título: `¡Ganador de las eliminatorias!` / `¡Ganadores de las eliminatorias!` → sí.
- Scope `round` eliminado del modelo → sí.
- Orden de aparición ko → sede → global → confirmado en este spec.
