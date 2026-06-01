# Página "Reglas" — diseño

**Fecha:** 2026-06-01
**Autor:** Ignacio Borrajo (con Claude)
**Estado:** propuesto, pendiente de plan de implementación

---

## 1. Motivación

Los jugadores y gestores necesitan un único sitio interno donde consultar cómo funciona la porra: cómo se puntúa, cuándo cierran las apuestas, qué pasa con el bote y cómo se accede. Hoy esa información solo vive en `docs/DATA_MODEL.md` (interno) y en cabezas distintas. Queremos una página en la propia app, en español de España, con la misma estética glass del prototipo.

**Compromiso de mantenimiento:** la página de Reglas es contractual cara al usuario. Cualquier cambio en las reglas de negocio (puntos por ronda, ventana de cierre, importes, premios, política de auth, criterio de desempate, estados de partido) debe ir acompañado de la actualización de esta página en el mismo PR.

## 2. Alcance

**Dentro:**
- Una sola página accesible desde la topbar para todo usuario autenticado.
- Mismo contenido para jugador y gestor (decisiones administrativas se aprenden con la UI, no se documentan aquí).
- Contenido: sistema de puntos, cierre 2 h antes del saque, estados de partido, bote y premios, desempate y clasificación, acceso/contraseñas.

**Fuera:**
- Sección específica de gestor con tareas administrativas.
- Acordeones, TOC, buscador.
- Enlace público desde login (se puede valorar más adelante).
- Versionado/changelog de reglas dentro de la página (solo un campo "Última actualización").

## 3. Decisiones tomadas en brainstorming

| Tema | Decisión |
|------|----------|
| Acceso | Nuevo ítem en la topbar (`Reglas`), visible solo a usuarios logueados. |
| Audiencia | Misma página para jugador y gestor. |
| Visual | Rico: tarjetas glass, mini-tarjetas-ejemplo, tabla con chips de color, timeline gráfico. |
| Origen de los números | Lectura del modelo (`Round.points`, `PotSettings.per_player`, `Prize` con `scope='global'`) — la copia es estática, los valores son dinámicos. |
| URL | `/reglas/` |
| App | `core` (transversal). |

## 4. Arquitectura

### 4.1 Backend (Django)

- **App:** `core`.
- **Vista:** `core.views.RulesView` (CBV `TemplateView` con `LoginRequiredMixin`).
- **URL:** crear `core/urls.py` con `path("reglas/", views.RulesView.as_view(), name="rules")` y enchufarlo en `porra26/urls.py` con `path("reglas/", include(("core.urls", "core"), namespace="core"))`. URL final: `/reglas/`, nombre completo: `core:rules`.
- **Context que aporta la vista:**
  - `rounds` — `Round.objects.all()` (ya ordenado por `Meta.ordering = ["order"]`).
  - `pot_per_player` — `PotSettings.load().per_player`. En la plantilla se renderiza con `{{ pot_per_player|floatformat:"-2" }} €` (sin decimales si son `.00`, con dos si los tiene).
  - `pot_prizes` — `Prize.objects.filter(scope="global").order_by("position")`. Tres puestos esperados. Si la consulta devuelve menos, los huecos se renderizan con `—`.
  - `bet_close_hours` — leer la constante única definida en `competition/models.py` (ver §4.3).
  - `rules_updated_at` — constante en `settings.py` (`RULES_UPDATED_AT = date(2026, 6, 1)`), inyectada por la vista. Único campo a actualizar a mano cuando se publique un cambio.
- `pot_total` ya lo inyecta `core.context_processors.app_context`, no hace falta repetirlo.

### 4.2 Frontend (templates + estáticos)

- **Plantilla:** `templates/core/rules.html` extendiendo `base.html`.
- **Topbar:** modificar `templates/partials/_topbar.html` para añadir el enlace entre **Rankings** y **Jugadores** (si gestor) / al final (si no). `is-active` cuando `request.resolver_match.url_name == "rules"`.
- **Icono nuevo:** `static/icons/book.svg` — libro abierto, trazo `currentColor` de 1.7, dimensiones 24×24, mismo aspecto que el resto del set. Se invoca con `{% icon "book" width=17 height=17 %}`.
- **CSS adicional:** ninguno obligatorio si reutilizamos `.glass`, `.eyebrow`, `.chip`, `.grad-text` y los tokens existentes. Si el timeline necesita una clase específica (`.rules-timeline`), añadirla al final de `static/css/styles.css` con scoping claro.

