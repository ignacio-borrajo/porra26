# Plan — Modal unificado de resultados

Spec: `docs/superpowers/specs/2026-06-02-resultados-modal-design.md`.

## Orden de ejecución

1. **Backend / servicio + tests del helper** (T1)
2. **Vista `ResultOfficialView` + tests vista** (T2)
3. **Templates (`_official_modal.html` + `manage_results.html`)** (T3)
4. **Verificación manual + suite completa** (T4)

T1, T2, T3 son independientes a nivel de archivo (no se tocan los mismos archivos), pero T2 depende de T1 (importa `next_pending_result_match`). T3 puede correr en paralelo con T1+T2. T4 sólo después de los tres.

---

## T1 — Helper `next_pending_result_match` + `pending_result_matches_count`

**Archivo:** `competition/services/predictions.py`

Añadir al final del archivo:

```python
def _result_candidates(after_match=None):
    qs = Match.objects.filter(result_home__isnull=True).select_related("round")
    if after_match is not None:
        qs = qs.exclude(pk=after_match.pk)
    return qs.order_by("kickoff", "pk")


def next_pending_result_match(after_match=None) -> Match | None:
    for m in _result_candidates(after_match=after_match):
        if m.status in ("closed", "live"):
            return m
    return None


def pending_result_matches_count() -> int:
    return sum(1 for m in _result_candidates() if m.status in ("closed", "live"))
```

**Tests:** `competition/tests/test_pending_result_match.py` (nuevo).
- Usar `competition/tests/factories.py` existente para crear `Match`, `Team`, `Round`.
- Cubrir los 3 casos descritos en spec §6 (puntos 1-3).
- Para forzar `status`, manipular `kickoff` con `timezone.now() + timedelta(...)`.

**Verificación:**
```bash
pytest competition/tests/test_pending_result_match.py -v
```

---

## T2 — `ResultOfficialView` con chain + headers modal

**Archivo:** `competition/views.py` (sustituir `ResultOfficialView`).

Reemplazar GET y POST según spec §5.3.

- GET añade `pending_count` y `has_next` al contexto.
- POST acepta `chain=1` y responde `204 + X-Modal-Next` o `200 + X-Modal-Redirect`.
- POST sin `chain` mantiene `redirect("competicion:manage_results")` para compatibilidad con la suite existente (`messages.success` se preserva).

**Tests:** `competition/tests/test_official_view_modal.py` (nuevo).
- Cubrir spec §6 puntos 4, 5, 6, 7.
- Usar `Client` Django con un `User` con `is_gestor=True`.
- Comprobar:
  - GET: `response.context["pending_count"]`, `response.context["has_next"]`, y que el body no contiene `<html` (es fragmento).
  - POST `chain=1` y hay siguiente: `response.status_code == 204`, header `X-Modal-Next` apunta al siguiente.
  - POST `chain=1` y no hay siguiente: `status_code == 200`, header `X-Modal-Redirect == "/competicion/resultados/"` (usar `reverse`).
  - POST sin chain: redirect 302 a `manage_results`.

**Verificación:**
```bash
pytest competition/tests/test_official_view_modal.py -v
```

**Dependencia:** T1 (importa helpers nuevos).

---

## T3 — Templates: modal real + enlaces con `data-modal-url`

**Archivo 1:** `templates/competition/_official_modal.html` (reescritura completa).
- Copiar la estructura de spec §5.1 al pie de la letra.
- `{% load icons %}` en línea con el botón ×. Verificar que el filtro `icons` y el icono `"x"` existen (`_detail_modal.html` ya los usa).
- **No** extender `base.html`.

**Archivo 2:** `templates/competition/manage_results.html`.
- En las tres listas (`pending`, `upcoming`, `done`) el botón Finalizar/Editar debe llevar **ambos** atributos: `href="{% url 'competicion:official' m.id %}"` y `data-modal-url="{% url 'competicion:official' m.id %}"`.
- No tocar el botón "PDF" ni la tabla de reportes.

**Test (smoke, opcional, integrar en `test_official_view_modal.py`):**
- GET `/competicion/resultados/` (cliente gestor) con al menos un partido `closed`.
- Assert que el HTML contiene `data-modal-url="/competicion/resultados/<id>/"`.

**Verificación manual:** ver T4.

**Sin dependencias técnicas con T1/T2** (sólo se beneficia visualmente si la vista está actualizada). Puede ejecutarse en paralelo.

---

## T4 — Verificación end-to-end

1. Lanzar la suite completa: `pytest -q`.
2. Arrancar el server local: `python manage.py runserver` (asumir env ya configurado, sino seed: `python manage.py seed_demo` si existe).
3. Login como gestor, visitar `/competicion/resultados/`.
4. Marcar un partido en estado `closed` o `live`, click "Finalizar" → debe aparecer modal con overlay desenfocado.
5. Usar +/- en ambos inputs, confirmar que el valor sube/baja.
6. Click "Guardar y siguiente" → debe abrirse modal del siguiente sin recarga.
7. Repetir hasta agotar pendientes → debe volver a `/competicion/resultados/`.
8. ESC y click fuera deben cerrar la modal.
9. Editar un partido `done` desde la lista → mismo modal, valores precargados con el resultado actual; al guardar recalcula puntos.

Si todo OK, commit final.
