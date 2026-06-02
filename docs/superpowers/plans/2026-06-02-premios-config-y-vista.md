# Premios: configuración del gestor y vista pública — Plan de implementación

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que el gestor pueda configurar 1er/2º/3er premio y un importe único de "premio por ganador de jornada", que esos importes se reflejen en la página de Reglas, y que los gestores puedan llegar a la pantalla desde el menú.

**Architecture:** El singleton `PotSettings` gana un campo `matchday_winner_prize` (Decimal). El modelo `Prize` queda restringido al podio final (top 3 con `scope="global"`) — las filas con scope `matchday` y `round` sembradas en `0003_seed_prizes.py` se borran en una data migration. La vista `PrizesSettingsView` se reescribe para editar 3 importes de podio + 1 de jornada. La página de Reglas y la topbar se actualizan en consecuencia.

**Tech Stack:** Django 5.1 (vistas basadas en clases, migraciones, plantillas), pytest + pytest-django, CSS variables, sin JavaScript nuevo.

**Spec:** `docs/superpowers/specs/2026-06-02-premios-config-y-vista-design.md`

---

## File Structure

**Crear:**
- `pot/migrations/0004_potsettings_matchday_winner_prize.py` — schema migration añadiendo el campo.
- `pot/migrations/0005_drop_scoped_prizes.py` — data migration borrando filas `Prize` con scope distinto a `global`.
- `pot/tests/test_prizes_settings_view.py` — tests de la vista del gestor.
- `pot/tests/test_topbar_premios_link.py` — tests del nav-item en topbar.

**Modificar:**
- `pot/models.py` — añadir `matchday_winner_prize` a `PotSettings`.
- `pot/views.py` — reescribir `PrizesSettingsView.get` y `post`.
- `pot/migrations/0003_seed_prizes.py` — quitar la siembra de filas `matchday` y `round` (la data migration 0005 dejará la BD limpia incluso si alguien resetea).
- `pot/tests/test_seed.py` — ajustar el assert para reflejar que solo se siembran 3 premios globales.
- `templates/pot/prizes_settings.html` — rediseño completo.
- `core/views.py` — añadir `matchday_winner_prize` al contexto de `RulesView`.
- `templates/core/rules.html` — añadir la tarjeta de premio por jornada en la sección 03.
- `core/tests/test_rules_view.py` — añadir tests de la nueva tarjeta.
- `templates/partials/_topbar.html` — añadir `nav-item` "Premios" y refinar el active-state de "Jugadores".
- `static/css/styles.css` — clases CSS nuevas para `.rules-matchday-prize` y `.prizes-config`.
- `docs/DATA_MODEL.md` — actualizar §1 Pot/Settings.
- `/Users/ignacioborrajo/.claude/projects/-Users-ignacioborrajo-Documents-GitHub-apuestas-interna/memory/project_reglas_pagina.md` — añadir mención al nuevo premio.

---

## Task 1: Añadir campo `matchday_winner_prize` a `PotSettings`

**Files:**
- Modify: `pot/models.py`
- Create: `pot/migrations/0004_potsettings_matchday_winner_prize.py`
- Test: `pot/tests/test_pot_settings.py` (ampliar)

- [ ] **Step 1: Escribir test que falla**

Añadir al final de `pot/tests/test_pot_settings.py`:

```python
from decimal import Decimal


@pytest.mark.django_db
def test_matchday_winner_prize_defaults_to_zero():
    s = PotSettings.load()
    assert s.matchday_winner_prize == Decimal("0")


@pytest.mark.django_db
def test_matchday_winner_prize_is_persisted():
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("25.50")
    s.save()
    assert PotSettings.load().matchday_winner_prize == Decimal("25.50")
```

- [ ] **Step 2: Ejecutar tests, comprobar que fallan**

Run: `pytest pot/tests/test_pot_settings.py -v`
Expected: FAIL con `AttributeError: 'PotSettings' object has no attribute 'matchday_winner_prize'`.

- [ ] **Step 3: Añadir el campo al modelo**

Editar `pot/models.py`, dentro de la clase `PotSettings`, añadir tras `allowed_email_domains`:

```python
    matchday_winner_prize = models.DecimalField(
        max_digits=8, decimal_places=2, default=Decimal("0")
    )
```

- [ ] **Step 4: Generar migración**

Run: `python manage.py makemigrations pot --name potsettings_matchday_winner_prize`
Expected: crea `pot/migrations/0004_potsettings_matchday_winner_prize.py` con la operación `AddField`. Inspeccionar que el archivo contiene exactamente:

```python
from decimal import Decimal
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [("pot", "0003_seed_prizes")]
    operations = [
        migrations.AddField(
            model_name="potsettings",
            name="matchday_winner_prize",
            field=models.DecimalField(decimal_places=2, default=Decimal("0"), max_digits=8),
        ),
    ]
```

