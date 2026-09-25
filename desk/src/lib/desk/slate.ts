import {
  ARM_PRIOR,
  FULL_MODEL,
  HIT_PRIOR,
  type HandRates,
  type ModelOptions,
  platoonRates,
  shrink,
  type Hand,
  type Rates,
  type SimArm,
  type SimGame,
  type SimHitter,
  type Slot,
  ratesFromCounting,
  starterWorkload,
} from "@/lib/desk/engine";

const MLB = "https://statsapi.mlb.com/api/v1";

const OPEN = new Set(["Scheduled", "Pre-Game", "Warmup", "Delayed", "Delayed Start", "In Progress"]);

export interface Slate {
  date: string;
  season: number;
  league: Rates;
  games: SimGame[];
  checkedAt: string;
}

function num(v: unknown) {
  const n = typeof v === "number" ? v : typeof v === "string" ? Number(v) : 0;
  return Number.isFinite(n) ? n : 0;
}

function str(v: unknown) {
  return typeof v === "string" ? v : "";
}

async function getJson(url: string): Promise<unknown> {
  const res = await fetch(url);
  if (!res.ok) throw new Error(`The MLB feed returned ${res.status}.`);
  return res.json();
}

export function mlbDate(d = new Date()) {
  return new Intl.DateTimeFormat("en-CA", { timeZone: "America/New_York" }).format(d);
}

function handOf(v: unknown): Hand {
  const code = str((v as { code?: string } | null)?.code);
  if (code === "L" || code === "R" || code === "S") return code;
  return "R";
}

function slotsFor(abbr: string): Slot[] {
  switch (abbr) {
    case "C":
      return ["C"];
    case "1B":
      return ["1B"];
    case "2B":
      return ["2B"];
    case "3B":
      return ["3B"];
    case "SS":
      return ["SS"];
    case "LF":
    case "CF":
    case "RF":
    case "OF":
      return ["OF"];
    case "DH":
      return ["OF"];
    default:
      return ["OF"];
  }
}

interface PitchWorkload {
  targetBf: number;
  role: "starter" | "opener" | "bulk" | "short";
  ipPerStart: number | null;
  source: string;
}

function inningsOf(v: unknown) {
  if (typeof v === "string" && v.includes(".")) {
    const [whole, frac] = v.split(".");
    const outs = Number(frac);
    if (outs === 1 || outs === 2) return Number(whole) + outs / 3;
  }
  const n = Number(v);
  return Number.isFinite(n) ? n : 0;
}

function workloadFrom(stat: Record<string, unknown> | undefined, recentStartIp: number[] = []): PitchWorkload {
  const ip = inningsOf(stat?.inningsPitched);
  const gs = num(stat?.gamesStarted);
  const games = num(stat?.gamesPlayed) || gs;
  return starterWorkload(ip, games, gs, recentStartIp);
}

interface Counting {
  pa: number;
  k: number;
  bb: number;
  hbp: number;
  h: number;
  d: number;
  t: number;
  hr: number;
  sb: number;
}

function countingOf(stat: Record<string, unknown>, kind: "hit" | "pitch"): Counting {
  const pa = kind === "hit" ? num(stat.plateAppearances) : num(stat.battersFaced);
  return {
    pa,
    k: num(stat.strikeOuts),
    bb: num(stat.baseOnBalls),
    hbp: kind === "hit" ? num(stat.hitByPitch) : num(stat.hitBatsmen) || num(stat.hitByPitch),
    h: num(stat.hits),
    d: num(stat.doubles),
    t: num(stat.triples),
    hr: num(stat.homeRuns),
    sb: num(stat.stolenBases),
  };
}

interface PersonStat {
  hitting?: Counting;
  pitching?: Counting;
  pitchingRaw?: Record<string, unknown>;
  hand: Hand;
  throwHand: Hand;
  pos: string;
}

interface PriorStat {
  hitting?: Counting;
  pitching?: Counting;
  hitVl?: Counting;
  hitVr?: Counting;
  pitchVl?: Counting;
  pitchVr?: Counting;
}

