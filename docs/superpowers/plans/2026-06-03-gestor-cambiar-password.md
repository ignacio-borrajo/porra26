# Gestor cambia contraseña de un jugador — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Permitir a un gestor establecer una contraseña concreta para cualquier usuario (con sugerencia generada que cumple las reglas), forzando cambio al próximo login excepto cuando se la cambia a sí mismo.

**Architecture:** Vista nueva `SetPasswordView` en la app `pot` con form propio (sin `current`), expuesta en `/jugadores/<pk>/contrasena/`. Botón con icono `lock` en la tabla de jugadores abre un modal pre-rellenado. Auditoría con acción nueva `password_set_by_manager`.

**Tech Stack:** Django 5.1, pytest-django, factory_boy, sistema de modales propio (`X-Modal`, `X-Modal-Redirect`, `X-Modal-Errors`).

**Spec:** `docs/superpowers/specs/2026-06-03-gestor-cambiar-password-design.md`

**Worktree:** `.claude/worktrees/gestor-set-password` (rama `worktree-gestor-set-password`).

**Python:** Usa el venv del repo principal: `/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python`. Para ahorrar tipeo, alias mental: `PY=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python`.

---

## File Structure

| Archivo | Acción | Responsabilidad |
|--------|--------|-----------------|
| `pot/forms.py` | modificar | Añadir `generate_suggested_password()` y clase `SetPlayerPasswordForm` |
| `pot/views.py` | modificar | Añadir `SetPasswordView` + imports nuevos |
| `pot/urls.py` | modificar | Añadir ruta `player_set_password` |
| `templates/pot/_password_set_modal.html` | crear | Modal con dos inputs + acciones "Sugerir otra" / "Mostrar" |
| `templates/pot/manage_players.html` | modificar | Añadir botón lock en columna de acciones |
| `pot/tests/test_set_password.py` | crear | 11 tests (forma + vista) |

---

## Task 1: Helper `generate_suggested_password()`

**Files:**
- Modify: `pot/forms.py`
- Test: `pot/tests/test_set_password.py` (crear archivo en esta tarea)

- [ ] **Step 1: Crear el archivo de tests con el primer test del helper**

Crear `pot/tests/test_set_password.py` con:

```python
import re

from pot.forms import generate_suggested_password


def test_generate_suggested_password_meets_rules():
    for _ in range(50):
        pwd = generate_suggested_password()
        assert len(pwd) >= 10
        assert any(ch.isupper() for ch in pwd)
        assert any(ch.isdigit() for ch in pwd)
        # No espacios ni caracteres raros que rompan al copiarla en un correo.
        assert re.fullmatch(r"[A-Za-z0-9!@#$%&*?-]+", pwd)


def test_generate_suggested_password_is_not_deterministic():
    samples = {generate_suggested_password() for _ in range(20)}
    assert len(samples) >= 18  # entropía suficiente
```

- [ ] **Step 2: Ejecutar el test y verificar que falla**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: `ImportError: cannot import name 'generate_suggested_password' from 'pot.forms'`.

- [ ] **Step 3: Implementar el helper en `pot/forms.py`**

En la parte baja del archivo, justo después de `generate_temp_password`, añadir:

```python
def generate_suggested_password() -> str:
    """Devuelve una contraseña aleatoria que siempre cumple las reglas
    del SetPlayerPasswordForm (>=10, una mayúscula, un dígito)."""
    alphabet = "abcdefghijkmnopqrstuvwxyz"  # sin 'l' por legibilidad
    uppers = "ABCDEFGHJKLMNPQRSTUVWXYZ"  # sin 'I', 'O'
    digits = "23456789"  # sin '0', '1'
    symbols = "!@#$%&*?-"
    pool = alphabet + uppers + digits + symbols
    body = [secrets.choice(pool) for _ in range(9)]
    body.extend([
        secrets.choice(uppers),
        secrets.choice(digits),
        secrets.choice(alphabet),
    ])
    secrets.SystemRandom().shuffle(body)
    return "".join(body)
```

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: ambos tests PASS.

- [ ] **Step 5: Commit**