- [ ] **Step 5: Aplicar migración y ejecutar tests**

Run: `python manage.py migrate pot && pytest pot/tests/test_pot_settings.py -v`
Expected: PASS los 4 tests del archivo.

- [ ] **Step 6: Commit**

```bash
git add pot/models.py pot/migrations/0004_potsettings_matchday_winner_prize.py pot/tests/test_pot_settings.py
git commit -m "feat(pot): añade matchday_winner_prize a PotSettings"
```

---

## Task 2: Data migration para limpiar `Prize` con scope `matchday`/`round`

**Files:**
- Create: `pot/migrations/0005_drop_scoped_prizes.py`
- Modify: `pot/migrations/0003_seed_prizes.py`
- Modify: `pot/tests/test_seed.py`

- [ ] **Step 1: Ajustar el test de siembra para reflejar el nuevo contrato (solo 3 premios globales)**

Reemplazar el contenido de `pot/tests/test_seed.py` por:

```python
import pytest
from django.core.management import call_command

from pot.models import Prize


@pytest.mark.django_db
def test_seed_creates_only_global_prizes():
    call_command("loaddata", "fixtures/rounds.json")
    call_command("migrate", "pot", verbosity=0)
    globals_qs = Prize.objects.filter(scope="global").order_by("position")
    assert globals_qs.count() == 3
    assert [p.position for p in globals_qs] == [1, 2, 3]
    # Tras la data migration 0005 no debe quedar ningún premio scoped.
    assert Prize.objects.exclude(scope="global").count() == 0
```

- [ ] **Step 2: Ejecutar tests, comprobar que falla**

Run: `pytest pot/tests/test_seed.py -v`
Expected: FAIL — la siembra actual crea filas con scope `matchday` y `round`.

- [ ] **Step 3: Reducir la siembra a solo premios globales en `0003_seed_prizes.py`**

Editar `pot/migrations/0003_seed_prizes.py` y reemplazar la función `seed_prizes` por:

```python
def seed_prizes(apps, schema_editor):
    Prize = apps.get_model("pot", "Prize")
    PotSettings = apps.get_model("pot", "PotSettings")

    PotSettings.objects.get_or_create(pk=1, defaults={"per_player": Decimal("10.00")})

    for pos, label in [(1, "1er premio"), (2, "2º premio"), (3, "3er premio")]:
        Prize.objects.get_or_create(
            scope="global", position=pos, defaults={"amount": 0, "label": label}
        )
```

Quitar también el import de `Round` que ya no se usa. El archivo final debe quedar:

```python
# Generated by Django 5.1.15 on 2026-05-31 12:35

from decimal import Decimal

from django.db import migrations


def seed_prizes(apps, schema_editor):
    Prize = apps.get_model("pot", "Prize")
    PotSettings = apps.get_model("pot", "PotSettings")

    PotSettings.objects.get_or_create(pk=1, defaults={"per_player": Decimal("10.00")})

    for pos, label in [(1, "1er premio"), (2, "2º premio"), (3, "3er premio")]:
        Prize.objects.get_or_create(
            scope="global", position=pos, defaults={"amount": 0, "label": label}
        )


def reverse_seed(apps, schema_editor):
    apps.get_model("pot", "Prize").objects.all().delete()


class Migration(migrations.Migration):
    dependencies = [
        ("pot", "0002_payment_prize"),
        ("competition", "0002_round"),
    ]
    operations = [migrations.RunPython(seed_prizes, reverse_seed)]
```

- [ ] **Step 4: Crear data migration 0005 que borre filas scoped previas**

Crear `pot/migrations/0005_drop_scoped_prizes.py` con:

```python
from django.db import migrations


def drop_scoped(apps, schema_editor):
    Prize = apps.get_model("pot", "Prize")
    Prize.objects.exclude(scope="global").delete()


def noop(apps, schema_editor):
    # No restauramos: las filas se pueden re-sembrar manualmente si hace falta.
    pass


class Migration(migrations.Migration):
    dependencies = [("pot", "0004_potsettings_matchday_winner_prize")]
    operations = [migrations.RunPython(drop_scoped, noop)]
```

- [ ] **Step 5: Aplicar migraciones y ejecutar el test**

Run: `python manage.py migrate pot && pytest pot/tests/test_seed.py -v`
Expected: PASS.

- [ ] **Step 6: Ejecutar la suite completa de pot para descartar regresiones**

Run: `pytest pot/ -v`
Expected: PASS toda la suite. Si `test_prize_payment.py::test_prize_matchday` y `::test_prize_round_only_for_ko` fallan no es regresión — esos tests crean filas en BD manualmente, no leen lo sembrado; deberían seguir pasando.

- [ ] **Step 7: Commit**

