# Fase de grupos por jornadas — Diseño v1

> Fecha: 2026-06-01
> Autor: brainstorming asistido por Claude Code
> Estado: aprobado por el responsable, pendiente de plan de implementación
> Relacionado: `docs/superpowers/specs/2026-05-31-porra26-design.md`, `docs/DATA_MODEL.md` §3 (estados de partido)

Este documento fija el alcance, las reglas y la implementación de la **carga completa de la fase de grupos del Mundial 2026** y de la **apertura progresiva por jornadas** (J1 → J2 → J3) para la pantalla de Competición. Sustituye el fixture *placeholder* actual (`fixtures/world_cup_2026.json`, 4 partidos) por el calendario real.

El objetivo inmediato es **probar la plataforma con un grupo reducido de usuarios**: la prueba no requiere precisión absoluta sobre sedes ni cuadros de eliminatorias, pero sí calendario real, 48 selecciones y la mecánica de jornada que se describe abajo.

---

## 1. Decisiones tomadas en el brainstorming

| Pregunta | Decisión |
|----------|----------|
| Fuente del calendario | Lo busca el asistente en la web (Sky Sports + ToffeeWeb + Yahoo Sports, cruzado). Para la fase de prueba es suficiente. |
| Regla de "todos los partidos cerrados" para abrir la siguiente jornada | **Apuestas cerradas (kickoff alcanzado)**. La jornada N+1 se abre cuando todos los partidos de la N han alcanzado su `kickoff`. No depende de que el gestor haya metido el resultado. |
| UI para jornadas bloqueadas | **Pestañas por jornada** (J1 · J2 · J3) dentro de la ronda `groups`. Las jornadas bloqueadas aparecen como pestaña pero deshabilitada y, si se fuerza el acceso, muestra un banner explicando cuándo se desbloquea. |

---

## 2. Datos a cargar

### 2.1 Selecciones (48)

El Mundial 2026 tiene **48 selecciones** repartidas en **12 grupos** (A–L) de 4 equipos. La tabla actual de `Team` tiene 16 (las del prototipo). Se mantienen los códigos existentes y se añaden los 32 que faltan.

Equipos por grupo (códigos finales en §2.3):

| Grupo | Equipos |
|-------|---------|
| A | México, Sudáfrica, Corea del Sur, Chequia |
| B | Canadá, Bosnia y Herzegovina, Catar, Suiza |
| C | Brasil, Marruecos, Haití, Escocia |
| D | EE. UU., Paraguay, Australia, Turquía |
| E | Alemania, Curazao, Costa de Marfil, Ecuador |
| F | Países Bajos, Japón, Suecia, Túnez |
| G | Bélgica, Egipto, Irán, Nueva Zelanda |
| H | España, Cabo Verde, Arabia Saudí, Uruguay |
| I | Francia, Senegal, Irak, Noruega |
| J | Argentina, Argelia, Austria, Jordania |
| K | Portugal, RD Congo, Uzbekistán, Colombia |
| L | Inglaterra, Croacia, Ghana, Panamá |

### 2.2 Partidos (72)

72 partidos = 12 grupos × 6 partidos por grupo (3 jornadas × 2 partidos/jornada). Todos en el rango **11–28 junio 2026**, todos con `round = "groups"` y `matchday ∈ {1, 2, 3}`.

Los `kickoff` se almacenan en **UTC**. Las fuentes consultadas dan los horarios en BST (UTC+1 en junio); se convierten en el seed.

Estructura del JSON (`fixtures/world_cup_2026.json`) — *pk* numérico estable para que el seed sea idempotente:

```json
{"model":"competition.match","pk":1,
 "fields":{"round":"groups","group":"A","matchday":1,
           "home":"MEX","away":"RSA","kickoff":"2026-06-11T19:00:00Z"}}
```

Convenciones:
- El campo `pk` del fixture se mantiene por compatibilidad con el formato Django pero **el seed lo ignora**: la identidad de un partido es la combinación funcional `(round, group, matchday, home, away)` (ver §5). Esto permite reordenar el fixture sin perder pronósticos.
- `group` es la letra (`"A"`..`"L"`). El campo es `CharField(max_length=20)` y ya admite el valor.

### 2.3 Códigos de selecciones nuevos

Códigos ISO de 3 letras (consistentes con los existentes y con el uso habitual FIFA):

