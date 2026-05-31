# Especificación de diseño — PORRA 26

Valores exactos extraídos del prototipo. **Fuente de verdad última:** `design-reference/styles.css` y los `*.jsx`. Este documento los resume para implementarlos en producción.

---

## 1. Tokens de diseño

### 1.1 Color — acentos multicolor (fijos en ambos temas)
Definidos en `oklch`. Identidad inspirada en el Mundial 2026.

| Token | Valor | Uso |
|-------|-------|-----|
| `--c-pink` | `oklch(0.68 0.24 5)` | acento rosa/magenta |
| `--c-cyan` | `oklch(0.78 0.15 210)` | acento cian |
| `--c-lime` | `oklch(0.85 0.21 130)` | éxito / abierto / exactos |
| `--c-yellow` | `oklch(0.86 0.18 95)` | aviso / racha / cuenta atrás |
| `--c-gold` | `oklch(0.80 0.13 85)` | trofeo / bote / 1er puesto |
| `--c-blue` | `oklch(0.62 0.20 250)` | acento azul |
| `--c-green` | `oklch(0.70 0.18 150)` | secundario |
| `--c-red` | `oklch(0.63 0.23 25)` | en juego / baja / tendencia abajo |

**Acento primario configurable** (`--accent`, `--accent-2`) — pares por defecto seleccionables:
`blue→[blue,cyan]`, `pink→[pink,cyan]`, `cyan→[cyan,lime]`, `lime→[lime,yellow]`, `yellow→[yellow,pink]`. Por defecto el prototipo arranca con acento **blue**.

### 1.2 Color — superficies por tema

**Tema oscuro (por defecto):**
```
--bg-0:      oklch(0.16 0.02 275)
--bg-1:      oklch(0.20 0.025 275)
--surface:       oklch(0.24 0.025 275 / 0.55)
--surface-solid: oklch(0.22 0.025 275)
--surface-hi:    oklch(0.30 0.03 275 / 0.7)
--border:        oklch(0.95 0.02 275 / 0.10)
--border-hi:     oklch(0.95 0.02 275 / 0.22)
--text:          oklch(0.97 0.01 275)
--text-dim:      oklch(0.78 0.02 275)
--text-faint:    oklch(0.62 0.02 275)
--glass-blur: 22px
```

**Tema claro:**
```
--bg-0:      oklch(0.97 0.012 270)
--bg-1:      oklch(0.99 0.008 270)
--surface:       oklch(1 0 0 / 0.7)
--surface-solid: oklch(1 0 0)
--surface-hi:    oklch(1 0 0 / 0.95)
--border:        oklch(0.25 0.02 275 / 0.10)
--border-hi:     oklch(0.25 0.02 275 / 0.18)
--text:          oklch(0.22 0.03 275)
--text-dim:      oklch(0.42 0.03 275)
--text-faint:    oklch(0.58 0.025 275)
--glass-blur: 18px
```
El tema se aplica con el atributo `data-theme="dark|light"` en `:root`.

### 1.3 Tipografía
- **Display / títulos:** `Sora` (400–800). Peso 800 para títulos, 700 para subtítulos/botones. `letter-spacing: -0.02em` a `-0.03em`.
- **Texto / UI:** `Inter` (400–700).
- **Mono / datos / etiquetas:** `Geist Mono` (400–600).
- `.eyebrow`: Geist Mono, mayúsculas, `letter-spacing: 0.18em`, `font-size: 11px`, color `--text-faint`.
- `.grad-text`: relleno con degradado `linear-gradient(100deg, pink, yellow 40%, lime 65%, cyan)` recortado al texto.

### 1.4 Radios, sombras, animación
```
--r-sm: 10px   --r-md: 16px   --r-lg: 24px   --r-xl: 32px
--shadow-glow (oscuro): 0 0 0 1px rgba(blanco/.06), 0 24px 60px -20px (azul muy oscuro/.7)
--ease-out:    cubic-bezier(0.16, 1, 0.3, 1)
--ease-spring: cubic-bezier(0.34, 1.56, 0.64, 1)
--anim: multiplicador 0–1 de intensidad de animaciones (configurable)
```
Animaciones de entrada: `rise` (sube + fade), `fade`, `pop` (escala con spring). `.stagger > *` aplica retardos incrementales de 0.04 s. Respeta `@media (prefers-reduced-motion: reduce)`.

