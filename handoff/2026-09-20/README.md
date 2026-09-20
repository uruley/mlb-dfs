# Handoff 2026-09-20 — Grok-run own-model

Ulysses does not have `/home/box`. This session ran the repo own-model
(`build_projections.py` salary/park/probable method) against the uploaded
DK Classic template. Not a Savant live pull. Not PR #1 activation.

- DK product is a **10-game** Classic slate (943 players), not all 15 MLB games.
- Probables for those 10 games: MLB StatsAPI 2026-09-20 (20 announced starters matched).
- Method: same salary-tier IP / hitter curve as `build_projections.py`.
- DK `AvgPointsPerGame` was not used as `proj_fp`.
- Posted batting orders / pitch-count restrictions: not in this runtime.
- `cash.cli` objective if used later: max provisional mean, not 9/31 cash probability.

## Files

- `pool.csv` — normalized DK pool + StatsAPI `game_id`
- `projections.csv` — own-model `proj_fp`
- `pitcher-evidence.json` — announced starters only; IP prior is salary-tier and labeled provisional
- `contest.json` — 31 entrants / 9 paid; other settings unknown

## Hashes

- pool.csv `e8a83c25cb026ccca862870d1aa6cbe9de378d5821908e2e86e0923c9c428a66`
- projections.csv `843d41db3ed45f36878b75f0afb16ca999ce68dcb88a73483d37ae4418c0f5f3`
- pitcher-evidence.json `90633e9e868da13b79702abb045b579b8e25619234d5a64d91722c29e9255574`
