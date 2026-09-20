# FantasyPros Probables / Lineups — 2026-09-11

## Source
- **Primary URL:** https://www.fantasypros.com/mlb/lineups/2026-09-11/
- **Probables grid (cross-check):** https://www.fantasypros.com/mlb/probable-pitchers.php
- **Method:** Public WebFetch of free FantasyPros MLB Daily Lineups page + Probable Pitchers grid (no login, no paywall).
- **Scraped at (UTC):** 2026-09-11T16:54:51Z

## Row counts
- **CSV total rows:** 300 (header excluded)
- **Starting pitchers (role=SP):** 30 (24 on desk 12-game slate)
- **Hitters with batting order (role=H):** 270 (216 on desk slate; 9 per team when posted)

## Desk slate coverage (12 games)
Games from desk context: BAL@TOR, CIN@MIL, CLE@MIN, CWS@STL, HOU@TB, KC@BOS, LAD@MIA, NYM@NYY, PHI@ATL, SD@SF, SEA@ATH, TEX@ARI.

**All 12 covered** with named FantasyPros starters (ATH used for Athletics; DFF uses OAK).

| Game | Away SP | Home SP |
|------|---------|---------|
| BAL@TOR | Chris Bassitt (R) | Max Scherzer (R) |
| CIN@MIL | Andrew Abbott (L) | Dustin May (R) |
| CLE@MIN | Parker Messick (L) | Taj Bradley (R) |
| CWS@STL | Anthony Kay (L) | Matthew Liberatore (L) |
| HOU@TB | Miguel Ullola (R) | Drew Rasmussen (R) |
| KC@BOS | Seth Lugo (R) | Sonny Gray (R) |
| LAD@MIA | Blake Snell (L) | Ryan Gusto (R) |
| NYM@NYY | Nolan McLean (R) | Carlos Rodon (L) |
| PHI@ATL | Aaron Nola (R) | Chris Sale (L) |
| SD@SF | Robbie Ray (L) | Anthony Molina (R) |
| SEA@ATH | George Kirby (R) | Jeffrey Springs (L) |
| TEX@ARI | Kumar Rocker (R) | Merrill Kelly (R) |

Also present on FantasyPros same-day page (not on desk 12-game slate): PIT@CHC, COL@DET, LAA@WSH — included with `on_desk_slate=N`.

## Pitchers vs DFF notes
- DFF marks Blake Snell and Kumar Rocker without `starting_pitcher=YES`; FantasyPros lists both as the projected SPs for LAD and TEX.
- HOU: FantasyPros lists **Miguel Ullola**; DFF also has Ethan Pecko marked YES alongside Ullola — FP does not list Pecko for this date.
- No slate pitcher blank/TBD on FantasyPros for the 12 games.

## Status / caveats
- Only **PIT@CHC** marked **Confirmed Lineup** on the lineups page at scrape time; all other batting orders are **Projected**.
- Pitcher `status` is `confirmed` only for PIT/CHC SPs; all other SPs are `probable` (not yet confirmed on the FP lineups page).
- `hitter_order` is blank on SP rows; filled 1–9 on hitter rows.
- `hand` = pitcher throwing hand; `bats` = hitter bats (L/R/B).
- Lineups can change until ~2 hours before first pitch; re-scrape closer to lock.
- Free public pages only; no paywall encountered.
- ATH abbr used for Athletics to match desk slate labeling (DFF file uses OAK).

## SP conflict recheck — 2026-09-11T22:33Z
- Live FP lineups/probables (not full CSV re-scrape): LAD **Blake Snell** Confirmed; TEX **MacKenzie Gore** (was Rocker in 16:54Z CSV); HOU still **Miguel Ullola**.
- Probable grid: Rocker moved to Sat 9/12 @ARI; Gore owns Fri.

## SP conflict recheck — 2026-09-12T00:09Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 22:33Z.

## SP conflict recheck — 2026-09-12T00:34Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 00:09Z.

## SP conflict recheck — 2026-09-12T00:56Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 00:34Z.

## SP conflict recheck — 2026-09-12T01:34Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 00:56Z.

## SP conflict recheck — 2026-09-12T02:04Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 01:34Z.

## SP conflict recheck — 2026-09-12T02:38Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 02:04Z.

## SP conflict recheck — 2026-09-12T03:05Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 02:38Z.

## SP conflict recheck — 2026-09-12T03:25Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 03:05Z.

## SP conflict recheck — 2026-09-12T04:04Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 03:25Z.

## SP conflict recheck — 2026-09-12T04:29Z
- Live FP lineups + probable grid: LAD Snell Confirmed; TEX Gore (Rocker Sat); HOU Ullola. No SP delta vs 04:04Z.