```bash
git add pot/forms.py pot/tests/test_set_password.py
git commit -m "feat(pot): generador de contraseña sugerida que cumple reglas"
```

---

## Task 2: Form `SetPlayerPasswordForm`

**Files:**
- Modify: `pot/forms.py`
- Test: `pot/tests/test_set_password.py`

- [ ] **Step 1: Añadir tests del form**

Al final de `pot/tests/test_set_password.py`:

```python
import pytest

from pot.forms import SetPlayerPasswordForm


def _data(new1="Abcdefghi1", new2=None):
    return {"new1": new1, "new2": new2 if new2 is not None else new1}


def test_set_player_password_form_valid():
    form = SetPlayerPasswordForm(data=_data())
    assert form.is_valid(), form.errors


def test_set_player_password_form_min_length():
    form = SetPlayerPasswordForm(data=_data(new1="Abc1", new2="Abc1"))
    assert not form.is_valid()
    assert "new1" in form.errors


def test_set_player_password_form_requires_upper_and_digit():
    form = SetPlayerPasswordForm(data=_data(new1="abcdefghij", new2="abcdefghij"))
    assert not form.is_valid()
    assert any("mayúscula" in e for e in form.errors.get("__all__", []))


def test_set_player_password_form_requires_digit_when_upper_present():
    form = SetPlayerPasswordForm(data=_data(new1="Abcdefghij", new2="Abcdefghij"))
    assert not form.is_valid()
    assert any("mayúscula" in e for e in form.errors.get("__all__", []))


def test_set_player_password_form_mismatch():
    form = SetPlayerPasswordForm(data=_data(new1="Abcdefghi1", new2="Abcdefghi2"))
    assert not form.is_valid()
    assert any("no coinciden" in e for e in form.errors.get("__all__", []))


def test_set_player_password_form_renders_value_for_re_render():
    # PasswordInput por defecto oculta el value tras un POST inválido.
    # Aquí queremos preservar lo tecleado: render_value=True.
    form = SetPlayerPasswordForm(initial={"new1": "Hola12345A", "new2": "Hola12345A"})
    html = form.as_p()
    assert 'value="Hola12345A"' in html
```

- [ ] **Step 2: Ejecutar y verificar que fallan los 6 tests nuevos**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: `ImportError: cannot import name 'SetPlayerPasswordForm' from 'pot.forms'`.

- [ ] **Step 3: Implementar el form en `pot/forms.py`**

Añadir al final del archivo:

```python
class SetPlayerPasswordForm(forms.Form):
    new1 = forms.CharField(
        label="Nueva contraseña",
        min_length=10,
        widget=forms.PasswordInput(attrs={"class": "input"}, render_value=True),
    )
    new2 = forms.CharField(
        label="Repite la contraseña",
        min_length=10,
        widget=forms.PasswordInput(attrs={"class": "input"}, render_value=True),
    )

    def clean(self):
        c = super().clean()
        if c.get("new1") and c.get("new2") and c["new1"] != c["new2"]:
            raise forms.ValidationError("Las dos contraseñas no coinciden.")
        if c.get("new1"):
            pwd = c["new1"]
            if not any(ch.isupper() for ch in pwd) or not any(ch.isdigit() for ch in pwd):
                raise forms.ValidationError(
                    "La contraseña debe tener al menos una mayúscula y un dígito."
                )
        return c
```

- [ ] **Step 4: Ejecutar y verificar que pasan**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add pot/forms.py pot/tests/test_set_password.py
git commit -m "feat(pot): SetPlayerPasswordForm con validación y render_value"
```

---

## Task 3: URL + esqueleto de la vista (devuelve 404/200 vacío)

Para poder testear la vista necesitamos URL y vista mínima. Hacemos el "esqueleto" primero y luego añadimos cada comportamiento con su test.

**Files:**
- Modify: `pot/urls.py`
- Modify: `pot/views.py`
- Create: `templates/pot/_password_set_modal.html`
- Test: `pot/tests/test_set_password.py`

- [ ] **Step 1: Añadir test de permisos**

Al final de `pot/tests/test_set_password.py`:

```python
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_get_requires_gestor(client):
    client.force_login(UserFactory())
    target = UserFactory()
    r = client.get(reverse("pot:player_set_password", args=[target.id]))
    assert r.status_code == 302  # redirect a dashboard
