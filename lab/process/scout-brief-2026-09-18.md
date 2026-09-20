# Scout Brief — DK MLB Classic
- **Date:** 2026-09-18
- **Slate:** 13-game Classic (`dk-classic-player-pool.csv`, 1205 players)
- **Method:** FREE only (MLB Stats API, FantasyPros, ESPN scoreboard)
- **Timestamp:** 2026-09-18 05:47 PM CDT

## Game table

| Matchup | Away SP | Home SP | Status | Weather | Park note | Total / lean |
|---------|---------|---------|--------|---------|-----------|--------------|
| ATH@CLE | Mason Barnett | Daniel Espino | Probable / FP Conf LU | PC 69F | Progressive — slight P | 8.0 · CLE -244 |
| ATL@HOU | Tyler Mahle | Peter Lambert | Probable / FP Conf LU | Roof 72F | Daikin — slight H (LF) | 8.0 · ATL -120 |
| BOS@TB | Ranger Suarez | Ian Seymour | Probable / FP Conf LU | Dome 72F | Trop — P / indoor | 7.0 · TB -137 |
| DET@CWS | Andrew Sears | David Sandlin | Probable / FP Conf LU | PC 69F | Rate Field — H | 8.0 · CWS -132 |
| MIA@SD | Tyler Phillips | Nick Pivetta | Probable · **MIA proj LU** | n/a | Petco — strong P | 7.5 · SD -219 |
| MIL@BAL | Dustin May | Cade Povich | Probable / FP Conf LU | PC 79F | Camden — H (RF) | 8.5 · MIL -149 |
| MIN@LAA | Connor Prielipp | Grayson Rodriguez | Probable · **MIN proj LU** | Clear 74F | Angel — neutral/P | 8.0 · MIN -115 |
| NYY@ARI | Gerrit Cole | Eduardo Rodriguez | Probable / FP Conf LU | Roof 72F | Chase — H (roof) | 7.5 · pick'em |
| PHI@NYM | Tim Mayza | Zac Thornton | Probable / FP Conf LU | Cloudy 77F | Citi — P | 8.5 · NYM -131 |
| SEA@COL | Bryan Woo | Gabriel Hughes | Probable / FP Conf LU | PC 70F | **Coors — extreme H** | **10.5** · SEA -193 |
| SF@LAD | Cesar Perdomo | Tyler Glasnow | Probable / FP Conf LU | Cloudy 70F | Dodger — slight P | 8.0 · LAD -314 |
| TOR@TEX | Dylan Cease | Kumar Rocker | Probable / FP Conf LU | Roof 74F | Globe Life — neutral/H | 7.5 · TOR -136 |
| WSH@STL | Cade Cavalli | Kyle Leahy | Probable / FP Conf LU | PC **90F** | Busch — slight P | 7.5 · pick'em |

SP names aligned **MLB Stats API = FantasyPros**. No TBD SPs on desk slate.

## Top flags / conflicts
1. **DK salary leaders ≠ today’s SPs** — Misiorowski ($11.5k), Schlittler ($11k), Sale ($10.7k), Luzardo/Sanchez ($10.5k), Yamamoto/Skubal ($10.5k) are pool noise; do not auto-lock.
2. **DK position mis-tags:** Tim Mayza, David Sandlin, Gabriel Hughes listed as **RP** in pool but are today’s SPs (FP/MLB) — builder must allow RP→SP or manual override.
3. **Unconfirmed batting orders:** MIN (projected), MIA (projected) on FantasyPros; all other desk teams Confirmed at scrape.
4. **Stack magnet:** SEA@COL OU **10.5** at Coors — clearest run environment on slate.
5. **Pitcher spots:** Glasnow (LAD -314), Pivetta (SD -219), Espino (CLE -244), Cease (TOR) are the clearest SP leverage favorites vs chalk-salary traps above.
6. Off-slate same day (ignore for Classic 13): CHC@CIN, KC@PIT (in progress).

## Free sources used
| Path | Role |
|------|------|
| `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-18.json` (+ `.csv`, `.NOTE.md`) | Schedule / SP / weather |
| `/home/box/mlb-dfs/sources/fantasypros-lineups-2026-09-18.html` | Lineups HTML |
| `/home/box/mlb-dfs/sources/fantasypros-probables-2026-09-18.csv` (+ SP summary + NOTE) | Parsed SP + orders |
| `/home/box/mlb-dfs/sources/fantasypros-probable-pitchers.html` | Probables grid |
| `/home/box/mlb-dfs/sources/espn-scoreboard-2026-09-18.json` | DK odds via ESPN |
| `/home/box/mlb-dfs/sources/vegas-lines-2026-09-18.csv` (+ NOTE) | Totals / ML / RL |
| `/home/box/mlb-dfs/sources/SOURCES-INDEX-2026-09-18.md` | Index |
| `/home/box/mlb-dfs/projections-tonight.csv` | On-disk desk projs (1205) — not a fresh free scrape |
| Pool: `/home/box/mlb-dfs/dk-classic-player-pool.csv` | DK Classic 13 |

**Not used today:** DFF CSV on disk is **2026-09-11**; VSIN free games API returned shell HTML (no lines).

## Caveats
- FREE sources only; no paid walls/logins.
- Probables/orders can change through lock — re-pull FP for MIN/MIA.
- ESPN implied team totals are a heuristic split of OU (not VSIN EST).
- Park notes = simple public knowledge, not a full PF model.
- Do **not** trust DK top SP salaries as today’s starters.
