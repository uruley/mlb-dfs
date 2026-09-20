# SP conflict watch — 2026-09-11

- **Checked (UTC):** 2026-09-11T22:33Z (~5:33pm CDT)
- **Sources:** FantasyPros lineups + probable grid (free), MLB Stats API schedule hydrate (free). DFF CSV on disk not re-exported (stale tags still noted).

## Deltas vs last desk state (~16:54Z)

### 1) LAD — Blake Snell — RESOLVED (official)
- **Was:** FP Snell; DFF no `starting_pitcher=YES`; Stats API LAD probable **blank**.
- **Now:** Stats API lists **Blake Snell** vs Ryan Gusto. FP Confirmed Lineup + Snell. Conflict cleared on official feed.
- **Caveat:** On-disk DFF still lacks YES tag for Snell (stale export).

### 2) TEX — Kumar Rocker → MacKenzie Gore — FLIP
- **Was:** FP Rocker; DFF no YES for Rocker; Stats API TEX@AZ both blank.
- **Now:** Stats API + FP both list **MacKenzie Gore** (L) @ ARI vs Merrill Kelly. FP probable grid: Gore Fri / Rocker Sat.
- **Action:** Drop Rocker as Fri SP; treat Gore as TEX starter. TEX batting order still **Projected** on FP; AZ Confirmed. Stats API has AZ lineup, TEX away order not fully hydrated in this pull.

### 3) HOU — Ullola vs Pecko — UNCHANGED
- FP + Stats API still **Miguel Ullola** @ TB vs Rasmussen.
- On-disk DFF still tags **both** Ullola and Pecko `YES`. FP grid: Pecko not until Thu 9/17.
- Dual-tag noise remains on DFF only; official sources agree Ullola.

## Desk slate status (Stats API)
Most 12-game desk games Pre-Game; late West games still open. Routine kept (deadline 23:59 CDT / slate not done).

## Hand-off
Notify MLB Manager + Ulysses: Snell confirmed; **TEX SP flipped to Gore (Rocker off Fri)**; HOU still Ullola.

## Quiet recheck — 2026-09-12T00:09Z (~7:08pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 22:33Z desk state.
- LAD@MIA: still **Blake Snell** (In Progress / FP Confirmed).
- TEX@AZ: still **MacKenzie Gore** (Pre-Game / FP Confirmed; Rocker remains Sat 9/12 on FP grid).
- HOU@TB: still **Miguel Ullola** (In Progress); Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 7 In Progress, 1 Warmup, 4 Pre-Game — not Final; routine kept.
- Action: stay quiet (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T00:34Z (~7:34pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 00:09Z desk state.
- LAD@MIA: still **Blake Snell** (In Progress / FP Confirmed).
- TEX@AZ: still **MacKenzie Gore** (Pre-Game / FP Confirmed; Rocker remains Sat 9/12 on FP grid).
- HOU@TB: still **Miguel Ullola** (In Progress); Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 In Progress, 1 Delayed Start, 3 Pre-Game — not Final; routine kept.
- Action: stay quiet (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T00:56Z (~7:56pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 00:34Z desk state.
- LAD@MIA: still **Blake Snell** (In Progress / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (Pre-Game / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (In Progress) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 In Progress, 1 Delayed Start (CWS@STL), 3 Pre-Game (SD@SF, SEA@ATH, TEX@AZ) — not Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T01:34Z (~8:33pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 00:56Z desk state.
- LAD@MIA: still **Blake Snell** (In Progress / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (Warmup / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Game Over) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 In Progress, 1 Game Over (HOU@TB), 2 Warmup (SEA@ATH, TEX@AZ), 1 Pre-Game (SD@SF) — not Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T02:04Z (~9:03pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 01:34Z desk state.
- LAD@MIA: still **Blake Snell** (In Progress / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (In Progress / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Final) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 In Progress, 2 Final (KC@BOS, HOU@TB), 1 Game Over (NYM@NYY), 1 Warmup (SD@SF) — not all Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T02:38Z (~9:38pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 02:04Z desk state.
- LAD@MIA: still **Blake Snell** (Final / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (In Progress / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Final) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 6 Final, 6 In Progress (PHI@ATL, CLE@MIN, CWS@STL, SEA@ATH, TEX@AZ, SD@SF) — not all Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T03:05Z (~10:04pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 02:38Z desk state.
- LAD@MIA: still **Blake Snell** (Final / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (In Progress / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Final) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 6 Final, 5 In Progress (PHI@ATL, CWS@STL, SEA@ATH, TEX@AZ, SD@SF), 1 Game Over (CLE@MIN) — not all Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T03:25Z (~10:25pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 03:05Z desk state.
- LAD@MIA: still **Blake Snell** (Final / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (In Progress / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Final) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 Final, 4 In Progress (CWS@STL, SEA@ATH, TEX@AZ, SD@SF) — not all Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T04:04Z (~11:04pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 03:25Z desk state.
- LAD@MIA: still **Blake Snell** (Final / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (In Progress / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Final) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 Final, 4 In Progress (CWS@STL, SEA@ATH, TEX@AZ, SD@SF) — not all Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Quiet recheck — 2026-09-12T04:29Z (~11:28pm CDT)
- Stats API + FP lineups/probables: **no SP flips** vs 04:04Z desk state.
- LAD@MIA: still **Blake Snell** (Final / FP Confirmed) vs Ryan Gusto.
- TEX@AZ: still **MacKenzie Gore** (In Progress / FP Confirmed) vs Merrill Kelly; Rocker remains Sat 9/12 on FP grid.
- HOU@TB: still **Miguel Ullola** (Final) vs Drew Rasmussen; Pecko still Thu 9/17 on FP grid; DFF dual-tag not re-exported.
- Desk slate: 8 Final, 1 Game Over, 3 In Progress (SEA@ATH, TEX@AZ, SD@SF) — not all Final; before 23:59 CDT.
- Schedule CSV refreshed: `/home/box/mlb-dfs/sources/mlb-statsapi-schedule-2026-09-11.csv`
- Action: QUIET (no Manager/Ulysses ping).

## Final close — 2026-09-12T05:10:23Z (~12:10am CDT Sat 9/12)
- Past deadline (after 2026-09-11 23:59 America/Chicago). Desk watch SPs **unchanged** vs 04:29Z.
- LAD@MIA: **Blake Snell** Final (6-2).
- TEX@AZ: **MacKenzie Gore** Final (1-9); Rocker was Sat grid only.
- HOU@TB: **Miguel Ullola** Final (1-3); DFF dual-tag Pecko noise never re-exported.
- Desk slate: 11 Final + 1 In Progress (SD@SF only; not a watched SP conflict). Lineups locked; further SP flips N/A for this slate.
- Action: **DELETE** routine `sp-conflict-watch-9-11`. No Manager/Ulysses ping (no SP delta).
