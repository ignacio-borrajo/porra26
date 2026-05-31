# Plan de implementación — PORRA 26

Plan por fases para construir la aplicación de producción a partir del prototipo. Cada fase debe **cerrarse y validarse contra el prototipo** antes de pasar a la siguiente.

---

## Fase 0 — Cimientos del proyecto

**Objetivo:** repositorio funcionando con el sistema de diseño cargado, sin pantallas todavía.

- [ ] Confirmar stack con el responsable (ver `README.md` §3). Por defecto: Next.js (App Router) + TypeScript.
- [ ] Inicializar el proyecto, linter/formateador, estructura de carpetas.
- [ ] **Trasladar los tokens de diseño** desde `design-reference/styles.css` a CSS global (variables `:root`, temas `[data-theme]`). Ver `DESIGN_SPEC.md` §1.
- [ ] Cargar las fuentes: **Sora**, **Inter**, **Geist Mono** (Google Fonts o self-hosted).
- [ ] Implementar las utilidades base: `.glass`, `.btn`/`.btn-primary`/`.btn-ghost`, `.input`, `.field`, `.chip` (+ variantes de estado), `.eyebrow`, `.mono`, `.display`, `.grad-text`, `.bar`, fondo `.ambient` animado, animaciones de entrada (`rise`, `fade`, `pop`, `stagger`).
- [ ] Conmutador de **tema claro/oscuro** funcionando a nivel de `:root` (atributo `data-theme`).

**Hecho cuando:** una página en blanco con un par de botones, un input y un chip se ve idéntica al prototipo en ambos temas.

---

## Fase 1 — Modelo de datos y backend base

**Objetivo:** persistencia y API de lectura/escritura. Ver `DATA_MODEL.md`.

- [ ] Esquema de base de datos: `Player`, `Team`, `Round`, `Match`, `Prediction`, `Settings/Pot`.
- [ ] Seed inicial con selecciones, rondas y partidos del Mundial 2026 (los del prototipo sirven de ejemplo; sustituir por el calendario real cuando exista).
- [ ] Lógica de **estado de partido** derivada de `kickoff` y resultado (no se almacena el estado; se calcula). Ver reglas en `DATA_MODEL.md`.
- [ ] Lógica de **puntuación** (exacto / resultado / fallo) y recálculo al confirmar un resultado oficial.
- [ ] Endpoints/acciones: listar partidos por ronda, guardar pronóstico, confirmar resultado oficial, listar clasificación, CRUD de jugadores.

**Hecho cuando:** se puede crear un pronóstico y, al confirmar un resultado, los puntos se recalculan correctamente (probado con casos: exacto, solo resultado, fallo).

---

## Fase 2 — Autenticación y roles

- [ ] Login con **correo corporativo + contraseña** (`DESIGN_SPEC.md` §3 — pantalla Login).
- [ ] Roles `jugador` / `gestor`; protección de rutas de gestor.
- [ ] Alta de jugador genera **contraseña temporal**; primer acceso obliga a cambiarla.
- [ ] **Sin recuperación automática**: el gestor restablece contraseñas.

**Hecho cuando:** un jugador y un gestor pueden entrar y ven solo lo que les corresponde.

---

## Fase 3 — Pantalla Competición (jugador)

La pantalla principal. Ver `DESIGN_SPEC.md` §4.

- [ ] Cabecera con saludo, posición y *stat pills* (Puntos, Aciertos, Exactos, Racha) con número animado.
- [ ] **Selector de ronda** (chips con contador de partidos).
- [ ] Partidos **agrupados por estado** (Abiertos / En juego / Finalizados), ordenados por fecha.
- [ ] **Tarjeta de partido** (`MatchCard`): banderas, marcador/VS, fecha, cuenta atrás de cierre, estado del pronóstico, puntos ganados. Hover elevado.
- [ ] **Modal de pronóstico** (`ResultModal`): *steppers* para el marcador, cuenta atrás, puntos del partido.
- [ ] **Clasificación lateral** (`Leaderboard`): podio top 3 + tabla con barras, racha y tendencia; resalta al usuario actual.

**Hecho cuando:** un jugador pronostica un partido, ve el toast de confirmación y su pronóstico reflejado en la tarjeta.

---

## Fase 4 — Pantalla Estadísticas

Ver `DESIGN_SPEC.md` §5.

- [ ] 4 KPIs: % de aciertos, vs Media, vs Líder, Percentil.
- [ ] **Gráfico de evolución** (SVG) de posición/puntos partido a partido, con líneas por jugador, etiquetas de identidad al final, tooltip al pasar el cursor, modo Posición/Puntos y switch "Mostrar todos".
- [ ] Panel **"Tú frente al grupo"** (barras comparativas con marcas de media y máximo).
- [ ] **Donut** de distribución de pronósticos (exactos / parciales / fallos).

**Hecho cuando:** el gráfico dibuja las curvas reales del histórico y el tooltip funciona.

> Nota: en el prototipo el histórico se genera de forma determinista (no hay datos reales). En producción debe construirse a partir del histórico real de pronósticos y resultados.

---

## Fase 5 — Panel de gestor

Ver `DESIGN_SPEC.md` §6.

- [ ] **Jugadores:** tabla con buscador, avatar, departamento, puntos, toggle de pago, estado activo/baja, acciones editar/dar de baja. Contadores de activos y pagos.
- [ ] **Modal alta/edición de jugador** (nombre, correo, departamento, rol, pago; aviso de contraseña temporal).
- [ ] **Resultados:** lista por ronda con secciones Pendientes / Próximos / Finalizados; botón Finalizar/Editar que abre el modal de resultado oficial.
- [ ] Al confirmar un resultado oficial, **recalcular puntos** de todos los jugadores y reflejarlo en clasificación y estadísticas.

**Hecho cuando:** un gestor da de alta un jugador, marca un pago e introduce un resultado que actualiza la clasificación.

---

## Fase 6 — Pulido y despliegue

- [ ] Estados de carga, vacío y error en todas las pantallas.
- [ ] Responsivo (el prototipo está pensado para escritorio; definir comportamiento en móvil/tablet con el responsable).
- [ ] Accesibilidad: foco visible, navegación por teclado en modales (ya hay `Esc` en el prototipo), `prefers-reduced-motion` (respetado en el CSS de referencia).
- [ ] Revisión final lado a lado con el prototipo en ambos temas.
- [ ] Despliegue interno + datos reales del calendario del Mundial.

---

## Orden de prioridad si hay que recortar

1. Login + Competición + pronósticos + clasificación (el corazón del producto).
2. Panel de gestor de resultados (sin esto la porra no avanza).
3. Gestión de jugadores y pagos.
4. Estadísticas (gran valor, pero secundario al juego en sí).
