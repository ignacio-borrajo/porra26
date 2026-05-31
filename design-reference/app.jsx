/* app.jsx — Shell: navegación, roles, tema, tweaks, toasts */

const TWEAK_DEFAULTS = /*EDITMODE-BEGIN*/{
  "theme": "dark",
  "accent": "blue",
  "loginVariant": "A",
  "leaderboard": "full",
  "anim": 10
}/*EDITMODE-END*/;

const ACCENTS = {
  blue:   ["var(--c-blue)",   "var(--c-cyan)"],
  pink:   ["var(--c-pink)",   "var(--c-cyan)"],
  cyan:   ["var(--c-cyan)",   "var(--c-lime)"],
  lime:   ["var(--c-lime)",   "var(--c-yellow)"],
  yellow: ["var(--c-yellow)", "var(--c-pink)"],
};

function Toast({ msg, onDone }) {
  useEffect(() => { const t = setTimeout(onDone, 2600); return () => clearTimeout(t); }, []);
  return (
    <div className="glass pop" style={{ position: "fixed", bottom: 24, left: "50%", transform: "translateX(-50%)", zIndex: 80, padding: "13px 20px", borderRadius: 16, display: "flex", alignItems: "center", gap: 10, background: "var(--surface-solid)", borderColor: "oklch(from var(--c-lime) l c h / 0.4)" }}>
      <span style={{ width: 26, height: 26, borderRadius: 8, background: "linear-gradient(135deg, var(--c-lime), var(--c-cyan))", display: "grid", placeItems: "center", color: "white" }}><I.check width="15" height="15" /></span>
      <span style={{ fontSize: 14, fontWeight: 600 }}>{msg}</span>
    </div>
  );
}

function NavItem({ active, icon: Ic, label, onClick }) {
  return (
    <button onClick={onClick} style={{
      display: "flex", alignItems: "center", gap: 10, padding: "10px 16px", borderRadius: 13, border: "none", cursor: "pointer",
      fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 14,
      background: active ? "var(--surface-hi)" : "transparent",
      color: active ? "var(--text)" : "var(--text-dim)",
      boxShadow: active ? "inset 0 0 0 1px var(--border-hi)" : "none",
      transition: "all .25s var(--ease-out)", position: "relative",
    }}>
      {active && <span style={{ position: "absolute", left: 0, top: "50%", transform: "translateY(-50%)", width: 3, height: 18, borderRadius: 3, background: "linear-gradient(var(--accent), var(--accent-2))" }} />}
      <Ic width="17" height="17" style={{ color: active ? "var(--accent)" : "currentColor" }} />
      {label}
    </button>
  );
}

function TopBar({ tweaks, setTweak, role, screen, setScreen, onLogout }) {
  const me = PLAYERS.find((p) => p.id === ME);
  const items = [
    { id: "competicion", label: "Competición", icon: I.ball, roles: ["jugador", "gestor"] },
    { id: "estadisticas", label: "Estadísticas", icon: I.chart, roles: ["jugador", "gestor"] },
    { id: "jugadores", label: "Jugadores", icon: I.users, roles: ["gestor"] },
    { id: "resultados", label: "Resultados", icon: I.whistle, roles: ["gestor"] },
  ].filter((i) => i.roles.includes(role));

  return (
    <header className="glass" style={{ borderRadius: 0, borderLeft: "none", borderRight: "none", borderTop: "none", padding: "12px clamp(16px, 3vw, 40px)", display: "flex", alignItems: "center", gap: 18, flexShrink: 0, zIndex: 20 }}>
      <div className="logo" style={{ fontSize: 17 }}>
        <span className="logo-mark" style={{ width: 30, height: 30, fontSize: 13 }}><span>26</span></span>
        PORRA<span className="grad-text">26</span>
      </div>

      <nav style={{ display: "flex", gap: 4, marginLeft: 12 }}>
        {items.map((it) => <NavItem key={it.id} active={screen === it.id} icon={it.icon} label={it.label} onClick={() => setScreen(it.id)} />)}
      </nav>

      <div style={{ marginLeft: "auto", display: "flex", alignItems: "center", gap: 12 }}>
        <span className="chip" style={{ color: "var(--c-gold)", borderColor: "oklch(from var(--c-gold) l c h / 0.35)", padding: "5px 11px" }}>
          <I.euro width="12" height="12" /> Bote {POT.total} €
        </span>
        <button className="btn btn-ghost" onClick={() => setTweak("theme", tweaks.theme === "dark" ? "light" : "dark")} style={{ width: 40, height: 40, padding: 0, borderRadius: 12 }} title="Cambiar tema">
          {tweaks.theme === "dark" ? <I.sun width="18" height="18" /> : <I.moon width="18" height="18" />}
        </button>
        <div style={{ display: "flex", alignItems: "center", gap: 9, paddingLeft: 6 }}>
          <Avatar p={me} size={36} ring />
          <div style={{ lineHeight: 1.2 }}>
            <div style={{ fontSize: 13, fontWeight: 700 }}>{me.name.replace("Tú · ", "")}</div>
            <div className="mono" style={{ fontSize: 10.5, color: "var(--text-faint)", textTransform: "capitalize" }}>{role}</div>
          </div>
          <button className="btn btn-ghost" onClick={onLogout} style={{ width: 38, height: 38, padding: 0, borderRadius: 11, marginLeft: 4 }} title="Salir"><I.logout width="16" height="16" /></button>
        </div>
      </div>
    </header>
  );
}

