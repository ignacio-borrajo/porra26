# Plan — PWA instalable básica

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Hacer la app instalable como PWA (manifest + service worker mínimo + iconos generados desde el logo nuevo), sin offline ni push.

**Architecture:** App Django nueva `pwa/` con dos vistas (manifest, service worker) renderizadas como plantillas. Rutas montadas en la raíz para que el SW tenga scope `/`. Iconos generados con Pillow desde `static/img/logo.png` por un script reejecutable. Meta tags y registro inline del SW en `templates/base.html`.

**Tech Stack:** Django 5, Python 3.12, Pillow (ya en `requirements.txt`), pytest, ruff.

Spec: `docs/superpowers/specs/2026-06-04-pwa-instalable-basico-design.md`.

---

## Archivos afectados

**Crear:**
- `pwa/__init__.py`
- `pwa/apps.py`
- `pwa/views.py`
- `pwa/urls.py`
- `pwa/tests/__init__.py`
- `pwa/tests/test_manifest.py`
- `pwa/tests/test_service_worker.py`
- `templates/pwa/manifest.webmanifest`
- `templates/pwa/service-worker.js`
- `bin/generate_pwa_icons.py`
- `static/img/pwa/icon-192.png`
- `static/img/pwa/icon-512.png`
- `static/img/pwa/icon-192-maskable.png`
- `static/img/pwa/icon-512-maskable.png`
- `static/img/pwa/apple-touch-icon.png`

**Modificar:**
- `static/img/logo.png` (reemplazo desde `~/Downloads/Logo_porras.png`)
- `porra26/settings/base.py` (añadir `"pwa"` a `INSTALLED_APPS`)
- `porra26/urls.py` (rutas raíz)
- `templates/base.html` (meta tags + script de registro)

---

## Convenciones del repo

- Python en `.venv/` del worktree principal. Comandos en este worktree usan:
  ```bash
  VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
  ```
- Tests: `pytest`. Selección por archivo o por nodeid (`pytest pwa/tests/test_manifest.py -v`).
- Lint: `ruff` (presente en requirements-dev). Antes de cada commit corremos `"$VENV/python" -m ruff check pwa/` sobre lo modificado.
- Commits: mensaje en español, prefijo `feat(pwa):` / `test(pwa):` / `chore(pwa):` según corresponda. Cuerpo opcional.
- Idioma: comentarios y strings en español.

---

## Task 1 — Reemplazar el logo y crear el script de iconos

**Files:**
- Modify: `static/img/logo.png` (binario, copia desde `~/Downloads/Logo_porras.png`)
- Create: `bin/generate_pwa_icons.py`

- [ ] **Paso 1: Copiar el logo nuevo a `static/img/logo.png` sobrescribiendo el anterior.**

```bash
cp "$HOME/Downloads/Logo_porras.png" static/img/logo.png
```

Verificar:
```bash
file static/img/logo.png
# Esperado: PNG image data, 520 x 480, 8-bit/color RGBA, non-interlaced
```

- [ ] **Paso 2: Crear `bin/generate_pwa_icons.py` con la lógica de Pillow.**

```python
#!/usr/bin/env python
"""
Genera los iconos PWA a partir de `static/img/logo.png`.

Idempotente: se puede reejecutar cada vez que cambie el logo fuente.
Escribe en `static/img/pwa/`.

Uso:
    python bin/generate_pwa_icons.py
"""
from __future__ import annotations

from pathlib import Path

from PIL import Image

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "static" / "img" / "logo.png"
OUT_DIR = ROOT / "static" / "img" / "pwa"

# Color de fondo (=== --bg-0 del tema oscuro, oklch(0.16 0.02 275) ≈ #1a1530).
BG = (26, 21, 48, 255)

# (filename, canvas_size, logo_ratio)
TARGETS = [
    ("icon-192.png", 192, 0.80),
    ("icon-512.png", 512, 0.80),
    ("icon-192-maskable.png", 192, 0.60),
    ("icon-512-maskable.png", 512, 0.60),
    ("apple-touch-icon.png", 180, 0.80),
]


def render_icon(source: Image.Image, size: int, logo_ratio: float) -> Image.Image:
    canvas = Image.new("RGBA", (size, size), BG)
    # Escalar el logo manteniendo aspecto para que su lado largo ocupe
    # `size * logo_ratio` del lienzo cuadrado.
    target = int(size * logo_ratio)
    scale = target / max(source.width, source.height)
    new_w = max(1, round(source.width * scale))
    new_h = max(1, round(source.height * scale))
    logo = source.resize((new_w, new_h), Image.Resampling.LANCZOS)
    x = (size - new_w) // 2
    y = (size - new_h) // 2
    canvas.alpha_composite(logo, dest=(x, y))
    return canvas


def main() -> None:
    if not SOURCE.exists():
        raise SystemExit(f"No existe el logo fuente: {SOURCE}")
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    source = Image.open(SOURCE).convert("RGBA")
    for filename, size, ratio in TARGETS:
        out_path = OUT_DIR / filename
        icon = render_icon(source, size, ratio)
        icon.save(out_path, format="PNG", optimize=True)
        print(f"✔ {out_path.relative_to(ROOT)} ({size}×{size}, logo {int(ratio*100)}%)")


if __name__ == "__main__":
    main()
```

