async function build(container) {
  const src = container.dataset.src;
  const data = await fetch(src).then((r) => r.json());
  const series = Object.entries(data.history);
  if (!series.length) { container.innerHTML = "<p>Sin datos todavía.</p>"; return; }

  const W = container.clientWidth || 700, H = 340, PAD = 30;
  const allIdx = series[0][1].map((p) => p.idx);
  const xMax = Math.max(...allIdx);
  const yMax = Math.max(...series.flatMap(([, pts]) => pts.map((p) => p.pts))) || 1;

  const xScale = (i) => PAD + (i / xMax) * (W - 2 * PAD);
  const yScale = (v) => H - PAD - (v / yMax) * (H - 2 * PAD);

  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("viewBox", `0 0 ${W} ${H}`);
  svg.style.width = "100%"; svg.style.height = "auto";

  for (const [pid, pts] of series) {
    const d = pts.map((p, k) => `${k === 0 ? "M" : "L"} ${xScale(p.idx)} ${yScale(p.pts)}`).join(" ");
    const path = document.createElementNS("http://www.w3.org/2000/svg", "path");
    path.setAttribute("d", d);
    path.setAttribute("fill", "none");
    const isMe = Number(pid) === data.me;
    path.setAttribute("stroke", isMe ? "var(--accent)" : "var(--border-hi)");
    path.setAttribute("stroke-width", isMe ? "3" : "1.5");
    svg.appendChild(path);
  }
  container.innerHTML = "";
  container.appendChild(svg);
}

document.querySelectorAll("[data-rank-chart]").forEach(build);
