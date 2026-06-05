// Mejoras para la nav del topbar en móvil:
//  - Actualiza las variables CSS --fade-left / --fade-right para que la
//    máscara solo recorte el borde donde realmente hay más contenido al
//    que scrollear (truco habitual para hint de scroll horizontal). Solo
//    relevante si .topbar-nav está visible (tablet/escritorio).
//  - Centra el ítem activo en el primer render si se sale del viewport.
//  - Gestor: abre y cierra el drawer móvil cuando se pulsa la hamburguesa.

const nav = document.querySelector(".topbar-nav");
if (nav) {
  const update = () => {
    const max = nav.scrollWidth - nav.clientWidth;
    if (max <= 1) {
      nav.style.setProperty("--fade-left", "0");
      nav.style.setProperty("--fade-right", "0");
      return;
    }
    const left = Math.min(1, nav.scrollLeft / 24);
    const right = Math.min(1, (max - nav.scrollLeft) / 24);
    nav.style.setProperty("--fade-left", left.toFixed(3));
    nav.style.setProperty("--fade-right", right.toFixed(3));
  };

  update();
  nav.addEventListener("scroll", update, { passive: true });
  window.addEventListener("resize", update);

  const active = nav.querySelector(".nav-item.is-active");
  if (active) {
    const navRect = nav.getBoundingClientRect();
    const itemRect = active.getBoundingClientRect();
    if (itemRect.left < navRect.left || itemRect.right > navRect.right) {
      const offset =
        active.offsetLeft -
        nav.clientWidth / 2 +
        active.clientWidth / 2;
      nav.scrollTo({ left: Math.max(0, offset), behavior: "auto" });
      update();
    }
  }
}

// Drawer móvil del gestor.
const toggle = document.querySelector("[data-mobile-menu-toggle]");
const drawer = document.querySelector("[data-mobile-drawer]");
const backdrop = document.querySelector("[data-mobile-drawer-backdrop]");

if (toggle && drawer && backdrop) {
  const iconOpen = toggle.querySelector("[data-menu-icon-open]");
  const iconClose = toggle.querySelector("[data-menu-icon-close]");

  const setOpen = (open) => {
    if (open) {
      drawer.removeAttribute("hidden");
      backdrop.removeAttribute("hidden");
      // Forzar reflow para que la transición de opacity se aprecie.
      drawer.getBoundingClientRect();
      drawer.setAttribute("data-open", "");
      backdrop.setAttribute("data-open", "");
      toggle.setAttribute("aria-expanded", "true");
      toggle.setAttribute("aria-label", "Cerrar menú");
      if (iconOpen) iconOpen.style.display = "none";
      if (iconClose) iconClose.style.display = "";
      document.body.style.overflow = "hidden";
      const firstLink = drawer.querySelector("a, button");
      if (firstLink) firstLink.focus({ preventScroll: true });
    } else {
      drawer.removeAttribute("data-open");
      backdrop.removeAttribute("data-open");
      toggle.setAttribute("aria-expanded", "false");
      toggle.setAttribute("aria-label", "Abrir menú");
      if (iconOpen) iconOpen.style.display = "";
      if (iconClose) iconClose.style.display = "none";
      document.body.style.overflow = "";
      // Esperar al final de la transición para volver a [hidden] y que
      // el contenido no quede en el árbol de accesibilidad.
      setTimeout(() => {
        if (!drawer.hasAttribute("data-open")) {
          drawer.setAttribute("hidden", "");
          backdrop.setAttribute("hidden", "");
        }
      }, 260);
      toggle.focus({ preventScroll: true });
    }
  };

  toggle.addEventListener("click", () => {
    const isOpen = toggle.getAttribute("aria-expanded") === "true";
    setOpen(!isOpen);
  });

  backdrop.addEventListener("click", () => setOpen(false));

  drawer.addEventListener("click", (event) => {
    const link = event.target.closest("a");
    if (link) setOpen(false);
  });

  document.addEventListener("keydown", (event) => {
    if (event.key === "Escape" && toggle.getAttribute("aria-expanded") === "true") {
      setOpen(false);
    }
  });

  // Si el viewport vuelve a desktop, cerrar el drawer por si quedó abierto.
  const mql = window.matchMedia("(min-width: 861px)");
  mql.addEventListener("change", (e) => {
    if (e.matches && toggle.getAttribute("aria-expanded") === "true") {
      setOpen(false);
    }
  });
}
