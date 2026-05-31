# PORRA 26 — Diseño de implementación v1

> Fecha: 2026-05-31
> Autor: brainstorming asistido por Claude Code
> Estado: aprobado por el responsable, pendiente de plan de implementación
> Reemplaza/complementa: `docs/PLAN.md` (que queda como guía narrativa por fases)

Este documento fija las decisiones de diseño para la versión 1 de PORRA 26: la app web interna de empresa para una porra del Mundial FIFA 2026. Está pensado para ser la **única fuente de verdad** desde la que se deriva el plan de implementación.

Las decisiones se han tomado en una sesión de brainstorming sobre la base del paquete de handoff existente (`README.md`, `CLAUDE.md`, `docs/`, `design-reference/`). Las reglas visuales y de negocio que ya quedaban fijadas en ese paquete (sistema de puntos, cierre a `kickoff - 2h`, identidad visual, etc.) se mantienen; este documento sólo añade las decisiones nuevas y las concreta para el stack elegido.

---

## 1. Stack, arquitectura y estructura del repo

### Stack productivo
- **Backend:** Python 3.12 + Django 5.x.
- **Base de datos:** MySQL en producción (la que ofrece PythonAnywhere free). **SQLite** para desarrollo local y para los tests.
- **Capa de UI:** Django templates puros + CSS estático + JS vanilla mínimo. **Sin SPA**, sin HTMX, sin frameworks JS, sin bundler.
- **Autenticación:** Django auth nativo con un `User` custom (email como `USERNAME_FIELD`) + validador de dominio corporativo configurable.
- **Hosting:** PythonAnywhere (plan free) — WSGI directo, MySQL incluida en el panel, dominio `*.pythonanywhere.com`.
- **Tests:** `pytest` + `pytest-django` + `factory-boy` + `freezegun`.
- **Lint/format:** `ruff` + `ruff format`.

### Por qué este stack
- Lo decisivo es la **regla de "sin SMTP saliente"** del free de PythonAnywhere: descarta cualquier flujo basado en emails y nos obliga a entregar contraseñas temporales por pantalla. Esa restricción está internalizada en todo el diseño.
- **0 € de hosting** era requisito explícito del responsable. PythonAnywhere free es hoy la opción Django más estable a 0 €: disco persistente, MySQL incluida, sin "cold starts".
- Django templates puros simplifican el despliegue (un único servicio WSGI, sin build de front) a cambio de re-escribir las interacciones del prototipo React en JS vanilla. Esa re-escritura es manejable porque el grueso del prototipo es CSS (que se copia 1:1) y las partes JS son aisladas (modales, animaciones de números, gráfico SVG, cuenta atrás, toasts).
- **MySQL** porque es la BD relacional incluida en el free de PythonAnywhere. SQLite no encaja porque, aunque el free permite disco persistente, el panel está orientado a apuntar Django a MySQL.

### Estructura del repo

```
apuestas-interna/
├── manage.py
├── pyproject.toml              # deps con uv/pip-tools, ruff, pytest config
├── porra26/                    # project Django
│   ├── settings/
│   │   ├── base.py
│   │   ├── dev.py              # SQLite, DEBUG=True
│   │   ├── test.py             # SQLite in-memory
│   │   └── prod.py             # MySQL, seguridad endurecida
│   ├── urls.py
│   └── wsgi.py
├── accounts/                   # User custom, login, change-password, audit
├── competition/                # Team, Round, Match, Prediction + scoring
├── pot/                        # PotSettings, Prize, Payment, gestión jugadores/premios
├── stats/                      # vistas y servicios de estadísticas
├── core/                       # context_processors, mixins, templatetags compartidos
├── templates/                  # plantillas centralizadas (no por app)
│   ├── base.html
│   ├── partials/
│   └── <app>/...
├── static/
│   ├── css/styles.css          # copia adaptada de design-reference/styles.css
│   ├── js/                     # theme.js, toast.js, anim-num.js, countdown.js,
│   │                           # modal.js, predict-stepper.js, rank-chart.js
│   └── icons/                  # 24 .svg de stroke fino del prototipo
├── fixtures/
│   ├── teams.json              # selecciones del Mundial 2026
│   ├── rounds.json             # 6 rondas con sus puntos
│   └── world_cup_2026.json     # ~104 partidos
├── design-reference/           # prototipo, FUENTE DE VERDAD VISUAL — no se toca
├── docs/                       # PLAN.md, DESIGN_SPEC.md, DATA_MODEL.md, WORKFLOW.md,
│   ├── DEPLOY.md               # paso a paso de despliegue en PythonAnywhere
│   ├── SYNC_DESIGN.md          # ciclo "sincroniza el diseño"
│   ├── RUNBOOK.md              # cómo recuperarse de incidentes
│   └── superpowers/specs/
│       └── 2026-05-31-porra26-design.md   # este documento
└── tests/                      # tests integrados (los unitarios viven junto al servicio)
```

