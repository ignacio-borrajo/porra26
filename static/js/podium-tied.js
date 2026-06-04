(function () {
  const SEL = ".podium-tied";
  const TIP_SEL = ".podium-tied__tooltip";
  const MAX_TIP_H = 320;
  let activeBtn = null;

  function tooltipOf(btn) {
    return btn.querySelector(TIP_SEL);
  }

  function position(btn) {
    const tip = tooltipOf(btn);
    if (!tip) return;
    const r = btn.getBoundingClientRect();
    const cx = r.left + r.width / 2;
    const spaceBelow = window.innerHeight - r.bottom;
    const placeAbove = spaceBelow < MAX_TIP_H + 16 && r.top > spaceBelow;
    tip.dataset.placement = placeAbove ? "top" : "bottom";
    tip.style.left = `${Math.round(cx)}px`;
    tip.style.top = `${Math.round(placeAbove ? r.top - 8 : r.bottom + 8)}px`;
  }

  function closeAll(except) {
    document.querySelectorAll(`${SEL}[data-open="true"]`).forEach((el) => {
      if (el !== except) {
        el.removeAttribute("data-open");
        el.setAttribute("aria-expanded", "false");
      }
    });
  }

  function syncActive() {
    if (activeBtn) position(activeBtn);
  }

  document.addEventListener(
    "pointerenter",
    (e) => {
      const btn = e.target instanceof Element ? e.target.closest(SEL) : null;
      if (!btn) return;
      activeBtn = btn;
      position(btn);
    },
    true,
  );

  document.addEventListener(
    "focusin",
    (e) => {
      const btn = e.target instanceof Element ? e.target.closest(SEL) : null;
      if (!btn) return;
      activeBtn = btn;
      position(btn);
    },
    true,
  );

  document.addEventListener(
    "pointerleave",
    (e) => {
      const btn = e.target instanceof Element ? e.target.closest(SEL) : null;
      if (!btn) return;
      if (btn.getAttribute("data-open") !== "true") activeBtn = null;
    },
    true,
  );

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(SEL);
    if (btn) {
      if (e.target.closest(TIP_SEL)) return;
      const open = btn.getAttribute("data-open") === "true";
      closeAll(open ? null : btn);
      if (open) {
        btn.removeAttribute("data-open");
        btn.setAttribute("aria-expanded", "false");
        activeBtn = null;
      } else {
        btn.setAttribute("data-open", "true");
        btn.setAttribute("aria-expanded", "true");
        activeBtn = btn;
        position(btn);
      }
      return;
    }
    if (!e.target.closest(TIP_SEL)) {
      closeAll(null);
      activeBtn = null;
    }
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") {
      closeAll(null);
      activeBtn = null;
    }
  });

  window.addEventListener("scroll", syncActive, true);
  window.addEventListener("resize", syncActive);
})();
