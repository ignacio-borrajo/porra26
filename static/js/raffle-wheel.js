/* Ruleta de eliminación del sorteo de camiseta, en directo.
 *
 * El servidor decide SIEMPRE el resultado: "Iniciar sorteo" precalcula el
 * guion completo (orden + timestamp programado de cada caída) y estado/ lo
 * revela poco a poco (anti-spoiler). Aquí solo se reproduce: polling ligero,
 * reloj sincronizado con el servidor y cada giro animado para que la flecha
 * caiga exactamente en su timestamp, de modo que todas las pantallas —gestor
 * y espectadores— vean caer al mismo eliminado a la vez.
 */

const SVG_NS = "http://www.w3.org/2000/svg";
const RADIUS = 150;
const HUB_RADIUS = 30;
const PALETTE = [
  "var(--c-pink)",
  "var(--c-cyan)",
  "var(--c-lime)",
  "var(--c-yellow)",
  "var(--c-blue)",
  "var(--c-green)",
  "var(--c-red)",
];

const POLL_MS = 5000;
// Las vueltas deben ser ENTERAS: el aterrizaje suma turns*360 + delta, y una
// fracción de vuelta desplaza la caída ese ángulo respecto a la flecha.
const NORMAL_TURNS = [3, 4]; // vueltas por giro (decidido con el gestor)
const DRAMATIC_TURNS = [5, 6]; // vueltas para los últimos
const DRAMATIC_FROM = 10; // "los últimos" = 10 o menos en juego
const NORMAL_SPIN_MS = 8000;
const DRAMATIC_SPIN_MS = 13000;
const MIN_SPIN_MS = 800; // sin tiempo para animar: la caída se aplica en seco

function getCsrf() {
  const m = document.cookie.match(/csrftoken=([^;]+)/);
  return m ? m[1] : "";
}

const root = document.querySelector("[data-raffle]");
const dataEl = document.getElementById("raffle-data");
if (root && dataEl) init(JSON.parse(dataEl.textContent));