### Estructura de apps Django: por dominio

Se descartó la app monolítica y la híbrida en favor de separación por dominio, porque la app está pensada para vivir varias ediciones del torneo:

- `accounts/` — `User`, login, cambio de contraseña, auditoría.
- `competition/` — `Team`, `Round`, `Match`, `Prediction`, servicios de scoring/status/standings/streak.
- `pot/` — `PotSettings`, `Prize`, `Payment`, vistas de gestión de jugadores y premios.
- `stats/` — agregaciones para la pantalla de estadísticas (KPIs, donut, historial).

---

## 2. Modelo de datos

Adaptación del `DATA_MODEL.md` original al stack elegido, **fusionando `User` y `Player`** (en el prototipo eran dos cosas separadas porque no había auth real; aquí no aporta separarlos) y **añadiendo el sistema de premios por jornada** que se ha decidido en esta sesión.

### `accounts.User`
```python
class User(AbstractBaseUser, PermissionsMixin):
    email = EmailField(unique=True)              # USERNAME_FIELD; debe pertenecer a un dominio permitido
    name = CharField(max_length=120)
    dept = CharField(max_length=80, blank=True)
    role = CharField(choices=[("jugador","jugador"), ("gestor","gestor")])
    is_active = BooleanField(default=True)        # = Player.active del prototipo
    must_change_password = BooleanField(default=True)
    created_at = DateTimeField(auto_now_add=True)
    # avatar: propiedad derivada del name (iniciales) + color por hash del id
```

### `accounts.AuditLog`
```python
class AuditLog(Model):
    actor = FK(User, related_name="audit_actions")
    action = CharField()         # match_resolved | password_reset | player_created | payment_toggled | prize_changed
    target_type = CharField()    # match | user | prize | payment
    target_id = CharField()
    payload = JSONField()        # snapshot mínimo, SIN secretos
    created_at = DateTimeField(auto_now_add=True)
```

### `competition.Team`
```python
class Team(Model):
    code = CharField(primary_key=True, max_length=3)   # ESP, ARG, FRA…
    name = CharField(max_length=80)
    flag = CharField(max_length=8)                      # emoji 🇪🇸
```

### `competition.Round`
```python
class Round(Model):
    id = CharField(primary_key=True)                    # groups | r32 | r16 | qf | sf | final
    label = CharField()                                 # "Fase de grupos"
    short = CharField()
    points = PositiveSmallIntegerField()                # 3, 5, 7, 10, 15, 25
    order = PositiveSmallIntegerField()                 # orden en el torneo
```

Seed de puntos: **3 (grupos) · 5 (dieciseisavos) · 7 (octavos) · 10 (cuartos) · 15 (semis) · 25 (final)**.

### `competition.Match`
```python
class Match(Model):
    round = FK(Round)
    group = CharField(max_length=20)                    # "A".."L" en grupos; "Octavos · 3" en KO
    matchday = PositiveSmallIntegerField(null=True)     # 1/2/3 SÓLO en grupos; null en KO
    home = FK(Team, related_name="home_matches")
    away = FK(Team, related_name="away_matches")
    kickoff = DateTimeField()                           # UTC; render en Europe/Madrid
    result_home = PositiveSmallIntegerField(null=True)
    result_away = PositiveSmallIntegerField(null=True)
    finished_at = DateTimeField(null=True)
    # status: property derivada (open/closing/closed/live/done), NO se persiste
```

### `competition.Prediction`
```python
class Prediction(Model):
    player = FK(User)
    match = FK(Match)
    home = PositiveSmallIntegerField()
    away = PositiveSmallIntegerField()
    earned = PositiveSmallIntegerField(null=True)       # se rellena al resolver el partido
    updated_at = DateTimeField(auto_now=True)
    class Meta:
        unique_together = [("player", "match")]
```

### `pot.PotSettings` (singleton, id=1)
```python
class PotSettings(Model):
    per_player = DecimalField(default=10)
    allowed_email_domains = JSONField(default=list)     # ["edisa.com"]
```

