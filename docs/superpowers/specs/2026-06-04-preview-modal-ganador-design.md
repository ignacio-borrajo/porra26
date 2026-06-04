# Spec — Previsualización del modal de "ganador de la jornada/fase"

Fecha: 2026-06-04
Stack: Django + plantillas server-side. Reutiliza `static/js/modal.js`, el partial `templates/announcements/_winner_modal.html` y el confetti existente.

---

## 1. Problema

El modal de ganador (introducido en `2026-06-03-ganador-jornada-modal-design.md`) solo aparece cuando una jornada/ronda se cierra de verdad y, para cada gestor, solo una vez en la vida útil de ese anuncio. Esto hace muy difícil:

- Validar visualmente cambios de estilo o texto en la modal sin esperar al cierre de una jornada real.
- Mostrar a un gestor cómo se verá la celebración cuando le toque ganar.
- Verificar las distintas variantes (jornada vs ronda KO vs Mundial · ganador único vs empate).

## 2. Objetivo

Que **un gestor**, desde la propia app, pueda **abrir el mismo modal** en cualquier momento, con sus datos (su nombre, su avatar) como ganador, sin que ese acto persista nada en la base de datos ni marque ningún anuncio real como visto.

## 3. Alcance

**Incluido:**

- Endpoint `GET /announcements/preview/?scope=<matchday|round|global>&tied=<0|1>` protegido por `GestorRequiredMixin`, que construye un `WinnerAnnouncement` **en memoria** (sin `.save()`) y renderiza `_winner_modal.html` con un flag `preview=True`.
- Pequeña adaptación de `templates/announcements/_winner_modal.html` para:
  - **No** emitir el atributo `data-seen-url` cuando `preview` es verdadero (ya que el anuncio no tiene `pk`).
  - Sustituir el botón "¡Felicidades!" (que hoy hace POST a `/seen`) por uno que simplemente cierra (`data-modal-close`).
  - Mostrar una etiqueta `VISTA PREVIA` discreta en una esquina para que quede claro que no es una celebración real.
- En `templates/pot/prizes_settings.html`, junto a la sección "02 · Por jornada" (donde ya vive `matchday_winner_prize`), añadir un bloque "Previsualizar modal de ganador" con:
  - `<select>` con las 3 variantes de scope: Jornada, Ronda KO, Campeón del Mundial.
  - `<select>` con 2 variantes: Ganador único, Empate (2 ganadores).
  - Botón "Previsualizar" que construye la URL y llama a `openModal(url)` de `static/js/modal.js`.
- Tests TDD en `announcements/tests/test_preview.py` cubriendo: redirect/403 para no gestor, render OK, no se crean filas en BD, variantes de scope y `tied`, datos del propio usuario presentes.

**Fuera de alcance:**

- Botón fuera de la página "Premios y puntos" (p. ej. en la topbar). Si el gestor lo pide más adelante, se valora.
- Previsualización de la variante "desierto" (hoy ni siquiera genera modal real; mantener la coherencia).
- Cualquier cambio a `WinnerAnnouncementSeen`, al flujo de detección o al modal real.
- Internacionalización: textos en español de España, como el resto.

## 4. Diseño técnico

### 4.1. Endpoint

Ruta: `GET /announcements/preview/` (nueva entrada en `announcements/urls.py`).

Vista nueva en `announcements/views.py`:

```python
class AnnouncementPreviewView(GestorRequiredMixin, View):
    def get(self, request):
        scope = request.GET.get("scope", "matchday")
        tied = request.GET.get("tied") == "1"
        ann, winners = build_preview(scope, tied=tied, current_user=request.user)
        return render(
            request,
            "announcements/_winner_modal.html",
            {"announcement": ann, "preview": True, "preview_winners": winners},
        )
```

Notas:

- `GestorRequiredMixin` ya existe en `accounts/mixins.py` y exige `is_gestor`. Para no gestores redirige a `competicion:dashboard` con un mensaje de aviso (mismo comportamiento que el resto de páginas de gestor).
- La vista responde un **fragmento** (sin `extends "base.html"`), igual que `AnnouncementModalView`, para que `openModal()` lo inyecte tal cual.

### 4.2. Helper de construcción

Nuevo módulo `announcements/preview.py` (o dentro de `services.py` si encaja mejor; preferible aislar para no mezclar con la detección real):

