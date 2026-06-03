# Plan de implementación — Modal de "ganador de la jornada/fase" con confetti

Spec: `docs/superpowers/specs/2026-06-03-ganador-jornada-modal-design.md`
Branch: `worktree-ganador-jornada`

## Reglas de ejecución

- **TDD estricto**: en cada fase, escribir los tests **antes** que la implementación. Ejecutar `python manage.py test <app>` después de cada paso y confirmar que el resultado es el esperado (rojo → verde).
- **Una fase = uno o varios commits** con mensaje descriptivo (`feat(announcements): ...`, `test(...): ...`).
- **No mezclar fases**: terminar una y commitear antes de empezar la siguiente. Si una fase falla, **detenerse** y dejar la rama en el último estado verde.
- **Idioma de UI**: español de España, copiando exactamente los strings del spec §15.
- **Fidelidad al diseño**: glass/pop/tokens existentes; consultar `design-reference/styles.css` si hay duda visual.
- **NO tocar `pot/services/prizes.py`**: la otra sesión podría estar modificándolo.
- Trabajar siempre desde la rama `worktree-ganador-jornada` ya creada.

## Fase 0 — Arranque y scaffolding (sin código)

- [ ] Confirmar que el worktree está en la rama correcta: `git branch --show-current` → `worktree-ganador-jornada`.
- [ ] Confirmar que existe el spec en `docs/superpowers/specs/2026-06-03-ganador-jornada-modal-design.md` y este plan.
- [ ] Ejecutar la suite actual (`python manage.py test`) para tener una baseline verde antes de tocar nada.
- [ ] Commit inicial vacío si conviene como marcador: `git commit --allow-empty -m "chore: start ganador-jornada feature"`.

## Fase 1 — App `announcements` (modelos + migración)

1. **Crear scaffolding de la app**:
   - [ ] `python manage.py startapp announcements`.
   - [ ] Eliminar `views.py` autogenerado (creará el spec en Fase 4) **o** dejarlo vacío.
2. **Tests primero** (`announcements/tests/test_models.py`):
   - [ ] `test_announcement_str_for_matchday`.
   - [ ] `test_announcement_str_for_round`.
   - [ ] `test_announcement_str_for_global`.
   - [ ] `test_uniqueness_constraint_matchday` (segunda inserción con misma matchday → `IntegrityError`).
   - [ ] `test_uniqueness_constraint_round`.
   - [ ] `test_uniqueness_constraint_global`.
   - [ ] `test_seen_uniqueness_per_user`.
   - [ ] `test_title_property_singular_vs_plural` (tied → "Ganadores").
3. **Implementar** `announcements/models.py` según §5 del spec.
4. **Registrar app**:
   - [ ] Añadir `"announcements"` a `INSTALLED_APPS` en `porra26/settings.py`.
5. **Migración**:
   - [ ] `python manage.py makemigrations announcements`.
   - [ ] `python manage.py migrate`.
   - [ ] Verificar nombre `0001_initial.py`.
6. **Tests verdes**: `python manage.py test announcements`.
7. Commit: `feat(announcements): modelos WinnerAnnouncement y WinnerAnnouncementSeen`.

## Fase 2 — Servicio `detect_after_match`

1. **Tests primero** (`announcements/tests/test_services.py`) según spec §11:
   - [ ] `test_no_announcement_when_matchday_incomplete`.
   - [ ] `test_announcement_created_when_last_matchday_match_resolved`.
   - [ ] `test_announcement_created_for_round_ko` (usar `round_id="r16"`).
   - [ ] `test_global_announcement_created_only_after_final`.
   - [ ] `test_announcement_idempotent_on_second_resolve_call`.
   - [ ] `test_no_announcement_when_status_is_desierto`.
   - [ ] `test_tied_winners_persisted_with_tied_flag`.
   - [ ] `test_announcement_uses_matchday_winners_contract` (assertion sobre la firma esperada).
2. **Implementar** `announcements/services.py` según §6 del spec.
3. **Tests verdes**.
4. Commit: `feat(announcements): servicio detect_after_match`.

