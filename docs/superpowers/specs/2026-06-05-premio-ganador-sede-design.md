# Spec — Premio al ganador final por sede

Fecha: 2026-06-05
Branch destino: `worktree-premio-ganador-sede`
Stack: Django + plantillas server-side. Reutiliza el sistema de anuncios existente (`announcements/`) y el modal de ganador (`templates/announcements/_winner_modal.html`).

---

## 1. Problema

Hoy, al cierre del Mundial 2026, solo se premia al podio global (1·2·3). Toda sede que no tenga a uno de sus jugadores entre los tres primeros del global queda sin reconocimiento, aunque dentro de esa sede haya habido competición real.

Queremos añadir un **premio simbólico al mejor jugador de cada sede** (Ourense, Vigo, Asturias, Madrid, Barcelona, Latinoamérica) que se entrega al cierre del torneo, mostrarlo en la página de reglas y comunicarlo a los jugadores con una modal análoga a la del campeón del Mundial.

Caso a evitar: que un jugador del podio global cobre además el premio de su sede. Si Ana es 1ª del global y mejor de Madrid, **Ana cobra solo el global** y el premio de Madrid pasa al siguiente mejor de Madrid que no esté en el top 3 del global.

## 2. Objetivo

- Definir el premio "ganador de sede" como una cifra única configurable por el gestor.
- Mostrarlo en la página de reglas dentro del bloque "El bote y los premios", con copy que explique la regla de exclusión global → sede.
- Crear, al resolver el último partido de la Final, un nuevo `WinnerAnnouncement` con `scope_kind="sede"` que cubre las 6 sedes a la vez.
- Mostrar a continuación de la modal del campeón global una **segunda modal** con un grid de las 6 sedes y su ganador (estilo pedestal coherente con el podio existente).
- Reutilizar el sistema de "modal vista" (`WinnerAnnouncementSeen`) y de cascada (`X-Modal-Next`) ya existente.

## 3. Alcance

**Incluido:**

- Nuevo `DecimalField` `sede_winner_prize` en `pot.models.PotSettings`.
- Nuevo valor `("sede", "Ganadores por sede")` en `WinnerAnnouncement.SCOPE_CHOICES` + `UniqueConstraint` (como máximo un anuncio `scope_kind="sede"`).
- Nuevo servicio `pot/services/prizes.py:sede_winners()` que computa el ganador de cada sede aplicando la regla de exclusión global.
- Hook en `announcements/services.py:detect_after_match()` para crear el anuncio `sede` tras la Final, además del `global`.
- Bifurcación de `templates/announcements/_winner_modal.html` por `scope_kind`: para `sede` se renderiza un grid de 6 tarjetas en vez del podio 2·1·3.
- CSS específico para las tarjetas de sede (versión compacta del pedestal del podio).
- Soporte de **vista previa** del gestor para `scope=sede` en `announcements/preview.py` y `AnnouncementPreviewView`.
- Nuevo bloque en `templates/core/rules.html` ("03 · El bote y los premios") con el premio por ganador de sede + redacción de la regla de exclusión.
- Extensión de la sección "04 · Desempate" para mencionar el ganador de sede.
- Nuevo campo `sede_winner_prize` en el formulario y la plantilla de "Premios y puntos" del gestor.
- Migraciones, tests, documentación en `docs/DATA_MODEL.md`.

**Fuera de alcance:**

- Premios para 2º y 3º de cada sede.
- Importe variable por sede (sería un cambio de modelo a `Prize(scope='sede', sede=…)`).
- Página navegable de "ganadores por sede" fuera de la modal.
- Notificaciones por email / Teams del ganador de sede.
- Cambios visuales fuera de la modal y del bloque de reglas.

## 4. Reglas de negocio

### 4.1 Quién es "ganador de sede"

Para una sede `S`:

