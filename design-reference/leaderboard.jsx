/* leaderboard.jsx — Clasificación: podio top 3 + tabla estilo liga con barras animadas.
   variant: 'full' (podio + lista) | 'list' (solo lista compacta) */

function TrendIcon({ trend }) {
  if (trend === "up") return <I.up width="13" height="13" style={{ color: "var(--c-lime)" }} />;
  if (trend === "down") return <I.down width="13" height="13" style={{ color: "var(--c-red)" }} />;
  return <span style={{ width: 13, height: 2, background: "var(--text-faint)", display: "inline-block", borderRadius: 2 }} />;
}

function Podium({ players, maxPts }) {
  const top3 = players.slice(0, 3);
  // orden visual: 2º, 1º, 3º
  const order = [top3[1], top3[0], top3[2]].filter(Boolean);
  const heights = { 0: 112, 1: 84, 2: 62 };
  const medal = ["🥇", "🥈", "🥉"];
  return (
    <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "center", gap: 10, padding: "8px 4px 0" }}>
      {order.map((p) => {
        const rank = players.indexOf(p);
        const isMe = p.id === ME;
        const podiumColors = ["var(--c-gold)", "oklch(0.82 0.02 250)", "oklch(0.68 0.1 50)"];
        return (
          <div key={p.id} className="pop" style={{ flex: rank === 0 ? 1.15 : 1, display: "flex", flexDirection: "column", alignItems: "center", gap: 8, animationDelay: `${0.1 + rank * 0.08}s` }}>
            <div style={{ fontSize: 22, filter: `drop-shadow(0 4px 10px ${podiumColors[rank]})` }}>{medal[rank]}</div>
            <Avatar p={p} size={rank === 0 ? 50 : 42} ring={isMe} />
            <div style={{ textAlign: "center", lineHeight: 1.15 }}>
              <div className="display" style={{ fontSize: 13, fontWeight: 700, color: isMe ? "var(--accent)" : "var(--text)", maxWidth: 78, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                {p.name.replace("Tú · ", "")}
              </div>
              <div className="mono grad-text" style={{ fontSize: 17, fontWeight: 700 }}><AnimNum value={p.pts} /></div>
            </div>
            <div style={{
              width: "100%", height: heights[rank], borderRadius: "12px 12px 0 0",
              background: `linear-gradient(180deg, oklch(from ${podiumColors[rank]} l c h / 0.5), oklch(from ${podiumColors[rank]} l c h / 0.08))`,
              border: "1px solid var(--border-hi)", borderBottom: "none",
              display: "grid", placeItems: "center",
              boxShadow: `0 -8px 30px -14px ${podiumColors[rank]}`,
              position: "relative", overflow: "hidden",
            }}>
              <span className="display" style={{ fontSize: 30, fontWeight: 800, color: podiumColors[rank], opacity: 0.85 }}>{rank + 1}</span>
            </div>
          </div>
        );
      })}
    </div>
  );
}

function LeaderRow({ p, rank, maxPts, highlight }) {
  const isMe = p.id === ME;
  const pct = Math.round((p.pts / maxPts) * 100);
  return (
    <div className="rise" style={{
      display: "grid", gridTemplateColumns: "26px 1fr auto", alignItems: "center", gap: 11,
      padding: "10px 12px", borderRadius: 14,
      background: isMe ? "linear-gradient(100deg, oklch(from var(--accent) l c h / 0.16), oklch(from var(--accent-2) l c h / 0.06))" : "transparent",
      border: isMe ? "1px solid oklch(from var(--accent) l c h / 0.4)" : "1px solid transparent",
      boxShadow: isMe ? "0 0 22px -10px var(--accent)" : "none",
      position: "relative",
    }}>
      <div className="mono" style={{ fontSize: 13, fontWeight: 700, color: isMe ? "var(--accent)" : "var(--text-faint)", textAlign: "center" }}>{rank}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
        <Avatar p={p} size={32} ring={isMe} />
        <div style={{ minWidth: 0 }}>
          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
            <span style={{ fontWeight: 600, fontSize: 13.5, color: isMe ? "var(--accent)" : "var(--text)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
              {p.name.replace("Tú · ", isMe ? "Tú · " : "")}
            </span>
            {p.streak >= 3 && <span className="chip" style={{ padding: "1px 6px", color: "var(--c-yellow)", borderColor: "oklch(from var(--c-yellow) l c h / 0.4)", gap: 3 }}><I.flame width="10" height="10" />{p.streak}</span>}
          </div>
          <div className="bar" style={{ marginTop: 5, height: 5 }}>
            <i style={{ width: `${pct}%` }} />
          </div>
        </div>
      </div>
      <div style={{ display: "flex", alignItems: "center", gap: 9, textAlign: "right" }}>
        <div style={{ fontSize: 11, color: "var(--text-faint)" }} className="mono" title="Aciertos · Exactos">
          {p.hits}·<span style={{ color: "var(--c-lime)" }}>{p.exact}</span>
        </div>
        <TrendIcon trend={p.trend} />
        <div className="display mono" style={{ fontSize: 16, fontWeight: 800, color: isMe ? "var(--accent)" : "var(--text)", minWidth: 30 }}>{p.pts}</div>
      </div>
    </div>
  );
}

function Leaderboard({ variant = "full", players, title = "Clasificación", scrollList = true }) {
  const ranked = [...players].filter((p) => p.active).sort((a, b) => b.pts - a.pts);
  const maxPts = ranked[0]?.pts || 1;
  const myRank = ranked.findIndex((p) => p.id === ME) + 1;
  const rest = variant === "full" ? ranked.slice(3) : ranked;

  return (
    <div style={{ display: "flex", flexDirection: "column", height: "100%", minHeight: 0 }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 14 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
          <I.trophy width="18" height="18" style={{ color: "var(--c-gold)" }} />
          <h3 className="display" style={{ margin: 0, fontSize: 16 }}>{title}</h3>
        </div>
        {myRank > 0 && (
          <span className="chip" style={{ color: "var(--accent)", borderColor: "oklch(from var(--accent) l c h / 0.4)" }}>
            Tú · #{myRank}
          </span>
        )}
      </div>

      {variant === "full" && <Podium players={ranked} maxPts={maxPts} />}

      <div style={{
        marginTop: variant === "full" ? 6 : 0,
        display: "flex", flexDirection: "column", gap: 2,
        overflowY: scrollList ? "auto" : "visible", paddingRight: 2, minHeight: 0,
      }} className="stagger no-scrollbar">
        {variant === "full" && (
          <div style={{ display: "grid", gridTemplateColumns: "26px 1fr auto", gap: 11, padding: "2px 12px 6px", borderBottom: "1px solid var(--border)" }}>
            <span className="eyebrow" style={{ fontSize: 9, textAlign: "center" }}>#</span>
            <span className="eyebrow" style={{ fontSize: 9 }}>Jugador</span>
            <span className="eyebrow" style={{ fontSize: 9 }}>Pts</span>
          </div>
        )}
        {rest.map((p) => (
          <LeaderRow key={p.id} p={p} rank={ranked.indexOf(p) + 1} maxPts={maxPts} />
        ))}
      </div>
    </div>
  );
}

Object.assign(window, { Leaderboard, Podium, LeaderRow, TrendIcon });