function parsePrior(payload: unknown): Map<number, PriorStat> {
  const out = new Map<number, PriorStat>();
  const people = (payload as { people?: unknown[] }).people ?? [];
  for (const raw of people) {
    const p = raw as Record<string, unknown>;
    const stat: PriorStat = {};
    const groups =
      (p.stats as {
        type?: { displayName?: string };
        group?: { displayName?: string };
        splits?: { split?: { code?: string }; stat?: Record<string, unknown> }[];
      }[]) ?? [];
    for (const g of groups) {
      const type = g.type?.displayName;
      const group = g.group?.displayName;
      for (const row of g.splits ?? []) {
        if (!row.stat) continue;
        const kind = group === "pitching" ? "pitch" : "hit";
        const c = countingOf(row.stat, kind);
        if (type === "season" && !row.split?.code) {
          if (group === "hitting") stat.hitting = c;
          if (group === "pitching") stat.pitching = c;
        }
        if (type === "statSplits") {
          const code = row.split?.code;
          if (group === "hitting" && code === "vl") stat.hitVl = c;
          if (group === "hitting" && code === "vr") stat.hitVr = c;
          if (group === "pitching" && code === "vl") stat.pitchVl = c;
          if (group === "pitching" && code === "vr") stat.pitchVr = c;
        }
      }
    }
    out.set(num(p.id), stat);
  }
  return out;
}

const UNIFORM = (k: number) => ({ k, bb: k, hbp: k, s1: k, s2: k, s3: k, hr: k });

function addCounting(a: Counting, b: Counting) {
  a.pa += b.pa;
  a.k += b.k;
  a.bb += b.bb;
  a.hbp += b.hbp;
  a.h += b.h;
  a.d += b.d;
  a.t += b.t;
  a.hr += b.hr;
  a.sb += b.sb;
}

function zeroCounting(): Counting {
  return { pa: 0, k: 0, bb: 0, hbp: 0, h: 0, d: 0, t: 0, hr: 0, sb: 0 };
}

const HAND_FALLBACK: Record<keyof HandRates, [number, number]> = {
  LL: [0.9, 1.1],
  LR: [1.04, 0.96],
  RL: [1.03, 0.96],
  RR: [0.98, 1.03],
};

function handRates(priors: PriorStat[], hands: Hand[], league: Rates): HandRates {
  const cells: Record<keyof HandRates, Counting> = { LL: zeroCounting(), LR: zeroCounting(), RL: zeroCounting(), RR: zeroCounting() };
  const all = zeroCounting();
  priors.forEach((p, i) => {
    const hand = hands[i];
    if (p.hitVl) {
      const bh = hand === "S" ? "R" : hand === "L" ? "L" : "R";
      addCounting(cells[`${bh}L` as keyof HandRates], p.hitVl);
      addCounting(all, p.hitVl);
    }
    if (p.hitVr) {
      const bh = hand === "S" ? "L" : hand === "L" ? "L" : "R";
      addCounting(cells[`${bh}R` as keyof HandRates], p.hitVr);
      addCounting(all, p.hitVr);
    }
  });
  const allRates = ratesFromCounting(all);
  const out = {} as HandRates;
  for (const key of ["LL", "LR", "RL", "RR"] as const) {
    const cell = ratesFromCounting(cells[key]);
    const r = { ...league };
    if (cell.sample >= 2500 && allRates.sample > 0) {
      for (const e of ["k", "bb", "hbp", "s1", "s2", "s3", "hr"] as const) {
        r[e] = allRates[e] > 0 ? league[e] * (cell[e] / allRates[e]) : league[e];
      }
    } else {
      const [reach, k] = HAND_FALLBACK[key];
      r.k = league.k * k;
      for (const e of ["bb", "hbp", "s1", "s2", "s3", "hr"] as const) r[e] = league[e] * reach;
    }
    out[key] = r;
  }
  return out;
}

function parsePeople(payload: unknown): Map<number, PersonStat> {
  const out = new Map<number, PersonStat>();
  const people = (payload as { people?: unknown[] }).people ?? [];
  for (const raw of people) {
    const p = raw as Record<string, unknown>;
    const id = num(p.id);
    const pos = str((p.primaryPosition as { abbreviation?: string } | undefined)?.abbreviation);
    const stat: PersonStat = { hand: handOf(p.batSide), throwHand: handOf(p.pitchHand), pos };
    const groups = (p.stats as { group?: { displayName?: string }; splits?: { stat?: Record<string, unknown> }[] }[]) ?? [];
    for (const g of groups) {
      const name = g.group?.displayName;
      const s = g.splits?.[0]?.stat;
      if (!s) continue;
      if (name === "hitting") stat.hitting = countingOf(s, "hit");
      if (name === "pitching") {
        stat.pitching = countingOf(s, "pitch");
        stat.pitchingRaw = s;
      }
    }
    out.set(id, stat);
  }
  return out;
}

