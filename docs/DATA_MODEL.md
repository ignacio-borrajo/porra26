# Modelo de datos y reglas de negocio — PORRA 26

Define las entidades, relaciones y reglas que la aplicación debe implementar. Los datos del prototipo (`design-reference/data.jsx`) son **mock**; sirven de ejemplo de forma y volumen, no como datos reales.

---

## 1. Entidades

### Player (Jugador)
| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | id | PK |
| `name` | string | nombre y apellidos |
| `email` | string | **usuario de acceso**; correo corporativo; único |
| `passwordHash` | string | contraseña (temporal en el alta) |
| `mustChangePassword` | bool | true tras un alta o un reset |
| `avatar` | string | iniciales (derivable del nombre) |
| `dept` | enum | `gestion` \| `financiera` \| `nominas` \| `entorno` \| `galileo` \| `web_movilidad` \| `pesca` \| `aluminio` \| `farmacia` \| `sistemas` \| `sie` \| `atencion_clientes` \| `otros` (opcional) |
| `sede` | enum | `ourense` \| `vigo` \| `asturias` \| `madrid` \| `barcelona` (opcional) |
| `puesto` | enum | `desarrollo` \| `sistemas` \| `consultoria` \| `administracion` \| `practicas` (opcional) |
| `is_jugador` | bool | aparece en clasificaciones y puede pronosticar |
| `is_gestor` | bool | accede a Jugadores, Resultados, Premios y Auditoría |
| `paid` | bool | ha pagado su parte del bote |
| `active` | bool | activo / dado de baja |
| `createdAt` | datetime | |

> **Métricas derivadas** (no se almacenan; se calculan de los pronósticos resueltos): `pts` (puntos), `hits` (aciertos = resultado correcto o exacto), `exact` (marcadores exactos), `streak` (racha de aciertos consecutivos), `trend` (▲/▼/— respecto al partido anterior). En el prototipo vienen precalculadas por comodidad.

### Team (Selección)
| Campo | Tipo | Notas |
|-------|------|-------|
| `code` | string | PK corta (ESP, ARG, FRA…) |
| `name` | string | nombre en español |
| `flag` | string | emoji o referencia a imagen de bandera |

### Round (Ronda)
| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | string | `groups`, `r32`, `r16`, `qf`, `sf`, `final` |
| `label` | string | "Fase de grupos", "Dieciseisavos", … |
| `short` | string | etiqueta corta |
| `points` | int | puntos que vale acertar el marcador exacto en esta ronda |
| `order` | int | orden de la competición |

### Match (Partido)
| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | id | PK |
| `roundId` | fk | → Round |
| `group` | string | grupo ("A".."H") o nombre de fase eliminatoria |
| `homeCode` | fk | → Team |
| `awayCode` | fk | → Team |
| `kickoff` | datetime | hora de saque |
| `resultHome` | int? | marcador oficial local (null si no finalizado) |
| `resultAway` | int? | marcador oficial visitante |
| `liveHome` | int? | marcador en directo (opcional) |
| `liveAway` | int? | marcador en directo (opcional) |
| `finishedAt` | datetime? | cuándo se confirmó el resultado |

> El **estado** del partido (`open/closing/closed/live/done`) **no se almacena**: se calcula (ver §3).

### Prediction (Pronóstico)
| Campo | Tipo | Notas |
|-------|------|-------|
| `id` | id | PK |
| `playerId` | fk | → Player |
| `matchId` | fk | → Match |
| `home` | int | marcador pronosticado local |
| `away` | int | marcador pronosticado visitante |
| `earned` | int? | puntos obtenidos una vez resuelto el partido |
| `updatedAt` | datetime | |

Restricción: **un pronóstico por jugador y partido** (único `playerId+matchId`).

### Pot / Settings (Bote y configuración)
| Campo | Tipo | Notas |
|-------|------|-------|
| `perPlayer` | Decimal | aportación por jugador (prototipo: 10 €) |
| `matchdayWinnerPrize` | Decimal | importe único que se entrega al jugador con más puntos en cada jornada de grupos (1ª, 2ª, 3ª) y en cada ronda eliminatoria salvo la Final: dieciseisavos, octavos, cuartos y semifinales |
| `sedeWinnerPrize` | Decimal | importe único que cobra el mejor jugador de cada sede al cierre del Mundial (excluyendo a los del podio global) |
| `maintenanceCost` | Decimal | gastos de mantenimiento del bote (informativo); se publica en la página de Reglas y queda disponible para descontar en cálculos manuales si hiciera falta |
| `prizes` | Prize[] | filas con `scope="global"` y `position ∈ {1,2,3}` — el podio final |

`total` = `perPlayer × nº de jugadores que pagan`. En el prototipo: 48 jugadores → 480 €.

