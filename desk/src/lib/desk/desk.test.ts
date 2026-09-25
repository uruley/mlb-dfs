import assert from "node:assert/strict";
import test from "node:test";
import { applySalaries, fileDates, parseSalaryFile, scorecardCsv } from "./csv.ts";
import {
  arrangeSlots,
  cashRate,
  lineupLegal,
  platoonRates,
  shrink,
  solveCash,
  solveLineup,
  starterWorkload,
  HIT_PRIOR,
  type PoolPlayer,
  type Slot,
} from "./engine.ts";

const rates = { k: 0.2, bb: 0.08, hbp: 0.01, s1: 0.15, s2: 0.05, s3: 0.005, hr: 0.03, sample: 400 };

function player(partial: Partial<PoolPlayer> & Pick<PoolPlayer, "id" | "name" | "slots" | "salary">): PoolPlayer {
  return {
    dkId: "",
    team: partial.team ?? `T${partial.id}`,
    opp: "OPP",
    gameId: partial.gameId ?? 1,
    order: partial.order ?? 2,
    isPitcher: partial.slots.includes("P"),
    hand: "R",
    rates,
    mean: partial.mean ?? 8,
    std: partial.std ?? 2,
    samples: partial.samples ?? new Float32Array([8, 8, 8, 8]),
    pricedFrom: "model",
    role: partial.slots.includes("P") ? "starter" : "bat",
    ipPerStart: null,
    workloadSource: "",
    ...partial,
  };
}

test("a second salary file does not keep ids from the first", () => {
  const base = [
    player({ id: 1, name: "Ada Stone", team: "PHI", slots: ["OF"], salary: 3000 }),
    player({ id: 2, name: "Bea Stone", team: "NYM", slots: ["OF"], salary: 3000 }),
  ];
  const fileA = `Position,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev
OF,Ada Stone,11111111,OF,5200,PHI@NYM 09/22/2026 01:10PM ET,PHI
OF,Bea Stone,22222222,OF,4100,PHI@NYM 09/22/2026 01:10PM ET,NYM`;
  const fileB = `Position,Name,ID,Roster Position,Salary,Game Info,TeamAbbrev
OF,Bea Stone,33333333,OF,4500,PHI@NYM 09/22/2026 01:10PM ET,NYM`;
  const first = base.map((p) => ({ ...p, slots: [...p.slots] }));
  applySalaries(first, parseSalaryFile(fileA));
  assert.equal(first[0].dkId, "11111111");
  const second = base.map((p) => ({ ...p, slots: [...p.slots] }));
  applySalaries(second, parseSalaryFile(fileB));
  assert.equal(second[0].pricedFrom, "model");
  assert.equal(second[0].dkId, "");
  assert.equal(second[0].salary, 3000);
  assert.equal(second[1].dkId, "33333333");
  assert.equal(second[1].salary, 4500);
  assert.deepEqual(fileDates(parseSalaryFile(fileA)), ["2026-09-22"]);
  const yesterday = parseSalaryFile(fileA.replaceAll("09/22/2026", "09/21/2026"));
  assert.deepEqual(fileDates(yesterday), ["2026-09-21"]);
});

test("one locked outfielder still leaves the legal roster", () => {
  const pool = [
    player({ id: 1, name: "P1", team: "AAA", opp: "BBB", gameId: 1, slots: ["P"], salary: 14000, order: 0 }),
    player({ id: 2, name: "P2", team: "CCC", opp: "DDD", gameId: 2, slots: ["P"], salary: 14000, order: 0 }),
    player({ id: 10, name: "C", slots: ["C"], salary: 2500 }),
    player({ id: 11, name: "SS", slots: ["SS"], salary: 2500 }),
    player({ id: 12, name: "2B", slots: ["2B"], salary: 2500 }),
    player({ id: 13, name: "3B", slots: ["3B"], salary: 2500 }),
    player({ id: 14, name: "1B", slots: ["1B"], salary: 4000 }),
    player({ id: 20, name: "OF Lock", slots: ["OF"], salary: 4000 }),
    player({ id: 21, name: "OF2", slots: ["OF"], salary: 2000 }),
    player({ id: 22, name: "OF3", slots: ["OF"], salary: 2000 }),
  ];
  const open = solveLineup(pool, 0.5, 9);
  assert.ok(open.lineup, open.note);
  const locked = solveLineup(pool, 0.5, 9, 50000, [20]);
  assert.ok(locked.lineup, locked.note);
  assert.ok(locked.lineup?.some((a) => a.player.id === 20 && a.slot === "OF"));
});