function App() {
  const [t, setTweak] = useTweaks(TWEAK_DEFAULTS);
  const [auth, setAuth] = useState(null);      // null | {role}
  const [screen, setScreen] = useState("competicion");
  const [players, setPlayers] = useState(PLAYERS);
  const [modal, setModal] = useState(null);    // {type:'pick'|'official'|'player', data}
  const [toast, setToast] = useState(null);

  // aplicar tema + acento + anim al :root
  useEffect(() => {
    const r = document.documentElement;
    r.setAttribute("data-theme", t.theme);
    const [a1, a2] = ACCENTS[t.accent] || ACCENTS.pink;
    r.style.setProperty("--accent", a1);
    r.style.setProperty("--accent-2", a2);
    r.style.setProperty("--anim", String((t.anim ?? 9) / 10));
  }, [t.theme, t.accent, t.anim]);

  // red de seguridad de visibilidad: re-anima al cambiar de pantalla y, pasado
  // un instante, garantiza el estado final visible aunque las animaciones se pausen.
  useEffect(() => {
    const r = document.documentElement;
    r.classList.remove("fv");
    const t = setTimeout(() => r.classList.add("fv"), 1800);
    return () => clearTimeout(t);
  }, [screen, auth ? auth.role : null]);

  const login = (role) => { setAuth({ role }); setScreen("competicion"); };
  const logout = () => setAuth(null);

  const savePick = (score) => {
    const m = modal.data;
    m.myPick = score; m.status = m.status === "open" ? "open" : m.status;
    setModal(null);
    setToast(`Pronóstico guardado · ${TEAMS[m.home].name} ${score.h}–${score.a} ${TEAMS[m.away].name}`);
  };
  const saveOfficial = (score) => {
    const m = modal.data;
    m.result = score; m.status = "done";
    if (m.myPick) m.earned = (m.myPick.h === score.h && m.myPick.a === score.a) ? m.pts : ((Math.sign(m.myPick.h - m.myPick.a) === Math.sign(score.h - score.a)) ? 1 : 0);
    setModal(null);
    setToast(`Resultado confirmado · ${TEAMS[m.home].name} ${score.h}–${score.a} ${TEAMS[m.away].name}`);
  };
  const savePlayer = (form) => {
    setModal(null);
    setToast(modal.data.id ? "Jugador actualizado" : "Jugador creado · contraseña temporal enviada");
  };

  return (
    <>
      <div className="ambient" />
      {!auth ? (
        <Login variant={t.loginVariant} onLogin={login} />
      ) : (
        <div style={{ position: "relative", zIndex: 1, height: "100vh", display: "flex", flexDirection: "column" }}>
          <TopBar tweaks={t} setTweak={setTweak} role={auth.role} screen={screen} setScreen={setScreen} onLogout={logout} />
          <main style={{ flex: 1, minHeight: 0, padding: "clamp(16px, 2.4vw, 32px) clamp(16px, 3vw, 40px)" }}>
            {screen === "competicion" && <PlayerDashboard tweaks={t} onPick={(m) => setModal({ type: "pick", data: m })} />}
            {screen === "estadisticas" && <StatsScreen />}
            {screen === "jugadores" && auth.role === "gestor" && <ManagePlayers players={players} setPlayers={setPlayers} onEdit={(p) => setModal({ type: "player", data: p })} />}
            {screen === "resultados" && auth.role === "gestor" && <ManageResults onOfficial={(m) => setModal({ type: "official", data: m })} />}
          </main>
        </div>
      )}

      {modal?.type === "pick" && <ResultModal m={modal.data} mode="pick" onClose={() => setModal(null)} onSave={savePick} />}
      {modal?.type === "official" && <ResultModal m={modal.data} mode="official" onClose={() => setModal(null)} onSave={saveOfficial} />}
      {modal?.type === "player" && <PlayerModal player={modal.data} onClose={() => setModal(null)} onSave={savePlayer} />}
      {toast && <Toast msg={toast} onDone={() => setToast(null)} />}
    </>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