```

- [ ] **Step 2: Ejecutar y verificar que falla**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py::test_get_requires_gestor -v
```

Esperado: `NoReverseMatch: Reverse for 'player_set_password' not found`.

- [ ] **Step 3: Añadir la ruta**

En `pot/urls.py`, dentro de `urlpatterns`, justo después de la línea de `player_reveal`:

```python
    path(
        "jugadores/<int:pk>/contrasena/",
        views.SetPasswordView.as_view(),
        name="player_set_password",
    ),
```

- [ ] **Step 4: Añadir esqueleto de vista en `pot/views.py`**

Imports adicionales al inicio del archivo (después de los `from django.shortcuts import ...`):

```python
from django.contrib.auth import update_session_auth_hash
from django.http import HttpResponse, JsonResponse
```

(Nota: `HttpResponse` ya está importado — comprueba antes de duplicar. Si ya existe, deja solo `update_session_auth_hash` y `JsonResponse`.)

Añadir esta vista al final del archivo:

```python
class SetPasswordView(GestorRequiredMixin, View):
    template_name = "pot/_password_set_modal.html"

    def _is_modal(self, request) -> bool:
        return request.headers.get("X-Modal") == "1"

    def _ctx(self, request, player, form):
        return {
            "form": form,
            "player": player,
            "is_self": player.id == request.user.id,
            "modal": self._is_modal(request),
        }

    def get(self, request, pk):
        player = get_object_or_404(User, pk=pk)
        if request.GET.get("suggest") == "1":
            return JsonResponse({"password": generate_suggested_password()})
        suggested = generate_suggested_password()
        form = SetPlayerPasswordForm(initial={"new1": suggested, "new2": suggested})
        return render(request, self.template_name, self._ctx(request, player, form))

    def post(self, request, pk):
        player = get_object_or_404(User, pk=pk)
        form = SetPlayerPasswordForm(request.POST)
        if not form.is_valid():
            response = render(request, self.template_name, self._ctx(request, player, form))
            if self._is_modal(request):
                response["X-Modal-Errors"] = "1"
            return response

        is_self = player.id == request.user.id
        player.set_password(form.cleaned_data["new1"])
        player.must_change_password = not is_self
        player.save(update_fields=["password", "must_change_password"])
        if is_self:
            update_session_auth_hash(request, player)
        AuditLog.objects.create(
            actor=request.user,
            action="password_set_by_manager",
            target_type="user",
            target_id=str(player.id),
            payload={"self": is_self},
        )
        messages.success(request, "Contraseña actualizada.")
        target = reverse("pot:manage_players")
        if self._is_modal(request):
            response = HttpResponse(status=200)
            response["X-Modal-Redirect"] = target
            return response
        return redirect(target)
```

Imports que la vista necesita y que **ya existen** en el archivo: `messages`, `redirect`, `render`, `reverse`, `View`, `GestorRequiredMixin`, `AuditLog`, `User`, `get_object_or_404`. Verifica.

Imports que **hay que añadir** de `pot.forms`: en la línea `from pot.forms import PlayerForm, generate_temp_password`, ampliar a:

```python
from pot.forms import (
    PlayerForm,
    SetPlayerPasswordForm,
    generate_suggested_password,
    generate_temp_password,
)
```

- [ ] **Step 5: Crear plantilla mínima**

Crear `templates/pot/_password_set_modal.html` con contenido mínimo para que `render` no explote (la rellenamos en Task 4):

```html
{% load icons %}
<section class="glass pop" style="width:min(520px,100%);border-radius:28px;padding:28px;background:var(--surface-solid)">
  <header style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <div>
      <span class="eyebrow">Contraseña</span>
      <h2 class="display" style="margin:6px 0 0;font-size:22px">Nueva contraseña de {{ player.name }}</h2>
    </div>
    <button type="button" data-modal-close class="btn btn-ghost" style="width:38px;height:38px;padding:0;border-radius:12px">{% icon "x" width=14 %}</button>
  </header>
  <form method="post" action="{% url 'pot:player_set_password' player.id %}">
    {% csrf_token %}
    <p>placeholder</p>
  </form>
</section>
```

