import type { Assignment, PoolPlayer, SimGame, Slot } from "@/lib/desk/engine";

export function uploadCsv(lineup: Assignment[]) {
  const ids = lineup.map((a) => a.player.dkId);
  return `P,P,C,1B,2B,3B,SS,OF,OF,OF\n${ids.join(",")}\n`;
}

export function uploadReady(lineup: Assignment[]) {
  return (
    lineup.length === 10 &&
    lineup.every(
      (a) =>
        a.player.pricedFrom === "draftkings" &&
        /^\d{8,}$/.test(a.player.dkId) &&
        a.player.salary >= 1500 &&
        a.player.slots.includes(a.slot),
    )
  );
}

export function uploadBlockers(lineup: Assignment[], games: SimGame[], now: number, entryIds: number[]) {
  const problems: string[] = [];
  if (lineup.length !== 10) problems.push("Lineup is not 10 players");
  for (const a of lineup) {
    if (a.player.pricedFrom !== "draftkings" || !/^\d{8,}$/.test(a.player.dkId)) {
      problems.push(`${a.player.name} is missing a DraftKings salary-file ID`);
    } else if (a.player.salary < 1500) {
      problems.push(`${a.player.name} is below the $1,500 floor`);
    } else if (!a.player.slots.includes(a.slot)) {
      problems.push(`${a.player.name} is not eligible at ${a.slot}`);
    }
  }
  const byId = new Map(games.map((g) => [g.id, g]));
  const live = (g: SimGame | undefined) => {
    if (!g) return false;
    if (g.status === "In Progress" || g.status === "Game Over" || g.status === "Final") return true;
    const start = Date.parse(g.start);
    return Number.isFinite(start) && start <= now;
  };
  const livePlayers = lineup.filter((a) => live(byId.get(a.player.gameId)));
  if (!entryIds.length && livePlayers.length) {
    problems.push("A game in this card has already started. Mark your submitted entry before a late swap");
  }
  if (entryIds.length) {
    const kept = new Set(lineup.map((a) => a.player.id));
    const startedMissing = entryIds.filter((id) => {
      if (kept.has(id)) return false;
      const g = games.find(
        (game) =>
          game.awayHitters.some((h) => h.id === id) ||
          game.homeHitters.some((h) => h.id === id) ||
          game.awayArm?.id === id ||
          game.homeArm?.id === id,
      );
      return live(g);
    });
    if (startedMissing.length) {
      problems.push("Late swap dropped a player whose game has already started");
    }
  }
  return [...new Set(problems)];
}

export function scorecardCsv(lineup: Assignment[], lambda = 0.5) {
  const header = "Slot,Name,Team,Opp,Order,Salary,Mean,StdDev,Floor,Id";
  const rows = lineup.map((a) => {
    const p = a.player;
    const floor = (p.mean - lambda * p.std).toFixed(2);
    return [
      a.slot,
      `"${p.name.replaceAll('"', "")}"`,
      p.team,
      p.opp,
      p.isPitcher ? "" : p.order,
      p.salary,
      p.mean.toFixed(2),
      p.std.toFixed(2),
      floor,
      p.dkId || p.id,
    ].join(",");
  });
  return `${header}\n${rows.join("\n")}\n`;
}

export function downloadText(filename: string, text: string) {
  const blob = new Blob([text], { type: "text/csv;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export interface SalaryRow {
  nameKey: string;
  team: string;
  salary: number;
  id: string;
  slots: Slot[];
  gameTeams: string[];
  date: string;
}

function splitCsv(line: string) {
  const out: string[] = [];
  let cur = "";
  let q = false;
  for (let i = 0; i < line.length; i++) {
    const ch = line[i];
    if (ch === '"') {
      q = !q;
      continue;
    }
    if (ch === "," && !q) {
      out.push(cur.trim());
      cur = "";
      continue;
    }
    cur += ch;
  }
  out.push(cur.trim());
  return out;
}

export function normName(name: string) {
  return name
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z\s]/g, "")
    .replace(/\s+/g, " ")
    .trim();
}

