/* login.jsx — Pantalla de acceso. 2 variantes (Tweaks).
   Form a la izquierda, info de la competición a la derecha. */

function NextMatchMini({ m }) {
  const now = Date.now();
  const closeAt = m.kickoff - 2 * 3600000; // las apuestas cierran 2h antes
  const canBet = now < closeAt;
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 9, padding: "11px 13px", borderRadius: 14, background: "var(--surface-hi)", border: "1px solid var(--border)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 11 }}>
        <div style={{ fontSize: 22 }}>{TEAMS[m.home].flag}</div>
        <div style={{ flex: 1, minWidth: 0 }}>
          <div className="display" style={{ fontSize: 13, fontWeight: 700 }}>{TEAMS[m.home].name} <span style={{ color: "var(--text-faint)", fontWeight: 400 }}>vs</span> {TEAMS[m.away].name}</div>
          <div className="mono" style={{ fontSize: 11, color: "var(--text-dim)", marginTop: 2 }}>{fmtDate(m.kickoff)}</div>
        </div>
        <div style={{ fontSize: 22 }}>{TEAMS[m.away].flag}</div>
      </div>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", gap: 8, borderTop: "1px solid var(--border)", paddingTop: 8 }}>
        {canBet ? (
          <span className="chip chip-open" style={{ gap: 5, padding: "3px 9px" }}><I.clock width="11" height="11" /> Apuestas abiertas</span>
        ) : (
          <span className="chip chip-closed" style={{ padding: "3px 9px" }}>Apuestas cerradas</span>
        )}
        <span className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)", textAlign: "right" }}>
          {canBet ? <>Cierra {fmtDate(closeAt).split(" · ")[1] || fmtDate(closeAt)}</> : "Cerró"}
        </span>
      </div>
    </div>
  );
}

