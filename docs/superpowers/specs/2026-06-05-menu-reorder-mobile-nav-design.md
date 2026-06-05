# Reorden de menú y navegación móvil por rol

Fecha: 2026-06-05

## Resumen

Cambio del topbar (`templates/partials/_topbar.html`) en dos dimensiones:

1. **Reordenar** los enlaces comunes a Competición → Rankings → Estadísticas → Reglas (Rankings sube al 2º puesto, Estadísticas baja al 3º). Aplica a todos los anchos.
2. **Navegación móvil específica por rol** (≤ 860 px):
   - **JUGADOR** (4 secciones) ve una *bottom nav* fija estilo iOS.
   - **GESTOR** (7 secciones) ve un botón hamburguesa que despliega un drawer.

El topbar > 860 px (escritorio/tablet horizontal) no cambia salvo por el orden.

## Motivación

- En móvil el `.topbar-nav` actual scrollea horizontalmente con máscara: el ítem activo puede caer fuera de pantalla y el gestor tiene 7 elementos apretados.
- Para el jugador, el patrón nativo de móvil es una *tab bar* inferior siempre visible.
- Para el gestor, con 7 secciones, una hamburguesa libera espacio del topbar y agrupa toda la nav en un solo gesto.

## Alcance

### Incluido

- Reorden de enlaces en `_topbar.html`.
- Vista móvil JUGADOR: topbar minimal (logo + avatar) + bottom nav fija.
- Vista móvil GESTOR: topbar minimal (logo + avatar + hamburguesa) + drawer.
- Añadir botón "Salir" en `templates/accounts/my_account.html` (jugador móvil pierde el del topbar).
- Nuevo icono `static/icons/menu.svg`.
- JS para el drawer (apertura/cierre/escape, expansión de `topbar-mobile.js`).
- Tests de orden, presencia de bottom nav (jugador) y hamburguesa (gestor).

### Fuera de alcance

- Cambios en escritorio más allá del orden de items.
- Cambios en el resto de pantallas.
- Animaciones nuevas: se reutilizan las curvas `--ease-out` / `--ease-spring` existentes.
- No exponer rol en `<body>` ni con clases CSS — la diferenciación se hace en plantilla con `{% if user.is_gestor %}`.

## Diseño

### 1. Orden del menú

Nuevo orden en `_topbar.html` (sustituye el actual):

1. Competición — `competicion:dashboard`
2. **Rankings** — `stats:rankings` *(antes 3º)*
3. **Estadísticas** — `stats:dashboard` *(antes 2º)*
4. Reglas — `core:rules`
5. *(gestor)* Jugadores — `pot:manage_players`
6. *(gestor)* Resultados — `competicion:manage_results`
7. *(gestor)* Premios y puntos — `pot:prizes`

La lógica de `is-active` no cambia (el `if` usa `ns` y `url_name`, no la posición).

### 2. Topbar móvil JUGADOR (≤ 860 px)

```
┌────────────────────────────────────────┐
│ [logo]                       (avatar) │  ← topbar slim
├────────────────────────────────────────┤
│                                        │
│  contenido de la página                │
│  (main con padding-bottom extra)       │
│                                        │
├────────────────────────────────────────┤
│  ⚽    🏆    📊    📖                  │  ← bottom nav fija
│ Comp. Rank. Stats. Reglas              │
└────────────────────────────────────────┘
```

- Topbar oculta `.topbar-nav`, botón tema (`[data-theme-toggle]`) y formulario de logout. Mantiene `.logo` y `<a>` al perfil con avatar.
- Bottom nav: `position: fixed; bottom: 0; left: 0; right: 0;` con el mismo *glass* (variables `--surface`, `--border`) y `border-top: 1px solid var(--border-hi)`.
- 4 ítems, `display: grid; grid-template-columns: repeat(4, 1fr)`. Cada ítem: icono (20px) arriba + label (11.5px) abajo, ambos centrados.
- Estado activo: color `--accent`, icono coloreado, pequeño "pill" superior de 3 px (linear-gradient `--accent` → `--accent-2`).
- Padding inferior con `env(safe-area-inset-bottom)` para iPhone con barra de gestos.
- `<main>` recibe `padding-bottom: calc(72px + env(safe-area-inset-bottom))` solo en este breakpoint.

### 3. Topbar móvil GESTOR (≤ 860 px)

```
┌────────────────────────────────────────┐
│ [logo]            (avatar) (☰)        │  ← topbar slim + hamburguesa
└────────────────────────────────────────┘
```

Al tocar la hamburguesa, se despliega un drawer slide-down desde justo debajo del topbar:

```
┌────────────────────────────────────────┐
│ [logo]            (avatar) (✕)        │
├────────────────────────────────────────┤
│  ⚽  Competición                       │
│  🏆  Rankings                          │
│  📊  Estadísticas                      │
│  📖  Reglas                            │
│  👥  Jugadores                         │
│  🏁  Resultados                        │
│  💶  Premios y puntos                  │
│ ──────────────────────────             │
│  ☀  Tema          ⎋  Salir            │
└────────────────────────────────────────┘
```

