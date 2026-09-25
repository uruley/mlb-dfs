import { FULL_MODEL, anchorToVegas, moments, pricePlayers, simulateGames, type ModelOptions, type PoolPlayer } from "@/lib/desk/engine";
import { loadSlate, pitchLimitFrom, type Slate } from "@/lib/desk/slate";

export const SIMS = 10000;

export interface DeskData {
  slate: Slate;
  players: PoolPlayer[];
  sims: number;
}

export async function buildDesk(
  date: string | undefined,
  onProgress: (message: string, pct: number) => void,
  overrides: Record<number, { ip: number; at: string }> = {},
  anchor = true,
  opts: { model?: ModelOptions; includeFinal?: boolean; sims?: number } = {},
): Promise<DeskData> {
  onProgress("Reading the board", 0.08);
  const model = opts.model ?? FULL_MODEL;
  const slate = await loadSlate(date, { model, includeFinal: opts.includeFinal });
  if (!slate.games.length) {
    throw new Error("No open games on this date. The slate may already be final.");
  }
  for (const game of slate.games) {
    for (const arm of [game.awayArm, game.homeArm]) {
      const over = arm ? overrides[arm.id] : undefined;
      if (!arm || !over) continue;
      arm.ipPerStart = over.ip;
      arm.targetBf = Math.round(Math.min(32, Math.max(6, over.ip * 4.35)));
      arm.role = over.ip < 2.2 ? "opener" : over.ip < 4.5 ? "bulk" : "starter";
      arm.workloadSource = `Manual ${over.ip.toFixed(1)} innings, set ${over.at}.`;
      const hook = pitchLimitFrom([], over.ip);
      arm.pitchLimit = hook.limit;
      arm.pitchSd = hook.sd;
    }
  }
  if (anchor && model.vegas) {
    onProgress("Anchoring team runs to Vegas totals", 0.14);
    await new Promise((resolve) => setTimeout(resolve, 0));
    anchorToVegas(slate.games, slate.league);
  } else {
    for (const g of slate.games) {
      g.awayMul = 1;
      g.homeMul = 1;
    }
  }
  onProgress("Running 10,000 half-inning chains", 0.18);
  const sims = opts.sims ?? SIMS;
  const samples = await simulateGames(slate.games, slate.league, sims, 0x5eed22, (done, total) => {
    onProgress(`Simulating ${done} of ${total} games`, 0.18 + (done / total) * 0.7);
  });
  onProgress("Pricing the floor", 0.92);
  const players: PoolPlayer[] = [];
  const pushHitter = (h: (typeof slate.games)[number]["awayHitters"][number]) => {
    const row = samples.get(h.id);
    if (!row) return;
    const { mean, std } = moments(row);
    players.push({
      id: h.id,
      dkId: "",
      name: h.name,
      team: h.team,
      opp: h.opp,
      gameId: h.gameId,
      slots: h.slots,
      order: h.order,
      isPitcher: false,
      hand: h.hand,
      rates: h.rates,
      salary: 3000,
      mean,
      std,
      samples: row,
      pricedFrom: "model",
      role: "bat",
      ipPerStart: null,
      workloadSource: "",
    });
  };
  const pushArm = (arm: (typeof slate.games)[number]["awayArm"]) => {
    if (!arm) return;
    const row = samples.get(arm.id);
    if (!row) return;
    const { mean, std } = moments(row);
    players.push({
      id: arm.id,
      dkId: "",
      name: arm.name,
      team: arm.team,
      opp: arm.opp,
      gameId: arm.gameId,
      slots: ["P"],
      order: 0,
      isPitcher: true,
      hand: arm.hand,
      rates: arm.rates,
      salary: 7000,
      mean,
      std,
      samples: row,
      pricedFrom: "model",
      role: arm.role,
      ipPerStart: arm.ipPerStart,
      workloadSource: arm.workloadSource,
    });
  };
  for (const g of slate.games) {
    g.awayHitters.forEach(pushHitter);
    g.homeHitters.forEach(pushHitter);
    pushArm(g.awayArm);
    pushArm(g.homeArm);
  }
  pricePlayers(players);
  onProgress("Solving the cash roster", 0.98);
  return { slate, players, sims };
}
