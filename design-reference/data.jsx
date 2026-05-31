/* data.jsx — Datos de demostración para PORRA 26
   Selecciones (banderas emoji), rondas, partidos y clasificación. */

const TEAMS = {
  ESP: { name: "España",     flag: "🇪🇸" },
  ARG: { name: "Argentina",  flag: "🇦🇷" },
  FRA: { name: "Francia",    flag: "🇫🇷" },
  BRA: { name: "Brasil",     flag: "🇧🇷" },
  ENG: { name: "Inglaterra", flag: "🏴\u{E0067}\u{E0062}\u{E0065}\u{E006E}\u{E0067}\u{E007F}" },
  POR: { name: "Portugal",   flag: "🇵🇹" },
  GER: { name: "Alemania",   flag: "🇩🇪" },
  NED: { name: "Países Bajos", flag: "🇳🇱" },
  MEX: { name: "México",     flag: "🇲🇽" },
  USA: { name: "EE. UU.",    flag: "🇺🇸" },
  CAN: { name: "Canadá",     flag: "🇨🇦" },
  JPN: { name: "Japón",      flag: "🇯🇵" },
  CRO: { name: "Croacia",    flag: "🇭🇷" },
  MAR: { name: "Marruecos",  flag: "🇲🇦" },
  URU: { name: "Uruguay",    flag: "🇺🇾" },
  BEL: { name: "Bélgica",    flag: "🇧🇪" },
};

const ROUNDS = [
  { id: "groups",  label: "Fase de grupos", short: "Grupos" },
  { id: "r32",     label: "Dieciseisavos",  short: "16avos" },
  { id: "r16",     label: "Octavos",        short: "Octavos" },
  { id: "qf",      label: "Cuartos",        short: "Cuartos" },
  { id: "sf",      label: "Semifinales",    short: "Semis" },
  { id: "final",   label: "Final",          short: "Final" },
];

/* status: 'open' (apuestas abiertas), 'closing' (<2h, cuenta atrás),
   'closed' (cerrado, sin resultado), 'live', 'done' */
function mins(n) { return Date.now() + n * 60000; }

const MATCHES = {
  groups: [
    { id: "g1", group: "A", home: "MEX", away: "CRO", kickoff: mins(220), status: "open",    pts: 3, myPick: null },
    { id: "g2", group: "B", home: "ESP", away: "JPN", kickoff: mins(95),  status: "closing", pts: 3, myPick: { h: 2, a: 1 } },
    { id: "g3", group: "C", home: "FRA", away: "CAN", kickoff: mins(40),  status: "closed",  pts: 3, myPick: { h: 3, a: 0 } },
    { id: "g4", group: "D", home: "ARG", away: "MAR", kickoff: mins(-25), status: "live",    pts: 3, myPick: { h: 1, a: 1 }, liveScore: { h: 1, a: 0 } },
    { id: "g5", group: "E", home: "BRA", away: "USA", kickoff: mins(-130),status: "done",    pts: 3, myPick: { h: 2, a: 2 }, result: { h: 2, a: 2 }, earned: 3 },
    { id: "g6", group: "F", home: "ENG", away: "URU", kickoff: mins(-220),status: "done",    pts: 3, myPick: { h: 1, a: 0 }, result: { h: 2, a: 0 }, earned: 1 },
    { id: "g7", group: "G", home: "POR", away: "BEL", kickoff: mins(380), status: "open",    pts: 3, myPick: null },
    { id: "g8", group: "H", home: "GER", away: "NED", kickoff: mins(460), status: "open",    pts: 3, myPick: null },
  ],
  r32: [
    { id: "k1", group: "16avos", home: "ESP", away: "URU", kickoff: mins(1500), status: "open", pts: 5, myPick: null },
    { id: "k2", group: "16avos", home: "FRA", away: "JPN", kickoff: mins(1600), status: "open", pts: 5, myPick: null },
    { id: "k3", group: "16avos", home: "ARG", away: "NED", kickoff: mins(1700), status: "open", pts: 5, myPick: null },
    { id: "k4", group: "16avos", home: "BRA", away: "CRO", kickoff: mins(1800), status: "open", pts: 5, myPick: null },
  ],
  r16: [
    { id: "o1", group: "Octavos", home: "ESP", away: "FRA", kickoff: mins(4200), status: "open", pts: 7, myPick: null },
    { id: "o2", group: "Octavos", home: "ARG", away: "BRA", kickoff: mins(4300), status: "open", pts: 7, myPick: null },
  ],
  qf: [
    { id: "c1", group: "Cuartos", home: "ESP", away: "ARG", kickoff: mins(7000), status: "open", pts: 10, myPick: null },
  ],
  sf: [],
  final: [],
};

