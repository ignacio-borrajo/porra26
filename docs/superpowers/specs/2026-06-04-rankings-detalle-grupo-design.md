# Spec — Detalle de clasificación por grupo en Rankings

## Problema
En `/stats/rankings/` los tabs `Sede`, `Puesto` y `Departamento` muestran una tabla agregada (una fila por grupo, con media, total y líder), pero no permiten **ver la clasificación interna del grupo**. Marketing quiere poder pulsar una fila (p. ej. "Madrid" en Sede) y aterrizar en una clasificación completa, con puestos de honor (podio) y selector de jornadas, restringida a los jugadores de ese grupo.

## Objetivo
Añadir una página de detalle por grupo que reproduzca *exactamente* el layout del tab **General** (panel general + panel por jornada + podio), pero filtrado a los usuarios pertenecientes al grupo seleccionado. Las pestañas y tablas actuales se mantienen sin cambios.

## Alcance
- Las filas de las tablas agregadas de `sede`, `puesto` y `dept` se vuelven enlaces a una nueva URL de detalle.
- Nueva URL `/stats/rankings/<dim>/<key>/` con `dim ∈ {sede, puesto, dept}` y `key` ∈ choices del dim.
- Nueva vista `GroupRankingsView` que reutiliza la lógica de la rama `general` de `RankingsView`, pero pasando un filtro de `player_ids` al servicio `standings()`.
- Extensión retro-compatible del servicio `competition.services.standings.standings()` para aceptar un parámetro opcional `player_ids`.
- Nuevo template `templates/stats/rankings_group.html` con breadcrumb y los dos paneles del tab General.
- Sigue siendo accesible solo para usuarios autenticados (`LoginRequiredMixin`).

## Fuera de alcance
- Cambios en `stats/services/group_standings.py` (la tabla agregada no se toca).
- Cambios en el tab General, los KPIs o el podio existente.
- KPIs específicos del grupo (media, mejor jornada del grupo, etc.): no los pide marketing y se pueden añadir después.
- Permitir clicar la fila "Sin asignar" (`__none__`): no es un grupo real.
- Compartir/enlazar profundo desde fuera de la app (la URL queda bonita y funcionará, pero no se hace nada extra).

## Diseño

### 1) URL y navegación
- `stats/urls.py`: nueva ruta
  ```python
  path("rankings/<slug:dim>/<slug:key>/", views.GroupRankingsView.as_view(), name="rankings_group")
  ```
- En `templates/stats/rankings.html`, cada `<div class="table-row">` de los tabs `sede/puesto/dept` se transforma en un `<a class="table-row" href="{% url 'stats:rankings_group' dim=tab key=r.key %}">…</a>`.
  - Excepción: la fila `__none__` ("Sin asignar") sigue siendo un `<div>` no clicable.
  - Se añade `text-decoration:none;color:inherit;cursor:pointer` y una sutil regla hover (`background:oklch(from var(--accent) l c h / 0.06)`) en línea, sin nuevas reglas CSS globales.

### 2) Servicio `standings()` — extensión
Firma actual:
```python
def standings(round_id: str | None = None, matchday: int | None = None) -> list[StandingRow]
```
Firma nueva:
```python
def standings(
    round_id: str | None = None,
    matchday: int | None = None,
    player_ids: Iterable[int] | None = None,
) -> list[StandingRow]
```
Cambios internos:
- Si `player_ids` no es `None`:
  - Se filtra el queryset de `Prediction` con `player_id__in=player_ids`.
  - El padding de jugadores sin predicciones se restringe con `User.objects.filter(...).filter(id__in=player_ids)`.
- `streak`/`trend` siguen las mismas reglas que ahora (solo se calculan si no hay scope de ronda/jornada). El cálculo se hace sobre el conjunto filtrado, así que las posiciones reflejan únicamente al grupo.
- Si `player_ids` es una colección vacía, el resultado es lista vacía sin disparar queries inútiles (early return).

### 3) Vista `GroupRankingsView`
- `LoginRequiredMixin`, `View.get`.
- Valida `dim` contra `{"sede", "puesto", "dept"}` → 404 si no.
- Valida `key` contra las keys de `CHOICES_BY_DIMENSION[dim]` (importado de `stats.services.group_standings`) → 404 si no.
- Resuelve `player_ids`:
  ```python
  player_ids = list(
      User.objects.filter(is_active=True, is_jugador=True, **{dim: key})
      .values_list("id", flat=True)
  )
  ```
- Construye el contexto reusando la lógica actual de la rama `general` de `RankingsView`, con dos diferencias:
  1. Las llamadas a `standings(...)` reciben `player_ids=player_ids`.
  2. El chip "Tú · #N" solo se pinta si `request.user.id in player_ids` (esto cae solo: `my_row` ya es `None` si el usuario no está en el grupo filtrado).
- Añade al contexto: `dim`, `dim_label` (de `RankingsView.TAB_LABELS`), `group_label` (el label legible del choice), `player_count` (`len(player_ids)`).
- Render: `templates/stats/rankings_group.html`.

### 4) Template `rankings_group.html`
Extiende `base.html` y reproduce el bloque actual del tab General (`{% if tab == "general" %}` en `rankings.html`), con dos cambios:

1. **Header**: en lugar del eyebrow "MUNDIAL 2026" + título "Rankings", un breadcrumb:
   ```
   ← Rankings · {{ dim_label }}
   {{ group_label }}
   ```
   El "← Rankings" es un enlace a `{% url 'stats:rankings' %}?tab={{ dim }}`. La descripción debajo dice: "Clasificación general y por jornada de {{ group_label }} ({{ player_count }} jugadores)."

2. **Estado vacío del grupo**: si `player_count == 0`, en lugar de los paneles se pinta una tarjeta `.glass` con un mensaje: "Aún no hay jugadores en {{ group_label }}." (los partials ya manejan rows vacíos, pero esta es una salida más explícita).

Los dos paneles (`general` + `scope`) y su selector de jornadas se renderizan con los mismos partials existentes (`_leaderboard_panel.html`, `_podium_step.html`, `_leaderboard_row.html`) y la misma estructura HTML/CSS que `rankings.html`. No se introduce CSS nuevo: el layout `.rankings-clas` y `.rankings-md-selector` ya está definido y funciona en cualquier página.

### 5) Refactor opcional (DRY)
La rama `tab == "general"` de `RankingsView` y la nueva `GroupRankingsView` comparten ~30 líneas (resolución de scope, llamadas a `standings`, cálculo de `max_pts`, etc.). Para no duplicar:
- Extraer un helper `stats.services.rankings_context.build_general_context(user, requested_scope_key, *, player_ids=None) -> dict` que devuelva el dict con `standings`, `standings_users`, `my_rank`, `my_is_tied`, `max_pts`, `scope_*`, `md_options`.
- Ambas vistas lo invocan; `RankingsView` con `player_ids=None`, `GroupRankingsView` con el filtrado.

Coste bajo y elimina la duplicación. Se incluye en este alcance.

## Decisiones tomadas
- **Posición de podio dentro del grupo** (no posición global). Es lo coherente con "puestos de honor de Madrid" y lo que pidió marketing (`PERP solo con los usuarios de la sede/puesto/departamento`). El detalle vive aislado del ranking global y no hay que cargar contexto extra.
- **Página dedicada** en lugar de modal o inline. Soporta enlace directo, back del navegador y se ve igual en móvil sin tener que mantener una variante de modal aparte.
- **Reutilizar partials existentes** (`_leaderboard_panel.html`, `_podium_step.html`) en lugar de duplicar HTML. Cualquier cambio futuro del podio se propaga a las dos páginas a la vez.
- **Extender `standings()` con `player_ids`** en lugar de crear un servicio paralelo: la lógica de orden, empates, streaks y trends es exactamente la misma; un parámetro opcional es la mínima intrusión.
- **Las claves del choice ya son slug-safe** (`madrid`, `desarrollo`, `nominas`…), así que no hace falta mapear a slugs externos.
- **Fila "Sin asignar" no clicable**: no representa un grupo real; si en el futuro se quiere ver, se decide caso aparte.

## Riesgos
- Cambiar la firma de `standings()` puede romper llamadas existentes si alguna pasa posicionalmente. Mitigación: el nuevo parámetro va al final con default `None`; revisar todos los call sites antes de aplicar.
- Una URL con `dim`/`key` falsos debe devolver 404 limpio (no 500). Mitigación: validación explícita + test.
- Hacer las filas `<a>` puede romper el estilo `grid` actual si el navegador no respeta `display:grid` en un anchor. Mitigación: se aplica `display:grid` explícito en el `<a>` y se valida en navegador.

## Verificación

### Tests (`stats/tests/test_rankings_view.py` y `competition/tests/test_standings.py`)
1. `standings(player_ids=[id1, id2])` devuelve únicamente esos jugadores con posiciones recalculadas a partir de 1.
2. `standings(player_ids=[])` devuelve lista vacía.
3. `standings(player_ids=..., round_id=..., matchday=...)` combina ambos filtros.
4. `GET /stats/rankings/sede/madrid/` con jugadores de Madrid → 200, contiene podio (`podium-slot--1`) y el selector de jornadas.
5. El podio del detalle son los top-3 dentro del grupo, no los top-3 globales (assert sobre IDs).
6. `GET /stats/rankings/sede/madrid/` cuando el usuario actual está en Madrid → chip "Tú · #N" presente. Cuando no está → ausente.
7. `GET /stats/rankings/sede/madrid/` con 0 jugadores en el grupo → 200 con mensaje de vacío.
8. `GET /stats/rankings/foo/bar/` → 404 (dim inválido).
9. `GET /stats/rankings/sede/atlantis/` → 404 (key inválida).
10. Regresión: las tablas agregadas de `sede/puesto/dept` siguen renderizando todas sus filas, y las filas (excepto `__none__`) son ahora enlaces a la nueva URL.

### Manual (`python manage.py runserver` con datos de prueba)
- Visitar `/stats/rankings/?tab=sede`, pulsar fila "Madrid": llega al detalle, el podio coincide con el top-3 de jugadores de Madrid, el selector de jornadas funciona y el chip "Tú" solo aparece si el usuario logueado es de Madrid.
- Navegar a un grupo con un solo jugador: el panel general muestra el podio con un único slot ocupado; el panel scope se comporta igual.
- Navegar a un grupo vacío: ver el mensaje explícito de vacío sin errores.
- Pulsar "← Rankings" del breadcrumb: vuelve al tab correspondiente.
