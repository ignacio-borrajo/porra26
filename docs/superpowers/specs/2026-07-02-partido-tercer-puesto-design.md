# Diseño — Partido por el 3.er y 4.º puesto

Fecha: 2026-07-02

## Objetivo

Añadir el partido por el tercer y cuarto puesto del Mundial 2026. Debe:

1. Mostrarse en la **misma columna que la Final** en la vista de eliminatorias.
2. Computar para la **clasificación absoluta (general)**.
3. Computar para la **jornada "Fases Finales"** (la que engloba octavos, cuartos,
   semifinales y final).
4. Valer **lo mismo que la Final** al acertar.

## Enfoque: reutilizar la ronda `final`

El partido cuelga de la ronda `final` (no se crea una ronda nueva). Motivación:
la ronda `final` ya está incluida en **todas** las listas de ámbito relevantes,
así que el resultado computa donde debe sin tocar esa lógica:

- `competition/views.py`: `KO_ROUND_IDS` y `FINALS_ROUND_IDS`.
- `pot/services/prizes.py`: `_FINALS_ROUND_IDS`.
- `stats/services/matchday_options.py`: `FINALS_ROUND_IDS`.
- `competition/services/resolve.py`: la rama `("r16", "qf", "sf", "final")`.

Además, al compartir ronda con la Final, los puntos por acierto son **una única
fuente de verdad** (`Round.points` de `final`, parametrizable desde "Premios y
puntos"): no hay riesgo de que se desincronicen. Sea 25 (valor sembrado por
defecto hoy) o el valor que configure el gestor, el 3.er puesto vale lo mismo.

Se descartó crear una ronda propia "Tercer puesto" porque el requisito es
explícitamente "vale lo mismo que la final", y una ronda separada obligaría a
migración + reordenación de `final` + fusión de columnas en la vista + añadir la
ronda a cuatro listas de ámbito, todo para replicar un valor que ya existe.

## Cambios

### 1. Dato — `fixtures/world_cup_2026.json` (el grueso)

Nuevo partido, tras `M103` (la Final):

```json
{
  "model": "competition.match",
  "pk": 104,
  "fields": {
    "round": "final",
    "group": "3.º y 4.º puesto",
    "matchday": null,
    "home": null,
    "away": null,
    "home_slot": "LM101",
    "away_slot": "LM102",
    "bracket_code": "M104",
    "kickoff": "2026-07-18T19:00:00Z"
  }
}
```

- `home_slot`/`away_slot` = perdedores de las semifinales (`M101`, `M102`).
- `kickoff` el día **antes** de la Final (Final: `2026-07-19T19:00:00Z`).
- `home`/`away` a `null`: los equipos se asignan a mano (no hay auto-asignación
  desde el commit que la eliminó).

`seed_world_cup_2026` es idempotente por `bracket_code` y **no poda KO**, así que
en producción basta re-ejecutar el seed para crear `M104`. Sin migración de datos.

Actualizar los conteos del docstring y del `help` del comando ("31 KO" → "32 KO",
"72 grupos + 31 KO" → "72 grupos + 32 KO").

### 2. Código — `competition/templatetags/competition_extras.py`

Único punto de código Python. Añadir el patrón de "perdedor" a `slot_label` para
que el estado `pending_teams` y el modal de edición muestren texto legible:

```python
LOSER_RE = re.compile(r"^L(M\d+)$")
# ...
if m := LOSER_RE.match(code):
    return f"Perdedor {m.group(1)}"
```

Así `LM101`/`LM102` se muestran como "Perdedor M101" / "Perdedor M102" en lugar
de "Por definir".

## Comportamiento (verificado, sin cambios de código adicionales)

- **Columna Final:** dos cards en la columna cuyo header es "Final". El eyebrow
  de la card distingue por `match.group` ("Final" vs "3.º y 4.º puesto") — la
  plantilla `_match_card.html` ya muestra `group` cuando su longitud es > 1, sin
  cambios.
- **Orden dentro de la columna:** cronológico por kickoff (regla existente
  `_order_ko_column`). El 3.er puesto se juega antes → queda arriba, la Final
  debajo. Coherente con "columnas ordenadas por fecha".
- **Puntos:** `Round.points` de `final`.
- **General + Fases Finales:** cuentan automáticamente (ronda `final` en ambos
  ámbitos).
- **Anuncios de ganador** (`announcements/services.py`): `finals`/`sede`/`global`
  ya están gated a que *todos* los partidos de fases finales estén resueltos y son
  idempotentes (`_try_create` comprueba existencia + `matchday_winners` exige
  todos resueltos). Resultado: solo se disparan cuando la Final **y** el 3.er
  puesto estén resueltos, en cualquier orden de resolución. Deshacer un resultado
  lo gestiona `_remove_invalidated_announcements` (rama `final` ya cubierta).
- **Resultados (gestor):** el 3.er puesto aparece como un partido más a resolver;
  equipos por asignación manual.
- **Recordatorios de Teams:** el 3.er puesto envía los avisos automáticos 2 h /
  30 min como cualquier partido. Sin código extra.

## Tests

- **Seed:** `M104` se crea con `round="final"` y aparece en la columna `final` de
  `ko_rounds`; el eyebrow muestra "3.º y 4.º puesto".
- **`slot_label`:** `LM101` → "Perdedor M101".
- **Clasificación:** una predicción acertada del 3.er puesto suma en `standings()`
  (general) y en `standings(round_ids=FINALS_ROUND_IDS)` (Fases Finales), con los
  puntos de la ronda `final`.
- **Anuncios:** con la Final resuelta pero el 3.er puesto sin resolver (y
  viceversa), `finals`/`global` **no** se crean; al resolver ambos, sí.
- **Idempotencia del seed:** re-ejecutar no duplica `M104`.

## Fuera de alcance

- Cambiar el valor de puntos de la Final (es configuración del gestor en "Premios
  y puntos", no código).
- Auto-asignación de los perdedores de semis (se asignan a mano, como el resto de
  cruces KO tras eliminar la auto-asignación).