### 4.3 Pequeño refactor: extraer `BET_CLOSE_HOURS`

Hoy la ventana "las apuestas cierran 2 h antes del saque" vive como literal `timedelta(hours=2)` en `competition/models.py` línea 63. Para que la página de Reglas y la lógica real **no puedan divergir**, extraer arriba del módulo:

```python
# competition/models.py
BET_CLOSE_HOURS = 2
```

y reemplazar el literal de la línea 63 por `timedelta(hours=BET_CLOSE_HOURS)`. La vista de Reglas importa `BET_CLOSE_HOURS` y lo pasa en el contexto.

> **No tocar la línea 68.** Ese `timedelta(hours=2)` define una regla distinta (cuánto antes del cierre el partido entra en estado `closing` con cuenta atrás visible). Mismo número hoy, pero distinto concepto: fusionarlos acoplaría dos ventanas independientes.

No hay cambios de esquema (`Round`, `PotSettings`, `Prize` se usan tal cual).

## 5. Estructura visual de la página

Layout: una sola columna centrada, `max-width: 880px`, separación vertical de 24 px entre tarjetas. Idéntica densidad a otras pantallas internas. Stagger en las cards de entrada.

### Hero (sin tarjeta)
- Eyebrow Geist Mono: `MUNDIAL 2026 · REGLAS`.
- H1 Sora 800: *"Cómo funciona la porra"*.
- Subtítulo `--text-dim`, 16 px: *"Todo lo que necesitas saber para jugar — y para no quedarte fuera del bote."*

### Card 1 · "Sistema de puntos"
1. Texto: *"Cada partido te da puntos según lo cerca que estés del resultado."*
2. **Tres mini-tarjetas-ejemplo** en grid `repeat(auto-fit, minmax(220px, 1fr))`, replicando la forma de `MatchCard`:
   - **Marcador exacto** — borde lima. *🇪🇸 España **2 — 1** Argentina 🇦🇷*. Línea inferior: "Tu apuesta: **2-1**" + chip lima `+3 pts · exacto`.
   - **Solo el resultado** — borde cian. *🇪🇸 España **3 — 2** Argentina 🇦🇷*. Línea inferior: "Tu apuesta: **2-1**" + chip cian `+1 pt`.
   - **Fallo** — borde atenuado. *🇪🇸 España **1 — 2** Argentina 🇦🇷*. Línea inferior: "Tu apuesta: **2-1**" + chip gris `0 pts`.
3. **Tabla de puntos por ronda** — `<table>` con dos columnas:
   - Columna 1: `chip` con el color de la ronda + nombre (`{{ round.label }}`).
   - Columna 2: número Sora grande (`{{ round.points }}`) + texto mono *"pts si aciertas el marcador exacto"*.
   - Mapeo de colores (id de ronda → chip): `groups` lima, `r32` cian, `r16` amarillo, `qf` oro, `sf` y `final` con `.grad-text`.
4. Pie en `--text-faint`, Geist Mono 11 px: *"Acertar solo el resultado (1·X·2) siempre vale 1 punto, sea cual sea la ronda."*

### Card 2 · "Cuándo cierran las apuestas"
1. Frase clave con `.grad-text`, Sora 700, 28 px: *"Las apuestas cierran {{ bet_close_hours }} horas antes del saque."*
2. **Timeline horizontal** (SVG inline, 100 % ancho, altura 64 px):
   - Track con degradado de acento.
   - Cinco hitos con `circle` + `chip` debajo: **Abierto** (lima), **Cerrando** (amarillo, halo pulsante en el ejemplo), **Cerrado** (atenuado), **En juego** (rojo, halo pulsante), **Final** (cian).
   - Dos etiquetas verticales sobre la línea: `kickoff − {{ bet_close_hours }}h` y `kickoff`.
   - En viewport `< 920px` el track se reorienta a vertical (CSS `transform: rotate(90deg)` o un segundo SVG con `media query`).
3. **Cuatro mini-MatchCards** debajo del timeline (grid igual que las de la Card 1), cada una marcando un estado distinto: Abierto / Cerrando (con cuenta atrás visible "01:23:45") / En juego (con marcador parcial "1 — 0") / Final ("2 — 1" + chip "+3 pts · exacto").
4. Pie en `--text-faint`: *"Una vez cerradas no podrás crear ni editar tu pronóstico — ni siquiera tras el pitido inicial."*

