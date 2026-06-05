const canvas = document.querySelector(".ko-canvas");
if (canvas) init(canvas);

function init(canvas) {
  scrollToActiveColumn(canvas);
  setupChipNavigation(canvas);
  if (matchMedia("(pointer:fine)").matches) setupDragToPan(canvas);
  setupConnectors(canvas);
  setupMobileDots(canvas);
  window.addEventListener("resize", debounceRAF(() => layoutConnectors(canvas)));
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
  let startScrollLeft = 0;
  let dragging = false;

  canvas.addEventListener("pointerdown", e => {
    if (e.target.closest(".match-card")) return;
    dragging = true;
    startX = e.clientX;
    startScrollLeft = canvas.scrollLeft;
    canvas.setPointerCapture(e.pointerId);
    canvas.classList.add("grabbing");
  });
  canvas.addEventListener("pointermove", e => {
    if (!dragging) return;
    canvas.scrollLeft = startScrollLeft + (startX - e.clientX);
  });
  const end = () => {
    dragging = false;
    canvas.classList.remove("grabbing");
  };
  canvas.addEventListener("pointerup", end);
  canvas.addEventListener("pointercancel", end);
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
    const sorted = siblings
      .map(c => ({ card: c, rect: rel(c, canvasRect, offsetX, offsetY) }))
      .sort((a, b) => a.rect.top - b.rect.top);
    const destRect = rel(dest, canvasRect, offsetX, offsetY);
    const destY = destRect.top + destRect.height / 2;
    const midX = (Math.max(...sorted.map(s => s.rect.right)) + destRect.left) / 2;
    const status = dest.dataset.status || "open";
    for (const s of sorted) {
      const y = s.rect.top + s.rect.height / 2;
      const path = document.createElementNS(ns, "path");
      path.setAttribute("d", `M ${s.rect.right} ${y} H ${midX} V ${destY} H ${destRect.left}`);
      path.setAttribute("data-status", status);
      svg.appendChild(path);
    }
  }
}

function setupMobileDots(canvas) {
  const dots = document.querySelector(".ko-dots");
  if (!dots) return;
  const cols = canvas.querySelectorAll(".ko-col[data-round]");
  const io = new IntersectionObserver(entries => {
    for (const en of entries) {
      if (en.isIntersecting && en.intersectionRatio >= 0.5) {
        const code = en.target.dataset.round;
        dots.querySelectorAll("span").forEach(s =>
          s.classList.toggle("active", s.dataset.round === code)
        );
      }
    }
  }, { root: canvas, threshold: [0.5] });
  cols.forEach(c => io.observe(c));
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