test("multi-position locks are arranged so both fit", () => {
  const pool = [
    player({ id: 1, name: "P1", team: "AAA", opp: "BBB", gameId: 1, slots: ["P"], salary: 8000, order: 0 }),
    player({ id: 2, name: "P2", team: "CCC", opp: "DDD", gameId: 2, slots: ["P"], salary: 8000, order: 0 }),
    player({ id: 10, name: "C", slots: ["C"], salary: 3000 }),
    player({ id: 11, name: "SS", slots: ["SS"], salary: 3000 }),
    player({ id: 12, name: "2B", slots: ["2B"], salary: 3000 }),
    player({ id: 13, name: "3B", slots: ["3B"], salary: 3000 }),
    player({ id: 30, name: "Utility", slots: ["1B", "OF"] as Slot[], salary: 3000 }),
    player({ id: 31, name: "Only First", slots: ["1B"], salary: 3000 }),
    player({ id: 21, name: "OF2", slots: ["OF"], salary: 3000 }),
    player({ id: 22, name: "OF3", slots: ["OF"], salary: 3000 }),
  ];
  const locked = solveLineup(pool, 0.5, 9, 50000, [30, 31]);
  assert.ok(locked.lineup, locked.note);
  const byId = new Map(locked.lineup?.map((a) => [a.player.id, a.slot]));
  assert.equal(byId.get(31), "1B");
  assert.equal(byId.get(30), "OF");
});

test("scorecard floor follows the selected risk penalty", () => {
  const lineup = [
    {
      slot: "OF" as const,
      player: player({ id: 1, name: "Ada", slots: ["OF"], salary: 4000, mean: 8, std: 8 }),
    },
  ];
  assert.match(scorecardCsv(lineup, 0.5), /,4\.00,/);
  assert.match(scorecardCsv(lineup, 1), /,0\.00,/);
});

test("relief innings are not counted as innings per start", () => {
  const load = starterWorkload(30, 20, 2);
  assert.ok(load.ipPerStart != null);
  assert.ok(load.ipPerStart < 8, `expected relief-adjusted innings, got ${load.ipPerStart}`);
  assert.ok(load.targetBf < 32);
  const recent = starterWorkload(30, 20, 2, [5, 4.2, 6]);
  assert.ok(Math.abs((recent.ipPerStart ?? 0) - 5.066) < 0.05);
});


test("per-event shrinkage trusts strikeouts sooner than singles", () => {
  const league = { k: 0.22, bb: 0.08, hbp: 0.01, s1: 0.14, s2: 0.045, s3: 0.004, hr: 0.03, sample: 1e5 };
  const hot = { k: 0.1, bb: 0.08, hbp: 0.01, s1: 0.24, s2: 0.045, s3: 0.004, hr: 0.03, sample: 150 };
  const r = shrink(hot, null, league, HIT_PRIOR);
  const kMoved = (league.k - r.k) / (league.k - hot.k);
  const s1Moved = (r.s1 - league.s1) / (hot.s1 - league.s1);
  assert.ok(kMoved > 0.6, `K should mostly stick (${kMoved})`);
  assert.ok(s1Moved < 0.3, `singles should mostly regress (${s1Moved})`);
  const withPrior = shrink(hot, { ...league, s1: 0.2, sample: 600 }, league, HIT_PRIOR);
  assert.ok(withPrior.s1 > r.s1, "a strong prior season pulls singles up");
});

