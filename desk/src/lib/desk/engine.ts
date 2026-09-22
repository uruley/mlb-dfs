export type Slot = "P" | "C" | "1B" | "2B" | "3B" | "SS" | "OF";

export const ROSTER: Slot[] = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"];

export const HITTER_SLOTS: Slot[] = ["C", "SS", "2B", "3B", "1B", "OF", "OF", "OF"];

export type EventKey = "k" | "bb" | "hbp" | "s1" | "s2" | "s3" | "hr" | "out";

export type Hand = "L" | "R" | "S";

export interface Rates {
  k: number;
  bb: number;
  hbp: number;
  s1: number;
  s2: number;
  s3: number;
  hr: number;
  sample: number;
}

export interface Dist {
  k: number;
  bb: number;
  hbp: number;
  s1: number;
  s2: number;
  s3: number;
  hr: number;
  out: number;
  cuts: number[];
}

const EVENT_POINTS: Record<EventKey, number> = {
  k: 0,
  out: 0,
  bb: 2,
  hbp: 2,
  s1: 3,
  s2: 5,
  s3: 8,
  hr: 10,
};

const RATE_KEYS = ["k", "bb", "hbp", "s1", "s2", "s3", "hr"] as const;

export function clamp(n: number, lo: number, hi: number) {
  return Math.min(hi, Math.max(lo, n));
}

export function round100(n: number) {
  return Math.round(n / 100) * 100;
}

/** Bill James Log5. Identity holds when batter, pitcher, and league match. */
export function log5(b: number, p: number, l: number): number {
  if (!(l > 0.000001) || l >= 0.999) return clamp(l, 0, 0.95);
  const num = (b * p) / l;
  const den = num + ((1 - b) * (1 - p)) / (1 - l);
  if (!(den > 0) || !Number.isFinite(den)) return clamp(l, 0, 0.95);
  return clamp(num / den, 0, 0.95);
}

export function emptyRates(): Rates {
  return { k: 0, bb: 0, hbp: 0, s1: 0, s2: 0, s3: 0, hr: 0, sample: 0 };
}

export function ratesFromCounting(
  c: { pa: number; k: number; bb: number; hbp: number; h: number; d: number; t: number; hr: number },
): Rates {
  const pa = Math.max(0, c.pa);
  if (pa < 1) return emptyRates();
  const singles = Math.max(0, c.h - c.d - c.t - c.hr);
  return {
    k: c.k / pa,
    bb: c.bb / pa,
    hbp: c.hbp / pa,
    s1: singles / pa,
    s2: Math.max(0, c.d) / pa,
    s3: Math.max(0, c.t) / pa,
    hr: Math.max(0, c.hr) / pa,
    sample: pa,
  };
}

export function regress(raw: Rates, league: Rates, prior: number): Rates {
  const n = Math.max(0, raw.sample);
  const w = n / (n + prior);
  const mix = (a: number, b: number) => w * a + (1 - w) * b;
  return {
    k: mix(raw.k, league.k),
    bb: mix(raw.bb, league.bb),
    hbp: mix(raw.hbp, league.hbp),
    s1: mix(raw.s1, league.s1),
    s2: mix(raw.s2, league.s2),
    s3: mix(raw.s3, league.s3),
    hr: mix(raw.hr, league.hr),
    sample: n,
  };
}

function pack(partial: Omit<Dist, "out" | "cuts">): Dist {
  let parts = RATE_KEYS.map((k) => Math.max(0, partial[k]));
  let sum = parts.reduce((a, b) => a + b, 0);
  if (sum > 0.93) {
    const s = 0.93 / sum;
    parts = parts.map((v) => v * s);
    sum = 0.93;
  }
  const [k, bb, hbp, s1, s2, s3, hr] = parts;
  const c0 = k;
  const c1 = c0 + bb;
  const c2 = c1 + hbp;
  const c3 = c2 + s1;
  const c4 = c3 + s2;
  const c5 = c4 + s3;
  const c6 = c5 + hr;
  return { k, bb, hbp, s1, s2, s3, hr, out: 1 - sum, cuts: [c0, c1, c2, c3, c4, c5, c6] };
}

