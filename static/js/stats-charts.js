/* Gráficas de la pantalla de Estadísticas (Chart.js).
   - Evolución: líneas de puntos/posición por jugador, con tooltip (nombre +
     valor), etiquetas de identidad al final de cada línea, toggle de modo,
     "mostrar todos" y selector de jugadores.
   - Donut: distribución de pronósticos del jugador (exactos / parciales /
     fallos) con % de aciertos al centro. */

const PALETTE = [
  "--c-pink", "--c-cyan", "--c-lime", "--c-yellow",
  "--c-gold", "--c-blue", "--c-green", "--c-red",
];

// El soporte de oklch() en <canvas> llegó después que en CSS; resolvemos cada
// color a rgb con una sonda (el motor CSS hace la conversión) para que Chart.js
// pinte siempre, también en navegadores algo antiguos.
let _probe;
function resolveColor(value) {
  const v = (value || "").trim();
  if (!v) return v;
  if (!_probe) {
    _probe = document.createElement("span");
    _probe.style.display = "none";
    document.body.appendChild(_probe);
  }
  _probe.style.color = "";
  _probe.style.color = v;
  return getComputedStyle(_probe).color || v;
}

const cssVar = (name) =>
  resolveColor(getComputedStyle(document.documentElement).getPropertyValue(name));

function firstName(name) {
  return (name || "").split(" ")[0] || name || "";
}