### 1.5 Fondo ambiente
`.ambient` fijo a pantalla completa: cuatro radiales difuminados (rosa, cian, lima, amarillo) con animación lenta `drift` (deriva + leve rotación), más líneas verticales muy sutiles tipo campo. En tema claro baja la opacidad al 55%.

---

## 2. Componentes base

| Componente | Especificación |
|------------|----------------|
| **`.glass`** | fondo `--surface`, `backdrop-filter: blur(var(--glass-blur)) saturate(1.3)`, borde `--border`, sombra `--shadow-glow`. |
| **`.btn-primary`** | Sora 700, degradado `135deg, --accent → --accent-2`, radio 10px, padding `12×20`, sombra de color; hover sube `-2px` y aumenta el glow; active escala 0.98. |
| **`.btn-ghost`** | fondo `--surface-hi`, borde `--border-hi`; hover borde de acento. Usado también como botón-icono cuadrado (38–40px, radio 11–12px). |
| **`.input`** | fondo `--surface-hi`, borde `--border-hi`, radio 10px, padding `13×15`; focus: borde de acento + halo `0 0 0 3px accent/.18`. Iconos a la izquierda con `padding-left: 42px`. |
| **`.chip`** | Geist Mono 11px, pill, borde `--border-hi`. Variantes: `chip-open` (lima), `chip-live` (rojo), `chip-done` (cian), `chip-closed` (atenuado). |
| **`.bar`** | barra de progreso 5–7px, relleno degradado de acento con glow; transición de `width` 1.1s. |
| **Avatar** | cuadrado redondeado (radio 12px), iniciales, degradado por hash del id; `ring` opcional (anillo de acento) para el usuario actual. |
| **Toggle** | interruptor 44×25, on = degradado lima→cian con glow; perilla blanca que se desplaza con spring. |
| **Countdown** | cuenta atrás `HH:MM:SS` en mono; se vuelve amarilla si quedan < 1 h. |
| **AnimNum** | número que cuenta hacia arriba al montar (easing cúbico, ~900 ms). |
| **Toast** | abajo-centro, `.glass`, icono check en cuadro degradado lima→cian; auto-cierre a 2.6 s. |
| **Logo** | wordmark "PORRA26" (Sora 800), marca cuadrada con degradado cónico multicolor y "26" dentro. |

### Iconos
Set propio de **trazo simple** (SVG `stroke`, `stroke-width` 1.7–1.8): trophy, ball, cal, clock, users, edit, check, x, lock, mail, flame, up, down, euro, whistle, plus, logout, sun, moon, grid, chart, target, scale, gauge. No usar librerías de iconos con otro estilo; replicar estos o equivalentes de trazo fino. Definidos en `design-reference/shared.jsx` (objeto `I`).

---

## 3. Pantalla · Login

Layout split a pantalla completa. **Dos variantes** (configurable):
- **Variante A (clásica):** cabecera con logo + chip "Edición interna". Cuerpo en dos columnas: izquierda un panel `.glass` con el formulario (máx. 460px); derecha la info del torneo (título "El torneo ya está en juego" + `LoginInfo`).
- **Variante B (inmersiva):** dos columnas; izquierda panel sólido con logo arriba, formulario centrado y pie mono; derecha zona con hero ("Pronostica. Suma puntos. Gana el bote.") sobre el `LoginInfo`.

**Formulario (`LoginForm`):** título "Bienvenido de nuevo", campos Correo (icono mail) y Contraseña (icono lock), selector de rol demo (Jugador/Gestor como segmented control degradado), botón primario "Entrar al torneo", nota de "¿Olvidaste tu contraseña? Pídele a un administrador que la restablezca." Al enviar, breve estado "Entrando…" (~650 ms).

