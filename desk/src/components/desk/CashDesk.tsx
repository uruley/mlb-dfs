import { useEffect, useMemo, useState } from "react";
import {
  AlertTriangle,
  Download,
  RefreshCw,
  ShieldCheck,
  Timer,
  Upload,
} from "lucide-react";
import { Bar, BarChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from "recharts";
import {
  BASE_LABELS,
  applyPlatoon,
  distribution,
  floorOf,
  log5,
  matchupDist,
  runExpectancy,
  solveLineup,
  type PoolPlayer,
  type Slot,
} from "@/lib/desk/engine";
import { applySalaries, downloadText, parseSalaryFile, scorecardCsv, uploadCsv } from "@/lib/desk/csv";
import { buildDesk, type DeskData } from "@/lib/desk/run";
import { mlbDate } from "@/lib/desk/slate";

type Phase = "load" | "ready" | "error";
type SortKey = "floor" | "mean" | "std" | "salary" | "order";

const RATE_ROWS = [
  ["k", "Strikeout"],
  ["bb", "Walk"],
  ["s1", "Single"],
  ["hr", "Home run"],
  ["s2", "Double"],
  ["hbp", "Hit by pitch"],
] as const;

function money(n: number) {
  return `$${Math.round(n).toLocaleString("en-US")}`;
}

function pts(n: number) {
  return n.toFixed(1);
}

function shiftDate(iso: string, days: number) {
  const [y, m, d] = iso.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d));
  dt.setUTCDate(dt.getUTCDate() + days);
  return dt.toISOString().slice(0, 10);
}

function prettyDate(iso: string) {
  const [y, m, d] = iso.split("-").map(Number);
  return new Date(Date.UTC(y, m - 1, d)).toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    timeZone: "UTC",
  });
}

function Countdown({ start }: { start: string }) {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, []);
  const target = Date.parse(start);
  if (!Number.isFinite(target)) return null;
  const delta = target - now;
  const past = delta <= 0;
  const abs = Math.abs(delta);
  const h = Math.floor(abs / 3_600_000);
  const m = Math.floor((abs % 3_600_000) / 60_000);
  const s = Math.floor((abs % 60_000) / 1000);
  const label = `${h}:${String(m).padStart(2, "0")}:${String(s).padStart(2, "0")}`;
  return (
    <div className="flex items-center gap-2 rounded-full border border-line bg-field px-3 py-2 text-sm">
      <Timer className="size-4 text-gold" aria-hidden="true" />
      <span className="text-mist">{past ? "First pitch was" : "First pitch"}</span>
      <span className="font-medium tabular-nums text-chalk">{label}</span>
    </div>
  );
}