1. Computar el podio global: jugadores con `position ∈ {1,2,3}` y `pts > 0` en la `standings()` general. Llamamos a ese conjunto `top3_global_ids`.
2. Filtrar `standings()` por:
   - `user.sede == S`
   - `user.id NOT IN top3_global_ids`
   - `pts > 0`
3. Coger todos los empatados en la **posición mínima** del subconjunto resultante (la posición de `standings()` ya aplica las 3 reglas de desempate: pts → exactos → aciertos).
4. Si el resultado es vacío → sede `S` queda **desierta**, no se entrega premio.
5. Si hay N ≥ 1 ganadores → cada uno cobra `sede_winner_prize / N`.

### 4.2 Casos especiales

| Caso | Comportamiento |
|------|----------------|
| Usuario con `sede=""` | No compite por ningún premio de sede; no aparece en ninguna tarjeta. |
| Sede sin jugadores con `sede==S` | Tarjeta en estado "Desierto". |
| Sede sin jugadores con `pts > 0` | Tarjeta en estado "Desierto". |
| Sede donde el mejor está en top 3 global | Se elige al siguiente mejor de esa sede no presente en top 3. |
| Sede donde TODOS los con `pts > 0` están en top 3 global | Tarjeta en estado "Desierto". |
| Empate ≥ 2 dentro de una sede tras desempate | Tarjeta muestra "N jugadores", "a cada uno", premio dividido. |
| Las 6 sedes desiertas | No se crea el `WinnerAnnouncement scope=sede` (no hay nada que celebrar). |
| `sede_winner_prize == 0` | El anuncio sí se crea, pero las tarjetas omiten el importe (mismo trato que el podio global cuando `prize == 0`). |
| Re-disparo de `detect_after_match` tras la Final | Idempotente por `UniqueConstraint`. |

### 4.3 Por qué top 3 global y no solo 1º

Decisión del usuario (brainstorming): los tres del podio global ya cobran un premio del torneo y deben quedar fuera del cálculo de sede. Esto maximiza el número de ganadores distintos y evita "doble premio".

## 5. Modelo de datos

### 5.1 `pot.PotSettings` (modificación)

```python
class PotSettings(models.Model):
    per_player = models.DecimalField(...)
    allowed_email_domains = models.JSONField(...)
    matchday_winner_prize = models.DecimalField(...)
    maintenance_cost = models.DecimalField(...)
    sede_winner_prize = models.DecimalField(           # ← NUEVO
        max_digits=8, decimal_places=2, default=Decimal("0")
    )
```

Migración: `AddField`, default `0`.

### 5.2 `announcements.WinnerAnnouncement` (modificación)

```python
SCOPE_CHOICES = [
    ("matchday", "Jornada de grupos"),
    ("round", "Ronda KO"),
    ("global", "Campeón del Mundial"),
    ("sede", "Ganadores por sede"),     # ← NUEVO
]
```

Añadir `UniqueConstraint` análoga a la del global:

```python
UniqueConstraint(
    fields=["scope_kind"],
    condition=Q(scope_kind="sede"),
    name="uniq_ann_sede",
),
```

Para `scope_kind="sede"`:
- `scope_matchday = None`, `scope_round = None`.
- `points = 0` (no aplica un valor único; cada sede tiene los suyos). En el template se oculta para este scope.
- `tied = False`.
- `share = Decimal("0")`. El premio real se calcula al renderizar (mismo patrón que el podio del global).
- `winners` (M2M) → unión plana de los ganadores de todas las sedes resueltas, para trazabilidad.

`WinnerAnnouncement.title` para `scope_kind="sede"`:
- `"¡Ganadores por sede!"` (siempre plural, no depende de `tied`).

### 5.3 No se toca `Prize`

La cifra única vive en `PotSettings.sede_winner_prize` (mismo enfoque que `matchday_winner_prize`). `Prize` queda reservado para premios con `scope ∈ {global, matchday, round}` y `position` definida.

## 6. Lógica de cómputo

