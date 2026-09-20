# MLB Stats API ingest — 2026-09-11

## Summary
- Slate date requested: **2026-09-11**
- Ingest time (UTC): **2026-09-11 16:54:58Z**
- Games on schedule: **15** (API full day)
- Desk expected-slate games present: **12**/12 (ARI listed as **AZ** by Stats API)
- Games with confirmed batting orders: **1**
- Games missing / unconfirmed orders: **14**
- Games with weather populated: **1**
- Lineup player rows written: **18**

## Method / URLs
1. Schedule (hydrate `probablePitcher,lineups,weather,venue`):
   `https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=09/11/2026&hydrate=probablePitcher,lineups,weather,venue`
2. Per-game live feed (confirmed `battingOrder` when posted):
   `https://statsapi.mlb.com/api/v1.1/game/{gamePk}/feed/live`
3. Boxscore cross-check:
   `https://statsapi.mlb.com/api/v1/game/{gamePk}/boxscore`

FREE public MLB Stats API (`statsapi.mlb.com`) — no auth required. Hydrate params succeeded as requested.

## Outputs
- `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- `/home/box/mlb-dfs/sources/mlb-statsapi-lineups-2026-09-11.csv`
- `/home/box/mlb-dfs/sources/NOTE.md` (this file)

## Probable starting pitchers
- PIT@CHC: **Wilber Dotel** vs **Shota Imanaga**
- COL@DET: **Mason Adams** vs **Framber Valdez**
- LAA@WSH: **Yusei Kikuchi** vs **Cade Cavalli**
- NYM@NYY: **Nolan McLean** vs **Carlos Rodón**
- BAL@TOR: **Chris Bassitt** vs **Max Scherzer**
- KC@BOS: **Seth Lugo** vs **Sonny Gray**
- HOU@TB: **Miguel Ullola** vs **Drew Rasmussen**
- LAD@MIA: **MISSING** vs **Ryan Gusto**
- PHI@ATL: **Aaron Nola** vs **Chris Sale**
- CIN@MIL: **Andrew Abbott** vs **Dustin May**
- CLE@MIN: **Parker Messick** vs **Taj Bradley**
- CWS@STL: **Anthony Kay** vs **Matthew Liberatore**
- SEA@ATH: **George Kirby** vs **Jeffrey Springs**
- TEX@AZ: **MISSING** vs **MISSING**
- SD@SF: **Robbie Ray** vs **Anthony Molina**

## Confirmed lineups
- CONFIRMED: PIT@CHC (824631)
- Confirmed source: live feed `battingOrder` while status Pre-Game (official posted order).

## Missing / unconfirmed batting orders (FLAGGED)
- UNCONFIRMED/MISSING: COL@DET (824227) — no batting order posted
- UNCONFIRMED/MISSING: LAA@WSH (822684) — no batting order posted
- UNCONFIRMED/MISSING: NYM@NYY (823498) — no batting order posted
- UNCONFIRMED/MISSING: BAL@TOR (822767) — no batting order posted
- UNCONFIRMED/MISSING: KC@BOS (824711) — no batting order posted
- UNCONFIRMED/MISSING: HOU@TB (822930) — no batting order posted
- UNCONFIRMED/MISSING: LAD@MIA (823817) — no batting order posted
- UNCONFIRMED/MISSING: PHI@ATL (824873) — no batting order posted
- UNCONFIRMED/MISSING: CIN@MIL (823736) — no batting order posted
- UNCONFIRMED/MISSING: CLE@MIN (823659) — no batting order posted
- UNCONFIRMED/MISSING: CWS@STL (823012) — no batting order posted
- UNCONFIRMED/MISSING: SEA@ATH (824954) — no batting order posted
- UNCONFIRMED/MISSING: TEX@AZ (825036) — no batting order posted
- UNCONFIRMED/MISSING: SD@SF (823173) — no batting order posted

## Weather
- PIT@CHC: Sunny; 76F; wind 6 mph, In From RF

## Desk expected slate vs API
Expected: BAL@TOR, CIN@MIL, CLE@MIN, CWS@STL, HOU@TB, KC@BOS, LAD@MIA, NYM@NYY, PHI@ATL, SD@SF, SEA@ATH, TEX@ARI

On expected slate (`on_expected_slate=Y`): 12
- NYM@NYY (gamePk 823498)
- BAL@TOR (gamePk 822767)
- KC@BOS (gamePk 824711)
- HOU@TB (gamePk 822930)
- LAD@MIA (gamePk 823817)
- PHI@ATL (gamePk 824873)
- CIN@MIL (gamePk 823736)
- CLE@MIN (gamePk 823659)
- CWS@STL (gamePk 823012)
- SEA@ATH (gamePk 824954)
- TEX@AZ (gamePk 825036)
- SD@SF (gamePk 823173)

Extra games not on desk list (`on_expected_slate=N`): 3
- PIT@CHC (gamePk 824631)
- COL@DET (gamePk 824227)
- LAA@WSH (gamePk 822684)

Note: Diamondbacks abbreviate as **AZ** in Stats API (desk list used ARI); CSV keeps API abbrev; slate flag treats AZ≡ARI.

## Caveats
- Most games are still **Scheduled** (not Pre-Game); official batting orders are not posted yet. Empty lineups are TBD, not scratches — orders usually post ~2–4 hours before first pitch (earlier for day games).
- Only `confirmed=Y` when live feed (or Pre-Game hydrate) provides a batting order. Projected/fantasy lineups are **not** invented here.
- Probable pitchers can change; blanks mean not yet listed (TBD / injury / unannounced).
- Weather often empty until closer to first pitch; indoor/retractable venues may stay sparse.
- Full MLB day has 15 games; desk expected list is 12 — filter `on_expected_slate=Y` for desk slate only.
- No DFS lineups built — schedule / probable / lineup ingest only.

## Missing probables detail
- LAD@MIA: away=MISSING, home=Ryan Gusto
- TEX@AZ: away=MISSING, home=MISSING

## SP conflict recheck — 2026-09-11T22:33Z
- Schedule CSV refreshed from same hydrate URL.
- LAD@MIA: away probable filled → **Blake Snell** (was MISSING).
- TEX@AZ: away → **MacKenzie Gore**, home → **Merrill Kelly** (both were MISSING; prior FP Rocker overwritten).
- HOU@TB: still **Miguel Ullola** vs Drew Rasmussen.

## SP conflict recheck — 2026-09-12T00:09Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only moves (not SP flips): PHI Delayed→In Progress; CIN Warmup→In Progress; CLE Pre-Game→Warmup.

## SP conflict recheck — 2026-09-12T00:34Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only moves (not SP flips): CLE Warmup→In Progress; CWS Pre-Game→Delayed Start.

## SP conflict recheck — 2026-09-12T00:56Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk still 8 In Progress, 1 Delayed Start (CWS@STL), 3 Pre-Game (SD@SF, SEA@ATH, TEX@AZ).

## SP conflict recheck — 2026-09-12T01:34Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 8 In Progress, 1 Game Over (HOU@TB), 2 Warmup (SEA@ATH, TEX@AZ), 1 Pre-Game (SD@SF).

## SP conflict recheck — 2026-09-12T02:04Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 8 In Progress, 2 Final (KC@BOS, HOU@TB), 1 Game Over (NYM@NYY), 1 Warmup (SD@SF).

## SP conflict recheck — 2026-09-12T02:38Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 6 Final, 6 In Progress (PHI@ATL, CLE@MIN, CWS@STL, SEA@ATH, TEX@AZ, SD@SF).

## SP conflict recheck — 2026-09-12T03:05Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 6 Final, 5 In Progress, 1 Game Over (CLE@MIN).

## SP conflict recheck — 2026-09-12T03:25Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 8 Final, 4 In Progress (CWS@STL, SEA@ATH, TEX@AZ, SD@SF).

## SP conflict recheck — 2026-09-12T04:04Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 8 Final, 4 In Progress (CWS@STL, SEA@ATH, TEX@AZ, SD@SF).

## SP conflict recheck — 2026-09-12T04:29Z
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status-only: desk 8 Final, 1 Game Over, 3 In Progress (SEA@ATH, TEX@AZ, SD@SF); CWS@STL Game Over.

## SP conflict recheck — 2026-09-12T05:10:23Z (FINAL / deadline)
- Schedule CSV refreshed. Watch SPs unchanged: Snell, Gore, Ullola.
- Status: LAD/TEX/HOU watch games all **Final**. Desk mostly Final; SD@SF still In Progress.
- Routine deleted per deadline (after 2026-09-11 23:59 CDT).
