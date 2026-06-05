# Histórico de pronósticos (matriz jugador × partido)

Fecha: 2026-06-05

## Resumen

Nueva página `/stats/historico/` que muestra una matriz con todos los jugadores (filas) frente a todos los partidos finalizados (columnas), con el marcador que pronosticó cada jugador en cada partido. La celda se colorea verde (marcador exacto), naranja (acierto 1·X·2) o sin color (fallo o sin apostar). La última columna agrega el total de puntos del jugador. Acceso desde un enlace alineado a la derecha en el `<header>` de la página de Rankings. Exportable a `.xlsx` manteniendo colores y datos.

## Motivación

- La clasificación de Rankings dice quién va ganando, pero no cómo: no se ve qué pronosticó cada jugador ni dónde acertó.
- Los jugadores piden poder cotillear los pronósticos del resto después de cada jornada y comparar de un vistazo.
- Para el gestor es útil como vista de auditoría: comprobar a la vista que los puntos cuadran con los aciertos.
- Una matriz colorada al estilo de hoja de cálculo es el formato más reconocible.

## Alcance

### Incluido

- Vista web `/stats/historico/` con la tabla matriz y enlace de descarga.
- Vista de export `/stats/historico.xlsx` con el mismo contenido coloreado.
- Servicio compartido `stats/services/history_matrix.py` que construye la estructura de datos.
- Servicio `stats/services/history_xlsx.py` que serializa la matriz a `.xlsx` usando `openpyxl`.
- Plantilla nueva `templates/stats/historico.html`.
- Enlace "Histórico →" en el header de `templates/stats/rankings.html`, alineado a la derecha.
- Estilos CSS bajo sección `/* history matrix */` en `static/css/styles.css`.
- Tests de servicio, vista web y export.

### Fuera de alcance

- Filtros por ronda, sede, departamento o subconjuntos de jugadores. La tabla siempre es completa.
- Paginación o virtualización. Con el orden de magnitud actual (≤80 × ≤100) no compensa la complejidad.
- Vista móvil distinta. Mismo HTML para todos los anchos, scroll horizontal con cabeceras congeladas.
- Mostrar pronósticos de partidos `live` o `open`. Solo entran partidos con `finished_at`.
- Cambios en la lógica de cálculo de puntos. Se consume `Prediction.earned` y `Match.exact_points_applied` tal cual.

## Diseño

### 1. Rutas y vistas

`stats/urls.py` añade:

```python
path("historico/", views.HistoryView.as_view(), name="historico"),
path("historico.xlsx", views.HistoryExportView.as_view(), name="historico_export"),
```

`stats/views.py` añade dos clases que heredan `LoginRequiredMixin, View`:

- `HistoryView.get(request)` → llama a `build_matrix()`, renderiza `stats/historico.html`.
- `HistoryExportView.get(request)` → llama a `build_matrix()`, delega en `render_xlsx(matrix)` y devuelve `HttpResponse` con `content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"` y `Content-Disposition: attachment; filename="historico-porra-26.xlsx"`.

Sin restricciones de rol más allá de `LoginRequiredMixin`: visible para jugadores y gestores.

### 2. Servicio `history_matrix.py`

```python
from dataclasses import dataclass

@dataclass(frozen=True)
class HistoryMatch:
    id: int
    home_code: str
    home_name: str
    home_flag: str
    away_code: str
    away_name: str
    away_flag: str
    result_home: int
    result_away: int

@dataclass(frozen=True)
class HistoryPlayer:
    id: int
    name: str
    initials: str
    position: int

@dataclass(frozen=True)
class HistoryCell:
    state: str  # "exact" | "partial" | "miss" | "empty"
    home: int | None
    away: int | None

@dataclass(frozen=True)
class HistoryMatrix:
    matches: list[HistoryMatch]
    players: list[HistoryPlayer]
    cells: dict[tuple[int, int], HistoryCell]  # (player_id, match_id) -> Cell
    totals: dict[int, int]                      # player_id -> total pts


def build_matrix() -> HistoryMatrix: ...
```

