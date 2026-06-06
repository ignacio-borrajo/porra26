const KEY = "porra26:matchesOrder";
const MODES = new Set(["date", "group"]);

function readMode() {
  try {
    const v = localStorage.getItem(KEY);
    return MODES.has(v) ? v : "date";
  } catch {
    return "date";
  }
}

function writeMode(mode) {
  try {
    localStorage.setItem(KEY, mode);
  } catch {
    /* private mode, ignore */
  }
}

function sortKey(card, mode) {
  const group = (card.dataset.group || "").toLowerCase();
  const kickoff = card.dataset.kickoff || "";
  return mode === "group" ? `${group}|${kickoff}` : kickoff;
}

function applyOrder(mode) {
  document.querySelectorAll(".matches-grid").forEach((grid) => {
    const cards = Array.from(grid.children);
    cards.sort((a, b) => sortKey(a, mode).localeCompare(sortKey(b, mode)));
    cards.forEach((c) => grid.appendChild(c));
  });
}

function syncButtons(mode) {
  document.querySelectorAll(".matches-order-toggle [data-order]").forEach((btn) => {
    const active = btn.dataset.order === mode;
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.classList.toggle("chip-open", active);
  });
}

function init() {
  const toggle = document.querySelector(".matches-order-toggle");
  if (!toggle) return;
  const mode = readMode();
  syncButtons(mode);
  if (mode === "group") applyOrder(mode);
  toggle.querySelectorAll("[data-order]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.order;
      if (!MODES.has(next)) return;
      writeMode(next);
      syncButtons(next);
      applyOrder(next);
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