export function matchupDist(batter: Rates, pitcher: Rates, league: Rates): Dist {
  const raw = {
    k: log5(batter.k, pitcher.k, league.k),
    bb: log5(batter.bb, pitcher.bb, league.bb),
    hbp: log5(batter.hbp, pitcher.hbp, league.hbp),
    s1: log5(batter.s1, pitcher.s1, league.s1),
    s2: log5(batter.s2, pitcher.s2, league.s2),
    s3: log5(batter.s3, pitcher.s3, league.s3),
    hr: log5(batter.hr, pitcher.hr, league.hr),
  };
  return pack(raw);
}

export function applyPlatoon(dist: Dist, batter: Hand, pitcher: Hand): Dist {
  if (pitcher === "S") return dist;
  const opposite = batter === "S" || batter !== pitcher;
  const hitMul = opposite ? 1.05 : 0.95;
  const kMul = opposite ? 0.97 : 1.04;
  return pack({
    k: dist.k * kMul,
    bb: dist.bb,
    hbp: dist.hbp,
    s1: dist.s1 * hitMul,
    s2: dist.s2 * hitMul,
    s3: dist.s3 * hitMul,
    hr: dist.hr * hitMul,
  });
}

export function pickEvent(cuts: number[], u: number): EventKey {
  if (u < cuts[0]) return "k";
  if (u < cuts[1]) return "bb";
  if (u < cuts[2]) return "hbp";
  if (u < cuts[3]) return "s1";
  if (u < cuts[4]) return "s2";
  if (u < cuts[5]) return "s3";
  if (u < cuts[6]) return "hr";
  return "out";
}