| Código | Nombre (es) | Bandera |
|--------|-------------|---------|
| RSA | Sudáfrica | 🇿🇦 |
| KOR | Corea del Sur | 🇰🇷 |
| CZE | Chequia | 🇨🇿 |
| BIH | Bosnia y Herzegovina | 🇧🇦 |
| QAT | Catar | 🇶🇦 |
| SUI | Suiza | 🇨🇭 |
| HAI | Haití | 🇭🇹 |
| SCO | Escocia | 🏴󠁧󠁢󠁳󠁣󠁴󠁿 |
| PAR | Paraguay | 🇵🇾 |
| AUS | Australia | 🇦🇺 |
| TUR | Turquía | 🇹🇷 |
| CUW | Curazao | 🇨🇼 |
| CIV | Costa de Marfil | 🇨🇮 |
| ECU | Ecuador | 🇪🇨 |
| SWE | Suecia | 🇸🇪 |
| TUN | Túnez | 🇹🇳 |
| EGY | Egipto | 🇪🇬 |
| IRN | Irán | 🇮🇷 |
| NZL | Nueva Zelanda | 🇳🇿 |
| CPV | Cabo Verde | 🇨🇻 |
| KSA | Arabia Saudí | 🇸🇦 |
| SEN | Senegal | 🇸🇳 |
| IRQ | Irak | 🇮🇶 |
| NOR | Noruega | 🇳🇴 |
| ALG | Argelia | 🇩🇿 |
| AUT | Austria | 🇦🇹 |
| JOR | Jordania | 🇯🇴 |
| COD | RD Congo | 🇨🇩 |
| UZB | Uzbekistán | 🇺🇿 |
| COL | Colombia | 🇨🇴 |
| GHA | Ghana | 🇬🇭 |
| PAN | Panamá | 🇵🇦 |

Los códigos existentes que se reutilizan: `ESP, ARG, FRA, BRA, ENG, POR, GER, NED, MEX, USA, CAN, JPN, CRO, MAR, URU, BEL`. (`MAR` cubre Marruecos.)

---

## 3. Regla de la "puerta de jornada"

### 3.1 Definición formal

```
is_matchday_open(round_id, matchday) -> bool
    1. Si matchday is None → True (rondas eliminatorias no tienen jornada; comportamiento sin cambios).
    2. Si matchday == 1 → True.
    3. Si matchday > 1:
        prev_matches = Match.objects.filter(round_id=round_id, matchday=matchday-1)
        si prev_matches está vacío → True (no había nada que cerrar).
        si no → all(now() >= m.kickoff for m in prev_matches).
```

Solo se aplica donde existen jornadas. Hoy: ronda `groups`. Si en el futuro otras rondas usan `matchday`, la regla aplica automáticamente.

### 3.2 Composición con la regla de cierre existente

La regla actual (`Match.editable`) es:
```
editable = status in ("open", "closing")
       ≡ now < kickoff - 2h        (con `closing` siendo los últimos <2h)
```

A partir de este diseño:
```
editable_for_predictions(match) = match.editable AND is_matchday_open(match.round_id, match.matchday)
```

`Match.editable` se mantiene como propiedad pura de tiempo (no se cambia su semántica para no romper otros usos). Se añade `Match.predictions_open` (o método equivalente) que aplica también la puerta. **Solo esta nueva propiedad debe usarse en flujos de pronóstico** (vista y template).

### 3.3 Punto de aplicación

- **Servidor (autoridad):** `PredictView.post` rechaza con `PermissionDenied` si `match.predictions_open is False`. El mensaje al usuario distingue los dos motivos:
  - Apuestas cerradas por proximidad al kickoff → "Las apuestas para este partido están cerradas."
  - Jornada bloqueada → "La J{N} se desbloqueará cuando termine la J{N-1}."
- **GET de la vista de pronóstico:** mismo chequeo, redirige al dashboard con `messages.error`.
- **Template:** la tarjeta del partido oculta el botón "Pronosticar" cuando la jornada está bloqueada y muestra un *chip* "🔒 Bloqueado · J{N}".

---

## 4. UI — sub-selector de jornada

### 4.1 Estructura

Dentro de la ronda `groups`, debajo del selector de rondas, se añade un **sub-selector** con tres pestañas: `J1 · J2 · J3`. El parámetro de URL es `?round=groups&matchday=1`. Si no se pasa `matchday`, se selecciona por defecto:
- La jornada activa: la primera que tenga al menos un partido en estado `open`/`closing`/`closed`/`live`.
- Si no hay ninguna activa (todas `done`), la última.

### 4.2 Estados visuales

| Estado de la jornada | Apariencia | Interacción |
|----------------------|------------|-------------|
| Abierta (puerta abre y hay partidos editables) | chip resaltado con `--accent` | clic navega |
| En curso (puerta abre, partidos en `closed`/`live`/`done`) | chip normal | clic navega |
| Bloqueada (puerta cerrada) | chip atenuado (`opacity: .45`), icono 🔒 antes del texto, `aria-disabled="true"` | clic permitido pero al entrar muestra banner explicativo; NO se desactiva el `<a>` para que se pueda inspeccionar |

