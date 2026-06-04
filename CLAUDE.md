# CLAUDE.md — Contexto del proyecto PORRA 26

> Este archivo se inyecta automáticamente en cada sesión de Claude Code. Léelo entero antes de generar o modificar código.

## El proyecto en una frase

Aplicación web **interna de empresa** para una porra (quiniela) del **Mundial FIFA 2026**: los empleados pronostican marcadores, suman puntos por aciertos y compiten por un bote común. Roles: **jugador** y **gestor**.

## Principios de trabajo (no negociables)

1. **Fidelidad al diseño primero.** El prototipo en `design-reference/` es alta fidelidad. Reprodúcelo con fidelidad de píxel: mismos colores, tipografías, espaciados, radios, sombras y animaciones. Ante cualquier duda de aspecto, abre `design-reference/PORRA 26.html` y consulta `design-reference/styles.css` — es la fuente de verdad visual.
2. **El prototipo NO es el código de producción.** Está hecho con React vía Babel en el navegador y datos *mock* en memoria. No lo copies tal cual: reimplementa en el stack de producción acordado, con sus patrones (componentes tipados, estado real, backend, base de datos).
3. **Confirma el stack antes de generar.** Lee `README.md` §3. Si no hay stack decidido, propón Next.js + TypeScript + Prisma/PostgreSQL + Auth.js y espera confirmación.
4. **Avanza por fases.** Sigue `docs/PLAN.md`. No generes toda la app de golpe; cierra y valida cada fase contra el prototipo.
5. **Respeta el modelo de datos y las reglas de negocio** de `docs/DATA_MODEL.md` (sistema de puntos, cierre de apuestas, estados de partido, etc.).
6. **Idioma:** toda la interfaz y los textos van en **español de España**. Copia los textos exactos del prototipo.

## Reglas de negocio clave (resumen — detalle en docs/DATA_MODEL.md)

- **Puntuación:** marcador exacto → puntos del partido (parametrizable por ronda); acertar solo el resultado (1/X/2) → puntos parciales (parametrizable por ronda, default 1); fallar → 0. Los puntos se congelan en cada `Match` al resolverse, así los cambios solo aplican a partidos sin resolver.
- **Puntos por ronda (defaults):** Grupos 3 · Dieciseisavos 5 · Octavos 7 · Cuartos 10 (escala creciente; semis/final por definir, mantén la progresión). 1·X·2 = 1 en todas las rondas. El gestor puede ajustarlos desde "Premios y puntos".
- **Cierre de apuestas:** 2 horas antes del saque (`kickoff − 2h`). Después no se puede crear ni editar el pronóstico.
- **Estados de partido:** `open` → `closing` (<2 h, cuenta atrás) → `closed` → `live` → `done`.
- **Bote:** aportación por jugador (10 €), premios para el top 3. El gestor marca quién ha pagado.
- **Auth:** correo corporativo + contraseña. **Recuperación por email autoservicio** (token 24h). Altas pueden enviar **email de bienvenida** (token 7d) para que el jugador establezca su contraseña, o quedar con contraseña fijada por el gestor.

## Estructura de pantallas

| Pantalla | Rol | Resumen |
|----------|-----|---------|
| Login | público | Acceso con correo de empresa. Panel lateral con bote, próximos partidos y top 5. |
| Competición | jugador + gestor | Selector de ronda, partidos agrupados por estado, clasificación lateral. |
| Estadísticas | jugador + gestor | KPIs, gráfico de evolución de posición/puntos, comparativa vs grupo, donut de aciertos. |
| Jugadores | solo gestor | Tabla de jugadores, alta/edición, toggles de pago y estado. |
| Resultados | solo gestor | Introducir marcadores oficiales; al confirmar recalcula puntos. |

## Lo que NO debes hacer

- No inventes pantallas, secciones, campos ni "contenido de relleno" que no estén en el prototipo o en `docs/`. Si crees que falta algo, pregunta.
- No cambies la identidad visual (paleta multicolor Mundial, tipografías Sora/Inter/Geist Mono, efecto *glass*, tema claro/oscuro) sin que se haya actualizado el prototipo.
- No introduzcas dependencias pesadas de UI (librerías de componentes con su propio look) que rompan la estética: los componentes son a medida.

## Archivos de referencia

- `README.md` — visión general y arranque.
- `docs/PLAN.md` — plan por fases.
- `docs/DESIGN_SPEC.md` — tokens y especificación de cada pantalla/componente.
- `docs/DATA_MODEL.md` — entidades, relaciones y reglas.
- `docs/WORKFLOW.md` — cómo aplicar nuevas iteraciones de diseño.
- `design-reference/` — el prototipo (abrir `PORRA 26.html`).