```python
def build_preview(scope: str, *, tied: bool, current_user) -> tuple[WinnerAnnouncement, list]:
    ann = WinnerAnnouncement(
        scope_kind=scope,
        points=12,  # valor de ejemplo, suficientemente "creíble"
    )

    if scope == "matchday":
        ann.scope_matchday = 1
    elif scope == "round":
        ko_round = (
            Round.objects.exclude(id="groups").order_by("order").first()
            or Round.objects.first()
        )
        ann.scope_round = ko_round  # se guarda en el cache de la FK
    elif scope == "global":
        pass
    else:
        raise Http404("scope inválido")

    winners = [current_user]
    if tied:
        other = (
            User.objects.exclude(pk=current_user.pk).order_by("name").first()
        )
        if other is not None:
            winners.append(other)
    ann.tied = len(winners) > 1

    base = PotSettings.load().matchday_winner_prize
    ann.share = (base / len(winners)) if winners else Decimal("0")

    return ann, winners
```

Observaciones:

- `ann` **no se guarda** (`.save()` jamás). Su `pk` es `None` durante todo el flujo.
- Para `scope=round`, se asigna `ann.scope_round = ko_round` (no `scope_round_id`), de modo que la `@property title` puede leer `self.scope_round.label` sin pegarle a la BD.
- `winners` se pasa por contexto separado (`preview_winners`) porque el M2M `announcement.winners.all()` no funciona en una instancia sin `pk`. La plantilla itera sobre la lista correcta dependiendo del flag `preview`.

### 4.3. Plantilla `_winner_modal.html`

Cambios mínimos, manteniendo la compatibilidad con el flujo real:

```django
<section class="glass pop winner-modal"
         role="dialog" aria-modal="true" aria-labelledby="winner-title"
         {% if not preview %}
           data-announcement-id="{{ announcement.id }}"
           data-seen-url="{% url 'announcements:seen' announcement.id %}"
         {% else %}
           data-preview="1"
         {% endif %}>
  {% if preview %}<span class="winner-preview-badge">Vista previa</span>{% endif %}
  <button type="button" class="modal-x" data-modal-close aria-label="Cerrar">×</button>
  ...
  <div class="winner-list">
    {% if preview %}
      {% for w in preview_winners %}
        <div class="winner-card">
          {% include "partials/_avatar.html" with u=w size=64 %}
          <div class="winner-name">{{ w.name }}</div>
        </div>
      {% endfor %}
    {% else %}
      {% for w in announcement.winners.all %}
        <div class="winner-card">
          {% include "partials/_avatar.html" with u=w size=64 %}
          <div class="winner-name">{{ w.name }}</div>
        </div>
      {% endfor %}
    {% endif %}
  </div>
  ...
  <div class="winner-actions">
    {% if preview %}
      <button type="button" class="btn btn-primary" data-modal-close>Cerrar vista previa</button>
    {% else %}
      <button type="button" class="btn btn-primary" data-winner-confirm>¡Felicidades!</button>
    {% endif %}
  </div>
</section>
```

CSS: nueva clase `.winner-preview-badge` en `static/css/announcements.css` (o donde vivan los estilos del modal), discreta, en la esquina superior izquierda, fondo translúcido, fuente Geist Mono, mayúsculas, similar a `.eyebrow`.

### 4.4. Disparador en "Premios y puntos"

En `templates/pot/prizes_settings.html`, después de la sección "02 · Por jornada", añadir una nueva subsección "tools de gestor" (fuera del `<form>` principal — no debe enviarse con guardar):

```django
<section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:14px">
  <header style="display:flex;flex-direction:column;gap:4px">
    <span class="eyebrow">Herramientas · vista previa</span>
    <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:20px">Previsualizar modal de ganador</h2>
    <p style="color:var(--text-dim);margin:0;font-size:13px">
      Abre el modal de celebración con tu usuario como ganador. No marca nada ni avisa a nadie.
    </p>
  </header>
  <div style="display:flex;flex-wrap:wrap;gap:12px;align-items:flex-end">
    <label style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">Tipo</span>
      <select id="preview-scope" class="input">
        <option value="matchday">Jornada de grupos</option>
        <option value="round">Ronda eliminatoria</option>
        <option value="global">Campeón del Mundial</option>
      </select>
    </label>
    <label style="display:flex;flex-direction:column;gap:4px">
      <span class="eyebrow">Modo</span>
      <select id="preview-tied" class="input">
        <option value="0">Ganador único</option>
        <option value="1">Empate (2 ganadores)</option>
      </select>
    </label>
    <button type="button" class="btn btn-primary" id="preview-open">Previsualizar</button>
  </div>
</section>
```