export function mulberry32(seed: number) {
  let a = seed >>> 0;
  return function rng() {
    a |= 0;
    a = (a + 0x6d2b79f5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** 24 half-inning states: outs 0–2 × 8 base masks (bit0 = 1B, bit1 = 2B, bit2 = 3B). */
export function advance(mask: number, outs: number, ev: EventKey): { mask: number; outs: number; runs: number } {
  if (ev === "k" || ev === "out") return { mask, outs: outs + 1, runs: 0 };
  if (ev === "hr") {
    const runners = (mask & 1 ? 1 : 0) + (mask & 2 ? 1 : 0) + (mask & 4 ? 1 : 0);
    return { mask: 0, outs, runs: runners + 1 };
  }
  if (ev === "s3") {
    const runners = (mask & 1 ? 1 : 0) + (mask & 2 ? 1 : 0) + (mask & 4 ? 1 : 0);
    return { mask: 4, outs, runs: runners };
  }
  if (ev === "s2") {
    const runners = (mask & 1 ? 1 : 0) + (mask & 2 ? 1 : 0) + (mask & 4 ? 1 : 0);
    return { mask: 2, outs, runs: runners };
  }
  if (ev === "s1") {
    let runs = 0;
    if (mask & 2) runs += 1;
    if (mask & 4) runs += 1;
    const next = 1 | (mask & 1 ? 2 : 0);
    return { mask: next, outs, runs };
  }
  let runs = 0;
  let m = mask;
  if (m & 1) {
    if (m & 2) {
      if (m & 4) runs += 1;
      m = 7;
    } else {
      m = (m & 4) | 3;
    }
  } else {
    m = m | 1;
  }
  return { mask: m, outs, runs };
}

export function runExpectancy(dist: Dist): number[] {
  const p = [dist.k, dist.bb, dist.hbp, dist.s1, dist.s2, dist.s3, dist.hr, dist.out];
  const evs: EventKey[] = ["k", "bb", "hbp", "s1", "s2", "s3", "hr", "out"];
  const n = 24;
  const a: number[][] = Array.from({ length: n }, () => Array(n + 1).fill(0));
  for (let s = 0; s < n; s++) {
    a[s][s] = 1;
    const outs = (s / 8) | 0;
    const mask = s % 8;
    for (let e = 0; e < 8; e++) {
      const next = advance(mask, outs, evs[e]);
      a[s][n] += p[e] * next.runs;
      if (next.outs < 3) a[s][next.outs * 8 + next.mask] -= p[e];
    }
  }
  for (let col = 0; col < n; col++) {
    let pivot = col;
    for (let r = col + 1; r < n; r++) if (Math.abs(a[r][col]) > Math.abs(a[pivot][col])) pivot = r;
    if (Math.abs(a[pivot][col]) < 1e-12) continue;
    if (pivot !== col) {
      const tmp = a[col];
      a[col] = a[pivot];
      a[pivot] = tmp;
    }
    const div = a[col][col];
    for (let c = col; c <= n; c++) a[col][c] /= div;
    for (let r = 0; r < n; r++) {
      if (r === col) continue;
      const f = a[r][col];
      if (f === 0) continue;
      for (let c = col; c <= n; c++) a[r][c] -= f * a[col][c];
    }
  }
  return a.map((row) => row[n]);
}

export const BASE_LABELS = ["—", "1B", "2B", "1·2", "3B", "1·3", "2·3", "Ld"];

export interface SimHitter {
  id: number;
  name: string;
  team: string;
  opp: string;
  gameId: number;
  slots: Slot[];
  order: number;
  rates: Rates;
  sb: number;
  hand: Hand;
}

export interface SimArm {
  id: number;
  name: string;
  team: string;
  opp: string;
  gameId: number;
  rates: Rates;
  hand: Hand;
  targetBf: number;
  role: "starter" | "opener" | "bulk" | "short";
  ipPerStart: number | null;
  workloadSource: string;
}

export interface SimGame {
  id: number;
  label: string;
  away: string;
  home: string;
  start: string;
  venue: string;
  weather: string;
  status: string;
  awayOrder: number;
  homeOrder: number;
  awayHitters: SimHitter[];
  homeHitters: SimHitter[];
  awayArm: SimArm | null;
  homeArm: SimArm | null;
}

interface ReadyHitter {
  id: number;
  vsArm: Dist;
  vsPen: Dist;
  sb: number;
}

interface Book {
  add: (id: number, sim: number, pts: number) => void;
}

function makeBook(ids: number[], n: number) {
  const map = new Map<number, Float32Array>();
  for (const id of ids) if (id > 0 && !map.has(id)) map.set(id, new Float32Array(n));
  const book: Book = {
    add(id, sim, pts) {
      if (id <= 0 || pts === 0) return;
      const row = map.get(id);
      if (row) row[sim] += pts;
    },
  };
  return { map, book };
}

function readyHitters(hitters: SimHitter[], arm: SimArm | null, league: Rates): ReadyHitter[] {
  const source = hitters.length
    ? hitters
    : Array.from({ length: 9 }, () => ({
        id: -1,
        rates: league,
        sb: 0.04,
        hand: "R" as Hand,
      }));
  return source.map((h) => {
    const vsPen = applyPlatoon(matchupDist(h.rates, league, league), h.hand, "R");
    const vsArm = arm
      ? applyPlatoon(matchupDist(h.rates, arm.rates, league), h.hand, arm.hand)
      : vsPen;
    return { id: h.id, vsArm, vsPen, sb: h.sb };
  });
}

interface ArmState {
  id: number;
  targetBf: number;
  bf: number;
  outs: number;
  er: number;
  hits: number;
  active: boolean;
  exited: boolean;
  runsForAtExit: number;
  runsAgainstAtExit: number;
}

function freshArm(arm: SimArm | null): ArmState {
  return {
    id: arm?.id ?? 0,
    targetBf: arm?.targetBf ?? 22,
    bf: 0,
    outs: 0,
    er: 0,
    hits: 0,
    active: !!arm,
    exited: !arm,
    runsForAtExit: 0,
    runsAgainstAtExit: 0,
  };
}

function simHalf(
  hitters: ReadyHitter[],
  ptr: { i: number },
  arm: ArmState,
  book: Book,
  sim: number,
  rng: () => number,
  scoreFor: () => number,
  scoreAgainst: () => number,
  addRuns: (n: number) => void,
): number {
  let b0 = 0;
  let b1 = 0;
  let b2 = 0;
  let outs = 0;
  let scored = 0;
  let pa = 0;
  const lineup = hitters.length ? hitters : [];
  if (!lineup.length) return 0;
  while (outs < 3 && pa < 48) {
    pa += 1;
    const h = lineup[ptr.i % lineup.length];
    ptr.i += 1;
    const dist = arm.active ? h.vsArm : h.vsPen;
    const ev = pickEvent(dist.cuts, rng());
    const id = h.id;
    if (arm.active) {
      arm.bf += 1;
      if (ev === "k") {
        book.add(arm.id, sim, 2.75);
        arm.outs += 1;
      } else if (ev === "out") {
        book.add(arm.id, sim, 0.75);
        arm.outs += 1;
      } else if (ev === "bb" || ev === "hbp") {
        book.add(arm.id, sim, -0.6);
      } else {
        book.add(arm.id, sim, -0.6);
        arm.hits += 1;
      }
    }
    let rbi = 0;
    if (ev === "k" || ev === "out") {
      outs += 1;
    } else if (ev === "hr") {
      if (b0) {
        book.add(b0, sim, 2);
        rbi += 1;
      }
      if (b1) {
        book.add(b1, sim, 2);
        rbi += 1;
      }
      if (b2) {
        book.add(b2, sim, 2);
        rbi += 1;
      }
      book.add(id, sim, 2);
      rbi += 1;
      book.add(id, sim, EVENT_POINTS.hr + rbi * 2);
      b0 = 0;
      b1 = 0;
      b2 = 0;
    } else if (ev === "s3") {
      if (b0) {
        book.add(b0, sim, 2);
        rbi += 1;
      }
      if (b1) {
        book.add(b1, sim, 2);
        rbi += 1;
      }
      if (b2) {
        book.add(b2, sim, 2);
        rbi += 1;
      }
      book.add(id, sim, EVENT_POINTS.s3 + rbi * 2);
      b0 = 0;
      b1 = 0;
      b2 = id;
    } else if (ev === "s2") {
      if (b0) {
        book.add(b0, sim, 2);
        rbi += 1;
      }
      if (b1) {
        book.add(b1, sim, 2);
        rbi += 1;
      }
      if (b2) {
        book.add(b2, sim, 2);
        rbi += 1;
      }
      book.add(id, sim, EVENT_POINTS.s2 + rbi * 2);
      b0 = 0;
      b1 = id;
      b2 = 0;
    } else if (ev === "s1") {
      if (b2) {
        book.add(b2, sim, 2);
        rbi += 1;
      }
      if (b1) {
        book.add(b1, sim, 2);
        rbi += 1;
      }
      const r1 = b0;
      b0 = id;
      b1 = r1;
      b2 = 0;
      book.add(id, sim, EVENT_POINTS.s1 + rbi * 2);
      if (b0 === id && b1 === 0 && outs < 2 && rng() < h.sb) {
        b1 = id;
        b0 = 0;
        book.add(id, sim, 5);
      }
    } else {
      if (b0) {
        if (b1) {
          if (b2) {
            book.add(b2, sim, 2);
            rbi += 1;
          }
          b2 = b1;
          b1 = b0;
          b0 = id;
        } else {
          b1 = b0;
          b0 = id;
        }
      } else {
        b0 = id;
      }
      book.add(id, sim, EVENT_POINTS[ev] + rbi * 2);
      if (b0 === id && b1 === 0 && outs < 2 && rng() < h.sb) {
        b1 = id;
        b0 = 0;
        book.add(id, sim, 5);
      }
    }
    if (rbi && arm.active) {
      arm.er += rbi;
      book.add(arm.id, sim, -2 * rbi);
    }
    scored += rbi;
    if (arm.active && (arm.bf >= arm.targetBf || arm.er >= 5)) {
      arm.active = false;
      arm.exited = true;
      arm.runsForAtExit = scoreFor();
      arm.runsAgainstAtExit = scoreAgainst() + scored;
    }
  }
  addRuns(scored);
  return scored;
}

function closeArm(arm: ArmState, teamFinal: number, oppFinal: number, book: Book, sim: number) {
  if (arm.id <= 0) return;
  if (arm.outs >= 27) book.add(arm.id, sim, 2.5);
  if (arm.outs >= 27 && arm.er === 0) book.add(arm.id, sim, 2.5);
  if (arm.outs >= 27 && arm.er === 0 && arm.hits === 0) book.add(arm.id, sim, 5);
  const leftAhead = arm.exited ? arm.runsForAtExit > arm.runsAgainstAtExit : teamFinal > oppFinal;
  if (arm.outs >= 15 && teamFinal > oppFinal && leftAhead) book.add(arm.id, sim, 4);
}

export async function simulateGames(
  games: SimGame[],
  league: Rates,
  n: number,
  seed: number,
  onProgress?: (done: number, total: number) => void,
): Promise<Map<number, Float32Array>> {
  const ids: number[] = [];
  for (const g of games) {
    for (const h of [...g.awayHitters, ...g.homeHitters]) ids.push(h.id);
    if (g.awayArm) ids.push(g.awayArm.id);
    if (g.homeArm) ids.push(g.homeArm.id);
  }
  const { map, book } = makeBook(ids, n);
  const rng = mulberry32(seed);
  for (const g of games) {
    const awayH = readyHitters(g.awayHitters, g.homeArm, league);
    const homeH = readyHitters(g.homeHitters, g.awayArm, league);
    for (let sim = 0; sim < n; sim++) {
      const homeArm = freshArm(g.homeArm);
      const awayArm = freshArm(g.awayArm);
      const aPtr = { i: 0 };
      const hPtr = { i: 0 };
      let awayScore = 0;
      let homeScore = 0;
      const play = (side: "away" | "home") => {
        if (side === "away") {
          const before = awayScore;
          simHalf(
            awayH,
            aPtr,
            homeArm,
            book,
            sim,
            rng,
            () => homeScore,
            () => before,
            (runs) => {
              awayScore += runs;
            },
          );
        } else {
          const before = homeScore;
          simHalf(
            homeH,
            hPtr,
            awayArm,
            book,
            sim,
            rng,
            () => awayScore,
            () => before,
            (runs) => {
              homeScore += runs;
            },
          );
        }
      };
      for (let inn = 1; inn <= 9; inn++) {
        play("away");
        if (inn === 9 && homeScore > awayScore) break;
        play("home");
      }
      if (awayScore === homeScore) {
        play("away");
        if (homeScore <= awayScore) play("home");
      }
      closeArm(homeArm, homeScore, awayScore, book, sim);
      closeArm(awayArm, awayScore, homeScore, book, sim);
    }
    onProgress?.(games.indexOf(g) + 1, games.length);
    await new Promise((resolve) => setTimeout(resolve, 0));
  }
  return map;
}

export interface PoolPlayer {
  id: number;
  dkId: string;
  name: string;
  team: string;
  opp: string;
  gameId: number;
  slots: Slot[];
  order: number;
  isPitcher: boolean;
  hand: Hand;
  rates: Rates;
  salary: number;
  mean: number;
  std: number;
  samples: Float32Array;
  pricedFrom: "model" | "draftkings";
  role: "starter" | "opener" | "bulk" | "short" | "bat";
  ipPerStart: number | null;
  workloadSource: string;
}

export function moments(samples: Float32Array) {
  let sum = 0;
  let sum2 = 0;
  const n = samples.length || 1;
  for (let i = 0; i < samples.length; i++) {
    const x = samples[i];
    sum += x;
    sum2 += x * x;
  }
  const mean = sum / n;
  const variance = Math.max(0, sum2 / n - mean * mean);
  return { mean, std: Math.sqrt(variance) };
}

export function floorOf(mean: number, std: number, lambda: number) {
  return mean - lambda * std;
}

function quantile(sorted: number[], t: number) {
  if (!sorted.length) return 0;
  const i = clamp(Math.round(t * (sorted.length - 1)), 0, sorted.length - 1);
  return sorted[i];
}

export function pricePlayers(players: PoolPlayer[]) {
  const groups = [
    { list: players.filter((p) => p.isPitcher), lo: 5600, hi: 10600, min: 4000, max: 11400 },
    { list: players.filter((p) => !p.isPitcher), lo: 2800, hi: 7400, min: 2000, max: 9800 },
  ];
  for (const g of groups) {
    const means = g.list.map((p) => p.mean).sort((a, b) => a - b);
    const a = quantile(means, 0.08);
    const b = quantile(means, 0.92);
    const span = Math.max(0.8, b - a);
    for (const p of g.list) {
      if (p.pricedFrom === "draftkings") continue;
      const t = clamp((p.mean - a) / span, 0, 1);
      p.salary = clamp(round100(g.lo + t * (g.hi - g.lo)), g.min, g.max);
    }
  }
}

export interface Assignment {
  slot: Slot;
  player: PoolPlayer;
}

export interface SolveResult {
  lineup: Assignment[] | null;
  note: string;
}

function teamCounts(players: PoolPlayer[]) {
  const counts: Record<string, number> = {};
  for (const p of players) {
    if (p.isPitcher) continue;
    counts[p.team] = (counts[p.team] ?? 0) + 1;
  }
  return counts;
}

function blockedOpps(players: PoolPlayer[]) {
  const s = new Set<string>();
  for (const p of players) if (p.isPitcher) s.add(p.opp);
  return s;
}

export function lineupLegal(players: PoolPlayer[], cap = 50000) {
  if (players.length !== 10) return false;
  let salary = 0;
  const ids = new Set<number>();
  const games = new Set<number>();
  const counts: Record<string, number> = {};
  const opps = new Set<string>();
  let arms = 0;
  for (const p of players) {
    salary += p.salary;
    if (ids.has(p.id)) return false;
    ids.add(p.id);
    if (p.isPitcher) {
      arms += 1;
      if (games.has(p.gameId)) return false;
      games.add(p.gameId);
      opps.add(p.opp);
    }
  }
  if (arms !== 2 || salary > cap) return false;
  for (const p of players) {
    if (p.isPitcher) continue;
    if (opps.has(p.team)) return false;
    counts[p.team] = (counts[p.team] ?? 0) + 1;
    if (counts[p.team] > 3) return false;
  }
  return true;
}

function objective(players: PoolPlayer[], lambda: number) {
  let s = 0;
  for (const p of players) s += floorOf(p.mean, p.std, lambda);
  return s;
}

export function solveLineup(
  pool: PoolPlayer[],
  lambda: number,
  maxOrder: number,
  cap = 50000,
  lockedIds: number[] = [],
  excludedIds: number[] = [],
): SolveResult {
  const locked = new Set(lockedIds);
  const banned = new Set(excludedIds);
  const active = pool.filter((p) => locked.has(p.id) || !banned.has(p.id));
  const arms = active.filter((p) => p.isPitcher);
  const hitters = active.filter(
    (p) => !p.isPitcher && (locked.has(p.id) || (p.order >= 1 && p.order <= maxOrder)),
  );
  const lockedArms = arms.filter((p) => locked.has(p.id));
  const lockedHitters = hitters.filter((p) => locked.has(p.id));
  if (lockedArms.length > 2) {
    return { lineup: null, note: "More than two pitchers are locked." };
  }
  const slotList: Slot[] = ["C", "1B", "2B", "3B", "SS", "OF"];
  for (const slot of slotList) {
    const have = hitters.filter((h) => h.slots.includes(slot));
    const need = slot === "OF" ? 3 : 1;
    if (have.length < need) {
      return {
        lineup: null,
        note: `Only ${have.length} eligible ${slot} inside the batting-order cut (need ${need}). Open the order or wait on lineups.`,
      };
    }
  }
  if (arms.length < 2) {
    return { lineup: null, note: "Need two probable starters on the board." };
  }
  const bySlot = new Map<Slot, PoolPlayer[]>();
  for (const slot of slotList) {
    bySlot.set(
      slot,
      hitters
        .filter((h) => h.slots.includes(slot))
        .sort((a, b) => floorOf(b.mean, b.std, lambda) - floorOf(a.mean, a.std, lambda)),
    );
  }
  const mustArms = new Set(lockedArms.map((p) => p.id));
  const pairs: { a: PoolPlayer; b: PoolPlayer; score: number; salary: number }[] = [];
  for (let i = 0; i < arms.length; i++) {
    for (let j = i + 1; j < arms.length; j++) {
      if (arms[i].gameId === arms[j].gameId) continue;
      if (mustArms.size === 2 && !(mustArms.has(arms[i].id) && mustArms.has(arms[j].id))) continue;
      if (mustArms.size === 1 && !mustArms.has(arms[i].id) && !mustArms.has(arms[j].id)) continue;
      const salary = arms[i].salary + arms[j].salary;
      if (mustArms.size === 0 && salary > cap - 16000) continue;
      pairs.push({
        a: arms[i],
        b: arms[j],
        salary,
        score: floorOf(arms[i].mean, arms[i].std, lambda) + floorOf(arms[j].mean, arms[j].std, lambda),
      });
    }
  }
  pairs.sort((a, b) => b.score - a.score);

  const byId = new Map(pool.map((p) => [p.id, p]));
  const floor = (p: PoolPlayer) => floorOf(p.mean, p.std, lambda);

  const greedyIds = (pair: { a: PoolPlayer; b: PoolPlayer; salary: number }, bias: "floor" | "value" | "cheap") => {
    const blocked = new Set([pair.a.opp, pair.b.opp]);
    const used = new Set<number>([pair.a.id, pair.b.id]);
    const teams: Record<string, number> = {};
    let salary = pair.salary;
    const reserved: (number | null)[] = HITTER_SLOTS.map(() => null);
    for (const h of lockedHitters) {
      if (blocked.has(h.team)) return null;
      const idx = HITTER_SLOTS.findIndex((slot, i) => reserved[i] == null && h.slots.includes(slot));
      if (idx < 0) return null;
      reserved[idx] = h.id;
      used.add(h.id);
      teams[h.team] = (teams[h.team] ?? 0) + 1;
      salary += h.salary;
    }
    const ids: number[] = [];
    for (let s = 0; s < HITTER_SLOTS.length; s++) {
      const held = reserved[s];
      if (held != null) {
        ids.push(held);
        continue;
      }
      const slot = HITTER_SLOTS[s];
      const remainSlots = HITTER_SLOTS.length - s - 1;
      const room = cap - salary - remainSlots * 2000;
      const cands = (bySlot.get(slot) ?? []).filter((p) => {
        if (used.has(p.id) || blocked.has(p.team)) return false;
        if ((teams[p.team] ?? 0) >= 3) return false;
        return p.salary <= room;
      });
      if (!cands.length) return null;
      const target = (cap - salary) / (remainSlots + 1);
      const ranked = cands.slice().sort((a, b) => {
        if (bias === "cheap") return a.salary - b.salary || floor(b) - floor(a);
        if (bias === "floor") return floor(b) - floor(a) || a.salary - b.salary;
        const av = floor(a) / Math.max(2.2, a.salary / 1000);
        const bv = floor(b) / Math.max(2.2, b.salary / 1000);
        const ap = Math.abs(a.salary - target);
        const bp = Math.abs(b.salary - target);
        return bv - av || ap - bp;
      });
      const afford = ranked.filter((p) => p.salary <= Math.max(target * 1.45, 3200));
      const pick = (bias === "value" && afford.length ? afford : ranked)[0];
      ids.push(pick.id);
      used.add(pick.id);
      teams[pick.team] = (teams[pick.team] ?? 0) + 1;
      salary += pick.salary;
    }
    return ids;
  };

  const arrange = (a: PoolPlayer, b: PoolPlayer, ids: number[]): Assignment[] => {
    const placed = HITTER_SLOTS.map((slot, i) => ({
      slot,
      player: byId.get(ids[i])!,
    }));
    const used = new Set<number>();
    const out: Assignment[] = [];
    let armN = 0;
    for (const slot of ROSTER) {
      if (slot === "P") {
        out.push({ slot, player: armN === 0 ? a : b });
        armN += 1;
        continue;
      }
      const found = placed.findIndex((p, idx) => p.slot === slot && !used.has(idx) && p.player);
      if (found < 0) return [];
      used.add(found);
      out.push(placed[found]);
    }
    return out;
  };

  let best: Assignment[] | null = null;
  let bestScore = -Infinity;

  for (const pair of pairs) {
    for (const bias of ["value", "floor", "cheap"] as const) {
      const ids = greedyIds(pair, bias);
      if (!ids) continue;
      const lineup = arrange(pair.a, pair.b, ids);
      if (lineup.length !== 10) continue;
      const picked = lineup.map((x) => x.player);
      if (!lineupLegal(picked, cap)) continue;
      const score = objective(picked, lambda);
      if (score > bestScore) {
        bestScore = score;
        best = lineup;
      }
    }
  }

  if (!best) {
    return {
      lineup: null,
      note: "The cash rules don't leave a legal 10-man roster. Raise the batting-order cut or check that lineups are posted.",
    };
  }

  let current = best;
  const eligible = (slot: Slot) => (slot === "P" ? arms : (bySlot.get(slot) ?? []));
  for (let pass = 0; pass < 5; pass++) {
    let improved = false;
    for (let s = 0; s < current.length; s++) {
      const slot = current[s].slot;
      if (locked.has(current[s].player.id)) continue;
      for (const cand of eligible(slot)) {
        if (current.some((a) => a.player.id === cand.id)) continue;
        const next = current.map((a, i) => (i === s ? { slot, player: cand } : a));
        const players = next.map((a) => a.player);
        if (!lineupLegal(players, cap)) continue;
        if (objective(players, lambda) > objective(current.map((a) => a.player), lambda) + 0.01) {
          current = next;
          improved = true;
        }
      }
    }
    if (!improved) break;
  }

  const players = current.map((a) => a.player);
  const counts = teamCounts(players);
  const blocks = [...blockedOpps(players)];
  const sal = players.reduce((s, p) => s + p.salary, 0);
  return {
    lineup: current,
    note: `Cap $${sal.toLocaleString("en-US")} · stacks ${
      Object.entries(counts)
        .map(([t, n]) => `${t} ${n}`)
        .join(", ") || "none"
    } · fading ${blocks.join(" & ") || "nobody"}`,
  };
}

export function distribution(players: PoolPlayer[]) {
  const n = players[0]?.samples.length ?? 0;
  const totals = new Float32Array(n);
  for (const p of players) {
    const s = p.samples;
    for (let i = 0; i < n; i++) totals[i] += s[i];
  }
  const { mean, std } = moments(totals);
  const copy = Array.from(totals).sort((a, b) => a - b);
  const q = (t: number) => copy[clamp(Math.floor(t * (copy.length - 1)), 0, copy.length - 1)] ?? 0;
  const bins = 16;
  const lo = copy[0] ?? 0;
  const hi = copy[copy.length - 1] ?? 1;
  const span = Math.max(1, hi - lo);
  const counts = Array.from({ length: bins }, (_, i) => ({
    x: Math.round(lo + ((i + 0.5) * span) / bins),
    n: 0,
  }));
  for (const v of copy) {
    const i = clamp(Math.floor(((v - lo) / span) * bins), 0, bins - 1);
    counts[i].n += 1;
  }
  return { mean, std, p10: q(0.1), p50: q(0.5), p90: q(0.9), bins: counts, floor: mean - 0.5 * std };
}