async function leagueRates(season: number, through?: string): Promise<Rates> {
  const range = through
    ? `stats=byDateRange&startDate=${season}-01-01&endDate=${through}`
    : "stats=season";
  const payload = (await getJson(
    `${MLB}/teams/stats?season=${season}&group=hitting&${range}&sportIds=1&gameType=R`,
  )) as { stats?: { splits?: { stat?: Record<string, unknown> }[] }[] };
  const splits = payload.stats?.[0]?.splits ?? [];
  const total: Counting = { pa: 0, k: 0, bb: 0, hbp: 0, h: 0, d: 0, t: 0, hr: 0, sb: 0 };
  for (const row of splits) {
    const c = countingOf(row.stat ?? {}, "hit");
    total.pa += c.pa;
    total.k += c.k;
    total.bb += c.bb;
    total.hbp += c.hbp;
    total.h += c.h;
    total.d += c.d;
    total.t += c.t;
    total.hr += c.hr;
    total.sb += c.sb;
  }
  const rates = ratesFromCounting(total);
  if (rates.sample < 1000) throw new Error("League rates didn't come back.");
  return rates;
}

function shiftDate(iso: string, days: number) {
  const [year, month, day] = iso.split("-").map(Number);
  const next = new Date(Date.UTC(year, month - 1, day));
  next.setUTCDate(next.getUTCDate() + days);
  return next.toISOString().slice(0, 10);
}

type CardPlayer = { id: number; fullName: string; primaryPosition?: { abbreviation?: string } };

function lineFields(line: GameLine | null) {
  if (!line || !line.total) return { awayImplied: null, homeImplied: null, lineSource: "No line posted. Stats model only." };
  const [a, h] = impliedTotals(line.total, line.awayMl, line.homeMl);
  const ml = line.awayMl != null && line.homeMl != null ? `ML ${line.awayMl > 0 ? "+" : ""}${line.awayMl}/${line.homeMl > 0 ? "+" : ""}${line.homeMl}` : "no ML, split even";
  return {
    awayImplied: a,
    homeImplied: h,
    lineSource: `${line.provider} total ${line.total}, ${ml}`,
  };
}

async function teamPitching(season: number, through: string, league: Rates): Promise<Map<number, Rates>> {
  const out = new Map<number, Rates>();
  try {
    const payload = (await getJson(
      `${MLB}/teams/stats?season=${season}&group=pitching&stats=byDateRange&startDate=${season}-01-01&endDate=${through}&sportIds=1&gameType=R`,
    )) as { stats?: { splits?: { team?: { id?: number }; stat?: Record<string, unknown> }[] }[] };
    for (const row of payload.stats?.[0]?.splits ?? []) {
      const id = num(row.team?.id);
      if (!id || !row.stat) continue;
      out.set(id, shrink(ratesFromCounting(countingOf(row.stat, "pitch")), null, league, UNIFORM(1500)));
    }
  } catch {
  }
  return out;
}

export const HOOK = { offset: -3 };

export function pitchLimitFrom(pitches: number[], ipPerStart: number | null) {
  if (pitches.length >= 2) {
    const mean = pitches.reduce((a, b) => a + b, 0) / pitches.length;
    return { limit: mean + HOOK.offset, sd: 9 };
  }
  if (ipPerStart != null) return { limit: ipPerStart * 16 + HOOK.offset, sd: 10 };
  return { limit: 79 + HOOK.offset, sd: 12 };
}

function chunk<T>(list: T[], size: number) {
  const out: T[][] = [];
  for (let i = 0; i < list.length; i += size) out.push(list.slice(i, i + size));
  return out;
}