const ME = "u_07";

const BASE_PLAYERS = [
  { id: "u_01", name: "Lucía Fernández", email: "lucia.fernandez@empresa.com", avatar: "LF", pts: 47, hits: 11, exact: 4, streak: 5, trend: "up",   paid: true,  active: true,  role: "jugador", dept: "Marketing" },
  { id: "u_02", name: "Marc Oller",      email: "marc.oller@empresa.com",      avatar: "MO", pts: 44, hits: 10, exact: 3, streak: 3, trend: "up",   paid: true,  active: true,  role: "gestor",  dept: "Producto" },
  { id: "u_03", name: "Aitana Ruiz",     email: "aitana.ruiz@empresa.com",     avatar: "AR", pts: 41, hits: 10, exact: 2, streak: 0, trend: "down", paid: true,  active: true,  role: "jugador", dept: "Ventas" },
  { id: "u_04", name: "Diego Santos",    email: "diego.santos@empresa.com",    avatar: "DS", pts: 39, hits: 9,  exact: 3, streak: 2, trend: "up",   paid: true,  active: true,  role: "jugador", dept: "Soporte" },
  { id: "u_05", name: "Nora Vidal",      email: "nora.vidal@empresa.com",      avatar: "NV", pts: 36, hits: 9,  exact: 1, streak: 1, trend: "flat", paid: true,  active: true,  role: "jugador", dept: "Finanzas" },
  { id: "u_06", name: "Pau Esteve",      email: "pau.esteve@empresa.com",      avatar: "PE", pts: 34, hits: 8,  exact: 2, streak: 0, trend: "down", paid: false, active: true,  role: "jugador", dept: "RRHH" },
  { id: "u_07", name: "Tú · Sergio Mas", email: "sergio.mas@empresa.com",      avatar: "SM", pts: 32, hits: 8,  exact: 1, streak: 2, trend: "up",   paid: true,  active: true,  role: "jugador", dept: "Ingeniería" },
  { id: "u_08", name: "Carla Bonet",     email: "carla.bonet@empresa.com",     avatar: "CB", pts: 30, hits: 7,  exact: 2, streak: 1, trend: "up",   paid: true,  active: true,  role: "jugador", dept: "Diseño" },
  { id: "u_09", name: "Iván Prieto",     email: "ivan.prieto@empresa.com",     avatar: "IP", pts: 27, hits: 7,  exact: 0, streak: 0, trend: "flat", paid: false, active: true,  role: "jugador", dept: "Ingeniería" },
  { id: "u_10", name: "Elena Caro",      email: "elena.caro@empresa.com",      avatar: "EC", pts: 24, hits: 6,  exact: 1, streak: 1, trend: "up",   paid: true,  active: true,  role: "jugador", dept: "Legal" },
  { id: "u_11", name: "Hugo Marín",      email: "hugo.marin@empresa.com",      avatar: "HM", pts: 21, hits: 5,  exact: 1, streak: 0, trend: "down", paid: true,  active: false, role: "jugador", dept: "Operaciones" },
  { id: "u_12", name: "Sara Lozano",     email: "sara.lozano@empresa.com",     avatar: "SL", pts: 18, hits: 5,  exact: 0, streak: 0, trend: "flat", paid: false, active: true,  role: "jugador", dept: "Marketing" },
];

