# Spec — Colapsar empates múltiples en el podio (≥3 jugadores)

## Problema

Cuando tres o más jugadores comparten plaza en el podio (1º, 2º o 3º), el slot apila avatares verticalmente (`.podium-slot--multi`). Funciona con 2 empatados, pero con 3+ los nombres se vuelven minúsculos, los avatares se aplastan y la columna estira el podio entero. Casos reales esperados:

- Inicio de la competición: docenas de jugadores empatados a 0 puntos en 1ª.
- Tras una jornada con pocos partidos: empates masivos.

## Objetivo

A partir de **3 empatados en la misma plaza del podio**, el slot deja de listar individualmente y muestra un **bloque colapsado** con:

- Icono de grupo + texto **"Varios (N)"** + los puntos.
- Pedestal idéntico al actual (medalla, color, altura, `={rank}`).
- **Popover** con la lista completa de jugadores empatados al pasar el ratón o tocar/click (escritorio y táctil).

Aplica de forma transparente tanto a la sidebar de `/competicion/` como a las dos columnas (General y Jornada) de la página Rankings, porque ambos consumen `_leaderboard_panel.html` → `_podium_step.html`.

## Reglas funcionales

### Umbral

| Empatados en la plaza | Render del slot |
|-----------------------|-----------------|
| 1 | Sin cambios. Avatar grande + nombre. |
| 2 | Sin cambios. `.podium-slot--multi` actual con dos avatares apilados. |
| **≥ 3** | **Colapsado**. Bloque "Varios (N)" + popover. |

### Contenido del popover

- Encabezado discreto: `Empatados en ={rank}º · {pts} pts`.
- Lista de jugadores: avatar 22px + nombre, una línea cada uno.
- Orden alfabético (ya garantizado upstream por `standings()`).
- Si la lista supera la altura visible (~ 320 px), scroll con `.no-scrollbar`.
- Resaltar al usuario actual con clase `is-me` (color accent) si forma parte del grupo.

### Interacción

- **Hover**: el popover aparece (CSS puro, `:hover` y `:focus-within` sobre el contenedor del slot).
- **Click/tap**: marca `data-open="true"` en el botón → popover permanece abierto aunque se quite el ratón. Útil en móvil/táctil.
- **Click fuera** del popover/botón → cierra (quita `data-open`).
- **Escape**: cierra cualquier popover abierto.
- **Solo un popover abierto a la vez**: si se abre otro, el anterior se cierra.
- Accesibilidad: el bloque es un `<button type="button">` con `aria-haspopup="dialog"` y `aria-expanded` sincronizado con `data-open`. El popover tiene `role="dialog"` y un `aria-label` (`"Empatados en {rank}º"`).

### Marcar al usuario actual desde fuera

- Si `me ∈ rows`, el botón colapsado recibe la clase `is-me` y el texto "Varios (N)" se pinta en color accent, igual que en el caso de un solo avatar.

## Render

### `templates/partials/_podium_step.html`

Estructura nueva:

```django
{% with first=rows.0 multi=rows|length %}
{% if multi < 3 %}
  {# rama actual: avatares apilados (1 o 2 jugadores) #}
{% else %}
  {% with me_in_group=... %}
  <div class="podium-slot podium-slot--{{ rank }} podium-slot--collapsed pop">
    <div class="podium-medal">🥇/🥈/🥉</div>
    <button type="button"
            class="podium-tied{% if me_in_group %} is-me{% endif %}"
            aria-haspopup="dialog"
            aria-expanded="false"
            aria-label="Ver {{ multi }} jugadores empatados en {{ rank }}º">
      <span class="podium-tied__icon" aria-hidden="true">{% icon "users" width=22 height=22 %}</span>
      <span class="podium-tied__label display">Varios ({{ multi }})</span>
      <div class="podium-tied__tooltip" role="dialog" aria-label="Empatados en {{ rank }}º">
        <div class="podium-tied__head eyebrow">Empatados en ={{ rank }}º · {{ first.pts }} pts</div>
        <ul class="podium-tied__list no-scrollbar">
          {% for r in rows %}
            <li class="podium-tied__item{% if me and r.player_id == me.id %} is-me{% endif %}">
              {% with u=users|get_item:r.player_id %}
                {% if u %}{% include "partials/_avatar.html" with u=u size=22 %}{% endif %}
              {% endwith %}
              <span>{% if me and r.player_id == me.id %}Tú{% else %}{{ r.name }}{% endif %}</span>
            </li>
          {% endfor %}
        </ul>
      </div>
    </button>
    <div class="podium-pts mono grad-text">{{ first.pts }}</div>
    <div class="podium-pedestal podium-pedestal--{{ rank }}">
      <span class="podium-rank-number">={{ rank }}</span>
    </div>
  </div>
  {% endwith %}
{% endif %}
{% endwith %}
```

`me_in_group` se calcula con un loop simple sobre `rows` (Django no tiene `any()` pero sí `{% for %}` con `{% if r.player_id == me.id %}{% with hit=True %}…`). Alternativa más limpia: usar `{% if me.id in row_ids %}` donde `row_ids` se construye en una variable temporal con `{% with %}` y `regroup`/`join`. Decisión final durante implementación; lo importante es que aparece `is-me` cuando aplica.

### CSS — `static/css/styles.css`

Nuevas reglas, sin tocar las existentes de `.podium-*`:

```css
.podium-slot--collapsed { position: relative; }

.podium-tied {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 6px;
  background: transparent;
  border: 1px dashed var(--border-hi);
  border-radius: 14px;
  padding: 10px 14px;
  cursor: pointer;
  color: var(--text);
  transition: border-color .15s, background .15s, transform .15s;
}
.podium-tied:hover,
.podium-tied:focus-visible {
  border-color: oklch(from var(--accent) l c h / 0.55);
  background: oklch(from var(--accent) l c h / 0.06);
}
.podium-tied.is-me { color: var(--accent); border-color: oklch(from var(--accent) l c h / 0.55); }

.podium-tied__icon { display: inline-flex; opacity: 0.85; }
.podium-tied__label { font-size: 13px; font-weight: 700; line-height: 1; }

.podium-tied__tooltip {
  position: absolute;
  left: 50%;
  top: calc(100% + 8px);
  transform: translateX(-50%) translateY(-4px);
  min-width: 200px;
  max-width: 260px;
  max-height: 320px;
  overflow: auto;
  padding: 10px 12px;
  border-radius: 12px;
  background: var(--glass-bg);
  backdrop-filter: blur(14px) saturate(140%);
  border: 1px solid var(--border-hi);
  box-shadow: 0 18px 40px -22px oklch(0 0 0 / 0.55);
  opacity: 0;
  visibility: hidden;
  pointer-events: none;
  transition: opacity .15s, transform .15s, visibility .15s;
  z-index: 5;
}
.podium-tied:hover .podium-tied__tooltip,
.podium-tied:focus-within .podium-tied__tooltip,
.podium-tied[data-open="true"] .podium-tied__tooltip {
  opacity: 1;
  visibility: visible;
  pointer-events: auto;
  transform: translateX(-50%) translateY(0);
}

.podium-tied__head { padding-bottom: 6px; border-bottom: 1px solid var(--border); margin-bottom: 6px; }
.podium-tied__list { list-style: none; margin: 0; padding: 0; display: flex; flex-direction: column; gap: 6px; }
.podium-tied__item { display: flex; align-items: center; gap: 8px; font-size: 13px; }
.podium-tied__item.is-me { color: var(--accent); font-weight: 700; }
```

Si `--glass-bg` no existe como variable, usar un valor equivalente al resto de glass (revisar variables en `:root`).

### JS — `static/js/podium-tied.js` (nuevo)

```js
(function () {
  const SEL = '.podium-tied';
  function closeAll(except) {
    document.querySelectorAll(`${SEL}[data-open="true"]`).forEach((el) => {
      if (el !== except) {
        el.removeAttribute('data-open');
        el.setAttribute('aria-expanded', 'false');
      }
    });
  }
  document.addEventListener('click', (e) => {
    const btn = e.target.closest(SEL);
    if (btn) {
      const open = btn.getAttribute('data-open') === 'true';
      closeAll(open ? null : btn);
      if (open) {
        btn.removeAttribute('data-open');
        btn.setAttribute('aria-expanded', 'false');
      } else {
        btn.setAttribute('data-open', 'true');
        btn.setAttribute('aria-expanded', 'true');
      }
      return;
    }
    if (!e.target.closest('.podium-tied__tooltip')) closeAll(null);
  });
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') closeAll(null);
  });
})();
```

Cargado desde `templates/base.html` con `<script defer src="{% static 'js/podium-tied.js' %}"></script>`.

## Archivos afectados

- `templates/partials/_podium_step.html` — rama `multi >= 3` con bloque colapsado.
- `static/css/styles.css` — reglas `.podium-tied*`.
- `static/js/podium-tied.js` (nuevo) — toggle, close-outside, Esc.
- `templates/base.html` — incluir el `<script defer>`.

## Fuera de alcance

- No se cambia la lógica del backend (`standings()`, flags `is_tied`/`is_first_in_tie`). El umbral se decide solo en el template, en base a `rows|length`.
- No se tocan los slots con 1 o 2 jugadores ni el comportamiento de la tabla bajo el podio.
- No se añade un modal real (es popover ligero); para listas extremadamente largas (>50) el scroll del popover es suficiente.
- No se internacionaliza el texto: "Varios" y "Empatados en …" van en español, como el resto del proyecto.

## Tests

El render del bloque colapsado es puramente front-end. Test mínimo en pytest-django (template-only):

- `competition/tests/test_podium_tied.py` (nuevo) o ampliación de tests existentes:
  - `test_podium_renders_collapsed_with_three_or_more_ties` — construye 3 `StandingRow` con misma posición, asserta que el HTML contiene `Varios (3)` y NO contiene cada nombre fuera del popover.
  - `test_podium_two_ties_still_renders_avatars_stacked` — regresión: con 2 sigue mostrándose la lista actual.
  - `test_podium_tooltip_lists_all_tied_names` — el popover contiene todos los nombres.
  - `test_podium_tied_is_me_class_applied_when_user_in_group`.

Verificación manual (skill `verify` o `run`): arrancar el servidor, fixture con ≥3 empatados, comprobar `/competicion/` y `/rankings/?tab=general` (con y sin scope), hover y click, tema claro/oscuro.

## Decisiones tomadas

- **Umbral en 3** (no en 4) para mantener el podio compacto siempre que haya empate triple o mayor.
- **Hover + click** combinados para que la interacción sea inmediata en escritorio y posible en móvil.
- **No se reutiliza `_avatar.html` para el icono de grupo**: se usa `{% icon "users" %}` que ya existe en `static/icons/`.
- **Solo el slot afectado se colapsa**: si 1º muestra 5 empatados y 2º solo 1, el primero va colapsado y el segundo conserva su avatar grande.
- **Mismo template de podio para Competición y Rankings**: el cambio se hace una sola vez en `_podium_step.html`.