#### Pasos del servicio

1. **Cargar partidos finalizados** en orden cronológico:
   ```python
   Match.objects.filter(finished_at__isnull=False)
       .select_related("home", "away")
       .order_by("kickoff", "id")
   ```
   Por construcción todos tienen `result_home` y `result_away` no nulos y `exact_points_applied` definido.

2. **Cargar jugadores** mediante `competition.services.standings.standings()` sin scope (mismo orden que la clasificación general). Filtra automáticamente `is_active=True, is_jugador=True`; los gestores quedan fuera.

3. **Cargar predicciones** en una sola query:
   ```python
   Prediction.objects.filter(
       match_id__in=match_ids, player_id__in=player_ids
   ).values_list("player_id", "match_id", "home", "away", "earned")
   ```

4. **Construir las celdas** comparando `earned` con `match.exact_points_applied`:
   - `earned == match.exact_points_applied` → `state="exact"`.
   - `earned > 0` y distinto del exacto → `state="partial"`.
   - `earned == 0` → `state="miss"`.
   - Sin entrada en el dict → `state="empty"`.

5. **Totales** desde `StandingRow.pts` para que coincidan con la clasificación general.

### 3. Servicio `history_xlsx.py`

```python
def render_xlsx(matrix: HistoryMatrix) -> bytes: ...
```

Una sola hoja `"Histórico"`:

| Fila | Columna A | Columnas B..N | Última columna |
|------|-----------|---------------|----------------|
| 1 | `"Jugador"` | `"ESP - FRA"` `"ESP - MEX"` … | `"Total"` |
| 2 | `""` | `"2-1"` `"0-0"` … (resultados oficiales) | `""` |
| 3..N | `"Nombre"` | pronósticos coloreados | puntos totales |

Formato:

- `freeze_panes = "B3"`.
- Fila 1: `Font(bold=True, color="FFFFFF")`, `PatternFill("solid", fgColor="1A1530")`, alineación centrada.
- Fila 2: `Font(italic=True, bold=True)`, alineación centrada.
- Celdas `exact`: `PatternFill("solid", fgColor="22C55E")`, `Font(color="FFFFFF")`.
- Celdas `partial`: `PatternFill("solid", fgColor="F59E0B")`, `Font(color="FFFFFF")`.
- Celdas `miss` y `empty`: sin relleno (texto del pronóstico para `miss`, vacío para `empty`).
- `column_dimensions["A"].width = 28`. El resto a `9`.
- Última columna (Total): `Font(bold=True)`, alineación derecha.

Devuelve `bytes` listo para `HttpResponse`. La vista controla la cabecera HTTP.

### 4. Plantilla `templates/stats/historico.html`

Estructura (extiende `base.html`, bloque `main`):

```html
<header class="rise" style="display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:18px">
  <div>
    <div class="eyebrow">MUNDIAL 2026</div>
    <h1 class="display" style="font-size:28px;margin:6px 0 4px">Histórico de pronósticos</h1>
  </div>
  <a class="chip chip-accent" href="{% url 'stats:historico_export' %}" download>
    {% icon "download" width=14 height=14 %} Exportar a Excel
  </a>
</header>

<div class="history-legend rise">
  <span><i class="legend-dot legend-dot--exact"></i> Marcador exacto</span>
  <span><i class="legend-dot legend-dot--partial"></i> Resultado 1·X·2</span>
  <span><i class="legend-dot legend-dot--miss"></i> Fallo o sin pronóstico</span>
</div>

<div class="glass rise history-wrap">
  <table class="history-matrix">
    <thead>
      <tr>
        <th class="hm-corner hm-sticky-col hm-sticky-row">Jugador</th>
        {% for m in matrix.matches %}
          <th class="hm-sticky-row hm-match">{{ m.home_code }} - {{ m.away_code }}</th>
        {% endfor %}
        <th class="hm-corner hm-sticky-col-right hm-sticky-row">Total</th>
      </tr>
      <tr>
        <th class="hm-sticky-col hm-sticky-row-2"></th>
        {% for m in matrix.matches %}
          <th class="hm-sticky-row-2 hm-result">{{ m.result_home }}-{{ m.result_away }}</th>
        {% endfor %}
        <th class="hm-sticky-col-right hm-sticky-row-2"></th>
      </tr>
    </thead>
    <tbody>
      {% for p in matrix.players %}
        <tr>
          <th class="hm-sticky-col hm-player">{{ p.position }}. {{ p.name }}</th>
          {% for m in matrix.matches %}
            {% with cell=matrix.cells|get_cell:p.id|get_cell:m.id %}
              <td class="hm-cell hm-cell--{{ cell.state }}">{% if cell.state != "empty" %}{{ cell.home }}-{{ cell.away }}{% endif %}</td>
            {% endwith %}
          {% endfor %}
          <th class="hm-sticky-col-right hm-total">{{ matrix.totals|get_item:p.id }}</th>
        </tr>
      {% endfor %}
    </tbody>
  </table>
</div>
```

