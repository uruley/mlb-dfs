# MLB Stats API ingest — 2026-09-12

## Summary
- Slate date: **2026-09-12**
- Ingest time (UTC): **2026-09-12 19:01 UTC**
- Desk slate games: 5/5 found
- Source: `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=2026-09-12&hydrate=probablePitcher,team,venue`
- FREE public MLB Stats API — no auth.

## Desk slate probable starting pitchers
- LAA@WSH (822685, Pre-Game, Nationals Park): **Walbert Ureña** vs **Andrew Alvarez**
- SD@SF (823170, Pre-Game, Oracle Park): **Michael King** vs **Cesar Perdomo**
- KC@BOS (824712, Pre-Game, Fenway Park): **Randy Dobnak** vs **Ranger Suarez**
- CLE@MIN (823657, Pre-Game, Target Field): **Daniel Espino** vs **Connor Prielipp**
- LAD@MIA (823819, Pre-Game, loanDepot park): **Tyler Glasnow** vs **Tyler Phillips**

All 10 names matched the DK Classic pool (Ureña → pool "Walbert Urena"). Several listed as RP on DK (King, Urena, Alvarez, Perdomo, Dobnak, Espino, Phillips) but tagged as starting SPs from official probablePitcher.

## Output
- `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-12.csv`

## Caveats
- Probables can change; several arms are low-salary / RP-listed (possible opener/bulk).
- Espino (43 PA) and Perdomo (35 PA) have thin 2026 Savant samples.
- Full MLB day has additional games not on this 5-game Classic pool.
