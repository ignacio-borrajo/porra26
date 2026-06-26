# Diseño — Arreglo de cruces R32 (Dieciseisavos)

Fecha: 2026-06-26
Rama: `worktree-fix-cruces-r32`

## Problema

Los cruces de Dieciseisavos (R32, partidos `M73`–`M88`) tienen:

1. **Fechas y horas incorrectas** en el calendario.
2. **Orden incorrecto** de los cruces en el cuadro de la pantalla de Competición.

Además se han detectado dos necesidades de proceso:

3. Un administrador ya asignó equipos a algún cruce de forma errónea; hay que
   **resetear** esos cruces.
4. Los equipos de los cruces KO **no deben rellenarse automáticamente**: para R32
   los asigna siempre un administrador a mano, para evitar errores.

## Decisiones tomadas (confirmadas con el usuario)

- **Zona horaria:** las horas de la especificación son hora local de Madrid
  (lo que muestra la app, `TIME_ZONE = "Europe/Madrid"`, `USE_TZ = True`).
  Se guardan en UTC (Madrid −2h en verano / CEST).
- **Auto-relleno:** se desactiva SOLO para R32. Octavos y rondas posteriores
  siguen autocompletándose desde el ganador del cruce anterior (`WM…`), porque
  eso solo ocurre cuando el admin ya ha confirmado el resultado del R32.
- **Orden 1–16 manda en toda la UI.** En escritorio las parejas se agrupan por
  posición (1-2, 3-4, …) en vez de por octavo destino.
- **Reset:** comando de gestión, ejecutado manualmente tras el deploy
  (no automático en el arranque).

## Datos correctos (fuente de verdad: `fixtures/world_cup_2026.json`)

| Orden | Código | Local (Madrid) | Guardado (UTC) |
|-------|--------|----------------|----------------|
| 1  | M74 | 29-jun 22:30 | `2026-06-29T20:30:00Z` |
| 2  | M77 | 30-jun 23:00 | `2026-06-30T21:00:00Z` |
| 3  | M73 | 28-jun 21:00 | `2026-06-28T19:00:00Z` |
| 4  | M75 | 30-jun 03:00 | `2026-06-30T01:00:00Z` |
| 5  | M83 | 03-jul 01:00 | `2026-07-02T23:00:00Z` |
| 6  | M84 | 02-jul 21:00 | `2026-07-02T19:00:00Z` |
| 7  | M81 | 02-jul 02:00 | `2026-07-02T00:00:00Z` |
| 8  | M82 | 01-jul 22:00 | `2026-07-01T20:00:00Z` |
| 9  | M76 | 29-jun 19:00 | `2026-06-29T17:00:00Z` |
| 10 | M78 | 30-jun 19:00 | `2026-06-30T17:00:00Z` |
| 11 | M79 | 01-jul 03:00 | `2026-07-01T01:00:00Z` |
| 12 | M80 | 01-jul 18:00 | `2026-07-01T16:00:00Z` |
| 13 | M86 | 04-jul 00:00 | `2026-07-03T22:00:00Z` |
| 14 | M88 | 03-jul 20:00 | `2026-07-03T18:00:00Z` |
| 15 | M85 | 03-jul 05:00 | `2026-07-03T03:00:00Z` |
| 16 | M87 | 04-jul 03:30 | `2026-07-04T01:30:00Z` |

Los `home_slot`/`away_slot` y los slots `WM…` de octavos **no se tocan**: solo
cambian `kickoff` y se añade `bracket_order`.

## Cambios

### 1. Modelo de datos
- Añadir `Match.bracket_order` (`PositiveSmallIntegerField`, `null=True`,
  `blank=True`). Solo los 16 cruces R32 llevan valor 1–16; el resto del KO queda
  `null`.
- Migración de esquema que añade el campo.

### 2. Fixture + seed
- Corregir `kickoff` y añadir `bracket_order` a M73–M88 en
  `fixtures/world_cup_2026.json`.
- `competition/management/commands/seed_world_cup_2026.py`: escribir
  `bracket_order` y refrescar `kickoff` en partidos ya existentes (idempotente),
  de modo que una instalación nueva quede correcta.

### 3. Orden 1–16 en la UI (`competition/views.py`)
- Los R32 se ordenan por `bracket_order` (con `bracket_code` como desempate).
- Para R32, las parejas de escritorio se agrupan por posición (chunks de 2:
  posiciones 1-2, 3-4, …) en lugar de por `feeds_into_code`.
- Los conectores SVG siguen apuntando al octavo correcto vía `data-feeds-into`
  en `_match_card.html` (sin cambios); alguna línea puede cruzarse visualmente,
  es aceptable.
- Móvil/lista usan `entry.matches`, que ya queda en el orden 1–16.

### 4. Sin auto-relleno en R32 (`competition/services/bracket.py`)
- `propagate_after_match` excluye `round_id="r32"` del queryset de pendientes.
- Resultado: al cerrar los grupos NO se rellenan los equipos de R32; los asigna
  el gestor con la pantalla "Asignar equipos" (`AssignTeamsView`, ya existe).
- Octavos+ siguen propagándose desde `WM…` al confirmar el resultado del R32.

### 5. Comando de reset (`reset_r32_crosses`)
Nuevo management command que, sobre la BD existente:
- Reaplica `kickoff` + `bracket_order` corregidos a M73–M88.
- Devuelve los 16 R32 a estado `pending_teams`: limpia `home`/`away`, resultados
  (`result_home`/`result_away`/`finished_at`), puntos congelados, **borra los
  pronósticos** de esos partidos, `live_score` y reportes asociados
  (reutilizando los servicios `clear_match_result` / lógica de `delete_match`).
- Por seguridad, limpia también equipos/resultados propagados a octavos+ que se
  hubieran derivado de esos R32.
- Idempotente y reproducible. Se ejecuta manualmente tras el deploy:
  `python manage.py reset_r32_crosses`.

### 6. Tests (TDD)
- **Fixture:** los 16 `kickoff` y `bracket_order` coinciden con la tabla.
- **Orden:** la vista de Competición devuelve los R32 en orden 1–16; las parejas
  son chunks de 2 por posición.
- **Propagación:** cerrar todos los grupos NO rellena equipos en R32; confirmar
  el resultado de un R32 SÍ rellena el octavo correspondiente.
- **Reset:** tras el comando, los R32 quedan en `pending_teams`, sin pronósticos,
  con `kickoff`/`bracket_order` correctos; octavos+ derivados quedan limpios.

### 7. Docs
- Actualizar `docs/DATA_MODEL.md`: la asignación de equipos en R32 es manual
  (gestor), no automática.

## Flujo de entrega

Worktree → implementación TDD → PR → merge → CI verde (Railway despliega desde
`main`). El reset en producción es un paso manual posterior al deploy.

## Fuera de alcance

- No se cambian los emparejamientos del cuadro (qué ganador va a qué octavo): los
  slots `WM…` se mantienen.
- No se desactiva la propagación de octavos/cuartos/semis/final.
- No se modifican fechas/horas de otras rondas.
