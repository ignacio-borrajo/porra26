/* manage.jsx — Pantallas de gestor: gestión de jugadores + introducción de resultados */

/* ===================== GESTIÓN DE JUGADORES ===================== */
function Toggle({ on, onClick }) {
  return (
    <button onClick={onClick} style={{
      width: 44, height: 25, borderRadius: 999, border: "none", cursor: "pointer", padding: 3,
      background: on ? "linear-gradient(135deg, var(--c-lime), var(--c-cyan))" : "var(--surface-hi)",
      boxShadow: on ? "0 0 14px -4px var(--c-lime)" : "inset 0 0 0 1px var(--border-hi)",
      transition: "background .3s", position: "relative",
    }}>
      <span style={{ display: "block", width: 19, height: 19, borderRadius: "50%", background: "white", transform: on ? "translateX(19px)" : "translateX(0)", transition: "transform .3s var(--ease-spring)", boxShadow: "0 2px 6px oklch(0 0 0 / 0.3)" }} />
    </button>
  );
}

function ManagePlayers({ players, setPlayers, onEdit }) {
  const [q, setQ] = useState("");
  const list = players.filter((p) => p.name.toLowerCase().includes(q.toLowerCase()) || p.email.toLowerCase().includes(q.toLowerCase()));
  const paidCount = players.filter((p) => p.paid).length;
  const activeCount = players.filter((p) => p.active).length;

  const togglePaid = (id) => setPlayers((ps) => ps.map((p) => p.id === id ? { ...p, paid: !p.paid } : p));
  const toggleActive = (id) => setPlayers((ps) => ps.map((p) => p.id === id ? { ...p, active: !p.active } : p));

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18, height: "100%", minHeight: 0 }}>
      <div className="rise" style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
        <div>
          <span className="eyebrow">Panel de gestor</span>
          <h1 className="display" style={{ margin: "6px 0 0", fontSize: "clamp(24px, 2.4vw, 32px)" }}>Jugadores</h1>
        </div>
        <div style={{ display: "flex", gap: 10, alignItems: "center" }}>
          <div style={{ display: "flex", gap: 8 }}>
            <span className="chip chip-open">{activeCount} activos</span>
            <span className="chip" style={{ color: paidCount === activeCount ? "var(--c-lime)" : "var(--c-yellow)", borderColor: "var(--border-hi)" }}><I.euro width="12" height="12" />{paidCount}/{players.length} pagado</span>
          </div>
          <button className="btn btn-primary" onClick={() => onEdit({})}><I.plus width="16" height="16" /> Nuevo jugador</button>
        </div>
      </div>

      <div className="rise" style={{ animationDelay: ".04s" }}>
        <div style={{ position: "relative", maxWidth: 360 }}>
          <I.users width="16" height="16" style={{ position: "absolute", left: 14, top: 13, color: "var(--text-faint)" }} />
          <input className="input" style={{ paddingLeft: 42 }} value={q} onChange={(e) => setQ(e.target.value)} placeholder="Buscar por nombre o correo…" />
        </div>
      </div>

      <div className="glass rise" style={{ borderRadius: 22, overflow: "hidden", display: "flex", flexDirection: "column", minHeight: 0, animationDelay: ".08s" }}>
        {/* cabecera */}
        <div style={{ display: "grid", gridTemplateColumns: "2.4fr 1fr 0.8fr 1fr 1.1fr 70px", gap: 12, padding: "14px 20px", borderBottom: "1px solid var(--border)", background: "var(--surface-hi)" }}>
          {["Jugador", "Departamento", "Puntos", "Pago", "Estado", ""].map((h) => <span key={h} className="eyebrow" style={{ fontSize: 9.5 }}>{h}</span>)}
        </div>
        <div style={{ overflowY: "auto", minHeight: 0 }} className="stagger">
          {list.map((p) => (
            <div key={p.id} style={{
              display: "grid", gridTemplateColumns: "2.4fr 1fr 0.8fr 1fr 1.1fr 70px", gap: 12, padding: "12px 20px", alignItems: "center",
              borderBottom: "1px solid var(--border)", opacity: p.active ? 1 : 0.5, transition: "opacity .3s, background .2s",
            }}
            onMouseEnter={(e) => e.currentTarget.style.background = "var(--surface-hi)"}
            onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              <div style={{ display: "flex", alignItems: "center", gap: 11, minWidth: 0 }}>
                <Avatar p={p} size={36} ring={p.id === ME} />
                <div style={{ minWidth: 0 }}>
                  <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
                    <span style={{ fontWeight: 600, fontSize: 14, overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.name.replace("Tú · ", "")}</span>
                    {p.role === "gestor" && <span className="chip" style={{ padding: "1px 6px", fontSize: 9, color: "var(--c-cyan)", borderColor: "oklch(from var(--c-cyan) l c h / 0.4)" }}>gestor</span>}
                  </div>
                  <div className="mono" style={{ fontSize: 11, color: "var(--text-faint)", overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>{p.email}</div>
                </div>
              </div>
              <span style={{ fontSize: 13, color: "var(--text-dim)" }}>{p.dept}</span>
              <span className="display mono" style={{ fontSize: 15, fontWeight: 800 }}>{p.pts}</span>
              <div style={{ display: "flex", alignItems: "center", gap: 9 }}>
                <Toggle on={p.paid} onClick={() => togglePaid(p.id)} />
                <span style={{ fontSize: 11.5, color: p.paid ? "var(--c-lime)" : "var(--text-faint)", fontWeight: 600 }}>{p.paid ? "Pagado" : "Pendiente"}</span>
              </div>
              <span className="chip" style={{ color: p.active ? "var(--c-lime)" : "var(--text-faint)", borderColor: p.active ? "oklch(from var(--c-lime) l c h / 0.4)" : "var(--border-hi)", background: p.active ? "oklch(from var(--c-lime) l c h / 0.08)" : "transparent" }}>
                <span className="dot" style={{ width: 6, height: 6 }} />{p.active ? "Activo" : "Baja"}
              </span>
              <div style={{ display: "flex", gap: 6, justifyContent: "flex-end" }}>
                <button className="btn btn-ghost" style={{ width: 34, height: 34, padding: 0, borderRadius: 10 }} title="Editar" onClick={() => onEdit(p)}><I.edit width="14" height="14" /></button>
                <button className="btn btn-ghost" style={{ width: 34, height: 34, padding: 0, borderRadius: 10, color: p.active ? "var(--c-red)" : "var(--c-lime)" }} title={p.active ? "Dar de baja" : "Reactivar"} onClick={() => toggleActive(p.id)}>
                  {p.active ? <I.x width="14" height="14" /> : <I.check width="14" height="14" />}
                </button>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}

/* ----- Modal de alta/edición de jugador ----- */
function PlayerModal({ player, onClose, onSave }) {
  const isNew = !player.id;
  const [form, setForm] = useState({ name: player.name?.replace("Tú · ", "") || "", email: player.email || "", dept: player.dept || "", role: player.role || "jugador", paid: player.paid || false });
  const set = (k, v) => setForm((f) => ({ ...f, [k]: v }));
  useEffect(() => {
    const onKey = (e) => e.key === "Escape" && onClose();
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, []);
  return (
    <div onClick={onClose} className="ovl" style={{ position: "fixed", inset: 0, zIndex: 60, display: "grid", placeItems: "center", padding: 20, background: "oklch(0.1 0.03 280 / 0.6)", backdropFilter: "blur(8px)", animation: "fade .25s ease both" }}>
      <div onClick={(e) => e.stopPropagation()} className="glass pop" style={{ width: "min(480px, 100%)", borderRadius: 28, padding: 28, background: "var(--surface-solid)" }}>
        <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: 20 }}>
          <div>
            <span className="eyebrow">{isNew ? "Alta" : "Editar"}</span>
            <h2 className="display" style={{ margin: "6px 0 0", fontSize: 22 }}>{isNew ? "Nuevo jugador" : form.name}</h2>
          </div>
          <button onClick={onClose} className="btn-ghost btn" style={{ width: 38, height: 38, padding: 0, borderRadius: 12 }}><I.x width="16" height="16" /></button>
        </div>
        <div style={{ display: "flex", flexDirection: "column", gap: 14 }}>
          <div className="field"><label>Nombre completo</label><input className="input" value={form.name} onChange={(e) => set("name", e.target.value)} placeholder="Nombre y apellidos" /></div>
          <div className="field"><label>Correo electrónico (usuario)</label><input className="input" type="email" value={form.email} onChange={(e) => set("email", e.target.value)} placeholder="nombre@empresa.com" /></div>
          <div style={{ display: "flex", gap: 12 }}>
            <div className="field" style={{ flex: 1 }}><label>Departamento</label><input className="input" value={form.dept} onChange={(e) => set("dept", e.target.value)} placeholder="Equipo" /></div>
            <div className="field" style={{ flex: 1 }}>
              <label>Rol</label>
              <div style={{ display: "flex", gap: 6, background: "var(--surface-hi)", padding: 4, borderRadius: 12, border: "1px solid var(--border-hi)" }}>
                {["jugador", "gestor"].map((r) => (
                  <button type="button" key={r} onClick={() => set("role", r)} style={{ flex: 1, padding: "9px", borderRadius: 9, border: "none", cursor: "pointer", textTransform: "capitalize", fontFamily: "var(--font-display)", fontWeight: 700, fontSize: 13, background: form.role === r ? "linear-gradient(135deg, var(--accent), var(--accent-2))" : "transparent", color: form.role === r ? "white" : "var(--text-dim)" }}>{r}</button>
                ))}
              </div>
            </div>
          </div>
          {isNew && <p className="mono" style={{ margin: 0, fontSize: 11.5, color: "var(--text-faint)", padding: "10px 12px", borderRadius: 10, background: "var(--surface-hi)" }}>Se generará una contraseña temporal que el jugador deberá cambiar. Sin recuperación automática: la restablece un gestor.</p>}
          <div style={{ display: "flex", alignItems: "center", gap: 10, padding: "10px 0" }}>
            <Toggle on={form.paid} onClick={() => set("paid", !form.paid)} />
            <span style={{ fontSize: 14, fontWeight: 600 }}>Ha realizado el pago del bote ({POT.perPlayer} €)</span>
          </div>
        </div>
        <div style={{ display: "flex", gap: 10, marginTop: 22 }}>
          <button className="btn btn-ghost" style={{ flex: 1 }} onClick={onClose}>Cancelar</button>
          <button className="btn btn-primary" style={{ flex: 2 }} onClick={() => onSave(form)}><I.check width="16" height="16" /> {isNew ? "Crear jugador" : "Guardar cambios"}</button>
        </div>
      </div>
    </div>
  );
}

/* ===================== INTRODUCIR RESULTADOS ===================== */
function ManageResults({ onOfficial }) {
  const [round, setRound] = useState("groups");
  const matches = MATCHES[round] || [];
  const pending = matches.filter((m) => m.status !== "done" && m.status !== "open");
  const done = matches.filter((m) => m.status === "done");
  const upcoming = matches.filter((m) => m.status === "open");

  const Row = ({ m }) => {
    const st = STATUS_LABEL[m.status];
    return (
      <div className="glass rise" style={{ borderRadius: 16, padding: "13px 16px", display: "grid", gridTemplateColumns: "auto 1fr auto auto", gap: 14, alignItems: "center" }}>
        <span className="eyebrow" style={{ width: 58 }}>{m.group.length <= 1 ? `Gr. ${m.group}` : m.group}</span>
        <div style={{ display: "flex", alignItems: "center", gap: 10, minWidth: 0 }}>
          <span style={{ fontSize: 22 }}>{TEAMS[m.home].flag}</span>
          <span className="display" style={{ fontSize: 14, fontWeight: 700 }}>{TEAMS[m.home].name}</span>
          {m.status === "done" ? (
            <span className="display mono" style={{ fontSize: 16, fontWeight: 800, padding: "2px 10px", borderRadius: 8, background: "var(--surface-hi)" }}>{m.result.h} : {m.result.a}</span>
          ) : m.status === "live" ? (
            <span className="display mono" style={{ fontSize: 16, fontWeight: 800, color: "var(--c-red)", padding: "2px 10px", borderRadius: 8, background: "oklch(from var(--c-red) l c h / 0.12)" }}>{m.liveScore.h} : {m.liveScore.a}</span>
          ) : (
            <span className="display" style={{ fontSize: 13, color: "var(--text-faint)" }}>vs</span>
          )}
          <span className="display" style={{ fontSize: 14, fontWeight: 700 }}>{TEAMS[m.away].name}</span>
          <span style={{ fontSize: 22 }}>{TEAMS[m.away].flag}</span>
        </div>
        <span className={`chip ${st.cls}`}>{(m.status === "live" || m.status === "closing") && <span className="dot dot-pulse" />}{st.text}</span>
        {m.status === "done" ? (
          <button className="btn btn-ghost" onClick={() => onOfficial(m)} style={{ padding: "8px 14px" }}><I.edit width="14" height="14" /> Editar</button>
        ) : (
          <button className="btn btn-primary" onClick={() => onOfficial(m)} style={{ padding: "8px 14px" }}><I.whistle width="14" height="14" /> Finalizar</button>
        )}
      </div>
    );
  };

  return (
    <div style={{ display: "flex", flexDirection: "column", gap: 18, height: "100%", minHeight: 0 }}>
      <div className="rise">
        <span className="eyebrow">Panel de gestor</span>
        <h1 className="display" style={{ margin: "6px 0 0", fontSize: "clamp(24px, 2.4vw, 32px)" }}>Resultados oficiales</h1>
        <p style={{ margin: "8px 0 0", color: "var(--text-dim)", fontSize: 14, maxWidth: 560 }}>Introduce el marcador final de cada partido para marcarlo como finalizado. Al confirmar, se recalculan los puntos de todos los jugadores.</p>
      </div>

      <div className="rise" style={{ animationDelay: ".04s" }}><RoundSelector active={round} onChange={setRound} /></div>

      <div style={{ overflowY: "auto", minHeight: 0, display: "flex", flexDirection: "column", gap: 18, paddingRight: 4, paddingBottom: 8 }}>
        {pending.length > 0 && (
          <section>
            <div style={{ display: "flex", alignItems: "center", gap: 8, marginBottom: 10 }}>
              <span className="dot dot-pulse" style={{ color: "var(--c-yellow)" }} />
              <h3 className="display" style={{ margin: 0, fontSize: 15 }}>Pendientes de finalizar <span style={{ color: "var(--text-faint)" }}>· {pending.length}</span></h3>
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }} className="stagger">{pending.map((m) => <Row key={m.id} m={m} />)}</div>
          </section>
        )}
        {upcoming.length > 0 && (
          <section>
            <h3 className="display" style={{ margin: "0 0 10px", fontSize: 15, color: "var(--text-dim)" }}>Próximos <span style={{ color: "var(--text-faint)" }}>· {upcoming.length}</span></h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }} className="stagger">{upcoming.map((m) => <Row key={m.id} m={m} />)}</div>
          </section>
        )}
        {done.length > 0 && (
          <section>
            <h3 className="display" style={{ margin: "0 0 10px", fontSize: 15, color: "var(--text-dim)" }}>Finalizados <span style={{ color: "var(--text-faint)" }}>· {done.length}</span></h3>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }} className="stagger">{done.map((m) => <Row key={m.id} m={m} />)}</div>
          </section>
        )}
      </div>
    </div>
  );
}

Object.assign(window, { ManagePlayers, PlayerModal, ManageResults, Toggle });