## Fase 3 — Hook en `resolve_match`

1. **Test de integración** primero (`announcements/tests/test_integration.py`):
   - [ ] `test_resolve_last_match_of_matchday_creates_announcement`.
   - [ ] `test_resolve_final_match_creates_both_round_and_global_announcements`.
   - [ ] `test_resolve_first_match_of_round_creates_no_announcement`.
2. **Modificar** `competition/services/resolve.py:resolve_match()` añadiendo, justo antes del fin de la transacción atómica:
   ```python
   from announcements.services import detect_after_match
   detect_after_match(match)
   ```
3. **Tests verdes** (incluye los de Fase 2).
4. Commit: `feat(competition): disparar detect_after_match en resolve_match`.

## Fase 4 — Vista del modal y vista "seen"

1. **Tests primero** (`announcements/tests/test_views.py`):
   - [ ] `test_modal_view_renders_for_authenticated_user`.
   - [ ] `test_modal_view_404_for_missing`.
   - [ ] `test_modal_view_requires_login`.
   - [ ] `test_seen_view_creates_record_and_returns_next_header`.
   - [ ] `test_seen_view_no_next_returns_204_no_header`.
   - [ ] `test_seen_view_idempotent` (2 POSTs no fallan y siguen devolviendo el mismo header).
   - [ ] `test_seen_view_requires_login`.
2. **Implementar**:
   - [ ] `announcements/views.py` con `AnnouncementModalView` y `AnnouncementSeenView` (§8.3 y §8.4 del spec).
   - [ ] `announcements/urls.py` (§8.2).
   - [ ] Incluir en `porra26/urls.py`: `path("anuncios/", include("announcements.urls"))`.
3. **Plantilla** `templates/announcements/_winner_modal.html` según §9.1.
4. **Tests verdes** + render manual: `python manage.py runserver` y comprobar `/anuncios/<id>/` (crear un anuncio en shell si hace falta).
5. Commit: `feat(announcements): vistas modal y seen + plantilla`.

## Fase 5 — Inyección en dashboard

1. **Tests** (extender `competition/tests/test_competition_view.py`):
   - [ ] `test_dashboard_passes_first_announcement_id_when_pending`.
   - [ ] `test_dashboard_omits_first_announcement_id_when_all_seen`.
   - [ ] `test_dashboard_first_announcement_id_is_oldest_pending`.
2. **Modificar** `competition/views.py:CompetitionView.get()` según §8.1 del spec.
3. **Modificar** `templates/competition/dashboard.html`:
   - [ ] Añadir el bloque `{% if first_announcement_id %}<script type="module">...openModal(...)</script>{% endif %}` dentro de `{% block scripts %}`.
4. **Tests verdes**.
5. Commit: `feat(competition): inyectar anuncios pendientes en el dashboard`.

## Fase 6 — Confetti (frontend)

1. **Vendorizar** `canvas-confetti`:
   - [ ] Crear `static/js/vendor/`.
   - [ ] Colocar en `static/js/vendor/canvas-confetti.min.js` la build minificada de `canvas-confetti` 1.9.x. Fuente preferida: https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js — descargar con `curl -L -o static/js/vendor/canvas-confetti.min.js https://cdn.jsdelivr.net/npm/canvas-confetti@1.9.3/dist/confetti.browser.min.js`. Verificar que el archivo expone `window.confetti`. Si por restricciones de red no es posible descargar, marcar el archivo como TODO y dejar el resto funcionando sin confetti (el modal sigue siendo válido).
