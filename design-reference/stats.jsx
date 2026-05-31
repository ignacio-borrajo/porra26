/* stats.jsx — Estadísticas del jugador (ancho completo)
   Centro (80%): gráfico de líneas con la evolución de la POSICIÓN/PUNTOS
   partido a partido. Cada línea termina a la derecha con la identidad del
   jugador (posición, avatar, nombre y apellidos). Columna derecha (20%):
   "Tú frente al grupo" + donut con la distribución de tus pronósticos. */

const LINE_COLORS = [
  "var(--c-pink)", "var(--c-cyan)", "var(--c-lime)", "var(--c-yellow)",
  "var(--c-gold)", "var(--c-blue)", "var(--c-green)", "oklch(0.70 0.19 320)",
];

/* mide ancho y alto del contenedor para dibujar el SVG y rellenar el alto */
function useMeasure() {
  const ref = useRef(null);
  const [size, setSize] = useState({ w: 820, h: 360 });
  useEffect(() => {
    if (!ref.current) return;
    const ro = new ResizeObserver((es) => { for (const e of es) setSize({ w: e.contentRect.width, h: e.contentRect.height }); });
    ro.observe(ref.current);
    setSize({ w: ref.current.clientWidth || 820, h: ref.current.clientHeight || 360 });
    return () => ro.disconnect();
  }, []);
  return [ref, size];
}

/* ====================== KPI ====================== */
function KPI({ icon: Ic, label, value, sub, color, delay = 0 }) {
  return (
    <div className="glass rise" style={{ flex: "1 1 180px", borderRadius: 18, padding: "15px 16px", display: "flex", flexDirection: "column", gap: 10, animationDelay: `${delay}s`, position: "relative", overflow: "hidden" }}>
      <div style={{ position: "absolute", inset: 0, background: `radial-gradient(120% 80% at 100% 0%, oklch(from ${color} l c h / 0.12), transparent 60%)`, pointerEvents: "none" }} />
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <span style={{ width: 30, height: 30, borderRadius: 9, display: "grid", placeItems: "center", background: `oklch(from ${color} l c h / 0.16)`, color }}><Ic width="16" height="16" /></span>
        <span className="eyebrow" style={{ fontSize: 9 }}>{label}</span>
      </div>
      <div className="display" style={{ fontSize: 28, fontWeight: 800, lineHeight: 1, color }}>{value}</div>
      <div style={{ fontSize: 11.5, color: "var(--text-dim)" }}>{sub}</div>
    </div>
  );
}