#### Filtros de plantilla

- `get_item` ya existe en `competition/templatetags/` (lo usa `_leaderboard_panel.html`).
- Se añade `get_cell` (o un patrón de pase de contexto) para acceder a `cells[(player_id, match_id)]`. Alternativa más simple: el servicio expone las celdas como `dict[player_id, dict[match_id, Cell]]` para usar `|get_item` dos veces (decisión final durante la implementación; comportamiento idéntico).

### 5. CSS

Nueva sección al final de `static/css/styles.css`:

```css
/* ===== history matrix ===== */
.history-legend {
  display: flex; gap: 16px; flex-wrap: wrap;
  font-size: 12px; color: var(--text-faint);
  margin-bottom: 12px;
}
.history-legend .legend-dot {
  display: inline-block; width: 10px; height: 10px;
  border-radius: 3px; margin-right: 6px; vertical-align: middle;
}
.legend-dot--exact   { background: oklch(from var(--accent-green)  l c h / 0.55); }
.legend-dot--partial { background: oklch(from var(--accent-orange) l c h / 0.55); }
.legend-dot--miss    { background: var(--border); }

.history-wrap {
  overflow: auto;
  max-height: 75vh;
  border-radius: 22px;
}
.history-matrix {
  border-collapse: separate; border-spacing: 0;
  font-family: var(--font-mono);
  font-size: 12px;
}
.history-matrix th, .history-matrix td {
  padding: 6px 10px;
  border-right: 1px solid var(--border);
  border-bottom: 1px solid var(--border);
  white-space: nowrap;
  text-align: center;
  background: var(--bg-elev);
}
.hm-sticky-col       { position: sticky; left: 0;  z-index: 2; min-width: 140px; max-width: 180px; text-align: left; }
.hm-sticky-col-right { position: sticky; right: 0; z-index: 2; min-width: 64px; font-weight: 700; }
.hm-sticky-row       { position: sticky; top: 0;   z-index: 3; font-weight: 700; }
.hm-sticky-row-2     { position: sticky; top: 36px; z-index: 3; font-style: italic; }
.hm-corner           { z-index: 4; }
.hm-cell--exact   { background: oklch(from var(--accent-green)  l c h / 0.25); color: var(--accent-green);  }
.hm-cell--partial { background: oklch(from var(--accent-orange) l c h / 0.25); color: var(--accent-orange); }
.hm-cell--miss    { color: var(--text-faint); }
.hm-cell--empty   { color: transparent; }
.hm-player        { font-family: var(--font-sans); font-weight: 600; }

@media (max-width: 720px) {
  .history-matrix th, .history-matrix td { padding: 4px 6px; font-size: 11px; }
  .hm-sticky-col { min-width: 110px; max-width: 130px; }
  .hm-sticky-col .hm-player { text-overflow: ellipsis; overflow: hidden; }
}
```

(Los valores de `top` para `hm-sticky-row-2` se ajustarán durante la implementación al alto real de la fila 1.)

### 6. Enlace desde Rankings

En `templates/stats/rankings.html` el header actual:

```html
<header class="rise" style="margin-bottom:18px">
  <div class="eyebrow">MUNDIAL 2026</div>
  <h1 class="display" style="font-size:28px;margin:6px 0 4px">Rankings</h1>
</header>
```

pasa a:

```html
<header class="rise" style="display:flex;align-items:end;justify-content:space-between;gap:16px;margin-bottom:18px">
  <div>
    <div class="eyebrow">MUNDIAL 2026</div>
    <h1 class="display" style="font-size:28px;margin:6px 0 4px">Rankings</h1>
  </div>
  <a class="chip" href="{% url 'stats:historico' %}">Histórico →</a>
</header>
```

## Tests

### `stats/tests/test_history_matrix.py`

- Devuelve solo partidos con `finished_at` no nulo (excluye `open`, `live`, `pending_teams`).
- Partidos ordenados por `kickoff` ascendente.
- Jugadores ordenados igual que `standings()` (pts, exact_hits, hits, nombre).
- Gestores no aparecen como filas.
- `earned == exact_points_applied` → `state == "exact"`.
- `earned > 0` y distinto del exacto → `state == "partial"`.
- `earned == 0` → `state == "miss"`.
- Sin predicción → `state == "empty"`.
- `totals[player_id]` coincide con la suma de `Prediction.earned` del jugador.

### `stats/tests/test_history_view.py`

- `GET /stats/historico/` sin auth → 302 a login.
- Con auth (jugador) → 200, contiene nombres de jugadores y la cabecera `"ESP - FRA"` (o equivalente real de fixture).
- Incluye `<a>` con `href` al `historico_export`.

### `stats/tests/test_history_export.py`

- `GET /stats/historico.xlsx` sin auth → 302 a login.
- Con auth → 200, `Content-Type` xlsx, `Content-Disposition` con `attachment`.
- `load_workbook(BytesIO(response.content))` produce un workbook con:
  - Hoja `"Histórico"`.
  - Fila 1 contiene `"Jugador"` y `"Total"`.
  - Fila 2 incluye el resultado oficial conocido del fixture.
  - Una celda con marcador exacto tiene `fill.fgColor.rgb` igual a `"FF22C55E"` (openpyxl prefija `FF`).
  - `freeze_panes == "B3"`.

### `stats/tests/test_rankings_view.py` (existente)

Se extiende con un test que comprueba que la página de Rankings (`?tab=general`) contiene un `<a href>` apuntando a `historico`.

## Riesgos y decisiones explícitas

- **Privacidad de pronósticos:** solo entran partidos finalizados; cualquier partido `open` o `live` queda fuera. Esto evita que un jugador vea el pronóstico de otro antes del kickoff. No hace falta gate adicional porque `finished_at` solo se rellena tras introducir el resultado oficial.
- **Coste de query:** una sola query a `Prediction` con `IN` de IDs filtra por la matriz completa. Para 80×100 ≈ 8000 filas máximo: aceptable.
- **Volumen HTML:** ~8000 celdas → ~50–100 KB de HTML. Aceptable; si crece se añadirá paginación más adelante.
- **Sticky en iOS Safari:** `position: sticky` con `border-collapse: separate` funciona en navegadores modernos (Safari 14+); para los bordes se usa `border-right`/`border-bottom` en celdas, no `border` en la tabla.
- **No mostramos avatares en la primera columna:** simplifica el cálculo de altura de fila para el sticky y mantiene el ancho de la columna acotado. Se muestra `posición + nombre`.

## Archivos afectados

**Nuevos:**

- `stats/services/history_matrix.py`
- `stats/services/history_xlsx.py`
- `templates/stats/historico.html`
- `stats/tests/test_history_matrix.py`
- `stats/tests/test_history_view.py`
- `stats/tests/test_history_export.py`

**Modificados:**

- `stats/urls.py` (+2 paths)
- `stats/views.py` (+2 vistas)
- `templates/stats/rankings.html` (header con enlace)
- `static/css/styles.css` (sección history matrix)
- `stats/tests/test_rankings_view.py` (test del enlace)
