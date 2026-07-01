# Rediseño de partidos KO: sin auto-asignación, vista por columnas y edición por el admin

**Fecha:** 2026-07-01
**Estado:** Diseño aprobado — pendiente de plan de implementación

## Problema

La visualización actual de las eliminatorias (bracket tipo grilla) genera confusión:
los cruces no se corresponden con la realidad, están mal creados y la asignación
automática de equipos propaga esos errores. Esto hace que los usuarios desconfíen
de la aplicación.

## Objetivos

1. **Que ningún equipo se asigne automáticamente en ninguna eliminatoria.** El admin
   asigna a mano.
2. **Cambiar la visualización** de la grilla bracket a **una columna por ronda**, con
   las cards de partido ya existentes dentro de su columna, ordenadas por fecha
   (no finalizados arriba).
3. **Permitir al admin editar cualquier partido**: asignar los equipos y fijar la
   fecha/hora. Los recordatorios de cierre deben respetar la fecha/hora que fije el
   admin.

## Alcance / decisiones tomadas

- **Slots KO:** se ignoran. Un partido sin equipos muestra **"Por definir"**; ya no se
  muestran etiquetas de slot ("Ganador M73", "1º Grupo A"), porque el cableado del
  bracket estaba mal y confundía.
- **Orden por columna:** primero los **no finalizados** (`status != done`) por `kickoff`
  ascendente; después los **finalizados** (`done`) por `kickoff` ascendente.
- **Recordatorios al cambiar kickoff:** si el nuevo `kickoff` es futuro (`> now`), se
  **resetean** los `BetsReminderLog` automáticos (2h/30min) de ese partido para que
  vuelvan a dispararse en las nuevas ventanas.
- **Edición del admin:** un único modal "Editar partido" para **cualquier** partido
  (grupos y KO). Permite cambiar equipos y kickoff. Si al cambiar equipos hay
  pronósticos, pide confirmación y los borra (misma lógica que hoy en `AssignTeamsView`,
  que queda absorbida).
- **Saneamiento de datos actuales:** management command `reset_ko_assignments` que
  nulifica equipos y borra pronósticos de partidos KO **sin resultado oficial**.

## Diseño

### Cambio 1 — Desactivar la auto-asignación de equipos KO

- **`competition/services/resolve.py`**: eliminar la llamada a `propagate_after_match(match)`
  dentro de `resolve_match` (hoy en `resolve.py:42`). Resolver un partido ya no rellena
  el siguiente cruce. La función `propagate_after_match` deja de invocarse desde el flujo
  de producción (se puede conservar en `bracket.py` sin uso, o retirarla; la retirada de
  la llamada es lo imprescindible).
- **`templates/competition/_match_card.html`**: un partido sin equipos
  (`home`/`away` nulos) muestra **"Por definir"** en ambos lados, sin `slot_label`. Los
  partidos KO sin equipos quedan en estado `pending_teams` hasta asignación manual.
- **`competition/management/commands/reset_ko_assignments.py`** (nuevo):
  - Selecciona partidos KO (`round_id in KO_ROUND_IDS`) con `status != "done"`
    (sin resultado oficial).
  - Pone `home=None`, `away=None` y borra los `Prediction` asociados a esos partidos.
  - Soporta `--dry-run` para listar sin escribir.
  - Es una limpieza puntual del estado corrupto en producción.

### Cambio 2 — Visualización: una columna por ronda

- **Vista** `CompetitionView.get()` (rama KO, `views.py:107-140`): sustituir la
  construcción de `feeds_map` / `pairs` / `_group_into_pairs()` por
  `ko_rounds = [{"round": r, "matches": [...]}]`. Cada lista de matches se ordena:
  1. No finalizados (`status != "done"`), por `kickoff` ascendente.
  2. Finalizados (`done`), por `kickoff` ascendente.
  - Eliminar del contexto lo específico del bracket (`feeds_into_code`, pares).
- **Template** nuevo `templates/competition/_ko_columns.html` (reemplaza el include de
  `_ko_canvas.html` en `dashboard.html`): contenedor con scroll horizontal; una columna
  por ronda (Dieciseisavos · Octavos · Cuartos · Semis · Final), cada una con cabecera
  (nombre de ronda) + pila vertical de `_match_card.html` (se reutiliza sin cambios de
  estructura, más allá del "Por definir").
- **CSS** (`static/css/styles.css`): retirar la grilla bracket (spans por ronda,
  `.ko-pair`, `.ko-connectors`) y añadir estilos de columnas planas (flex, scroll
  horizontal, cabecera de columna). Mantener el contenedor con scroll horizontal.
- **JS** (`static/js/ko-bracket.js`): retirar el dibujado de conectores SVG y la lógica
  de parejas. Mantener scroll a la columna activa, chips de navegación por ronda y
  arrastre-para-desplazar.
- **Vista de grupos:** sin cambios.

### Cambio 3 — El admin edita cualquier partido (equipos + fecha/hora)

- **Vista nueva** `MatchEditView` (GET modal + POST) en `/resultados/<id>/editar/`,
  restringida a gestores. Aplica a **cualquier** partido.
- **Modal** `templates/competition/_match_edit_modal.html`: selector de equipo local,
  selector de equipo visitante y campos de fecha + hora (`kickoff`). Se permite dejar
  equipos vacíos → "Por definir". Si ambos están informados, valida que sean distintos.
- **POST**:
  - Actualiza `home`, `away`, `kickoff`.
  - **Invalidación de pronósticos**: si el partido ya tenía equipos y hay pronósticos y
    cambian los equipos, exige `confirm_invalidate=1`; al confirmar, borra los
    pronósticos del partido. Reutiliza la lógica actual de `AssignTeamsView`, que queda
    absorbida por esta vista (se retira `AssignTeamsView` y su ruta, o se redirige a la
    nueva).
  - **Reset de recordatorios**: si `kickoff` cambia y el nuevo es `> now`, borrar los
    `BetsReminderLog` de tipos automáticos (`AUTO_KINDS`) de ese partido.
- **UI**: botón "Editar" en las filas/cards de `manage_results.html`, disponible para
  todos los estados de partido (pendiente, próximo, en juego, finalizado).
- **Recordatorios**: `send_match_reminders` ya opera sobre `kickoff`; al respetar el
  nuevo horario y haberse reseteado los logs, los avisos se reprograman solos.

## Pruebas (TDD)

- `resolve_match` **no** propaga equipos al siguiente cruce tras resolver un partido.
- Ordenación por columna: no-finalizados (asc por kickoff) antes que finalizados (asc).
- `MatchEditView`:
  - Asigna equipos y kickoff correctamente.
  - Permite dejar equipos vacíos ("Por definir").
  - Rechaza dos equipos iguales.
  - Exige `confirm_invalidate` y borra pronósticos al cambiar equipos con pronósticos.
  - Al mover `kickoff` a futuro, borra los `BetsReminderLog` automáticos del partido.
- `reset_ko_assignments`: nulifica equipos y borra pronósticos solo en KO `status != done`;
  `--dry-run` no escribe.

## Fuera de alcance

- No se rediseña la vista de grupos.
- No se elimina el modelo de slots/`bracket_code` de la base de datos (solo se deja de
  usar para auto-asignar y de mostrar como etiqueta); una limpieza de esquema queda para
  otra iteración si se desea.