test("platoon rates follow the league split until a player has a big sample", () => {
  const all = { k: 0.22, bb: 0.08, hbp: 0.01, s1: 0.14, s2: 0.045, s3: 0.004, hr: 0.03, sample: 1e5 };
  const vsL = { ...all, hr: 0.024 };
  const vsR = { ...all, hr: 0.033 };
  const none = platoonRates(all, null, vsL, vsR, all);
  assert.ok(Math.abs(none.vsL.hr - 0.024) < 1e-9 && Math.abs(none.vsR.hr - 0.033) < 1e-9);
  const tiny = platoonRates(all, { vl: { ...all, hr: 0.08, sample: 20 }, vr: { ...all, sample: 60 } }, vsL, vsR, all);
  assert.ok(tiny.vsL.hr < 0.03, "20 PA vs LHP barely moves the split");
});

test("arrangeSlots places multi-position players", () => {
  const ps = [
    player({ id: 1, name: "P1", slots: ["P"], salary: 9000, gameId: 1, team: "A", opp: "B" }),
    player({ id: 2, name: "P2", slots: ["P"], salary: 8000, gameId: 2, team: "C", opp: "D" }),
    player({ id: 3, name: "C", slots: ["C", "1B"], salary: 3000 }),
    player({ id: 4, name: "1B", slots: ["1B", "OF"], salary: 3000 }),
    player({ id: 5, name: "2B", slots: ["2B"], salary: 3000 }),
    player({ id: 6, name: "3B", slots: ["3B", "SS"], salary: 3000 }),
    player({ id: 7, name: "SS", slots: ["SS"], salary: 3000 }),
    player({ id: 8, name: "OF1", slots: ["OF"], salary: 3000 }),
    player({ id: 9, name: "OF2", slots: ["OF"], salary: 3000 }),
    player({ id: 10, name: "OF3", slots: ["OF", "1B"], salary: 3000 }),
  ];
  const lu = arrangeSlots(ps);
  assert.ok(lu);
  for (const a of lu!) assert.ok(a.player.slots.includes(a.slot), `${a.player.name} in ${a.slot}`);
});

test("solveCash returns a legal lineup that clears the line at least as often as the mean solver", () => {
  const n = 400;
  let seed = 7;
  const rnd = () => ((seed = (seed * 1103515245 + 12345) >>> 0) / 4294967296);
  const pool: PoolPlayer[] = [];
  const slots: Slot[] = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF", "OF"];
  let id = 1;
  for (let g = 1; g <= 4; g++) {
    for (const side of ["H", "A"]) {
      const team = `${side}${g}`;
      const opp = `${side === "H" ? "A" : "H"}${g}`;
      const mean = 12 + rnd() * 10;
      const samples = new Float32Array(n).map(() => Math.max(-5, mean + (rnd() - 0.5) * 30));
      pool.push(player({ id: id++, name: `SP ${team}`, team, opp, gameId: g, slots: ["P"], salary: 6000 + Math.round(rnd() * 40) * 100, mean, std: 9, samples }));
      slots.forEach((slot, i) => {
        const m = 4 + rnd() * 6;
        const s = new Float32Array(n).map(() => (rnd() < 0.3 ? 0 : m * 2 * rnd() * 1.4));
        pool.push(player({ id: id++, name: `${team} ${slot}${i}`, team, opp, gameId: g, slots: [slot], order: i + 1, salary: 2500 + Math.round(rnd() * 30) * 100, mean: m, std: 6, samples: s }));
      });
    }
  }
  const line = 75;
  const cash = solveCash(pool, line, 9);
  assert.ok(cash.lineup, cash.note);
  const players = cash.lineup!.map((a) => a.player);
  assert.ok(lineupLegal(players));
  for (const a of cash.lineup!) assert.ok(a.player.slots.includes(a.slot));
  const mean = solveLineup(pool, 0, 9);
  assert.ok(mean.lineup);
  assert.ok(cashRate(players, line) >= cashRate(mean.lineup!.map((a) => a.player), line) - 1e-9);
});