```bash
git add pot/migrations/0003_seed_prizes.py pot/migrations/0005_drop_scoped_prizes.py pot/tests/test_seed.py
git commit -m "feat(pot): siembra solo el podio final; limpia premios scoped"
```

---

## Task 3: Tests de la vista `PrizesSettingsView` (GET)

**Files:**
- Create: `pot/tests/test_prizes_settings_view.py`

- [ ] **Step 1: Escribir los tests del GET**

Crear `pot/tests/test_prizes_settings_view.py`:

```python
from decimal import Decimal

import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory
from pot.models import PotSettings, Prize


@pytest.mark.django_db
def test_prizes_requires_gestor(client):
    client.force_login(UserFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    assert r.status_code == 302


@pytest.mark.django_db
def test_prizes_get_renders_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    assert r.status_code == 200


@pytest.mark.django_db
def test_prizes_get_context_has_top3_and_settings(client):
    client.force_login(GestorFactory(must_change_password=False))
    Prize.objects.filter(scope="global").delete()
    Prize.objects.create(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    Prize.objects.create(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    Prize.objects.create(scope="global", position=3, amount=Decimal("96"), label="3er premio")
    settings = PotSettings.load()
    settings.matchday_winner_prize = Decimal("15.00")
    settings.save()

    r = client.get(reverse("pot:prizes"))
    ctx = r.context
    assert [p.position for p in ctx["prizes"]] == [1, 2, 3]
    assert ctx["settings"].matchday_winner_prize == Decimal("15.00")


@pytest.mark.django_db
def test_prizes_get_renders_inputs_for_each_prize(client):
    client.force_login(GestorFactory(must_change_password=False))
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=Decimal("240"), label="1er premio")
    p2 = Prize.objects.create(scope="global", position=2, amount=Decimal("144"), label="2º premio")
    p3 = Prize.objects.create(scope="global", position=3, amount=Decimal("96"), label="3er premio")

    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    assert f'name="amount_{p1.id}"' in content
    assert f'name="amount_{p2.id}"' in content
    assert f'name="amount_{p3.id}"' in content
    assert 'name="matchday_winner_prize"' in content
```

- [ ] **Step 2: Ejecutar tests, comprobar estado**

Run: `pytest pot/tests/test_prizes_settings_view.py -v`
Expected: Tests 1, 2, 3 PASS (la vista ya existe); test 4 puede FAIL si el template aún no expone `matchday_winner_prize` — eso es esperado y se arregla en Task 5.

- [ ] **Step 3: Commit los tests aunque alguno falle (estado WIP)**

```bash
git add pot/tests/test_prizes_settings_view.py
git commit -m "test(pot): contrato GET de PrizesSettingsView (incluye matchday)"
```

---

## Task 4: Reescribir `PrizesSettingsView` (GET + POST)

**Files:**
- Modify: `pot/views.py`

- [ ] **Step 1: Ampliar tests con cobertura del POST**

Añadir al final de `pot/tests/test_prizes_settings_view.py`:

```python
from accounts.models import AuditLog


@pytest.mark.django_db
def test_prizes_post_updates_top3_amounts(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")
    p2 = Prize.objects.create(scope="global", position=2, amount=0, label="2º premio")
    p3 = Prize.objects.create(scope="global", position=3, amount=0, label="3er premio")

    r = client.post(
        reverse("pot:prizes"),
        {
            f"amount_{p1.id}": "240",
            f"amount_{p2.id}": "144",
            f"amount_{p3.id}": "96",
            "matchday_winner_prize": "0",
        },
    )
    assert r.status_code == 302
    p1.refresh_from_db(); p2.refresh_from_db(); p3.refresh_from_db()
    assert p1.amount == Decimal("240")
    assert p2.amount == Decimal("144")
    assert p3.amount == Decimal("96")


@pytest.mark.django_db
def test_prizes_post_updates_matchday_winner_prize(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "0", "matchday_winner_prize": "25.50"},
    )
    assert PotSettings.load().matchday_winner_prize == Decimal("25.50")


@pytest.mark.django_db
def test_prizes_post_writes_audit_log(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=0, label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "100", "matchday_winner_prize": "10"},
    )
    log = AuditLog.objects.filter(actor=g, action="prize_changed").first()
    assert log is not None
    assert log.target_type == "prize"


@pytest.mark.django_db
def test_prizes_post_ignores_invalid_amount(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=Decimal("50"), label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "not-a-number", "matchday_winner_prize": "10"},
    )
    p1.refresh_from_db()
    assert p1.amount == Decimal("50")  # sin cambio
    assert PotSettings.load().matchday_winner_prize == Decimal("10")  # otros sí


@pytest.mark.django_db
def test_prizes_post_rejects_negative_amount(client):
    g = GestorFactory(must_change_password=False)
    client.force_login(g)
    Prize.objects.filter(scope="global").delete()
    p1 = Prize.objects.create(scope="global", position=1, amount=Decimal("50"), label="1er premio")

    client.post(
        reverse("pot:prizes"),
        {f"amount_{p1.id}": "-10", "matchday_winner_prize": "-5"},
    )
    p1.refresh_from_db()
    assert p1.amount == Decimal("50")  # ignorado
    assert PotSettings.load().matchday_winner_prize == Decimal("0")  # default tras load (sin cambio si rechazamos)
```