### 6.1 `pot/services/prizes.py`

Nueva dataclass:

```python
@dataclass
class SedeWinner:
    sede_key: str            # "madrid", "vigo", ...
    sede_label: str          # "Madrid", "Vigo", ...
    users: list              # 0, 1 o N (empate)
    points: int              # puntos del ganador (0 si desierto)
    prize_per_user: Decimal  # share del sede_winner_prize si N > 0
    status: str              # "resolved" | "desierto"
```

Nuevo servicio:

```python
def sede_winners() -> list[SedeWinner]:
    """Devuelve un SedeWinner por cada sede de User.SEDE_CHOICES,
    en el orden de SEDE_CHOICES. Excluye del cálculo a los jugadores
    del top 3 global."""
```

Algoritmo:

1. `rows = standings()` (clasificación general completa).
2. `top3_global_ids = {r.player_id for r in rows if r.position in (1,2,3) and r.pts > 0}`.
3. Bulk fetch de `User.sede` por id.
4. Para cada `(sede_key, sede_label)` en `User.SEDE_CHOICES`:
   - Filtrar `rows` por sede y excluir top 3 global y `pts > 0`.
   - Si vacío → `SedeWinner(status="desierto", ...)`.
   - Si no, coger empatados en `min(position)` y construir `SedeWinner(status="resolved", users=[...], points=..., prize_per_user=PotSettings.load().sede_winner_prize / N)`.

### 6.2 Idempotencia y momento de cálculo

- El servicio `sede_winners()` se llama **al renderizar** la modal (mismo patrón que `announcement_podium`), así el importe siempre refleja el `PotSettings.sede_winner_prize` vigente.
- Lo que persiste en la BD es el M2M `winners` (unión plana) — esto es para auditoría/futuro, no se usa en el render.

## 7. Disparo del anuncio

En `announcements/services.py:detect_after_match()`:

```python
if match.round_id == "final":
    ann_global = _try_create("global")
    if ann_global is not None:
        created.append(ann_global)
    ann_sede = _try_create("sede")              # ← NUEVO
    if ann_sede is not None:
        created.append(ann_sede)
```

Extender `_try_create()` para aceptar `scope_kind="sede"`:

- `filter_kwargs = {"scope_kind": "sede"}`.
- Para determinar si "está resuelto":
  - Llamar a `sede_winners()`.
  - Considerar "resolved" si **al menos una** sede tiene `status="resolved"`.
  - Si las 6 están desiertas → no crear el anuncio.
- Al crear:
  - `points=0`, `tied=False`, `share=Decimal("0")`.
  - `winners` = unión flat de `[u for sw in sede_winners() if sw.status=="resolved" for u in sw.users]`.

Orden de cascada para el jugador:

1. Modal "¡Campeón del Mundial!" (creada justo antes, `created_at` menor).
2. Modal "¡Ganadores por sede!" (creada justo después).

Esto sale gratis del sistema actual: `X-Modal-Next` selecciona el siguiente `WinnerAnnouncement` no visto por el usuario ordenando por `created_at`.

## 8. Renderizado: vistas y plantilla

### 8.1 `AnnouncementModalView.get()`

Bifurcar el contexto por `scope_kind`:

```python
if ann.scope_kind == "sede":
    return render(request, "announcements/_winner_modal.html", {
        "announcement": ann,
        "sede_winners": sede_winners(),
    })
else:
    podium = announcement_podium(ann)
    return render(request, "announcements/_winner_modal.html", {
        "announcement": ann,
        "podium": podium,
        "podium_visual": _podium_visual_order(podium),
    })
```

### 8.2 `AnnouncementPreviewView.get()` (vista previa del gestor)

Soportar `?scope=sede`. En `announcements/preview.py`:

```python
def build_preview_sede(*, current_user) -> tuple[WinnerAnnouncement, list[SedeWinner]]:
    """Construye un anuncio sintético para previsualizar la modal de sede.
    Devuelve 6 SedeWinner: para sedes con jugadores reales se toma uno
    aleatorio (el primero por nombre); para sedes vacías se devuelve
    estado 'desierto' para que el gestor vea ambos estados."""
```

Cuando `?scope=sede` llega a `AnnouncementPreviewView`, devolver `_winner_modal.html` con el contexto `{announcement, preview: True, sede_winners}`.

### 8.3 `templates/announcements/_winner_modal.html`

Bifurcar en la plantilla:

```django
<section class="glass pop winner-modal winner-modal--{{ announcement.scope_kind }}" ...>
  ...
  <h2 id="winner-title" class="winner-title">{{ announcement.title }}</h2>

  {% if announcement.scope_kind == "sede" %}
    {# Subtítulo y grid de sedes #}
    <p class="winner-subtitle">Los mejores de cada sede del Mundial 2026.</p>
    <div class="winner-modal-sede-grid" role="list">
      {% for sw in sede_winners %}
        <div class="winner-modal-sede-card {% if sw.status == 'desierto' %}is-empty{% endif %}" role="listitem">
          <span class="winner-modal-sede-label">{{ sw.sede_label }}</span>
          {% if sw.status == "resolved" %}
            <div class="winner-modal-sede-medal">🥇</div>
            <div class="winner-modal-sede-avatars {% if sw.users|length > 1 %}is-tied{% endif %}">
              {% for u in sw.users|slice:":2" %}
                {% include "partials/_avatar.html" with u=u size=44 %}
              {% endfor %}
              {% if sw.users|length > 2 %}
                <span class="winner-modal-sede-more">+{{ sw.users|length|add:'-2' }}</span>
              {% endif %}
            </div>
            <div class="winner-modal-sede-name">
              {% if sw.users|length > 1 %}{{ sw.users|length }} jugadores
              {% else %}{{ sw.users.0.name }}{% endif %}
            </div>
            {% if sw.prize_per_user > 0 %}
              <div class="winner-modal-sede-prize">
                <span class="mono">{{ sw.prize_per_user|floatformat:2 }} €</span>
                {% if sw.users|length > 1 %}<span class="winner-prize-note">a cada uno</span>{% endif %}
              </div>
            {% endif %}
          {% else %}
            <div class="winner-modal-sede-empty">Desierto</div>
          {% endif %}
        </div>
      {% endfor %}
    </div>
  {% else %}
    {# Bloque actual: puntos + podio 2·1·3 #}
    <p class="winner-points">{{ announcement.points }} puntos</p>
    <div class="winner-modal-podium" role="list"> ... </div>
  {% endif %}

  <p class="winner-subtitle">...</p>
  <div class="winner-actions">...</div>
</section>
```

### 8.4 Estilos

Añadir un bloque CSS con clases `.winner-modal-sede-*` que reproduzcan el lenguaje visual del pedestal actual pero a escala compacta. Decisiones concretas:

- Grid: `grid-template-columns: repeat(3, 1fr)` desktop, `repeat(2, 1fr)` tablet, `1fr` móvil estrecho.
- Cada tarjeta: `padding: 14px`, borde glass, `border-radius: var(--r-md)`, gap interno 8px.
- Estado `is-empty`: opacity 0.6, sin medalla, sin pedestal dorado.
- Avatar 44px, medalla 28px (más pequeño que en el podio global).

El CSS de la modal vive en `static/css/styles.css` (junto al resto de `.winner-modal-*`); los nuevos selectores `.winner-modal-sede-*` se añaden allí, en la zona vecina a `.winner-modal-podium-*`.

## 9. Página de reglas

### 9.1 `core/views.py:RulesView.get_context_data`

Añadir:

```python
ctx["sede_winner_prize"] = pot_settings.sede_winner_prize
```

### 9.2 `templates/core/rules.html`

En la sección "03 · El bote y los premios", añadir tras el bloque de `matchday_winner_prize` (líneas 217-226):