- [ ] **Step 6: Ejecutar el test de permisos y verificar que pasa**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py::test_get_requires_gestor -v
```

Esperado: PASS.

También corre la suite entera para no romper nada:

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest -q
```

Esperado: 282 + nuevos tests, 0 fallos.

- [ ] **Step 7: Commit**

```bash
git add pot/urls.py pot/views.py pot/forms.py templates/pot/_password_set_modal.html pot/tests/test_set_password.py
git commit -m "feat(pot): ruta y vista esqueleto para set password (sólo permisos)"
```

---

## Task 4: GET renderiza modal con sugerencia + endpoint `?suggest=1`

**Files:**
- Test: `pot/tests/test_set_password.py`

(La vista ya implementa estos dos comportamientos; sólo añadimos tests que los blindan.)

- [ ] **Step 1: Añadir tests**

Al final de `pot/tests/test_set_password.py`:

```python
import json


@pytest.mark.django_db
def test_get_renders_modal_with_suggestion(client):
    client.force_login(GestorFactory())
    target = UserFactory()
    r = client.get(
        reverse("pot:player_set_password", args=[target.id]),
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert b"<html" not in r.content.lower()  # es fragmento
    assert target.name.encode() in r.content
    # La sugerencia llega pre-rellenada en ambos inputs.
    body = r.content.decode()
    assert body.count('name="new1"') == 1
    assert 'value="' in body  # algún value sugerido


@pytest.mark.django_db
def test_get_suggest_returns_json(client):
    client.force_login(GestorFactory())
    target = UserFactory()
    r = client.get(
        reverse("pot:player_set_password", args=[target.id]) + "?suggest=1"
    )
    assert r.status_code == 200
    assert r["Content-Type"].startswith("application/json")
    payload = json.loads(r.content)
    pwd = payload["password"]
    assert len(pwd) >= 10
    assert any(ch.isupper() for ch in pwd)
    assert any(ch.isdigit() for ch in pwd)


@pytest.mark.django_db
def test_get_404_for_unknown_user(client):
    client.force_login(GestorFactory())
    r = client.get(reverse("pot:player_set_password", args=[99999]))
    assert r.status_code == 404
```

- [ ] **Step 2: Ejecutar y verificar que pasan**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: todos PASS. (Si falla `value="`, revisa que el `initial` se aplica al widget — debería gracias a `render_value=True` del Task 2.)

- [ ] **Step 3: Commit**

```bash
git add pot/tests/test_set_password.py
git commit -m "test(pot): GET renderiza modal con sugerencia + endpoint JSON"
```

---

## Task 5: POST cambia contraseña + auditoría + comportamiento self vs others

**Files:**
- Test: `pot/tests/test_set_password.py`

- [ ] **Step 1: Añadir tests del POST**

Al final de `pot/tests/test_set_password.py`:

```python
from accounts.models import AuditLog


@pytest.mark.django_db
def test_post_valid_changes_password_and_forces_change(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory(must_change_password=False)
    old_hash = target.password
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Nueva1234X", "new2": "Nueva1234X"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Redirect") == reverse("pot:manage_players")
    target.refresh_from_db()
    assert target.password != old_hash
    assert target.check_password("Nueva1234X")
    assert target.must_change_password is True
    log = AuditLog.objects.get(action="password_set_by_manager", target_id=str(target.id))
    assert log.actor_id == g.id
    assert log.payload == {"self": False}


@pytest.mark.django_db
def test_post_self_does_not_force_change_and_keeps_session(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    r = client.post(
        reverse("pot:player_set_password", args=[g.id]),
        {"new1": "MiNueva1Pwd", "new2": "MiNueva1Pwd"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    g.refresh_from_db()
    assert g.check_password("MiNueva1Pwd")
    assert g.must_change_password is False
    log = AuditLog.objects.get(action="password_set_by_manager", target_id=str(g.id))
    assert log.payload == {"self": True}
    # Sesión sigue activa: una vista protegida responde 200.
    r2 = client.get(reverse("pot:manage_players"))
    assert r2.status_code == 200


@pytest.mark.django_db
def test_post_mismatch_re_renders_with_errors(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory()
    old_hash = target.password
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Abcdefghi1", "new2": "Abcdefghi2"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Errors") == "1"
    target.refresh_from_db()
    assert target.password == old_hash
    assert not AuditLog.objects.filter(action="password_set_by_manager").exists()


@pytest.mark.django_db
def test_post_short_password_re_renders(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory()
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Abc1", "new2": "Abc1"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Errors") == "1"


@pytest.mark.django_db
def test_post_no_uppercase_re_renders(client):
    g = GestorFactory()
    client.force_login(g)
    target = UserFactory()
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "abcdefghij1", "new2": "abcdefghij1"},
        HTTP_X_MODAL="1",
    )
    assert r.status_code == 200
    assert r.get("X-Modal-Errors") == "1"


@pytest.mark.django_db
def test_post_requires_gestor(client):
    client.force_login(UserFactory())
    target = UserFactory()
    r = client.post(
        reverse("pot:player_set_password", args=[target.id]),
        {"new1": "Nueva1234X", "new2": "Nueva1234X"},
    )
    assert r.status_code == 302
    target.refresh_from_db()
    assert not target.check_password("Nueva1234X")
```