- [ ] **Step 2: Ejecutar los nuevos tests, comprobar que fallan**

Run: `pytest pot/tests/test_prizes_settings_view.py -v`
Expected: FAIL los nuevos tests:
- `test_prizes_post_updates_top3_amounts` puede pasar parcialmente (la vista actual ya actualiza `amount` con `int(raw)`), pero las cantidades con decimales fallarán.
- `test_prizes_post_updates_matchday_winner_prize` falla — la vista no toca `PotSettings`.
- `test_prizes_post_rejects_negative_amount` puede pasar parcialmente.

- [ ] **Step 3: Reescribir `PrizesSettingsView`**

Reemplazar la clase completa en `pot/views.py` por:

```python
class PrizesSettingsView(GestorRequiredMixin, View):
    def get(self, request):
        return render(
            request,
            "pot/prizes_settings.html",
            {
                "prizes": Prize.objects.filter(scope="global").order_by("position"),
                "settings": PotSettings.load(),
                "paid_count": Payment.objects.filter(paid=True).count(),
            },
        )

    def post(self, request):
        from decimal import Decimal, InvalidOperation
        from django.db import transaction

        def _parse_decimal(raw):
            try:
                value = Decimal(raw)
            except (TypeError, InvalidOperation):
                return None
            return value if value >= 0 else None

        with transaction.atomic():
            for prize in Prize.objects.filter(scope="global"):
                raw = request.POST.get(f"amount_{prize.id}")
                value = _parse_decimal(raw)
                if value is not None:
                    prize.amount = value
                    prize.save(update_fields=["amount"])

            mw_raw = request.POST.get("matchday_winner_prize")
            mw_value = _parse_decimal(mw_raw)
            if mw_value is not None:
                settings_obj = PotSettings.load()
                settings_obj.matchday_winner_prize = mw_value
                settings_obj.save(update_fields=["matchday_winner_prize"])

            AuditLog.objects.create(
                actor=request.user,
                action="prize_changed",
                target_type="prize",
                target_id="*",
                payload={},
            )
        messages.success(request, "Premios actualizados.")
        return redirect("pot:prizes")
```

Asegúrate de que `from pot.models import Payment, Prize, PotSettings` está en los imports del fichero (sustituye el import existente si solo trae `Payment, Prize`).

- [ ] **Step 4: Ejecutar tests de vista**

Run: `pytest pot/tests/test_prizes_settings_view.py -v`
Expected: PASS todos. Si el test del template (`test_prizes_get_renders_inputs_for_each_prize`) aún falla por `name="matchday_winner_prize"`, queda pendiente para Task 5.

- [ ] **Step 5: Suite completa de `pot` para no romper nada**

Run: `pytest pot/ -v`
Expected: PASS (excepto el test del template hasta Task 5).

- [ ] **Step 6: Commit**

```bash
git add pot/views.py pot/tests/test_prizes_settings_view.py
git commit -m "feat(pot): vista de premios edita top3 + matchday en una transacción"
```

---

## Task 5: Rediseñar el template `prizes_settings.html`

**Files:**
- Modify: `templates/pot/prizes_settings.html`
- Modify: `static/css/styles.css`

- [ ] **Step 1: Reemplazar el template**

Sobrescribir `templates/pot/prizes_settings.html` con:

```django
{% extends "base.html" %}
{% load icons %}
{% block title %}Premios · PORRA 26{% endblock %}
{% block main %}
<div class="prizes-config stagger" style="max-width:880px;margin:0 auto;display:flex;flex-direction:column;gap:24px">

  <header style="display:flex;flex-direction:column;gap:8px">
    <span class="eyebrow">GESTOR · CONFIGURACIÓN</span>
    <h1 class="grad-text" style="font-family:Sora,sans-serif;font-weight:800;letter-spacing:-0.03em;font-size:clamp(28px,4vw,40px);margin:0;line-height:1.1">
      Premios del bote
    </h1>
    <p style="color:var(--text-dim);font-size:15px;margin:0">
      Define cuánto se lleva cada puesto del podio final y cuánto premia ganar una jornada.
    </p>
  </header>

  <section class="glass" style="padding:18px;border-radius:var(--r-lg);display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">
    <div style="display:flex;flex-direction:column;gap:2px">
      <strong style="font-family:Sora,sans-serif;font-size:26px;color:var(--c-gold)">{{ pot_total|default:0 }} €</strong>
      <span class="eyebrow">Bote total</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:2px">
      <strong style="font-family:Sora,sans-serif;font-size:26px">{{ settings.per_player|floatformat:"-2" }} €</strong>
      <span class="eyebrow">Por jugador</span>
    </div>
    <div style="display:flex;flex-direction:column;gap:2px">
      <strong style="font-family:Sora,sans-serif;font-size:26px">{{ paid_count }}</strong>
      <span class="eyebrow">Pagos confirmados</span>
    </div>
  </section>

  <form method="post" style="display:flex;flex-direction:column;gap:24px">
    {% csrf_token %}

    <section class="glass" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:18px">
      <header style="display:flex;flex-direction:column;gap:4px">
        <span class="eyebrow">01 · Podio final</span>
        <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:20px">Premios al cierre del Mundial</h2>
        <p style="color:var(--text-dim);margin:0;font-size:13px">Se reparten entre los tres primeros de la clasificación general.</p>
      </header>

      <ul class="prizes-podium" role="list">
        {% for prize in prizes %}
        <li data-position="{{ prize.position }}">
          <span class="prizes-podium-badge">{{ prize.position }}º</span>
          <label class="prizes-podium-label" for="amount_{{ prize.id }}">{{ prize.label }}</label>
          <div class="prizes-podium-input">
            <input class="input" type="number" min="0" step="0.01" inputmode="decimal"
                   id="amount_{{ prize.id }}" name="amount_{{ prize.id }}"
                   value="{{ prize.amount|floatformat:'-2' }}">
            <span class="mono">€</span>
          </div>
        </li>
        {% endfor %}
      </ul>
    </section>

    <section class="glass prizes-matchday-card" style="padding:24px;border-radius:var(--r-lg);display:flex;flex-direction:column;gap:18px">
      <header style="display:flex;flex-direction:column;gap:4px">
        <span class="eyebrow">02 · Por jornada</span>
        <h2 style="margin:0;font-family:Sora,sans-serif;font-weight:700;font-size:20px">Premio por ganador de jornada</h2>
        <p style="color:var(--text-dim);margin:0;font-size:13px">
          El jugador con más puntos en cada jornada de grupos y en cada ronda eliminatoria se lleva este importe.
          Se aplica por igual a todas.
        </p>
      </header>

      <div class="prizes-matchday-row">
        <div class="prizes-matchday-icon">{% icon "trophy" width=28 height=28 %}</div>
        <label class="prizes-matchday-label" for="matchday_winner_prize">Importe por jornada/ronda</label>
        <div class="prizes-matchday-input">
          <input class="input" type="number" min="0" step="0.01" inputmode="decimal"
                 id="matchday_winner_prize" name="matchday_winner_prize"
                 value="{{ settings.matchday_winner_prize|floatformat:'-2' }}">
          <span class="mono">€</span>
        </div>
      </div>
    </section>

    <div style="display:flex;justify-content:flex-end">
      <button class="btn btn-primary" type="submit">Guardar premios</button>
    </div>
  </form>
</div>
{% endblock %}
```

- [ ] **Step 2: Añadir CSS para `.prizes-podium` y `.prizes-matchday-card`**

Añadir al final de `static/css/styles.css`:

```css
/* === Pantalla de configuración de premios ============================ */
.prizes-podium {
  list-style: none;
  margin: 0;
  padding: 0;
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: 12px;
}
.prizes-podium li {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 10px;
  padding: 16px 12px;
  border-radius: var(--r-md);
  border: 1px solid var(--border);
  background: var(--surface-hi);
}
.prizes-podium li[data-position="1"] { border-color: oklch(from var(--c-gold) l c h / 0.55); }
.prizes-podium li[data-position="2"] { border-color: oklch(from var(--text-dim) l c h / 0.45); }
.prizes-podium li[data-position="3"] { border-color: oklch(from var(--c-yellow) l c h / 0.45); }
.prizes-podium-badge {
  font-family: Sora, sans-serif;
  font-weight: 800;
  font-size: 22px;
  color: var(--text);
}
.prizes-podium li[data-position="1"] .prizes-podium-badge { color: var(--c-gold); }
.prizes-podium li[data-position="2"] .prizes-podium-badge { color: var(--text-dim); }
.prizes-podium li[data-position="3"] .prizes-podium-badge { color: var(--c-yellow); }
.prizes-podium-label {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-faint);
}
.prizes-podium-input {
  display: flex;
  align-items: center;
  gap: 6px;
  width: 100%;
}
.prizes-podium-input .input {
  flex: 1;
  text-align: right;
  font-family: Sora, sans-serif;
  font-weight: 700;
  font-size: 18px;
}

.prizes-matchday-card { border-color: oklch(from var(--c-cyan) l c h / 0.35); }
.prizes-matchday-row {
  display: grid;
  grid-template-columns: auto 1fr auto;
  align-items: center;
  gap: 16px;
}
.prizes-matchday-icon {
  width: 48px;
  height: 48px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-md);
  background: oklch(from var(--c-cyan) l c h / 0.12);
  color: var(--c-cyan);
}
.prizes-matchday-label {
  font-family: 'Geist Mono', monospace;
  font-size: 11px;
  text-transform: uppercase;
  letter-spacing: 0.12em;
  color: var(--text-faint);
}
.prizes-matchday-input {
  display: flex;
  align-items: center;
  gap: 8px;
}
.prizes-matchday-input .input {
  width: 180px;
  text-align: right;
  font-family: Sora, sans-serif;
  font-weight: 700;
  font-size: 20px;
}

@media (max-width: 720px) {
  .prizes-podium { grid-template-columns: 1fr; }
  .prizes-matchday-row { grid-template-columns: 1fr; }
  .prizes-matchday-input .input { width: 100%; }
}
```

