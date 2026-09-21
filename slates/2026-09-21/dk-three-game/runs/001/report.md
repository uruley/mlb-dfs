# September 21 model cash build

Status: PROVISIONAL. Cash CLI passed its implemented checks, but those checks do not establish complete real-world readiness. Both selected pitchers are in MIN@SF; those batting orders were not posted at collection. Pitch-count restrictions have not been independently cleared. Recheck before use. No contest submitted.

Model: repository build_projections.py functions, dynamically supplied today's probable pitchers and pool. Hitter formulas remain salary/order-rank proxies; no independent hitter-stat projection upgrade is claimed. Pitcher skill uses the frozen original model rate; workload uses up to five recent MLB starts via the PR #1 workload module. Stale/no recent workload excludes Yesavage, Herz and Ryan. No manual player selections.

Optimizer: cash.cli from PR #1, with a local three-line constraint rejecting hitters opposing selected pitchers. Search hit its node budget, so output is heuristic_bounded, not proven optimal. Forecast 95.0561 points, not a floor or probability of 100. Payout probability has not been calculated. Field size 32; multiplier paid places unknown. Also intended for head-to-heads and double-up.

Input: user's DKSalaries (52).csv, 298 players, three games. 36 posted hitters eligible; unposted MIN/SF hitters excluded. Local slate key is derived from template SHA256, not asserted to be DraftKings contest ID.

Source: https://statsapi.mlb.com/api/v1/schedule?sportId=1&date=2026-09-21&hydrate=probablePitcher and game boxscores / pitcher game logs saved in the run bundle. FantasyPros weather cross-check: https://www.fantasypros.com/mlb/lineups/ .

CSV is Lineup Upload, not Entry Upload (no Entry IDs supplied).

## Lineup CSV

```csv
P,P,C,1B,2B,3B,SS,OF,OF,OF
Zebby Matthews (44217763),Blade Tidwell (44217778),Dillon Dingler (44217602),Spencer Torkelson (44217619),Gleyber Torres (44217609),Kazuma Okamoto (44217604),Gunnar Henderson (44217594),James Wood (44217588),Riley Greene (44217595),Brett Bateman (44217607)
```
