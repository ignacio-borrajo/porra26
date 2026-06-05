// Pull-to-refresh para iOS instalado como PWA.
//
// En modo standalone (apple-mobile-web-app-capable=yes + abrir desde el
// home screen) Safari oculta su chrome y, con él, el gesto nativo de
// pull-to-refresh. Aquí lo reimplementamos solo en ese escenario: en
// Safari normal y en otros navegadores no hacemos nada para no pisar el
// gesto del sistema.

const isStandalone =
  window.navigator.standalone === true ||
  window.matchMedia("(display-mode: standalone)").matches;

const isIOS = /iPad|iPhone|iPod/.test(window.navigator.userAgent);

if (isStandalone && isIOS) {
  const THRESHOLD = 70;        // px que hay que arrastrar para refrescar
  const MAX_PULL = 140;         // límite visual del arrastre
  const DAMPING = 0.55;         // factor de resistencia (rubber band)

  const indicator = document.createElement("div");
  indicator.className = "ptr-indicator";
  indicator.setAttribute("aria-hidden", "true");
  indicator.innerHTML = `
    <svg viewBox="0 0 24 24" width="22" height="22" fill="none"
         stroke="currentColor" stroke-width="2.4" stroke-linecap="round"
         stroke-linejoin="round">
      <path d="M21 12a9 9 0 1 1-3-6.7"/>
      <path d="M21 4v5h-5"/>
    </svg>
  `;

  const style = document.createElement("style");
  style.textContent = `
    .ptr-indicator {
      position: fixed;
      top: env(safe-area-inset-top, 0px);
      left: 50%;
      z-index: 9999;
      width: 44px;
      height: 44px;
      display: grid;
      place-items: center;
      border-radius: 999px;
      background: var(--surface, rgba(255,255,255,0.08));
      backdrop-filter: blur(var(--glass-blur, 18px)) saturate(1.3);
      -webkit-backdrop-filter: blur(var(--glass-blur, 18px)) saturate(1.3);
      border: 1px solid var(--border-hi, rgba(255,255,255,0.18));
      color: var(--text, white);
      box-shadow: var(--shadow-glow, 0 12px 30px -10px rgba(0,0,0,0.4));
      opacity: 0;
      pointer-events: none;
      transform: translate(-50%, -120%) rotate(0deg);
      transition: opacity 0.18s ease, transform 0.18s var(--ease-out, cubic-bezier(0.16,1,0.3,1));
      will-change: transform, opacity;
    }
    .ptr-indicator[data-state="dragging"] { transition: none; }
    .ptr-indicator[data-state="refreshing"] svg { animation: ptr-spin 0.85s linear infinite; }
    @keyframes ptr-spin { to { transform: rotate(360deg); } }
  `;

  document.head.appendChild(style);
  document.body.appendChild(indicator);

  let startY = 0;
  let startX = 0;
  let pulling = false;
  let refreshing = false;
  let pointerId = null;

  const setTransform = (distance, rotation) => {
    // -120% es la posición oculta (justo por encima del viewport).
    const y = Math.min(distance, MAX_PULL);
    indicator.style.opacity = String(Math.min(1, distance / THRESHOLD));
    indicator.style.transform = `translate(-50%, ${y - 60}px) rotate(${rotation}deg)`;
  };

  const reset = () => {
    indicator.dataset.state = "";
    indicator.style.opacity = "0";
    indicator.style.transform = "translate(-50%, -120%) rotate(0deg)";
  };

  const onTouchStart = (event) => {
    if (refreshing) return;
    if (event.touches.length !== 1) return;
    if (window.scrollY > 0) return;

    // Opt-out: cualquier ancestro con [data-no-ptr] desactiva el gesto
    // (útil para carruseles horizontales o áreas con scroll propio).
    const target = event.target;
    if (target && target.closest && target.closest("[data-no-ptr]")) return;

    startY = event.touches[0].clientY;
    startX = event.touches[0].clientX;
    pulling = true;
    pointerId = event.touches[0].identifier;
  };

  const onTouchMove = (event) => {
    if (!pulling || refreshing) return;

    const touch = Array.from(event.touches).find((t) => t.identifier === pointerId);
    if (!touch) return;

    const dy = touch.clientY - startY;
    const dx = touch.clientX - startX;

    // Si el primer movimiento es claramente horizontal, abandonamos
    // para no interferir con swipes laterales (carruseles, etc.).
    if (Math.abs(dx) > Math.abs(dy) && Math.abs(dx) > 8) {
      pulling = false;
      reset();
      return;
    }

    if (dy <= 0) {
      // El usuario está empujando hacia arriba: no es PTR. Salimos
      // sin preventDefault para que el scroll normal funcione.
      pulling = false;
      reset();
      return;
    }

    // A partir de aquí estamos arrastrando hacia abajo desde el tope:
    // bloqueamos el rubber band nativo del body y dibujamos el indicador.
    event.preventDefault();
    const damped = Math.pow(dy, DAMPING) * 4;
    indicator.dataset.state = "dragging";
    setTransform(damped, Math.min(360, damped * 2.4));
  };

  const onTouchEnd = (event) => {
    if (!pulling || refreshing) {
      pulling = false;
      return;
    }
    pulling = false;

    const lastTouch = event.changedTouches && event.changedTouches[0];
    const dy = lastTouch ? lastTouch.clientY - startY : 0;
    const damped = Math.pow(Math.max(0, dy), DAMPING) * 4;

    if (damped >= THRESHOLD) {
      refreshing = true;
      indicator.dataset.state = "refreshing";
      indicator.style.opacity = "1";
      indicator.style.transform = "translate(-50%, 16px) rotate(0deg)";
      // Pequeño retardo para que el usuario vea el spinner antes del reload.
      window.setTimeout(() => window.location.reload(), 280);
    } else {
      reset();
    }
  };

  const onTouchCancel = () => {
    if (refreshing) return;
    pulling = false;
    reset();
  };

  document.addEventListener("touchstart", onTouchStart, { passive: true });
  document.addEventListener("touchmove", onTouchMove, { passive: false });
  document.addEventListener("touchend", onTouchEnd, { passive: true });
  document.addEventListener("touchcancel", onTouchCancel, { passive: true });
}
