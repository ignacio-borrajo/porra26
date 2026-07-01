const canvas = document.querySelector(".ko-columns");
if (canvas) init(canvas);

function init(canvas) {
  setupChipNavigation(canvas);
  if (isCanvasVisible(canvas)) {
    scrollToActiveColumn(canvas);
    setupDragToPan(canvas);
  }
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