async function priorCards(date: string): Promise<Map<string, CardPlayer[]>> {
  const payload = (await getJson(
    `${MLB}/schedule?sportId=1&startDate=${shiftDate(date, -4)}&endDate=${shiftDate(date, -1)}&hydrate=lineups,team`,
  )) as { dates?: { date?: string; games?: Record<string, unknown>[] }[] };
  const best = new Map<string, { date: string; players: CardPlayer[] }>();
  for (const day of payload.dates ?? []) {
    const dayKey = str(day.date);
    for (const g of day.games ?? []) {
      const teams = g.teams as {
        away: { team: { abbreviation?: string } };
        home: { team: { abbreviation?: string } };
      };
      const lineups = (g.lineups ?? {}) as { awayPlayers?: CardPlayer[]; homePlayers?: CardPlayer[] };
      for (const side of ["away", "home"] as const) {
        const players = (side === "away" ? lineups.awayPlayers : lineups.homePlayers) ?? [];
        const abbr = teams[side].team.abbreviation ?? "";
        if (!abbr || players.length < 9) continue;
        const prev = best.get(abbr);
        if (!prev || dayKey >= prev.date) best.set(abbr, { date: dayKey, players: players.slice(0, 9) });
      }
    }
  }
  return new Map([...best].map(([team, card]) => [team, card.players]));
}

interface RecentStarts {
  ip: number[];
  pitches: number[];
}

async function recentStarts(ids: number[], season: number, date: string): Promise<Map<number, RecentStarts>> {
  const out = new Map<number, RecentStarts>();
  for (const group of chunk(ids, 6)) {
    await Promise.all(
      group.map(async (id) => {
        try {
          const payload = (await getJson(
            `${MLB}/people/${id}/stats?stats=gameLog&group=pitching&season=${season}&gameType=R`,
          )) as { stats?: { splits?: { date?: string; stat?: Record<string, unknown> }[] }[] };
          const splits = (payload.stats?.[0]?.splits ?? [])
            .filter((row) => str(row.date) < date && num(row.stat?.gamesStarted) >= 1)
            .slice(-5);
          out.set(id, {
            ip: splits.map((row) => inningsOf(row.stat?.inningsPitched)),
            pitches: splits.map((row) => num(row.stat?.numberOfPitches)).filter((n) => n > 0),
          });
        } catch {
          out.set(id, { ip: [], pitches: [] });
        }
      }),
    );
  }
  return out;
}

const ESPN = "https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard";
const PYTH_EXP = 1.83;

export interface GameLine {
  awayName: string;
  homeName: string;
  awayAbbr: string;
  homeAbbr: string;
  start: number;
  total: number | null;
  awayMl: number | null;
  homeMl: number | null;
  provider: string;
}

function americanToProb(odds: number) {
  return odds < 0 ? -odds / (-odds + 100) : 100 / (odds + 100);
}

export function impliedTotals(total: number, awayMl: number | null, homeMl: number | null): [number, number] {
  if (awayMl == null || homeMl == null) return [total / 2, total / 2];
  const a = americanToProb(awayMl);
  const h = americanToProb(homeMl);
  const pAway = Math.min(0.8, Math.max(0.2, a / (a + h)));
  const ratio = Math.pow(pAway / (1 - pAway), 1 / PYTH_EXP);
  const away = (total * ratio) / (1 + ratio);
  return [away, total - away];
}

function oddsNum(v: unknown): number | null {
  if (typeof v === "number" && Number.isFinite(v)) return v;
  if (typeof v !== "string") return null;
  const t = v.trim().toUpperCase();
  if (t === "EVEN" || t === "EV") return 100;
  const n = Number(t.replace("+", ""));
  return Number.isFinite(n) && n !== 0 ? n : null;
}

function teamKey(name: string) {
  return name.toLowerCase().replace(/[^a-z]/g, "");
}

const ABBR_ALIAS: Record<string, string> = { CHW: "CWS", CWS: "CWS", ARI: "AZ", AZ: "AZ", OAK: "ATH", ATH: "ATH", WAS: "WSH", WSH: "WSH" };

function abbrKey(a: string) {
  const u = a.toUpperCase();
  return ABBR_ALIAS[u] ?? u;
}