/* ====================== Evolución ====================== */
function setupEvolution(root, payload) {
  const canvas = root.querySelector("[data-evo-canvas]");
  const plotEl = root.querySelector("[data-evo-plot]");
  const labelsBox = root.querySelector("[data-evo-labels]");
  const legendBox = root.querySelector("[data-evo-legend]");
  const emptyEl = root.querySelector("[data-evo-empty]");
  const headingEl = root.querySelector("[data-evo-heading]");
  const subEl = root.querySelector("[data-evo-sub]");
  const modesEl = root.querySelector("[data-evo-modes]");
  const showAllBtn = root.querySelector("[data-evo-showall]");

  const { players, me, finished } = payload;
  if (!finished || !players.length) {
    canvas.hidden = true;
    if (emptyEl) emptyEl.hidden = false;
    if (showAllBtn) showAllBtn.disabled = true;
    return;
  }

  // pool por defecto: top 10 + tú (si no estás en el top 10)
  const top10 = players.slice(0, 10);
  const meP = players.find((p) => p.id === me);
  const meInTop = top10.some((p) => p.id === me);
  const basePool = meInTop || !meP ? top10 : [...top10, meP];

  let mode = "pts"; // 'pts' | 'rank'
  let showAll = false;
  const visible = new Set(basePool.map((p) => p.id));

  const colorOf = (p, i) => (p.id === me ? cssVar("--accent") : cssVar(PALETTE[i % PALETTE.length]));
  const labels = Array.from({ length: finished }, (_, i) => String(i + 1));
  // En pantallas estrechas no caben las etiquetas de identidad: se omiten y se
  // libera el hueco derecho (se identifica por leyenda y tooltip).
  const isNarrow = () => plotEl.clientWidth < 560;

  const chart = new Chart(canvas.getContext("2d"), {
    type: "line",
    data: { labels, datasets: [] },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: { duration: 300 },
      interaction: { mode: "index", intersect: false },
      layout: { padding: { right: 188, top: 6 } },
      scales: {
        x: {
          title: { display: true, text: "Partidos", color: cssVar("--text-faint"), font: { size: 11 } },
          grid: { color: cssVar("--border") },
          ticks: { color: cssVar("--text-faint"), font: { size: 10 } },
        },
        y: {
          title: { display: true, text: "Puntos", color: cssVar("--text-faint"), font: { size: 11 } },
          grid: { color: cssVar("--border") },
          ticks: { color: cssVar("--text-faint"), font: { size: 10 }, precision: 0 },
        },
      },
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: cssVar("--surface-solid"),
          titleColor: cssVar("--text"),
          bodyColor: cssVar("--text"),
          borderColor: cssVar("--border-hi"),
          borderWidth: 1,
          padding: 10,
          itemSort: (a, b) => (mode === "rank" ? a.parsed.y - b.parsed.y : b.parsed.y - a.parsed.y),
          callbacks: {
            title: (items) => (items.length ? `Partido ${items[0].label}` : ""),
            label: (item) =>
              `${item.dataset.label}: ${mode === "rank" ? "#" + item.parsed.y : item.parsed.y + " pts"}`,
          },
        },
      },
    },
  });

  function activePool() {
    return showAll ? players : basePool;
  }

  function rebuild() {
    const pool = activePool();
    chart.data.datasets = pool.map((p, i) => {
      const c = colorOf(p, i);
      const isMe = p.id === me;
      return {
        label: isMe ? "Tú" : firstName(p.name),
        data: mode === "rank" ? p.rank_hist : p.pts_hist,
        borderColor: c,
        backgroundColor: c,
        borderWidth: isMe ? 3 : 2,
        tension: 0.25,
        pointRadius: 0,
        pointHoverRadius: isMe ? 5 : 4,
        pointHoverBackgroundColor: cssVar("--surface-solid"),
        pointHoverBorderColor: c,
        pointHoverBorderWidth: 2.5,
        order: isMe ? -1 : i,
        hidden: !showAll && !visible.has(p.id),
        _player: p,
        _color: c,
      };
    });

    const showLabels = !showAll && !isNarrow();
    chart.options.layout.padding.right = showLabels ? 188 : 12;

    const reversed = mode === "rank";
    chart.options.scales.y.reverse = reversed;
    chart.options.scales.y.title.text = reversed ? "Posición" : "Puntos";
    chart.options.scales.y.min = reversed ? 1 : 0;
    chart.options.scales.y.max = undefined;
    chart.options.scales.y.ticks.callback = reversed ? (v) => "#" + v : (v) => v;

    headingEl.textContent = reversed ? "Evolución de la posición" : "Evolución de puntos";
    updateSubtitle();
    chart.update();
    requestAnimationFrame(() => positionLabels());
    renderLegend();
  }

  function updateSubtitle() {
    if (!subEl || !meP) {
      if (subEl) subEl.textContent = "";
      return;
    }
    const hist = meP.rank_hist;
    if (!hist || hist.length < 1) {
      subEl.textContent = "";
      return;
    }
    const climbed = hist[0] - hist[hist.length - 1];
    if (climbed > 0) {
      subEl.innerHTML = `Has escalado <strong style="color:var(--c-lime)">${climbed} posiciones</strong> desde el primer partido.`;
    } else if (climbed < 0) {
      subEl.innerHTML = `Has cedido <strong style="color:var(--c-red)">${-climbed} posiciones</strong> desde el primer partido.`;
    } else {
      subEl.textContent = "Mantienes tu posición desde el primer partido.";
    }
  }

  // Etiquetas de identidad al final de cada línea (solo en vista acotada:
  // con todos los jugadores no caben sin solaparse y se usa el tooltip).
  function positionLabels() {
    labelsBox.innerHTML = "";
    if (showAll || isNarrow()) return;
    const { scales } = chart;
    if (!scales || !scales.x || !scales.y) return;
    const lastIdx = finished - 1;

    const ends = [];
    chart.data.datasets.forEach((ds) => {
      if (ds.hidden) return;
      const v = ds.data[lastIdx];
      if (v == null) return;
      ends.push({ ds, y: scales.y.getPixelForValue(v) });
    });
    ends.sort((a, b) => a.y - b.y);
    const minGap = 36;
    for (let k = 1; k < ends.length; k++) {
      if (ends[k].y - ends[k - 1].y < minGap) ends[k].y = ends[k - 1].y + minGap;
    }

    const left = scales.x.getPixelForValue(lastIdx) + 12;
    for (const e of ends) {
      const p = e.ds._player;
      const isMe = p.id === me;
      const el = document.createElement("div");
      el.className = "evo-label" + (isMe ? " is-me" : "");
      el.style.left = `${left}px`;
      el.style.top = `${e.y}px`;
      const avatar = p.avatar_url
        ? `<img src="${p.avatar_url}" alt="">`
        : `<span class="evo-label-ini" style="background:${e.ds._color}">${p.initials || "?"}</span>`;
      el.innerHTML = `
        <span class="evo-label-av" style="--ring:${e.ds._color}">
          ${avatar}
          <span class="evo-label-rank" style="border-color:${e.ds._color};color:${e.ds._color}">${p.rank}</span>
        </span>
        <span class="evo-label-txt">
          <span class="evo-label-name"${isMe ? ' style="color:var(--accent)"' : ""}>${isMe ? "Tú" : firstName(p.name)}</span>
        </span>`;
      labelsBox.appendChild(el);
    }
  }

  function renderLegend() {
    legendBox.innerHTML = "";
    if (showAll) {
      const info = document.createElement("div");
      info.className = "evo-allinfo";
      info.innerHTML = `Mostrando los <strong>${players.length}</strong> jugadores · pasa el cursor por el gráfico para identificarlos.`;
      legendBox.appendChild(info);
      return;
    }
    basePool.forEach((p, i) => {
      const c = colorOf(p, i);
      const on = visible.has(p.id);
      const btn = document.createElement("button");
      btn.type = "button";
      btn.className = "evo-pill" + (on ? " is-on" : "");
      btn.style.setProperty("--pill", c);
      btn.innerHTML = `<span class="evo-pill-dot"></span>${p.id === me ? "Tú" : firstName(p.name)}<span class="evo-pill-rank mono">#${p.rank}</span>`;
      btn.addEventListener("click", () => {
        if (visible.has(p.id)) visible.delete(p.id);
        else visible.add(p.id);
        rebuild();
      });
      legendBox.appendChild(btn);
    });
  }

  modesEl.querySelectorAll("button[data-mode]").forEach((b) => {
    b.addEventListener("click", () => {
      if (mode === b.dataset.mode) return;
      mode = b.dataset.mode;
      modesEl.querySelectorAll("button").forEach((x) => x.classList.toggle("is-active", x === b));
      rebuild();
    });
  });

  showAllBtn.addEventListener("click", () => {
    showAll = !showAll;
    showAllBtn.classList.toggle("is-on", showAll);
    showAllBtn.setAttribute("aria-pressed", String(showAll));
    rebuild();
  });

  let lastNarrow = isNarrow();
  const ro = new ResizeObserver(() => {
    const narrow = isNarrow();
    if (narrow !== lastNarrow) {
      lastNarrow = narrow;
      rebuild(); // cambia el padding del lienzo y la visibilidad de etiquetas
    } else {
      requestAnimationFrame(positionLabels);
    }
  });
  ro.observe(plotEl);

  rebuild();
}

