# Spec — PWA instalable básica

## Problema

La aplicación se usa principalmente en el móvil durante los partidos: comprobar pronósticos, mirar la clasificación, meter resultados (gestor). Hoy es una web Django normal, sin manifest ni service worker, así que no se puede "instalar" como app. Eso obliga a navegar por el navegador y pasa por:

- El usuario tiene que buscarla en el historial o tener un favorito.
- Cada apertura muestra la barra de URL y los chrome del navegador, restando espacio útil en pantallas pequeñas.
- No hay icono propio en la pantalla de inicio.

## Objetivo

Que el navegador (Chrome en Android, Safari en iOS, Edge/Chrome en escritorio) considere la app instalable y ofrezca "Añadir a pantalla de inicio" / "Instalar app". Una vez instalada:

- Se abre con icono propio en el launcher.
- Arranca en modo standalone (sin barra de URL).
- Muestra un splash screen con el color y el icono de marca.

Sin offline, sin push, sin caché custom — solo lo necesario para cumplir los criterios de instalabilidad.

## Alcance

**Dentro:**

- Manifest (`/manifest.webmanifest`) con metadatos e iconos.
- Service worker (`/service-worker.js`) mínimo que cumpla los criterios de Chrome (un fetch handler que responde a navegaciones).
- Iconos PWA a partir del logo nuevo (`Logo_porras.png`) — sustituye también al `static/img/logo.png` actual, que se usa en login y topbar.
- Meta tags y registro del SW en `templates/base.html`.
- Tests de las dos vistas nuevas.

**Fuera (futuro):**

- Cacheo del shell (offline ligero).
- Caché de datos dinámicos (offline completo con SWR).
- Web Push (claves VAPID, suscripciones, hooks de cierre y resultados).
- Botón propio de instalación capturando `beforeinstallprompt`.
- Favicon optimizado para tamaños pequeños (solo trofeo, sin texto).

## Decisiones de diseño

### Sin librería externa

Se evaluó `django-pwa`. Para este alcance "instalable básico" mete una dependencia y configuración (`PWA_*` settings) para algo que son ~80 líneas de código propio. La aproximación manual da control total del SW cuando crezcamos a offline real y mantiene la dependencia tree limpia.

### Una app dedicada `pwa/`

Aunque el código cabe en `core/`, se aísla en su propia app para que (a) la responsabilidad sea evidente, (b) sea borrable si algún día cambiamos a otra solución, (c) los tests vivan junto al código.

### Rutas en la raíz del proyecto

`/manifest.webmanifest` y `/service-worker.js` se montan en `porra26/urls.py` directamente, no a través de `pwa/urls.py` con prefijo. El **scope** del service worker es la ruta donde se sirve: para que controle toda la app debe servirse desde `/`.

### Manifest renderizado como template Django

En lugar de un archivo estático, lo sirve una view que usa `render()` sobre `templates/pwa/manifest.webmanifest`. Razones:

- Las URLs de los iconos pasan por `{% static %}` → compatible con el hashing de WhiteNoise en producción (`STATICFILES_STORAGE = CompressedManifestStaticFilesStorage` si se activa más adelante).
- Permite usar `Content-Type: application/manifest+json` correcto.
- Una sola fuente de verdad: si se renombra un asset, el manifest sigue válido sin tocar JSON a mano.

### Service worker versionado

`templates/pwa/service-worker.js` se renderiza con una variable `VERSION` calculada en la vista:

1. Primero intenta `os.environ.get("GIT_SHA")` (Railway lo expone como `RAILWAY_GIT_COMMIT_SHA`, lo mapeamos).
2. Si no, usa el timestamp de arranque del proceso (suficiente en dev).

Esta versión se usa como sufijo del nombre de caché (`porra26-shell-${VERSION}`). En esta versión no cacheamos nada, pero queda la infraestructura para que al añadir offline el `activate` borre versiones previas correctamente.

### `Service-Worker-Allowed: /` explícito

El SW se sirve desde `/service-worker.js`, así que el scope por defecto ya es `/`. Aun así, fijamos la cabecera `Service-Worker-Allowed: /` por defensa: si en el futuro algún reverse proxy (Railway, Cloudflare) reescribe rutas, el scope sigue claro.