/* ====================== Gráfico de evolución ====================== */
function RankChart({ ranked }) {
  const [mode, setMode] = useState("rank");   // 'rank' | 'pts'
  const [showAll, setShowAll] = useState(false); // switch "Mostrar todos"
  const [hi, setHi] = useState(null);          // índice de partido bajo el cursor
  const [box, size] = useMeasure();
  const W = size.w;
  const availH = Math.max(240, size.h);

  // pool por defecto: los 10 primeros (siempre) + tú si no estás en el top 10
  const meP = ranked.find((p) => p.id === ME);
  const top10 = ranked.slice(0, 10);
  const meInTop = top10.some((p) => p.id === ME);
  const basePool = meInTop ? top10 : [...top10, meP].filter(Boolean);
  const pool = showAll ? ranked : basePool;            // "Mostrar todos" → plantilla completa
  const colorOf = (p, i) => (p.id === ME ? "var(--accent)" : LINE_COLORS[i % LINE_COLORS.length]);

  const [visible, setVisible] = useState(() => new Set(basePool.map((p) => p.id)));
  const toggle = (id) => setVisible((s) => { const n = new Set(s); n.has(id) ? n.delete(id) : n.add(id); return n; });

  const N = FINISHED;
  const pad = { l: 40, r: 172, t: 16, b: 26 };
  const plotW = Math.max(60, W - pad.l - pad.r);
  const x = (i) => pad.l + (N <= 1 ? 0 : (i / (N - 1)) * plotW);

  const vis = showAll ? pool : pool.filter((p) => visible.has(p.id));
  const seriesData = (p) => (mode === "rank" ? RANK_HIST[p.id] : PTS_HIST[p.id]) || [];

  // altura del lienzo: rellena el alto disponible y, con muchas líneas, crece
  // (la card hace scroll interno sin barras) para que las etiquetas no se solapen
  const rowH = 42;
  const H = Math.max(availH, pad.t + pad.b + Math.max(1, vis.length) * rowH);
  const plotH = H - pad.t - pad.b;

  let yMin, yMax;
  if (mode === "rank") {
    let mx = 1; vis.forEach((p) => seriesData(p).forEach((v) => (mx = Math.max(mx, v))));
    yMin = 1; yMax = Math.min(ranked.length, mx + 1); if (yMax <= yMin) yMax = yMin + 1;
  } else {
    let mx = 1; vis.forEach((p) => seriesData(p).forEach((v) => (mx = Math.max(mx, v))));
    yMin = 0; yMax = mx || 1;
  }
  const y = (v) => mode === "rank"
    ? pad.t + ((v - yMin) / (yMax - yMin)) * plotH
    : pad.t + (1 - (v - yMin) / (yMax - yMin)) * plotH;

  const ticks = [];
  const steps = 4;
  for (let k = 0; k <= steps; k++) ticks.push(Math.round(yMin + (k / steps) * (yMax - yMin)));
  const uniqTicks = [...new Set(ticks)];

  const pathOf = (p) => seriesData(p).map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");

  const onMove = (e) => {
    const r = e.currentTarget.getBoundingClientRect();
    const px = ((e.clientX - r.left) / r.width) * W;
    const i = Math.round(((px - pad.l) / plotW) * (N - 1));
    setHi(Math.max(0, Math.min(N - 1, i)));
  };

  const meStart = RANK_HIST[ME]?.[0] ?? 0;
  const meNow = RANK_HIST[ME]?.[N - 1] ?? 0;
  const climbed = meStart - meNow;

  const tipFull = hi != null ? vis
    .map((p) => ({ p, i: pool.indexOf(p), v: seriesData(p)[hi] }))
    .sort((a, b) => mode === "rank" ? a.v - b.v : b.v - a.v) : [];
  const tip = showAll ? tipFull.slice(0, 12) : tipFull;   // tooltip acotado con todos

  // etiquetas de fin de línea (identidad del jugador), con anti-solape vertical
  const ends = vis.map((p) => ({ p, i: pool.indexOf(p), c: colorOf(p, pool.indexOf(p)), y: y(seriesData(p)[N - 1]) }))
    .sort((a, b) => a.y - b.y);
  const minGap = 38;
  for (let k = 1; k < ends.length; k++) if (ends[k].y - ends[k - 1].y < minGap) ends[k].y = ends[k - 1].y + minGap;
  // empuje hacia arriba si rebasa el borde inferior
  const bottom = H - 6;
  for (let k = ends.length - 1; k > 0; k--) if (ends[k].y > bottom) ends[k - 1].y = Math.min(ends[k - 1].y, ends[k].y - minGap);

  return (
    <div className="glass rise" style={{ borderRadius: 22, padding: 20, display: "flex", flexDirection: "column", gap: 14, minWidth: 0, minHeight: 0 }}>
      {/* cabecera */}
      <div style={{ display: "flex", alignItems: "flex-start", justifyContent: "space-between", gap: 12, flexWrap: "wrap", flexShrink: 0 }}>
        <div>
          <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
            <I.chart width="18" height="18" style={{ color: "var(--accent)" }} />
            <h3 className="display" style={{ margin: 0, fontSize: 16 }}>{mode === "rank" ? "Evolución de la posición" : "Evolución de puntos"}</h3>
          </div>
          <p style={{ margin: "6px 0 0", fontSize: 12, color: "var(--text-dim)" }}>
            {climbed > 0
              ? <>Has escalado <strong style={{ color: "var(--c-lime)" }}>{climbed} posiciones</strong> desde el primer partido.</>
              : climbed < 0
              ? <>Has cedido <strong style={{ color: "var(--c-red)" }}>{-climbed} posiciones</strong> desde el primer partido.</>
              : <>Mantienes tu posición desde el primer partido.</>}
          </p>
        </div>
        <div style={{ display: "flex", alignItems: "center", gap: 12, flexWrap: "wrap" }}>
          {/* switch: cargar el gráfico con todos los jugadores */}
          <button onClick={() => setShowAll((v) => !v)} title="Cargar el gráfico con todos los jugadores" style={{
            display: "flex", alignItems: "center", gap: 9, padding: "6px 12px 6px 11px", borderRadius: 999, cursor: "pointer",
            border: `1px solid ${showAll ? "oklch(from var(--accent) l c h / 0.5)" : "var(--border-hi)"}`,
            background: showAll ? "oklch(from var(--accent) l c h / 0.12)" : "var(--surface-hi)",
            color: showAll ? "var(--text)" : "var(--text-dim)", transition: "all .2s",
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 12.5,
          }}>
            <span style={{ position: "relative", width: 30, height: 17, borderRadius: 999, flexShrink: 0, transition: "background .2s",
              background: showAll ? "linear-gradient(135deg, var(--accent), var(--accent-2))" : "var(--border-hi)" }}>
              <span style={{ position: "absolute", top: 2, left: showAll ? 15 : 2, width: 13, height: 13, borderRadius: "50%", background: "white", transition: "left .2s var(--ease-out)", boxShadow: "0 1px 3px rgba(0,0,0,.35)" }} />
            </span>
            Mostrar todos
          </button>
          <div style={{ display: "flex", gap: 4, background: "var(--surface-hi)", padding: 4, borderRadius: 12, border: "1px solid var(--border-hi)" }}>
            {[["rank", "Posición"], ["pts", "Puntos"]].map(([k, lbl]) => (
              <button key={k} onClick={() => setMode(k)} style={{
                padding: "7px 14px", borderRadius: 9, border: "none", cursor: "pointer",
                fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 12.5,
                background: mode === k ? "linear-gradient(135deg, var(--accent), var(--accent-2))" : "transparent",
                color: mode === k ? "white" : "var(--text-dim)", transition: "all .25s var(--ease-out)",
              }}>{lbl}</button>
            ))}
          </div>
        </div>
      </div>

      {/* SVG: rellena el alto disponible; scroll interno SIN barras cuando hay muchas líneas */}
      <div ref={box} style={{ position: "relative", width: "100%", flex: 1, minHeight: 220 }}>
       <div className="no-scrollbar" style={{ position: "absolute", inset: 0, overflowY: "auto", overflowX: "hidden" }}>
        <div style={{ position: "relative", width: "100%", height: H }}>
        <svg width={W} height={H} onMouseMove={onMove} onMouseLeave={() => setHi(null)} style={{ display: "block", overflow: "visible" }}>
          {uniqTicks.map((v) => (
            <g key={v}>
              <line x1={pad.l} x2={pad.l + plotW} y1={y(v)} y2={y(v)} stroke="var(--border)" strokeWidth="1" />
              <text x={pad.l - 8} y={y(v) + 3.5} textAnchor="end" fontSize="10" fontFamily="var(--font-mono)" fill="var(--text-faint)">{mode === "rank" ? `#${v}` : v}</text>
            </g>
          ))}
          {Array.from({ length: N }).map((_, i) => (
            <text key={i} x={x(i)} y={H - 4} textAnchor="middle" fontSize="9" fontFamily="var(--font-mono)" fill="var(--text-faint)">{i + 1}</text>
          ))}
          {hi != null && <line x1={x(hi)} x2={x(hi)} y1={pad.t} y2={pad.t + plotH} stroke="var(--border-hi)" strokeWidth="1" strokeDasharray="3 3" />}

          {vis.map((p) => {
            const i = pool.indexOf(p);
            const me = p.id === ME;
            const c = colorOf(p, i);
            return (
              <path key={p.id} d={pathOf(p)} fill="none" stroke={c} strokeWidth={me ? 3 : 2}
                strokeLinejoin="round" strokeLinecap="round" opacity={me ? 1 : 0.78}
                style={{ filter: me ? "drop-shadow(0 2px 8px var(--accent))" : "none" }} />
            );
          })}
          {/* conector del último punto a la etiqueta */}
          {ends.map(({ p, c }) => {
            const v0 = seriesData(p)[N - 1];
            return <line key={p.id} x1={x(N - 1)} y1={y(v0)} x2={pad.l + plotW + 8} y2={ends.find((e) => e.p === p).y} stroke={c} strokeWidth="1" opacity="0.45" />;
          })}
          {ends.map(({ p, c }) => <circle key={p.id} cx={x(N - 1)} cy={y(seriesData(p)[N - 1])} r={p.id === ME ? 4.5 : 3.5} fill={c} />)}

          {hi != null && vis.map((p) => {
            const i = pool.indexOf(p);
            const c = colorOf(p, i);
            const v = seriesData(p)[hi];
            return <circle key={p.id} cx={x(hi)} cy={y(v)} r={p.id === ME ? 5 : 3.5} fill="var(--surface-solid)" stroke={c} strokeWidth="2.5" />;
          })}
        </svg>

        {/* etiquetas de identidad al final de cada línea */}
        {ends.map(({ p, i, c, y: ly }) => {
          const me = p.id === ME;
          const clean = p.name.replace("Tú · ", "");
          const parts = clean.split(" ");
          const first = parts[0];
          const last = parts.slice(1).join(" ");
          return (
            <div key={p.id} style={{
              position: "absolute", left: pad.l + plotW + 16, top: ly, transform: "translateY(-50%)",
              display: "flex", alignItems: "center", gap: 8, width: pad.r - 22, pointerEvents: "none",
            }}>
              <div style={{ position: "relative", flexShrink: 0 }}>
                <Avatar p={p} size={30} ring={me} />
                <span className="mono" style={{ position: "absolute", top: -7, left: -7, fontSize: 9, fontWeight: 700, padding: "1px 4px", borderRadius: 6, background: "var(--surface-solid)", border: `1px solid ${c}`, color: c, lineHeight: 1.3 }}>
                  {ranked.indexOf(p) + 1}
                </span>
              </div>
              <div style={{ flex: 1, minWidth: 0, lineHeight: 1.12 }}>
                <div style={{ fontSize: 12, fontWeight: 700, color: me ? "var(--accent)" : "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{me ? "Tú" : first}</div>
                {(last || me) && <div style={{ fontSize: 11, color: "var(--text-dim)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{me ? clean : last}</div>}
              </div>
            </div>
          );
        })}

        {/* tooltip */}
        {hi != null && tip.length > 0 && (
          <div className="glass" style={{
            position: "absolute", top: 4,
            left: Math.min(Math.max(0, (x(hi) / W) * 100), 100) + "%",
            transform: `translateX(${hi > N / 2 ? "calc(-100% - 12px)" : "12px"})`,
            background: "var(--surface-solid)", borderRadius: 12, padding: "9px 11px", minWidth: 150, pointerEvents: "none", zIndex: 5,
          }}>
            <div className="eyebrow" style={{ fontSize: 8.5, marginBottom: 6 }}>Partido {hi + 1}</div>
            <div style={{ display: "flex", flexDirection: "column", gap: 5 }}>
              {tip.map(({ p, i, v }) => (
                <div key={p.id} style={{ display: "flex", alignItems: "center", gap: 7, fontSize: 12 }}>
                  <span style={{ width: 9, height: 9, borderRadius: 3, background: colorOf(p, i), flexShrink: 0 }} />
                  <span style={{ flex: 1, fontWeight: p.id === ME ? 700 : 500, color: p.id === ME ? "var(--accent)" : "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name.replace("Tú · ", "Tú")}</span>
                  <span className="mono" style={{ fontWeight: 700 }}>{mode === "rank" ? `#${v}` : v}</span>
                </div>
              ))}
              {tipFull.length > tip.length && (
                <div className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)", paddingLeft: 16 }}>+{tipFull.length - tip.length} más</div>
              )}
            </div>
          </div>
        )}
        </div>
       </div>
      </div>

      {/* leyenda / selector de jugadores (oculta al mostrar todos) */}
      {!showAll ? (
      <div style={{ display: "flex", flexWrap: "wrap", gap: 7, borderTop: "1px solid var(--border)", paddingTop: 13, flexShrink: 0 }}>
        {pool.map((p, i) => {
          const on = visible.has(p.id);
          const c = colorOf(p, i);
          const me = p.id === ME;
          return (
            <button key={p.id} onClick={() => toggle(p.id)} style={{
              display: "flex", alignItems: "center", gap: 7, padding: "5px 11px 5px 8px", borderRadius: 999, cursor: "pointer",
              border: `1px solid ${on ? `oklch(from ${c} l c h / 0.5)` : "var(--border)"}`,
              background: on ? `oklch(from ${c} l c h / 0.12)` : "transparent",
              color: on ? "var(--text)" : "var(--text-faint)", transition: "all .2s",
              fontFamily: "var(--font-sans)", fontWeight: 600, fontSize: 12.5,
            }}>
              <span style={{ width: 10, height: 10, borderRadius: 3, background: on ? c : "var(--border-hi)", flexShrink: 0 }} />
              {me ? "Tú" : p.name.replace("Tú · ", "")}
              <span className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)" }}>#{ranked.indexOf(p) + 1}</span>
            </button>
          );
        })}
      </div>
      ) : (
      <div style={{ borderTop: "1px solid var(--border)", paddingTop: 13, flexShrink: 0, display: "flex", alignItems: "center", gap: 8, fontSize: 12, color: "var(--text-dim)" }}>
        <I.users width="15" height="15" style={{ color: "var(--accent)", flexShrink: 0 }} />
        Mostrando los <strong style={{ color: "var(--text)" }}>{pool.length}</strong> jugadores · desplázate dentro del gráfico para verlos todos.
      </div>
      )}
    </div>
  );
}

/* ====================== Panel comparativo ====================== */
function CompareBar({ label, me, avg, best, fmt = (v) => v }) {
  const max = Math.max(me, avg, best, 1);
  const pct = (v) => `${(v / max) * 100}%`;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 6 }}>
      <div style={{ display: "flex", alignItems: "baseline", justifyContent: "space-between", gap: 8 }}>
        <span style={{ fontSize: 13, fontWeight: 600 }}>{label}</span>
        <span className="mono" style={{ fontSize: 13, fontWeight: 700, color: "var(--accent)" }}>{fmt(me)}</span>
      </div>
      <div style={{ position: "relative", height: 13, borderRadius: 999, background: "var(--border)" }}>
        <div style={{ position: "absolute", inset: 0, width: pct(me), borderRadius: 999, background: "linear-gradient(90deg, var(--accent), var(--accent-2))", boxShadow: "0 0 12px -3px var(--accent)" }} />
        <div style={{ position: "absolute", top: -3, bottom: -3, left: pct(avg), width: 2, background: "var(--text-faint)" }} title="Media" />
        <div style={{ position: "absolute", top: -3, bottom: -3, left: pct(best), width: 2, background: "var(--c-gold)" }} title="Mejor" />
      </div>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)", display: "flex", gap: 12 }}>
        <span>media {fmt(avg)}</span><span style={{ color: "var(--c-gold)" }}>máx {fmt(best)}</span>
      </div>
    </div>
  );
}

function ComparePanel({ ranked, me }) {
  const n = ranked.length;
  const avg = (sel) => ranked.reduce((s, p) => s + sel(p), 0) / n;
  const best = (sel) => Math.max(...ranked.map(sel));
  const r1 = (x) => Math.round(x * 10) / 10;
  return (
    <div className="glass rise" style={{ borderRadius: 22, padding: 20, display: "flex", flexDirection: "column", gap: 16, animationDelay: ".06s", flexShrink: 0 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <I.scale width="18" height="18" style={{ color: "var(--c-gold)" }} />
        <h3 className="display" style={{ margin: 0, fontSize: 16 }}>Tú frente al grupo</h3>
      </div>
      <div style={{ display: "flex", flexDirection: "column", gap: 16 }}>
        <CompareBar label="Puntos" me={me.pts} avg={r1(avg((p) => p.pts))} best={best((p) => p.pts)} fmt={r1} />
        <CompareBar label="Aciertos" me={me.hits} avg={r1(avg((p) => p.hits))} best={best((p) => p.hits)} fmt={r1} />
        <CompareBar label="Exactos" me={me.exact} avg={r1(avg((p) => p.exact))} best={best((p) => p.exact)} fmt={r1} />
      </div>
      <div style={{ display: "flex", gap: 14, borderTop: "1px solid var(--border)", paddingTop: 12, fontSize: 11, color: "var(--text-dim)", flexWrap: "wrap" }}>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 12, height: 8, borderRadius: 3, background: "linear-gradient(90deg, var(--accent), var(--accent-2))" }} /> Tú</span>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 2, height: 12, background: "var(--text-faint)" }} /> Media</span>
        <span style={{ display: "flex", alignItems: "center", gap: 6 }}><span style={{ width: 2, height: 12, background: "var(--c-gold)" }} /> Mejor</span>
      </div>
    </div>
  );
}