```html
{% if sede_winner_prize and sede_winner_prize > 0 %}
<div class="rules-matchday-prize">
  <div class="rules-matchday-prize-icon">{% icon "map-pin" width=22 height=22 aria_hidden="true" %}</div>
  <div class="rules-matchday-prize-body">
    <span class="eyebrow">Premio por ganador de sede</span>
    <strong>{{ sede_winner_prize|floatformat:"-2" }} €</strong>
    <p>
      Al cierre del Mundial, el mejor jugador de cada sede
      (Ourense, Vigo, Asturias, Madrid, Barcelona y Latinoamérica) se lleva este premio.
      Si alguien ya está entre los tres primeros del podio final, el premio de su sede pasa
      al siguiente mejor de esa sede que no esté en el podio global.
    </p>
  </div>
</div>
{% endif %}
```

En la sección "04 · Desempate", extender el párrafo final mencionando que la misma regla de desempate aplica al ganador de sede.

> Si el icono `map-pin` no existe en el set actual, escoger uno equivalente del conjunto disponible (por ejemplo `flag` o `trophy` ya usado), sin introducir un nuevo asset.

## 10. Pantalla del gestor — "Premios y puntos"

Pasos en `pot/forms.py`, `pot/views.py` y la plantilla correspondiente:

1. Añadir `sede_winner_prize` a `PotSettingsForm.Meta.fields`.
2. `DecimalField(min_value=0)`, mismo widget que `matchday_winner_prize`.
3. En la plantilla, añadir el campo justo debajo de "Premio por ganador de jornada":
   - Label: "Premio por ganador de sede".
   - Helper text: "Importe que cobra el mejor jugador de cada sede al cierre del Mundial (excluyendo el podio global)."
4. La pantalla ya tiene un botón "Vista previa modal ganador"; añadir el botón análogo "Vista previa ganadores por sede" que enlace a `?scope=sede`.

## 11. Documentación

Actualizar `docs/DATA_MODEL.md`:

- Sección "PotSettings": añadir `sede_winner_prize`.
- Sección de reglas de negocio (premios): describir el premio por ganador de sede y la regla de exclusión global → sede.

`CLAUDE.md` no requiere cambios (las reglas concretas viven en `docs/DATA_MODEL.md`).

## 12. Tests

Mismo patrón que `pot/tests/test_prizes.py` y `announcements/tests/test_services.py`.

### 12.1 `pot/tests/test_sede_winners.py` (nuevo)

1. `test_basic_two_sedes_with_clear_winners` — 2 sedes con un ganador claro cada una. Verifica selección, premio, status="resolved".
2. `test_excludes_global_top3` — el mejor de Madrid es 1º global → el ganador de Madrid es el 2º de Madrid (no en top 3 global).
3. `test_sede_with_all_players_in_global_top3` — toda la sede X tiene a sus jugadores con puntos en top 3 global → status="desierto".
4. `test_tied_inside_sede` — empate dentro de la sede tras los 3 desempates → premio dividido, ambos usuarios en `users`.
5. `test_user_without_sede_ignored` — usuario con `sede=""` no aparece en ninguna tarjeta.
6. `test_empty_sede_returns_desierto` — sede sin jugadores → status="desierto".
7. `test_sede_with_no_points_returns_desierto` — sede con jugadores pero todos `pts=0` → status="desierto".
8. `test_returns_six_entries_in_sede_choices_order` — siempre devuelve len=6 en el orden de `SEDE_CHOICES`.
9. `test_prize_zero_when_setting_zero` — `PotSettings.sede_winner_prize=0` → `prize_per_user=0` pero status sigue siendo "resolved" si hay ganadores.

### 12.2 `announcements/tests/test_sede_announcement.py` (nuevo)

