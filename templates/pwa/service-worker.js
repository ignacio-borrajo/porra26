// Service worker de PORRA 26.
//
// Estrategia mínima:
//   - Precachea una página /offline/ en el `install` para tener un fallback
//     servible sin red.
//   - En navegaciones (`request.mode === 'navigate'`), intenta la red y, si
//     falla o el origen devuelve 5xx, sirve la página /offline/ desde caché.
//     Así, durante el hueco de redeploy de Railway (o cualquier caída), la
//     PWA muestra una pantalla controlada en vez del error genérico del
//     proxy.
//   - Para todo lo demás (assets, XHR/fetch de la app), passthrough: que el
//     navegador decida y los componentes JS manejen el error como vean.

const VERSION = "{{ version }}";
const CACHE = `porra26-shell-${VERSION}`;
const OFFLINE_URL = "/offline/";

self.addEventListener('install', (event) => {
  event.waitUntil((async () => {
    const cache = await caches.open(CACHE);
    // `cache: 'reload'` fuerza ir al origen ignorando HTTP cache del navegador:
    // así al desplegar una versión nueva del SW, el offline cacheado es el de
    // ESA versión, no uno viejo todavía válido en disk cache.
    await cache.add(new Request(OFFLINE_URL, { cache: 'reload' }));
    // Activación inmediata sin esperar a que se cierren pestañas viejas.
    await self.skipWaiting();
  })());
});

self.addEventListener('activate', (event) => {
  event.waitUntil((async () => {
    // Borrado defensivo de caches de versiones previas.
    const keys = await caches.keys();
    await Promise.all(
      keys.filter((k) => k !== CACHE).map((k) => caches.delete(k))
    );
    await self.clients.claim();
  })());
});

self.addEventListener('fetch', (event) => {
  const req = event.request;
  // Solo interceptamos navegaciones (carga de documento HTML del scope).
  // El resto (CSS/JS/imágenes/XHR) sigue passthrough.
  if (req.mode !== 'navigate') {
    event.respondWith(fetch(req));
    return;
  }

  event.respondWith((async () => {
    try {
      const res = await fetch(req);
      // Los 5xx incluyen el 502/503 que sirve Railway cuando el contenedor
      // está reiniciándose en un deploy. Caemos al fallback en ese caso.
      if (res.status >= 500 && res.status <= 599) {
        throw new Error(`upstream ${res.status}`);
      }
      return res;
    } catch (e) {
      const cache = await caches.open(CACHE);
      const cached = await cache.match(OFFLINE_URL);
      if (cached) return cached;
      // Sin offline cacheado (caso muy raro: install falló): devolvemos un
      // error de red estándar para que el navegador muestre su pantalla.
      return Response.error();
    }
  })());
});