/* ====================== Donut ====================== */
function setupDonut(root, payload) {
  const canvas = root.querySelector("[data-donut-canvas]");
  const legendBox = root.querySelector("[data-donut-legend]");
  const pctEl = root.querySelector("[data-donut-pct]");
  const bodyEl = root.querySelector("[data-donut-body]");
  const emptyEl = root.querySelector("[data-donut-empty]");
  if (!canvas) return;

  const meP = payload.players.find((p) => p.id === payload.me);
  const finished = payload.finished || 0;
  if (!meP || !finished) {
    if (bodyEl) bodyEl.hidden = true;
    if (emptyEl) emptyEl.hidden = false;
    return;
  }

  const exact = meP.exact;
  const partial = Math.max(0, meP.hits - meP.exact);
  const miss = Math.max(0, finished - meP.hits);
  const total = exact + partial + miss || 1;
  const segs = [
    { label: "Exactos", v: exact, c: cssVar("--c-lime") },
    { label: "Aciertos parciales", v: partial, c: cssVar("--c-cyan") },
    { label: "Fallos", v: miss, c: cssVar("--text-faint") },
  ];

  pctEl.textContent = `${Math.round((meP.hits / finished) * 100)}%`;

  new Chart(canvas.getContext("2d"), {
    type: "doughnut",
    data: {
      labels: segs.map((s) => s.label),
      datasets: [{
        data: segs.map((s) => s.v),
        backgroundColor: segs.map((s) => s.c),
        borderColor: cssVar("--surface-solid"),
        borderWidth: 2,
      }],
    },
    options: {
      responsive: true,
      maintainAspectRatio: true,
      cutout: "70%",
      plugins: {
        legend: { display: false },
        tooltip: {
          backgroundColor: cssVar("--surface-solid"),
          titleColor: cssVar("--text"),
          bodyColor: cssVar("--text"),
          borderColor: cssVar("--border-hi"),
          borderWidth: 1,
          callbacks: {
            label: (item) => ` ${item.label}: ${item.parsed} (${Math.round((item.parsed / total) * 100)}%)`,
          },
        },
      },
    },
  });

  legendBox.innerHTML = "";
  segs.forEach((s) => {
    const row = document.createElement("div");
    row.className = "donut-leg-row";
    row.innerHTML = `<span class="donut-leg-key" style="background:${s.c}"></span>
      <span class="donut-leg-label">${s.label}</span>
      <span class="mono donut-leg-val">${s.v}</span>
      <span class="mono donut-leg-pct">${Math.round((s.v / total) * 100)}%</span>`;
    legendBox.appendChild(row);
  });
}

/* ====================== Arranque ====================== */
async function init() {
  const srcEl = document.querySelector("[data-chart-src]");
  if (!srcEl || typeof Chart === "undefined") return;
  const page = document.querySelector(".stats-page");
  let payload;
  try {
    payload = await fetch(srcEl.dataset.chartSrc).then((r) => r.json());
  } catch {
    return;
  }
  setupEvolution(page, payload);
  setupDonut(page, payload);
}

init();