### 4.3 Banner de jornada bloqueada

Cuando la URL apunta a una jornada bloqueada, antes de las tarjetas se muestra una caja `.glass`:

> 🔒 **Jornada J{N} bloqueada**
> Se desbloqueará cuando termine la J{N-1} (último partido: **{nombre del último partido}** el **{fecha-hora local del kickoff}**).

Las tarjetas se renderizan **atenuadas** (`opacity: .55`, `pointer-events: none` en el botón de pronóstico). Esto da contexto visual del fixture sin permitir apuestas.

### 4.4 Otras pantallas

- **`ManageResultsView` (Resultados, solo gestor):** también se añade el sub-selector. La puerta de jornada **no** afecta a esta pantalla: el gestor debe poder introducir resultados oficiales independientemente de la jornada. Solo se filtra por jornada para ergonomía.
- **`StatsView`, `RankingsView`, etc.:** sin cambios. La puerta solo afecta a la creación/edición de pronósticos.

---

## 5. Estrategia de seed e idempotencia

### 5.1 Fixtures

- `fixtures/teams.json` se amplía con las 32 nuevas selecciones (incluyendo las 16 actuales sin tocar).
- `fixtures/world_cup_2026.json` se sustituye por los 72 partidos.

### 5.2 Comando de gestión

Se crea `competition/management/commands/seed_world_cup_2026.py`. Hace:

1. **Carga de Teams** desde `fixtures/teams.json` con `update_or_create` por `code`.
2. **Carga de Matches** desde `fixtures/world_cup_2026.json` con `update_or_create` por (`round_id`, `group`, `matchday`, `home_id`, `away_id`). Es decir: **la clave funcional NO es el `pk` del fixture**, sino la combinación que identifica un partido del calendario. Esto:
   - Permite reordenar los `pk` del fixture sin perder predicciones.
   - Hace el comando idempotente.
3. **Si existen partidos en la BD que no están en el fixture**, el comando los deja en paz por defecto y los lista. Con la opción `--prune` los borra (junto a sus predicciones). Importante: los 4 partidos *placeholder* actuales (MEX-USA, CAN-JPN, ESP-POR, ARG-BRA) **no corresponden** a ningún partido real de J1 (los equipos están en grupos distintos), así que sin `--prune` quedarían como huérfanos. Para una carga limpia desde cero, lo esperado es ejecutar `--prune` la primera vez.
4. **Transacción atómica**. Si algo falla, no se carga nada.
5. **Reporte**: imprime "Equipos creados/actualizados", "Partidos creados/actualizados/sin tocar", y el total final.

Uso típico:
```
python manage.py seed_world_cup_2026
python manage.py seed_world_cup_2026 --prune     # limpia partidos huérfanos
python manage.py seed_world_cup_2026 --dry-run   # solo muestra el plan
```

### 5.3 Modo desarrollo

El `db.sqlite3` actual del repositorio tiene los 4 partidos *placeholder* (pk 1–4) con emparejamientos que no se dan en la realidad. La primera ejecución recomendada es con `--prune`:

```
python manage.py seed_world_cup_2026 --prune
```

Esto deja la BD con exactamente los 72 partidos reales y elimina los 4 *placeholder*. Si esos 4 tuvieran pronósticos asociados, `--prune` los borra también (es esperado: son datos de prueba sin valor).

### 5.4 Producción

- En el *runbook* de despliegue se añade un paso opcional para ejecutar el comando.
- El comando **no carga jugadores ni pronósticos**, solo el calendario.

---

## 6. Cambios en el código

### 6.1 Nuevos archivos

- `competition/services/matchday_gate.py`
  - `def is_matchday_open(round_id: str, matchday: int | None) -> bool`
  - `def previous_matchday_close_info(round_id, matchday) -> tuple[Match | None, datetime | None]` (para el banner)
- `competition/management/__init__.py`, `competition/management/commands/__init__.py`
- `competition/management/commands/seed_world_cup_2026.py`
- `templates/partials/_matchday_selector.html`

### 6.2 Archivos modificados

- `competition/models.py` — añade `Match.predictions_open` (property) que combina `editable` con `is_matchday_open(...)`.
- `competition/views.py`
  - `CompetitionView.get`: si `active_round` tiene jornadas, lee `matchday` de query string, calcula jornada por defecto, pasa al template tanto la lista de jornadas como el estado de la puerta de cada una.
  - `PredictView.get` y `.post`: validan `match.predictions_open` con mensaje específico.
  - `ManageResultsView.get`: añade sub-selector de jornada (sin gating).
