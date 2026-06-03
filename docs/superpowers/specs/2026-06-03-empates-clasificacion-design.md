# Spec — Empates compartidos en clasificación y premios

## Problema

Hoy la regla 4 de desempate es **orden alfabético del nombre**: si dos jugadores empatan a puntos, exactos y aciertos, uno acaba "delante" del otro arbitrariamente. Eso produce dos artefactos no deseados:

- En el podio y la tabla se elige a uno como ganador real cuando deportivamente están empatados.
- Los premios económicos del bote (P1·P2·P3) se asignan íntegros al "primero alfabético", lo que no refleja la realidad del empate.

## Objetivo

Eliminar la regla 4 (alfabético) y tratar los empates como **plaza compartida** (ranking denso: 1, 1, 2, 2, 3). Los jugadores empatados:

- Ocupan la misma posición numérica.
- Comparten visualmente la plaza en podio y tablas.
- Se reparten a partes iguales el premio económico de esa plaza.

El orden alfabético se mantiene **solo a efectos visuales** dentro del grupo de empate (para que la presentación sea estable), pero no afecta a la plaza.

## Reglas funcionales

### Orden de la clasificación

1. `pts` descendente.
2. `exact_hits` descendente.
3. `hits` descendente.
4. Si tras 1·2·3 persiste el empate → **misma plaza** (ranking denso). Dentro del grupo, orden alfabético por nombre (case-insensitive) solo para presentación.

### Ranking denso (sin saltos)

Tras 2 empatados en 1ª plaza, el siguiente jugador es 2ª (no 3ª). Tras 3 empatados en 2ª, el siguiente es 3ª. Ejemplo:

```
 #   Jugador   Pts  Exact  Hits
=1   Ana       24    3      8
     Borja     24    3      8
 2   Carla     22    2      7
=3   Dani      18    1      6
     Eva       18    1      6
 4   Fer       16    0      5
```

### Reparto del bote del podio (P1·P2·P3)

- El importe de cada plaza se reparte a partes iguales entre quienes la ocupen.
- 2 empatados en 1ª → cada uno cobra `P1 / 2`. 2ª plaza cobra `P2` íntegro. 3ª plaza cobra `P3` íntegro.
- 3 empatados en 2ª → cada uno cobra `P2 / 3`. 1ª cobra `P1`. 3ª cobra `P3`.
- Si una plaza queda sin ocupante (caso extremo: todos empatados en 1ª) su importe queda **sin asignar** (estado `pending`/`unfilled`).

### Ganador de jornada/ronda (`matchday_winner_prize`)

- Hoy `pot/services/prizes.py::matchday_winners` empata solo por puntos totales del scope.
- Se reescribe para aplicar las **3 reglas** dentro del scope (puntos, exactos, aciertos).
- Si tras 3 reglas siguen empatados, los empatados se reparten el importe a partes iguales (`matchday_winner_prize / N`).

## Modelo de datos

### `competition/services/standings.py::StandingRow`

```python
@dataclass
class StandingRow:
    position: int          # densa (1, 1, 2, 2, 3)
    is_tied: bool          # comparte plaza con al menos otro
    is_first_in_tie: bool  # primera fila alfabética de su grupo
    player_id: int
    name: str
    email: str
    pts: int
    hits: int
    exact_hits: int
    streak: int = 0
    trend: str = "flat"
```

### Cálculo

1. Recopilar `merged` igual que hoy (predicciones + extras de jugadores sin predicciones).
2. Ordenar por `(-pts, -exact_hits, -hits, name.lower())`. El `name.lower()` deja de ser desempate "real": es solo orden de presentación.
3. Recorrer asignando `position` densa:
   - `position = 1` para la primera fila.
   - Para cada fila siguiente, si `(pts, exact_hits, hits)` coincide con la anterior → misma `position`; si difiere → `position = position_anterior + 1`.
   - Marcar `is_tied=True` en todas las filas cuyo grupo tenga ≥2 miembros.
   - Marcar `is_first_in_tie=True` solo en la primera fila de cada grupo (en el orden alfabético ya garantizado).

### Servicio nuevo `pot/services/payouts.py`

```python
@dataclass
class PodiumPayout:
    player_id: int
    name: str
    position: int          # 1, 2 o 3
    share: Decimal         # importe individual
    tied: bool
    group_size: int
    base_prize: Decimal    # P1/P2/P3 íntegro

def podium_payouts() -> list[PodiumPayout]: ...
```

Implementación: `standings()` (general, sin scope) → filtra `position ∈ {1,2,3}` → agrupa por posición → `share = Prize.objects.get(scope="global", position=N).amount / group_size`.

### Cambios en `pot/services/prizes.py::matchday_winners`

