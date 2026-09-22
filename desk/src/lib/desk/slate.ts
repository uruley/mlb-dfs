import {
  type Hand,
  type Rates,
  type SimArm,
  type SimGame,
  type SimHitter,
  type Slot,
  ratesFromCounting,
  regress,
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

function workloadFrom(stat: Record<string, unknown> | undefined): PitchWorkload {
  const ip = inningsOf(stat?.inningsPitched);
  const gs = num(stat?.gamesStarted);
  const games = num(stat?.gamesPlayed) || gs;
  const ipPerStart = gs >= 1 ? ip / gs : games > 0 && ip > 0 ? ip / games : null;
  let role: PitchWorkload["role"] = "starter";
  if (ipPerStart == null) role = "starter";
  else if (ipPerStart < 2.2) role = "opener";
  else if (gs <= 3 && ipPerStart < 4.5) role = "bulk";
  else if (ipPerStart < 4.5) role = "short";
  const targetBf =
    ipPerStart == null ? 22 : Math.round(Math.min(32, Math.max(6, ipPerStart * 4.35)));
  const source =
    ipPerStart == null
      ? "No season innings on file. Using 22 batters faced."
      : `MLB season, ${ipPerStart.toFixed(1)} innings per start, ${role}.`;
  return { targetBf, role, ipPerStart, source };
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

async function leagueRates(season: number): Promise<Rates> {
  const payload = (await getJson(
    `${MLB}/teams/stats?season=${season}&group=hitting&stats=season&sportIds=1&gameType=R`,
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

function chunk<T>(list: T[], size: number) {
  const out: T[][] = [];
  for (let i = 0; i < list.length; i += size) out.push(list.slice(i, i + size));
  return out;
}

export async function loadSlate(date = mlbDate()): Promise<Slate> {
  const schedule = (await getJson(
    `${MLB}/schedule?sportId=1&date=${date}&hydrate=lineups,probablePitcher,team,weather`,
  )) as { dates?: { games?: Record<string, unknown>[] }[] };
  const gamesRaw = schedule.dates?.[0]?.games ?? [];
  const open = gamesRaw.filter((g) => OPEN.has(str((g.status as { detailedState?: string })?.detailedState)));
  const season = num(open[0]?.season) || num(gamesRaw[0]?.season) || Number(date.slice(0, 4));
  const ids = new Set<number>();
  for (const g of open) {
    const teams = g.teams as {
      away: { probablePitcher?: { id?: number } };
      home: { probablePitcher?: { id?: number } };
    };
    const lineups = (g.lineups ?? {}) as { awayPlayers?: { id?: number }[]; homePlayers?: { id?: number }[] };
    for (const p of [...(lineups.awayPlayers ?? []), ...(lineups.homePlayers ?? [])]) {
      if (p.id) ids.add(p.id);
    }
    if (teams.away.probablePitcher?.id) ids.add(teams.away.probablePitcher.id);
    if (teams.home.probablePitcher?.id) ids.add(teams.home.probablePitcher.id);
  }
  const people = new Map<number, PersonStat>();
  const hydrate = "stats(group=[hitting,pitching],type=[season],season=" + season + ")";
  await Promise.all(
    chunk([...ids], 40).map(async (group) => {
      const payload = await getJson(`${MLB}/people?personIds=${group.join(",")}&hydrate=${encodeURIComponent(hydrate)}&season=${season}`);
      for (const [id, stat] of parsePeople(payload)) people.set(id, stat);
    }),
  );
  const league = await leagueRates(season);

  const games: SimGame[] = open.map((g) => {
    const teams = g.teams as {
      away: { team: { abbreviation?: string; id?: number }; probablePitcher?: { id?: number; fullName?: string } };
      home: { team: { abbreviation?: string; id?: number }; probablePitcher?: { id?: number; fullName?: string } };
    };
    const away = teams.away.team.abbreviation ?? "AWY";
    const home = teams.home.team.abbreviation ?? "HOM";
    const lineups = (g.lineups ?? {}) as {
      awayPlayers?: { id: number; fullName: string; primaryPosition?: { abbreviation?: string } }[];
      homePlayers?: { id: number; fullName: string; primaryPosition?: { abbreviation?: string } }[];
    };
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
        const person = people.get(row.id);
        const gamePos = row.primaryPosition?.abbreviation || "";
        const abbr = gamePos && gamePos !== "DH" ? gamePos : person?.pos || "OF";
        if (abbr === "P") return;
        const counting = person?.hitting;
        const raw = counting ? ratesFromCounting(counting) : ratesFromCounting({ pa: 0, k: 0, bb: 0, hbp: 0, h: 0, d: 0, t: 0, hr: 0 });
        const rates = regress(raw, league, 140);
        const onBase = Math.max(1, (counting?.h ?? 0) + (counting?.bb ?? 0) + (counting?.hbp ?? 0));
        hitters.push({
          id: row.id,
          name: row.fullName,
          team,
          opp,
          gameId: num(g.gamePk),
          slots: slotsFor(abbr),
          order: index + 1,
          rates,
          sb: Math.min(0.42, (counting?.sb ?? 0) / onBase),
          hand: person?.hand ?? "R",
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
      const rates = regress(raw, league, 180);
      const workload = workloadFrom(person?.pitchingRaw);
      const targetBf = workload.targetBf;
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
        workloadSource: workload.source,
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
      awayOrder: (lineups.awayPlayers ?? []).length,
      homeOrder: (lineups.homePlayers ?? []).length,
      awayHitters: buildHitters(lineups.awayPlayers, away, home),
      homeHitters: buildHitters(lineups.homePlayers, home, away),
      awayArm: buildArm(teams.away.probablePitcher, away, home),
      homeArm: buildArm(teams.home.probablePitcher, home, away),
    };
  });

  return { date, season, league, games, checkedAt: new Date().toISOString() };
}
