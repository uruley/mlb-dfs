# MLB Stats API ingest — 2026-09-18

## Summary
- Slate date: **2026-09-18**
- Ingest time (UTC): **2026-09-18T22:46:00Z** approx
- Games on full MLB schedule: **15**
- Desk DK Classic 13-game slate present: **13**/13 (ARI as AZ in some feeds; desk uses ARI)
- Off-slate same day: CHC@CIN, KC@PIT (in progress at scrape)

## Method / URL
`https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=09/18/2026&hydrate=probablePitcher,weather,venue`

FREE public API — no auth.

## Outputs
- `mlb-statsapi-schedule-2026-09-18.json`
- `mlb-statsapi-schedule-2026-09-18.csv`
- this NOTE

## Desk slate probable SPs (Stats API)
| Game | Away SP | Home SP | Weather | Venue |
|------|---------|---------|---------|-------|
| ATH@CLE | Mason Barnett | Daniel Espino | PC 69F | Progressive Field |
| ATL@HOU | Tyler Mahle | Peter Lambert | Roof Closed 72F | Daikin Park |
| BOS@TB | Ranger Suarez | Ian Seymour | Dome 72F | Tropicana Field |
| DET@CWS | Andrew Sears | David Sandlin | PC 69F | Rate Field |
| MIA@SD | Tyler Phillips | Nick Pivetta | (blank) | Petco Park |
| MIL@BAL | Dustin May | Cade Povich | PC 79F | Camden Yards |
| MIN@LAA | Connor Prielipp | Grayson Rodriguez | Clear 74F | Angel Stadium |
| NYY@ARI | Gerrit Cole | Eduardo Rodriguez | Roof Closed 72F | Chase Field |
| PHI@NYM | Tim Mayza | Zac Thornton | Cloudy 77F | Citi Field |
| SEA@COL | Bryan Woo | Gabriel Hughes | PC 70F | Coors Field |
| SF@LAD | Cesar Perdomo | Tyler Glasnow | Cloudy 70F | Dodger Stadium |
| TOR@TEX | Dylan Cease | Kumar Rocker | Roof Closed 74F | Globe Life Field |
| WSH@STL | Cade Cavalli | Kyle Leahy | PC 90F | Busch Stadium |

## Status
All desk games Pre-Game/Warmup at scrape (MIL@BAL Warmup). No TBD SPs on desk slate.

## Caveats
- Probables can still change; cross-check FantasyPros + lock.
- Weather blank for MIA@SD at scrape.