- [ ] **Paso 3: Ejecutar el script y verificar que crea los 5 iconos.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" bin/generate_pwa_icons.py
ls -la static/img/pwa/
```
Esperado: 5 archivos PNG, todos cuadrados, los `192` ~10-25 KB, los `512` ~40-90 KB.

Inspección visual rápida:
```bash
file static/img/pwa/*.png
```
Cada línea debe terminar en `192 x 192`, `512 x 512` o `180 x 180`.

- [ ] **Paso 4: Hacer el script ejecutable.**

```bash
chmod +x bin/generate_pwa_icons.py
```

- [ ] **Paso 5: Commit.**

```bash
git add static/img/logo.png static/img/pwa/ bin/generate_pwa_icons.py
git commit -m "feat(pwa): logo nuevo + script de generación de iconos

Sustituye static/img/logo.png por el logo definitivo del Mundial 2026
(trofeo dorado con texto 'MUNDIAL 2026 · Tu porra interna'), RGBA con
fondo transparente, mejor base para iconos PWA.

bin/generate_pwa_icons.py es reejecutable: produce icon-192/512 (any
y maskable, ratios 80% y 60% para la zona segura de Android) y
apple-touch-icon 180x180, todos sobre fondo #1a1530."
```

---

## Task 2 — Esqueleto de la app `pwa/`

**Files:**
- Create: `pwa/__init__.py`
- Create: `pwa/apps.py`
- Create: `pwa/urls.py`
- Create: `pwa/views.py`
- Create: `pwa/tests/__init__.py`
- Modify: `porra26/settings/base.py`

- [ ] **Paso 1: Crear los archivos del paquete vacíos pero funcionales.**

`pwa/__init__.py`:
```python
```

`pwa/apps.py`:
```python
from django.apps import AppConfig


class PwaConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "pwa"
```

`pwa/urls.py`:
```python
# Las rutas PWA viven en porra26/urls.py porque el scope del service
# worker depende de su ubicación: debe servirse desde la raíz.
# Este archivo existe para mantener la convención de tener un urls.py
# por app, pero no expone rutas propias.
from django.urls import path

app_name = "pwa"

urlpatterns: list[path] = []
```

`pwa/views.py`:
```python
import os
import time

from django.shortcuts import render

# Versión del service worker. Se calcula al importar el módulo (una vez por
# proceso): así todos los workers de gunicorn comparten la misma versión
# durante la vida del deploy, pero al hacer un release nuevo el proceso
# arranca con otra versión y los clientes detectan que el SW ha cambiado.
_VERSION = os.environ.get("GIT_SHA") or os.environ.get("RAILWAY_GIT_COMMIT_SHA") or str(int(time.time()))


def _sw_version() -> str:
    return _VERSION


def manifest(request):
    return render(
        request,
        "pwa/manifest.webmanifest",
        content_type="application/manifest+json",
    )


def service_worker(request):
    response = render(
        request,
        "pwa/service-worker.js",
        {"version": _sw_version()},
        content_type="application/javascript",
    )
    # Garantiza scope raíz incluso si algún proxy reescribe la ruta.
    response["Service-Worker-Allowed"] = "/"
    # El SW lo gestiona el navegador internamente; HTTP cache nos estorba
    # al desplegar (los clientes no detectarían cambios hasta expirar).
    response["Cache-Control"] = "no-cache"
    return response
```

`pwa/tests/__init__.py`:
```python
```

- [ ] **Paso 2: Añadir `"pwa"` a `INSTALLED_APPS` en `porra26/settings/base.py`.**

Edición en `porra26/settings/base.py` líneas 14-28: añadir `"pwa"` justo después de `"announcements"`, antes de `"axes"`.

```python
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "accounts",
    "competition",
    "pot",
    "stats",
    "core",
    "announcements",
    "pwa",
    "axes",
]
```

- [ ] **Paso 3: Verificar que Django arranca con la app registrada.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" manage.py check
```
Esperado: `System check identified no issues (0 silenced).`

- [ ] **Paso 4: Commit (esqueleto sin rutas todavía).**

```bash
git add pwa/ porra26/settings/base.py
git commit -m "feat(pwa): esqueleto de app aislada

Crea la app pwa/ con views() de manifest y service_worker. Sin rutas
todavía (van en la raíz, no en pwa/urls.py, porque el scope del SW
exige servirlo desde /). _sw_version() lee GIT_SHA / RAILWAY_GIT_COMMIT_SHA
con fallback a timestamp de import del módulo."
```

---

## Task 3 — Tests rojos del manifest

**Files:**
- Create: `pwa/tests/test_manifest.py`

- [ ] **Paso 1: Escribir los tests fallidos del manifest.**

```python
"""Tests de la vista /manifest.webmanifest."""
import json

import pytest


@pytest.mark.django_db
def test_manifest_is_public(client):
    """El manifest se sirve sin autenticación (el navegador lo pide antes del login)."""
    response = client.get("/manifest.webmanifest")
    assert response.status_code == 200


@pytest.mark.django_db
def test_manifest_content_type(client):
    response = client.get("/manifest.webmanifest")
    assert response["Content-Type"].startswith("application/manifest+json")


@pytest.mark.django_db
def test_manifest_is_valid_json(client):
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    assert isinstance(data, dict)


@pytest.mark.django_db
def test_manifest_has_required_fields(client):
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    assert data["name"] == "PORRA 26 · Mundial 2026"
    assert data["short_name"] == "PORRA 26"
    assert data["start_url"] == "/"
    assert data["scope"] == "/"
    assert data["display"] == "standalone"
    assert data["theme_color"] == "#1a1530"
    assert data["background_color"] == "#1a1530"
    assert data["lang"] == "es-ES"


@pytest.mark.django_db
def test_manifest_has_required_icons(client):
    response = client.get("/manifest.webmanifest")
    data = json.loads(response.content)
    icons = data["icons"]
    # Al menos un 192 any, un 512 any, y al menos un maskable.
    purposes = {(i["sizes"], i["purpose"]) for i in icons}
    assert ("192x192", "any") in purposes
    assert ("512x512", "any") in purposes
    assert any("maskable" in p for _, p in purposes)
```

- [ ] **Paso 2: Correr los tests y verificar que fallan con 404 (la ruta aún no existe).**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" -m pytest pwa/tests/test_manifest.py -v
```
Esperado: todos fallan. Mensaje típico: `assert 404 == 200` (la URL `/manifest.webmanifest` aún no está mapeada).

---

## Task 4 — Plantilla del manifest + ruta + tests verdes

**Files:**
- Create: `templates/pwa/manifest.webmanifest`
- Modify: `porra26/urls.py`

- [ ] **Paso 1: Crear `templates/pwa/manifest.webmanifest`.**

```jinja
{% load static %}{
  "name": "PORRA 26 · Mundial 2026",
  "short_name": "PORRA 26",
  "description": "Porra interna del Mundial FIFA 2026.",
  "lang": "es-ES",
  "dir": "ltr",
  "start_url": "/",
  "scope": "/",
  "display": "standalone",
  "orientation": "any",
  "background_color": "#1a1530",
  "theme_color": "#1a1530",
  "icons": [
    {
      "src": "{% static 'img/pwa/icon-192.png' %}",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "{% static 'img/pwa/icon-512.png' %}",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "any"
    },
    {
      "src": "{% static 'img/pwa/icon-192-maskable.png' %}",
      "sizes": "192x192",
      "type": "image/png",
      "purpose": "maskable"
    },
    {
      "src": "{% static 'img/pwa/icon-512-maskable.png' %}",
      "sizes": "512x512",
      "type": "image/png",
      "purpose": "maskable"
    }
  ]
}
```

- [ ] **Paso 2: Añadir la ruta en `porra26/urls.py`.**

Edición en `porra26/urls.py`:

```python
import re

from django.conf import settings
from django.contrib import admin
from django.http import HttpResponse
from django.urls import include, path, re_path
from django.views.static import serve

from pwa import views as pwa_views


def _serve_media(request, path):
    """Sirve los archivos de MEDIA_ROOT.

    Lee settings.MEDIA_ROOT en cada request (no se congela en registro) para
    respetar overrides en tests y eventuales cambios en runtime.
    """
    return serve(request, path, document_root=settings.MEDIA_ROOT)


urlpatterns = [
    path("admin/", admin.site.urls),
    path("healthz/", lambda r: HttpResponse("ok", content_type="text/plain")),
    # Endpoints PWA: deben servirse desde la raíz para que el scope del
    # service worker sea "/" y controle toda la app.
    path("manifest.webmanifest", pwa_views.manifest, name="pwa-manifest"),
    path("service-worker.js", pwa_views.service_worker, name="pwa-sw"),
    path("", include(("accounts.urls", "accounts"), namespace="accounts")),
    path("competicion/", include(("competition.urls", "competicion"), namespace="competicion")),
    path("stats/", include(("stats.urls", "stats"), namespace="stats")),
    path("gestion/", include(("pot.urls", "pot"), namespace="pot")),
    path("reglas/", include(("core.urls", "core"), namespace="core")),
    path("anuncios/", include(("announcements.urls", "announcements"), namespace="announcements")),
    re_path(
        rf"^{re.escape(settings.MEDIA_URL.lstrip('/'))}(?P<path>.*)$",
        _serve_media,
    ),
]
```

- [ ] **Paso 3: Correr los tests del manifest hasta verde.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" -m pytest pwa/tests/test_manifest.py -v
```
Esperado: 5 tests pasan.

- [ ] **Paso 4: Commit.**

```bash
git add pwa/tests/test_manifest.py templates/pwa/manifest.webmanifest porra26/urls.py
git commit -m "feat(pwa): manifest.webmanifest servido en raíz

Plantilla Django renderizada para que las URLs de los iconos pasen por
{% static %} (compatible con el hashing de WhiteNoise). Content-Type
application/manifest+json. 5 tests cubren visibilidad pública, formato
JSON, campos obligatorios y existencia de iconos any+maskable a 192 y 512."
```

---

## Task 5 — Tests rojos del service worker

**Files:**
- Create: `pwa/tests/test_service_worker.py`

- [ ] **Paso 1: Escribir los tests fallidos del SW.**

```python
"""Tests de la vista /service-worker.js."""
import pytest


@pytest.mark.django_db
def test_sw_is_public(client):
    response = client.get("/service-worker.js")
    assert response.status_code == 200


@pytest.mark.django_db
def test_sw_content_type(client):
    response = client.get("/service-worker.js")
    assert response["Content-Type"].startswith("application/javascript")


@pytest.mark.django_db
def test_sw_headers(client):
    response = client.get("/service-worker.js")
    assert response["Service-Worker-Allowed"] == "/"
    assert response["Cache-Control"] == "no-cache"


@pytest.mark.django_db
def test_sw_has_fetch_handler(client):
    """Chrome exige un fetch handler para considerar la app instalable."""
    response = client.get("/service-worker.js")
    body = response.content.decode("utf-8")
    assert "addEventListener('fetch'" in body or 'addEventListener("fetch"' in body


@pytest.mark.django_db
def test_sw_includes_version(client):
    response = client.get("/service-worker.js")
    body = response.content.decode("utf-8")
    assert "const VERSION" in body
    # El valor de VERSION no debe ser una cadena vacía entre comillas.
    assert 'const VERSION = ""' not in body
    assert "const VERSION = ''" not in body
```

- [ ] **Paso 2: Correr los tests y verificar que fallan.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" -m pytest pwa/tests/test_service_worker.py -v
```
Esperado: todos fallan con 404 (la ruta `/service-worker.js` aún no existe en `porra26/urls.py`).

> Nota: la ruta ya está añadida en Task 4 (paso 2), así que en realidad fallarán porque la plantilla `templates/pwa/service-worker.js` aún no existe → `TemplateDoesNotExist`. Cualquiera de los dos modos de fallo es válido como red baseline; la implementación en Task 6 los pone en verde.

---

## Task 6 — Plantilla del service worker + tests verdes

**Files:**
- Create: `templates/pwa/service-worker.js`

- [ ] **Paso 1: Crear `templates/pwa/service-worker.js`.**

```jinja
// Service worker mínimo de PORRA 26.
// Sin caché de assets en esta versión: el handler de fetch existe solo
// para cumplir el criterio de instalabilidad de Chrome (debe haber un
// fetch handler que responda a navegaciones).
//
// Cuando ampliemos a offline, este archivo crecerá con caches.open()
// en el install y una estrategia (cache-first / stale-while-revalidate)
// en fetch. La estructura ya queda preparada para esa evolución.

const VERSION = "{{ version }}";
const CACHE = `porra26-shell-${VERSION}`;

self.addEventListener('install', () => {
  // Activación inmediata sin esperar a que se cierren pestañas viejas.
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Borrado defensivo de caches de versiones previas (ahora no hay
    // ninguna, pero al añadir offline esto evita acumular basura).
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  // Passthrough explícito: necesario para que el navegador considere
  // la app instalable (Chrome exige un fetch handler que responda a
  // navegaciones).
  event.respondWith(fetch(event.request));
});
```

- [ ] **Paso 2: Correr los tests del SW hasta verde.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" -m pytest pwa/tests/test_service_worker.py -v
```
Esperado: 5 tests pasan.

- [ ] **Paso 3: Commit.**

```bash
git add pwa/tests/test_service_worker.py templates/pwa/service-worker.js
git commit -m "feat(pwa): service worker mínimo en raíz

JS renderizado por Django con VERSION inyectada (GIT_SHA / RAILWAY_GIT_COMMIT_SHA
o timestamp del proceso). Sin caché de assets: este SW solo cubre el
requisito de instalabilidad de Chrome con un fetch handler que pasa a la
red. Headers Service-Worker-Allowed: / y Cache-Control: no-cache.
5 tests cubren visibilidad pública, content-type, headers, fetch handler
y presencia de VERSION."
```

---

## Task 7 — Integrar meta tags y registro del SW en `base.html`

**Files:**
- Modify: `templates/base.html`

- [ ] **Paso 1: Añadir el bloque de meta tags PWA en el `<head>` (después del `<link rel="icon">`).**

Edición en `templates/base.html` líneas 14-16. Estado actual:
```html
  <link rel="icon" type="image/png" href="{% static 'img/logo.png' %}">
  <link rel="stylesheet" href="{% static 'css/styles.css' %}">
</head>
```

Nuevo estado:
```html
  <link rel="icon" type="image/png" href="{% static 'img/logo.png' %}">
  <link rel="manifest" href="{% url 'pwa-manifest' %}">
  <meta name="theme-color" content="#1a1530">
  <meta name="apple-mobile-web-app-capable" content="yes">
  <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
  <meta name="apple-mobile-web-app-title" content="PORRA 26">
  <link rel="apple-touch-icon" href="{% static 'img/pwa/apple-touch-icon.png' %}">
  <link rel="stylesheet" href="{% static 'css/styles.css' %}">
</head>
```

- [ ] **Paso 2: Añadir el script de registro del SW antes del cierre de `<body>`.**

Edición en `templates/base.html` justo después del último `<script>` existente y antes de `{% block scripts %}{% endblock %}`. Estado actual:
```html
  <script type="module" src="{% static 'js/winner-confetti.js' %}"></script>
  {% block scripts %}{% endblock %}
</body>
```

Nuevo estado:
```html
  <script type="module" src="{% static 'js/winner-confetti.js' %}"></script>
  <script>
    // Registro del service worker. `load` (no DOMContentLoaded) para no
    // competir con los recursos críticos del primer paint.
    if ("serviceWorker" in navigator) {
      window.addEventListener("load", function () {
        navigator.serviceWorker.register("{% url 'pwa-sw' %}", { scope: "/" });
      });
    }
  </script>
  {% block scripts %}{% endblock %}
</body>
```

- [ ] **Paso 3: Verificar manualmente que el HTML renderizado contiene las tags.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" -m pytest -q  # suite completa: nada debe romperse
```
Esperado: 539+ tests pasan (534 anteriores + ~10 nuevos).

```bash
"$VENV/python" manage.py runserver 0.0.0.0:8000 &
sleep 2
curl -s http://localhost:8000/ | grep -E '(rel="manifest"|theme-color|apple-touch-icon|serviceWorker)'
kill %1
```
Esperado: las 4 líneas aparecen.

> Si `runserver` requiere migraciones, usar `--skip-checks` o aplicar migraciones primero. La página `/` redirige al login si no hay sesión y el login es público, así que el HTML del `<head>` se sirve igualmente.

- [ ] **Paso 4: Commit.**

```bash
git add templates/base.html
git commit -m "feat(pwa): meta tags + registro del SW en base.html

link rel=manifest, theme-color #1a1530, meta legacy de iOS
(apple-mobile-web-app-capable / status-bar-style / title /
apple-touch-icon) y script inline que registra navigator.serviceWorker
en window.load con scope explícito '/'."
```

---

## Task 8 — Verificación final y PR

**Files:** ninguno (solo verificación).

- [ ] **Paso 1: Correr la suite completa y comprobar 0 fallos.**

```bash
VENV=/Users/ignacioborrajo/Documents/GitHub/apuestas-interna/.venv/bin
"$VENV/python" -m pytest -q
```
Esperado: línea final tipo `544 passed in N.NNs` (534 base + 5 manifest + 5 SW = 544). 0 fallos.

- [ ] **Paso 2: Pasar ruff sobre los archivos Python nuevos/modificados.**

```bash
"$VENV/python" -m ruff check pwa/ bin/generate_pwa_icons.py porra26/urls.py porra26/settings/base.py
```
Esperado: `All checks passed!`. Si hay quejas, ajustar y commitear como `chore(pwa): ruff fixes`.

- [ ] **Paso 3: Verificar `manage.py check`.**

```bash
"$VENV/python" manage.py check
```
Esperado: `System check identified no issues (0 silenced).`

- [ ] **Paso 4: Push de la rama del worktree y abrir PR.**

```bash
git push -u origin worktree-pwa-instalable-basico
gh pr create --title "feat(pwa): porra instalable como app (manifest + SW mínimo)" --body "$(cat <<'EOF'
## Summary

- App nueva `pwa/` con dos vistas: `/manifest.webmanifest` y `/service-worker.js`. Rutas en la raíz del proyecto para que el scope del SW sea `/`.
- Logo definitivo del Mundial 2026 sustituye al placeholder en `static/img/logo.png` (mismo path → login, topbar y password reset lo usan automáticamente).
- `bin/generate_pwa_icons.py` (idempotente): produce icon-192/512 any + maskable y apple-touch-icon 180 desde el logo. Reejecutable cuando cambie el logo.
- Meta tags PWA y registro del SW en `templates/base.html`.
- Sin offline ni push en esta versión: el SW solo cubre el criterio de instalabilidad de Chrome (un fetch handler que pasa a la red).

## Test plan

- [x] `pytest -q` → toda la suite verde (534 + 10 nuevos).
- [x] `manage.py check` sin warnings.
- [ ] Manual en producción tras deploy: Chrome DevTools → Application → Manifest sin errores, Service Workers registrado y activo.
- [ ] Manual móvil Android: banner "Instalar PORRA 26" aparece.
- [ ] Manual iOS: Safari → Compartir → "Añadir a pantalla de inicio" muestra icono y nombre correctos.

Spec: `docs/superpowers/specs/2026-06-04-pwa-instalable-basico-design.md`.
Plan: `docs/superpowers/plans/2026-06-04-pwa-instalable-basico.md`.
EOF
)"
```

Esperado: la salida termina con la URL del PR.

- [ ] **Paso 5: Salir del worktree.**

Llamar a `ExitWorktree` con `action: "keep"` para que la rama quede disponible localmente mientras el PR está abierto (cuando se mergee y borre la rama remota, se puede limpiar a mano con `git worktree remove`).

---

## Resumen de commits previstos

1. `docs(pwa): spec instalable básica` (ya hecho)
2. `feat(pwa): logo nuevo + script de generación de iconos`
3. `feat(pwa): esqueleto de app aislada`
4. `feat(pwa): manifest.webmanifest servido en raíz`
5. `feat(pwa): service worker mínimo en raíz`
6. `feat(pwa): meta tags + registro del SW en base.html`
7. (opcional) `chore(pwa): ruff fixes` si lint pide algo

Total esperado: 6-7 commits.
