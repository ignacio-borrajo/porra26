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

## Fase 7 — Cierre de apuestas → PDF → Teams (vía email)

**Objetivo:** dejar constancia automática en el chat de Teams de la empresa de todas las apuestas realizadas para cada partido, en cuanto se cierra la ventana de pronósticos (kickoff − 2 h).

Specs:
- Original (HTTP-pull): [`docs/superpowers/specs/2026-06-01-cierre-apuestas-teams-design.md`](superpowers/specs/2026-06-01-cierre-apuestas-teams-design.md).
- Final (email-push, sin connectores premium): [`docs/superpowers/specs/2026-06-01-cierre-apuestas-email-design.md`](superpowers/specs/2026-06-01-cierre-apuestas-email-design.md).

**Por qué dos specs**: el primer intento usaba Power Automate sondeando tres endpoints HTTP de Django. Al desplegar descubrimos que el conector HTTP de Power Automate es **premium** (≈ €12/usuario/mes) y la organización no quiere pagar premium. La reescritura usa solo conectores estándar: Django envía un email con el PDF adjunto vía SMTP cada vez que un partido se cierra, y un flow con trigger Outlook + Teams lo publica en el chat.

**Adaptación a Railway**: durante el despliegue migramos de PythonAnywhere a Railway porque PA no permite SMTP saliente sin Hacker plan ($5/mes) y porque Railway nos da SMTP saliente libre, Postgres gestionado y volumen persistente. El SMTP lo provee Resend (free tier, 100 envíos/día) por el puerto 2587.

**Disparo del envío — on-demand, no cron**: el plan original contemplaba un cron `*/10 min` que recorriese matches pendientes. Lo descartamos al replantearlo: con ~104 partidos en todo el Mundial, un cron consume miles de invocaciones para mover 100 emails (mal ratio), y el gestor ya entra a la plataforma a introducir el resultado oficial — pulsar un botón en esa misma pantalla es trivial. El comando `send_pending_closures` se mantiene como herramienta CLI para reenvíos masivos en emergencia. Ver `docs/DEPLOY_RAILWAY.md` §14.

Backend ya implementado (modelo, PDF, endpoint `/pdf` para descarga manual, sección "Estado de envíos") sigue valiendo tal cual; solo cambia el "transporte" del PDF al chat.

- [x] Modelo `BetsClosingReport` (1‑1 con `Match`) + migración.
- [x] Generación del PDF con ReportLab (`build_closing_pdf`).
- [x] UI gestor: botón "📄 PDF" + sección "Estado de envíos a Teams".
- [x] Endpoint `/api/teams/cierres/<id>/pdf` (descarga manual desde la UI).
- [x] Service `send_closure_email(match)` con SMTP + tests.
- [x] Management command `send_pending_closures` (herramienta CLI batch).
- [x] Eliminar endpoint `marcar-enviado` (ya no se consume desde fuera).
- [x] SMTP de Resend desde Railway en producción (puerto 2587).
- [x] Endpoint POST `/api/teams/cierres/<id>/enviar/` + botón Enviar/Reenviar en panel del gestor.
- [ ] `docs/TEAMS_FLOW.md` con el flujo on-demand (Outlook trigger + Teams Post message in chat).
- [ ] Power Automate flow configurado + regla Outlook que filtra `[Porra26]`.

Plan de implementación: [`docs/superpowers/plans/2026-06-01-cierre-apuestas-email.md`](superpowers/plans/2026-06-01-cierre-apuestas-email.md).

**Hecho cuando:** el gestor pulsa "Enviar" tras introducir el resultado oficial y en segundos aparece el PDF en el chat de Teams. Si el envío falla puede reenviar desde la misma pantalla.

---

## Fase 8 — Recordatorios pre-cierre → Teams

**Objetivo:** evitar que se olviden jugadores apostando. Publicar un mensaje en el chat de Teams 2 h y 30 min antes del cierre de cada partido con la lista de quienes aún no han apostado. Además, botón manual del gestor para forzarlo en cualquier momento.

Spec: [`docs/superpowers/specs/2026-06-04-recordatorios-apuestas-design.md`](superpowers/specs/2026-06-04-recordatorios-apuestas-design.md).
Plan: [`docs/superpowers/plans/2026-06-04-recordatorios-apuestas.md`](superpowers/plans/2026-06-04-recordatorios-apuestas.md).

**Arquitectura distinta de Fase 7**: aquí el cron sí hace falta (la naturaleza del aviso es temporal, no on-demand). Pero **fuera de Railway**: GitHub Actions cron `*/15 * * * *` llama un endpoint Bearer del backend. Coste Railway = 0 cuando no hay trabajo.

