/**
 * Desk backtest: replay past slates exactly as they looked that morning and
 * score the model against real DraftKings points.
 *
 *   npm run desk:backtest -- --from 2026-08-18 --to 2026-09-22 --variants base,vegas,full
 *
 * Variants: base, vegas, full, full-no{Vegas,Event,Prior,Pen,Hook,TTO}, full-platoon;
 * append @hookN to set the pitch-limit margin (e.g. full@hook0). Cache + report
 * go to $DESK_BT_DIR (default: the OS temp dir), never into the repo.
 *
 * No leakage: stats come through the day before (byDateRange), workloads only
 * from earlier starts, lines are ESPN's DraftKings closers, lineups are the ones
 * that were posted. Every HTTP response is cached under .desk-backtest/cache.
 *
 * Salaries: historical DraftKings prices aren't free, so players are priced the
 * way DK roughly prices them, from season-to-date DK points per game. The
 * lineup test asks: does our cash lineup beat the lineup that pricing alone
 * would pick ("market")?
 */
import { execFileSync } from "node:child_process";
import { createHash } from "node:crypto";
import { existsSync, mkdirSync, readFileSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import {
  BASE_MODEL,
  FULL_MODEL,
  cashRate,
  lineupTotals,
  solveCash,
  solveLineup,
  type ModelOptions,
  type PoolPlayer,
} from "@/lib/desk/engine";
import { buildDesk } from "@/lib/desk/run";
import { HOOK } from "@/lib/desk/slate";

const ROOT = process.env.DESK_BT_DIR ?? join(tmpdir(), "desk-backtest");
const CACHE = join(ROOT, "cache");
mkdirSync(CACHE, { recursive: true });

const realFetch = globalThis.fetch;
function cachePath(url: string) {
  return join(CACHE, createHash("sha1").update(url).digest("hex") + ".json");
}
async function rawGet(url: string): Promise<string> {
  if (url.includes("espn.com")) {
    return execFileSync("curl", ["-sS", "--compressed", url], { encoding: "utf8", maxBuffer: 64 << 20 });
  }
  for (let attempt = 0; ; attempt++) {
    const res = await realFetch(url);
    if (res.ok) return res.text();
    if (attempt >= 3) throw new Error(`${res.status} ${url}`);
    await new Promise((r) => setTimeout(r, 800 * (attempt + 1)));
  }
}
async function cachedGet(url: string): Promise<string> {
  const p = cachePath(url);
  if (existsSync(p)) return readFileSync(p, "utf8");
  const text = await rawGet(url);
  if (text.trimStart().startsWith("<")) throw new Error(`blocked (HTML) ${url}`);
  writeFileSync(p, text);
  return text;
}
async function getJson<T = unknown>(url: string): Promise<T> {
  return JSON.parse(await cachedGet(url)) as T;
}

async function scoreboardWithOdds(url: string): Promise<string> {
  const board = await getJson<{ events?: Record<string, unknown>[] }>(url);
  for (const ev of board.events ?? []) {
    const comp = (ev.competitions as Record<string, unknown>[] | undefined)?.[0];
    if (!comp || (comp.odds as unknown[] | undefined)?.length) continue;
    try {
      const sum = await getJson<{ pickcenter?: Record<string, unknown>[] }>(
        `https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/summary?event=${ev.id}`,
      );
      const pc = sum.pickcenter?.[0];
      if (!pc) continue;
      const away = pc.awayTeamOdds as { moneyLine?: number } | undefined;
      const home = pc.homeTeamOdds as { moneyLine?: number } | undefined;
      comp.odds = [
        {
          provider: pc.provider,
          overUnder: pc.overUnder,
          moneyline: {
            away: { close: { odds: away?.moneyLine != null ? String(away.moneyLine) : undefined } },
            home: { close: { odds: home?.moneyLine != null ? String(home.moneyLine) : undefined } },
          },
        },
      ];
    } catch {}
  }
  return JSON.stringify(board);
}

globalThis.fetch = (async (input: RequestInfo | URL) => {
  const url = String(input);
  const body = url.includes("espn.com") && url.includes("/scoreboard") ? await scoreboardWithOdds(url) : await cachedGet(url);
  return new Response(body, { status: 200, headers: { "content-type": "application/json" } });
}) as typeof fetch;

const MLB = "https://statsapi.mlb.com/api/v1";
type Stat = Record<string, number | string | undefined>;
const n = (v: unknown) => (typeof v === "number" ? v : Number(v ?? 0) || 0);

function outsOf(ip: unknown) {
  const [w, f] = String(ip ?? "0").split(".");
  return Number(w) * 3 + (Number(f) || 0);
}

export function dkHitter(s: Stat) {
  const singles = n(s.hits) - n(s.doubles) - n(s.triples) - n(s.homeRuns);
  return (
    3 * singles + 5 * n(s.doubles) + 8 * n(s.triples) + 10 * n(s.homeRuns) +
    2 * n(s.rbi) + 2 * n(s.runs) + 2 * n(s.baseOnBalls) + 2 * n(s.hitByPitch) + 5 * n(s.stolenBases)
  );
}

export function dkPitcher(s: Stat) {
  const outs = n(s.outs) || outsOf(s.inningsPitched);
  const cg = n(s.completeGames) > 0;
  const sho = n(s.shutouts) > 0;
  const nh = cg && n(s.hits) === 0;
  return (
    0.75 * outs + 2 * n(s.strikeOuts) + 4 * n(s.wins) - 2 * n(s.earnedRuns) -
    0.6 * (n(s.hits) + n(s.baseOnBalls) + n(s.hitBatsmen || s.hitByPitch)) +
    (cg ? 2.5 : 0) + (sho ? 2.5 : 0) + (nh ? 5 : 0)
  );
}

async function actuals(date: string) {
  const sched = await getJson<{ dates?: { games?: { gamePk: number; status?: { detailedState?: string } }[] }[] }>(
    `${MLB}/schedule?sportId=1&date=${date}`,
  );
  const out = new Map<number, { hit: Map<number, number>; pitch: Map<number, number> }>();
  for (const g of sched.dates?.[0]?.games ?? []) {
    const state = g.status?.detailedState ?? "";
    if (state !== "Final" && state !== "Game Over") continue;
    const box = await getJson<{ teams: Record<"away" | "home", { players: Record<string, { person: { id: number }; stats: { batting?: Stat; pitching?: Stat } }> }> }>(
      `${MLB}/game/${g.gamePk}/boxscore`,
    );
    const hit = new Map<number, number>();
    const pitch = new Map<number, number>();
    for (const side of ["away", "home"] as const) {
      for (const p of Object.values(box.teams[side].players)) {
        const b = p.stats.batting;
        if (b && Object.keys(b).length && n(b.plateAppearances) > 0) hit.set(p.person.id, dkHitter(b));
        const pi = p.stats.pitching;
        if (pi && Object.keys(pi).length && n(pi.gamesStarted) > 0) pitch.set(p.person.id, dkPitcher(pi));
      }
    }
    out.set(g.gamePk, { hit, pitch });
  }
  return out;
}

async function fppg(ids: number[], date: string) {
  const season = Number(date.slice(0, 4));
  const d = new Date(date + "T12:00:00Z");
  d.setUTCDate(d.getUTCDate() - 1);
  const through = d.toISOString().slice(0, 10);
  const hydrate = `stats(group=[hitting,pitching],type=[byDateRange],startDate=${season}-01-01,endDate=${through},season=${season})`;
  const out = new Map<number, { hit?: number; pitch?: number }>();
  for (let i = 0; i < ids.length; i += 40) {
    const group = ids.slice(i, i + 40).sort((a, b) => a - b);
    const payload = await getJson<{ people?: { id: number; stats?: { group?: { displayName?: string }; splits?: { stat?: Stat }[] }[] }[] }>(
      `${MLB}/people?personIds=${group.join(",")}&hydrate=${encodeURIComponent(hydrate)}&season=${season}`,
    );
    for (const p of payload.people ?? []) {
      const row: { hit?: number; pitch?: number } = {};
      for (const s of p.stats ?? []) {
        const st = s.splits?.[0]?.stat;
        if (!st) continue;
        if (s.group?.displayName === "hitting" && n(st.gamesPlayed) > 0) row.hit = dkHitter(st) / n(st.gamesPlayed);
        if (s.group?.displayName === "pitching") {
          const gs = n(st.gamesStarted);
          const gp = n(st.gamesPlayed);
          if (gs >= 1) row.pitch = dkPitcher({ ...st, completeGames: 0, shutouts: 0 }) / Math.max(gs, gp * 0.5);
        }
      }
      out.set(p.id, row);
    }
  }
  return out;
}

function priceLike(players: PoolPlayer[], value: Map<number, number>) {
  const groups = [
    { list: players.filter((p) => p.isPitcher), lo: 5000, hi: 11000 },
    { list: players.filter((p) => !p.isPitcher), lo: 2200, hi: 6300 },
  ];
  for (const g of groups) {
    const vals = g.list.map((p) => value.get(p.id) ?? 0).sort((a, b) => a - b);
    const q = (t: number) => vals[Math.min(vals.length - 1, Math.max(0, Math.round(t * (vals.length - 1))))] ?? 0;
    const a = q(0.05);
    const b = q(0.95);
    for (const p of g.list) {
      const t = Math.min(1, Math.max(0, ((value.get(p.id) ?? a) - a) / Math.max(0.5, b - a)));
      p.salary = Math.round((g.lo + t * (g.hi - g.lo)) / 100) * 100;
      p.pricedFrom = "draftkings";
    }
  }
}

function spearman(x: number[], y: number[]) {
  const rank = (v: number[]) => {
    const idx = v.map((val, i) => [val, i] as const).sort((a, b) => a[0] - b[0]);
    const r = new Array(v.length).fill(0);
    for (let i = 0; i < idx.length; ) {
      let j = i;
      while (j + 1 < idx.length && idx[j + 1][0] === idx[i][0]) j++;
      for (let k = i; k <= j; k++) r[idx[k][1]] = (i + j) / 2;
      i = j + 1;
    }
    return r;
  };
  const rx = rank(x);
  const ry = rank(y);
  const m = (v: number[]) => v.reduce((a, b) => a + b, 0) / v.length;
  const mx = m(rx);
  const my = m(ry);
  let num = 0;
  let dx = 0;
  let dy = 0;
  for (let i = 0; i < rx.length; i++) {
    num += (rx[i] - mx) * (ry[i] - my);
    dx += (rx[i] - mx) ** 2;
    dy += (ry[i] - my) ** 2;
  }
  return num / Math.sqrt(dx * dy || 1);
}

function pit(samples: Float32Array, actual: number, u: number) {
  let below = 0;
  let eq = 0;
  for (let i = 0; i < samples.length; i++) {
    if (samples[i] < actual - 1e-6) below++;
    else if (Math.abs(samples[i] - actual) <= 1e-6) eq++;
  }
  return (below + u * eq) / samples.length;
}

interface Row {
  date: string;
  pitcher: boolean;
  pred: number;
  actual: number;
  pit: number;
}

interface LineupRow {
  date: string;
  market: number;
  cash: number;
  mean: number;
  cashSimRate: number;
}

function dates(from: string, to: string) {
  const out: string[] = [];
  const d = new Date(from + "T12:00:00Z");
  const end = new Date(to + "T12:00:00Z");
  while (d <= end) {
    out.push(d.toISOString().slice(0, 10));
    d.setUTCDate(d.getUTCDate() + 1);
  }
  return out;
}

function arg(name: string, fallback: string) {
  const i = process.argv.indexOf(`--${name}`);
  return i > 0 ? process.argv[i + 1] : fallback;
}

const VARIANTS: Record<string, ModelOptions> = {
  base: BASE_MODEL,
  vegas: { ...BASE_MODEL, vegas: true },
  full: FULL_MODEL,
  "full-noVegas": { ...FULL_MODEL, vegas: false },
  "full-noEvent": { ...FULL_MODEL, eventRegression: false },
  "full-noPrior": { ...FULL_MODEL, priorSeason: false },
  "full-noPlatoon": { ...FULL_MODEL, platoon: false },
  "full-noPen": { ...FULL_MODEL, bullpen: false },
  "full-noHook": { ...FULL_MODEL, pitchHook: false },
  "full-noTTO": { ...FULL_MODEL, tto: false },
  "full-platoon": { ...FULL_MODEL, platoon: true },
};

function parseVariant(v: string): { model: ModelOptions | undefined; hook: number | null } {
  const [name, extra] = v.split("@");
  const hook = extra?.startsWith("hook") ? Number(extra.slice(4)) : null;
  return { model: VARIANTS[name], hook };
}

const MLB_ID = (id: number) => (id > 1e8 ? Math.floor(id / 100000) : id);

async function main() {
  const from = arg("from", "2026-09-01");
  const to = arg("to", "2026-09-22");
  const variants = arg("variants", "base,full").split(",");
  const sims = Number(arg("sims", "4000"));
  const maxOrder = Number(arg("order", "9"));
  const rows: Record<string, Row[]> = {};
  const lus: Record<string, LineupRow[]> = {};
  const noise = (() => {
    let a = 12345;
    return () => ((a = (a * 1103515245 + 12345) >>> 0) / 4294967296);
  })();

  for (const date of dates(from, to)) {
    const act = await actuals(date);
    if (act.size < 4) {
      console.error(`${date}: ${act.size} final games, skipped`);
      continue;
    }
    for (const v of variants) {
      const { model, hook } = parseVariant(v);
      if (!model) throw new Error(`unknown variant ${v}`);
      const defaultHook = HOOK.offset;
      if (hook != null) HOOK.offset = hook;
      const t0 = Date.now();
      let desk;
      try {
        desk = await buildDesk(date, () => {}, {}, true, { model, includeFinal: true, sims });
      } catch (e) {
        console.error(`${date} ${v}: ${(e as Error).message}`);
        HOOK.offset = defaultHook;
        continue;
      }
      HOOK.offset = defaultHook;
      const pool: PoolPlayer[] = [];
      const truth = new Map<number, number>();
      for (const p of desk.players) {
        const a = act.get(p.gameId);
        if (!a) continue;
        const pts = p.isPitcher ? a.pitch.get(p.id) : a.hit.get(MLB_ID(p.id));
        if (pts == null) continue;
        truth.set(p.id, pts);
        pool.push(p);
        (rows[v] ??= []).push({ date, pitcher: p.isPitcher, pred: p.mean, actual: pts, pit: pit(p.samples, pts, noise()) });
      }
      const value = await fppg([...new Set(pool.map((p) => MLB_ID(p.id)))], date);
      const val = new Map<number, number>();
      for (const p of pool) {
        const f = value.get(MLB_ID(p.id));
        val.set(p.id, (p.isPitcher ? f?.pitch : f?.hit) ?? (p.isPitcher ? 10 : 6));
      }
      priceLike(pool, val);
      const marketPool = pool.map((p) => ({ ...p, mean: val.get(p.id)!, std: 0, samples: new Float32Array(0) }));
      const market = solveLineup(marketPool, 0, maxOrder);
      if (!market.lineup) continue;
      const byId = new Map(pool.map((p) => [p.id, p]));
      const marketSim = market.lineup.map((a) => byId.get(a.player.id)!);
      const lineAvg = lineupTotals(marketSim).reduce((a, b) => a + b, 0) / sims;
      const cash = solveCash(pool, lineAvg, maxOrder);
      const mean = solveLineup(pool, 0, maxOrder);
      const score = (lu: { player: PoolPlayer }[] | null) => (lu ?? []).reduce((s, a) => s + (truth.get(a.player.id) ?? 0), 0);
      const row: LineupRow = {
        date,
        market: score(market.lineup),
        cash: score(cash.lineup),
        mean: score(mean.lineup),
        cashSimRate: cash.lineup ? cashRate(cash.lineup.map((a) => a.player), lineAvg) : 0,
      };
      (lus[v] ??= []).push(row);
      console.error(
        `${date} ${v.padEnd(15)} players ${pool.length}  market ${row.market.toFixed(1)}  cash ${row.cash.toFixed(1)}  mean ${row.mean.toFixed(1)}  ${((Date.now() - t0) / 1000).toFixed(1)}s`,
      );
    }
  }

  const report: string[] = [];
  const f = (x: number, d = 2) => x.toFixed(d);
  report.push(`Desk backtest ${from} → ${to} · sims ${sims} · order cut 1–${maxOrder}`);
  report.push("");
  report.push("PLAYER PROJECTIONS (lower MAE better; Spearman higher better; PIT: 10/50/90 ideal, 80% band ideal 80)");
  for (const v of variants) {
    const all = rows[v] ?? [];
    for (const kind of [false, true]) {
      const r = all.filter((x) => x.pitcher === kind);
      if (!r.length) continue;
      const bias = r.reduce((s, x) => s + x.pred - x.actual, 0) / r.length;
      const mae = r.reduce((s, x) => s + Math.abs(x.pred - x.actual), 0) / r.length;
      const byDate = new Map<string, Row[]>();
      for (const x of r) byDate.set(x.date, [...(byDate.get(x.date) ?? []), x]);
      const rhos = [...byDate.values()].filter((d) => d.length > 8).map((d) => spearman(d.map((x) => x.pred), d.map((x) => x.actual)));
      const rho = rhos.reduce((a, b) => a + b, 0) / Math.max(1, rhos.length);
      const lo = r.filter((x) => x.pit < 0.1).length / r.length;
      const mid = r.filter((x) => x.pit < 0.5).length / r.length;
      const hi = r.filter((x) => x.pit < 0.9).length / r.length;
      const band = r.filter((x) => x.pit >= 0.1 && x.pit < 0.9).length / r.length;
      report.push(
        `${v.padEnd(15)} ${kind ? "P" : "H"} n=${String(r.length).padStart(5)}  bias ${f(bias).padStart(6)}  MAE ${f(mae)}  Spearman ${f(rho, 3)}  PIT<.1 ${f(lo * 100, 1)}%  <.5 ${f(mid * 100, 1)}%  <.9 ${f(hi * 100, 1)}%  80%band ${f(band * 100, 1)}%`,
      );
    }
  }
  report.push("");
  report.push("LINEUPS vs market (DK-like pricing from season FPPG; actual DK points)");
  for (const v of variants) {
    const l = lus[v] ?? [];
    if (!l.length) continue;
    const m = (k: keyof LineupRow) => l.reduce((s, x) => s + (x[k] as number), 0) / l.length;
    const diff = l.map((x) => x.cash - x.market);
    const md = diff.reduce((a, b) => a + b, 0) / diff.length;
    const sd = Math.sqrt(diff.reduce((s, x) => s + (x - md) ** 2, 0) / Math.max(1, diff.length - 1));
    const wins = l.filter((x) => x.cash > x.market).length;
    report.push(
      `${v.padEnd(15)} slates ${l.length}  market ${f(m("market"), 1)}  cash ${f(m("cash"), 1)}  mean-max ${f(m("mean"), 1)}  cash−market ${f(md, 1)} ± ${f(sd / Math.sqrt(diff.length), 1)}  beat market ${wins}/${l.length}`,
    );
  }
  const text = report.join("\n");
  console.log(text);
  writeFileSync(join(ROOT, `report-${from}-${to}.txt`), text + "\n");
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
