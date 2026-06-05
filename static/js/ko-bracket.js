const canvas = document.querySelector(".ko-canvas");
if (canvas) init(canvas);

function init(canvas) {
  setupChipNavigation(canvas);
  if (isCanvasVisible(canvas)) {
    scrollToActiveColumn(canvas);
    setupDragToPan(canvas);
    setupConnectors(canvas);
  }
  window.addEventListener("resize", debounceRAF(() => {
    if (isCanvasVisible(canvas)) layoutConnectors(canvas);
  }));
}

function isCanvasVisible(canvas) {
  return getComputedStyle(canvas).display !== "none";
}

function scrollToActiveColumn(canvas) {
  const active = canvas.dataset.activeRound;
  if (!active) return;
  const col = canvas.querySelector(`.ko-col[data-round="${active}"]`);
  if (!col) return;
  const padLeft = parseInt(getComputedStyle(canvas).paddingLeft) || 0;
  canvas.classList.add("prevent-scroll-animation");
  canvas.scrollLeft = col.offsetLeft - padLeft;
  requestAnimationFrame(() => canvas.classList.remove("prevent-scroll-animation"));
}

function setupChipNavigation(canvas) {
  const chips = document.querySelectorAll(".round-selector .chip[data-target-round]");
  chips.forEach(chip => {
    chip.addEventListener("click", e => {
      if (!isCanvasVisible(canvas)) return;
      const target = chip.dataset.targetRound;
      if (!target) return;
      const col = canvas.querySelector(`.ko-col[data-round="${target}"]`);
      if (!col) return;
      e.preventDefault();
      col.scrollIntoView({ inline: "start", block: "nearest", behavior: "smooth" });
      history.pushState(null, "", chip.href);
    });
  });
}

function setupDragToPan(canvas) {
  let startX = 0;
  let startY = 0;
  let startScrollLeft = 0;
  let startPageY = 0;
  let active = false;

  function onMove(e) {
    if (!active) return;
    canvas.scrollLeft = startScrollLeft + (startX - e.clientX);
    window.scrollTo(window.scrollX, startPageY + (startY - e.clientY));
  }
  function onEnd() {
    if (!active) return;
    active = false;
    canvas.classList.remove("grabbing");
    document.removeEventListener("pointermove", onMove);
    document.removeEventListener("pointerup", onEnd);
    document.removeEventListener("pointercancel", onEnd);
  }

  canvas.addEventListener("pointerdown", e => {
    if (e.button !== 0) return;
    if (e.target.closest("a, button")) return;
    active = true;
    startX = e.clientX;
    startY = e.clientY;
    startScrollLeft = canvas.scrollLeft;
    startPageY = window.scrollY;
    canvas.classList.add("grabbing");
    document.addEventListener("pointermove", onMove);
    document.addEventListener("pointerup", onEnd);
    document.addEventListener("pointercancel", onEnd);
    e.preventDefault();
  });
}

function setupConnectors(canvas) {
  layoutConnectors(canvas);
  const ro = new ResizeObserver(debounceRAF(() => layoutConnectors(canvas)));
  ro.observe(canvas);
  canvas.querySelectorAll(".ko-col").forEach(col => ro.observe(col));
}

function layoutConnectors(canvas) {
  const svg = canvas.querySelector(".ko-connectors");
  if (!svg) return;
  if (getComputedStyle(svg).display === "none") {
    svg.innerHTML = "";
    return;
  }
  const cards = [...canvas.querySelectorAll(".match-card[data-bracket-code]")].filter(c => c.dataset.bracketCode);
  const byCode = new Map(cards.map(c => [c.dataset.bracketCode, c]));
  const canvasRect = canvas.getBoundingClientRect();
  const offsetX = canvas.scrollLeft;
  const offsetY = canvas.scrollTop;
  const w = canvas.scrollWidth;
  const h = canvas.scrollHeight;
  svg.setAttribute("viewBox", `0 0 ${w} ${h}`);
  svg.setAttribute("width", w);
  svg.setAttribute("height", h);

  const groups = new Map();
  for (const card of cards) {
    const dest = card.dataset.feedsInto;
    if (!dest) continue;
    if (!groups.has(dest)) groups.set(dest, []);
    groups.get(dest).push(card);
  }

  const ns = "http://www.w3.org/2000/svg";
  svg.innerHTML = "";
  for (const [destCode, siblings] of groups) {
    const dest = byCode.get(destCode);
    if (!dest || siblings.length === 0) continue;
    const sortedSibs = siblings
      .map(c => ({ card: c, rect: rel(c, canvasRect, offsetX, offsetY) }))
      .sort((a, b) => a.rect.top - b.rect.top);
    const destRect = rel(dest, canvasRect, offsetX, offsetY);
    const destY = destRect.top + destRect.height / 2;
    const midX = (Math.max(...sortedSibs.map(s => s.rect.right)) + destRect.left) / 2;
    const status = dest.dataset.status || "open";
    const path = document.createElementNS(ns, "path");
    if (sortedSibs.length >= 2) {
      const top = sortedSibs[0].rect;
      const bot = sortedSibs[sortedSibs.length - 1].rect;
      const topY = top.top + top.height / 2;
      const botY = bot.top + bot.height / 2;
      // 4 segmentos sin solape: stub-top, stub-bot, vertical-junta, exit-a-destino.
      path.setAttribute(
        "d",
        `M ${top.right} ${topY} L ${midX} ${topY} ` +
          `M ${bot.right} ${botY} L ${midX} ${botY} ` +
          `M ${midX} ${topY} L ${midX} ${botY} ` +
          `M ${midX} ${destY} L ${destRect.left} ${destY}`,
      );
    } else {
      const s = sortedSibs[0].rect;
      const y = s.top + s.height / 2;
      path.setAttribute(
        "d",
        `M ${s.right} ${y} L ${midX} ${y} L ${midX} ${destY} L ${destRect.left} ${destY}`,
      );
    }
    path.setAttribute("data-status", status);
    svg.appendChild(path);
  }
}

function rel(el, canvasRect, offsetX, offsetY) {
  const r = el.getBoundingClientRect();
  return {
    left: r.left - canvasRect.left + offsetX,
    right: r.right - canvasRect.left + offsetX,
    top: r.top - canvasRect.top + offsetY,
    bottom: r.bottom - canvasRect.top + offsetY,
    width: r.width,
    height: r.height,
  };
}

function debounceRAF(fn) {
  let raf;
  return (...args) => {
    if (raf) cancelAnimationFrame(raf);
    raf = requestAnimationFrame(() => fn(...args));
  };
}