- [ ] **Step 3: Ejecutar tests del template**

Run: `pytest pot/tests/test_prizes_settings_view.py -v`
Expected: PASS todos los tests, incluyendo `test_prizes_get_renders_inputs_for_each_prize`.

- [ ] **Step 4: Comprobación visual rápida (manual)**

Run: `python manage.py runserver` (o equivalente del proyecto). En el navegador, autenticarse como gestor y abrir `/gestion/premios/` (verificar la URL exacta consultando `pot/urls.py` y `porra26/urls.py`). Confirmar que:
- Aparece el header con eyebrow + título degradado.
- Aparecen 3 tarjetas de podio con badges 1º/2º/3º en oro/plata/bronce.
- La tarjeta de "Por jornada" tiene borde cian y el icono trofeo.
- Editar valores y enviar → toast "Premios actualizados." + valores persistidos al recargar.

- [ ] **Step 5: Commit**

```bash
git add templates/pot/prizes_settings.html static/css/styles.css
git commit -m "feat(pot): rediseño de la pantalla de premios con podio y tarjeta de jornada"
```

---

## Task 6: Mostrar `matchday_winner_prize` en la página de Reglas

**Files:**
- Modify: `core/views.py`
- Modify: `templates/core/rules.html`
- Modify: `static/css/styles.css`
- Modify: `core/tests/test_rules_view.py`

- [ ] **Step 1: Escribir tests que fallen**

Añadir al final de `core/tests/test_rules_view.py`:

```python
@pytest.mark.django_db
def test_rules_shows_matchday_winner_prize_when_set(client):
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("18.00")
    s.save()
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "Premio por ganador de jornada" in content
    assert "18" in content
    assert "rules-matchday-prize" in content


@pytest.mark.django_db
def test_rules_hides_matchday_winner_prize_when_zero(client):
    s = PotSettings.load()
    s.matchday_winner_prize = Decimal("0")
    s.save()
    client.force_login(UserFactory())
    r = client.get(reverse("core:rules"))
    content = r.content.decode("utf-8")
    assert "rules-matchday-prize" not in content
    assert "Premio por ganador de jornada" not in content
```

- [ ] **Step 2: Ejecutar tests, comprobar que fallan**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: FAIL los dos nuevos.

- [ ] **Step 3: Añadir `matchday_winner_prize` al contexto de la vista**

Editar `core/views.py`, dentro de `RulesView.get_context_data`, añadir antes del `return`:

```python
        ctx["matchday_winner_prize"] = PotSettings.load().matchday_winner_prize
```

- [ ] **Step 4: Añadir la tarjeta al template de reglas**

En `templates/core/rules.html`, dentro de la `<section>` "03 · El bote y los premios", añadir justo después del bloque `<ul class="rules-medals">...</ul>` y antes del `<p>` final, este markup:

```django
    {% if matchday_winner_prize and matchday_winner_prize > 0 %}
    <div class="rules-matchday-prize">
      <div class="rules-matchday-prize-icon">{% icon "trophy" width=22 height=22 aria_hidden="true" %}</div>
      <div class="rules-matchday-prize-body">
        <span class="eyebrow">Premio por ganador de jornada</span>
        <strong>{{ matchday_winner_prize|floatformat:"-2" }} €</strong>
        <p>El jugador con más puntos en cada jornada de grupos y en cada ronda eliminatoria se lleva este premio extra.</p>
      </div>
    </div>
    {% endif %}
```

- [ ] **Step 5: Añadir CSS para `.rules-matchday-prize`**

Añadir en `static/css/styles.css` justo después del bloque `.rules-medals` (antes de `.rules-tiebreak`):