### `pot.Prize`
```python
class Prize(Model):
    SCOPES = [
        ("global", "Global"),         # 1º/2º/3º de la clasificación final
        ("matchday", "Jornada"),      # ganador de una jornada de grupos (1/2/3)
        ("round", "Ronda KO"),        # ganador de toda una ronda eliminatoria (r32/r16/qf)
    ]
    scope = CharField(choices=SCOPES)
    position = PositiveSmallIntegerField(null=True)     # 1/2/3 sólo cuando scope=global
    matchday = PositiveSmallIntegerField(null=True)     # 1/2/3 sólo cuando scope=matchday
    round = FK(Round, null=True)                         # r32|r16|qf sólo cuando scope=round (nunca sf/final)
    amount = DecimalField(default=0)
    label = CharField()                                  # texto a mostrar
```

Seed inicial: **9 filas con `amount = 0`** (3 global + 3 matchday + 3 round). El gestor las edita desde `/gestion/premios/`.

### `pot.Payment`
```python
class Payment(Model):
    player = OneToOne(User)
    paid = BooleanField(default=False)
    paid_at = DateTimeField(null=True)
```

---

## 3. Reglas de negocio y servicios

Las reglas que ya estaban fijadas en `docs/DATA_MODEL.md` se mantienen; este apartado las concreta como funciones puras (`services.py` por app) para que sean fáciles de testear.

### 3.1 Puntuación de un pronóstico

```python
def score(pred, match) -> int | None:
    if match.result_home is None:
        return None
    if pred.home == match.result_home and pred.away == match.result_away:
        return match.round.points          # EXACTO
    if sign(pred.home - pred.away) == sign(match.result_home - match.result_away):
        return 1                            # acierta 1X2
    return 0                                # fallo
```

### 3.2 Resolver un partido (atómico)

```python
@transaction.atomic
def resolve_match(match, home, away, actor):
    match.result_home, match.result_away = home, away
    match.finished_at = timezone.now()
    match.save()
    preds = Prediction.objects.select_for_update().filter(match=match)
    for p in preds:
        p.earned = score(p, match)
    Prediction.objects.bulk_update(preds, ["earned"])
    AuditLog.log(actor, "match_resolved", "match", match.id, {"home": home, "away": away})
    invalidate_standings_cache()
    invalidate_prize_winners_cache()
```

Editar un resultado ya confirmado vuelve a ejecutar el mismo flujo.

### 3.3 Estado derivado del partido

```python
@property
def status(self) -> str:
    now = timezone.now()
    if self.result_home is not None:
        return "done"
    close_at = self.kickoff - timedelta(hours=2)
    if now >= self.kickoff:
        return "live"
    if now >= close_at:
        return "closed"
    if close_at - now <= timedelta(hours=2):
        return "closing"
    return "open"
```

Sólo se puede crear/editar un `Prediction` cuando `status in {"open", "closing"}`. Validado en backend (`PredictView.post`), nunca solo en cliente.

### 3.4 Clasificación con desempate

Una sola consulta SQL agrupada por jugador:

```sql
SELECT u.id, u.name,
       COALESCE(SUM(pr.earned), 0)                       AS pts,
       COUNT(CASE WHEN pr.earned > 0 THEN 1 END)         AS hits,
       COUNT(CASE WHEN pr.earned = r.points THEN 1 END)  AS exact_hits
FROM accounts_user u
LEFT JOIN competition_prediction pr ON pr.player_id = u.id
LEFT JOIN competition_match m       ON pr.match_id = m.id
LEFT JOIN competition_round r       ON m.round_id = r.id
WHERE u.is_active = TRUE
GROUP BY u.id
ORDER BY pts DESC, exact_hits DESC, hits DESC, u.name ASC;
```

**Criterio de desempate: exactos → aciertos → orden alfabético.** Los jugadores `is_active = False` quedan fuera.

### 3.5 Racha

Aciertos (`earned > 0`) consecutivos contando desde el último partido resuelto del jugador hacia atrás. Implementación: `Prediction` ordenados por `match__kickoff` descendente, contando hasta encontrar un `earned == 0` o agotar la lista.

### 3.6 Tendencia (▲▼—)

Posición tras el último partido resuelto vs posición tras el penúltimo. Se calcula reconstruyendo dos snapshots de standings sobre el histórico ordenado por `kickoff`.

### 3.7 Premios por jornada — algoritmo de ganador

Para una `scope_key` (p. ej. `("matchday", 1)` o `("round", "qf")`):