- [ ] **Step 2: Ejecutar y verificar que pasan**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: todos PASS.

- [ ] **Step 3: Commit**

```bash
git add pot/tests/test_set_password.py
git commit -m "test(pot): POST set_password (valid/self/mismatch/short/upper/permisos)"
```

---

## Task 6: Plantilla `_password_set_modal.html` con UI completa

**Files:**
- Modify: `templates/pot/_password_set_modal.html`

- [ ] **Step 1: Reescribir la plantilla con la UI final**

Reemplazar el contenido completo de `templates/pot/_password_set_modal.html` por:

```html
{% load icons %}
<section class="glass pop" style="width:min(520px,100%);border-radius:28px;padding:28px;background:var(--surface-solid)">
  <header style="display:flex;align-items:center;justify-content:space-between;margin-bottom:20px">
    <div>
      <span class="eyebrow">Contraseña</span>
      <h2 class="display" style="margin:6px 0 0;font-size:22px">Nueva contraseña de {{ player.name }}</h2>
    </div>
    <button type="button" data-modal-close class="btn btn-ghost" style="width:38px;height:38px;padding:0;border-radius:12px">{% icon "x" width=14 %}</button>
  </header>

  <form method="post" action="{% url 'pot:player_set_password' player.id %}" data-set-password-form>
    {% csrf_token %}
    <p class="mono" style="margin:0 0 16px;font-size:11.5px;color:var(--text-faint);padding:10px 12px;border-radius:10px;background:var(--surface-hi)">
      {% if is_self %}
        Estás cambiando tu propia contraseña. No se te pedirá cambiarla de nuevo al entrar.
      {% else %}
        Hemos generado una contraseña que cumple las reglas. Cópiala o teclea otra. Se forzará al jugador a cambiarla en su próximo acceso.
      {% endif %}
    </p>

    <div style="display:flex;flex-direction:column;gap:14px">
      <div class="field">
        <label for="id_new1">Nueva contraseña</label>
        {{ form.new1 }}
        {% for e in form.new1.errors %}<p style="color:var(--c-red);font-size:12px">{{ e }}</p>{% endfor %}
      </div>
      <div class="field">
        <label for="id_new2">Repite la contraseña</label>
        {{ form.new2 }}
        {% for e in form.new2.errors %}<p style="color:var(--c-red);font-size:12px">{{ e }}</p>{% endfor %}
      </div>
      {% if form.non_field_errors %}
        <p style="color:var(--c-red);font-size:12px;margin:0">{{ form.non_field_errors|join:" " }}</p>
      {% endif %}
    </div>

    <div style="display:flex;gap:8px;margin-top:12px;flex-wrap:wrap">
      <button type="button" class="btn btn-ghost" data-suggest-url="{% url 'pot:player_set_password' player.id %}?suggest=1" style="padding:6px 12px;font-size:12px">
        {% icon "lock" width=12 %} Sugerir otra
      </button>
      <button type="button" class="btn btn-ghost" data-toggle-reveal style="padding:6px 12px;font-size:12px">
        Mostrar / ocultar
      </button>
    </div>

    <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:22px">
      <button type="button" data-modal-close class="btn btn-ghost">Cancelar</button>
      <button class="btn btn-primary" type="submit">Guardar contraseña</button>
    </div>
  </form>

  <script>
    (() => {
      const root = document.currentScript.parentElement;
      const form = root.querySelector("[data-set-password-form]");
      if (!form) return;
      const new1 = form.querySelector('input[name="new1"]');
      const new2 = form.querySelector('input[name="new2"]');

      const suggest = form.querySelector("[data-suggest-url]");
      if (suggest) {
        suggest.addEventListener("click", async () => {
          const r = await fetch(suggest.dataset.suggestUrl, { headers: { "X-Modal": "1" } });
          if (!r.ok) return;
          const { password } = await r.json();
          new1.value = password;
          new2.value = password;
        });
      }

      const reveal = form.querySelector("[data-toggle-reveal]");
      if (reveal) {
        reveal.addEventListener("click", () => {
          const next = new1.type === "password" ? "text" : "password";
          new1.type = next;
          new2.type = next;
        });
      }
    })();
  </script>
</section>
```