- Sustituye el `annotate(p=Sum("earned"))` por una llamada a `standings(round_id=…, matchday=…)`.
- Toma todos los rows con `position == 1`.
- `share = settings.matchday_winner_prize / len(winners)`.
- Devuelve `WinnerResult(status="resolved", winners=[…], points=top, tied=len>1, share=…)`.

## Render UI

### Tabla — `templates/partials/_leaderboard_row.html`

La celda de posición pasa de `{{ r.position }}` a:

```django
{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position }}{% endif %}
```

- Si la fila no es la primera de su grupo de empate, la celda queda vacía.
- Si lo es y comparte plaza, antepone `=`.
- En filas empatadas se añade clase `leaderboard-row--tied` para ajuste sutil (borde, agrupación visual). Detalle CSS concreto durante implementación.

### Podio — `templates/partials/_leaderboard_panel.html` y `_podium_step.html`

- `_leaderboard_panel.html` agrupa los rows por `position` con `{% regroup rows by position as positions %}`.
- Toma las plazas 1, 2, 3 (cada una contiene una **lista** de empatados).
- `_podium_step.html` se reescribe para aceptar `rows` (lista) en vez de un único `row`:
  - Cabecera: medalla (🥇/🥈/🥉) + label `Nº` o `=Nº` si `len(rows) > 1`.
  - Cuerpo: avatares apilados verticalmente con el nombre a la derecha (uno por jugador empatado). Resalta `is-me` si alguno es el usuario actual.
  - Puntos: una sola cifra (los empatados tienen los mismos).
  - Pedestal: misma altura simbólica que hoy (1ª más alta, centro; 2ª izquierda media; 3ª derecha baja). La columna crece hacia arriba al añadir avatares; el pedestal no cambia de altura.
- Columnas vacías (caso extremo de todos empatados en 1ª): se mantiene `podium-slot--empty` actual.
- Nuevos selectores CSS: `.podium-slot--multi` con espaciado vertical para los avatares apilados.

### Chip "Tú · #X"

Plantillas: `templates/partials/_leaderboard.html`, `templates/stats/rankings.html`.

- Hoy: `Tú · #{{ my_rank }}`.
- Nuevo: `Tú · {% if my_is_tied %}=#{% else %}#{% endif %}{{ my_rank }}`.
- Las vistas (`competition/views.py`, `stats/views.py`) calculan `my_is_tied` localizando al usuario en `rows` y leyendo su `is_tied`. Lo mismo para el chip de scope (`scope_my_rank` + `scope_my_is_tied`).

### Login — top 5 (`templates/accounts/login.html`)

Hoy usa `forloop.counter` para la posición. Pasa a usar `r.position`, `r.is_first_in_tie`, `r.is_tied` con el mismo formato (`=N` en primero, vacío en el resto). La vista que prepara `top_rows` (probablemente `accounts/views.py::LoginView` o equivalente) pasa el `standings()[:N]` ya con flags.

### Stats — tabla de grupos (`templates/stats/rankings.html`)

La tabla por dimensión (sede/puesto/dept) hoy numera con `forloop.counter`. Cambio:

- `stats/services/group_standings.py::group_standings` añade `position`, `is_tied`, `is_first_in_tie` por `GroupRow`, calculados con la misma lógica densa sobre la lista ordenada.
- La plantilla deja de usar `forloop.counter` y pasa a `{% if r.is_first_in_tie %}{% if r.is_tied %}={% endif %}{{ r.position }}{% endif %}`.

### Stats — líder del grupo (chip)

`group_standings.py::_row_for` resuelve hoy el "líder" con `max()` y `-player_id` como desempate. Cambio:

- Aplica las 3 reglas (pts, exact_hits, hits).
- Si tras 3 reglas hay K>1 líderes empatados:
  - `top_name` = primer alfabético del grupo.
  - Nuevo campo en `GroupRow`: `top_tied_count: int` (=K, 1 si no hay empate).
  - El chip de líder pasa a `Ana +{{K-1}} · 240 pts` cuando `top_tied_count > 1` (ej: 3 empatados → "Ana +2 · 240 pts").

## Página de Reglas — `templates/core/rules.html`

Sección "04 · Desempate":

```
1  Más puntos.
2  Más marcadores exactos.
3  Más aciertos (resultado correcto, incluidos exactos).
```

Y bajo la lista, párrafo nuevo:

> Si tras aplicar las tres reglas siguen empatados, **comparten plaza**: en el podio aparecen juntos y el premio de esa plaza se reparte a partes iguales entre ellos. Lo mismo aplica al premio por ganador de jornada/ronda.

## Documentación

`docs/DATA_MODEL.md` sección 4 ("Clasificación (orden)"):