1. Recoger los partidos del scope (matchday 1 de grupos / toda la ronda `qf`).
2. Si **algún partido no está `done`** → ganador `pending`. No se anuncia ni se reparte.
3. Si todos están `done`:
   - Agrupar `Prediction.earned` por jugador y sumar.
   - Ganadores = jugadores con la suma máxima **siempre que esa suma sea > 0**.
   - Si hay un único ganador, le toca el `Prize.amount` entero.
   - Si hay empate, se reparte a partes iguales (`amount / N`).
   - Si nadie sumó puntos → premio **desierto**. Se muestra como tal en la UI; el dinero queda sin asignar y el gestor decide manualmente qué hacer con él (acumular a otro premio, devolver, etc.).

Criterio de puntuación: el **mismo del sistema general** (exacto = `round.points`, 1X2 = 1).

### 3.8 Estadísticas (KPIs y donut)

```python
def kpis(player):
    s = standings()
    me = next(x for x in s if x.player_id == player.id)
    return {
        "hit_rate":    me.hits / max(me.played, 1),
        "exact":       me.exact_hits,
        "vs_avg":      me.pts - mean(x.pts for x in s),
        "vs_leader":   s[0].pts - me.pts,
        "percentile":  (me.position - 1) / len(s) * 100,
        "better_than": len(s) - me.position,
    }
```

Donut: tres segmentos por jugador → `exactos / aciertos parciales / fallos` sobre los partidos `done` en los que tenía pronóstico.

### 3.9 Histórico para el gráfico de evolución

```python
def per_player_history():
    matches = Match.objects.filter(finished_at__isnull=False).order_by("kickoff")
    points = defaultdict(int)
    history = defaultdict(list)
    for idx, m in enumerate(matches, start=1):
        for pred in m.predictions.all():
            points[pred.player_id] += pred.earned or 0
        order = sorted(points.items(), key=lambda x: -x[1])
        positions = {pid: pos for pos, (pid, _) in enumerate(order, start=1)}
        for pid, pts in points.items():
            history[pid].append({"idx": idx, "pts": pts, "pos": positions[pid]})
    return history
```

Cacheado con `cache.set(key, history, timeout=300)`. La caché se invalida al resolver/editar un partido.

### 3.10 Cacheo

- Standings, ganadores de premios e histórico cachean por una clave versionada del modelo `Match` (que cambia cada `resolve_match`).
- Backend de caché: `LocMemCache` en dev, `DatabaseCache` en prod (PythonAnywhere free no tiene Redis).

---

## 4. URLs, vistas y plantillas

### Mapa de rutas

| Ruta | Vista | Rol | Plantilla |
|---|---|---|---|
| `/` | `LoginView` (redirige si auth) | público | `accounts/login.html` |
| `/login` | `LoginView` (POST) | público | — |
| `/logout` | `LogoutView` | autenticado | — |
| `/cambiar-password` | `ChangePasswordView` | autenticado | `accounts/change_password.html` |
| `/competicion/` | `CompetitionView` (filtros por ronda en QS) | jugador+gestor | `competition/dashboard.html` |
| `/competicion/pronosticar/<match_id>/` | `PredictView` (GET=modal, POST=guardar) | jugador+gestor | `competition/_predict_modal.html` |
| `/stats/` | `StatsView` | jugador+gestor | `stats/stats.html` |
| `/stats/chart-data.json` | `ChartDataView` | jugador+gestor | endpoint JSON |
| `/gestion/resultados/` | `ManageResultsView` | gestor | `competition/manage_results.html` |
| `/gestion/resultados/<match_id>/` | `ResultOfficialView` | gestor | `competition/_official_modal.html` |
| `/gestion/jugadores/` | `ManagePlayersView` | gestor | `pot/manage_players.html` |
| `/gestion/jugadores/nuevo/` | `PlayerFormView` | gestor | `pot/_player_modal.html` |
| `/gestion/jugadores/<id>/` | `PlayerFormView` (editar) | gestor | — |
| `/gestion/jugadores/<id>/reset-password/` | `ResetPasswordView` | gestor | `pot/_password_reveal.html` |
| `/gestion/jugadores/<id>/baja/` | `TogglePlayerActiveView` | gestor | — |
| `/gestion/jugadores/<id>/pago/` | `TogglePaymentView` | gestor | — |
| `/gestion/premios/` | `PrizesSettingsView` | gestor | `pot/prizes_settings.html` |
| `/gestion/auditoria/` | `AuditLogView` | gestor | `accounts/audit_log.html` |
| `/admin/` | Django admin | superuser | nativa |

### Mixins

- `RoleRequiredMixin(required_role="gestor")` → 403 → redirect a `/competicion` con `messages.warning`.
- `ForcePasswordChangeMiddleware` → redirige a `/cambiar-password` si `request.user.must_change_password`.