export async function loadLines(date: string): Promise<GameLine[]> {
  try {
    const payload = (await getJson(`${ESPN}?dates=${date.replaceAll("-", "")}`)) as { events?: Record<string, unknown>[] };
    const out: GameLine[] = [];
    for (const ev of payload.events ?? []) {
      const comp = (ev.competitions as Record<string, unknown>[] | undefined)?.[0];
      if (!comp) continue;
      const teams = (comp.competitors as { homeAway?: string; team?: { displayName?: string; abbreviation?: string } }[]) ?? [];
      const away = teams.find((t) => t.homeAway === "away")?.team;
      const home = teams.find((t) => t.homeAway === "home")?.team;
      const odds = (comp.odds as Record<string, unknown>[] | undefined)?.[0];
      if (!away || !home || !odds) continue;
      const ml = odds.moneyline as
        | { away?: { close?: { odds?: unknown }; open?: { odds?: unknown } }; home?: { close?: { odds?: unknown }; open?: { odds?: unknown } } }
        | undefined;
      const total = num(odds.overUnder) || null;
      out.push({
        awayName: away.displayName ?? "",
        homeName: home.displayName ?? "",
        awayAbbr: away.abbreviation ?? "",
        homeAbbr: home.abbreviation ?? "",
        start: Date.parse(str(ev.date)),
        total,
        awayMl: oddsNum(ml?.away?.close?.odds) ?? oddsNum(ml?.away?.open?.odds),
        homeMl: oddsNum(ml?.home?.close?.odds) ?? oddsNum(ml?.home?.open?.odds),
        provider: str((odds.provider as { name?: string } | undefined)?.name) || "ESPN",
      });
    }
    return out;
  } catch {
    return [];
  }
}

function matchLine(
  lines: GameLine[],
  away: { name: string; abbr: string },
  home: { name: string; abbr: string },
  start: number,
): GameLine | null {
  const same = (n: string, a: string, ln: string, la: string) =>
    (n && teamKey(n) === teamKey(ln)) || (a && abbrKey(a) === abbrKey(la));
  const hits = lines.filter((l) => same(away.name, away.abbr, l.awayName, l.awayAbbr) && same(home.name, home.abbr, l.homeName, l.homeAbbr));
  if (!hits.length) return null;
  hits.sort((a, b) => Math.abs(a.start - start) - Math.abs(b.start - start));
  return hits[0];
}

export interface SlateOptions {
  includeFinal?: boolean;
  model?: ModelOptions;
}

