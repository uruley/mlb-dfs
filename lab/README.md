# MLB DFS Science Lab (DraftKings Classic)

Small offline lab under `/home/box/mlb-dfs/lab` for blending free DailyFantasyFuel (DFF) projections with the desk’s own-model file, joining free Baseball Savant expected stats, Monte Carlo–simulating the 50 Classic lineups, and backtesting projection quality.

**No paid APIs.** Inputs are local CSVs on the desk / free public pulls.

## One-command run

From anywhere on the box:

```bash
python3 /home/box/mlb-dfs/lab/blend_projections.py && \
python3 /home/box/mlb-dfs/lab/simulate_lineups.py
```

Or step-by-step:

```bash
cd /home/box/mlb-dfs/lab
python3 blend_projections.py
python3 simulate_lineups.py          # default N=5000
python3 simulate_lineups.py -n 10000 # more sims
```

## Savant / Statcast features

Pull free Baseball Savant expected-statistics + exit-velo/barrels CSVs (browser-like User-Agent), attach teams via MLB StatsAPI, then join onto tonight’s DK pool.

```bash
python3 /home/box/mlb-dfs/lab/fetch_savant.py          # → sources/savant-expected-{batters,pitchers}-2026.csv
python3 /home/box/mlb-dfs/lab/join_savant_features.py  # → lab/features-savant-tonight.csv
python3 /home/box/mlb-dfs/lab/backtest.py --demo
```

### Fetch details

- Expected URL: `expected_statistics?type={batter|pitcher}&year=YYYY&min=…&csv=true`
- Exit-velo/barrels: `statcast?type={batter|pitcher}&year=YYYY&min=…&csv=true`
- Prefers denser `min=1`; also tries `min=q` / `min=50`. Falls back to year−1 if empty (NOTE records it).
- Team map: StatsAPI roster (`AZ`→`ARI`, `OAK`→`ATH`).
- Writes (canonical plural names):
  - `/home/box/mlb-dfs/sources/savant-expected-batters-2026.csv` + `.NOTE.md`
  - `/home/box/mlb-dfs/sources/savant-expected-pitchers-2026.csv` + `.NOTE.md`
- **Present:** xBA, xSLG, xwOBA, xERA (pitchers), barrel%, hard-hit% (`ev95percent`).
- **Blank on these free boards:** K% / BB% / whiff% (columns reserved).

### Join output

`/home/box/mlb-dfs/lab/features-savant-tonight.csv`

Columns include: `dk_id,name,team,salary,savant_name,savant_id,savant_role,xba,xslg,xwoba,xera,pa,hard_hit_pct,barrel_pct,avg_hit_speed,match_kind,match_confidence`

- Match: normalized name + team (accents stripped; `OAK`↔`ATH`, `AZ`↔`ARI`); fuzzy fallback.
- Does **not** modify Builder / Projections scripts.

## Savant projection uplift

Fold joined Savant x-stats into `blend_proj` as a transparent % nudge (does **not** replace salary/matchup stack).

```bash
python3 /home/box/mlb-dfs/lab/project_with_savant.py
# → /home/box/mlb-dfs/projections-savant-tonight.csv
# → lab/projections-savant-tonight-summary.txt
```

### Method (defaults; CLI-tunable)

- **Base** = `blend_proj` (fallback own/dff).
- **Batters** (valid xwOBA): league-anchor z from xwOBA (PA≥50) + optional barrel% (weight ~0.3 of primary).
  - `savant_adj = blend * clip(0.08*z_xwoba + 0.03*z_barrel, ±0.18)`
- **Pitchers** (valid xERA): inverted z from xERA (lower = better); optional hard-hit-against off by default.
  - `savant_adj = blend * clip(0.10*z_xera, ±0.20)`
- No match → `savant_adj=0`, `savant_proj=blend_proj`.
- `savant_proj = max(0.1, blend + adj)`; `value = savant_proj / (salary/1000)`.

Flags: `--xwoba-coef`, `--barrel-coef`, `--xera-coef`, `--hh-coef`, `--max-bat-pct`, `--max-pit-pct`, `--min-pa`, `--blend`, `--features`, `--out`.

### Cash / multiplier profile ($1–$3)

