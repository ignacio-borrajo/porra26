# Rankings en directo — banda de partidos en juego + clasificaciones live

Fecha: 2026-06-11
Estado: aprobado

## Motivación

Cuando hay partidos en juego, el dashboard de Competición ya muestra marcadores parciales y una clasificación "live" (puntos congelados + puntos hipotéticos de los `LiveScore`). La pantalla de **Rankings**, en cambio, sigue mostrando puntos oficiales congelados y no informa de qué partidos se están jugando. El jugador que entra a Rankings durante una jornada con partidos en juego no ve nada moverse, aunque su posición real "ahora mismo" sí está cambiando.

Esta iteración alinea Rankings con el patrón ya existente del dashboard:

1. Una **banda de partidos en juego** (con marcador parcial y minuto/periodo) en todas las pestañas.
2. Las **tablas de clasificación** usan `live_standings()` en vez de `standings()`, así que las posiciones reflejan el estado en directo.

## Alcance

**Aplica a:**
- `RankingsView` (`stats/views.py`) — pestañas General, Sede, Puesto, Departamento.
- `GroupRankingsView` (`stats/views.py`) — detalle de un grupo (`/rankings/<dim>/<key>/`).

**No aplica a:**
- Histórico (`HistoryView`), Estadísticas personales (`StatsView`) — quedan con puntos oficiales. Histórico es retrospectivo; Estadísticas tiene KPIs por jugador que no se interpretan bien con números cambiando al vuelo.
- Dashboard de Competición — ya tiene live; no se toca.

## Comportamiento

### Layout — banda superior

Estructura vertical de la página de Rankings (igual en todas las pestañas y en el detalle de grupo):

```
┌──── Rankings ─────────────────────────────────┐
│ [General][Sede][Puesto][Departamento]         │
├───────────────────────────────────────────────┤
│ EN JUEGO · 2    [🇪🇸 ESP 2:1 FRA 🇫🇷 · 1H 38'] │
│                 [🇦🇷 ARG 0:0 BRA 🇧🇷 · HT]      │
├───────────────────────────────────────────────┤
│ {contenido específico de la pestaña actual}   │
└───────────────────────────────────────────────┘
```

- Banda `.glass` a ancho completo, insertada entre `.rankings-tabs` (nav existente) y el contenido de la pestaña.
- Si no hay partidos `live` ni `awaiting` → banda con placeholder: "No hay partidos en juego ahora mismo".
- Banda siempre presente (no se esconde). Layout estable, no salta cuando empieza/acaba un partido.
- En móvil: la lista de chips hace scroll horizontal (`overflow-x:auto`), cada chip mantiene su anchura.

### Chip de partido

Cada chip contiene, en horizontal:

```
🇪🇸 ESP   2 : 1   FRA 🇫🇷
        1H 38'
```

- Banderas y códigos TLA de los equipos (`match.home.flag`, `match.home.code`).
- Marcador con `score-bubble` (mismo componente que la match card del dashboard).
- Separador `:` con clase `live-colon` (rojo) cuando el partido está en juego puro.
- Pie del chip con el periodo/minuto:
  - `1H 38'`, `2H 67'`, `HT`, `ET 105'`, `PEN`, `Final` según `live_score.period` y `live_score.minute`.
  - Si `awaiting_validation` (FT pero el gestor no confirmó) → chip amarillo `chip-awaiting`, texto "Pendiente oficial" en vez del minuto, separador en color neutro (no rojo).
- Sin pulso animado (el pulso del dashboard reside en el chip de estado, no en la match card; aquí mantenemos la banda visualmente calmada).

### Auto-refresh

- Copiamos el bloque del dashboard (`templates/competition/dashboard.html:56-69`): `setInterval` 60 s, recarga completa.
- Pausado si `document.hidden` (pestaña en segundo plano) o si hay un `.ovl` abierto (modal en uso).
- Condicional a `has_live_matches` en el contexto: si no hay live ni awaiting, no se monta el `setInterval`.
- Aplica a `rankings.html` y `rankings_group.html`.

### Tablas en directo

`build_general_context()` y `group_standings()` cambian de `standings()` a `live_standings()`:

- `standings` (tabla "General") usa `live_pts` como ordenador y como número visible.
- `scope_standings` (tabla "Jornada"/"Ronda") idem.
- `group_standings()` (tablas Sede / Puesto / Departamento) suma `live_pts` por grupo → afecta `total`, `avg`, `top_pts` y el desempate del líder de grupo.
- `GroupRankingsView` reusa `build_general_context()`, por lo que el detalle de grupo hereda el comportamiento.

Cuando no hay ningún `LiveScore`, `live_pts == pts` para todos los jugadores → las tablas se ven exactamente igual que hoy.

## Arquitectura

### Backend

#### `competition/services/live_view.py` (nuevo)

Helper compartido entre `CompetitionView` y `RankingsView`/`GroupRankingsView`:

```python
def current_live_matches() -> tuple[list[Match], list[Match]]:
    """Devuelve (live_matches, awaiting_matches) ordenados por kickoff.

    Filtra `Match` con `status == 'live'`, ya con `live_score` precargado
    (select_related). Separa los que están en `awaiting_validation` (FT
    sin oficial) del resto.
    """
```

`CompetitionView` migra a este helper también, para no duplicar la lógica de separación que hoy vive inline en `competition/views.py:61-73`. Concretamente, sustituye el bucle que distribuye `matches` en `open/live/awaiting/done` por una llamada explícita; los partidos `open`/`done` del round activo siguen calculándose como hoy.

> Nota de scope: el helper devuelve **todos** los `live`/`awaiting` del torneo, no solo los del round activo. En el dashboard la sección "EN JUEGO" se filtra por round/jornada activos — esa parte sigue como está y NO usa el helper nuevo. El helper se usa para la banda de Rankings (que muestra todos los live) y, opcionalmente, como replacement de la separación awaiting/live dentro del bucle existente del dashboard si encaja sin sobrescribir el filtrado por round.

Si la integración limpia en `CompetitionView` no compensa, el helper queda solo para `stats/`. Decisión en el plan.

#### `stats/services/rankings_context.py`

- Importa `live_standings` en lugar de `standings`.
- Cambia las dos llamadas (`rows`, `scope_rows`).
- Después de cada llamada: `for r in rows: r.pts = r.live_pts` (idéntico al patrón de `competition/views.py:80-95`).
- Resto del flujo (`my_rank`, `max_pts`, scope, md_options, users_by_id) intacto.

#### `stats/services/group_standings.py`

- Importa `live_standings` en lugar de `standings`.
- Tras obtener `standings_rows = live_standings()`: `for r in standings_rows: r.pts = r.live_pts` antes del bucketing.
- `_row_for()` no se toca: ya lee `r.pts`.

#### `stats/views.py`

`RankingsView.get()` y `GroupRankingsView.get()` añaden al contexto:

```python
live_matches, awaiting_matches = current_live_matches()
ctx.update({
    "live_matches": live_matches,
    "awaiting_matches": awaiting_matches,
    "has_live_matches": bool(live_matches) or bool(awaiting_matches),
})
```

### Frontend

#### `templates/partials/_live_matches_strip.html` (nuevo)

Partial que renderiza la banda. Recibe `live_matches`, `awaiting_matches` y dibuja:

- Header `eyebrow` con "EN JUEGO · N" (N = `live_matches|length + awaiting_matches|length`).
- Lista horizontal de chips: primero `live_matches`, luego `awaiting_matches` (orden estable, ya vienen por kickoff).
- Si N == 0 → solo el header y un párrafo: "No hay partidos en juego ahora mismo".

#### `templates/stats/rankings.html` y `templates/stats/rankings_group.html`

Insertan el partial entre `<nav class="rankings-tabs">` y el contenido condicional (`{% if tab == "general" %}...`).

Ambos templates añaden un `{% block scripts %}` (si no lo tienen ya) con el bloque de auto-refresh condicional a `has_live_matches`, idéntico al del dashboard.

#### `static/css/styles.css`

Nuevas reglas:

- `.live-strip` — contenedor `.glass`, padding interno, gap entre header y lista.
- `.live-strip__list` — `display:flex; gap; overflow-x:auto; scroll-snap-type:x mandatory` (snap suave en móvil).
- `.live-strip__chip` — chip individual: padding, border-radius, fondo translúcido. Variante `.live-strip__chip--awaiting` con borde/fondo amarillo (reusar tokens de `chip-awaiting`).
- `.live-strip__chip-foot` — texto pequeño con minuto/periodo.
- `.live-strip__empty` — placeholder cuando no hay partidos.

Reutiliza `score-bubble`, `live-colon`, `team-flag` ya existentes.

## Edge cases

- **`live_score` ausente** en un `Match` con `status == 'live'` (kickoff recién pasado, cron aún no ha disparado): se muestra el chip con marcador "VS" en lugar de "X:Y", sin minuto. Coherente con el match card del dashboard, que tiene la misma rama de fallback.
- **Más de ~6 partidos simultáneos**: scroll horizontal del `.live-strip__list`. No paginamos ni colapsamos (el Mundial nunca tiene más de 4 simultáneos).
- **Banda con solo `awaiting`** (todos los live en directo acabaron pero el gestor no confirmó ninguno): header sigue diciendo "EN JUEGO · N" — es coherente con el dashboard, que también agrupa awaiting bajo el concepto "en juego" hasta confirmación.
- **Banda sin partidos pero la pestaña sigue refrescándose**: NO se refresca. `has_live_matches=False` desactiva el `setInterval`.
- **Pestaña Sede/Puesto/Dept con grupo "Sin asignar"**: `_row_for` ya maneja `__none__`; con live_pts el comportamiento es idéntico (se ordena por live_pts también).
- **Modal abierto al recargar**: el `setInterval` salta esa iteración (mismo guard `.ovl` que el dashboard); el usuario no pierde lo que está leyendo en un modal de detalle.

## Verificación

Tests a añadir (carpeta `stats/tests/`):

1. `test_rankings_uses_live_standings` — con un `LiveScore` que da +N puntos a un jugador, la tabla "General" coloca al jugador en la posición correspondiente.
2. `test_rankings_group_uses_live_standings` — `group_standings("sede")` refleja los puntos live en `total` y `top_pts`.
3. `test_rankings_live_strip_renders` — la banda muestra los partidos live + awaiting con marcador correcto.
4. `test_rankings_live_strip_empty` — sin partidos en juego, placeholder visible y `has_live_matches=False`.
5. `test_group_rankings_detail_inherits_live` — `GroupRankingsView` muestra puntos live en la tabla del detalle.

Test existentes a revisar:
- `stats/tests/test_rankings_*` — actualizar asserts si comparaban contra `standings()` directamente.
- `competition/tests/test_live_dashboard_view.py` — sigue verde; no se toca el dashboard salvo el refactor opcional del helper.

Verificación manual:
- Abrir `/rankings/?tab=general` sin partidos live → banda con "No hay partidos en juego ahora mismo", tabla idéntica a hoy.
- Crear un `LiveScore` desde admin (o `manage.py shell`) con un marcador "raro" y abrir las 4 pestañas → el chip aparece en todas, la tabla "General" cambia posiciones según las predicciones afectadas.
- Marcar el `LiveScore` como `period='FT'` (sin oficial) → el chip pasa a `chip-awaiting` con texto "Pendiente oficial".
- Validar auto-refresh: dejar la pestaña 70 s abierta → reload. Abrir un modal (chip clicable si lo es) → reload pausado.

## Decisiones explícitas

- **Las tablas siempre live, sin toggle.** Sin partidos live, `live_pts == pts`; con partidos live, queremos el comportamiento "en directo". Un toggle "oficial vs live" añade complejidad sin beneficio claro.
- **Banda siempre visible, incluso vacía.** Evita "saltos" de layout cuando arranca/acaba un partido y mantiene la página predecible.
- **Reutilizamos auto-refresh del dashboard (60 s, reload completo).** Sin SSE ni WebSockets; la latencia objetivo es minuto, no segundo. El cron de cron-job.org ya rueda cada minuto.
- **El chip de la banda NO es clicable a "detalle del partido".** Mantenerlo informativo y simple. Si el jugador quiere apostar/ver predicciones, va por la pestaña Competición.
- **Stats personales e Histórico quedan fuera.** Stats tiene KPIs que no encajan con números fluctuando; Histórico es retrospectivo.
