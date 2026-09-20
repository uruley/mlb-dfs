# Vegas lines — 2026-09-18

## Primary free source
**ESPN public scoreboard API** (no key):
`https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=20260918`
Provider embedded: **DraftKings** ML / RL / totals.

## Outputs
- `espn-scoreboard-2026-09-18.json`
- `vegas-lines-espn-2026-09-18.csv` (raw)
- `vegas-lines-2026-09-18.csv` (enriched w/ implied run split heuristic)
- this NOTE

## VSIN
- `data.vsin.com/mlb/games/?gamedate=2026-09-18` and `/api/mlb/games` returned marketing HTML / redirect shell — **no usable free odds table** this run. Saved `vsin-games-2026-09-18.html` / `.json` (HTML) for audit.

## Desk slate totals (ESPN/DK)
| Game | OU | ML favorite | Away RL |
|------|-----|-------------|---------|
| MIL@BAL | 8.5 | MIL -149 | MIL -1.5 |
| ATH@CLE | 8.0 | CLE -244 | ATH +1.5 |
| BOS@TB | 7.0 | TB -137 | BOS +1.5 |
| PHI@NYM | 8.5 | NYM -131 | PHI +1.5 |
| DET@CWS | 8.0 | CHW -132 | DET +1.5 |
| TOR@TEX | 7.5 | TOR -136 | TOR -1.5 |
| ATL@HOU | 8.0 | ATL -120 | ATL -1.5 |
| SEA@COL | 10.5 | SEA -193 | SEA -1.5 |
| WSH@STL | 7.5 | WSH -112 | pick'em juice |
| MIN@LAA | 8.0 | MIN -115 | near pick'em |
| MIA@SD | 7.5 | SD -219 | MIA +1.5 |
| NYY@ARI | 7.5 | ARI -111 | pick'em |
| SF@LAD | 8.0 | LAD -314 | SF +1.5 |

## Caveats
- Lines move; snapshot only.
- Implied team totals = crude ML-probability split of OU (not VSIN EST Score).
- No paid Odds API / FanDuel Research.