For small-field DraftKings multipliers, use the **cash** gate profile (same mean projections; different gates). See `CASH-PROFILE.md` and desk `DK-MLB-MULTIPLIER-CASH-RULES.md`.

```bash
python3 /home/box/mlb-dfs/lab/export_builder_gates.py --profile cash
# or
python3 /home/box/mlb-dfs/lab/export_cash_gates.py
# → lab/builder-gates-cash.csv

python3 /home/box/mlb-dfs/lab/apply_backtest_fixes.py --profile cash   --projections /home/box/mlb-dfs/projections-tonight.csv   --out /home/box/mlb-dfs/lab/backtests/projections-cash-gated.csv
```

Cash: smash boost off, stronger SP floor/exposure, chalk OK, unknown ownership neutral, MLB probables kept. Does **not** overwrite live slate files.

## Backtest with Savant projs

```bash
# Demo prefers savant_proj when the file has it:
python3 /home/box/mlb-dfs/lab/backtest.py --demo \
  --blend /home/box/mlb-dfs/projections-savant-tonight.csv

# Real slate folder: drop a copy as projections.csv (include savant_proj
# or alias it to blend_proj) under lab/backtests/YYYY-MM-DD/ plus actuals.csv
```

## Backtest skeleton

Folder convention:

```
/home/box/mlb-dfs/lab/backtests/YYYY-MM-DD/
  projections.csv   # dk_id + blend_proj (or proj_fp)
  actuals.csv       # dk_id, actual_fp
```

Metrics: **MAE**, **RMSE**, **Spearman** rank correlation, **top-20% overlap**.

```bash
# Real slate folder (after you drop actuals)
python3 /home/box/mlb-dfs/lab/backtest.py --date 2026-09-11

# Synthetic demo NOW (invents noisy actuals from tonight's blend)
python3 /home/box/mlb-dfs/lab/backtest.py --demo
# → lab/backtests/demo/{projections,actuals}.csv
# → lab/backtests/demo-results.txt
```

## Inputs (desk)

| File | Role |
|------|------|
| `/home/box/mlb-dfs/projections-tonight.csv` | Own-model projections (`dk_id`, `name`, `proj_fp`, …) |
| `/home/box/mlb-dfs/sources/dailyfantasyfuel-tonight.csv` | Free DFF CSV (`first_name`, `last_name`, `team`, `ppg_projection`, …) |
| `/home/box/mlb-dfs/dk-classic-player-pool.csv` | DK IDs, salaries, positions |
| `/home/box/mlb-dfs/lineups-50-tonight.csv` | 50 lineups, DK upload format `Name (id)` |
| `/home/box/mlb-dfs/sources/savant-expected-*-2026.csv` | Free Savant x-stats (via `fetch_savant.py`) |
| `/home/box/mlb-dfs/DK-MLB-CLASSIC-RULES.md` | Cap $50k, max 5 hitters/team, slots, etc. |

## Outputs

| File | Contents |
|------|----------|
| `/home/box/mlb-dfs/projections-blend-tonight.csv` | Blended projections |
| `/home/box/mlb-dfs/lab/features-savant-tonight.csv` | DK pool × Savant x-stats |
| `/home/box/mlb-dfs/lab/sim-results-tonight.csv` | Per-lineup mean / percentiles / win rate |
| `/home/box/mlb-dfs/lab/sim-results-tonight-summary.txt` | Short top-line summary |
| `/home/box/mlb-dfs/projections-savant-tonight.csv` | Savant-uplifted projections |
| `/home/box/mlb-dfs/lab/projections-savant-tonight-summary.txt` | Uplift method + adj distribution |
| `/home/box/mlb-dfs/lab/backtests/demo-results.txt` | Demo backtest metrics |

### Blend columns

`dk_id,name,team,salary,own_proj,dff_proj,blend_proj,value,sources,notes`

- Match DFF → DK by **normalized name + team** (accents stripped; `OAK`↔`ATH`; fuzzy fallback ≥0.85 same team).
- Default blend: **`0.55 * DFF + 0.45 * own`** when both exist; else whichever exists.
- `value` = `blend_proj / (salary/1000)`.

### Sim model

For each player in each lineup, sample fantasy points:

- Hitters: `Normal(proj, σ)` with `σ = max(3.0, proj * 0.35)`
- Pitchers: `Normal(proj, σ)` with `σ = max(4.0, proj * 0.40)`
- `proj` = `blend_proj` (fallback `own_proj` / `proj_fp`)
- Shared player samples across the 50 lineups within a sim (correlated field).
- Default **N=5000** (`--sims` / `-n`), seed 42 (`--seed`).

`win_rate_vs_field` = fraction of sims where that lineup is #1 among the 50.

## Flags

```bash
python3 blend_projections.py --dff-weight 0.55 \
  --own /home/box/mlb-dfs/projections-tonight.csv \
  --dff /home/box/mlb-dfs/sources/dailyfantasyfuel-tonight.csv \
  --out /home/box/mlb-dfs/projections-blend-tonight.csv

python3 simulate_lineups.py -n 5000 --seed 42 \
  --lineups /home/box/mlb-dfs/lineups-50-tonight.csv \
  --blend /home/box/mlb-dfs/projections-blend-tonight.csv \
  --out /home/box/mlb-dfs/lab/sim-results-tonight.csv

python3 fetch_savant.py --year 2026
python3 join_savant_features.py \
  --pool /home/box/mlb-dfs/dk-classic-player-pool.csv \
  --out /home/box/mlb-dfs/lab/features-savant-tonight.csv

python3 backtest.py --demo
python3 backtest.py --date 2026-09-11
```

## Notes

- Does **not** modify Builder / Projections agent scripts.
- Does **not** overwrite `lineups-50-tonight.csv`.
- Re-run after refreshing tonight’s CSVs on the desk.

## Sep 11 backtest fixes (2026-09-11)

Evidence-based gates from both Dime Time standings (`fix-these-brief.md` → `fix-these-response.md`).

```bash
# Real calibration (not --demo)
python3 /home/box/mlb-dfs/lab/backtest.py --date 2026-09-11 --proj-col blend_proj
# → lab/backtests/2026-09-11/calibration-metrics.txt

# Apply smash / elite-SP / dead-weight gates to a COPY (never live tonight)
python3 /home/box/mlb-dfs/lab/apply_backtest_fixes.py   --projections /home/box/mlb-dfs/projections-blend-0911-archive.csv   --out /home/box/mlb-dfs/lab/backtests/2026-09-11/projections-savant-fixed.csv

# Optional stack bonus in MC (default OFF)
python3 /home/box/mlb-dfs/lab/simulate_lineups.py --stack-bonus
```

| Module | Role |
|--------|------|
| `lab/slate_gates.py` | Smash-bat boost, `elite_sp` (40%/50% SP1), dead-weight floors |
| `lab/apply_backtest_fixes.py` | Writes adjusted copy under `lab/backtests/YYYY-MM-DD/` only |
| `lab/stack_rules.py` | 3–5 team/game stacks + bring-back; DK max 5 hitters/team |
| `lab/backtests/2026-09-11/fix-these-response.md` | Full metrics, tables, constants |

**Do not** point these writers at `projections-tonight.csv` / live lineup files.

## Sep 12 night 195543450 (fold-in)

CSV-verified calibration + gate note from `$100` Dime Time Night (`night-195543450-notes.md`). Contest `195543451` not folded.

```bash
python3 /home/box/mlb-dfs/lab/backtest.py --date 2026-09-12 --proj-col proj_fp
# → lab/backtests/2026-09-12/calibration-metrics.txt
# named copy: calibration-195543450.txt
```

| Artifact | Role |
|----------|------|
| `lab/backtests/2026-09-12/night-195543450-notes.md` | Recap, gates right/wrong, stack, constant changes |
| `lab/backtests/2026-09-12/actuals-195543450.csv` | 122 scorers from standings Player/FPTS/%Drafted |
| `lab/backtests/2026-09-12/our-entries-195543450.csv` | 20 hdbandit EntryIds (late lock upload) |
| `lab/backtests/2026-09-12/our-exposure-195543450.csv` | Exposure + late proj + lock tags |
| `lab/slate_gates.py` | Sep 12: unknown own ≠ 0%; `SMASH_HIGH_PROJ=14` × `0.50` taper |

**Do not** point writers at `projections-tonight.csv` / `projections-late.csv` / live lineup files. Lock-time `projections-late-gated.csv` left as the historical copy.

