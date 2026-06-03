# Spec — Modal de "ganador de la jornada/fase" con confetti

Fecha: 2026-06-03
Branch destino: `worktree-ganador-jornada`
Stack: Django + plantillas server-side (no React). Reutiliza el sistema de modales existente (`static/js/modal.js`).

---

## 1. Problema

Cuando se cierra una **jornada de fase de grupos** o una **ronda eliminatoria** (todos sus partidos resueltos), nadie en la app sabe automáticamente **quién ha ganado esa jornada/ronda**. Hoy el cálculo existe (`pot/services/prizes.py:matchday_winners`) pero solo se usa en backoffice/admin: los jugadores no se enteran de forma destacada.

Queremos un anuncio festivo que aparezca **una sola vez por jugador** la primera vez que entre al portal después de que se haya determinado un ganador de una jornada o fase.

## 2. Objetivo

- Persistir un "anuncio de ganador" cuando una jornada/ronda se completa.
- En el primer GET de la pantalla principal (`/competicion/`) tras esa creación, mostrar un **modal vistoso** con confetti que celebre al ganador (o ganadores empatados).
- Marcar como **visto por ese usuario** al cerrar el modal, para que no vuelva a aparecer.
- Si hay varios anuncios pendientes, **encadenarlos**: al cerrar uno se abre el siguiente.

## 3. Alcance

**Incluido:**

- Nueva app Django `announcements/` con dos modelos: `WinnerAnnouncement` y `WinnerAnnouncementSeen`.
- Servicio `announcements/services.py:detect_after_match(match)` que, dado un partido recién resuelto, detecta si se ha cerrado algún scope (matchday/round/global) y crea (idempotente) el anuncio correspondiente con sus ganadores.
- Hook en `competition/services/resolve.py:resolve_match()` para llamar a `detect_after_match(match)` al final de la transacción.
- Endpoint `GET /anuncios/<id>/` que devuelve el HTML del modal (fragmento, sin extender base).
- Endpoint `POST /anuncios/<id>/seen` que crea `WinnerAnnouncementSeen` y devuelve la URL del siguiente anuncio pendiente vía `X-Modal-Next` (patrón ya usado por el flujo "guardar y siguiente").
- Cambio en `competition/views.py:CompetitionView.get()` para inyectar IDs de anuncios pendientes en el contexto y un trigger en `templates/competition/dashboard.html` que abre el primer modal automáticamente al cargar.
- Vendorizar `canvas-confetti` (~10 KB minificado) en `static/js/vendor/canvas-confetti.min.js`.
- Pequeño script `static/js/winner-confetti.js` que dispara las ráfagas al montar el modal.
- Plantilla `templates/announcements/_winner_modal.html` con el HTML del modal.
- Migraciones, tests TDD, registro en `INSTALLED_APPS`, URLs.

**Fuera de alcance:**

- Notificaciones por email / Teams (queda para otra iteración).
- Historial navegable de ganadores (página dedicada).
- Cambios en la lógica de cálculo de ganadores (vive en `pot/services/prizes.py` y otra sesión podría estar tocando reglas de desempate; ver §10).
- Cambios visuales en otros modales o en el ambient/topbar.

## 4. Definición de "scope" y de "se ha cerrado"

Reutilizamos los `scope_key` que ya entiende `matchday_winners`:

| `scope_kind` | Definición de "scope cerrado" |
|--------------|--------------------------------|
| `matchday` (`scope_matchday=N`) | Existe al menos un partido en `Match.objects.filter(round_id="groups", matchday=N)` y **todos** tienen `result_home is not None`. |
| `round` (`scope_round=<round_id>` con `round_id ≠ "groups"`) | Todos los partidos de esa ronda KO tienen resultado. |
| `global` | **Únicamente** cuando se resuelve el partido de la `Final` (`round_id="final"`). Es un anuncio especial "Campeón del Mundial". |

> Nota: `scope_kind="round"` aplica solo a R32/R16/QF/SF/Final. La fase de grupos no genera anuncios de tipo `round` (sólo `matchday`).

> Nota: el anuncio `global` se crea **además** del de `round=final`. Son dos anuncios distintos (la final tiene su ganador "de la final" y luego está el "campeón del Mundial" — coinciden los puntos pero el copy y la celebración deben ser más grandes).

## 5. Modelo de datos

Nueva app `announcements/`. Tablas:

```python
# announcements/models.py

from django.db import models
from django.db.models import Q, UniqueConstraint


class WinnerAnnouncement(models.Model):
    SCOPE_CHOICES = [
        ("matchday", "Jornada de grupos"),
        ("round", "Ronda KO"),
        ("global", "Campeón del Mundial"),
    ]

    scope_kind = models.CharField(max_length=10, choices=SCOPE_CHOICES)
    scope_matchday = models.PositiveSmallIntegerField(null=True, blank=True)
    scope_round = models.ForeignKey(
        "competition.Round",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="announcements",
    )
    points = models.PositiveIntegerField()
    tied = models.BooleanField(default=False)
    winners = models.ManyToManyField(
        "accounts.User", related_name="winning_announcements"
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ["created_at"]
        constraints = [
            UniqueConstraint(
                fields=["scope_kind", "scope_matchday"],
                condition=Q(scope_kind="matchday"),
                name="uniq_ann_matchday",
            ),
            UniqueConstraint(
                fields=["scope_kind", "scope_round"],
                condition=Q(scope_kind="round"),
                name="uniq_ann_round",
            ),
            UniqueConstraint(
                fields=["scope_kind"],
                condition=Q(scope_kind="global"),
                name="uniq_ann_global",
            ),
        ]

    def __str__(self):
        if self.scope_kind == "matchday":
            return f"Anuncio jornada {self.scope_matchday}"
        if self.scope_kind == "round":
            return f"Anuncio ronda {self.scope_round_id}"
        return "Anuncio campeón del Mundial"

    @property
    def title(self) -> str:
        if self.scope_kind == "matchday":
            return f"¡Ganador de la Jornada {self.scope_matchday}!" if not self.tied else f"¡Ganadores de la Jornada {self.scope_matchday}!"
        if self.scope_kind == "round":
            label = self.scope_round.label if self.scope_round_id else "la ronda"
            return f"¡Ganador de {label}!" if not self.tied else f"¡Ganadores de {label}!"
        return "¡Campeón del Mundial!" if not self.tied else "¡Campeones del Mundial!"


class WinnerAnnouncementSeen(models.Model):
    announcement = models.ForeignKey(
        WinnerAnnouncement, on_delete=models.CASCADE, related_name="seen_by"
    )
    user = models.ForeignKey(
        "accounts.User", on_delete=models.CASCADE, related_name="seen_announcements"
    )
    seen_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        constraints = [
            UniqueConstraint(
                fields=["announcement", "user"], name="uniq_seen_per_user"
            )
        ]
        indexes = [models.Index(fields=["user", "announcement"])]

    def __str__(self):
        return f"Seen({self.user_id} → {self.announcement_id})"
```

## 6. Servicio de detección

```python
# announcements/services.py

from typing import Optional

from competition.models import Match, Round
from pot.services.prizes import matchday_winners

from .models import WinnerAnnouncement


def detect_after_match(match: Match) -> list[WinnerAnnouncement]:
    """Llamado tras resolve_match(). Devuelve los anuncios creados (0..N)."""
    created: list[WinnerAnnouncement] = []

    if match.round_id == "groups" and match.matchday is not None:
        ann = _try_create("matchday", matchday=match.matchday)
        if ann:
            created.append(ann)
    else:
        ann = _try_create("round", round_id=match.round_id)
        if ann:
            created.append(ann)
        if match.round_id == "final":
            ann = _try_create("global")
            if ann:
                created.append(ann)

    return created


def _try_create(scope_kind: str, *, matchday: Optional[int] = None, round_id: Optional[str] = None) -> Optional[WinnerAnnouncement]:
    if scope_kind == "matchday":
        scope_key = ("matchday", matchday)
        filter_kwargs = {"scope_kind": "matchday", "scope_matchday": matchday}
    elif scope_kind == "round":
        scope_key = ("round", round_id)
        filter_kwargs = {"scope_kind": "round", "scope_round_id": round_id}
    elif scope_kind == "global":
        scope_key = ("global",)
        filter_kwargs = {"scope_kind": "global"}
    else:
        raise ValueError(scope_kind)

    if WinnerAnnouncement.objects.filter(**filter_kwargs).exists():
        return None

    result = matchday_winners(scope_key)
    if result.status != "resolved":
        return None  # aún quedan partidos sin resultado o nadie acertó nada

    ann = WinnerAnnouncement.objects.create(
        scope_kind=scope_kind,
        scope_matchday=matchday,
        scope_round_id=round_id,
        points=result.points,
        tied=result.tied,
    )
    ann.winners.set(result.winners)
    return ann
```