- [ ] **Step 2: Smoke-check manual del template renderizado**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py -v
```

Esperado: todos los tests siguen verdes. Concretamente `test_get_renders_modal_with_suggestion` valida el nombre del jugador y la presencia de un `value="..."` pre-rellenado.

- [ ] **Step 3: Commit**

```bash
git add templates/pot/_password_set_modal.html
git commit -m "feat(pot): plantilla del modal de set password con sugerir/ocultar"
```

---

## Task 7: Botón "lock" en la tabla de jugadores

**Files:**
- Modify: `templates/pot/manage_players.html`
- Test: `pot/tests/test_set_password.py`

- [ ] **Step 1: Añadir test de integración**

Al final de `pot/tests/test_set_password.py`:

```python
@pytest.mark.django_db
def test_manage_players_renders_set_password_button(client):
    client.force_login(GestorFactory())
    target = UserFactory(name="Adelaida Plumífera")
    r = client.get(reverse("pot:manage_players"))
    assert r.status_code == 200
    expected_url = reverse("pot:player_set_password", args=[target.id])
    assert expected_url.encode() in r.content
```

- [ ] **Step 2: Ejecutar y verificar que falla**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py::test_manage_players_renders_set_password_button -v
```

Esperado: FAIL — la URL del botón no está en el HTML todavía.

- [ ] **Step 3: Añadir el botón a `templates/pot/manage_players.html`**

Localiza el bloque de acciones (líneas 40-46, dentro del `for p in players`):

```html
    <div style="display:flex;gap:6px">
      <button class="btn btn-ghost" data-modal-url="{% url 'pot:player_edit' p.id %}" style="width:32px;height:32px;padding:0">{% icon "edit" width=14 %}</button>
      <form method="post" action="{% url 'pot:player_toggle_active' p.id %}" style="display:inline">
        {% csrf_token %}
        <button class="btn btn-ghost" style="width:32px;height:32px;padding:0">{% if p.is_active %}{% icon "x" width=14 %}{% else %}{% icon "check" width=14 %}{% endif %}</button>
      </form>
    </div>
```

Inserta un **nuevo botón con el icono `lock`** entre el botón de Editar y el `<form>` del toggle active. El bloque resultante queda:

```html
    <div style="display:flex;gap:6px">
      <button class="btn btn-ghost" data-modal-url="{% url 'pot:player_edit' p.id %}" style="width:32px;height:32px;padding:0" title="Editar">{% icon "edit" width=14 %}</button>
      <button class="btn btn-ghost" data-modal-url="{% url 'pot:player_set_password' p.id %}" style="width:32px;height:32px;padding:0" title="Cambiar contraseña">{% icon "lock" width=14 %}</button>
      <form method="post" action="{% url 'pot:player_toggle_active' p.id %}" style="display:inline">
        {% csrf_token %}
        <button class="btn btn-ghost" style="width:32px;height:32px;padding:0" title="{{ p.is_active|yesno:'Dar de baja,Reactivar' }}">{% if p.is_active %}{% icon "x" width=14 %}{% else %}{% icon "check" width=14 %}{% endif %}</button>
      </form>
    </div>
```