2. **Crear** `static/js/winner-confetti.js`:
   ```js
   // Espera a que se monte un .winner-modal, dispara la celebración y gestiona el botón.
   function blast() {
     if (!window.confetti) return;
     window.confetti({ particleCount: 120, spread: 70, origin: { y: 0.4 } });
     const end = Date.now() + 2500;
     (function frame() {
       window.confetti({ particleCount: 4, angle: 270, spread: 60, startVelocity: 35, origin: { x: Math.random(), y: 0 }, gravity: 1.1 });
       if (Date.now() < end) requestAnimationFrame(frame);
     })();
   }

   const observer = new MutationObserver(() => {
     const modal = document.querySelector(".winner-modal:not([data-confetti-fired])");
     if (modal) {
       modal.setAttribute("data-confetti-fired", "1");
       setTimeout(blast, 80);
     }
   });
   observer.observe(document.body, { childList: true, subtree: true });

   document.addEventListener("click", async (event) => {
     const btn = event.target.closest("[data-winner-confirm]");
     if (!btn) return;
     const modal = btn.closest(".winner-modal");
     if (!modal) return;
     const url = modal.dataset.seenUrl;
     const res = await fetch(url, { method: "POST", headers: { "X-CSRFToken": getCSRF(), "X-Modal": "1" }, credentials: "same-origin" });
     const next = res.headers.get("X-Modal-Next");
     const { openModal, closeModal } = await import("/static/js/modal.js");
     if (next) {
       await openModal(next);
     } else {
       closeModal();
     }
   });

   function getCSRF() {
     const m = document.cookie.match(/csrftoken=([^;]+)/);
     return m ? m[1] : "";
   }
   ```
   > Ajusta la import path si el proyecto sirve `modal.js` con `{% static %}` (en ese caso, usar la URL emitida por Django, no `/static/js/modal.js` hardcoded — alternativa: dejar `openModal`/`closeModal` en `window` desde `modal.js`).
3. **Modificar** `templates/base.html` para incluir `canvas-confetti.min.js` (script clásico) y `winner-confetti.js` (módulo) después del `modal.js` existente.
4. **Tests**: no hay tests unitarios JS en el proyecto. Verificación manual:
   - [ ] Resolver el último partido de una jornada en local → entrar como jugador → ver el confetti.
   - [ ] Confirmar que al cerrar el modal se llama a `POST /anuncios/<id>/seen` (DevTools → Network).
5. Commit: `feat(announcements): confetti + cierre con marcado como visto`.

## Fase 7 — CSS

1. **Añadir** las reglas de §9.5 al **final** de `static/css/styles.css`. No tocar reglas existentes.
2. **Verificación visual manual** en tema claro y oscuro.
3. Commit: `style(announcements): estilos del modal de ganador`.

## Fase 8 — Verificación final

1. [ ] `python manage.py test` — toda la suite verde.
2. [ ] `python manage.py runserver` y validar a mano los 10 criterios de aceptación del §12 del spec.
3. [ ] `git log --oneline origin/main..HEAD` para revisar historial limpio.
4. [ ] `git push -u origin worktree-ganador-jornada`.
5. [ ] Abrir PR con `gh pr create` apuntando a `main`. Título: `feat(announcements): modal de ganador de jornada/fase con confetti`. Cuerpo: resumen + checklist de pruebas manuales del §12.

## Variables de entorno y dependencias

- **Sin nuevas dependencias Python**.
- **Sin nuevas dependencias JS** (canvas-confetti vendorizado, no es npm package).
- **Sin cambios de configuración** salvo `INSTALLED_APPS`.

## Coordinación con la otra sesión

- Antes de empezar Fase 8, hacer `git fetch origin main && git rebase origin/main`.
- Si el rebase introduce conflictos en `pot/services/prizes.py`, aceptar siempre la versión de `main`.
- Re-ejecutar todos los tests después del rebase.
- Si `matchday_winners` ha cambiado su firma o nombre, adaptar la única llamada en `announcements/services.py` y los tests que comprueban el contrato. **Documentar el cambio en el cuerpo del PR**.

## Pista para depuración rápida en local

Para forzar un anuncio sin tener que resolver 16 partidos, abrir shell:

```bash
python manage.py shell
>>> from announcements.models import WinnerAnnouncement
>>> from accounts.models import User
>>> a = WinnerAnnouncement.objects.create(scope_kind="matchday", scope_matchday=1, points=12, tied=False)
>>> a.winners.add(User.objects.first())
```

Luego entrar en `/competicion/` como cualquier usuario que no sea el creador del anuncio (o borrar `WinnerAnnouncementSeen` para verlo de nuevo).