/* Resto de la plantilla inscrita (48 en total) — generados para poblar la clasificación */
const _EXTRA_NAMES = [
  "Álvaro Gil", "Marta Sáez", "Rubén Díaz", "Noa Calvo", "Bruno Reyes", "Vera Ortega",
  "Adrián Moya", "Lola Crespo", "Gael Soler", "Irene Pardo", "Mateo Nieto", "Julia Roca",
  "Pablo Vega", "Claudia León", "Dario Romero", "Alba Gallego", "Nico Herrera", "Marina Ferrer",
  "Hugo Castro", "Daniela Mora", "Óscar Ibáñez", "Lucas Rivas", "Emma Suárez", "Pol Navarro",
  "Carmen Gómez", "Sergio Lara", "Aroa Méndez", "Teo Bravo", "Greta Aguilar", "Saúl Peña",
  "Lara Vázquez", "Ismael Cano", "Naia Garrido", "Beltrán Ramos", "Cloe Serrano", "Unai Mateos",
];
const _DEPTS = ["Ingeniería", "Marketing", "Ventas", "Producto", "Soporte", "Finanzas", "RRHH", "Diseño", "Legal", "Operaciones"];
const _TRENDS = ["up", "down", "flat"];
const PLAYERS = BASE_PLAYERS.concat(_EXTRA_NAMES.map((name, i) => {
  const pts = Math.max(0, 16 - i - (i % 3)); // descendente con algo de variación, todos por debajo de los nombrados
  const parts = name.split(" ");
  return {
    id: `u_${String(13 + i).padStart(2, "0")}`,
    name, email: `${parts[0].toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")}.${parts[1].toLowerCase().normalize("NFD").replace(/[\u0300-\u036f]/g, "")}@empresa.com`,
    avatar: parts.map((p) => p[0]).join("").slice(0, 2),
    pts, hits: Math.max(0, Math.round(pts / 3.6)), exact: Math.max(0, Math.round(pts / 11)),
    streak: i % 4 === 0 ? (i % 7) % 4 : 0, trend: _TRENDS[i % 3],
    paid: i % 5 !== 0, active: i % 11 !== 0, role: "jugador", dept: _DEPTS[i % _DEPTS.length],
  };
}));

const POT = { perPlayer: 10, players: 48, total: 480, prizes: [240, 144, 96] }; // €

const STATUS_LABEL = {
  open:    { text: "Abierto",   cls: "chip-open" },
  closing: { text: "Cierra pronto", cls: "chip-open" },
  closed:  { text: "Cerrado",   cls: "chip-closed" },
  live:    { text: "En juego",  cls: "chip-live" },
  done:    { text: "Finalizado",cls: "chip-done" },
};

/* =========================================================================
   HISTÓRICO — Evolución partido a partido
   La porra lleva FINISHED partidos disputados. Generamos, de forma
   determinista, la curva de puntos acumulados de cada jugador hasta su total
   actual y, a partir de ahí, su posición en la clasificación tras cada partido.
   El último punto coincide siempre con la clasificación real.
   ========================================================================= */
const FINISHED = 14; // partidos ya disputados y puntuados

/* PRNG determinista (LCG) sembrado por jugador → mismas curvas en cada carga */
function _seeded(seed) {
  let s = seed % 2147483647;
  if (s <= 0) s += 2147483646;
  return () => (s = (s * 16807) % 2147483647) / 2147483647;
}

function _buildHistory() {
  const active = PLAYERS.filter((p) => p.active);
  const ranked = [...active].sort((a, b) => b.pts - a.pts);
  const rankIndex = new Map(ranked.map((p, i) => [p.id, i])); // desempate estable

  // 1) Puntos acumulados por jugador en cada partido (monótono, termina en pts)
  const ptsHist = {};
  active.forEach((p) => {
    const seed = p.id.split("").reduce((a, c) => a + c.charCodeAt(0), 0) * 131 + p.pts * 7 + 1;
    const rnd = _seeded(seed);
    const w = Array.from({ length: FINISHED }, () => 0.15 + rnd() * 1.7); // volatilidad → cruces
    const sum = w.reduce((a, b) => a + b, 0);
    const arr = [];
    let cum = 0;
    for (let j = 0; j < FINISHED; j++) {
      cum += (w[j] / sum) * p.pts;
      arr.push(Math.min(p.pts, Math.round(cum)));
    }
    for (let j = 1; j < FINISHED; j++) if (arr[j] < arr[j - 1]) arr[j] = arr[j - 1];
    arr[FINISHED - 1] = p.pts; // el último coincide con el total real
    ptsHist[p.id] = arr;
  });

  // 2) Posición en cada partido (misma regla de orden que la clasificación)
  const rankHist = {};
  active.forEach((p) => (rankHist[p.id] = []));
  for (let j = 0; j < FINISHED; j++) {
    const order = [...active].sort((a, b) =>
      ptsHist[b.id][j] - ptsHist[a.id][j] || rankIndex.get(a.id) - rankIndex.get(b.id)
    );
    order.forEach((p, i) => rankHist[p.id].push(i + 1));
  }
  return { ptsHist, rankHist };
}

const { ptsHist: PTS_HIST, rankHist: RANK_HIST } = _buildHistory();

Object.assign(window, { TEAMS, ROUNDS, MATCHES, PLAYERS, ME, POT, STATUS_LABEL, mins, FINISHED, PTS_HIST, RANK_HIST });