export function CashDesk() {
  const [phase, setPhase] = useState<Phase>("load");
  const [message, setMessage] = useState("Reading the board");
  const [pct, setPct] = useState(0.05);
  const [error, setError] = useState("");
  const [data, setData] = useState<DeskData | null>(null);
  const [date, setDate] = useState(mlbDate());
  const [nonce, setNonce] = useState(0);
  const [lambda, setLambda] = useState(0.5);
  const [maxOrder, setMaxOrder] = useState(5);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [query, setQuery] = useState("");
  const [sortKey, setSortKey] = useState<SortKey>("floor");
  const [salaryNote, setSalaryNote] = useState("Salaries are modeled from the floor until a DraftKings file is dropped.");
  const [view, setView] = useState<"ticket" | "pool" | "math">("ticket");

  useEffect(() => {
    let dead = false;
    setPhase("load");
    setError("");
    setPct(0.04);
    buildDesk(date, (msg, next) => {
      if (!dead) {
        setMessage(msg);
        setPct(next);
      }
    })
      .then((desk) => {
        if (dead) return;
        setData(desk);
        setSalaryNote("Salaries are modeled from the floor until a DraftKings file is dropped.");
        setPhase("ready");
        setSelectedId(desk.players.find((p) => !p.isPitcher)?.id ?? null);
      })
      .catch((err: unknown) => {
        if (dead) return;
        setPhase("error");
        setError(err instanceof Error ? err.message : "The board didn't load.");
      });
    return () => {
      dead = true;
    };
  }, [date, nonce]);

  const solved = useMemo(() => {
    if (!data) return null;
    return solveLineup(data.players, lambda, maxOrder);
  }, [data, lambda, maxOrder]);

  const lineupPlayers = useMemo(() => solved?.lineup?.map((a) => a.player) ?? [], [solved]);

  const dist = useMemo(() => (lineupPlayers.length === 10 ? distribution(lineupPlayers) : null), [lineupPlayers]);

  const salary = lineupPlayers.reduce((s, p) => s + p.salary, 0);
  const objective = lineupPlayers.reduce((s, p) => s + floorOf(p.mean, p.std, lambda), 0);

  const selected = data?.players.find((p) => p.id === selectedId) ?? lineupPlayers[0] ?? null;

  const rows = useMemo(() => {
    if (!data) return [];
    const q = query.trim().toLowerCase();
    const inLineup = new Set(lineupPlayers.map((p) => p.id));
    return data.players
      .filter((p) => {
        if (q && !`${p.name} ${p.team}`.toLowerCase().includes(q)) return false;
        if (view === "pool" && !p.isPitcher && p.order > maxOrder) return true;
        return true;
      })
      .map((p) => ({ p, floor: floorOf(p.mean, p.std, lambda), in: inLineup.has(p.id) }))
      .sort((a, b) => {
        if (sortKey === "order") return (a.p.order || 99) - (b.p.order || 99);
        if (sortKey === "salary") return b.p.salary - a.p.salary;
        if (sortKey === "mean") return b.p.mean - a.p.mean;
        if (sortKey === "std") return b.p.std - a.p.std;
        return b.floor - a.floor;
      });
  }, [data, query, lineupPlayers, lambda, sortKey, maxOrder, view]);

  const firstStart = data?.slate.games.map((g) => g.start).sort()[0];
  const confirmed = data
    ? data.slate.games.filter((g) => g.awayOrder >= 9 && g.homeOrder >= 9).length
    : 0;

  function onSalaryFile(file: File) {
    file.text().then((text) => {
      if (!data) return;
      const parsed = parseSalaryFile(text);
      if (!parsed.length) {
        setSalaryNote("That file didn't look like a DraftKings salary sheet.");
        return;
      }
      const next = data.players.map((p) => ({ ...p }));
      const matched = applySalaries(next, parsed);
      setData({ ...data, players: next });
      setSalaryNote(
        matched
          ? `Matched ${matched} salaries from ${file.name}. The upload file will use DraftKings ids.`
          : "No names matched. Check that the sheet is the classic salary export.",
      );
    });
  }

  return (
    <main className="mx-auto min-h-screen max-w-6xl px-4 py-6 sm:px-6 sm:py-8">
      <header className="flex flex-col gap-5 border-b border-line pb-6 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <p className="text-xs font-medium tracking-widest text-gold uppercase">MLB classic cash</p>
          <h1 className="font-display mt-1 text-5xl leading-none text-chalk sm:text-6xl">Cash Desk</h1>
          <p className="mt-3 max-w-xl text-sm leading-6 text-mist">
            Floor-weighted DraftKings lineups. Log5 matchups, a 24-state half-inning chain, ten thousand
            sims a game, then the cash constraints.
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <div className="flex items-center gap-2 rounded-full border border-line bg-field px-3 py-2 text-sm">
            <span className="pulse-dot size-2 rounded-full bg-gold" aria-hidden="true" />
            <span className="tabular-nums text-chalk">{prettyDate(date)}</span>
          </div>
          {firstStart ? <Countdown start={firstStart} /> : null}
        </div>
      </header>

      {phase === "load" ? (
        <section className="mt-8 rounded-2xl border border-line bg-field p-6">
          <p className="text-xs tracking-widest text-mist uppercase">Pipeline</p>
          <h2 className="font-display mt-2 text-3xl text-chalk">{message}</h2>
          <div className="mt-5 h-2 overflow-hidden rounded-full bg-raised">
            <div className="h-full bg-gold" style={{ width: `${Math.round(pct * 100)}%` }} />
          </div>
          <ol className="mt-6 grid gap-2 text-sm text-mist sm:grid-cols-3">
            {["Board & lineups", "Log5 + Markov", "10k sims", "Floor solve", "Cap & fades", "Upload CSV"].map(
              (step, i) => (
                <li key={step} className="rounded-xl border border-line bg-ink px-3 py-3">
                  <span className="tabular-nums text-gold">0{i + 1}</span>
                  <span className="mt-1 block text-chalk">{step}</span>
                </li>
              ),
            )}
          </ol>
        </section>
      ) : null}

      {phase === "error" ? (
        <section className="mt-8 rounded-2xl border border-line bg-field p-6">
          <AlertTriangle className="size-6 text-risk" aria-hidden="true" />
          <h2 className="font-display mt-3 text-3xl">The board stalled</h2>
          <p className="mt-2 max-w-lg text-sm leading-6 text-mist">{error}</p>
          <button
            type="button"
            className="mt-5 min-h-11 rounded-full bg-gold px-5 text-sm font-medium text-ink"
            onClick={() => setNonce((n) => n + 1)}
          >
            Try again
          </button>
        </section>
      ) : null}

      {phase === "ready" && data && solved ? (
        <div className="mt-6 flex flex-col gap-6">
          <section className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
            <div className="flex flex-wrap gap-2">
              {(["ticket", "pool", "math"] as const).map((key) => (
                <button
                  key={key}
                  type="button"
                  onClick={() => setView(key)}
                  className={
                    view === key
                      ? "min-h-11 rounded-full bg-chalk px-4 text-sm font-medium text-ink"
                      : "min-h-11 rounded-full border border-line px-4 text-sm text-chalk"
                  }
                >
                  {key === "ticket" ? "Lineup" : key === "pool" ? "Pool" : "Matchup"}
                </button>
              ))}
            </div>
            <div className="flex flex-wrap gap-2">
              <button
                type="button"
                className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line px-4 text-sm"
                onClick={() => setDate((d) => shiftDate(d, -1))}
              >
                Prior day
              </button>
              <button
                type="button"
                className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line px-4 text-sm"
                onClick={() => setDate(mlbDate())}
              >
                Tonight
              </button>
              <button
                type="button"
                className="inline-flex min-h-11 items-center gap-2 rounded-full border border-line px-4 text-sm"
                onClick={() => setNonce((n) => n + 1)}
              >
                <RefreshCw className="size-4" aria-hidden="true" />
                Rerun
              </button>
            </div>
          </section>

          <section className="grid gap-3 sm:grid-cols-3">
            <label className="rounded-2xl border border-line bg-field px-4 py-3 text-sm">
              <span className="block text-mist">Risk penalty · {lambda.toFixed(2)} × stdev</span>
              <input
                className="mt-3 w-full"
                type="range"
                min={0}
                max={1.5}
                step={0.05}
                value={lambda}
                onChange={(e) => setLambda(Number(e.target.value))}
              />
            </label>
            <label className="rounded-2xl border border-line bg-field px-4 py-3 text-sm">
              <span className="block text-mist">Batting-order cut · 1 through {maxOrder}</span>
              <input
                className="mt-3 w-full"
                type="range"
                min={5}
                max={9}
                step={1}
                value={maxOrder}
                onChange={(e) => setMaxOrder(Number(e.target.value))}
              />
            </label>
            <div className="rounded-2xl border border-line bg-field px-4 py-3 text-sm">
              <span className="block text-mist">
                {confirmed}/{data.slate.games.length} lineups posted · {data.sims.toLocaleString("en-US")} sims
              </span>
              <p className="mt-2 text-chalk">{salaryNote}</p>
            </div>
          </section>

          {view === "ticket" ? (
            <section className="grid gap-4 lg:grid-cols-[minmax(0,1.3fr)_minmax(0,0.7fr)]">
              <article className="rounded-2xl bg-chalk p-5 text-ink sm:p-6">
                <div className="flex flex-wrap items-end justify-between gap-3 border-b border-ink/15 pb-4">
                  <div>
                    <p className="text-xs tracking-widest text-ink/60 uppercase">Optimal cash ticket</p>
                    <h2 className="font-display text-4xl leading-none">
                      {dist ? pts(dist.mean) : solved.lineup ? pts(objective) : "No ticket"}
                    </h2>
                    <p className="mt-1 text-sm text-ink/70">
                      {dist
                        ? `Projected mean · floor ${pts(objective)} · p10 ${pts(dist.p10)}`
                        : `Objective is mean minus ${lambda.toFixed(2)} × stdev`}
                    </p>
                  </div>
                    <div className="text-right text-sm tabular-nums">
                      <div>{solved.lineup ? money(salary) : "—"} / $50,000</div>
                      <div className="text-ink/70">{dist ? `Median ${pts(dist.p50)} · p90 ${pts(dist.p90)}` : solved.note}</div>
                    </div>
                </div>
                {solved.lineup ? (
                  <ol className="mt-2 divide-y divide-ink/10">
                    {solved.lineup.map((a, i) => (
                      <li key={`${a.slot}-${a.player.id}-${i}`}>
                        <button
                          type="button"
                          onClick={() => {
                            setSelectedId(a.player.id);
                            setView("math");
                          }}
                          className="flex w-full items-center gap-3 py-3 text-left"
                        >
                          <span className="w-8 text-xs font-medium text-ink/50">{a.slot}</span>
                          <span className="min-w-0 flex-1">
                            <span className="block truncate font-medium">{a.player.name}</span>
                            <span className="text-xs text-ink/60">
                              {a.player.team} vs {a.player.opp}
                              {a.player.isPitcher ? "" : ` · ${ordinal(a.player.order)}`}
                            </span>
                          </span>
                          <span className="text-right text-sm tabular-nums">
                            <span className="block">{money(a.player.salary)}</span>
                            <span className="text-xs text-ink/60">
                              {pts(a.player.mean)} ± {pts(a.player.std)}
                            </span>
                          </span>
                        </button>
                      </li>
                    ))}
                  </ol>
                ) : (
                  <p className="mt-4 text-sm leading-6 text-ink/75">{solved.note}</p>
                )}
                <div className="mt-4 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={!solved.lineup}
                    className="inline-flex min-h-11 items-center gap-2 rounded-full bg-ink px-4 text-sm font-medium text-chalk disabled:opacity-40"
                    onClick={() => solved.lineup && downloadText("optimal_upload.csv", uploadCsv(solved.lineup))}
                  >
                    <Download className="size-4" aria-hidden="true" />
                    Upload CSV
                  </button>
                  <button
                    type="button"
                    disabled={!solved.lineup}
                    className="inline-flex min-h-11 items-center gap-2 rounded-full border border-ink/20 px-4 text-sm disabled:opacity-40"
                    onClick={() => solved.lineup && downloadText("scorecard.csv", scorecardCsv(solved.lineup))}
                  >
                    Scorecard
                  </button>
                  <label className="inline-flex min-h-11 cursor-pointer items-center gap-2 rounded-full border border-ink/20 px-4 text-sm">
                    <Upload className="size-4" aria-hidden="true" />
                    DK salaries
                    <input
                      className="sr-only"
                      type="file"
                      accept=".csv,text/csv"
                      onChange={(e) => {
                        const file = e.target.files?.[0];
                        if (file) onSalaryFile(file);
                        e.target.value = "";
                      }}
                    />
                  </label>
                </div>
                {solved.lineup ? <p className="mt-3 text-xs leading-5 text-ink/60">{solved.note}</p> : null}
              </article>

              <div className="flex flex-col gap-4">
                <article className="rounded-2xl border border-line bg-field p-4">
                  <h3 className="text-sm font-medium text-chalk">Lineup distribution</h3>
                  <p className="mt-1 text-xs text-mist">Same-game sims stay correlated. Bars are total DraftKings points.</p>
                  <div className="mt-3 h-44">
                    {dist ? (
                      <ResponsiveContainer width="100%" height="100%">
                        <BarChart data={dist.bins}>
                          <XAxis
                            dataKey="x"
                            interval={3}
                            tick={{ fill: "var(--color-mist)", fontSize: 11 }}
                            axisLine={false}
                            tickLine={false}
                          />
                          <YAxis hide />
                          <Tooltip
                            cursor={{ fill: "transparent" }}
                            contentStyle={{
                              background: "var(--color-ink)",
                              border: "1px solid var(--color-line)",
                              borderRadius: 12,
                              color: "var(--color-chalk)",
                              fontSize: 12,
                            }}
                            formatter={(value) => [Number(value).toLocaleString("en-US"), "Sims"]}
                            labelFormatter={(label) => `${label} pts`}
                          />
                          <Bar dataKey="n" fill="var(--color-gold)" radius={3} />
                        </BarChart>
                      </ResponsiveContainer>
                    ) : (
                      <p className="text-sm text-mist">Solve a legal ticket to see the distribution.</p>
                    )}
                  </div>
                  {dist ? (
                    <dl className="mt-2 grid grid-cols-3 gap-2 text-center text-sm tabular-nums">
                      <div className="rounded-xl bg-ink px-2 py-2">
                        <dt className="text-xs text-mist">p10</dt>
                        <dd>{pts(dist.p10)}</dd>
                      </div>
                      <div className="rounded-xl bg-ink px-2 py-2">
                        <dt className="text-xs text-mist">Median</dt>
                        <dd>{pts(dist.p50)}</dd>
                      </div>
                      <div className="rounded-xl bg-ink px-2 py-2">
                        <dt className="text-xs text-mist">p90</dt>
                        <dd>{pts(dist.p90)}</dd>
                      </div>
                    </dl>
                  ) : null}
                </article>
                <Rules salary={salary} lineup={solved.lineup} maxOrder={maxOrder} />
              </div>
            </section>
          ) : null}

          {view === "pool" ? (
            <section className="rounded-2xl border border-line bg-field">
              <div className="flex flex-col gap-3 border-b border-line p-4 sm:flex-row sm:items-center">
                <input
                  value={query}
                  onChange={(e) => setQuery(e.target.value)}
                  placeholder="Search the pool"
                  className="min-h-11 flex-1 rounded-xl border border-line bg-ink px-3 text-sm text-chalk outline-none"
                />
                <div className="flex flex-wrap gap-2">
                  {(
                    [
                      ["floor", "Floor"],
                      ["mean", "Mean"],
                      ["std", "Stdev"],
                      ["salary", "Salary"],
                    ] as const
                  ).map(([key, label]) => (
                    <button
                      key={key}
                      type="button"
                      className={
                        sortKey === key
                          ? "min-h-11 rounded-full bg-gold px-3 text-sm font-medium text-ink"
                          : "min-h-11 rounded-full border border-line px-3 text-sm"
                      }
                      onClick={() => setSortKey(key)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
              </div>
              <div className="overflow-x-auto">
                <table className="w-full min-w-3xl text-left text-sm">
                  <thead className="text-xs tracking-widest text-mist uppercase">
                    <tr>
                      <th className="px-4 py-3 font-medium">Player</th>
                      <th className="px-3 py-3 font-medium">Pos</th>
                      <th className="px-3 py-3 font-medium">Order</th>
                      <th className="px-3 py-3 font-medium">Salary</th>
                      <th className="px-3 py-3 font-medium">Mean</th>
                      <th className="px-3 py-3 font-medium">Stdev</th>
                      <th className="px-3 py-3 font-medium">Floor</th>
                    </tr>
                  </thead>
                  <tbody>
                    {rows.map(({ p, floor, in: inside }) => {
                      const blocked = !p.isPitcher && p.order > maxOrder;
                      return (
                        <tr key={p.id} className="border-t border-line">
                          <td className="px-4 py-3">
                            <button type="button" className="text-left" onClick={() => setSelectedId(p.id)}>
                              <span className="block font-medium text-chalk">
                                {p.name}
                                {inside ? <span className="ml-2 text-xs text-gold">In</span> : null}
                              </span>
                              <span className="text-xs text-mist">
                                {p.team} vs {p.opp}
                                {blocked ? " · blocked by order cut" : ""}
                              </span>
                            </button>
                          </td>
                          <td className="px-3 py-3 tabular-nums text-mist">{p.slots.join("/")}</td>
                          <td className="px-3 py-3 tabular-nums">{p.isPitcher ? "SP" : p.order}</td>
                          <td className="px-3 py-3 tabular-nums">{money(p.salary)}</td>
                          <td className="px-3 py-3 tabular-nums">{pts(p.mean)}</td>
                          <td className="px-3 py-3 tabular-nums text-risk">{pts(p.std)}</td>
                          <td className="px-3 py-3 tabular-nums text-gold">{pts(floor)}</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </section>
          ) : null}

          {view === "math" && selected ? (
            <Matchup player={selected} players={data.players} league={data.slate.league} />
          ) : null}

          <section className="grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {data.slate.games.map((g) => (
              <article key={g.id} className="rounded-2xl border border-line bg-field px-4 py-3">
                <div className="flex items-baseline justify-between gap-3">
                  <h3 className="font-medium text-chalk">{g.label}</h3>
                  <span className="text-xs text-mist">{g.status}</span>
                </div>
                <p className="mt-1 text-xs text-mist">
                  {g.awayArm?.name ?? "TBD"} · {g.homeArm?.name ?? "TBD"}
                </p>
                <p className="mt-2 text-xs tabular-nums text-chalk">
                  Lineups {g.awayOrder >= 9 ? "away posted" : "away waiting"} / {g.homeOrder >= 9 ? "home posted" : "home waiting"}
                </p>
                {g.weather ? <p className="mt-1 text-xs text-mist">{g.weather}</p> : null}
              </article>
            ))}
          </section>
        </div>
      ) : null}
    </main>
  );
}

function ordinal(n: number) {
  const mod = n % 10;
  if (n % 100 >= 11 && n % 100 <= 13) return `${n}th`;
  if (mod === 1) return `${n}st`;
  if (mod === 2) return `${n}nd`;
  if (mod === 3) return `${n}rd`;
  return `${n}th`;
}

function Rules({
  salary,
  lineup,
  maxOrder,
}: {
  salary: number;
  lineup: { slot: Slot; player: PoolPlayer }[] | null;
  maxOrder: number;
}) {
  const players = lineup?.map((a) => a.player) ?? [];
  const arms = players.filter((p) => p.isPitcher);
  const hitters = players.filter((p) => !p.isPitcher);
  const games = new Set(arms.map((p) => p.gameId));
  const counts: Record<string, number> = {};
  for (const h of hitters) counts[h.team] = (counts[h.team] ?? 0) + 1;
  const facing = hitters.some((h) => arms.some((a) => a.opp === h.team));
  const deep = hitters.some((h) => h.order > maxOrder);
  const slotsOk =
    lineup?.length === 10 &&
    lineup.filter((a) => a.slot === "P").length === 2 &&
    lineup.filter((a) => a.slot === "OF").length === 3;
  const rules = [
    [salary > 0 && salary <= 50000, "Salary at or under $50,000"],
    [!!slotsOk, "2 P, C, 1B, 2B, 3B, SS, 3 OF"],
    [arms.length === 2 && games.size === 2, "Starters from different games"],
    [hitters.length > 0 && !facing, "No hitter facing a rostered arm"],
    [Object.values(counts).every((n) => n <= 3), "At most three hitters from one club"],
    [hitters.length > 0 && !deep, `Hitters batting 1–${maxOrder} only`],
  ] as const;
  return (
    <article className="rounded-2xl border border-line bg-field p-4">
      <div className="flex items-center gap-2">
        <ShieldCheck className="size-4 text-gold" aria-hidden="true" />
        <h3 className="text-sm font-medium">Cash rules</h3>
      </div>
      <ul className="mt-3 flex flex-col gap-2 text-sm">
        {rules.map(([ok, label]) => (
          <li key={label} className="flex items-start gap-2">
            <span className={ok ? "mt-1 size-2 shrink-0 rounded-full bg-gold" : "mt-1 size-2 shrink-0 rounded-full bg-risk"} />
            <span className={ok ? "text-chalk" : "text-mist"}>{label}</span>
          </li>
        ))}
      </ul>
    </article>
  );
}

function Matchup({
  player,
  players,
  league,
}: {
  player: PoolPlayer;
  players: PoolPlayer[];
  league: DeskData["slate"]["league"];
}) {
  const foe = players.find((p) => p.isPitcher && p.gameId === player.gameId && p.team === player.opp);
  const pitcherRates = player.isPitcher ? player.rates : (foe?.rates ?? league);
  const batterRates = player.isPitcher ? league : player.rates;
  const dist = applyPlatoon(
    matchupDist(batterRates, pitcherRates, league),
    player.isPitcher ? "R" : player.hand,
    player.isPitcher ? player.hand : (foe?.hand ?? "R"),
  );
  const re = useMemo(() => runExpectancy(dist), [dist]);
  const title = player.isPitcher
    ? `${player.name} allowed rates vs a league bat`
    : `${player.name} vs ${foe?.name ?? "league pitching"}`;

  return (
    <section className="grid gap-4 lg:grid-cols-2">
      <article className="rounded-2xl border border-line bg-field p-5">
        <p className="text-xs tracking-widest text-gold uppercase">Log5</p>
        <h2 className="font-display mt-1 text-3xl">{title}</h2>
        <p className="mt-2 text-sm leading-6 text-mist">
          Prob = (B × P / L) / (B × P / L + (1 − B) × (1 − P) / (1 − L)). That is Bill James Log5 — it
          stays at the league rate when batter and pitcher are both average, then the plate appearance is rescaled to one.
        </p>
        <ul className="mt-4 flex flex-col gap-3">
          {RATE_ROWS.map(([key, label]) => {
            const b = batterRates[key];
            const p = pitcherRates[key];
            const l = league[key];
            const isolated = log5(b, p, l);
            return (
              <li key={key}>
                <div className="flex items-baseline justify-between text-sm">
                  <span>{label}</span>
                  <span className="tabular-nums text-gold">{(dist[key] * 100).toFixed(1)}%</span>
                </div>
                <div className="mt-1 h-1.5 overflow-hidden rounded-full bg-ink">
                  <div className="h-full bg-gold" style={{ width: `${Math.min(100, dist[key] * 220)}%` }} />
                </div>
                <p className="mt-1 text-xs tabular-nums text-mist">
                  B {(b * 100).toFixed(1)} · P {(p * 100).toFixed(1)} · L {(l * 100).toFixed(1)} · raw{" "}
                  {(isolated * 100).toFixed(1)}
                </p>
              </li>
            );
          })}
        </ul>
      </article>
      <article className="rounded-2xl border border-line bg-field p-5">
        <p className="text-xs tracking-widest text-gold uppercase">24-state chain</p>
        <h2 className="font-display mt-1 text-3xl">Run expectancy</h2>
        <p className="mt-2 text-sm leading-6 text-mist">
          Bases empty through loaded, zero outs through two. Same matchup every plate appearance, until the third out.
        </p>
        <div className="mt-4 overflow-x-auto">
          <table className="w-full min-w-xl text-center text-xs tabular-nums">
            <thead>
              <tr className="text-mist">
                <th className="py-2 text-left font-medium">Outs</th>
                {BASE_LABELS.map((label) => (
                  <th key={label} className="py-2 font-medium">
                    {label}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {[0, 1, 2].map((outs) => (
                <tr key={outs} className="border-t border-line">
                  <th className="py-2 text-left font-medium text-mist">{outs}</th>
                  {BASE_LABELS.map((_, mask) => (
                    <td key={mask} className="py-2 text-chalk">
                      {re[outs * 8 + mask].toFixed(2)}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <p className="mt-4 text-sm text-chalk">
          Projected {pts(player.mean)} points, stdev {pts(player.std)}, floor {pts(floorOf(player.mean, player.std, 0.5))}.
        </p>
      </article>
    </section>
  );
}
