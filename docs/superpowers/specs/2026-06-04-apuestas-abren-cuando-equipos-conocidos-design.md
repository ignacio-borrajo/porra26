# Apuestas abiertas en cuanto se conocen los dos equipos

## Resumen

El negocio quiere quitar la barrera de la "puerta de jornada" en la fase de grupos y permitir que cualquier partido sea apostable desde el momento en que se conocen sus dos equipos. En grupos eso significa **los 72 partidos abiertos desde el día 1**. En las rondas eliminatorias, cada cruce se va abriendo automáticamente a medida que la ronda anterior los va resolviendo.

Para soportarlo, los partidos KO se precargan en BD sin equipos, con **slots** que se resuelven solos al confirmar resultados. El único cierre que sigue valiendo es `kickoff − 2 h`.

## Estado actual (qué se elimina)

- `competition/services/matchday_gate.py` bloquea J{N+1} hasta que todos los partidos de J{N} hayan saqueado. Se elimina.
- `Match.predictions_open` consulta el gate. Se elimina la dependencia.
- `CompetitionView` y `PredictView` derivan el bloqueo y muestran el banner "Jornada bloqueada" + chip 🔒 en `_match_card.html`. Se eliminan.
- `competition/tests/test_matchday_gate.py` se elimina.

## Modelo de datos

Cambios en `competition.models.Match`:

| Campo | Cambio |
|---|---|
| `home`, `away` | `null=True, blank=True` (siguen `PROTECT`). |
| `home_slot` | **Nuevo** `CharField(max_length=12, blank=True)`. Código del slot que ocupará ese hueco (ej. `"1A"`, `"WM49"`). Vacío en partidos donde el equipo es fijo desde el principio. |
| `away_slot` | **Nuevo** análogo. |
| `bracket_code` | **Nuevo** `CharField(max_length=12, blank=True, null=True, unique=True)`. Identificador estable del partido dentro del cuadro (ej. `"M73"` para el partido 73 del torneo según FIFA). Permite que slots futuros referencien al ganador (`"WM73"`). `null` para partidos de grupos (necesario para que el `unique=True` no rompa con múltiples valores en blanco). |

### Convención de slots

| Patrón | Significado | Cuándo se resuelve |
|---|---|---|
| `1A`, `2A`, `3A` | 1º, 2º, 3º del grupo A | Todos los partidos del grupo confirmados. |
| `WMnn` | Ganador en 90' del partido con `bracket_code = "Mnn"` | El partido `Mnn` tiene resultado oficial con ganador claro. |
| `3WG_S{n}` | Tercero clasificado asignado al slot `Sn` según la tabla FIFA 2026 | Los 12 grupos están cerrados. |

Si en algún momento un slot no es resolvible (empate insuficientemente desempatado, datos incompletos), queda a `None` y lo asigna el gestor.

## Servicio resolver

Nuevo módulo `competition/services/bracket.py`:

```python
def resolve_slot(code: str) -> Team | None:
    """Equipo concreto al que apunta el código, o None si no es determinable aún."""

def propagate_after_match(match: Match) -> list[Match]:
    """Rellena home/away en todos los partidos cuyos slots queden resolvibles
    tras este resultado. Idempotente: solo escribe donde está a None."""

def slot_label(code: str) -> str:
    """Etiqueta legible para la UI: '1º Grupo A', 'Ganador R32 #1', etc."""
```

Tabla FIFA de mejores terceros: constante Python en `competition/services/bracket_rules.py` (no se edita por gestor).

**Punto de invocación:** al final de `competition.services.resolve.resolve_match`, dentro de la misma transacción, se llama `propagate_after_match(match)`. Esto cubre el "auto-publicar" pedido por negocio.

**Criterios de desempate de grupo:** los estándar FIFA (pts → dif goles → goles a favor → enfrentamiento directo → fair play → sorteo). Si tras todos los criterios derivables seguimos empatados, `resolve_slot` devuelve `None`.

**Empates KO en 90':** la regla del proyecto ya es "solo cuentan los 90'" (`docs/DATA_MODEL.md` §2). Si los 90' acaban empate, `WMnn` devuelve `None` y el gestor asigna el cruce siguiente manualmente — no calculamos prórroga/penaltis.

## Estado del partido

```python
class Match:
    @property
    def has_teams(self) -> bool:
        return self.home_id is not None and self.away_id is not None

    @property
    def status(self) -> str:
        if self.has_result:
            return "done"
        if not self.has_teams:
            return "pending_teams"          # nuevo
        # resto idéntico: live / closed / closing / open

    @property
    def editable(self) -> bool:
        return self.has_teams and self.status in ("open", "closing")

    @property
    def predictions_open(self) -> bool:
        return self.editable                 # ya no consulta gate de jornada
```

`docs/DATA_MODEL.md` §3 se amplía con la fila `pending_teams`: "uno de los equipos sin asignar — tarjeta con placeholders, no apostable".

`competition/services/predictions.py` no requiere cambios: `next_pending_match` y `pending_matches_count` ya filtran por `predictions_open`.

## Vistas y templates

### `CompetitionView`
- Quita el bloque de `matchday_state` con `is_matchday_open`/`previous_matchday_close_info`.
- `matchday_state` pasa a la forma simple `{"matchday": md, "open": True, "active": md == active_md}`.
- Variables de contexto `locked`, `locked_last_match`, `locked_last_kickoff` desaparecen.

### `PredictView`
- Elimina la rama `if not is_matchday_open(...)`.
- Añade `if not m.has_teams: messages.error("Este cruce aún no tiene los dos equipos definidos.") → redirect("competicion:dashboard")` antes del check de editabilidad.