export async function loadSlate(date = mlbDate(), opts: SlateOptions = {}): Promise<Slate> {
  const model = opts.model ?? FULL_MODEL;
  const through = shiftDate(date, -1);
  const schedule = (await getJson(
    `${MLB}/schedule?sportId=1&date=${date}&hydrate=lineups,probablePitcher,team,weather`,
  )) as { dates?: { games?: Record<string, unknown>[] }[] };
  const gamesRaw = schedule.dates?.[0]?.games ?? [];
  const open = gamesRaw.filter((g) => {
    const state = str((g.status as { detailedState?: string })?.detailedState);
    return OPEN.has(state) || (opts.includeFinal === true && (state === "Final" || state === "Game Over"));
  });
  const season = num(open[0]?.season) || num(gamesRaw[0]?.season) || Number(date.slice(0, 4));
  const prior = await priorCards(date).catch(() => new Map<string, CardPlayer[]>());
  const ids = new Set<number>();
  const claimed = new Set<number>();
  const sideCard = (g: Record<string, unknown>, side: "away" | "home") => {
    const teams = g.teams as { away: { team: { abbreviation?: string } }; home: { team: { abbreviation?: string } } };
    const lineups = (g.lineups ?? {}) as { awayPlayers?: CardPlayer[]; homePlayers?: CardPlayer[] };
    const posted = (side === "away" ? lineups.awayPlayers : lineups.homePlayers) ?? [];
    const abbr = teams[side].team.abbreviation ?? "";
    if (posted.length >= 9) return { players: posted.slice(0, 9), source: "posted" as const };
    const last = prior.get(abbr) ?? [];
    if (last.length >= 9) return { players: last.slice(0, 9), source: "projected" as const };
    return { players: posted, source: "waiting" as const };
  };
  for (const g of open) {
    for (const side of ["away", "home"] as const) {
      for (const p of sideCard(g, side).players) if (p.id) ids.add(p.id);
    }
    const teams = g.teams as {
      away: { probablePitcher?: { id?: number } };
      home: { probablePitcher?: { id?: number } };
    };
    if (teams.away.probablePitcher?.id) ids.add(teams.away.probablePitcher.id);
    if (teams.home.probablePitcher?.id) ids.add(teams.home.probablePitcher.id);
  }
  const people = new Map<number, PersonStat>();
  const priors = new Map<number, PriorStat>();
  const hydrate = `stats(group=[hitting,pitching],type=[byDateRange],startDate=${season}-01-01,endDate=${through},season=${season})`;
  const priorHydrate = `stats(group=[hitting,pitching],type=[season,statSplits],sitCodes=[vl,vr],season=${season - 1})`;
  const wantPrior = model.priorSeason || model.platoon;
  await Promise.all(
    chunk([...ids], 40).map(async (group) => {
      const payload = await getJson(`${MLB}/people?personIds=${group.join(",")}&hydrate=${encodeURIComponent(hydrate)}&season=${season}`);
      for (const [id, stat] of parsePeople(payload)) people.set(id, stat);
      if (wantPrior) {
        const prior = await getJson(`${MLB}/people?personIds=${group.join(",")}&hydrate=${encodeURIComponent(priorHydrate)}`).catch(() => null);
        if (prior) for (const [id, stat] of parsePrior(prior)) priors.set(id, stat);
      }
    }),
  );
  const [league, lines] = await Promise.all([
    leagueRates(season, through).catch(() => leagueRates(season - 1)),
    model.vegas ? loadLines(date) : Promise.resolve([] as GameLine[]),
  ]);
  const pens = model.bullpen ? await teamPitching(season, through, league) : new Map<number, Rates>();
  const hitterIds = [...ids].filter((id) => people.get(id)?.hitting || priors.get(id)?.hitVl || priors.get(id)?.hitVr);
  const hand = handRates(
    hitterIds.map((id) => priors.get(id) ?? {}),
    hitterIds.map((id) => people.get(id)?.hand ?? "R"),
    league,
  );
  const hitK = model.eventRegression ? HIT_PRIOR : UNIFORM(140);
  const armK = model.eventRegression ? ARM_PRIOR : UNIFORM(180);
  const toRates = (c: Counting | undefined) => (c ? ratesFromCounting(c) : null);
  const armIds = new Set<number>();
  for (const g of open) {
    const teams = g.teams as {
      away: { probablePitcher?: { id?: number } };
      home: { probablePitcher?: { id?: number } };
    };
    if (teams.away.probablePitcher?.id) armIds.add(teams.away.probablePitcher.id);
    if (teams.home.probablePitcher?.id) armIds.add(teams.home.probablePitcher.id);
  }
  const recent = await recentStarts([...armIds], season, date);

  const games: SimGame[] = open.map((g) => {
    const teams = g.teams as {
      away: { team: { abbreviation?: string; id?: number; name?: string }; probablePitcher?: { id?: number; fullName?: string } };
      home: { team: { abbreviation?: string; id?: number; name?: string }; probablePitcher?: { id?: number; fullName?: string } };
    };
    const away = teams.away.team.abbreviation ?? "AWY";
    const home = teams.home.team.abbreviation ?? "HOM";
    const awayCard = sideCard(g, "away");
    const homeCard = sideCard(g, "home");
    const weather = g.weather as { condition?: string; temp?: string; wind?: string } | undefined;
    const weatherText = [weather?.temp ? `${weather.temp}°` : "", weather?.condition ?? "", weather?.wind ?? ""]
      .filter(Boolean)
      .join(" · ");
    const buildHitters = (
      rows: { id: number; fullName: string; primaryPosition?: { abbreviation?: string } }[] | undefined,
      team: string,
      opp: string,
    ): SimHitter[] => {
      const list = rows ?? [];
      const hitters: SimHitter[] = [];
      list.forEach((row, index) => {
        const mlbId = row.id;
        const id = claimed.has(mlbId) ? mlbId * 100000 + (num(g.gamePk) % 100000) : mlbId;
        claimed.add(mlbId);
        const person = people.get(mlbId);
        const gamePos = row.primaryPosition?.abbreviation || "";
        const abbr = gamePos && gamePos !== "DH" ? gamePos : person?.pos || "OF";
        if (abbr === "P") return;
        const counting = person?.hitting;
        const raw = counting ? ratesFromCounting(counting) : ratesFromCounting({ pa: 0, k: 0, bb: 0, hbp: 0, h: 0, d: 0, t: 0, hr: 0 });
        const prior = priors.get(mlbId);
        const rates = shrink(raw, model.priorSeason ? toRates(prior?.hitting) : null, league, hitK);
        const bh = person?.hand ?? "R";
        const split = model.platoon
          ? platoonRates(
              rates,
              { vl: toRates(prior?.hitVl) ?? undefined, vr: toRates(prior?.hitVr) ?? undefined },
              hand[`${bh === "S" ? "R" : bh}L` as keyof HandRates],
              hand[`${bh === "S" ? "L" : bh}R` as keyof HandRates],
              league,
            )
          : null;
        const onBase = Math.max(1, (counting?.h ?? 0) + (counting?.bb ?? 0) + (counting?.hbp ?? 0));
        hitters.push({
          id,
          name: row.fullName,
          team,
          opp,
          gameId: num(g.gamePk),
          slots: slotsFor(abbr),
          order: index + 1,
          rates,
          sb: Math.min(0.42, (counting?.sb ?? 0) / onBase),
          hand: person?.hand ?? "R",
          vsL: split?.vsL,
          vsR: split?.vsR,
        });
      });
      return hitters.slice(0, 9);
    };
    const buildArm = (
      probable: { id?: number; fullName?: string } | undefined,
      team: string,
      opp: string,
    ): SimArm | null => {
      if (!probable?.id || !probable.fullName) return null;
      const person = people.get(probable.id);
      const counting = person?.pitching;
      const pa = counting?.pa || 0;
      const raw = counting
        ? ratesFromCounting({ ...counting, pa: pa || 1 })
        : ratesFromCounting({ pa: 0, k: 0, bb: 0, hbp: 0, h: 0, d: 0, t: 0, hr: 0 });
      if (pa > 0) raw.sample = pa;
      const prior = priors.get(probable.id);
      const rates = shrink(raw, model.priorSeason ? toRates(prior?.pitching) : null, league, armK);
      const th = person?.throwHand === "L" ? "L" : "R";
      const split = model.platoon
        ? platoonRates(
            rates,
            { vl: toRates(prior?.pitchVl) ?? undefined, vr: toRates(prior?.pitchVr) ?? undefined },
            hand[`L${th}` as keyof HandRates],
            hand[`R${th}` as keyof HandRates],
            league,
          )
        : null;
      const starts = recent.get(probable.id) ?? { ip: [], pitches: [] };
      const workload = workloadFrom(person?.pitchingRaw, starts.ip);
      const targetBf = workload.targetBf;
      const hook = pitchLimitFrom(starts.pitches, workload.ipPerStart);
      return {
        id: probable.id,
        name: probable.fullName,
        team,
        opp,
        gameId: num(g.gamePk),
        rates,
        hand: person?.throwHand ?? "R",
        targetBf,
        role: workload.role,
        ipPerStart: workload.ipPerStart,
        workloadSource: model.pitchHook
          ? `${workload.source} Pitch limit about ${Math.round(hook.limit)}${starts.pitches.length >= 2 ? ` (last ${starts.pitches.length} starts averaged ${Math.round(hook.limit - HOOK.offset)})` : ""}.`
          : workload.source,
        vsL: split?.vsL,
        vsR: split?.vsR,
        pitchLimit: hook.limit,
        pitchSd: hook.sd,
      };
    };
    return {
      id: num(g.gamePk),
      label: `${away} @ ${home}`,
      away,
      home,
      start: str(g.gameDate),
      venue: str((g.venue as { name?: string } | undefined)?.name),
      weather: weatherText,
      status: str((g.status as { detailedState?: string })?.detailedState),
      awaySource: awayCard.source,
      homeSource: homeCard.source,
      awayOrder: awayCard.players.length,
      homeOrder: homeCard.players.length,
      awayHitters: buildHitters(awayCard.players, away, home),
      homeHitters: buildHitters(homeCard.players, home, away),
      awayArm: buildArm(teams.away.probablePitcher, away, home),
      homeArm: buildArm(teams.home.probablePitcher, home, away),
      awayPen: pens.get(num(teams.away.team.id)),
      homePen: pens.get(num(teams.home.team.id)),
      hand,
      model,
      ...lineFields(
        matchLine(
          lines,
          { name: teams.away.team.name ?? "", abbr: away },
          { name: teams.home.team.name ?? "", abbr: home },
          Date.parse(str(g.gameDate)),
        ),
      ),
    };
  });

  return { date, season, league, games, checkedAt: new Date().toISOString() };
}