> **Contrato con `matchday_winners`:** devuelve un objeto con campos `status` (∈ {"pending","desierto","resolved"}), `winners` (lista de `User`), `points` (int) y `tied` (bool). Si la otra sesión cambia la lógica de desempate, este servicio sigue funcionando: solo grabamos lo que la función devuelva.

> **`status == "desierto"`** (nadie tiene puntos positivos): **no creamos anuncio**. La jornada se cierra en silencio.

## 7. Hook en `resolve_match`

Modificar `competition/services/resolve.py:resolve_match()` para añadir, al final (después del `AuditLog.objects.create(...)` y dentro de la misma transacción atómica):

```python
from announcements.services import detect_after_match
detect_after_match(match)
```

> Mantener dentro de la transacción atómica: si se cae la creación del anuncio, también se revierte la resolución del partido. Es deseable porque garantiza coherencia.

## 8. Vistas, URLs y serialización al template

### 8.1 `CompetitionView.get()` (competition/views.py)

Tras calcular `standings`, añadir:

```python
pending_announcements = list(
    WinnerAnnouncement.objects
    .exclude(seen_by__user=request.user)
    .order_by("created_at")
    .prefetch_related("winners", "scope_round")
)
first_announcement_id = pending_announcements[0].id if pending_announcements else None
```

Pasar `first_announcement_id` y `pending_announcements_count` al contexto.

### 8.2 Nueva app `announcements/` — `urls.py`

```python
from django.urls import path
from .views import AnnouncementModalView, AnnouncementSeenView

app_name = "announcements"
urlpatterns = [
    path("<int:pk>/", AnnouncementModalView.as_view(), name="modal"),
    path("<int:pk>/seen", AnnouncementSeenView.as_view(), name="seen"),
]
```

En `porra26/urls.py`: `path("anuncios/", include("announcements.urls"))`.

### 8.3 `AnnouncementModalView` (GET)

- `LoginRequiredMixin`.
- Render `templates/announcements/_winner_modal.html` con `{"announcement": ann}` (fetch del `WinnerAnnouncement` con `prefetch_related("winners", "scope_round")`).
- 404 si el id no existe.

### 8.4 `AnnouncementSeenView` (POST)

- `LoginRequiredMixin`.
- `get_or_create(announcement_id=pk, user=request.user)`.
- Buscar siguiente anuncio pendiente para ese usuario (`exclude(seen_by__user=request.user).exclude(id=pk).order_by("created_at").first()`).
- Si existe → `HttpResponse(status=204)` con header `X-Modal-Next: <reverse("announcements:modal", args=[next.id])>`.
- Si no existe → `HttpResponse(status=204)` sin header (modal.js cierra sin recargar; ver §9 punto 3).

## 9. Frontend

### 9.1 Plantilla del modal

`templates/announcements/_winner_modal.html`:

```html
{% load static %}
<section class="glass pop winner-modal" role="dialog" aria-modal="true" aria-labelledby="winner-title" data-announcement-id="{{ announcement.id }}" data-seen-url="{% url 'announcements:seen' announcement.id %}">
  <button type="button" class="modal-x" data-modal-close aria-label="Cerrar">×</button>
  <div class="winner-trophy" aria-hidden="true">🏆</div>
  <h2 id="winner-title" class="winner-title">{{ announcement.title }}</h2>
  <p class="winner-points">{{ announcement.points }} puntos</p>
  <div class="winner-list">
    {% for w in announcement.winners.all %}
      <div class="winner-card">
        {% include "partials/_avatar.html" with user=w size="lg" %}
        <div class="winner-name">{{ w.name }}</div>
      </div>
    {% endfor %}
  </div>
  <p class="winner-subtitle">
    {% if announcement.tied %}Empate en la cima. ¡Bien jugado!{% else %}¡Enhorabuena!{% endif %}
  </p>
  <div class="modal-actions">
    <button type="button" class="btn btn-primary" data-winner-confirm>¡Felicidades!</button>
  </div>
</section>
```

> Reutiliza el partial `_avatar.html` (en memoria de proyecto: único punto de render de avatar).

### 9.2 Disparador en `dashboard.html`

Justo antes del cierre de `{% block scripts %}`:

```html
{% if first_announcement_id %}
  <script type="module">
    import { openModal } from "{% static 'js/modal.js' %}";
    openModal("{% url 'announcements:modal' first_announcement_id %}");
  </script>
{% endif %}
```

### 9.3 Confetti