### `dashboard.html`
- Quita el banner "Jornada bloqueada" + cualquier `{% if locked %}`.
- Quita el chip 🔒 "Jornada bloqueada" en `_match_card.html`.

### `_match_card.html`
Nueva primera rama:
```
{% if st == 'pending_teams' %}
    {# tarjeta no clickable con placeholders #}
```
- En vez de bandera+nombre del equipo: `🏳️` + `{{ match.home_slot|slot_label }}` (y análogo away). Helper `slot_label` registrado como template filter en `competition/templatetags/`.
- Chip: variante visual nueva `chip-pending` (estilo neutral, gris) con texto `"Por definir"`. Tokens en el sistema de diseño existente — reutiliza la paleta de `chip-closed` pero con su propia clase para evitar confundir "apuestas cerradas" con "equipos pendientes".
- Footer: `"Equipos pendientes"`, sin link/modal.
- Sin `<a>` envolvente (no es clickable).

### UI del gestor para asignar/corregir equipos
- En `ManageResultsView`, los partidos con `status == "pending_teams"` se listan en una sección nueva **"Cruce pendiente"** sobre "Próximos".
- Cada fila lleva dos `<select>` (`home`/`away` de la lista de `Team`) y botón **"Asignar equipos"**.
- Mismo endpoint sirve para **corregir** un cruce ya publicado: si el partido ya tiene `home`/`away`, también aparece editable (botón "Editar cruce"). Si hay pronósticos existentes y se cambia un equipo, se borran todas las `Prediction` de ese partido (warning explícito en el modal/confirm).
- Nueva vista `AssignTeamsView` con `GestorRequiredMixin`, ruta `competicion/match/<id>/teams/`. POST con `home_code`, `away_code`, opcional `confirm_invalidate=1`.

### Página de Reglas (`templates/core/rules.html`)
Actualizar el bloque "cierre de apuestas":
- Quitar mención al desbloqueo progresivo de jornadas.
- Añadir: "Las apuestas de un partido se abren en cuanto se conocen los dos equipos. Los partidos de la fase de grupos están todos abiertos desde el día 1. Los cruces de las rondas eliminatorias aparecen como *Por definir* hasta que la ronda anterior los determine".
- Mantener: "El cierre es 2 horas antes del saque".

## Fixture / seed

- `fixtures/world_cup_2026.json`: añadir los 31 partidos KO restantes (16 R32 + 8 R16 + 4 QF + 2 SF + 1 Final). Cada uno:
  - `round` (`"r32"`/`"r16"`/`"qf"`/`"sf"`/`"final"`).
  - `bracket_code` (`"M73".."M104"` siguiendo la numeración FIFA 2026 oficial).
  - `home: null`, `away: null`.
  - `home_slot`, `away_slot` según el bracket oficial.
  - `kickoff` con la fecha/hora oficial de la sede.
- Tabla FIFA mejores terceros 2026: constante en `competition/services/bracket_rules.py`.
- Comando `competition/management/commands/seed_world_cup_2026.py`: actualizar para cargar los KO y verificar unicidad de `bracket_code`.

## Tests

Nuevos:
- `competition/tests/test_bracket_resolver.py`:
  - `resolve_slot("1A")` con grupo A completo y líder claro.
  - `resolve_slot("1A")` con grupo A incompleto → `None`.
  - `resolve_slot("WM49")` con M49 done y ganador en 90'.
  - `resolve_slot("WM49")` con M49 empate 90' → `None`.
  - `propagate_after_match`: cerrar el último partido del grupo A → R32 que dependía de `1A`/`2A` se autorellena.
  - Idempotencia: invocar dos veces no pisa equipos ya asignados.
- `competition/tests/test_match_pending_teams.py`:
  - `status == "pending_teams"` cuando `home_id` o `away_id` están a `None`.
  - `editable == False` y `predictions_open == False` para partidos sin equipos.
- `competition/tests/test_assign_teams_view.py`:
  - Asignación inicial por el gestor.
  - Corrección con invalidación de pronósticos existentes (requiere `confirm_invalidate=1`).

Adaptar:
- `competition/tests/test_match.py` y `test_predictions_service.py`: cualquier asunción de `home`/`away` no nulos.

Eliminar:
- `competition/tests/test_matchday_gate.py`.

## Migración

Una migración Django:
- `home` y `away` → `null=True`.
- Añadir `home_slot`, `away_slot`, `bracket_code` (con índice único parcial / unique=True).
- No requiere data migration: los 72 partidos de grupos ya cargados quedan con los tres campos nuevos vacíos, que es correcto.

## Orden de implementación sugerido

1. Migración + propiedades `has_teams`/`status` + `_match_card.html` rama `pending_teams`.
2. Eliminar gate de jornada (servicio, tests, vistas, templates, banner).
3. `competition/services/bracket.py` + tabla FIFA + tests del resolver.
4. Hook `propagate_after_match` en `resolve_match`.
5. `AssignTeamsView` + sección "Cruce pendiente" en `ManageResultsView`.
6. Fixture KO + actualizar `core/rules.html` + `docs/DATA_MODEL.md`.

## Fuera de scope

- No se rediseña la vista de cuadro/bracket: la pantalla de KO sigue listando partidos como ahora, solo con tarjetas `pending_teams` donde corresponda.
- No se implementan prórroga ni penaltis: si los 90' KO acaban empate, el siguiente cruce queda sin equipo y lo asigna el gestor.
- No se permite editar `kickoff` desde la nueva UI de gestor (sigue siendo solo lectura, como hoy).