### Card 3 · "El bote y los premios"
1. Tres `StatPill` apilados horizontalmente:
   - **{{ pot_per_player }} €** · "Aportación por jugador".
   - **{{ pot_total }} €** · "Bote total".
   - **3** · "Premios al final del torneo".
2. Tres `chip` tipo medalla con degradado oro/plata/bronce, mostrando para cada `Prize` global por `position` (1, 2, 3) su `amount` y `label`. Si no hay `Prize` cargados todavía: 3 chips vacíos con `—`.
3. Pie en `--text-faint`: *"El gestor marca quién ha pagado — solo los jugadores con el pago confirmado entran en el bote."*

### Card 4 · "Cómo se decide quién gana"
Lista ordenada compacta, con números Sora a la izquierda y texto a la derecha:
1. **Más puntos.**
2. **Más marcadores exactos.**
3. **Más aciertos** (resultado correcto, incluidos exactos).
4. **Orden alfabético** del nombre.

Mono pequeño debajo: *"Solo cuentan los jugadores activos."*

### Card 5 · "Acceso a la app"
Tres puntos con icono SVG (`mail`, `lock`, `check`):
- **Correo corporativo + contraseña.** Tu usuario es tu email de empresa.
- **Sin recuperación automática.** Si la olvidas, un gestor te la restablece.
- **Primera vez.** Te pediremos cambiar la contraseña temporal antes de seguir.

### Pie de página
Una línea Geist Mono, 12 px, `--text-faint`: *"Última actualización del reglamento: {{ rules_updated_at|date:"j F Y" }}. Si algo cambia te lo comunicaremos por aquí."*

## 6. Responsive

- Breakpoint principal en `920px` (consistente con el resto de la app).
- `<920px`: una sola columna, mini-tarjetas-ejemplo apilan, StatPills apilan, timeline pasa a layout vertical, tabla de rondas mantiene dos columnas pero reduce padding.
- `<560px`: tabla pasa a layout de pares clave-valor apilados.

## 7. Accesibilidad

- Heading hierarchy correcta: H1 en hero, H2 por cada card, H3 si una card lo requiere internamente (no es el caso ahora mismo).
- Iconos decorativos con `aria-hidden="true"`.
- Tabla con `<thead>` y `scope="col"`.
- Timeline SVG con `role="img"` y `<title>` descriptivo del estado.
- Contraste: usar `--text` y `--text-dim` sobre `--surface`; evitar `--text-faint` para texto >14 px.

## 8. Plan de tests

- **Test de vista (`core/tests/test_rules_view.py`):**
  - 302 si anónimo.
  - 200 si autenticado.
  - Renderiza los `points` de cada `Round` presente en el fixture.
  - Renderiza `pot_per_player` y los `Prize` globales en orden.
- **Test de topbar:** el enlace `Reglas` aparece en la navegación.
- **Snapshot mínimo del template:** que el bloque "Sistema de puntos" muestre las tres mini-tarjetas-ejemplo (busca los textos "exacto", "+1 pt", "0 pts").

## 9. Riesgos y notas

- Si en el futuro la ventana de cierre deja de ser fija (2 h) y se vuelve configurable por ronda, hay que ajustar tanto la frase clave como el timeline para que muestren un rango. Por eso `bet_close_hours` ya viaja en el contexto.
- Si se añaden más premios (por jornada o por ronda KO), aquí solo mostramos los `scope="global"`. El resto se documenta en otra parte si se decide hacerlo público.
- El icono `book.svg` es activo nuevo: hay que dibujarlo coherente con el set (mismo grosor de trazo, mismas dimensiones). Si hay dudas estilísticas, usar `grid` como fallback temporal.

## 10. Definición de "hecho"

- [ ] Vista, URL, plantilla y enlace en topbar funcionando con datos reales.
- [ ] Icono `book.svg` añadido a `static/icons/`.
- [ ] Constante `RULES_UPDATED_AT` en `settings.py`.
- [ ] Tests pasan.
- [ ] Verificación visual en `dark` y `light`, en desktop y en ancho 375 px.
- [ ] `docs/DATA_MODEL.md` referenciado en un comentario del template (`{# Mantener sincronizado con docs/DATA_MODEL.md §2, §3, §5 #}`) para recordar la responsabilidad de mantenimiento.