### Estrategia de plantillas

```
base.html
├── partials/_ambient.html        # fondo animado fijo
├── partials/_topbar.html         # logo + nav filtrada por rol + chip bote + tema + perfil
├── partials/_toast.html          # contenedor para Django messages, alimenta toast.js
└── partials/_leaderboard.html    # clasificación lateral (variantes full | list | hidden)
```

Cada pantalla extiende `base.html` y rellena `{% block main %}` y `{% block sidebar %}`.

### Modales

Cada modal tiene **URL propia** y plantilla parcial. Si el cliente tiene JS, `modal.js` los abre vía `fetch` + inyección del HTML en un contenedor overlay. Sin JS, se navega a la página completa con el formulario embebido. **La app es funcional sin JavaScript** — sólo pierde animaciones, modales en overlay, cuenta atrás dinámica y el gráfico SVG interactivo.

---

## 5. CSS, JS vanilla y fidelidad al prototipo

### CSS

1. `design-reference/styles.css` se **copia 1:1** a `static/css/styles.css` (mismos nombres de clases y de variables: `.glass`, `.btn-primary`, `--c-pink`, `--accent`, `--glass-blur`, etc.). Esta copia es lo que hace que el flujo "sincroniza el diseño" funcione mediante `git diff`.
2. Las fuentes Sora / Inter / Geist Mono se cargan vía `@import` de Google Fonts (igual que el prototipo). Self-host queda como decisión menor para revisar con el DPO si se requiere.
3. El tema se controla con `data-theme="dark|light"` en `<html>`. Server-side desde sesión; el cliente puede sobreescribir con `localStorage`. Default: `dark`.
4. El acento se fija en `blue` para producción. El sistema queda preparado para hacerlo configurable si en el futuro se quiere.

### JS — módulos vanilla

Cada uno se autoinicializa por atributos `data-*` y se carga con `<script type="module" defer>`. Total estimado: < 25 KB sin minificar.

| Fichero | Función | Activación |
|---|---|---|
| `theme.js` | Conmutar dark/light + persistir en `localStorage` | `[data-theme-toggle]` |
| `toast.js` | Convierte Django `messages` en toasts (auto-cierre 2.6 s) | `<div id="dj-messages" data-msg="...">` |
| `anim-num.js` | Animación cúbica (~900 ms) al montar | `[data-anim-num="N"]` |
| `countdown.js` | HH:MM:SS hasta `data-countdown-to` (ISO); vira a amarillo bajo 1 h | `[data-countdown-to]` |
| `modal.js` | Abrir overlay con `fetch`; cerrar con Esc, clic fuera, botón × | `[data-modal-url]` |
| `predict-stepper.js` | Steppers de marcador con teclado (←/→/↑/↓) | dentro del modal de pronóstico |
| `rank-chart.js` | Gráfico SVG: líneas, etiquetas anti-solape, tooltip, modos Posición/Puntos, "Mostrar todos" | `<div data-rank-chart data-src="/stats/chart-data.json">` |

### Iconos

Los 24 iconos del prototipo (objeto `I` en `design-reference/shared.jsx`) se exportan como ficheros `static/icons/<name>.svg` de **stroke fino**. Un template tag `{% icon "trophy" width=18 %}` los inlinea en el HTML (con caché), heredando `currentColor` del contexto.

### Degradación sin JS

| Feature | Con JS | Sin JS |
|---|---|---|
| Modales | Overlay con fetch | Página completa por URL propia |
| Toasts | Auto-cierre animado | Bloque `messages` arriba |
| Cuenta atrás | HH:MM:SS dinámico | "Cierra a las 18:30" |
| AnimNum | Cuenta hacia arriba | Número final estático |
| Gráfico evolución | SVG interactivo | Tabla de puntos actuales + "Activa JS para ver el gráfico" |

---

## 6. Autenticación, autorización y seguridad

### Login y sesión
- `LoginForm` valida que el email pertenezca a `PotSettings.allowed_email_domains`.
- Reintentos limitados con `django-axes` (5 / 15 min, bloqueo por IP+email).
- Mensaje genérico ("Correo o contraseña incorrectos") — no revelamos si el correo existe.
- Sesiones: cookies `HttpOnly`, `Secure` en prod, `SameSite=Lax`. `SESSION_EXPIRE_AT_BROWSER_CLOSE=True` en prod.
- CSRF activo en todos los POST.