10. `test_announcement_sede_created_after_final` — al resolver el último partido de la final, se crea `WinnerAnnouncement(scope_kind="sede")` además del `global`.
11. `test_announcement_sede_idempotent` — segunda llamada no duplica (UniqueConstraint).
12. `test_announcement_sede_not_created_when_all_desierto` — caso degenerado: 6 sedes desiertas → no se crea anuncio.
13. `test_announcement_sede_winners_m2m_is_union_of_sede_winners` — al crearlo, el M2M `winners` contiene la unión flat de ganadores de todas las sedes resueltas.

### 12.3 `announcements/tests/test_views.py` (extensión)

14. `test_modal_renders_sede_grid` — GET `/anuncios/<id>/` con scope `sede` renderiza el grid con 6 tarjetas (selector CSS o conteo en el HTML).
15. `test_modal_sede_card_resolved_state` — tarjeta de sede resuelta muestra nombre y premio.
16. `test_modal_sede_card_desierto_state` — tarjeta desierta muestra texto "Desierto" y no muestra avatar.
17. `test_modal_preview_sede_for_gestor` — GET `/anuncios/preview/?scope=sede` con usuario gestor devuelve 200 y renderiza el grid con datos sintéticos.
18. `test_modal_preview_sede_forbidden_for_jugador` — GET `?scope=sede` con jugador normal devuelve 403 (igual que otros scopes).

### 12.4 `core/tests/test_rules_view.py` (extensión)

19. `test_rules_shows_sede_prize_block` — con `PotSettings.sede_winner_prize > 0`, la página renderiza el bloque "Premio por ganador de sede".
20. `test_rules_hides_sede_prize_block_when_zero` — con `sede_winner_prize=0`, el bloque no aparece (consistente con `matchday_winner_prize`).
21. `test_rules_mentions_exclusion_rule` — el copy contiene la frase clave sobre la regla de exclusión (afirmación de "no esté en el podio global").

### 12.5 `pot/tests/test_pot_settings.py` (extensión)

22. `test_form_includes_sede_winner_prize` — `PotSettingsForm` tiene el campo y acepta `Decimal`.
23. `test_form_rejects_negative_sede_prize` — `sede_winner_prize=-1` no valida.

## 13. Migraciones

- `pot/migrations/000X_potsettings_sede_winner_prize.py` — `AddField(sede_winner_prize, DecimalField, default=0)`.
- `announcements/migrations/000Y_winnerannouncement_sede_scope.py` — `AlterField(scope_kind.choices)` + `AddConstraint(uniq_ann_sede)`.

Sin data migrations.

## 14. Cambios fuera de alcance pero a vigilar

- **PDFs y "shareables"**: si en el futuro se genera un PDF con todos los ganadores, ese flujo deberá leer también `sede_winners()`. Hoy no aplica.
- **Página de rankings por sede** (`/stats/rankings/sede/<key>/`): no cambia. El podio que muestra ahí no aplica la regla de exclusión global, porque ahí queremos ver el ranking *real* de la sede, no quién cobra el premio. Documentar este matiz en el copy de Reglas o en `DATA_MODEL.md` si se considera necesario.

## 15. Riesgos

- **Inconsistencia entre "ganador mostrado en la modal" y "ranking de sede en /stats"**: la modal aplica regla de exclusión, el ranking no. El copy de la modal y de Reglas debe dejar esto explícito ("si está en el podio final, el premio pasa al siguiente"). El ranking se sigue mostrando intacto.
- **Importe 0 + anuncio creado**: si el gestor olvida configurar `sede_winner_prize`, la modal sigue apareciendo con tarjetas sin importe. Aceptable como reconocimiento simbólico, y la pantalla "Premios y puntos" ya destaca campos sin configurar (mismo trato que `matchday_winner_prize`).
- **Vendoring/CSS**: la modal `sede` añade clases nuevas. Cuidado con no romper estilos del podio global (`.winner-modal-podium-*` se mantiene intacto; usamos prefijo `.winner-modal-sede-*`).