```css
.rules-matchday-prize {
  display: grid;
  grid-template-columns: auto 1fr;
  gap: 14px;
  padding: 14px 16px;
  border-radius: var(--r-md);
  border: 1px solid oklch(from var(--c-cyan) l c h / 0.35);
  background: oklch(from var(--c-cyan) l c h / 0.06);
  align-items: center;
}
.rules-matchday-prize-icon {
  width: 40px;
  height: 40px;
  display: flex;
  align-items: center;
  justify-content: center;
  border-radius: var(--r-sm, 10px);
  background: oklch(from var(--c-cyan) l c h / 0.15);
  color: var(--c-cyan);
}
.rules-matchday-prize-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}
.rules-matchday-prize-body strong {
  font-family: Sora, sans-serif;
  font-weight: 800;
  font-size: 26px;
  color: var(--c-cyan);
  line-height: 1.1;
}
.rules-matchday-prize-body p {
  margin: 4px 0 0;
  color: var(--text-dim);
  font-size: 13px;
}
```

- [ ] **Step 6: Ejecutar los tests de reglas**

Run: `pytest core/tests/test_rules_view.py -v`
Expected: PASS los nuevos y los anteriores.

- [ ] **Step 7: Commit**

```bash
git add core/views.py templates/core/rules.html static/css/styles.css core/tests/test_rules_view.py
git commit -m "feat(rules): muestra premio por ganador de jornada"
```

---

## Task 7: Nav-item "Premios" en la topbar para gestores

**Files:**
- Modify: `templates/partials/_topbar.html`
- Create: `pot/tests/test_topbar_premios_link.py`

- [ ] **Step 1: Escribir tests que fallen**

Crear `pot/tests/test_topbar_premios_link.py`:

```python
import pytest
from django.urls import reverse

from accounts.tests.factories import GestorFactory, UserFactory


@pytest.mark.django_db
def test_topbar_has_premios_link_for_gestor(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("pot:prizes") in content
    assert ">Premios<" in content or "Premios" in content


@pytest.mark.django_db
def test_topbar_no_premios_link_for_jugador(client):
    client.force_login(UserFactory(must_change_password=False, is_jugador=True))
    r = client.get(reverse("competicion:dashboard"))
    content = r.content.decode("utf-8")
    assert reverse("pot:prizes") not in content


@pytest.mark.django_db
def test_topbar_premios_is_active_on_prizes_page(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    href = reverse("pot:prizes")
    assert f'href="{href}" class="nav-item is-active"' in content


@pytest.mark.django_db
def test_topbar_jugadores_not_active_on_prizes_page(client):
    client.force_login(GestorFactory(must_change_password=False))
    r = client.get(reverse("pot:prizes"))
    content = r.content.decode("utf-8")
    href_jugadores = reverse("pot:manage_players")
    # El enlace de jugadores aparece pero SIN is-active.
    assert href_jugadores in content
    assert f'href="{href_jugadores}" class="nav-item is-active"' not in content
```

- [ ] **Step 2: Ejecutar tests, comprobar que fallan**

Run: `pytest pot/tests/test_topbar_premios_link.py -v`
Expected: FAIL — no existe el enlace y "Jugadores" se quedaría activo en `/premios/` (porque hoy es `ns == 'pot'`).

- [ ] **Step 3: Editar `_topbar.html`**

En `templates/partials/_topbar.html`, sustituir el bloque `{% if user.is_gestor %} ... {% endif %}` por:

```django
    {% if user.is_gestor %}
    <a href="{% url 'pot:manage_players' %}" class="nav-item{% if ns == 'pot' and url_name != 'prizes' and url_name != 'audit' %} is-active{% endif %}">
      {% icon "users" width=17 height=17 %} Jugadores
    </a>
    <a href="{% url 'competicion:manage_results' %}" class="nav-item{% if url_name == 'manage_results' %} is-active{% endif %}">
      {% icon "whistle" width=17 height=17 %} Resultados
    </a>
    <a href="{% url 'pot:prizes' %}" class="nav-item{% if url_name == 'prizes' %} is-active{% endif %}">
      {% icon "euro" width=17 height=17 %} Premios
    </a>
    {% endif %}
```

- [ ] **Step 4: Ejecutar tests**

Run: `pytest pot/tests/test_topbar_premios_link.py core/tests/test_topbar.py -v`
Expected: PASS los nuevos y los preexistentes.

- [ ] **Step 5: Commit**

```bash
git add templates/partials/_topbar.html pot/tests/test_topbar_premios_link.py
git commit -m "feat(topbar): enlace Premios para gestores y active-state refinado"
```

---

## Task 8: Suite completa y verificación final

- [ ] **Step 1: Ejecutar TODA la suite**

Run: `pytest -q`
Expected: PASS toda. Cualquier fallo se diagnostica antes de seguir.

