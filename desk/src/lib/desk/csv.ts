import type { Assignment, PoolPlayer } from "@/lib/desk/engine";

export function uploadCsv(lineup: Assignment[]) {
  const ids = lineup.map((a) => a.player.dkId || String(a.player.id));
  return `P,P,C,1B,2B,3B,SS,OF,OF,OF\n${ids.join(",")}\n`;
}

export function scorecardCsv(lineup: Assignment[]) {
  const header = "Slot,Name,Team,Opp,Order,Salary,Mean,StdDev,Floor,Id";
  const rows = lineup.map((a) => {
    const p = a.player;
    const floor = (p.mean - 0.5 * p.std).toFixed(2);
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
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length);
  if (lines.length < 2) return [];
  const header = splitCsv(lines[0]).map((h) => h.toLowerCase());
  const idx = (...names: string[]) => header.findIndex((h) => names.some((n) => h.includes(n)));
  const nameI = idx("name");
  const salI = idx("salary");
  const teamI = idx("teamabbrev", "team");
  const idI = header.findIndex((h) => h === "id" || h.endsWith(" id"));
  if (nameI < 0 || salI < 0) return [];
  const rows: SalaryRow[] = [];
  for (const line of lines.slice(1)) {
    const cols = splitCsv(line);
    const salary = Number(String(cols[salI] ?? "").replace(/[$,]/g, ""));
    if (!Number.isFinite(salary) || salary < 1500) continue;
    const name = cols[nameI] ?? "";
    rows.push({
      nameKey: normName(name.replace(/\s+\(\d+\)\s*$/, "")),
      team: (cols[teamI] ?? "").toUpperCase(),
      salary: Math.round(salary),
      id: idI >= 0 ? cols[idI] ?? "" : "",
    });
  }
  return rows;
}

export function applySalaries(players: PoolPlayer[], rows: SalaryRow[]) {
  const byName = new Map<string, SalaryRow[]>();
  for (const row of rows) {
    const list = byName.get(row.nameKey) ?? [];
    list.push(row);
    byName.set(row.nameKey, list);
  }
  let matched = 0;
  for (const p of players) {
    const hits = byName.get(normName(p.name)) ?? [];
    const row = hits.find((h) => !h.team || h.team === p.team) ?? (hits.length === 1 ? hits[0] : undefined);
    if (!row) continue;
    p.salary = row.salary;
    if (row.id) p.dkId = row.id;
    p.pricedFrom = "draftkings";
    matched += 1;
  }
  return matched;
}
