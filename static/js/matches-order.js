const KEY = "porra26:matchesOrder";
const MODES = new Set(["date", "group"]);
const DAY_FMT = new Intl.DateTimeFormat("es-ES", {
  weekday: "long",
  day: "numeric",
  month: "long",
});

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

function dayKey(iso) {
  return (iso || "").slice(0, 10);
}

function subgroupKey(card, mode) {
  if (mode === "group") {
    const g = card.dataset.group || "";
    return g.length === 1 ? `1${g}` : `2${g}`;
  }
  return dayKey(card.dataset.kickoff);
}

function subgroupLabel(card, mode) {
  if (mode === "group") {
    const g = card.dataset.group || "?";
    return g.length === 1 ? `Grupo ${g}` : g;
  }
  const k = card.dataset.kickoff;
  if (!k) return "";
  const d = new Date(k);
  if (Number.isNaN(d.getTime())) return "";
  const label = DAY_FMT.format(d);
  return label.charAt(0).toUpperCase() + label.slice(1);
}

function rebuild(grid, mode) {
  const cards = Array.from(grid.querySelectorAll(".match-card"));
  if (!cards.length) return;
  cards.sort((a, b) => {
    const ka = subgroupKey(a, mode);
    const kb = subgroupKey(b, mode);
    if (ka !== kb) return ka.localeCompare(kb);
    return (a.dataset.kickoff || "").localeCompare(b.dataset.kickoff || "");
  });
  grid.innerHTML = "";
  let lastKey = null;
  for (const c of cards) {
    const k = subgroupKey(c, mode);
    if (k !== lastKey) {
      const h = document.createElement("h3");
      h.className = "eyebrow matches-subgroup-header";
      h.style.cssText =
        "grid-column:1/-1;margin:10px 0 -2px;font-size:11px;opacity:.7";
      h.textContent = subgroupLabel(c, mode);
      grid.appendChild(h);
      lastKey = k;
    }
    grid.appendChild(c);
  }
}

function syncButtons(mode) {
  document.querySelectorAll(".matches-order-toggle [data-order]").forEach((btn) => {
    const active = btn.dataset.order === mode;
    btn.setAttribute("aria-pressed", active ? "true" : "false");
    btn.classList.toggle("chip-open", active);
  });
}

function applyMode(mode) {
  syncButtons(mode);
  document.querySelectorAll(".matches-grid").forEach((g) => rebuild(g, mode));
}

function init() {
  const grids = document.querySelectorAll(".matches-grid");
  if (!grids.length) return;
  applyMode(readMode());
  document.querySelectorAll(".matches-order-toggle [data-order]").forEach((btn) => {
    btn.addEventListener("click", () => {
      const next = btn.dataset.order;
      if (!MODES.has(next)) return;
      writeMode(next);
      applyMode(next);
    });
  });
}

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", init);
} else {
  init();
}
