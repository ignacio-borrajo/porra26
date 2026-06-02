# Premios: configuración del gestor y vista pública

**Fecha:** 2026-06-02
**Estado:** Aprobado por usuario, listo para plan

## Objetivo

Dar al gestor un sitio claro y bonito para configurar los premios del bote, y reflejar esos premios en la página de Reglas. Hay cuatro importes que configurar:

1. **1er premio** (top de la clasificación final).
2. **2º premio**.
3. **3er premio**.
4. **Premio por ganador de jornada** — un único importe que se entrega al jugador con más puntos en cada jornada de grupos y cada ronda eliminatoria. Es la misma cuantía para todas las jornadas/rondas.

Además, los gestores deben poder llegar a la pantalla `/premios/` desde el menú principal — hoy la ruta existe (`pot:prizes`) pero no hay enlace.

## No-objetivos

- No se calcula automáticamente quién es el ganador de cada jornada — eso es un cálculo futuro. Solo se almacena el importe.
- No se permite personalizar etiquetas: "1er/2º/3er premio" y "Ganador de jornada" son fijas.
- No hay validación de "suma debe cuadrar con el bote"; el gestor es libre de configurar como quiera.

## Modelo de datos

### Cambios

**`pot.PotSettings`** — añadir un campo:

```python
matchday_winner_prize = models.DecimalField(
    max_digits=8, decimal_places=2, default=Decimal("0")
)
```

**`pot.Prize`** — el modelo no cambia. Data migration: borrar las filas con `scope="matchday"` y `scope="round"` sembradas por `0003_seed_prizes.py`. Quedan únicamente las 3 filas con `scope="global"` (posiciones 1, 2, 3).

### Migraciones

- `0004_potsettings_matchday_winner_prize.py` — schema migration.
- `0005_drop_matchday_round_prizes.py` — data migration que limpia filas obsoletas.

Resultado: separación limpia. `PotSettings` es el singleton de configuración (aportación por jugador, dominios de email, premio por jornada). `Prize` es la lista ordenada del podio final (3 filas).

## Backend

### `pot/views.py → PrizesSettingsView`

**`get`** — contexto:

```python
{
  "prizes": Prize.objects.filter(scope="global").order_by("position"),
  "settings": PotSettings.load(),
  "paid_count": Payment.objects.filter(paid=True).count(),
}
```

`pot_total` ya viene del context processor.

**`post`** — en una sola transacción:

1. Para cada `prize` con scope=`global`, leer `amount_{id}` y guardar (no negativo, parsea como `Decimal`).
2. Leer `matchday_winner_prize` y guardar en `PotSettings.load()`.
3. Registrar un único `AuditLog(action="prize_changed", target_type="prize", target_id="*")`.
4. `messages.success("Premios actualizados.")` y redirigir a `pot:prizes`.

Si el parseo falla en algún campo, ignorar ese campo (mismo comportamiento que el código actual). Mantener decimales (no truncar a `int`) — el campo soporta 8.2.

### `core/views.py → RulesView`

Añadir al contexto:

```python
ctx["matchday_winner_prize"] = PotSettings.load().matchday_winner_prize
```

## UI — pantalla `/premios/`

Rediseño del template `templates/pot/prizes_settings.html`, usando los tokens del sistema (glass, Sora, eyebrow, `--c-gold/--c-silver/--c-bronze`, `--r-lg`).

```
┌── Header ─────────────────────────────────────────────────┐
│ eyebrow: GESTOR · CONFIGURACIÓN                           │
│ H1 grad-text Sora 800: Premios del bote                   │
│ subtítulo: "Define cuánto se lleva cada uno y dónde…"     │
└───────────────────────────────────────────────────────────┘

┌── Resumen del bote (3 mini-stats glass) ──────────────────┐
│ Bote total · Aportación/jugador · Jugadores pagando        │
└───────────────────────────────────────────────────────────┘

<form method="post">
  ┌── Podio final ────────────────────────────────────────┐
  │ eyebrow: "Premios finales"                            │
  │ Grid 3 columnas, tarjetas glass tipo medalla:         │
  │   ┌─────────┐ ┌─────────┐ ┌─────────┐                 │
  │   │ 1º oro  │ │ 2º plata│ │ 3º bronce│                │
  │   │ [____]€ │ │ [____]€ │ │ [____]€  │                │
  │   │ "1er    │ │ "2º     │ │ "3er     │                │
  │   │ premio" │ │ premio" │ │ premio"  │                │
  │   └─────────┘ └─────────┘ └─────────┘                 │
  └───────────────────────────────────────────────────────┘

  ┌── Premio por ganador de jornada ──────────────────────┐
  │ eyebrow: "Por jornada"                                │
  │ Tarjeta destacada, acento --c-cyan                    │
  │ trofeo + input grande + €                             │
  │ Texto: "El jugador con más puntos en cada jornada     │
  │  o ronda se lleva este importe. Se aplica por igual   │
  │  a las 3 jornadas de grupos y a cada ronda KO."       │
  └───────────────────────────────────────────────────────┘

  [ Guardar premios ]   ← primary button
</form>
```

