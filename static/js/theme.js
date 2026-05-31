const root = document.documentElement;
const KEY = "porra26:theme";

function apply(theme) {
  root.setAttribute("data-theme", theme);
}

function init() {
  const saved = localStorage.getItem(KEY);
  if (saved) apply(saved);
  document.querySelectorAll("[data-theme-toggle]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = root.getAttribute("data-theme") === "dark" ? "light" : "dark";
      apply(next);
      localStorage.setItem(KEY, next);
    });
  });
}

init();