### `Cache-Control: no-cache` en el SW

El propio service worker NO debe ser cacheado por HTTP — el navegador tiene su propia lógica de actualización (compara byte a byte con la versión anterior). Si lo cacheamos vía CDN, los despliegues no se notarían hasta que expire la caché. Header explícito para evitarlo.

### Iconos generados por script reejecutable

`bin/generate_pwa_icons.py` lee `static/img/logo.png` y escribe a `static/img/pwa/`. Cuando cambie el logo (ahora con `Logo_porras.png`, en el futuro con otra versión), basta con reemplazar el fuente y reejecutar. Idempotente.

**Tamaños generados:**

| Archivo | Tamaño | Propósito | Logo ocupa |
|---------|--------|-----------|------------|
| `icon-192.png` | 192×192 | `purpose: any` (manifest) | ~80% |
| `icon-512.png` | 512×512 | `purpose: any` (manifest, splash) | ~80% |
| `icon-192-maskable.png` | 192×192 | `purpose: maskable` (Android adaptable) | ~60% |
| `icon-512-maskable.png` | 512×512 | `purpose: maskable` (Android adaptable) | ~60% |
| `apple-touch-icon.png` | 180×180 | iOS home screen | ~80% |

Fondo del cuadrado: `#1a1530` (derivado del `--bg-0` del tema oscuro, `oklch(0.16 0.02 275)`).

**Zona segura maskable:** la spec PWA define que un icono maskable solo garantiza visible el 80% central (radio del 40% desde el centro). Por eso el logo en maskable ocupa solo ~60% del lienzo: deja margen suficiente para que Android lo recorte a círculo/squircle sin comerse los balones laterales ni el texto "MUNDIAL 2026".

### Tema y colores

- `theme_color` y `background_color` en manifest: `#1a1530`. Pinta:
  - La barra de estado del SO al abrir en modo standalone.
  - El splash screen (fondo + icono centrado) antes del primer paint.
- Meta `<meta name="theme-color" content="#1a1530">` complementa para navegadores que no leen el manifest a tiempo.
- La app tiene tema claro y oscuro, pero el tema por defecto del proyecto es oscuro, y `theme_color` debe ser un único color fijo. Acepta inconsistencia visual cuando el usuario tiene el claro activo — el splash y la barra de estado quedan oscuros aun así. No es bloqueante.

### iOS legacy meta tags

Safari iOS no implementa el manifest completo. Necesita meta tags propias para reconocer la app como "Web App" al añadir a inicio:

- `apple-mobile-web-app-capable: yes` → oculta los chrome del navegador.
- `apple-mobile-web-app-status-bar-style: black-translucent` → barra de estado transparente sobre el contenido.
- `apple-mobile-web-app-title: PORRA 26` → nombre debajo del icono (limita a ~12 chars).
- `<link rel="apple-touch-icon">` → el icono de 180×180.

### Registro inline del SW en `base.html`

Un único script inline:

```html
<script>
  if ("serviceWorker" in navigator) {
    window.addEventListener("load", () => {
      navigator.serviceWorker.register("{% url 'pwa-sw' %}", { scope: "/" });
    });
  }
</script>
```

Inline porque son 5 líneas y evita una petición HTTP extra. `load` (no `DOMContentLoaded`) para no competir con recursos críticos. El feature check evita errores en navegadores antiguos.

## Modelo de archivos

```
pwa/
  __init__.py
  apps.py
  views.py                                 # manifest(), service_worker(), _sw_version()
  urls.py                                  # vacío o un urlpatterns mínimo; las rutas reales viven en porra26/urls.py
  tests/
    __init__.py
    test_manifest.py
    test_service_worker.py

templates/
  pwa/
    manifest.webmanifest                   # template Django, Content-Type application/manifest+json
    service-worker.js                      # template Django, recibe {{ version }}

static/
  img/
    logo.png                               # REEMPLAZADO por Logo_porras.png (mismo nombre, mismo path)
    pwa/                                   # NUEVO directorio
      icon-192.png
      icon-512.png
      icon-192-maskable.png
      icon-512-maskable.png
      apple-touch-icon.png

bin/
  generate_pwa_icons.py                    # script Pillow, idempotente
```

