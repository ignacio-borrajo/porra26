(function () {
  const SEL = ".podium-tied";

  function closeAll(except) {
    document.querySelectorAll(`${SEL}[data-open="true"]`).forEach((el) => {
      if (el !== except) {
        el.removeAttribute("data-open");
        el.setAttribute("aria-expanded", "false");
      }
    });
  }

  document.addEventListener("click", (e) => {
    const btn = e.target.closest(SEL);
    if (btn) {
      // Click sobre items dentro del tooltip ya abierto: no togglear.
      if (e.target.closest(".podium-tied__tooltip")) return;
      const open = btn.getAttribute("data-open") === "true";
      closeAll(open ? null : btn);
      if (open) {
        btn.removeAttribute("data-open");
        btn.setAttribute("aria-expanded", "false");
      } else {
        btn.setAttribute("data-open", "true");
        btn.setAttribute("aria-expanded", "true");
      }
      return;
    }
    closeAll(null);
  });

  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape") closeAll(null);
  });
})();