> El modelo `Prize` solo se usa para el podio final (top 3). Las filas con scope `matchday` o `round` quedaron retiradas en favor de `matchdayWinnerPrize` en PotSettings — un único importe para todas las jornadas/rondas.

> **Premios por jornada y por ronda eliminatoria.** El importe `matchdayWinnerPrize` se entrega:
> - **1 vez por cada jornada de la fase de grupos** (Jornada 1, 2 y 3) — el jugador con más puntos en esa jornada.
> - **1 vez por cada ronda eliminatoria salvo la Final** (dieciseisavos, octavos, cuartos y semifinales) — el jugador con más puntos en esa ronda.
> - **La Final NO genera premio de ronda**: el ganador del Mundial cobra a través del podio final (P1). El servicio `announcements.services.detect_after_match` no crea un anuncio de scope `round` para la Final; solo el anuncio `global` (podio) y, si procede, el `sede`.

> **Premio por ganador de sede.** Al resolverse la Final del Mundial, cada sede premia al mejor de sus jugadores **que no esté entre los tres primeros del podio global**. Si todos los jugadores con puntos de una sede ya están en el top 3 global, esa sede queda **desierta** y no se entrega su premio. En caso de empate dentro de la sede (tras las tres reglas de desempate: pts → exactos → aciertos), los empatados comparten plaza y el `sedeWinnerPrize` se reparte a partes iguales entre ellos. Los jugadores con `sede=""` (sin sede asignada) no compiten por este premio.

---

## 2. Sistema de puntuación

Al resolver un partido (resultado oficial confirmado), por cada pronóstico:

```
si pronóstico.home == resultado.home Y pronóstico.away == resultado.away:
    earned = match.exact_points_applied      // MARCADOR EXACTO
sino si signo(pron.home − pron.away) == signo(res.home − res.away):
    earned = match.partial_points_applied    // ACIERTA SOLO EL RESULTADO (1·X·2)
sino:
    earned = 0                                // FALLO
```

`signo()` distingue victoria local (+), empate (0) y victoria visitante (−). Es la lógica del prototipo (`app.jsx → saveOfficial`) adaptada a la parametrización.

> **Parametrización y congelado.** Tanto los puntos por marcador exacto como los puntos por 1·X·2 son parametrizables por ronda desde "Premios y puntos" (gestor). Al confirmar el resultado de un partido se congelan los valores vigentes en el propio `Match` (`exact_points_applied`, `partial_points_applied`): los cambios posteriores en la tabla de puntos **no afectan** a partidos ya resueltos.

> **Fases finales: solo 90 minutos.** En las rondas eliminatorias el resultado que cuenta para puntuar es el del **tiempo reglamentario (90 minutos)** — se excluyen **prórroga y penaltis**. El gestor introduce el marcador de los 90 minutos como resultado oficial del `Match`.

**Valores por defecto por ronda**:

| Ronda | Exacto | 1·X·2 |
|-------|--------|-------|
| Fase de grupos | **3** | 1 |
| Dieciseisavos | **5** | 1 |
| Octavos | **7** | 1 |
| Cuartos | **10** | 1 |
| Semifinales | por definir | 1 |
| Final | por definir (el mayor) | 1 |

**Métricas que se recalculan** tras resolver: puntos totales, aciertos (`earned > 0`), exactos (`earned == match.exact_points_applied`), racha (aciertos consecutivos por orden de partido), tendencia y posición en la clasificación.

---

## 3. Estados del partido (derivados)

Calculados a partir de `kickoff`, el momento actual, el resultado y la asignación de equipos. Las apuestas de un partido se abren **cuando se conocen los dos equipos** (en grupos todos los partidos están disponibles desde el día 1; en KO cada cruce aparece cuando la ronda anterior lo determina) y se cierran **en el pitido inicial**: `closeAt = kickoff`. Para reducir rezagados se mandan dos recordatorios automáticos antes del saque (2 h y 30 min); no abren ni cierran ventanas, solo avisan.

| Estado | Condición | UI |
|--------|-----------|-----|
| `pending_teams` | `home` o `away` sin asignar todavía (cruce KO pendiente) | tarjeta con placeholders ("1º Grupo A"), no apostable |
| `open` | `now < kickoff` y ambos equipos asignados | apuestas abiertas; "Cierra {hora}" |
| `live` | `kickoff ≤ now` y sin resultado oficial | marcador en directo, halo/punto rojo |
| `done` | resultado oficial confirmado | marcador final + puntos obtenidos |

> Solo se puede crear/editar un pronóstico mientras el partido esté `open` (ambos equipos conocidos y `now < kickoff`).