function LoginInfo() {
  const ranked = [...PLAYERS].filter((p) => p.active).sort((a, b) => b.pts - a.pts).slice(0, 5);
  const next = MATCHES.groups.filter((m) => m.kickoff > Date.now()).sort((a, b) => a.kickoff - b.kickoff).slice(0, 3);
  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 14, width: "100%", maxWidth: 440 }}>
      {/* tira del bote */}
      <div style={{ display: "flex", gap: 10 }}>
        {[["Bote", `${POT.total} €`], ["Jugadores", POT.players], ["1er premio", `${POT.prizes[0]} €`]].map(([k, v]) => (
          <div key={k} style={{ flex: 1, padding: "12px 10px", borderRadius: 14, background: "var(--surface-hi)", border: "1px solid var(--border)", textAlign: "center" }}>
            <div className="display grad-text" style={{ fontSize: 19, fontWeight: 800 }}>{v}</div>
            <div className="eyebrow" style={{ fontSize: 9, marginTop: 2 }}>{k}</div>
          </div>
        ))}
      </div>

      {/* card · próximos partidos */}
      <div className="glass" style={{ borderRadius: 20, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 12 }}>
          <I.cal width="15" height="15" style={{ color: "var(--accent)" }} />
          <span className="eyebrow">Próximos partidos</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 8 }} className="stagger">
          {next.map((m) => <NextMatchMini key={m.id} m={m} />)}
        </div>
      </div>

      {/* card · clasificación */}
      <div className="glass" style={{ borderRadius: 20, padding: 16 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
          <I.trophy width="15" height="15" style={{ color: "var(--c-gold)" }} />
          <span className="eyebrow">Top 5 · clasificación</span>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 4 }} className="stagger">
          {ranked.map((p, i) => (
            <div key={p.id} style={{ display: "grid", gridTemplateColumns: "20px 1fr auto", alignItems: "center", gap: 10, padding: "7px 10px", borderRadius: 12, background: i === 0 ? "oklch(from var(--c-gold) l c h / 0.1)" : "transparent", border: i === 0 ? "1px solid oklch(from var(--c-gold) l c h / 0.3)" : "1px solid transparent" }}>
              <span className="mono" style={{ fontSize: 12, fontWeight: 700, color: i < 3 ? "var(--c-gold)" : "var(--text-faint)", textAlign: "center" }}>{i + 1}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 9, minWidth: 0 }}>
                <Avatar p={p} size={28} />
                <span style={{ fontSize: 13, fontWeight: 600, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name.replace("Tú · ", "")}</span>
              </div>
              <span className="display mono" style={{ fontSize: 14, fontWeight: 800 }}>{p.pts}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

function LoginForm({ onLogin, sub }) {
  const [email, setEmail] = useState("sergio.mas@empresa.com");
  const [pwd, setPwd] = useState("mundial26");
  const [role, setRole] = useState("jugador");
  const [busy, setBusy] = useState(false);
  const submit = (e) => {
    e.preventDefault();
    setBusy(true);
    setTimeout(() => onLogin(role), 650);
  };
  return (
    <form onSubmit={submit} style={{ display: "flex", flexDirection: "column", gap: 18, width: "100%", maxWidth: 380 }}>
      <div>
        <h1 className="display" style={{ margin: 0, fontSize: 30, letterSpacing: "-0.03em" }}>Bienvenido de nuevo</h1>
        <p style={{ margin: "8px 0 0", color: "var(--text-dim)", fontSize: 14 }}>{sub || "Accede con tu correo de empresa para jugar la porra."}</p>
      </div>

      <div className="field">
        <label>Correo electrónico</label>
        <div style={{ position: "relative" }}>
          <I.mail width="17" height="17" style={{ position: "absolute", left: 14, top: 14, color: "var(--text-faint)" }} />
          <input className="input" style={{ paddingLeft: 42 }} type="email" value={email} onChange={(e) => setEmail(e.target.value)} placeholder="nombre@empresa.com" required />
        </div>
      </div>
      <div className="field">
        <label>Contraseña</label>
        <div style={{ position: "relative" }}>
          <I.lock width="17" height="17" style={{ position: "absolute", left: 14, top: 14, color: "var(--text-faint)" }} />
          <input className="input" style={{ paddingLeft: 42 }} type="password" value={pwd} onChange={(e) => setPwd(e.target.value)} placeholder="••••••••" required />
        </div>
      </div>

      {/* selector de rol (demo) */}
      <div className="field">
        <label>Entrar como <span style={{ color: "var(--text-faint)", fontWeight: 400 }}>· demo</span></label>
        <div style={{ display: "flex", gap: 8, background: "var(--surface-hi)", padding: 4, borderRadius: 12, border: "1px solid var(--border-hi)" }}>
          {[["jugador", "Jugador", I.ball], ["gestor", "Gestor", I.whistle]].map(([id, label, Ic]) => (
            <button type="button" key={id} onClick={() => setRole(id)} style={{
              flex: 1, padding: "9px 10px", borderRadius: 9, border: "none", cursor: "pointer",
              fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13,
              display: "flex", alignItems: "center", justifyContent: "center", gap: 7,
              background: role === id ? "linear-gradient(135deg, var(--accent), var(--accent-2))" : "transparent",
              color: role === id ? "white" : "var(--text-dim)",
              boxShadow: role === id ? "0 6px 18px -8px var(--accent)" : "none",
              transition: "all .25s var(--ease-out)",
            }}><Ic width="15" height="15" />{label}</button>
          ))}
        </div>
      </div>

      <button className="btn btn-primary" type="submit" style={{ padding: "14px", fontSize: 15.5, opacity: busy ? 0.8 : 1 }}>
        {busy ? "Entrando…" : <>Entrar al torneo <I.ball width="17" height="17" /></>}
      </button>
      <p style={{ margin: 0, fontSize: 12, color: "var(--text-faint)", textAlign: "center", lineHeight: 1.5 }}>
        ¿Olvidaste tu contraseña? Pídele a un administrador que la restablezca.
      </p>
    </form>
  );
}

function Login({ variant, onLogin }) {
  const Brand = (
    <div className="logo" style={{ fontSize: 20 }}>
      <span className="logo-mark"><span>26</span></span>
      PORRA<span className="grad-text">26</span>
    </div>
  );

  if (variant === "B") {
    /* Variante B — inmersiva: hero a la derecha con foco en el bote y podio, form a la izquierda sobre panel sólido */
    return (
      <div style={{ position: "relative", zIndex: 1, height: "100vh", display: "grid", gridTemplateColumns: "minmax(420px, 0.85fr) 1.15fr" }}>
        <div className="fade" style={{ display: "flex", flexDirection: "column", padding: "clamp(28px, 4vw, 60px)", background: "var(--surface-solid)", borderRight: "1px solid var(--border)", overflowY: "auto" }}>
          <div style={{ marginBottom: "auto" }}>{Brand}</div>
          <div style={{ margin: "auto 0", display: "flex", justifyContent: "center" }}><LoginForm onLogin={onLogin} sub="La porra del Mundial 2026 de la empresa. Pronostica, suma puntos y llévate el bote." /></div>
          <div style={{ marginTop: "auto", fontSize: 11, color: "var(--text-faint)" }} className="mono">Mundial FIFA 2026 · Edición interna</div>
        </div>
        <div style={{ position: "relative", display: "flex", flexDirection: "column", justifyContent: "center", alignItems: "center", padding: "clamp(28px, 4vw, 60px)", gap: 30, overflow: "hidden" }}>
          <div style={{ textAlign: "center", maxWidth: 460 }} className="rise">
            <div className="eyebrow">11 jun – 19 jul · USA · México · Canadá</div>
            <h2 className="display" style={{ fontSize: "clamp(34px, 4vw, 52px)", margin: "12px 0 0", lineHeight: 1.02 }}>
              Pronostica.<br /><span className="grad-text">Suma puntos.</span><br />Gana el bote.
            </h2>
          </div>
          <div className="pop" style={{ width: "min(460px, 100%)", maxHeight: "82vh", overflowY: "auto", padding: "2px 4px" }}>
            <LoginInfo />
          </div>
        </div>
      </div>
    );
  }

  /* Variante A — split clásico: form izquierda sobre glass, info derecha */
  return (
    <div style={{ position: "relative", zIndex: 1, height: "100vh", display: "flex", flexDirection: "column", padding: "clamp(24px, 4vw, 56px)" }}>
      <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between" }}>
        {Brand}
        <span className="chip">Edición interna · Mundial 2026</span>
      </div>
      <div style={{ flex: 1, minHeight: 0, display: "grid", gridTemplateColumns: "minmax(0, 0.9fr) minmax(0, 1.1fr)", gap: "clamp(30px, 5vw, 72px)", alignItems: "center" }}>
        <div className="glass rise" style={{ borderRadius: 28, padding: "clamp(28px, 3vw, 44px)", justifySelf: "center", width: "100%", maxWidth: 460 }}>
          <LoginForm onLogin={onLogin} />
        </div>
        <div className="rise" style={{ justifySelf: "center", animationDelay: ".1s", width: "100%", maxWidth: 440, maxHeight: "78vh", overflowY: "auto", paddingRight: 2 }}>
          <div style={{ marginBottom: 16 }}>
            <h2 className="display" style={{ fontSize: "clamp(24px, 2.4vw, 32px)", margin: 0, lineHeight: 1.05 }}>El torneo <span className="grad-text">ya está en juego</span></h2>
          </div>
          <LoginInfo />
        </div>
      </div>
    </div>
  );
}

Object.assign(window, { Login });