- [x] Modelo `BetsReminderLog` (kind ∈ {T_MINUS_4H, T_MINUS_2_5H, MANUAL}) + migración.
- [x] Service `get_pending_bettors` y `matches_due_for_kind`.
- [x] Service `send_reminder_email(match, kind)` con `EmailMultiAlternatives` (HTML + plain).
- [x] Management command `send_match_reminders`.
- [x] Endpoints `POST /api/recordatorios/disparar/` (cron) y `POST /api/recordatorios/<id>/enviar/` (botón gestor).
- [x] UI en `/competicion/resultados/`: pill `🟠 N sin apostar` y botón `✉ Recordatorio` por partido upcoming.
- [x] GitHub Actions workflow `.github/workflows/match-reminders.yml`.
- [ ] Power Automate flow nuevo configurado (subject filter `[Porra26 RECORDATORIO]`).
- [ ] Secrets `PORRA26_API_TOKEN` y `PORRA26_BASE_URL` configurados en GitHub.

**Hecho cuando:** un partido entra en ventana T-4h y aparece el aviso en Teams listando los rezagados; el gestor también puede pulsar el botón desde Resultados y disparar uno manual.

---

## Fase 9 — Marcadores en directo + clasificación live

**Objetivo:** publicar una clasificación "en directo" que vaya actualizándose con los marcadores parciales mientras se juegan los partidos.

Spec rápida (decisión cerrada en sesión con Ignacio el 2026-06-10):

- **Productor de datos:** un servicio externo (sports API por confirmar — candidatos: API-Football, Sportradar). Queda fuera del alcance del backend mientras no tengamos credenciales contratadas.
- **Cron:** **cron-job.org** (gratis) golpea cada minuto un endpoint Bearer del backend. Mismo patrón que Fase 8.
- **Tick = `POST /competicion/api/teams/live/tick/`**: el endpoint comprueba en BD si hay algún `Match` en estado `live`. Si no hay ninguno, devuelve `204` en pocos ms — **0 € de coste real en Railway** porque el contenedor web ya está vivo 24/7 y el tick "vacío" consume solo unos ms de CPU.
- **Cuando sí hay partidos live**, el service llama al provider externo, parsea los marcadores parciales y los persiste en `LiveScore` (modelo nuevo, 1-1 con `Match`). **Nunca** toca `result_home`/`result_away` de `Match` — eso sigue siendo exclusivo del gestor para el resultado oficial.
- **Clasificación en directo:** `live_standings()` calcula puntos *hipotéticos* sobre la marcha sumando los puntos de los pronósticos contra `LiveScore` cuando lo hay, y contra `result_home/away` cuando ya hay resultado oficial. **Solo lectura**, los puntos no se congelan hasta que el gestor confirme el resultado oficial.

Por qué descartamos otras opciones (sesión de diseño con Ignacio):
- **Polling desde un worker dedicado de Railway:** sobreingeniería, gasta RAM 24/7 (~2-4 €/mes).
- **Cron nativo de Railway:** cada disparo arranca un contenedor desde cero (~5-10 s cold start). 99% del tiempo desperdiciado.
- **Servidor externo que empuje vía webhook al backend:** arquitectónicamente más limpio pero introduce otro servicio que mantener y otro punto de fallo. Reservado como evolución futura si el polling se queda corto.
- **Cron-job.org haciendo el polling y empujando solo en cambios:** cron-job.org no ejecuta código, solo golpea URLs. Servicios que sí podrían (Cloudflare Workers, GitHub Actions) añadirían un segundo codebase con su propio estado, deploy y secretos. La ganancia es marginal (el tick vacío en Django cuesta ms).

Trabajo de backend:

- [x] Modelo `LiveScore` (1-1 con `Match`) + migración.
- [x] Campo `Match.external_id` (nullable, único) para mapeo contra el API externo.
- [x] Service `competition/services/live_scores.py` con interfaz `LiveScoreProvider` + provider stub para tests.
- [x] Endpoint `POST /competicion/api/teams/live/tick/` con Bearer (mismo `TEAMS_API_TOKEN`).
- [x] Función `live_standings()` para clasificación en directo (lectura).
- [x] Provider real: `FootballDataProvider` contra **football-data.org** (tier gratuito, ~10 req/min, latencia 60-90 s). Activado por `FOOTBALL_DATA_API_KEY` en settings; sin clave cae a `_NoopProvider`.
- [x] Management command `seed_match_external_ids`: casa partidos por fecha + TLA contra `/v4/competitions/WC/matches` y rellena `Match.external_id`.
- [x] Configurar cron-job.org apuntando a `/competicion/api/teams/live/tick/` con `Authorization: Bearer …`.
- [ ] UI: actualizar `CompetitionView` para mostrar marcadores parciales y clasificación live (siguiente PR).

**Hecho cuando:** el endpoint responde 204 sin partidos live, y cuando los hay procesa el tick contra un provider configurable; la función `live_standings()` recalcula clasificación con marcadores parciales sin tocar `result_home/away`.

---

## Orden de prioridad si hay que recortar

1. Login + Competición + pronósticos + clasificación (el corazón del producto).
2. Panel de gestor de resultados (sin esto la porra no avanza).
3. Gestión de jugadores y pagos.
4. Estadísticas (gran valor, pero secundario al juego en sí).
5. Cierre de apuestas → Teams (mejora operativa: auditoría externa; no bloquea el juego).