```
1. `pts` descendente.
2. Desempate: más exactos → más aciertos.
3. Empate persistente → plaza compartida (ranking denso), reparto a partes iguales
   de premios económicos. Dentro del grupo de empate, orden alfabético solo a
   efectos visuales.
```

## Tests

### `competition/tests/test_standings.py`

- Sustituir `test_standings_tiebreak_by_exact_then_hits_then_name` por:
  - `test_tiebreak_keeps_shared_position` — Ana y Borja con mismos pts/exact/hits → ambos `position=N`, `is_tied=True`, Ana `is_first_in_tie=True`.
  - `test_dense_ranking_no_gap_after_tie` — 2 empatados en 1ª → siguiente es 2ª.
  - `test_alphabetical_only_visual_within_tie` — el orden alfabético no afecta a `position`, solo al orden de las filas.
- Nuevo `test_is_tied_false_when_unique`.
- `my_rank`: el cliente saca `position` directamente; no se testea aquí (se cubre en `competition/tests/test_views.py` y `stats/tests`).

### `pot/tests/test_payouts.py` (nuevo)

- `test_podium_payout_splits_p1_among_tied` (2 en 1ª → cada uno P1/2; 2ª cobra P2; 3ª cobra P3).
- `test_podium_payout_handles_tie_on_second_place`.
- `test_podium_payout_marks_position_pending_when_unfilled` (3 empatados en 1ª y nadie más → P2 y P3 sin asignar).

### `pot/tests/test_prizes.py`

- `test_matchday_winners_applies_three_rules` (exactos desempatan dentro del scope).
- `test_matchday_winners_share_split_when_still_tied`.
- Adaptar tests existentes que dependieran del comportamiento "solo puntos".

### `stats/tests/test_group_standings.py` y `test_rankings_view.py`

- `test_group_standings_assigns_dense_position_with_ties`.
- `test_group_leader_chip_shows_tied_count_when_multiple_leaders`.
- `test_rankings_template_renders_equals_sign_on_first_of_tie`.

### `core/tests/test_rules_view.py`

- `test_rules_page_no_longer_mentions_alphabetical_tiebreak`.
- `test_rules_page_explains_shared_position_and_prize_split`.

### Login top 5

- `test_login_top5_renders_equals_sign_on_first_of_tie` (en `accounts/tests/` donde aplique).

## Archivos afectados

- `competition/services/standings.py` — lógica densa, flags `is_tied`/`is_first_in_tie`.
- `competition/views.py` — exposición de `my_is_tied`/`scope_my_is_tied`.
- `stats/views.py` — equivalente.
- `stats/services/group_standings.py` — plaza densa para grupos, líder con 3 reglas + `top_tied_count`.
- `pot/services/prizes.py` — `matchday_winners` con 3 reglas + share.
- `pot/services/payouts.py` (nuevo) — `podium_payouts`.
- `templates/partials/_leaderboard_row.html` — render de la posición con `=`.
- `templates/partials/_leaderboard.html` — chip "Tú·=#X".
- `templates/partials/_leaderboard_panel.html` — regroup por posición.
- `templates/partials/_podium_step.html` — acepta lista de empatados.
- `templates/stats/rankings.html` — chips y tabla de grupos con plaza densa.
- `templates/accounts/login.html` — top 5 con `=`.
- `templates/core/rules.html` — texto del paso 4.
- `docs/DATA_MODEL.md` — sección 4.
- CSS (archivo a determinar en implementación) — `.podium-slot--multi`, `.leaderboard-row--tied`.

## Fuera de alcance

- Cambio del modelo `Prize` (sigue siendo 1 fila por posición con importe íntegro).
- Recalcular pagos ya emitidos: el cambio aplica a partir del despliegue; los pagos pasados quedan como están.
- UI para que el gestor "rompa" un empate manualmente: no existe, los empates son automáticos y permanentes.
- Cambios en `streak` y `trend`: la lógica actual sigue valiendo (comparan posición numérica; con plazas compartidas se calcula igual).

## Decisiones tomadas durante el diseño

- **Reparto del bote**: cada plaza se reparte a partes iguales entre los empatados que la ocupen; si una plaza queda vacía por empates extremos, su importe queda sin asignar.
- **Ganador de jornada**: aplica las 3 reglas dentro del scope (no solo puntos).
- **Podio visual**: avatares apilados verticalmente dentro de la columna; el pedestal no cambia de altura.
- **Formato visual de la posición**: `=N` en el primero del empate (alfabético), vacío en el resto. Aplica a todas las pantallas: clasificación general, jornada/ronda, login top 5, chip "Tú", y grupos de stats.
- **Arquitectura del row**: `position` sigue siendo `int`, se añaden flags `is_tied` y `is_first_in_tie`. Las plantillas conservan el control del formato visual.