**Info lateral (`LoginInfo`):** tira de 3 métricas (Bote `480 €`, Jugadores `48`, 1er premio `240 €`); tarjeta `.glass` "Próximos partidos" (3 minicards con banderas, fecha, estado abierto/cerrado); tarjeta `.glass` "Top 5 · clasificación" (filas con posición, avatar, nombre, puntos; 1º resaltado en oro).

---

## 4. Pantalla · Competición (jugador)

**TopBar** (en `.glass`, full-width): logo · navegación (Competición, Estadísticas; + Jugadores y Resultados si gestor) · a la derecha chip "Bote 480 €" (oro), botón tema (sol/luna), avatar + nombre + rol + botón salir.

**Layout principal:** grid 2 columnas `1fr / 360–420px` (la clasificación lateral puede ocultarse → 1 columna).

**Columna principal** (scroll propio):
- **Hero:** eyebrow "MUNDIAL 2026", título "Hola, Sergio", chip "Posición #N" (oro). Fila de 4 `StatPill` (icono en cuadro de color + número grande Sora + etiqueta): Puntos (oro, `AnimNum`), Aciertos (cian), Exactos (lima), Racha (amarillo).
- **`RoundSelector`:** chips en barra `.glass`; chip activo con degradado de acento; cada uno muestra contador de partidos en mono. Rondas: Fase de grupos, Dieciseisavos, Octavos, Cuartos, Semifinales, Final.
- **Partidos** agrupados en secciones por estado — **Abiertos** (lima), **En Juego** (rojo), **Finalizados** (atenuado) — cada sección con eyebrow + contador + línea divisoria; rejilla `repeat(auto-fill, minmax(280px, 1fr))` de `MatchCard`. Estado vacío con icono calendario si la ronda no tiene partidos.

**`MatchCard`** (`.glass`, radio 20, botón clicable solo si editable): fila grupo + chip de estado (con punto pulsante si live/closing); fila de equipos con banderas grandes (38px) y nombres, en el centro marcador (`ScoreBubble`) si done/live o "VS"; pie con fecha (icono cal, mono); línea de acción según estado: cuenta atrás si closing, "Cierra …" si open, "Tu pronóstico h-a" si done, "Apuestas cerradas" si closed; a la derecha chip de resultado (`+N pts` / "0 pts" / "· exacto"), o "Apostaste h-a" (lima) si ya hay pronóstico, o "Pronosticar" (acento) si editable. Hover: eleva `-4px`, borde de acento, sombra de color. Si live, halo rojo superior.

**`ResultModal` (modo pronóstico):** overlay con blur. Título "¿Cómo va a quedar?" + nombres. Dos `Stepper` (bandera 46px + nombre + botones −/+ y caja de marcador grande 64px) separados por ":". Línea de cuenta atrás/edición + chip "+N pts". Botones Cancelar (ghost) / "Guardar pronóstico" (primary). Cierra con `Esc` o clic fuera.

**Clasificación lateral (`Leaderboard`, variante `full`):** ver §7.

---

## 5. Pantalla · Estadísticas

Cabecera: eyebrow "MUNDIAL 2026 · ESTADÍSTICAS", título "Tu rendimiento", chip "Posición #N de M".

**4 KPIs** (`.glass`, icono en cuadro de color, número grande Sora, subtexto):
- **% de aciertos** (cian) — "X de N partidos · E exactos".
- **vs Media** (lima si ≥0, rojo si <0) — "+X" frente a la media del grupo.
- **vs Líder** (oro) — diferencia con el primero.
- **Percentil** (acento) — "Top X%" + "mejor que K jugadores · mejor #pos".

**Layout:** grid `4fr / 1fr` (apila en <920px).

