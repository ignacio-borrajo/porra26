/* match.jsx — Tarjeta de partido + modal de pronóstico */

function TeamSide({ code, align, score }) {
  const t = TEAMS[code];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 7, flex: 1, minWidth: 0 }}>
      <div style={{ fontSize: 38, lineHeight: 1, filter: "drop-shadow(0 4px 8px oklch(0 0 0 / 0.25))" }}>{t.flag}</div>
      <div className="display" style={{ fontSize: 13, fontWeight: 700, textAlign: "center", letterSpacing: "-0.01em" }}>{t.name}</div>
    </div>
  );
}

function ScoreBubble({ value, dim }) {
  return (
    <div className="display mono" style={{
      minWidth: 38, height: 46, padding: "0 8px", borderRadius: 12,
      display: "grid", placeItems: "center", fontSize: 24, fontWeight: 800,
      background: dim ? "var(--surface-hi)" : "linear-gradient(135deg, oklch(from var(--accent) l c h / 0.22), oklch(from var(--accent-2) l c h / 0.12))",
      border: "1px solid var(--border-hi)", color: dim ? "var(--text-faint)" : "var(--text)",
    }}>{value ?? "–"}</div>
  );
}

function MatchCard({ m, onPick }) {
  const st = STATUS_LABEL[m.status];
  const editable = m.status === "open" || m.status === "closing";
  const hasPick = !!m.myPick;
  const now = useNow(1000);
  const closeAt = m.kickoff - 2 * 3600000; // cierre 2h antes

  return (
    <button
      onClick={() => editable && onPick(m)}
      className="glass rise"
      style={{
        textAlign: "left", border: "1px solid var(--border)", borderRadius: 20, padding: 16,
        cursor: editable ? "pointer" : "default", color: "var(--text)",
        display: "flex", flexDirection: "column", gap: 13, position: "relative", overflow: "hidden",
        transition: "transform .3s var(--ease-spring), box-shadow .3s, border-color .3s",
        outline: "none",
      }}
      onMouseEnter={(e) => { if (editable) { e.currentTarget.style.transform = "translateY(calc(-4px * var(--anim)))"; e.currentTarget.style.borderColor = "oklch(from var(--accent) l c h / 0.5)"; e.currentTarget.style.boxShadow = "0 22px 50px -22px var(--accent), var(--shadow-glow)"; } }}
      onMouseLeave={(e) => { e.currentTarget.style.transform = ""; e.currentTarget.style.borderColor = ""; e.currentTarget.style.boxShadow = ""; }}
    >
      {/* halo superior según estado */}
      {m.status === "live" && <div style={{ position: "absolute", inset: 0, background: "radial-gradient(120% 60% at 50% 0%, oklch(from var(--c-red) l c h / 0.16), transparent 60%)", pointerEvents: "none" }} />}

      {/* fila superior: grupo + estado */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        <span className="eyebrow">{m.group.length <= 1 ? `Grupo ${m.group}` : m.group}</span>
        <span className={`chip ${st.cls}`}>
          {m.status === "live" ? <span className="dot dot-pulse" /> : m.status === "closing" ? <span className="dot dot-pulse" /> : null}
          {st.text}
        </span>
      </div>

      {/* equipos + marcador */}
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <TeamSide code={m.home} align="right" />
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          {m.status === "done" ? (
            <><ScoreBubble value={m.result.h} /><span style={{ color: "var(--text-faint)", fontWeight: 700 }}>:</span><ScoreBubble value={m.result.a} /></>
          ) : m.status === "live" ? (
            <><ScoreBubble value={m.liveScore.h} /><span style={{ color: "var(--c-red)", fontWeight: 700 }}>:</span><ScoreBubble value={m.liveScore.a} /></>
          ) : (
            <span className="display" style={{ fontSize: 15, color: "var(--text-faint)", fontWeight: 700 }}>VS</span>
          )}
        </div>
        <TeamSide code={m.away} align="left" />
      </div>

      {/* pie: fecha / cierre / pronóstico */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, borderTop: "1px solid var(--border)", paddingTop: 12 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 11.5, color: "var(--text-dim)" }}>
          <I.cal width="13" height="13" style={{ color: "var(--text-faint)" }} />
          <span className="mono">{fmtDate(m.kickoff)}</span>
        </div>
      </div>

      {/* línea de acción */}
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8 }}>
        {m.status === "closing" ? (
          <div style={{ display: "flex", alignItems: "center", gap: 6, fontSize: 12 }}>
            <I.clock width="13" height="13" style={{ color: "var(--c-yellow)" }} />
            <Countdown to={closeAt} prefix="Cierra en " />
          </div>
        ) : m.status === "open" ? (
          <span style={{ fontSize: 12, color: "var(--text-faint)" }}>
            Cierra {fmtDate(closeAt).split("·")[1]}
          </span>
        ) : m.status === "done" ? (
          <span style={{ fontSize: 12, color: "var(--text-faint)" }}>Tu pronóstico {m.myPick ? `${m.myPick.h}-${m.myPick.a}` : "—"}</span>
        ) : (
          <span style={{ fontSize: 12, color: "var(--text-faint)" }}>Apuestas cerradas</span>
        )}

        {m.status === "done" ? (
          <span className="chip" style={{ color: m.earned >= m.pts ? "var(--c-lime)" : m.earned > 0 ? "var(--c-yellow)" : "var(--text-faint)", borderColor: m.earned > 0 ? "oklch(from var(--c-lime) l c h / 0.4)" : "var(--border-hi)" }}>
            {m.earned > 0 ? `+${m.earned} pts` : "0 pts"} {m.earned >= m.pts && "· exacto"}
          </span>
        ) : hasPick ? (
          <span className="chip chip-open" style={{ gap: 5 }}>
            <I.check width="11" height="11" /> Apostaste {m.myPick.h}-{m.myPick.a}
          </span>
        ) : editable ? (
          <span className="chip" style={{ color: "var(--accent)", borderColor: "oklch(from var(--accent) l c h / 0.5)", background: "oklch(from var(--accent) l c h / 0.1)" }}>
            <I.edit width="11" height="11" /> Pronosticar
          </span>
        ) : null}
      </div>
    </button>
  );
}

