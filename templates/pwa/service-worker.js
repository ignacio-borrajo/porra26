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