Modificaciones en archivos existentes:

- `porra26/urls.py`: dos `path()` nuevos a la raíz.
- `porra26/settings/base.py`: `"pwa"` en `INSTALLED_APPS`.
- `templates/base.html`: bloque de meta tags PWA + script de registro.

## Contratos

### `GET /manifest.webmanifest`

- **Auth**: pública (anónima).
- **Status**: 200.
- **Content-Type**: `application/manifest+json`.
- **Body**: JSON parseable con al menos estos campos:
  - `name`: `"PORRA 26 · Mundial 2026"`
  - `short_name`: `"PORRA 26"`
  - `description`: `"Porra interna del Mundial FIFA 2026."`
  - `lang`: `"es-ES"`
  - `dir`: `"ltr"`
  - `start_url`: `"/"`
  - `scope`: `"/"`
  - `display`: `"standalone"`
  - `orientation`: `"any"`
  - `background_color`: `"#1a1530"`
  - `theme_color`: `"#1a1530"`
  - `icons`: array con 4 entradas (192/512 any + 192/512 maskable), cada una con `src`, `sizes`, `type: image/png`, `purpose`.

### `GET /service-worker.js`

- **Auth**: pública (anónima).
- **Status**: 200.
- **Content-Type**: `application/javascript`.
- **Headers**:
  - `Service-Worker-Allowed: /`
  - `Cache-Control: no-cache`
- **Body**: JS válido que registra al menos un `addEventListener('fetch', …)` que responde a peticiones (criterio de instalabilidad de Chrome). Contiene una constante `VERSION` resuelta en server-side.

## Plan de tests

Tests TDD en `pwa/tests/`. Pequeños y deterministas:

### `test_manifest.py`

1. `test_manifest_is_public` — cliente sin login → 200.
2. `test_manifest_content_type` — `application/manifest+json`.
3. `test_manifest_is_valid_json` — `json.loads(response.content)` sin error.
4. `test_manifest_has_required_fields` — comprueba presencia de `name`, `short_name`, `start_url`, `display`, `theme_color`, `background_color`.
5. `test_manifest_has_required_icons` — el array `icons` contiene al menos un 192 y un 512, ambos `purpose: any`, más un maskable.

### `test_service_worker.py`

1. `test_sw_is_public` — cliente sin login → 200.
2. `test_sw_content_type` — `application/javascript`.
3. `test_sw_headers` — `Service-Worker-Allowed: /` y `Cache-Control: no-cache` presentes.
4. `test_sw_has_fetch_handler` — el body contiene `addEventListener('fetch'` (criterio Chrome).
5. `test_sw_includes_version` — el body contiene `const VERSION =` con un valor no vacío.

### Verificación manual (no automatizable)

Tras desplegar, abrir Chrome DevTools en producción → Application:

- **Manifest**: validar que aparece sin errores, iconos cargan, sin warnings rojos.
- **Service Workers**: registrado, activo, sin errores en consola.
- **Lighthouse → PWA**: pasa los checks de instalabilidad (Chrome muestra prompt o el "+" en barra de URL).
- En móvil Android: aparece el banner "Instalar PORRA 26".
- En iOS: Safari → Compartir → "Añadir a pantalla de inicio" usa el icono y nombre correctos.

## Verificación de no-regresión

- Suite completa sigue pasando (534 tests actuales + nuevos).
- Login, password reset y topbar siguen mostrando el logo correctamente tras el reemplazo (proporciones casi idénticas: 511×472 → 520×480, 8% más alto, despreciable a 44-48 px).

## Trabajo no realizado intencionadamente

- No se añade botón "Instalar" en la UI. El usuario instala vía el prompt nativo del navegador. Si en uso real vemos baja conversión, lo añadimos en una iteración posterior.
- No se desactiva `whitenoise` ni se cambia `STATIC_URL` en prod. WhiteNoise sirve los iconos sin problema.
- No se genera un favicon optimizado pequeño. El `logo.png` actual sigue siendo el favicon vía la línea existente en `base.html`.
- No se cambia el comportamiento de tema claro/oscuro. `theme_color` queda fijo en el color oscuro.