**`RankChart`** (columna ancha, SVG a medida): líneas de evolución por jugador a lo largo de los partidos disputados. Modos **Posición** (eje invertido, #1 arriba) / **Puntos** (segmented control). Switch **"Mostrar todos"** (pasa del top 10 + tú a toda la plantilla, con scroll interno sin barras). Cada línea termina a la derecha con la **identidad del jugador**: avatar (anillo si eres tú), número de posición, nombre/apellidos, con anti-solape vertical. Línea del usuario más gruesa, con glow de acento. **Tooltip** al pasar el cursor: lista ordenada de jugadores en ese partido con su valor; acotada a 12 con "+N más" en modo todos. Leyenda/selector de jugadores como chips de color toggleables (oculto en modo todos).

**`ComparePanel` ("Tú frente al grupo"):** 3 barras comparativas (Puntos, Aciertos, Exactos) con relleno de acento + marcas verticales de Media (gris) y Máximo (oro). Leyenda al pie.

**`DonutCard` ("Tus pronósticos"):** donut SVG con 3 segmentos — Exactos (lima), Aciertos parciales (cian), Fallos (gris) — separados por pequeños huecos; centro con % de aciertos grande (cian). Lista debajo con conteo y porcentaje por segmento.

---

## 6. Panel de gestor

### 6.1 Jugadores (`ManagePlayers`)
Cabecera: eyebrow "Panel de gestor", título "Jugadores", chips "N activos" y "P/T pagado", botón primary "Nuevo jugador" (icono +). Buscador (icono users, máx 360px) por nombre o correo.

Tabla en tarjeta `.glass`: columnas **Jugador · Departamento · Puntos · Pago · Estado · (acciones)** (`grid-template-columns: 2.4fr 1fr 0.8fr 1fr 1.1fr 70px`). Cada fila: avatar (+ chip "gestor" si aplica), nombre y correo (mono), departamento, puntos (Sora), `Toggle` de pago + etiqueta Pagado/Pendiente, chip Activo/Baja (lima/atenuado con punto), acciones editar (ghost) y dar de baja/reactivar (x roja / check lima). Filas inactivas a opacidad 0.5; hover resalta fondo.

**`PlayerModal`:** título "Nuevo jugador" o el nombre. Campos: Nombre completo, Correo (usuario), Departamento, Rol (segmented Jugador/Gestor). Si es alta, aviso mono: contraseña temporal a cambiar, restablecida por gestor. `Toggle` "Ha realizado el pago del bote (10 €)". Botones Cancelar / "Crear jugador" o "Guardar cambios".

### 6.2 Resultados (`ManageResults`)
Cabecera: eyebrow "Panel de gestor", título "Resultados oficiales", descripción ("Introduce el marcador final… al confirmar se recalculan los puntos"). `RoundSelector`. Tres secciones: **Pendientes de finalizar** (con punto pulsante amarillo), **Próximos**, **Finalizados**. Cada fila (`.glass`, grid `auto 1fr auto auto`): grupo, equipos con banderas y marcador (o "vs"), chip de estado, botón "Finalizar" (primary) o "Editar" (ghost).

**`ResultModal` (modo oficial):** igual estructura que el de pronóstico pero título "Marcar resultado final", eyebrow "Resultado oficial", botón "Confirmar y finalizar" (icono whistle). Sin cuenta atrás ni chip de puntos.

---

## 7. Clasificación (`Leaderboard`)

Cabecera: icono trofeo (oro) + título "Clasificación" + chip "Tú · #N".

- **Variante `full`:** **Podio** top 3 (orden visual 2-1-3, alturas 84/112/62, medallas 🥇🥈🥉, avatares, puntos con `AnimNum`, columnas con degradado por color de puesto) + cabecera de tabla (#, Jugador, Pts) + lista del 4º en adelante.
- **Variante `list`:** solo la lista compacta (todos).

**`LeaderRow`:** grid `26px 1fr auto` — posición (mono), avatar (+ anillo si eres tú) + nombre (+ chip racha 🔥 si racha ≥3) + barra de progreso proporcional al líder, y a la derecha aciertos·exactos (mono), icono de tendencia (▲ lima / ▼ rojo / — gris) y puntos (Sora). La fila del usuario actual va resaltada con fondo de acento, borde y glow.

---

## 8. Configurables (del prototipo)

El prototipo expone estos ajustes; en producción decide cuáles son fijos y cuáles configurables por el gestor:
- **theme:** dark / light.
- **accent:** blue / pink / cyan / lime / yellow (par de acento primario).
- **loginVariant:** A / B.
- **leaderboard:** full / list / hidden (en la pantalla Competición).
- **anim:** intensidad de animación 0–10.
