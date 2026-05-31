/* dashboard.jsx — Panel del jugador: selector de ronda + partidos + clasificación lateral */

/* Agrupación de partidos por estado. Dentro de cada grupo se ordenan por fecha
   (kickoff ascendente) para que los que cierran antes queden a la izquierda. */
const MATCH_GROUPS = [
  { key: "abiertos", label: "Abiertos",    color: "var(--c-lime)", test: (m) => m.status === "open" || m.status === "closing" },
  { key: "juego",    label: "En Juego",    color: "var(--c-red)",  test: (m) => m.status === "live" || m.status === "closed" },
  { key: "fin",      label: "Finalizados", color: "var(--text-dim)", test: (m) => m.status === "done" },
];

function RoundSelector({ active, onChange }) {
  return (
    <div style={{ display: "flex", gap: 6, overflowX: "auto", padding: 4, background: "var(--surface)", borderRadius: 16, border: "1px solid var(--border)", backdropFilter: "blur(var(--glass-blur))" }}>
      {ROUNDS.map((r) => {
        const count = MATCHES[r.id]?.length || 0;
        const on = active === r.id;
        return (
          <button key={r.id} onClick={() => onChange(r.id)} style={{
            flexShrink: 0, padding: "9px 16px", borderRadius: 12, border: "none", cursor: "pointer",
            fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13.5,
            display: "flex", alignItems: "center", gap: 8,
            background: on ? "linear-gradient(135deg, var(--accent), var(--accent-2))" : "transparent",
            color: on ? "white" : "var(--text-dim)",
            boxShadow: on ? "0 8px 22px -10px var(--accent)" : "none",
            transition: "all .28s var(--ease-spring)"
          }}>
            {r.label}
            <span style={{ fontSize: 11, fontWeight: 700, padding: "1px 7px", borderRadius: 999, background: on ? "oklch(1 0 0 / 0.2)" : "var(--surface-hi)", color: on ? "white" : "var(--text-faint)" }} className="mono">{count}</span>
          </button>);

      })}
    </div>);

}

function StatPill({ icon: Ic, label, value, color }) {
  return (
    <div className="glass" style={{ flex: 1, borderRadius: 16, padding: "13px 15px", display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 38, height: 38, borderRadius: 11, display: "grid", placeItems: "center", background: `oklch(from ${color} l c h / 0.16)`, color, flexShrink: 0 }}>
        <Ic width="19" height="19" />
      </div>
      <div style={{ minWidth: 0 }}>
        <div className="display" style={{ fontSize: 20, fontWeight: 800, lineHeight: 1 }}>{value}</div>
        <div className="eyebrow" style={{ fontSize: 9, marginTop: 3 }}>{label}</div>
      </div>
    </div>);

}

function PlayerDashboard({ tweaks, onPick }) {
  const [round, setRound] = useState("groups");
  const matches = MATCHES[round] || [];
  const me = PLAYERS.find((p) => p.id === ME);
  const ranked = [...PLAYERS].filter((p) => p.active).sort((a, b) => b.pts - a.pts);
  const myRank = ranked.findIndex((p) => p.id === ME) + 1;
  const lbVariant = tweaks.leaderboard;

  return (
    <div style={{ display: "grid", gridTemplateColumns: lbVariant === "hidden" ? "1fr" : "1fr minmax(360px, 420px)", gap: 20, height: "100%", minHeight: 0 }}>
      {/* COLUMNA PRINCIPAL */}
      <div style={{ display: "flex", flexDirection: "column", gap: 18, minHeight: 0, overflowY: "auto", paddingRight: 4, paddingBottom: 8 }}>
        {/* hero stats */}
        <div className="rise" style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <div>
              <span className="eyebrow">MUNDIAL 2026</span>
              <h1 className="display" style={{ margin: "6px 0 0", fontSize: "clamp(24px, 2.4vw, 32px)", fontFamily: "Sora" }}>Hola, Sergio </h1>
            </div>
            <div style={{ display: "flex", alignItems: "center", gap: 8 }}>
              <span className="chip" style={{ color: "var(--c-gold)", borderColor: "oklch(from var(--c-gold) l c h / 0.4)", padding: "6px 12px" }}>
                <I.trophy width="13" height="13" /> Posición #{myRank}
              </span>
            </div>
          </div>
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <StatPill icon={I.trophy} label="Puntos" value={<AnimNum value={me.pts} />} color="var(--c-gold)" />
            <StatPill icon={I.ball} label="Aciertos" value={me.hits} color="var(--c-cyan)" />
            <StatPill icon={I.check} label="Exactos" value={me.exact} color="var(--c-lime)" />
            <StatPill icon={I.flame} label="Racha" value={me.streak} color="var(--c-yellow)" />
          </div>
        </div>

        {/* selector ronda */}
        <div className="rise" style={{ animationDelay: ".05s" }}>
          <RoundSelector active={round} onChange={setRound} />
        </div>

        {/* partidos agrupados por estado, ordenados por fecha */}
        {matches.length > 0 ?
        <div key={round} style={{ display: "flex", flexDirection: "column", gap: 24 }}>
            {MATCH_GROUPS.map((g) => {
              const list = matches.filter(g.test).sort((a, b) => a.kickoff - b.kickoff);
              if (!list.length) return null;
              return (
                <section key={g.key} className="rise">
                  <div style={{ display: "flex", alignItems: "center", gap: 10, marginBottom: 12 }}>
                    <span className="eyebrow" style={{ color: g.color }}>{g.label}</span>
                    <span className="mono" style={{ fontSize: 11, fontWeight: 700, padding: "1px 8px", borderRadius: 999, background: `oklch(from ${g.color} l c h / 0.14)`, color: g.color }}>{list.length}</span>
                    <span style={{ flex: 1, height: 1, background: "var(--border)" }} />
                  </div>
                  <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))", gap: 14 }} className="stagger">
                    {list.map((m) => <MatchCard key={m.id} m={m} onPick={onPick} />)}
                  </div>
                </section>
              );
            })}
          </div> :

        <div className="glass fade" style={{ borderRadius: 20, padding: "48px 24px", textAlign: "center", color: "var(--text-dim)" }}>
            <I.cal width="32" height="32" style={{ color: "var(--text-faint)", marginBottom: 12 }} />
            <p style={{ margin: 0, fontSize: 15 }}>Aún no hay partidos para <strong>{ROUNDS.find((r) => r.id === round).label}</strong>.</p>
            <p style={{ margin: "6px 0 0", fontSize: 13, color: "var(--text-faint)" }}>Se desbloquearán cuando avance la competición.</p>
          </div>
        }
      </div>

      {/* COLUMNA CLASIFICACIÓN */}
      {lbVariant !== "hidden" &&
      <aside className="glass rise" style={{ borderRadius: 24, padding: 18, display: "flex", flexDirection: "column", minHeight: 0, animationDelay: ".08s" }}>
          <Leaderboard variant={lbVariant} players={PLAYERS} />
        </aside>
      }
    </div>);

}

Object.assign(window, { PlayerDashboard, RoundSelector });