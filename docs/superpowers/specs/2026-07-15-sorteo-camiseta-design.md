# Sorteo de camiseta — ruleta de eliminación

**Fecha:** 2026-07-15 · **Estado:** aprobado (brainstorming con mockups)

## Qué es

Sección nueva a pantalla completa con una **ruleta de eliminación** para sortear una
camiseta de la selección entre los participantes de la porra. El show se hace en
directo por videollamada compartiendo la pantalla del gestor; el resto de jugadores
podrá (más adelante) abrir la página y ver el estado. **De momento la sección entera
es solo para gestores** (menú y vista), para validar internamente.

## Reglas del sorteo (decididas con el usuario)

- **Participantes:** jugadores `is_active=True`, `is_jugador=True` y con `payment.paid=True`.
  Se **congelan** (snapshot) al crear el sorteo para que altas/pagos posteriores no muevan la ruleta.
- **Por descarte:** cada tirada elimina al participante donde cae la flecha. Gana el último que queda.
- **Tandas:** cada pulsación del botón lanza una tanda automática:
  - Si quedan **más de 15**: la tanda elimina `min(5, restantes − 15)` de uno en uno encadenados
    (giro → eliminado → vuelve a girar solo).
  - Si quedan **15 o menos**: cada pulsación elimina **1**.
  - Con 70 participantes: 11 pulsaciones de 5 + 14 de 1.
- **Aleatoriedad en servidor** (`random.SystemRandom`), se persiste el orden de eliminación.
- **Reinicio:** botón discreto "Reiniciar sorteo" (gestor, con confirmación) para ensayar.
  Borra el sorteo entero.
- Si se recarga la página a mitad, el sorteo continúa donde estaba (estado en BD).

## Visual (opción A del mockup + layout validado)

- **Izquierda:** ruleta SVG ocupando todo el alto disponible. Gajos con colores de la
  paleta Mundial y el **nombre rotado** dentro de cada gajo (pequeños con 70, crecen al
  eliminar). Contador central con los que quedan. **Flecha a las 3 en punto** (derecha).
- **Derecha:** panel con el **nombre en grande** del eliminado (durante el giro "traquetea"
  el nombre que cruza la flecha), contadores En juego / Eliminados, botón
  **"Que gire la ruleta"** (solo gestor) y lista de últimos eliminados tachados.
- **Giro realista:** aceleración + deceleración larga (~2 giros completos mínimo),
  **tick sonoro** (WebAudio, sin assets) cada vez que un gajo cruza la flecha.
- **Eliminado:** su nombre aparece en grande con animación y su gajo desaparece con
  animación; la ruleta se recompone y, si la tanda sigue, vuelve a girar sola.
- **Ganador:** overlay superpuesto con el nombre en gigante + **confeti** reutilizando
  `canvas-confetti` ya vendorizado (patrón de `winner-confetti.js`).

## Arquitectura

Nueva app Django **`raffle`**, montada en `/sorteo/` (namespace `raffle`).

### Modelos

- `Raffle(created_at)` — un sorteo; el activo es el más reciente.
- `RaffleEntry(raffle FK related_name="entries", player FK, eliminated_order int null, eliminated_at null)`
  — snapshot de participantes; `eliminated_order` 1..n según van cayendo. Ganador = única entry sin eliminar cuando solo queda una.

### Endpoints (todos `GestorRequiredMixin` de momento)

- `GET /sorteo/` — página. Estado embebido como JSON (`entries` con id/nombre/orden de eliminación, flags, urls).
- `POST /sorteo/girar/` — crea sorteo+snapshot si no existe; elimina la tanda que toque
  y devuelve `{"eliminated": [ids en orden], "remaining": n, "winner": id|null}`.
  Transacción atómica; 400 si ya hay ganador o no hay participantes suficientes.
- `POST /sorteo/reiniciar/` — borra el sorteo. `AuditLog` con acciones `raffle_spin` / `raffle_reset`.

### Frontend

- `templates/raffle/draw.html` (extiende `base.html`) + `static/js/raffle-wheel.js` (módulo) + estilos en `static/css/styles.css`.
- El JS anima en cliente la secuencia exacta que devolvió el servidor (el resultado nunca se decide en cliente).

### Navegación

- Item "Sorteo" (icono `target`) en `_topbar.html`, dentro de los bloques `{% if user.is_gestor %}` (nav escritorio + drawer móvil).

## Tests

- Acceso: no-gestor → redirect; gestor → 200.
- Snapshot: solo activos+jugadores+pagados.
- Tandas: 70→elimina 5; 17→2; 16→1; ≤15→1; con 2 restantes → devuelve `winner`; con ganador → 400.
- Orden de eliminación secuencial y persistente; reiniciar borra todo.

## Fuera de alcance (por ahora)

- Vista para jugadores no gestores (se abrirá quitando el mixin cuando se valide).
- Sincronización en directo (polling/SSE) — el directo es por videollamada.
