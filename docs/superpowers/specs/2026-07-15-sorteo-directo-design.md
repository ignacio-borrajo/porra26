# Sorteo de camiseta en directo — un botón, eliminación automática y espectadores

**Fecha:** 2026-07-15 · **Estado:** aprobado · Evoluciona `2026-07-15-sorteo-camiseta-design.md`

## Qué cambia

1. El gestor pulsa **"Iniciar sorteo"** una sola vez; a partir de ahí la ruleta
   elimina participantes automáticamente hasta que queda el ganador (desaparece
   el modo de tanda por pulsación).
2. `/sorteo/` se abre a **todos los usuarios logueados**: cualquiera que entre ve
   la ruleta girando en directo, sincronizada con el resto de pantallas.

## Reglas (decididas con el usuario)

- **Cadencia:** un eliminado cada **30 segundos** (constante `CADENCE_SECONDS`).
- **Dramatismo:** giros de 3–4 vueltas al principio; con **10 o menos** en juego,
  5–6 vueltas y frenada más larga.
- El resultado se decide **100 % en servidor** con `random.SystemRandom`.

## Arquitectura

### Guion precalculado (sin procesos en segundo plano)

Al pulsar "Iniciar sorteo" el servidor ejecuta el sorteo completo en ese instante:
congela el snapshot de elegibles (activos + jugadores + pagados), baraja con
`SystemRandom` y asigna a cada entry su `eliminated_order` (1..n−1) y su
`eliminated_at` **programado** = `started_at + orden × 30 s`. El último sin orden
es el ganador. No hace falta cron ni worker: el guion vive en BD y los clientes
lo reproducen. Compatible con gunicorn síncrono en Railway.

- `Raffle.started_at` (nuevo, null hasta iniciar).
- `RaffleEntry.eliminated_at` pasa a ser el instante **programado** de la caída.
- Si existe un sorteo antiguo sin iniciar (flujo por tandas legado), "Iniciar" lo
  borra y crea uno nuevo. Si ya hay uno iniciado → 400.

### Anti-spoiler

El estado público **nunca** revela eliminaciones con `eliminated_at` posterior a
`now + REVEAL_AHEAD_SECONDS` (20 s): lo justo para que el cliente pueda apuntar
el giro antes de frenar, pero sin que nadie vea el ganador en las devtools.

### Sincronización

- `GET /sorteo/estado/` (login requerido) → `serverNowMs`, `startedAtMs` y
  participantes con `eliminatedOrder`/`eliminatedAtMs` solo si ya son visibles.
- Cada cliente calcula el offset con el reloj del servidor y hace **polling cada
  5 s** (se detiene cuando el guion visible está completo).
- Cada giro se anima para que la flecha caiga **exactamente** en el timestamp
  programado → todas las pantallas ven caer al mismo eliminado a la vez.
- Quien entra a mitad (o recarga) hace fast-forward: ruleta recompuesta sin los
  ya eliminados y se incorpora al punto actual. Si llega acabado, ve al ganador.

### Endpoints

- `GET /sorteo/` — página, ahora `LoginRequiredMixin` (todos los usuarios).
- `GET /sorteo/estado/` — JSON de estado visible (login).
- `POST /sorteo/iniciar/` — gestor; crea snapshot + guion; `AuditLog raffle_start`.
- `POST /sorteo/reiniciar/` — gestor; sigue igual y sirve de freno de emergencia
  a mitad de sorteo (los espectadores lo detectan por polling y vuelven a espera).

### UI

- Botón **"Iniciar sorteo"** (solo gestor) sustituye a "Que gire la ruleta".
- Jugadores antes del inicio: ruleta completa + "El sorteo empezará en breve".
- Botón **"Activar sonido"** para espectadores (el navegador bloquea WebAudio sin
  gesto del usuario); el gestor lo activa implícitamente al pulsar iniciar.
- Menú "Sorteo" visible para todos (escritorio + drawer móvil).
- Ganador: overlay + confeti como hasta ahora, disparado al caer la última bola.
- **Contador** "Siguiente tirada en N s" entre giros (el estado envía `cadenceMs`).
- El gajo del **eliminado permanece en la ruleta** (atenuado, gris) hasta que
  empieza la siguiente tirada; entonces desaparece y la ruleta se recompone.
- Las vueltas por giro son **enteras** (3–4 normales, 5–6 dramáticas): el
  aterrizaje suma `vueltas × 360° + delta` y una fracción de vuelta desplazaría
  la caída respecto a la flecha (bug corregido tras el estreno de la v1).

## Tests

- Acceso: página y estado → cualquier usuario logueado; iniciar/reiniciar → solo gestor.
- `start_raffle`: guion completo (n−1 eliminados a 30 s, 1 ganador), snapshot
  congelado, <2 participantes → error, ya iniciado → 400, legado sin iniciar se regenera.
- `public_state`: oculta eliminaciones más allá del horizonte de 20 s; revela la
  inminente; antes de iniciar lista elegibles.
- Topbar: enlace Sorteo visible para jugadores y gestores.
