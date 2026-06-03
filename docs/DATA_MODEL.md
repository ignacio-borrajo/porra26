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
| `dept` | enum | `nominas` \| `gestion` \| `financiera` \| `pesca` (opcional) |
| `sede` | enum | `ourense` \| `vigo` \| `asturias` \| `madrid` \| `barcelona` \| `latam` (opcional) |
| `puesto` | enum | `desarrollo` \| `sistemas` \| `consultoria` \| `administracion` (opcional) |
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
| `matchdayWinnerPrize` | Decimal | importe único que se entrega al jugador con más puntos en cada jornada de grupos y cada ronda KO |
| `prizes` | Prize[] | filas con `scope="global"` y `position ∈ {1,2,3}` — el podio final |

`total` = `perPlayer × nº de jugadores que pagan`. En el prototipo: 48 jugadores → 480 €.

> El modelo `Prize` solo se usa para el podio final (top 3). Las filas con scope `matchday` o `round` quedaron retiradas en favor de `matchdayWinnerPrize` en PotSettings — un único importe para todas las jornadas/rondas.

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

Calculados a partir de `kickoff`, el momento actual y el resultado. El cierre de apuestas es **2 horas antes del saque**: `closeAt = kickoff − 2h`.

| Estado | Condición | UI |
|--------|-----------|-----|
| `open` | `now < closeAt` | apuestas abiertas; "Cierra {hora}" |
| `closing` | `closeAt − 2h ≤ now < closeAt` (última franja, prototipo usa <2h) | cuenta atrás visible, punto pulsante |
| `closed` | `closeAt ≤ now < kickoff` | "Apuestas cerradas", sin resultado |
| `live` | `kickoff ≤ now` y sin resultado oficial | marcador en directo, halo/punto rojo |
| `done` | resultado oficial confirmado | marcador final + puntos obtenidos |

> En el prototipo el estado viene fijado en los datos mock; en producción **debe derivarse** de los tiempos y del resultado. Solo se puede crear/editar un pronóstico mientras el partido esté `open` o `closing` (es decir, `now < closeAt`).

---

## 4. Clasificación (orden)

Jugadores **activos** ordenados por:
1. `pts` descendente.
2. **Desempate (en este orden):**
   1. Más marcadores exactos.
   2. Más aciertos totales (resultado correcto, incluidos exactos).
   3. Orden alfabético del nombre.

Solo cuentan jugadores `active = true`. El podio destaca el top 3; el usuario actual va resaltado en toda la tabla.

---

## 5. Reglas de autenticación

- Acceso con **correo corporativo + contraseña**.
- **No hay recuperación automática de contraseña.** El restablecimiento lo hace un **gestor**.
- Al **dar de alta** un jugador se genera una **contraseña temporal**; en el primer acceso (`mustChangePassword`) debe cambiarla.
- Dos flags independientes: `is_jugador` (Competición, Estadísticas, Rankings, Mi perfil) e `is_gestor` (todo lo anterior + Jugadores + Resultados + Premios + Auditoría). Pueden coexistir o estar ambos a `false` (usuario administrativo invisible en el juego).

---

## 6. Acciones principales (casos de uso)

| Acción | Rol | Efecto |
|--------|-----|--------|
| Guardar pronóstico | jugador | Crea/actualiza su `Prediction` si el partido está abierto. Toast de confirmación. |
| Confirmar resultado oficial | gestor | Fija `resultHome/Away`, marca `done`, **recalcula `earned`** de todos los pronósticos y la clasificación. |
| Editar resultado | gestor | Permite corregir un resultado ya confirmado y recalcular. |
| Alta de jugador | gestor | Crea `Player` con contraseña temporal. |
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
