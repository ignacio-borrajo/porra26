const SVG_NS = "http://www.w3.org/2000/svg";

function el(tag, attrs = {}) {
  const n = document.createElementNS(SVG_NS, tag);
  for (const [k, v] of Object.entries(attrs)) n.setAttribute(k, v);
  return n;
}

function legendNode(pid, info, isMe) {
  const g = el("g");
  if (info && info.avatar_url) {
    const clipId = `clip-${pid}`;
    const defs = el("defs");
    const clip = el("clipPath", { id: clipId });
    clip.appendChild(el("circle", { cx: 0, cy: 0, r: 12 }));
    defs.appendChild(clip);
    g.appendChild(defs);
    g.appendChild(el("image", {
      href: info.avatar_url,
      x: -12, y: -12, width: 24, height: 24,
      preserveAspectRatio: "xMidYMid slice",
      "clip-path": `url(#${clipId})`,
    }));
    g.appendChild(el("circle", {
      cx: 0, cy: 0, r: 12, fill: "none",
      stroke: isMe ? "var(--accent)" : "var(--border-hi)",
      "stroke-width": isMe ? 2.5 : 1,
    }));
  } else {
    const hue = info ? info.hue : 250;
    g.appendChild(el("circle", {
      cx: 0, cy: 0, r: 12,
      fill: `oklch(0.64 0.19 ${hue})`,
      stroke: isMe ? "var(--accent)" : "transparent",
      "stroke-width": isMe ? 2.5 : 0,
    }));
    const t = el("text", {
      x: 0, y: 0,
      "text-anchor": "middle",
      "dominant-baseline": "central",
      fill: "white",
      "font-size": 10,
      "font-weight": 700,
      "font-family": "var(--font-display)",
    });
    t.textContent = (info && info.initials) || "?";
    g.appendChild(t);
  }
  return g;
}

async function build(container) {
  const src = container.dataset.src;
  const data = await fetch(src).then((r) => r.json());
  const series = Object.entries(data.history);
  if (!series.length) { container.innerHTML = "<p>Sin datos todavía.</p>"; return; }

  const players = data.players || {};
  const W = container.clientWidth || 700, H = 340, PAD = 30, LEGEND_PAD = 18;
  const allIdx = series[0][1].map((p) => p.idx);
  const xMax = Math.max(...allIdx);
  const yMax = Math.max(...series.flatMap(([, pts]) => pts.map((p) => p.pts))) || 1;

  const xScale = (i) => PAD + (i / xMax) * (W - 2 * PAD - LEGEND_PAD);
  const yScale = (v) => H - PAD - (v / yMax) * (H - 2 * PAD);

  const svg = el("svg", { viewBox: `0 0 ${W} ${H}` });
  svg.style.width = "100%"; svg.style.height = "auto";

  for (const [pid, pts] of series) {
    const d = pts.map((p, k) => `${k === 0 ? "M" : "L"} ${xScale(p.idx)} ${yScale(p.pts)}`).join(" ");
    const isMe = Number(pid) === data.me;
    svg.appendChild(el("path", {
      d, fill: "none",
      stroke: isMe ? "var(--accent)" : "var(--border-hi)",
      "stroke-width": isMe ? 3 : 1.5,
    }));
    const last = pts[pts.length - 1];
    if (last) {
      const legend = legendNode(pid, players[pid], isMe);
      legend.setAttribute("transform", `translate(${xScale(last.idx) + LEGEND_PAD},${yScale(last.pts)})`);
      svg.appendChild(legend);
    }
  }
  container.innerHTML = "";
  container.appendChild(svg);
}

document.querySelectorAll("[data-rank-chart]").forEach(build);