Detalles visuales:
- Las medallas reutilizan el lenguaje visual de `.rules-medals` (gradiente oro/plata/bronce en el badge) pero con el importe como input editable en lugar de `<strong>` estático.
- Inputs `type="number" min="0" step="0.01"` con tipografía Sora grande dentro del card.
- Sin sticky button — botón al final del form, ancho contenido (variant `btn-primary`).

## UI — página de Reglas

`templates/core/rules.html`, sección **03 · El bote y los premios**:

- Mantener tal cual el bloque actual de `rules-medals` (top 3).
- **Añadir** debajo de las medallas (antes del párrafo final "El gestor marca quién ha pagado…") una tarjeta `glass` nueva tipo "callout":

```html
<div class="rules-matchday-prize">
  <span class="rules-matchday-icon">{% icon "trophy" ... %}</span>
  <div>
    <strong>{{ matchday_winner_prize|floatformat:"-2" }} €</strong>
    <span class="eyebrow">Premio por ganador de jornada</span>
    <p>El jugador con más puntos en cada jornada de grupos y en cada
       ronda eliminatoria se lleva este premio extra.</p>
  </div>
</div>
```

Estilo: glass + acento `--c-cyan` (para diferenciarse del oro de las medallas). CSS nuevo en `static/css/styles.css` (sección rules), siguiendo las convenciones del archivo.

Si `matchday_winner_prize == 0`, ocultar la tarjeta (sin sentido mostrar 0 €).

## Navegación — Topbar

`templates/partials/_topbar.html`:

- Añadir un nuevo `<a>` dentro del bloque `{% if user.is_gestor %}`:

```html
<a href="{% url 'pot:prizes' %}"
   class="nav-item{% if url_name == 'prizes' %} is-active{% endif %}">
  {% icon "euro" width=17 height=17 %} Premios
</a>
```

- Ajustar el active-state del enlace "Jugadores" para que no se quede activo en `/premios/`. Actualmente:
  `{% if ns == 'pot' %}` — demasiado amplio.
  Pasa a: `{% if ns == 'pot' and url_name != 'prizes' and url_name != 'audit' %}`.

## Tests

`pot/tests/test_prizes_settings.py` (nuevo):

1. `test_get_renders_form` — gestor accede a `/premios/`, ve 3 inputs de podio + input de matchday winner, valores actuales precargados.
2. `test_non_gestor_denied` — jugador (sin `is_gestor`) recibe 302/403.
3. `test_post_updates_all_amounts` — POST con 4 importes → comprueba que `Prize.amount` cambia en las 3 filas globales y `PotSettings.matchday_winner_prize` cambia.
4. `test_post_creates_audit_log` — POST → existe un `AuditLog(action="prize_changed")` para `request.user`.
5. `test_post_ignores_invalid_amount` — POST con texto no numérico en un campo → ese campo no se actualiza, los demás sí.

`pot/tests/test_topbar_prizes_link.py` (o ampliar uno existente): gestor ve el enlace "Premios" en el topbar; jugador no.

`core/tests/test_rules_view.py` (ampliar si existe): si `matchday_winner_prize > 0`, la tarjeta aparece; si es 0, no aparece.

## Documentación y memoria

- `docs/DATA_MODEL.md` §1, fila Pot/Settings: añadir `matchdayWinnerPrize` (Decimal) y nota: "el modelo `Prize` ahora se usa solo para el podio final (top 3)".
- Memoria `project_reglas_pagina.md`: añadir mención al premio por ganador de jornada y a la pantalla `/premios/` como fuente de configuración.

## Riesgos / consideraciones

- **Migración destructiva**: la `0005` borra filas existentes de `Prize` con scope distinto a global. El gestor pierde sus importes anteriores de matchday/round (probable que estén a 0 — son recién sembrados). No es una regresión real, pero la migración debe ser reversible (en reverse, no las restauramos — son re-sembrables a 0 si hace falta).
- **Concurrency**: el `post` actualiza varias filas sin transacción explícita. Envolver en `transaction.atomic()` por consistencia con el `AuditLog`.
- **Permisos**: ya cubiertos por `GestorRequiredMixin` en la vista. Sin cambios.
