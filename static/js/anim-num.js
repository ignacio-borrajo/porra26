function easeOutCubic(t) { return 1 - Math.pow(1 - t, 3); }

function animate(el) {
  const target = Number(el.dataset.animNum || "0");
  const start = performance.now();
  const dur = 900;
  function tick(now) {
    const t = Math.min(1, (now - start) / dur);
    el.textContent = Math.round(target * easeOutCubic(t));
    if (t < 1) requestAnimationFrame(tick);
  }
  requestAnimationFrame(tick);
}

document.querySelectorAll("[data-anim-num]").forEach(animate);