> **Cruces KO con slots.** Los partidos eliminatorios se modelan con `home_slot`/`away_slot` (`"1A"`, `"2B"`, `"WM73"`…) y un `bracket_code` propio. Al confirmar el resultado oficial de un partido, el servicio `competition.services.bracket.propagate_after_match` rellena automáticamente los `home`/`away` de los siguientes cruces cuyos dos slots queden resolvibles. El gestor puede asignar manualmente cualquier cruce desde "Resultados → Cruce pendiente".

---

## 4. Clasificación (orden)

Jugadores **activos** ordenados por:
1. `pts` descendente.
2. Desempate: más marcadores exactos → más aciertos totales (resultado correcto, incluidos exactos).
3. Si tras esos criterios siguen empatados → **plaza compartida** (ranking denso 1, 1, 2, 2, 3). Dentro del grupo de empate, orden alfabético del nombre **solo a efectos visuales** (no decide plaza).

Solo cuentan jugadores `active = true`. El podio destaca el top 3 (puede tener más de un jugador por plaza si hay empate); el usuario actual va resaltado en toda la tabla.

**Premios económicos.** El importe de cada plaza del podio (P1·P2·P3) se reparte a partes iguales entre quienes la ocupen. El premio por ganador de jornada de grupos o de ronda eliminatoria (dieciseisavos, octavos, cuartos, semifinales — **no la Final**) se decide aplicando las mismas reglas dentro del scope; si tras las tres siguen empatados, los empatados se reparten el importe a partes iguales.

---

## 5. Reglas de autenticación

- Acceso con **correo corporativo + contraseña**.
- **Recuperación por email autoservicio.** Desde el login, el jugador introduce su correo y recibe un enlace firmado con token de **24 h** (uso único: cambiar la contraseña invalida el enlace). Si el correo no existe, no se distingue del caso "existe" (anti-enumeración).
- **Altas con email de bienvenida.** El gestor crea el jugador y, por defecto, marca "Enviar email de bienvenida": el usuario recibe un enlace con token de **7 días** para establecer su propia contraseña sin pasar por una temporal. Si desmarca el check, el flujo legacy de contraseña temporal sigue disponible.
- **Fallback del gestor.** El botón candado en la tabla de jugadores permite fijar la contraseña a mano (caso "no le llega el email"). El botón mail reenvía el welcome/reset según el estado del jugador.
- Dos flags independientes: `is_jugador` (Competición, Estadísticas, Rankings, Mi perfil) e `is_gestor` (todo lo anterior + Jugadores + Resultados + Premios + Auditoría). Pueden coexistir o estar ambos a `false` (usuario administrativo invisible en el juego).

---

## 6. Acciones principales (casos de uso)

| Acción | Rol | Efecto |
|--------|-----|--------|
| Guardar pronóstico | jugador | Crea/actualiza su `Prediction` si el partido está abierto. Toast de confirmación. |
| Confirmar resultado oficial | gestor | Fija `resultHome/Away`, marca `done`, **recalcula `earned`** de todos los pronósticos y la clasificación. |
| Editar resultado | gestor | Permite corregir un resultado ya confirmado y recalcular. |
| Alta de jugador | gestor | Crea `Player` y opcionalmente envía email de bienvenida (token 7d). Si no marca el check, genera contraseña temporal a la vieja usanza. |
| Editar jugador | gestor | Modifica nombre, correo, departamento, rol, pago. |
| Marcar pago | gestor | `paid = true/false`. Afecta al total del bote. |
| Dar de baja / reactivar | gestor | `active = false/true`. Los inactivos no cuentan en la clasificación. |

---

## 7. Datos de ejemplo (en el prototipo)

- **16 selecciones** con banderas (emoji): ESP, ARG, FRA, BRA, ENG, POR, GER, NED, MEX, USA, CAN, JPN, CRO, MAR, URU, BEL.
- **48 jugadores** (12 nombrados + 36 generados) con departamentos, puntos, pagos y estados variados. El usuario de demo es `u_07` ("Tú · Sergio Mas").
- **Partidos** repartidos por rondas con los cinco estados representados, incluido un partido `live` con marcador en directo.
- **Histórico** de posición/puntos partido a partido generado de forma **determinista** solo para alimentar el gráfico de estadísticas — en producción se construye del histórico real.

---

## 8. Rankings por grupo

La página Rankings agrega los puntos de la clasificación general por una de tres dimensiones organizativas (`sede`, `puesto`, `dept`). Cada fila representa un grupo con:

- **Jugadores**: número de usuarios `is_jugador=True, is_active=True` con ese valor en la dimensión.
- **Total**: suma de `earned` de sus pronósticos resueltos.
- **Media**: `Total / Jugadores`. 0 si no hay jugadores.
- **Líder**: el jugador del grupo con más puntos.

Los `choices` sin miembros aparecen igualmente (fila vacía). Una fila final "Sin asignar" agrupa a los jugadores que tengan el campo en blanco. El orden es `media desc → total desc → label asc`.