- Drawer: `position: fixed; top: <altura topbar>; left: 0; right: 0;` con `max-height: calc(100dvh - <altura topbar>)` y `overflow-y: auto`. Misma estética glass.
- Lista de 7 enlaces apilada verticalmente, mismo componente `.nav-item` (queda full-width gracias a `display: flex; width: 100%` dentro del drawer).
- Tras el último enlace: separador `border-top: 1px solid var(--border)`, seguido por una fila con dos `btn-icon` (tema y salir) lado a lado.
- Botón hamburguesa: `[data-mobile-menu-toggle]`, alterna icono `menu` ↔ `x` y atributo `aria-expanded`.
- Cierre: clic en backdrop (un overlay `position: fixed; inset: 0` traslúcido por debajo del drawer), clic en un enlace, tecla `Escape`. Foco vuelve al botón hamburguesa.

### 4. Cambios concretos por archivo

| Archivo | Cambio |
|---|---|
| `templates/partials/_topbar.html` | Reordenar enlaces. Envolver `topbar-nav` con clase extra `topbar-nav-desktop` para esconderlo en móvil. Renderizar condicionalmente bottom nav (jugador) o botón + drawer (gestor) cuando `≤ 860 px`. |
| `templates/accounts/my_account.html` | Añadir botón "Salir" debajo de la card de "Tema" (form POST a `accounts:logout`). |
| `static/css/styles.css` | Reglas nuevas: `.bottom-nav`, `.bottom-nav-item`, `.mobile-menu-toggle`, `.mobile-drawer`, `.mobile-drawer-backdrop`. Ajustes en `@media (max-width: 860px)` para esconder `.topbar-nav-desktop`, botones de tema/salir en el topbar y dar `padding-bottom` al `<main>`. |
| `static/icons/menu.svg` | Nuevo icono (3 líneas horizontales, mismo trazo que el resto). |
| `static/js/topbar-mobile.js` | Añadir manejo del drawer: toggle, backdrop, Escape, atributos ARIA. La función actual de máscara de scroll queda fuera del flujo móvil (la nav desktop ya no aparece en móvil), pero la dejamos por si en tablet la barra todavía se ve. |

### 5. Accesibilidad

- Bottom nav: `<nav aria-label="Navegación móvil">` con `<a>` que tienen `aria-current="page"` cuando están activos.
- Hamburguesa: `<button aria-expanded="false" aria-controls="mobile-drawer">` que pasa a `aria-expanded="true"` al abrir; el drawer recibe `role="dialog" aria-modal="true" aria-label="Menú"`.
- Cierre con Escape y devolución del foco al botón hamburguesa.
- `tab-index` y foco trampa básico dentro del drawer (focus management mínimo: primer link recibe foco al abrir).

### 6. Tests

- `core/tests/test_topbar.py`:
  - Test nuevo: orden esperado en el HTML para `competicion:dashboard` (jugador).
  - Test nuevo: para jugador existe `data-bottom-nav` en el HTML y no existe `data-mobile-menu-toggle`.
  - Test nuevo: para gestor existe `data-mobile-menu-toggle` y `data-mobile-drawer`, y no existe `data-bottom-nav`.
- `pot/tests/test_topbar_premios_link.py`: sigue pasando (el href y `is-active` no cambian).
- `accounts/tests/test_my_account.py`: añadir test que verifique presencia del form de logout en `my_account.html`.

### 7. Riesgos / consideraciones

- `topbar-mobile.js` actualmente busca `.topbar-nav` y aplica máscara; al ocultar `topbar-nav` en móvil esa lógica deja de aplicar en móvil pero sigue válida en tablet horizontal. No es un riesgo, solo una nota.
- El drawer se monta dentro del `<header>` actual o como sibling. Lo más limpio: dentro del header, así `position: fixed` cuelga del topbar sticky correctamente sin desfase.
- En PWA standalone iOS, `env(safe-area-inset-bottom)` debe respetarse para no solapar con la barra de gestos.

## Criterios de aceptación

- ✅ En escritorio (> 860 px), el topbar muestra los enlaces en el orden: Competición · Rankings · Estadísticas · Reglas · *(gestor)* Jugadores · Resultados · Premios y puntos.
- ✅ En móvil ≤ 860 px, **jugador**: topbar contiene solo logo + avatar, hay una bottom nav fija con 4 ítems en el orden anterior (sin los del gestor), el ítem activo está marcado.
- ✅ En móvil ≤ 860 px, **gestor**: topbar contiene logo + avatar + botón hamburguesa, al pulsar se abre un drawer con los 7 enlaces + tema + salir; cierra con backdrop / link / Escape.
- ✅ "Mi cuenta" tiene un botón "Salir" además del de Tema.
- ✅ Tests de orden y presencia de cada estructura pasan.
- ✅ `is-active` sigue marcando el enlace correcto en cada pantalla.