function init(state) {
  const wheelSvg = root.querySelector("[data-raffle-wheel]");
  const labelEl = root.querySelector("[data-raffle-label]");
  const nameEl = root.querySelector("[data-raffle-name]");
  const aliveEl = root.querySelector("[data-raffle-alive]");
  const outEl = root.querySelector("[data-raffle-out]");
  const elimsEl = root.querySelector("[data-raffle-elims]");
  const nextEl = root.querySelector("[data-raffle-next]");
  const startBtn = root.querySelector("[data-raffle-start]");
  const soundBtn = root.querySelector("[data-raffle-sound]");
  const resetForm = root.querySelector("[data-raffle-reset]");
  const overlay = document.querySelector("[data-raffle-overlay]");
  const winnerNameEl = document.querySelector("[data-raffle-winner-name]");

  let participants = [];
  let byId = new Map();
  let eliminated = [];
  let alive = [];
  const knownEvents = new Map(); // orden -> { id, atMs } revelados por el servidor
  let processed = 0; // último orden ya reproducido en esta pantalla
  let finalOrder = 0; // total - 1: la última caída deja al ganador
  let started = false;
  let finished = false;
  let sawLiveAction = false; // distingue directo de fast-forward (recargas)
  let waitTimer = null;
  let startedAtMs = null;
  let cadenceMs = null;
  let doomedId = null; // eliminado que sigue en la ruleta hasta la siguiente tirada

  let rotation = 0; // grados acumulados de la ruleta
  let spinning = false;
  let soundOn = false;
  let audioCtx = null;
  let wheelGroup = null;
  let segmentEls = new Map();

  let clockOffset = state.serverNowMs - Date.now();
  const serverNow = () => Date.now() + clockOffset;

  // --- Sonido: tick corto por gajo, sin assets (WebAudio) ---
  function tick() {
    if (!soundOn || !audioCtx) return;
    const t = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "triangle";
    osc.frequency.value = 620 + Math.random() * 60;
    gain.gain.setValueAtTime(0.12, t);
    gain.gain.exponentialRampToValueAtTime(0.001, t + 0.045);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(t);
    osc.stop(t + 0.05);
  }

  function ensureAudio() {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    }
    if (audioCtx && audioCtx.state === "suspended") audioCtx.resume();
  }

  function setSound(on) {
    soundOn = on;
    if (on) ensureAudio();
    if (soundBtn) {
      soundBtn.textContent = on ? "🔇 Silenciar" : "🔊 Activar sonido";
    }
  }

  // --- Geometría ---
  const step = () => 360 / alive.length;

  function polar(deg, r) {
    const rad = (deg * Math.PI) / 180;
    return [r * Math.cos(rad), r * Math.sin(rad)];
  }

  function segmentPath(a0, a1) {
    const [x0, y0] = polar(a0, RADIUS);
    const [x1, y1] = polar(a1, RADIUS);
    const large = a1 - a0 > 180 ? 1 : 0;
    return `M0,0 L${x0},${y0} A${RADIUS},${RADIUS} 0 ${large} 1 ${x1},${y1} Z`;
  }

  function segmentColor(i, n) {
    // Paleta cíclica evitando que el último gajo repita color con el primero.
    let idx = i % PALETTE.length;
    if (i === n - 1 && idx === 0) idx = 3;
    return PALETTE[idx];
  }

  function fontSizeFor(n) {
    return Math.min(12, Math.max(4.4, 290 / n));
  }

  function buildWheel() {
    wheelSvg.textContent = "";
    segmentEls = new Map();
    wheelGroup = document.createElementNS(SVG_NS, "g");
    wheelGroup.setAttribute("transform", `rotate(${rotation})`);
    const n = alive.length;
    const fs = fontSizeFor(n);
    alive.forEach((p, i) => {
      const a0 = i * step();
      const a1 = (i + 1) * step();
      const g = document.createElementNS(SVG_NS, "g");
      g.classList.add("raffle-seg");
      const path = document.createElementNS(SVG_NS, "path");
      path.setAttribute("d", n === 1 ? "" : segmentPath(a0, a1));
      if (n === 1) {
        const c = document.createElementNS(SVG_NS, "circle");
        c.setAttribute("r", RADIUS);
        c.setAttribute("fill", segmentColor(0, 1));
        g.appendChild(c);
      } else {
        path.setAttribute("fill", segmentColor(i, n));
        g.appendChild(path);
      }
      const text = document.createElementNS(SVG_NS, "text");
      const mid = (a0 + a1) / 2;
      text.setAttribute("transform", `rotate(${mid}) translate(${RADIUS - 6},0)`);
      text.setAttribute("text-anchor", "end");
      text.setAttribute("dominant-baseline", "middle");
      text.setAttribute("font-size", fs);
      text.textContent = p.name;
      g.appendChild(text);
      wheelGroup.appendChild(g);
      segmentEls.set(p.id, g);
    });
    wheelSvg.appendChild(wheelGroup);

    const hub = document.createElementNS(SVG_NS, "circle");
    hub.setAttribute("r", HUB_RADIUS);
    hub.classList.add("raffle-hub");
    wheelSvg.appendChild(hub);
    const count = document.createElementNS(SVG_NS, "text");
    count.classList.add("raffle-hub-count");
    count.setAttribute("text-anchor", "middle");
    count.setAttribute("dominant-baseline", "central");
    count.textContent = alive.length;
    wheelSvg.appendChild(count);
  }

  // Índice del gajo bajo la flecha (a las 3 en punto = ángulo 0).
  function indexAtPointer() {
    const a = ((-rotation % 360) + 360) % 360;
    return Math.floor(a / step()) % alive.length;
  }

  function setRotation(deg) {
    rotation = deg;
    wheelGroup.setAttribute("transform", `rotate(${rotation})`);
  }

  // Aceleración inicial + deceleración larga, derivada nula en ambos extremos.
  function ease(t) {
    return 1 - Math.pow(1 - Math.pow(t, 1.4), 3);
  }

  function spinTo(victimId, durationMs, turns) {
    return new Promise((resolve) => {
      const idx = alive.findIndex((p) => p.id === victimId);
      const mid = (idx + 0.5) * step();
      // Jitter dentro del gajo para no clavar siempre el centro.
      const jitter = (Math.random() - 0.5) * step() * 0.7;
      const target = -(mid + jitter);
      const current = ((rotation % 360) + 360) % 360;
      const targetNorm = ((target % 360) + 360) % 360;
      const delta = (targetNorm - current + 360) % 360;
      const total = turns * 360 + delta;
      const start = rotation;
      const t0 = performance.now();
      let lastTickIdx = null;

      function frame(now) {
        // El timestamp del primer rAF puede ser anterior a t0: clamp a [0, 1]
        // o ease() devuelve NaN y la animación muere a mitad de guion.
        const t = Math.min(1, Math.max(0, (now - t0) / durationMs));
        setRotation(start + total * ease(t));
        const under = indexAtPointer();
        if (under !== lastTickIdx && alive[under]) {
          lastTickIdx = under;
          tick();
          nameEl.textContent = alive[under].name;
        }
        if (t < 1) {
          requestAnimationFrame(frame);
        } else {
          resolve();
        }
      }
      requestAnimationFrame(frame);
    });
  }

  function removeSegment(victimId) {
    return new Promise((resolve) => {
      const g = segmentEls.get(victimId);
      if (!g) return resolve();
      g.classList.add("is-eliminated");
      setTimeout(resolve, 600);
    });
  }

  function renderPanels() {
    aliveEl.textContent = alive.length;
    outEl.textContent = eliminated.length;
    elimsEl.textContent = "";
    const all = eliminated.slice().reverse();
    if (all.length) elimsEl.setAttribute("start", eliminated.length);
    for (const p of all) {
      const li = document.createElement("li");
      li.textContent = p.name;
      elimsEl.appendChild(li);
    }
  }

  function popName(label, name) {
    labelEl.textContent = label;
    nameEl.textContent = name;
    nameEl.classList.remove("is-pop");
    void nameEl.offsetWidth; // reinicia la animación
    nameEl.classList.add("is-pop");
  }

  function showWinner(p) {
    finished = true;
    if (startBtn) startBtn.hidden = true;
    if (sawLiveAction) {
      winnerNameEl.textContent = p.name;
      overlay.hidden = false;
      confettiBlast();
    }
    popName("🏆 Ganador", p.name);
  }

  function confettiBlast() {
    if (!window.confetti) return;
    window.confetti({
      particleCount: 160,
      spread: 90,
      origin: { y: 0.45 },
      startVelocity: 45,
      scalar: 1.15,
    });
    const end = Date.now() + 3500;
    (function frame() {
      window.confetti({
        particleCount: 6,
        angle: 270,
        spread: 70,
        startVelocity: 35,
        origin: { x: Math.random(), y: 0 },
        gravity: 1.1,
        scalar: 0.9,
      });
      if (Date.now() < end) requestAnimationFrame(frame);
    })();
  }

  // --- Estado y roster ---
  function setRoster(list) {
    participants = list.map((p) => ({ id: p.id, name: p.name, eliminatedOrder: null }));
    byId = new Map(participants.map((p) => [p.id, p]));
    finalOrder = participants.length - 1;
    eliminated = [];
    alive = participants.slice().sort((a, b) => a.name.localeCompare(b.name, "es"));
    rotation = 0;
  }

  // Recompone la ruleta sin el gajo pendiente de retirar (si lo hay).
  // La flecha manda: reseteamos la rotación acumulada sin salto visual.
  function flushDoomed() {
    doomedId = null;
    rotation = rotation % 360;
    buildWheel();
  }

  function eliminateData(victim) {
    alive = alive.filter((p) => p.id !== victim.id);
    victim.eliminatedOrder = eliminated.length + 1;
    eliminated.push(victim);
    renderPanels();
    processed += 1;
  }

  // Caída aplicada en seco, sin animación (fast-forward o llegamos tarde).
  function applyElimination(victim) {
    eliminateData(victim);
    flushDoomed();
  }

  async function afterStep() {
    if (processed === finalOrder) {
      if (doomedId !== null) {
        await removeSegment(doomedId);
        flushDoomed();
      }
      showWinner(alive[0]);
    } else {
      scheduleNext();
    }
    updateCountdown();
  }

  // Reproduce la siguiente caída del guion: si su timestamp aún queda lejos
  // espera, si hay margen anima el giro para caer clavado en él y si esta
  // pantalla llega tarde (recarga, incorporación a mitad) la aplica en seco.
  function scheduleNext() {
    if (!started || finished || spinning || waitTimer) return;
    const next = knownEvents.get(processed + 1);
    if (!next) return; // aún no revelado: el próximo poll volverá a llamar
    const lead = next.atMs - serverNow();
    if (lead <= MIN_SPIN_MS) {
      applyElimination(byId.get(next.id));
      afterStep();
      return;
    }
    const base = alive.length <= DRAMATIC_FROM ? DRAMATIC_SPIN_MS : NORMAL_SPIN_MS;
    const startIn = Math.max(0, lead - base);
    waitTimer = setTimeout(() => {
      waitTimer = null;
      runSpin(next);
    }, startIn);
  }

  async function runSpin(evt) {
    if (finished || spinning) return;
    spinning = true;
    sawLiveAction = true;
    updateCountdown();
    // El eliminado anterior sale de la ruleta ahora, al empezar esta tirada.
    if (doomedId !== null) {
      await removeSegment(doomedId);
      flushDoomed();
    }
    const duration = Math.max(MIN_SPIN_MS, evt.atMs - serverNow());
    const range = alive.length <= DRAMATIC_FROM ? DRAMATIC_TURNS : NORMAL_TURNS;
    const turns = range[Math.floor(Math.random() * range.length)];
    await spinTo(evt.id, duration, turns);
    const victim = byId.get(evt.id);
    popName("Eliminado", victim.name);
    // El gajo se queda (atenuado) hasta la siguiente tirada.
    const seg = segmentEls.get(evt.id);
    if (seg) seg.classList.add("is-doomed");
    doomedId = evt.id;
    eliminateData(victim);
    spinning = false;
    afterStep();
  }

  function mergeState(data) {
    clockOffset = data.serverNowMs - Date.now();
    if (data.startedAtMs === null) {
      if (started) {
        // El gestor reinició a mitad: recarga limpia hacia la pantalla de espera.
        window.location.reload();
        return;
      }
      // Pre-inicio: los elegibles pueden cambiar (altas, pagos).
      const ids = (list) => list.map((p) => p.id).join(",");
      if (ids(data.participants) !== ids(participants)) {
        setRoster(data.participants);
        buildWheel();
        renderPanels();
      }
      return;
    }
    if (!started) {
      started = true;
      startedAtMs = data.startedAtMs;
      cadenceMs = data.cadenceMs;
      if (startBtn) startBtn.hidden = true;
      setRoster(data.participants); // snapshot congelado al iniciar
      buildWheel();
      renderPanels();
      popName("Sorteo en marcha", "…");
    }
    for (const p of data.participants) {
      if (p.eliminatedOrder !== null && !knownEvents.has(p.eliminatedOrder)) {
        knownEvents.set(p.eliminatedOrder, { id: p.id, atMs: p.eliminatedAtMs });
      }
    }
    scheduleNext();
  }

  // Contador hasta que arranque el giro de la siguiente tirada.
  function updateCountdown() {
    if (!nextEl) return;
    const usable = started && !finished && !spinning && cadenceMs && processed < finalOrder;
    if (!usable) {
      nextEl.hidden = true;
      return;
    }
    const nextAt = startedAtMs + (processed + 1) * cadenceMs;
    const base = alive.length <= DRAMATIC_FROM ? DRAMATIC_SPIN_MS : NORMAL_SPIN_MS;
    const secs = Math.ceil((nextAt - base - serverNow()) / 1000);
    if (secs <= 0) {
      nextEl.hidden = true;
      return;
    }
    nextEl.hidden = false;
    nextEl.textContent = `Siguiente tirada en ${secs} s`;
  }

  async function poll() {
    try {
      const res = await fetch(state.stateUrl, { credentials: "same-origin" });
      if (res.ok) mergeState(await res.json());
    } catch (err) {
      console.error(err);
    }
    if (!finished) setTimeout(poll, POLL_MS);
  }

  async function handleStart() {
    if (!window.confirm("¿Iniciar el sorteo? A partir de aquí la ruleta corre sola.")) {
      return;
    }
    startBtn.disabled = true;
    setSound(true);
    try {
      const res = await fetch(state.startUrl, {
        method: "POST",
        headers: { "X-CSRFToken": getCsrf() },
        credentials: "same-origin",
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      mergeState(await res.json());
    } catch (err) {
      popName("Error", "No se pudo iniciar, reintenta");
      startBtn.disabled = false;
      console.error(err);
    }
  }

  // --- Arranque ---
  setRoster(state.participants);
  buildWheel();
  renderPanels();
  if (state.startedAtMs === null) {
    popName("Sorteo de camiseta", "El sorteo empezará en breve");
  }
  mergeState(state); // fast-forward de lo ya caído e inicio del guion
  if (!finished) setTimeout(poll, POLL_MS);
  setInterval(updateCountdown, 250);

  if (startBtn) startBtn.addEventListener("click", handleStart);
  if (soundBtn) soundBtn.addEventListener("click", () => setSound(!soundOn));
  if (resetForm) {
    resetForm.addEventListener("submit", (e) => {
      if (!window.confirm("¿Seguro? Se borra todo el progreso del sorteo.")) {
        e.preventDefault();
      }
    });
  }
  if (overlay) {
    overlay.addEventListener("click", () => {
      overlay.hidden = true;
    });
  }
}