Cambios: nuevo botón de lock + un par de `title=` para accesibilidad mínima.

Antes de modificar la columna de acciones revisa también la cabecera (línea 16). El grid es `2.4fr 1.6fr 0.8fr 1fr 1.1fr 90px`. La última columna está a 90 px y aguanta 3 botones de 32 px. **No hay que tocar el grid**: 3·32 + 2·6 (gap) = 108 px se desbordan. Ajustar el último valor a `110px` (ya que el último botón es una `<form>` que añade margen mínimo) o, más seguro, a `120px`. **Decisión**: cambiar el último valor del `grid-template-columns` en cabecera (línea 16) y en cada fila (línea 20) de `90px` a `120px`.

- [ ] **Step 4: Ejecutar el test y verificar que pasa**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest pot/tests/test_set_password.py::test_manage_players_renders_set_password_button -v
```

Esperado: PASS. Lanza también `pytest -q` por si rompimos otra cosa.

- [ ] **Step 5: Smoke visual manual (opcional pero recomendado)**

Si tienes el server local corriendo, abre `/pot/jugadores/` como gestor, comprueba que:
- El tercer botón (candado) aparece a la derecha del lápiz.
- Pulsarlo abre el modal con dos inputs pre-rellenados.
- "Sugerir otra" cambia los valores; "Mostrar / ocultar" los hace visibles.
- Guardar redirige y `must_change_password` queda en `True`.

- [ ] **Step 6: Commit**

```bash
git add templates/pot/manage_players.html pot/tests/test_set_password.py
git commit -m "feat(pot): botón lock en tabla de jugadores para set password"
```

---

## Task 8: Cierre — suite completa + lint

**Files:** ninguno nuevo. Verificación global.

- [ ] **Step 1: Suite completa**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m pytest -q
```

Esperado: 282 baseline + ~17 nuevos = ~299 tests, 0 fallos.

- [ ] **Step 2: Lint (ruff)**

```bash
/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m ruff check pot templates docs/superpowers/specs/2026-06-03-gestor-cambiar-password-design.md 2>/dev/null || /Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin/python -m ruff check pot
```

Esperado: `All checks passed!`. Si ruff señala issues legítimos en código añadido, corrégelos antes de continuar.

- [ ] **Step 3: Stagear y commitear el spec si todavía está untracked**

```bash
git status
```

Si `docs/superpowers/specs/2026-06-03-gestor-cambiar-password-design.md` aparece como untracked:

```bash
git add docs/superpowers/specs/2026-06-03-gestor-cambiar-password-design.md docs/superpowers/plans/2026-06-03-gestor-cambiar-password.md
git commit -m "docs(pot): spec y plan de set password por gestor"
```

(Si ya están commiteados de antes, salta este paso.)

- [ ] **Step 4: Reporte final**

Imprime un resumen al usuario:
- Tests añadidos y verdes.
- Archivos modificados.
- Commits creados (`git log worktree-gestor-set-password --oneline ^main`).
- Sugerir el siguiente paso: `finishing-a-development-branch` para abrir PR o merge.

---

## Notas de implementación

- **PasswordInput + render_value**: Django oculta los `value` de inputs `type=password` por defecto. Sin `render_value=True` el `initial={"new1": suggested}` no llega al HTML y el form aparece vacío. El test `test_set_player_password_form_renders_value_for_re_render` lo blinda.
- **`update_session_auth_hash`**: necesario sólo cuando `is_self`. Sin esto, cambiar la pwd cierra la sesión del propio gestor.
- **No exponer la temp en `_password_reveal.html`**: a diferencia del flujo de reset/alta, aquí el gestor ya conoce la pwd (la acaba de teclear). El redirect va directo a `manage_players`.
- **Worktree**: todo el trabajo sucede en `.claude/worktrees/gestor-set-password`. Para mover el spec dentro del worktree se usó `git stash` desde `main` (ya hecho antes de empezar la implementación).
