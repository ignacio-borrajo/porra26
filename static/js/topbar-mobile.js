// Mejoras para la nav del topbar en móvil:
//  - Actualiza las variables CSS --fade-left / --fade-right para que la
//    máscara solo recorte el borde donde realmente hay más contenido al
//    que scrollear (truco habitual para hint de scroll horizontal).
//  - En el primer render desplaza el ítem activo hasta que se vea, así
//    el usuario que entra a "Premios y puntos" o "Reglas" no llega a una
//    barra con el item activo recortado fuera de pantalla.

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

  // Centrar el ítem activo si existe y se sale del viewport horizontal.
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