export function parseSalaryFile(text: string): SalaryRow[] {
  const lines = text.replace(/^\uFEFF/, "").split(/\r?\n/).filter((l) => l.trim().length);
  let header: string[] = [];
  let start = 1;
  for (let i = 0; i < lines.length; i++) {
    const cols = splitCsv(lines[i]).map((h) => h.toLowerCase());
    const hasName = cols.some((h) => h === "name" || h.includes("name"));
    const hasSalary = cols.some((h) => h.includes("salary"));
    if (hasName && hasSalary) {
      header = cols;
      start = i + 1;
      break;
    }
  }
  if (!header.length) return [];
  const nameI = header.findIndex((h) => h === "name");
  const nameFallback = header.findIndex((h) => h.includes("name"));
  const salI = header.findIndex((h) => h.includes("salary"));
  const teamI = header.findIndex((h) => h.includes("teamabbrev") || h === "team" || h.endsWith(" team"));
  const idI = header.findIndex((h) => h === "id");
  const rosterI = header.findIndex((h) => h === "roster position");
  const posI = header.findIndex((h) => h === "position");
  const gameI = header.findIndex((h) => h === "game info" || h.includes("game info"));
  const useName = nameI >= 0 ? nameI : nameFallback;
  if (useName < 0 || salI < 0) return [];
  const rows: SalaryRow[] = [];
  for (const line of lines.slice(start)) {
    const cols = splitCsv(line);
    const salary = Number(String(cols[salI] ?? "").replace(/[$,]/g, ""));
    if (!Number.isFinite(salary) || salary < 1500) continue;
    const raw = cols[useName] ?? "";
    const roster = rosterI >= 0 ? slotsFromRoster(cols[rosterI] ?? "") : [];
    const fallback = posI >= 0 ? slotsFromRoster(cols[posI] ?? "") : [];
    const info = gameI >= 0 ? cols[gameI] ?? "" : "";
    rows.push({
      nameKey: normName(raw.replace(/\s+\(\d+\)\s*$/, "")),
      team: aliasTeam(cols[teamI] ?? ""),
      salary: Math.round(salary),
      id: idI >= 0 ? cols[idI] ?? "" : "",
      slots: roster.length ? roster : fallback,
      gameTeams: gameTeams(info),
      date: fileDateFromInfo(info),
    });
  }
  return rows;
}

function slotsFromRoster(raw: string): Slot[] {
  const slots: Slot[] = [];
  for (const part of raw.toUpperCase().split("/")) {
    const token = part.trim();
    const slot: Slot | null =
      token === "P" || token === "SP" || token === "RP" ? "P" : token === "C" || token === "1B" || token === "2B" || token === "3B" || token === "SS" || token === "OF" ? token : null;
    if (slot && !slots.includes(slot)) slots.push(slot);
  }
  return slots;
}

function aliasTeam(team: string) {
  const code = team.trim().toUpperCase();
  if (code === "OAK") return "ATH";
  if (code === "CHW") return "CWS";
  if (code === "WSH" || code === "WAS") return "WSH";
  return code;
}

function gameTeams(info: string) {
  const match = info.toUpperCase().match(/([A-Z]{2,3})@([A-Z]{2,3})/);
  if (!match) return [];
  return [aliasTeam(match[1]), aliasTeam(match[2])];
}

function fileDateFromInfo(info: string) {
  const match = info.match(/(\d{1,2})\/(\d{1,2})\/(\d{4})/);
  if (!match) return "";
  return `${match[3]}-${match[1].padStart(2, "0")}-${match[2].padStart(2, "0")}`;
}

export function fileDates(rows: SalaryRow[]) {
  return [...new Set(rows.map((row) => row.date).filter(Boolean))].sort();
}

export function gameKey(away: string, home: string, date: string) {
  return `${aliasTeam(away)}@${aliasTeam(home)}|${date}`;
}

export interface ApplyResult {
  matched: number;
  slateTeams: string[];
  unmatched: number;
  gameKeys: string[];
  dates: string[];
}

export function applySalaries(players: PoolPlayer[], rows: SalaryRow[]): ApplyResult {
  const byName = new Map<string, SalaryRow[]>();
  for (const row of rows) {
    const list = byName.get(row.nameKey) ?? [];
    list.push(row);
    byName.set(row.nameKey, list);
  }
  const used = new Set<SalaryRow>();
  let matched = 0;
  for (const p of players) {
    const hits = byName.get(normName(p.name)) ?? [];
    const row = hits.find((h) => !h.team || h.team === p.team) ?? (hits.length === 1 ? hits[0] : undefined);
    if (!row || !/^\d{8,}$/.test(row.id)) continue;
    const slots: Slot[] = p.isPitcher ? ["P"] : row.slots.filter((slot) => slot !== "P");
    if (!slots.length) continue;
    p.salary = row.salary;
    p.dkId = row.id;
    p.slots = slots;
    p.pricedFrom = "draftkings";
    used.add(row);
    matched += 1;
  }
  const slateTeams = [...new Set(rows.flatMap((row) => (row.gameTeams.length ? row.gameTeams : row.team ? [row.team] : [])))];
  const gameKeys = [
    ...new Set(
      rows
        .map((row) => (row.gameTeams.length >= 2 && row.date ? gameKey(row.gameTeams[0], row.gameTeams[1], row.date) : ""))
        .filter(Boolean),
    ),
  ];
  return { matched, slateTeams, unmatched: rows.length - used.size, gameKeys, dates: fileDates(rows) };
}