/* ====================== Donut: distribución de pronósticos ====================== */
function DonutCard({ me }) {
  const exact = me.exact;
  const partial = Math.max(0, me.hits - me.exact);
  const miss = Math.max(0, FINISHED - me.hits);
  const total = exact + partial + miss || 1;
  const segs = [
    { label: "Exactos", v: exact, c: "var(--c-lime)" },
    { label: "Aciertos parciales", v: partial, c: "var(--c-cyan)" },
    { label: "Fallos", v: miss, c: "oklch(0.5 0.02 275)" },
  ];
  const S = 168, sw = 22, r = (S - sw) / 2 - 2, cx = S / 2, cy = S / 2;
  const C = 2 * Math.PI * r;
  const gap = 2; // px de separación entre segmentos
  let off = 0;
  const acc = Math.round((me.hits / FINISHED) * 100);

  return (
    <div className="glass rise" style={{ borderRadius: 22, padding: 20, display: "flex", flexDirection: "column", gap: 14, animationDelay: ".1s", flex: 1, minHeight: 300 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
        <I.target width="18" height="18" style={{ color: "var(--c-cyan)" }} />
        <h3 className="display" style={{ margin: 0, fontSize: 16 }}>Tus pronósticos</h3>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", gap: 16, flex: 1, minHeight: 0 }}>
        <div style={{ position: "relative", width: S, height: S, flexShrink: 0 }}>
          <svg width={S} height={S} viewBox={`0 0 ${S} ${S}`} style={{ transform: "rotate(-90deg)" }}>
            <circle cx={cx} cy={cy} r={r} fill="none" stroke="var(--border)" strokeWidth={sw} />
            {segs.map((s) => {
              const len = (s.v / total) * C;
              const dash = Math.max(0, len - gap);
              const el = <circle key={s.label} cx={cx} cy={cy} r={r} fill="none" stroke={s.c} strokeWidth={sw}
                strokeDasharray={`${dash} ${C - dash}`} strokeDashoffset={-off} strokeLinecap="butt" />;
              off += len;
              return el;
            })}
          </svg>
          <div style={{ position: "absolute", inset: 0, display: "grid", placeItems: "center", textAlign: "center" }}>
            <div>
              <div className="display" style={{ fontSize: 34, fontWeight: 800, lineHeight: 1, color: "var(--c-cyan)" }}>{acc}%</div>
              <div className="eyebrow" style={{ fontSize: 8.5, marginTop: 4 }}>aciertos</div>
            </div>
          </div>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 9, width: "100%" }}>
          {segs.map((s) => (
            <div key={s.label} style={{ display: "flex", alignItems: "center", gap: 9 }}>
              <span style={{ width: 11, height: 11, borderRadius: 4, background: s.c, flexShrink: 0 }} />
              <span style={{ flex: 1, fontSize: 12.5, color: "var(--text-dim)" }}>{s.label}</span>
              <span className="mono" style={{ fontSize: 13, fontWeight: 700 }}>{s.v}</span>
              <span className="mono" style={{ fontSize: 11, color: "var(--text-faint)", minWidth: 34, textAlign: "right" }}>{Math.round((s.v / total) * 100)}%</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ====================== Pantalla ====================== */
function StatsScreen() {
  const ranked = [...PLAYERS].filter((p) => p.active).sort((a, b) => b.pts - a.pts);
  const me = PLAYERS.find((p) => p.id === ME);
  const n = ranked.length;
  const myRank = ranked.findIndex((p) => p.id === ME) + 1;
  const leader = ranked[0];
  const avgPts = ranked.reduce((s, p) => s + p.pts, 0) / n;
  const diffAvg = me.pts - avgPts;
  const gapLeader = me.pts - leader.pts;
  const aheadOf = n - myRank;
  const percentile = Math.round((aheadOf / (n - 1)) * 100);
  const acc = Math.round((me.hits / FINISHED) * 100);
  const myHist = RANK_HIST[ME] || [];
  const bestPos = Math.min(...myHist);
  const r1 = (x) => Math.round(x * 10) / 10;

  return (
    <div style={{ height: "100%", minHeight: 0, display: "flex", flexDirection: "column", gap: 16, overflowY: "auto", paddingRight: 4 }}>
      {/* cabecera */}
      <div className="rise" style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 12, flexShrink: 0 }}>
        <div>
          <span className="eyebrow">MUNDIAL 2026 · ESTADÍSTICAS</span>
          <h1 className="display" style={{ margin: "6px 0 0", fontSize: "clamp(22px, 2.2vw, 30px)", fontFamily: "Sora" }}>Tu rendimiento</h1>
        </div>
        <span className="chip" style={{ color: "var(--c-gold)", borderColor: "oklch(from var(--c-gold) l c h / 0.4)", padding: "6px 12px" }}>
          <I.trophy width="13" height="13" /> Posición #{myRank} de {n}
        </span>
      </div>

      {/* KPIs */}
      <div style={{ display: "flex", gap: 12, flexWrap: "wrap", flexShrink: 0 }}>
        <KPI icon={I.target} label="% de aciertos" value={`${acc}%`} sub={`${me.hits} de ${FINISHED} partidos · ${me.exact} exactos`} color="var(--c-cyan)" delay={0} />
        <KPI icon={I.scale} label="vs Media" value={`${diffAvg >= 0 ? "+" : ""}${r1(diffAvg)}`} sub={`Media del grupo ${r1(avgPts)} pts`} color={diffAvg >= 0 ? "var(--c-lime)" : "var(--c-red)"} delay={0.04} />
        <KPI icon={I.trophy} label="vs Líder" value={`${gapLeader >= 0 ? "+" : ""}${gapLeader}`} sub={`${leader.name.replace("Tú · ", "")} · ${leader.pts} pts`} color="var(--c-gold)" delay={0.08} />
        <KPI icon={I.gauge} label="Percentil" value={`Top ${Math.max(1, 100 - percentile)}%`} sub={`Mejor que ${aheadOf} jugadores · mejor #${bestPos}`} color="var(--accent)" delay={0.12} />
      </div>

      {/* gráfico (80%) + columna derecha (20%): comparativa + donut */}
      <div className="stats-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0, 4fr) minmax(300px, 1fr)", gap: 16, flex: 1, minHeight: 460 }}>
        <RankChart ranked={ranked} />
        <div style={{ display: "flex", flexDirection: "column", gap: 16, minHeight: 0 }}>
          <ComparePanel ranked={ranked} me={me} />
          <DonutCard me={me} />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { StatsScreen });