### Cambio forzado de contraseña
- Tras login, si `must_change_password=True` → middleware redirige a `/cambiar-password` (todas las rutas salvo esa y `/logout`).
- Política mínima: 10 caracteres, una mayúscula, un dígito (`django-password-validators`).

### Contraseña temporal (alta y reset)
1. Gestor pulsa "Nuevo jugador" o "Resetear contraseña".
2. Backend: `secrets.token_urlsafe(9)` → 12 chars URL-safe → `user.set_password(...)` → `must_change_password=True` → `save()`.
3. La respuesta del POST renderiza un modal con la contraseña visible en grande + botón "Copiar" + aviso "Compártela por canal privado".
4. Se registra `AuditLog(action="password_reset", ...)` **sin la contraseña**.
5. La contraseña **no se loguea ni se almacena en claro** y se muestra **una sola vez**.

### Autorización
- `LoginRequiredMixin` en toda vista autenticada.
- `RoleRequiredMixin(required_role="gestor")` en las vistas de `/gestion/*` y en `ManageResultsView`.
- Validación dura en el servidor de que `Match.status in {"open","closing"}` antes de guardar `Prediction`.

### Auditoría
`accounts.AuditLog` captura: `match_resolved`, `password_reset`, `player_created`, `payment_toggled`, `prize_changed`. Visible para el gestor en `/gestion/auditoria/`.

### Configuración prod (`settings/prod.py`)
```python
DEBUG = False
SECURE_SSL_REDIRECT = True
SECURE_HSTS_SECONDS = 31_536_000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_REFERRER_POLICY = "same-origin"
SECURE_CONTENT_TYPE_NOSNIFF = True
X_FRAME_OPTIONS = "DENY"
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True
ALLOWED_HOSTS = [<dominio PythonAnywhere>]
SECRET_KEY = env("DJANGO_SECRET_KEY")
DATABASES = { "default": mysql_config_from_env() }

# django-csp
CSP_DEFAULT_SRC = ("'self'",)
CSP_STYLE_SRC = ("'self'", "https://fonts.googleapis.com", "'unsafe-inline'")
CSP_FONT_SRC = ("https://fonts.gstatic.com",)
CSP_IMG_SRC = ("'self'", "data:")
CSP_SCRIPT_SRC = ("'self'",)
```

### GDPR
- Datos tratados: nombre, email corporativo, departamento. Base legal: interés legítimo, actividad recreativa interna voluntaria.
- "Baja" = soft delete (`is_active=False`); preserva histórico.
- "Borrado real" sólo desde Django admin, acción manual del gestor.

### Fuera de alcance v1
- 2FA, SSO, recuperación automática de contraseñas (descartados).
- Email (alta, reset, recordatorios) — PythonAnywhere free no permite SMTP saliente.

---

## 7. Testing, despliegue y operativa

### Estrategia de tests

**Cobertura objetivo:**
- `competition.services` + `pot.services.prizes`: **100%**.
- Vistas: cubrir flujos principales por integración.
- Plantillas, CSS, JS: revisión visual manual contra el prototipo.

**Unit tests** (`pytest`):
- `score`: todas las combinaciones de signo × todas las rondas.
- `derive_match_status` con `freezegun`.
- `resolve_match`: atomicidad y `bulk_update` correcto.
- `standings`: desempate determinista, exclusión de inactivos.
- `per_player_history`: dada una fixture, salida idéntica.
- `matchday_winners`: pending / resolved con ganador único / empate / desierto.
- Validador de dominio email.

**Integration tests:**
- Login: ok / contraseña mala / dominio no permitido / bloqueo a los 6 intentos.
- Pronóstico: jugador POSTea ok; `match.status="closed"` → 403.
- Resolución: gestor confirma → puntos y standings se recalculan.
- Acceso a `/gestion/*`: jugador redirigido, gestor 200.
- `must_change_password=True` redirige siempre a `/cambiar-password`.

**Smoke E2E (opcional):** un test `playwright-python` que recorre el flujo "gestor crea jugador → jugador entra y cambia password → pronostica → gestor resuelve → puntos visibles".

### CI

`.github/workflows/ci.yml`:
- `ruff check .`
- `ruff format --check .`
- `pytest -q --cov=. --cov-fail-under=80`

### Despliegue en PythonAnywhere

`docs/DEPLOY.md` lo documenta paso a paso. Resumen:

1. Crear cuenta free y abrir consola Bash.
2. `git clone` del repo en `~/apuestas-interna`.
3. `mkvirtualenv -p python3.12 porra26` + `pip install -r requirements.txt`.
4. Crear DB MySQL en el panel: `<user>$porra26`.
5. `cp porra26/settings/example.env .env` y rellenar (`DJANGO_SECRET_KEY`, `MYSQL_PASSWORD`, `DJANGO_ALLOWED_HOSTS`, `EMAIL_DOMAIN`).
6. `python manage.py migrate`.
7. `python manage.py loaddata fixtures/teams.json fixtures/rounds.json fixtures/world_cup_2026.json` + seed inicial de `PotSettings` y 9 `Prize` con amount=0.
8. `python manage.py createsuperuser` → primer gestor.
9. `python manage.py collectstatic --no-input`.
10. Panel "Web app": WSGI → `porra26/wsgi.py`, virtualenv `porra26`, static mapping `/static/` → `~/apuestas-interna/staticfiles/`.
11. Reload.

Redeploys: `docs/scripts/deploy.sh` con `git pull`, `pip install`, `migrate`, `collectstatic`, `touch wsgi`.

### Calendario del Mundial

El fixture `fixtures/world_cup_2026.json` se prepara a mano (a partir del calendario oficial de la FIFA cuando esté publicado y consolidado) o por scraping offline. Sin dependencia de red en runtime.

### Backup

Tarea diaria en la sección "Tasks" de PythonAnywhere:

```bash
mysqldump -u <user> -p$MYSQL_PASS \
  -h <user>.mysql.pythonanywhere-services.com <user>$porra26 \
  | gzip > ~/backups/porra26-$(date +%F).sql.gz
find ~/backups -name "porra26-*.sql.gz" -mtime +30 -delete
```

Retención: 30 días. Descargable por FTP/web.

### Observabilidad

- `django.utils.log` a fichero `~/apuestas-interna/logs/error.log`; PythonAnywhere lo expone en el panel.
- Auditoría funcional vía `accounts.AuditLog`.
- Sin Sentry/APM externo en v1 (PythonAnywhere free bloquea tráfico saliente arbitrario).

### Entornos

| Entorno | DB | Settings | Datos |
|---|---|---|---|
| **dev** (local) | SQLite | `dev.py` | seed mínimo (1 gestor, 4 partidos demo) |
| **test** (CI + local) | SQLite in-memory | `test.py` | factory-boy |
| **prod** (PythonAnywhere) | MySQL | `prod.py` | seed real Mundial + gestor inicial |

### Documentación operativa que se creará junto con el código

- `docs/DEPLOY.md` — despliegue paso a paso.
- `docs/SYNC_DESIGN.md` — flujo "sincroniza el diseño".
- `docs/RUNBOOK.md` — reset de contraseña por consola, regenerar standings, restaurar backup.

---

## 8. Riesgos, suposiciones y criterios de aceptación

### Riesgos y mitigaciones

| Riesgo | Prob. | Impacto | Mitigación |
|---|---|---|---|
| Quota de CPU del free se agota en pico (todos pronosticando a la vez) | Media | Medio | Caché agresivo de standings/winners. Plan B: subir a Hacker plan ($5/mes). |
| Tamaño de MySQL free se agota (~512 MB) | Baja | Medio | Cálculo conservador < 50 MB para 48 jugadores. Holgado. |
| FIFA cambia el calendario | Alta | Bajo | Seed es JSON editable; admin Django permite editar partidos sin redeploy. |
| Empate en 1.er premio global | Baja | Medio | Mismo desempate (exactos → aciertos → alfabético). Si persiste, decisión manual del gestor desde auditoría. |
| Jornada "desierta" (nadie sumó) | Baja | Bajo | Premio queda como "Desierto"; el gestor decide qué hacer con el dinero. |
| Resultado oficial mal introducido | Media | Alto | Edición vuelve a recalcular todo y queda en auditoría. Confirmación "¿estás seguro?" en el modal. |
| Fidelidad de píxel se desvía en próximas iteraciones del prototipo | Alta | Bajo | `docs/SYNC_DESIGN.md` + `design-reference/` versionado en repo. |
| JavaScript bloqueado por política corporativa | Baja | Bajo | Cada feature degrada con gracia. App usable sin JS. |
| Sesiones abiertas en máquinas compartidas | Baja | Bajo | `SESSION_EXPIRE_AT_BROWSER_CLOSE=True` en prod. |

### Suposiciones de partida