- `templates/competition/dashboard.html` — incluye el sub-selector cuando hay jornadas; muestra el banner de jornada bloqueada cuando corresponde; atenúa las tarjetas.
- `templates/competition/_match_card.html` — esconde botón "Pronosticar" si `not match.predictions_open`; añade chip 🔒.
- `templates/competition/manage_results.html` — incluye el sub-selector.
- `fixtures/teams.json` y `fixtures/world_cup_2026.json` — datos nuevos.

### 6.3 Tests nuevos

- `competition/tests/test_matchday_gate.py`
  - J1 siempre abierta.
  - J2 cerrada mientras quede un partido de J1 con `now < kickoff`.
  - J2 abierta cuando todos los partidos de J1 tienen `now >= kickoff` (uno a uno, con `freezegun`).
  - J3 sigue las mismas reglas respecto a J2 (no respecto a J1).
  - Rondas sin `matchday` (None) → siempre abiertas.
- `competition/tests/test_prediction.py` (ampliar)
  - `PredictView.post` con jornada bloqueada → 403, no se crea `Prediction`.
  - Mensaje de error específico para jornada bloqueada.
- `competition/tests/test_competition_view.py` (ampliar)
  - Sub-selector de jornadas aparece en `groups`.
  - Banner aparece para jornada bloqueada.
- `competition/tests/test_seed_command.py` (nuevo)
  - Carga limpia: 48 equipos, 72 partidos.
  - Re-ejecución sin cambios: 0 creaciones, 0 actualizaciones (`unchanged` count == 72).
  - `--prune` borra huérfanos.
  - Conserva pronósticos existentes al re-ejecutar.

---

## 7. Cómo se traduce esto al estado del producto el 2026-06-01

- Hoy es 10 días antes del primer partido (11/jun). Tras ejecutar el seed:
  - Los **24 partidos de J1** están todos en estado `open` y son pronosticables.
  - Los **24 de J2** y los **24 de J3** están en estado `open` por tiempo, pero **bloqueados por la puerta de jornada**.
- A partir del 11/jun los partidos de J1 empiezan a entrar en `closing` (últimas 2 h), luego `closed` (cerrados, sin haber empezado), luego `live`, luego (cuando el gestor cierra el resultado) `done`. La puerta de J2 no abre hasta que **el último partido de J1** alcance su kickoff (aproximadamente **2026-06-18 08:00 UTC**, según el calendario importado).
- A partir de ese momento, J2 pasa a `open` y la J3 sigue bloqueada hasta el último kickoff de J2 (~25/jun).

---

## 8. Fuera de alcance (no se hace ahora)

- Carga de las **rondas eliminatorias** (`r32`, `r16`, `qf`, `sf`, `final`). Su calendario depende de la clasificación; se cargará cuando se acerque la fecha y existan equipos clasificados.
- Cualquier mecanismo manual para que el gestor **fuerce el desbloqueo** de una jornada (no se ha pedido; añadiría complejidad innecesaria para la prueba).
- Cambios en `Match.matchday` para rondas eliminatorias.
- Movimiento de zona horaria para los usuarios (los tiempos se renderizan ya con el `TIME_ZONE` de Django y los `templatetag` existentes).

---

## 9. Criterios de aceptación

1. `python manage.py seed_world_cup_2026` deja la BD con exactamente **48 selecciones** y **72 partidos** en `round=groups`, repartidos 24+24+24 por `matchday`.
2. Un usuario logueado como jugador, accediendo a Competición:
   - Ve el sub-selector `J1 · J2 · J3` solo en la ronda `groups`.
   - En `?round=groups` (sin matchday) cae en J1 por defecto.
   - En J1 ve los 24 partidos abiertos para pronosticar.
   - En J2 y J3 ve las tarjetas atenuadas, sin botón "Pronosticar", y el banner de jornada bloqueada.
3. Un intento de `POST /competicion/pronostico/<match_id>/` para un partido de J2 retorna 403 y **no** crea/actualiza `Prediction`.
4. Bajo `freezegun`, avanzando el reloj hasta justo después del último kickoff de J1, la J2 pasa a estar abierta y los pronósticos de partidos de J2 se aceptan (siempre que sigan en `editable`).
5. Todos los tests previos siguen pasando + los nuevos tests del gate, vista, seed y pronóstico bloqueado.
6. La pantalla de gestor (`Resultados`) muestra el sub-selector pero permite introducir resultados en cualquier jornada.