- Vendorizar `canvas-confetti` 1.9.x minificado: `static/js/vendor/canvas-confetti.min.js`. Obtener de la release oficial en GitHub (https://github.com/catdad/canvas-confetti) — copiar el contenido a mano si no hay acceso a internet desde el agente.
- Nuevo `static/js/winner-confetti.js` que, **al detectar `.winner-modal` en el DOM** (MutationObserver sobre body o disparado por evento), arranca dos efectos:
  1. **Ráfaga inicial desde detrás del título** (origen `y: 0.4`, ángulo aleatorio, ~120 partículas, spread ≈ 70).
  2. **Lluvia cayendo durante 2.5 s** desde la parte superior (`y: 0`, ángulo 270°, drift aleatorio).
- Cargar en `base.html` justo después de `modal.js` (no en `dashboard.html`, así está disponible si en el futuro el modal aparece en otra vista).

```html
<!-- base.html, dentro de <body>, después de modal.js -->
<script src="{% static 'js/vendor/canvas-confetti.min.js' %}"></script>
<script type="module" src="{% static 'js/winner-confetti.js' %}"></script>
```

> El `canvas-confetti` se carga como script clásico (expone `window.confetti`); `winner-confetti.js` lo consume desde `window.confetti`.

### 9.4 Botón "¡Felicidades!" — flujo de marcado como visto

`winner-confetti.js` también gestiona el click en `[data-winner-confirm]`:

1. POST a `data-seen-url` del `<section.winner-modal>`.
2. Lee `X-Modal-Next` de la respuesta.
3. Si existe → llama a `openModal(next)` (reemplaza el modal actual encadenando).
4. Si no existe → `closeModal()` sin recargar.

Se hace en este script (no en `modal.js`) para no acoplar el sistema genérico al caso del ganador.

### 9.5 CSS

Nuevas reglas en `static/css/styles.css` (al final, no tocar nada existente):

```css
.winner-modal { text-align: center; padding: 32px clamp(20px, 4vw, 48px); max-width: 520px; }
.winner-trophy { font-size: clamp(56px, 8vw, 88px); line-height: 1; margin-bottom: 8px; filter: drop-shadow(0 4px 12px rgba(0,0,0,.35)); }
.winner-title { font-family: 'Sora', system-ui, sans-serif; font-weight: 800; font-size: clamp(22px, 3.5vw, 32px); margin: 4px 0 8px; background: linear-gradient(135deg, var(--accent), var(--accent-2, #ffd25e)); -webkit-background-clip: text; background-clip: text; color: transparent; }
.winner-points { font-family: 'Geist Mono', ui-monospace, monospace; font-size: clamp(15px, 2vw, 18px); opacity: .85; margin: 0 0 20px; }
.winner-list { display: flex; flex-wrap: wrap; gap: 16px; justify-content: center; margin: 0 0 16px; }
.winner-card { display: flex; flex-direction: column; align-items: center; gap: 8px; }
.winner-card .avatar { width: 56px; height: 56px; font-size: 22px; }
.winner-name { font-weight: 600; font-size: 15px; }
.winner-subtitle { opacity: .75; margin: 8px 0 20px; }
.winner-modal .modal-actions { display: flex; justify-content: center; }
.winner-modal .modal-actions .btn { min-width: 180px; }
```

> Si alguna de las variables (`--accent-2`) no existe en `styles.css`, dejar solo `var(--accent)` o un fallback explícito. Verificar antes de commitear.

## 10. Coordinación con la otra sesión (riesgo conocido)

Otra sesión está modificando las **reglas de desempate** en jornadas/rondas (posiblemente en `pot/services/prizes.py` y/o en `competition/services/standings.py`). Impacto sobre esta feature:

- **Sin impacto si:** la función `matchday_winners(scope_key)` mantiene su firma y devuelve `WinnerResult(status, winners, points, tied)`.
- **Trivial de adaptar si:** renombran la función o cambian la firma — solo hay **una** llamada (en `announcements/services.py:_try_create`).
- **Sin impacto en el modelo:** `winners` es M2M, soporta 0..N ganadores. `tied` es informativo.

**Estrategia al rebasar `main`:**
1. `git fetch origin main && git rebase origin/main`.
2. Si hay conflicto en `pot/services/prizes.py`: aceptar la versión de `main` (la otra sesión define la lógica de ganadores).
3. Ejecutar `python manage.py test announcements pot competition` — si el test `test_announcement_uses_matchday_winners_contract` pasa, el contrato sigue intacto.

## 11. Tests (TDD — escribir antes de implementar)

`announcements/tests/test_services.py`:

- `test_no_announcement_when_matchday_incomplete`
- `test_announcement_created_when_last_matchday_match_resolved`
- `test_announcement_created_for_round_ko`
- `test_global_announcement_created_only_after_final`
- `test_announcement_idempotent_on_second_resolve_call`
- `test_no_announcement_when_status_is_desierto` (todos los pronósticos a 0)
- `test_tied_winners_persisted_with_tied_flag`
- `test_announcement_uses_matchday_winners_contract` (assertion sobre el resultado del servicio público, no sobre implementación interna)

`announcements/tests/test_views.py`:

- `test_modal_view_renders_for_authenticated_user`
- `test_modal_view_404_for_missing`
- `test_modal_view_requires_login`
- `test_seen_view_creates_record_and_returns_next_header`
- `test_seen_view_no_next_returns_204_no_header`
- `test_seen_view_idempotent`

`competition/tests/test_competition_view.py` (extender):

- `test_dashboard_passes_first_announcement_id_when_pending`
- `test_dashboard_omits_first_announcement_id_when_all_seen`

`announcements/tests/test_integration.py`:

- `test_resolve_last_match_of_matchday_creates_announcement` (end-to-end vía `resolve_match`)
- `test_resolve_final_match_creates_both_round_and_global_announcements`

> Todos los tests usan factorías existentes (`competition/tests/factories.py`). Añadir factoría `WinnerAnnouncementFactory` si simplifica.

## 12. Criterios de aceptación

1. Resuelvo el último partido de la J1 desde la pantalla de gestor → al recargar `/competicion/` como cualquier jugador, sale el modal con confetti.
2. Cierro el modal → recargo la página → **no** vuelve a salir.
3. Otro jugador entra por primera vez después de ese momento → ve el modal una vez, luego no.
4. Resuelvo seguidamente la J2 y la J3 → al entrar como jugador, veo J1, al cerrar veo J2, al cerrar veo J3.
5. El ganador de la J1 también ve el modal (no se le oculta por ser él/ella el ganador).
6. Si la J1 termina sin que nadie acertara nada (status `desierto`), **no** se muestra modal.
7. Al resolver la Final, se crean **dos** anuncios (round=final + global) y el jugador los ve encadenados.
8. Empate doble en J1 → el modal muestra ambos avatares y el copy "¡Ganadores de la Jornada 1!".
9. El confetti aparece detrás del título, dura ~3 s y desaparece.
10. La feature funciona en tema claro y oscuro (no hay regresiones visuales).

## 13. Archivos esperados (alta de novedades)

```
announcements/
  __init__.py
  apps.py
  admin.py
  models.py
  services.py
  views.py
  urls.py
  migrations/
    __init__.py
    0001_initial.py
  tests/
    __init__.py
    test_services.py
    test_views.py
    test_integration.py
templates/announcements/
  _winner_modal.html
static/js/winner-confetti.js
static/js/vendor/canvas-confetti.min.js
docs/superpowers/specs/2026-06-03-ganador-jornada-modal-design.md      (este archivo)
docs/superpowers/plans/2026-06-03-ganador-jornada-modal-plan.md        (plan)
```

Modificaciones a archivos existentes:

```
porra26/settings.py            (añadir "announcements" a INSTALLED_APPS)
porra26/urls.py                (incluir announcements.urls bajo /anuncios/)
competition/services/resolve.py (llamada a detect_after_match al final)
competition/views.py           (CompetitionView.get: pending_announcements + first_announcement_id)
templates/competition/dashboard.html (script disparador del primer modal)
templates/base.html            (incluir canvas-confetti + winner-confetti.js)
static/css/styles.css          (clases .winner-*)
```

## 14. Notas de fidelidad al diseño

- Tipografías y tokens existentes: `Sora` para títulos, `Geist Mono` para puntos, `--accent` para color destacado.
- Reutiliza `.ovl`, `.glass`, `.pop`, `.modal-x`, `.btn.btn-primary` — son las clases de los modales existentes (ver `_predict_modal.html`).
- Avatar grande: usa el partial existente y pásale `size="lg"` o crea una variante CSS específica `.winner-card .avatar`.

## 15. Idioma

Todos los strings visibles, en **español de España**:

- "¡Ganador de la Jornada {N}!" / "¡Ganadores de la Jornada {N}!"
- "¡Ganador de {ronda.label}!" / "¡Ganadores de {ronda.label}!"
- "¡Campeón del Mundial!" / "¡Campeones del Mundial!"
- "{points} puntos"
- "¡Enhorabuena!" / "Empate en la cima. ¡Bien jugado!"
- Botón: "¡Felicidades!"
- Aria-label cierre: "Cerrar"