1. **~50 jugadores máx.** En el rango ≤ 500 el diseño aguanta sin cambios. > 500 → revisar caché y plan de hosting.
2. **Un torneo activo a la vez.** Si en el futuro hay varios en paralelo, se introduce `Tournament` como FK en `Round`/`Match`/`Prize`. Anotado, no implementado.
3. **Calendario correcto en seed.** No validamos coherencias (mismo equipo en dos partidos a la misma hora, etc.).
4. **Cierre fijo a `kickoff − 2h`** para todos los partidos.
5. **Idioma fijo: español de España.** Sin i18n multi-idioma.
6. **Zona horaria de render: `Europe/Madrid`** (kickoffs almacenados en UTC).

### Criterios de aceptación de v1

La v1 está lista cuando un gestor recién creado puede, sin ayuda externa:

1. Hacer login en `/`.
2. Crear un jugador desde el panel y obtener su contraseña temporal en pantalla.
3. Que ese jugador haga login, sea forzado a cambiar contraseña y entre a `/competicion`.
4. Que el jugador pronostique un partido `open` y vea el toast de confirmación + el pronóstico reflejado en la tarjeta.
5. Que el jugador intente editar un partido `closed` y reciba el mensaje "Las apuestas están cerradas".
6. Que el gestor confirme el resultado oficial de un partido desde `/gestion/resultados/` y vea cambiar los puntos del jugador y la clasificación.
7. Que `/stats` muestre KPIs, donut y gráfico de evolución con datos reales.
8. Que el gestor edite los importes de los 9 premios en `/gestion/premios/` y vea reflejado el reparto.
9. Que al cerrar todas las jornadas de un grupo, aparezca el ganador de la jornada con su premio (o "Desierto" si nadie sumó).
10. Que la app se vea **idéntica al prototipo** en tema oscuro y claro a ≥ 1280 px de ancho.
11. Que la suite de tests pase y CI esté verde.

### Fuera de alcance v1

- 2FA, SSO, recuperación automática de contraseñas.
- Email (alta, reset, recordatorios) — bloqueado por PythonAnywhere free.
- Histórico entre ediciones del torneo.
- Exportación a CSV/PDF.
- Subida de fotos de perfil (sólo iniciales).
- App móvil nativa.
- Múltiples torneos en paralelo.
- Notificaciones push o web push.
- Sentry / APM externo.

### Decisiones explícitamente descartadas

- **Next.js, Vite SPA, HTMX, Inertia.js** — descartados por el responsable a favor de Django templates puros.
- **PostgreSQL, SQLite en prod** — descartados por la oferta del hosting (PythonAnywhere free ofrece MySQL).
- **Railway, Render, Fly.io** — descartados por coste recurrente o por cold starts.
- **Servir el prototipo tal cual con un htpasswd** — descartado: sin persistencia, sin auth real, sin auditoría.

---

## 9. Decisiones tomadas en esta sesión (registro)

Lista compacta de las decisiones nuevas que este documento añade sobre el handoff original:

1. **Stack:** Django + MySQL + templates puros + PythonAnywhere free.
2. **Estructura:** 4 apps por dominio (`accounts`, `competition`, `pot`, `stats`) + `core`.
3. **Auth y reset:** mostrar contraseña temporal en pantalla del gestor (sin SMTP). Sin email transaccional en v1.
4. **Escala de puntos:** **3 · 5 · 7 · 10 · 15 · 25**.
5. **Desempate clasificación:** exactos → aciertos → orden alfabético.
6. **Premios por jornada:** 6 premios extra (3 jornadas de grupos + r32/r16/qf). Mismo sistema de puntos. Sólo se anuncian cuando todos los partidos del scope están `done`. Empate → reparto a partes iguales. Sin ganadores → premio "Desierto" (decisión manual del gestor sobre el dinero).
7. **Bote editable:** el gestor controla los 9 importes desde `/gestion/premios/` + la aportación por jugador.
8. **Calendario:** seed `fixtures/world_cup_2026.json` cargado con `loaddata`. Editable por admin.
9. **Primer gestor:** `python manage.py createsuperuser` en la consola de PythonAnywhere tras desplegar.
10. **Dominio email:** restricción a un dominio configurable (`PotSettings.allowed_email_domains`).
11. **Datos iniciales:** producción arranca con sólo el gestor inicial. Sin seed de los 48 mock.
12. **Responsive:** escritorio + tablet (≥ 768 px) bien resueltos; móvil usable pero no pulido.

---

## 10. Próximo paso

Tras la revisión y aprobación de este spec por el responsable, se invoca la skill `superpowers:writing-plans` para producir el plan de implementación detallado (con fases, milestones y tareas verificables). El plan extenderá las fases del `docs/PLAN.md` original ajustándolas a las decisiones recogidas aquí.