JS al final de la página (`{% block scripts %}`):

```html
<script type="module">
  import { openModal } from "{% static 'js/modal.js' %}";
  document.getElementById("preview-open").addEventListener("click", () => {
    const scope = document.getElementById("preview-scope").value;
    const tied = document.getElementById("preview-tied").value;
    openModal(`{% url 'announcements:preview' %}?scope=${scope}&tied=${tied}`);
  });
</script>
```

Como el `<section>` cuelga **fuera** del `<form method="post">` original, los selects no se envían al guardar premios. El confetti se dispara solo por el `MutationObserver` ya existente en `static/js/winner-confetti.js` (sin cambios).

### 4.5. URLs

En `announcements/urls.py`:

```python
urlpatterns = [
    path("preview/", AnnouncementPreviewView.as_view(), name="preview"),
    path("<int:pk>/", AnnouncementModalView.as_view(), name="modal"),
    path("<int:pk>/seen", AnnouncementSeenView.as_view(), name="seen"),
]
```

Orden importa: `preview/` antes de `<int:pk>/` para evitar colisión.

## 5. Reglas de negocio y casos borde

- **No gestor** → redirect 302 a `competicion:dashboard` (vía `GestorRequiredMixin`). Test cubre.
- **Edge: solo existe el propio gestor en la BD.** En `tied=1` se cae a un único ganador (la lista de `User` queda con 1 elemento) y `tied` se ajusta a `False` para no mentir en el copy "Empate en la cima". Documentado en el helper.
- **Edge: no hay rondas KO en BD.** En `scope=round`, se cae a `Round.objects.first()` (groups) y se sigue mostrando — preview no debe romper nunca.
- **`points` y `share`** son ficticios pero coherentes: `points=12`, `share` derivado del `PotSettings.matchday_winner_prize` actual (lo importante es que el formato visual sea fiel; el número exacto no es crítico).
- **No persistencia.** En tests: `assert WinnerAnnouncement.objects.count() == 0` antes y después.
- **No marca como visto.** En tests: `assert WinnerAnnouncementSeen.objects.count() == 0`.
- **Confetti** se dispara igual que en el modal real (no hay que hacer nada — el observer reacciona a `.winner-modal`).

## 6. Tests (TDD)

Archivo: `announcements/tests/test_preview.py`.

Casos:

1. `test_preview_requires_gestor` — jugador normal: respuesta 302 hacia `competicion:dashboard`.
2. `test_preview_matchday_single_renders_current_user` — gestor, `scope=matchday&tied=0`: 200, HTML contiene su nombre, no contiene `data-seen-url`.
3. `test_preview_matchday_tied_renders_two_winners` — gestor + un segundo `User` creado en el test: HTML lista 2 nombres y el copy "Empate en la cima".
4. `test_preview_round_uses_first_ko_round` — fixture con rondas: el título contiene la `label` de la primera ronda KO.
5. `test_preview_global` — título "¡Campeón del Mundial!".
6. `test_preview_does_not_persist` — antes y después, `WinnerAnnouncement.objects.count() == 0` y `WinnerAnnouncementSeen.objects.count() == 0`.
7. `test_preview_share_uses_pot_settings` — fija `matchday_winner_prize=50` y crea un segundo user; con `tied=0` el HTML muestra `50.00 €`, con `tied=1` muestra `25.00 €`.
8. `test_preview_unknown_scope_returns_404` — `?scope=bogus` → 404.

## 7. Riesgos y mitigaciones

- **Riesgo:** un futuro cambio en `_winner_modal.html` rompe el flujo real al añadir lógica de preview. **Mitigación:** los `{% if preview %}` están localizados y los tests del flujo real (en `test_views.py`) siguen pasando sin tocarse — la rama por defecto es la del flujo real.
- **Riesgo:** alguien intenta acceder a `/announcements/preview/?scope=...` sin ser gestor para ver datos de otros usuarios. **Mitigación:** `GestorRequiredMixin` + la vista solo usa `request.user` y un `User` arbitrario para el empate (no expone PII selectiva).
- **Riesgo:** el segundo ganador en `tied=1` siempre es el mismo (orden alfabético). **Mitigación aceptada:** es solo una previsualización; si molesta, se puede aleatorizar más adelante.