/* ----------------- Modal de pronóstico ----------------- */
function Stepper({ label, code, value, set }) {
  const t = TEAMS[code];
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 12, flex: 1 }}>
      <div style={{ fontSize: 46, lineHeight: 1 }}>{t.flag}</div>
      <div className="display" style={{ fontSize: 15, fontWeight: 700, textAlign: "center" }}>{t.name}</div>
      <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
        <button className="btn-ghost btn" style={{ width: 40, height: 40, padding: 0, borderRadius: 12 }} onClick={() => set(Math.max(0, value - 1))}>–</button>
        <div className="display mono" style={{ width: 64, height: 64, display: "grid", placeItems: "center", fontSize: 34, fontWeight: 800, borderRadius: 16, background: "linear-gradient(135deg, oklch(from var(--accent) l c h / 0.22), oklch(from var(--accent-2) l c h / 0.1))", border: "1px solid var(--border-hi)" }}>{value}</div>
        <button className="btn-ghost btn" style={{ width: 40, height: 40, padding: 0, borderRadius: 12 }} onClick={() => set(Math.min(20, value + 1))}>+</button>
      </div>
    </div>
  );
}

function ResultModal({ m, onClose, onSave, mode = "pick" }) {
  // mode: 'pick' (jugador apuesta) | 'official' (gestor mete resultado oficial)
  const init = mode === "official" ? (m.result || { h: 0, a: 0 }) : (m.myPick || { h: 0, a: 0 });
  const [h, setH] = useState(init.h);
  const [a, setA] = useState(init.a);
  const closeAt = m.kickoff - 2 * 3600000;
  const isOfficial = mode === "official";

  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);

  return (
    <div onClick={onClose} className="ovl" style={{ position: "fixed", inset: 0, zIndex: 60, display: "grid", placeItems: "center", padding: 20, background: "oklch(0.1 0.03 280 / 0.6)", backdropFilter: "blur(8px)", animation: "fade .25s ease both" }}>
      <div onClick={(e) => e.stopPropagation()} className="glass pop" style={{ width: "min(520px, 100%)", borderRadius: 28, padding: 28, position: "relative", background: "var(--surface-solid)" }}>
        <button onClick={onClose} className="btn-ghost btn" style={{ position: "absolute", top: 16, right: 16, width: 38, height: 38, padding: 0, borderRadius: 12 }}><I.x width="16" height="16" /></button>

        <div style={{ textAlign: "center", marginBottom: 6 }}>
          <span className="eyebrow">{isOfficial ? "Resultado oficial" : "Tu pronóstico"} · {m.group.length <= 1 ? `Grupo ${m.group}` : m.group}</span>
          <h2 className="display" style={{ margin: "8px 0 2px", fontSize: 22 }}>{isOfficial ? "Marcar resultado final" : "¿Cómo va a quedar?"}</h2>
          <p style={{ margin: 0, fontSize: 13, color: "var(--text-dim)" }}>{TEAMS[m.home].name} vs {TEAMS[m.away].name}</p>
        </div>

        <div style={{ display: "flex", alignItems: "flex-start", gap: 8, margin: "26px 0 22px" }}>
          <Stepper code={m.home} value={h} set={setH} />
          <div className="display" style={{ alignSelf: "center", fontSize: 24, color: "var(--text-faint)", paddingTop: 30 }}>:</div>
          <Stepper code={m.away} value={a} set={setA} />
        </div>

        {!isOfficial && (
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 8, marginBottom: 18, fontSize: 12.5, color: "var(--text-dim)" }}>
            <I.clock width="14" height="14" style={{ color: "var(--c-yellow)" }} />
            {m.status === "closing" ? <Countdown to={closeAt} prefix="Cierra en " /> : <span>Puedes editarlo hasta {fmtDate(closeAt)}</span>}
            <span className="chip" style={{ color: "var(--c-gold)", borderColor: "oklch(from var(--c-gold) l c h / 0.35)" }}>+{m.pts} pts</span>
          </div>
        )}

        <div style={{ display: "flex", gap: 10 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={() => onSave({ h, a })}>
            {isOfficial ? <><I.whistle width="16" height="16" /> Confirmar y finalizar</> : <><I.check width="16" height="16" /> Guardar pronóstico</>}
          </button>
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { MatchCard, ResultModal });
