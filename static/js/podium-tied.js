(function () {
  const BTN_SEL = ".podium-tied";
  const TIP_SEL = ".podium-tied__tooltip";
  const MAX_TIP_H = 320;

  function init() {
    // Sacamos cada tooltip del interior del botón y lo adjuntamos al body
    // para que .pop (animation con transform residual) no convierta al
    // .podium-slot en containing block del position:fixed, que rompía las
    // coordenadas calculadas desde getBoundingClientRect.
    const pairs = [];
    document.querySelectorAll(BTN_SEL).forEach((btn) => {
      const tip = btn.querySelector(TIP_SEL);
      if (!tip) return;
      tip.parentNode.removeChild(tip);
      document.body.appendChild(tip);
      pairs.push({ btn, tip });
    });
    if (!pairs.length) return;

    function position(btn, tip) {
      const r = btn.getBoundingClientRect();
      const cx = r.left + r.width / 2;
      const spaceBelow = window.innerHeight - r.bottom;
      const placeAbove = spaceBelow < MAX_TIP_H + 16 && r.top > spaceBelow;
      tip.dataset.placement = placeAbove ? "top" : "bottom";
      tip.style.left = `${Math.round(cx)}px`;
      tip.style.top = `${Math.round(placeAbove ? r.top - 8 : r.bottom + 8)}px`;
    }

    function show(btn, tip, mode) {
      position(btn, tip);
      tip.dataset.show = mode; // "hover" | "open"
      btn.setAttribute("aria-expanded", "true");
    }

    function hide(btn, tip) {
      delete tip.dataset.show;
      btn.setAttribute("aria-expanded", "false");
    }

    function hideAll(except) {
      pairs.forEach(({ btn, tip }) => {
        if (tip !== except) hide(btn, tip);
      });
    }

    pairs.forEach(({ btn, tip }) => {
      btn.addEventListener("pointerenter", () => {
        if (tip.dataset.show !== "open") show(btn, tip, "hover");
      });
      btn.addEventListener("pointerleave", () => {
        if (tip.dataset.show === "hover") {
          // Pequeño retraso para que el usuario pueda mover el cursor del
          // botón a la propia tooltip sin que se cierre.
          setTimeout(() => {
            if (tip.dataset.show === "hover" && !tip.matches(":hover")) {
              hide(btn, tip);
            }
          }, 80);
        }
      });
      tip.addEventListener("pointerleave", () => {
        if (tip.dataset.show === "hover") hide(btn, tip);
      });
      btn.addEventListener("focus", () => {
        if (tip.dataset.show !== "open") show(btn, tip, "hover");
      });
      btn.addEventListener("blur", () => {
        if (tip.dataset.show === "hover") hide(btn, tip);
      });
      btn.addEventListener("click", (e) => {
        e.stopPropagation();
        if (tip.dataset.show === "open") {
          hide(btn, tip);
        } else {
          hideAll(tip);
          show(btn, tip, "open");
        }
      });
    });

    document.addEventListener("click", (e) => {
      if (!e.target.closest(BTN_SEL) && !e.target.closest(TIP_SEL)) hideAll(null);
    });
    document.addEventListener("keydown", (e) => {
      if (e.key === "Escape") hideAll(null);
    });

    function syncAll() {
      pairs.forEach(({ btn, tip }) => {
        if (tip.dataset.show) position(btn, tip);
      });
    }
    window.addEventListener("scroll", syncAll, true);
    window.addEventListener("resize", syncAll);
  }

  if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", init);
  } else {
    init();
  }
})();
