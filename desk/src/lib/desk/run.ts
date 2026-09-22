import { moments, pricePlayers, simulateGames, type PoolPlayer } from "@/lib/desk/engine";
import { loadSlate, type Slate } from "@/lib/desk/slate";

export const SIMS = 10000;

export interface DeskData {
  slate: Slate;
  players: PoolPlayer[];
  sims: number;
}

export async function buildDesk(
  date: string | undefined,
  onProgress: (message: string, pct: number) => void,
): Promise<DeskData> {
  onProgress("Reading the board", 0.08);
  const slate = await loadSlate(date);
  if (!slate.games.length) {
    throw new Error("No open games on this date. The slate may already be final.");
  }
  onProgress("Running 10,000 half-inning chains", 0.18);
  const samples = await simulateGames(slate.games, slate.league, SIMS, 0x5eed22, (done, total) => {
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
  return { slate, players, sims: SIMS };
}
