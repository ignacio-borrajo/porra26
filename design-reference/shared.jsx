/* shared.jsx — primitivas reutilizables (iconos, avatar, banderas, cuenta atrás, leaderboard) */

const { useState, useEffect, useRef } = React;

/* ----------------- Iconos (trazo simple, no ilustración) ----------------- */
const I = {
  trophy: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M6 4h12v4a6 6 0 0 1-12 0V4Z"/><path d="M6 6H3v2a3 3 0 0 0 3 3M18 6h3v2a3 3 0 0 1-3 3"/><path d="M9 16h6M10 20h4M12 16v4"/></svg>,
  ball:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" {...p}><circle cx="12" cy="12" r="9"/><path d="m12 7 3 2.2-1.1 3.5h-3.8L9 9.2 12 7Z"/><path d="M12 7V3.2M14.9 9.2l3.4-1.3M13.9 12.7l2.2 3M10.1 12.7l-2.2 3M9 9.2 5.6 7.9"/></svg>,
  cal:    (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" {...p}><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/></svg>,
  clock:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></svg>,
  users:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M16 19v-1a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v1"/><circle cx="9" cy="7" r="3.2"/><path d="M22 19v-1a4 4 0 0 0-3-3.8M16 4.2A4 4 0 0 1 16 11"/></svg>,
  edit:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 20h9"/><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5Z"/></svg>,
  check:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m4 12 5 5L20 6"/></svg>,
  x:      (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" {...p}><path d="M6 6l12 12M18 6 6 18"/></svg>,
  lock:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" {...p}><rect x="4" y="10" width="16" height="11" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/></svg>,
  mail:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="5" width="18" height="14" rx="2"/><path d="m3 7 9 6 9-6"/></svg>,
  flame:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3s5 3.5 5 9a5 5 0 0 1-10 0c0-1.5.6-2.7 1.3-3.6C9 10 9.5 11 11 11c0-3 1-5 1-8Z"/></svg>,
  up:     (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m6 14 6-6 6 6"/></svg>,
  down:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="m6 10 6 6 6-6"/></svg>,
  euro:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M17 6a7 7 0 1 0 0 12M4 10h9M4 14h8"/></svg>,
  whistle:(p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 12a6 6 0 0 0 6 6h2l4 3v-5a6 6 0 0 0-2-11H8"/><circle cx="7.5" cy="12" r="1.4"/><path d="M14 4h6"/></svg>,
  plus:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" {...p}><path d="M12 5v14M5 12h14"/></svg>,
  logout: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M15 4h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2h-3M10 17l5-5-5-5M15 12H3"/></svg>,
  sun:    (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" {...p}><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>,
  moon:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M21 12.8A9 9 0 1 1 11.2 3a7 7 0 0 0 9.8 9.8Z"/></svg>,
  grid:   (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>,
  chart:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M3 3v16a2 2 0 0 0 2 2h16"/><path d="m7 14 3.5-4 3 2.5L20 6"/></svg>,
  target: (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><circle cx="12" cy="12" r="8.5"/><circle cx="12" cy="12" r="4.5"/><circle cx="12" cy="12" r="0.6" fill="currentColor"/></svg>,
  scale:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M12 3v18M5 7h14M7 7l-3 6a3 3 0 0 0 6 0L7 7Zm10 0-3 6a3 3 0 0 0 6 0l-3-6Z"/></svg>,
  gauge:  (p) => <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" {...p}><path d="M4 19a8 8 0 1 1 16 0"/><path d="m12 13 4-4"/></svg>,
};

/* ----------------- Avatar ----------------- */
function Avatar({ p, size = 38, ring }) {
  const hue = (p.id.charCodeAt(p.id.length - 1) * 47) % 360;
  return (
    <div style={{
      width: size, height: size, borderRadius: 12, flexShrink: 0,
      display: "grid", placeItems: "center",
      fontFamily: "var(--font-display)", fontWeight: 700,
      fontSize: size * 0.36, color: "white",
      background: `linear-gradient(135deg, oklch(0.62 0.19 ${hue}), oklch(0.66 0.2 ${(hue + 60) % 360}))`,
      boxShadow: ring ? "0 0 0 2px var(--accent), 0 0 14px -2px var(--accent)" : "0 2px 8px -2px oklch(0 0 0 / 0.4)",
    }}>{p.avatar}</div>
  );
}

/* ----------------- Cuenta atrás ----------------- */
function useNow(intervalMs = 1000) {
  const [, force] = useState(0);
  useEffect(() => {
    const t = setInterval(() => force((n) => n + 1), intervalMs);
    return () => clearInterval(t);
  }, [intervalMs]);
  return Date.now();
}

function Countdown({ to, prefix }) {
  const now = useNow(1000);
  let diff = Math.max(0, to - now);
  const h = Math.floor(diff / 3600000);
  const m = Math.floor((diff % 3600000) / 60000);
  const s = Math.floor((diff % 60000) / 1000);
  const pad = (n) => String(n).padStart(2, "0");
  const urgent = diff < 3600000;
  return (
    <span className="mono" style={{ color: urgent ? "var(--c-yellow)" : "var(--text-dim)", fontWeight: 600, letterSpacing: "0.02em" }}>
      {prefix}{h > 0 ? `${pad(h)}:` : ""}{pad(m)}:{pad(s)}
    </span>
  );
}

/* fecha legible */
function fmtDate(ts) {
  const d = new Date(ts);
  const dias = ["dom", "lun", "mar", "mié", "jue", "vie", "sáb"];
  const meses = ["ene", "feb", "mar", "abr", "may", "jun", "jul", "ago", "sep", "oct", "nov", "dic"];
  return `${dias[d.getDay()]} ${d.getDate()} ${meses[d.getMonth()]} · ${String(d.getHours()).padStart(2,"0")}:${String(d.getMinutes()).padStart(2,"0")}`;
}

/* ----------------- Animated number ----------------- */
function AnimNum({ value, dur = 900, suffix = "" }) {
  const [n, setN] = useState(0);
  const raf = useRef();
  useEffect(() => {
    const start = performance.now();
    const from = 0, to = value;
    const tick = (t) => {
      const k = Math.min(1, (t - start) / dur);
      const e = 1 - Math.pow(1 - k, 3);
      setN(Math.round(from + (to - from) * e));
      if (k < 1) raf.current = requestAnimationFrame(tick);
    };
    raf.current = requestAnimationFrame(tick);
    // red de seguridad: garantiza el valor final aunque rAF se pause en 2º plano
    const safety = setTimeout(() => setN(value), dur + 200);
    return () => { cancelAnimationFrame(raf.current); clearTimeout(safety); };
  }, [value]);
  return <>{n}{suffix}</>;
}

Object.assign(window, { I, Avatar, Countdown, useNow, fmtDate, AnimNum });