- [ ] **Step 2: Verificación visual manual end-to-end**

Run: `python manage.py runserver`
- Como gestor: navegar a la topbar → ver "Premios", entrar → comprobar pantalla. Editar 1º=240, 2º=144, 3º=96, jornada=15. Guardar → toast OK.
- Navegar a /reglas/ → la sección "El bote y los premios" muestra las medallas con 240/144/96 y debajo la tarjeta cian "Premio por ganador de jornada · 15 €".
- Cambiar matchday_winner_prize a 0 en /premios/ → recargar /reglas/ → la tarjeta cian desaparece.
- Como jugador (no gestor): /reglas/ sigue mostrando bote + tarjeta cian; /premios/ debe redirigir (302).

- [ ] **Step 3: Commit (si hay ajustes finales)**

Solo si los pasos anteriores forzaron cambios. Si no hay nada que commitear, saltar.

---

## Task 9: Actualizar `docs/DATA_MODEL.md`

**Files:**
- Modify: `docs/DATA_MODEL.md`

- [ ] **Step 1: Actualizar la fila Pot/Settings en §1**

En `docs/DATA_MODEL.md`, sustituir la tabla "Pot / Settings (Bote y configuración)" por:

```markdown
### Pot / Settings (Bote y configuración)
| Campo | Tipo | Notas |
|-------|------|-------|
| `perPlayer` | Decimal | aportación por jugador (prototipo: 10 €) |
| `matchdayWinnerPrize` | Decimal | importe único que se entrega al jugador con más puntos en cada jornada de grupos y cada ronda KO |
| `prizes` | Prize[] | filas con `scope="global"` y `position ∈ {1,2,3}` — el podio final |

`total` = `perPlayer × nº de jugadores que pagan`. En el prototipo: 48 jugadores → 480 €.

> El modelo `Prize` solo se usa para el podio final (top 3). Las filas con scope `matchday` o `round` quedaron retiradas en favor de `matchdayWinnerPrize` en PotSettings — un único importe para todas las jornadas/rondas.
```

- [ ] **Step 2: Commit**

```bash
git add docs/DATA_MODEL.md
git commit -m "docs(data-model): describe matchdayWinnerPrize y el alcance reducido de Prize"
```

---

## Task 10: Actualizar memoria persistente

**Files:**
- Modify: `/Users/ignacioborrajo/.claude/projects/-Users-ignacioborrajo-Documents-GitHub-apuestas-interna/memory/project_reglas_pagina.md`

- [ ] **Step 1: Ampliar la memoria existente**

Leer primero el archivo (puede no existir aún en disco como cuento). Si existe, abrir y ampliar el cuerpo para incluir:

> El campo `matchday_winner_prize` de `PotSettings` también debe verse reflejado en la página de Reglas (tarjeta cian bajo el podio). La configuración vive en `/premios/` (vista `PrizesSettingsView`, ruta `pot:prizes`).

Si no existe, crearlo con el patrón estándar (frontmatter `name`, `description`, `metadata.type: project`). No commitear la memoria.

---

## Self-Review

Revisión final del plan contra la spec:

1. **Spec coverage:**
   - Modelo: `matchday_winner_prize` en PotSettings → Task 1 ✓
   - Limpieza de Prize matchday/round → Task 2 ✓
   - Backend `PrizesSettingsView` get + post atómico + AuditLog → Task 4 ✓
   - Contexto de `RulesView` con matchday_winner_prize → Task 6 ✓
   - Rediseño de `/premios/` con podio + tarjeta jornada → Task 5 ✓
   - Reglas con tarjeta `--c-cyan` oculta si =0 → Task 6 ✓
   - Topbar nav-item Premios + fix activo Jugadores → Task 7 ✓
   - Tests (5 escenarios vista + 4 topbar + 2 reglas + 2 settings) → Tasks 1,3,4,6,7 ✓
   - Docs DATA_MODEL.md → Task 9 ✓
   - Memoria → Task 10 ✓

2. **Placeholder scan:** sin TBDs ni "implement later". Todo el código que se escribe está completo y exacto.

3. **Type consistency:** `matchday_winner_prize` es Decimal en todos los puntos (modelo, vista, template, tests). `Prize.amount` es Decimal y se parsea con `Decimal()` en la vista. Los nombres de input HTML (`amount_{id}`, `matchday_winner_prize`) son consistentes entre template, vista y tests.

4. **Riesgos verificados:**
   - `pot/services/prizes.py::matchday_winners` no lee `Prize.amount` — la limpieza de filas scoped no rompe esa lógica.
   - `pot/tests/test_prize_payment.py` crea filas Prize en BD desde cero — no depende de lo sembrado, sigue pasando.
   - El campo `payload={}` de `AuditLog` se mantiene como hasta ahora.
