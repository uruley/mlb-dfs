# Fix-these response — Sep 11 DK Dime Time backtest

**Desk handle:** `hdbandit` (matched via EntryIds in `lineups-40-LOCK-ENTRIES-UPLOAD.csv`)  
**Contests:** $100 Dime Time `195514318` (field 1189) · $300 Dime Time `195514320` (field 3561)  
**Our 20:** 20/20 EntryIds matched in each contest (40 total). Best: #$100 #113 (142.85) · #$300 #99 (161.1).  
**Data:** Free only (DK standings CSVs + archived Sep 11 projections + Savant expected stats).  
**Live tonight (Sep 12) projections/lineups were NOT overwritten.**

---

## What we measured

| Contest | Field n | Our n | Our avg | Field avg | Best | Top-20% |
|---------|--------:|------:|--------:|----------:|------|--------:|
| $100 (195514318) | 1189 | 20 | 98.0 | 107.6 | #113 / 142.85 | 2/20 |
| $300 (195514320) | 3561 | 20 | 95.1 | 105.0 | #99 / 161.1 | 5/20 |

- **Player actuals:** 297 unique names from standings `Player` / `FPTS` / `%Drafted` (deduped by name; Max Muncy had two FPTS rows 13 vs 5 — kept own≈12.73 → **13 FPTS**; noted in actuals `source_contest`).
- **Projections joined:** all 297 → `projections-blend-0911-archive.csv` by normalized name (`dk_id` filled). Used **archived** Sep 11 blend/savant — not live Sep 12 files.
- **Exposure:** parsed from our 20×2 matched entries (standings Lineup + LOCK upload slots).

---

## Calibration table (real join — blend_proj primary)

Source metrics: `calibration-metrics.txt` (also `calibration-metrics-savant.txt`).

### blend_proj

| Split | n | MAE | RMSE | Spearman | Top-20% overlap |
|-------|--:|----:|-----:|---------:|----------------:|
| **Overall** | 297 | **5.2015** | **7.0982** | **0.3817** | **0.3051** |
| Hitters | 270 | 4.9978 | 6.8253 | 0.3584 | 0.3148 |
| Pitchers | 27 | 7.2391 | 9.4013 | 0.5531 | 0.2000 |

### savant_proj (same join)

| Split | n | MAE | RMSE | Spearman | Top-20% overlap |
|-------|--:|----:|-----:|---------:|----------------:|
| Overall | 297 | 5.2661 | 7.1410 | 0.3916 | 0.3220 |
| Hitters | 270 | 5.0577 | 6.8716 | 0.3723 | 0.3148 |
| Pitchers | 27 | 7.3503 | 9.4204 | 0.5092 | 0.2000 |

### Bias flags (blend)

- Low-sal hitters (&lt;$4k): n=180, mean(proj−actual)=**−0.69** (near-neutral — *not* systematic low-sal overproj on this slate).
- High-sal hitters (≥$5k): n=28, mean(proj−actual)=**+1.37** (mild OVER-proj).
- **OF smash (actual ≥20):** n=12, mean(proj−actual)=**−16.75** — clear **UNDER-projection** of ceiling OF outcomes (Tucker 7.3→35, Mitchell 5.4→30, Chourio 11.5→26, …).
- Pitchers: mean(proj−actual)=**+1.96** (slight overproj on the 27 who posted FPTS).

**Takeaway:** Rank correlation is modest (ρ≈0.38). Ceiling bats are the failure mode — not chalk midtier inflation. Savant uplift slightly helps Spearman/top-20% but does **not** fix OF smash underproj alone.

---

## Priority 1 — Smash-bat underweight

| Player | Exp $100 | Exp $300 | Actual | DK own% | blend | savant | xwOBA | barrel% | Fixed adj | Why underweighted |
|--------|--------:|--------:|-------:|--------:|------:|-------:|------:|--------:|----------:|-------------------|
| Kyle Tucker | 2/20 | 0/20 | **35** | 10.23 | 7.32 | 7.56 | 0.330 | 6.3 | 8.12 (`smash_bat`) | Proj mid-pack @ $3800; salary-proxy midtiers filled OF; 40% cap never reached |
| Brice Turang | 1/20 | 0/20 | **34** | 3.87 | 9.82 | 10.47 | 0.342 | 7.5 | 11.53 (`smash_bat`) | Solid blend but low owned; stack not prioritized |
| Chase Meidroth | 0/20 | 0/20 | **30** | 8.16 | 6.99 | 6.63 | 0.297 | 4.5 | 6.63 (no tag) | Below smash z-thresholds (xwOBA z&lt;0.5); pure chalk miss |
| Garrett Mitchell | 1/20 | 0/20 | **30** | 2.80 | 5.37 | 6.04 | **0.353** | **11.9** | 7.20 (`smash_bat`) | High barrel/xwOBA but low proj → crowded out |
| William Contreras | 1/20 | 1/20 | **29** | 5.30 | 8.21 | 8.73 | 0.335 | 8.5 | 9.59 (`smash_bat`) | Core of winning stacks; we barely touched |
| Jackson Chourio | 0/20 | 3/20 | **26** | 10.29 | 11.46 | 12.71 | 0.342 | 12.4 | 14.75 (`smash_bat`) | Best of group on $300 still only 3/20 |

### Recommended rule (implemented)

**Smash-bat boost** in `lab/slate_gates.py` → applied via `lab/apply_backtest_fixes.py`:

- Eligible: hitter, PA≥50, confirmed/posted order (or unknown-ok for lab replay), and `z_xwoba ≥ 0.50` **or** `z_barrel ≥ 0.75`.
- Formula:
  - `raw = 0.10 * max(0,z_xwoba) + 0.05 * max(0,z_barrel)`
  - `own_factor = 1 + 0.8 * max(0, 12 − own_proj) / 100` (low-owned smash get more boost)
  - `boost_pct = clip(raw * own_factor, 0, 0.25)`
  - `adjusted = proj * (1 + boost_pct)`
- Tag: `smash_bat`. Goal: keep them competitive vs midtier salary proxies under a 40% exposure cap.

**Code:** `lab/slate_gates.py`, `lab/apply_backtest_fixes.py` → `lab/backtests/2026-09-11/projections-savant-fixed.csv`.

**Caveat:** Season xwOBA alone also tags Yandy/Bleday (see P3) — boost should still require **confirmed order + game environment** in production wiring.

---

## Priority 2 — Elite / chalk SP thin when they go off

| Player | Exp $100 | Exp $300 | Actual | DK own% | blend | savant | xERA | Gate | Why thin |
|--------|--------:|--------:|-------:|--------:|------:|-------:|-----:|------|----------|
| Blake Snell | 2/20 | 2/20 | **27.15** | 36.64 | 21.19 | 25.25 | **2.10** | `elite_sp` → target 40% | Chalk smash; we maxed ~2/20 |
| Dustin May | 2/20 | 3/20 | **27.70** | 20.04 | 13.07 | 12.94 | 4.24 | keep (not elite) | Underprojected; still only 2–3/20 |
| Chris Sale | 1/20 | 0/20 | **18.15** | 33.70 | 21.18 | 23.38 | **3.04** | `elite_sp` → target 40% | Near-zero exposure despite chalk |
| Carlos Rodón | 3/20 | 2/20 | **29.85** | 5.41 | 16.52 | 16.97 | 3.77 | keep | Best of our SPs when rostered |
| Taj Bradley | 3/20 | 2/20 | **22.50** | 4.82 | 16.01 | 16.41 | 3.98 | keep | Decent when rostered |

### Recommended rule

- Tag `elite_sp` when probable **and** (`xERA ≤ 3.20` **or** `z_xera ≥ 0.75`).
- **Exposure target 40%** for elite SP pool; **soft 50% for clear SP1** (Snell/Sale class).
- Do **not** silently rewrite live projection files — lab tags + Builder/optimizer consume `exposure_target`.

**Code:** `elite_sp_tag()` in `lab/slate_gates.py`. Sep 11 fixed copy tags Snell + Sale with `exposure_target=0.40`.

---

## Priority 3 — Dead-weight kill list

| Player | Exp $100 | Exp $300 | Actual | DK own% | blend | savant | Signal | Gate action |
|--------|--------:|--------:|-------:|--------:|------:|-------:|--------|-------------|
| Jorge Mateo | **5/20** | **3/20** | **2** | 1.23 | 4.71 | 4.61 | cheap filler | `dead_weight` → **cap_1_of_20** |
| Yandy Díaz | 0/20 | **4/20** | **0** | 4.23 | 10.01 | 11.05 | high xwOBA but 0 FPTS | still `smash_bat` on season metrics — need order/matchup veto |
| JJ Bleday | 1/20 | **4/20** | **0** | 1.93 | 8.29 | 9.08 | same | same caveat |
| Anthony Molina | **3/20** | **4/20** | **−5.85** | 2.52 | 10.70 | 11.07 | xERA 4.36, PA 94, $7500 | `dead_weight` → **exclude** |

### Gate constants (from calibration + this slate)

| Constant | Value | Role |
|----------|------:|------|
| `HITTER_FLOOR` | **5.0** | proj &lt; 5 → `cap_1_of_20`; proj &lt; 4 → `exclude` |
| `PITCHER_FLOOR` | **6.0** | non-elite low-proj SP soft gate |
| `BAD_XERA_MIN` | **5.0** | hard pitcher exclude |
| `MOLINA_XERA` | **4.5** | soft-SP exclude at SP salary |
| Soft-SP small sample | xERA ≥ **4.2** and PA &lt; **250** | catches Molina (PA=94) without killing May (xERA 4.24, PA 584) |
| `MOLINA_SAL_MIN` | **7000** | SP-salary tier for soft-arm gate |

**Why we overweighted:** Mateo was a sub-$4k salary sink with proj≈4.7 (above old mental floor); Molina looked like a mid-$7.5k “probable” with blend≈10.7 — no xERA/PA quality gate. Yandy/Bleday were projection-reasonable (10/8) and high xwOBA — failures are outcome + lack of stack discipline, not pure proj floor (documented caveat).

---

## Priority 5 — Stack / correlation ideas

**$100 #1 (BlackAvenger, 218.85):** Sale + May · Contreras / Chourio / Tucker / Mitchell / Ortiz / Vaughn / Marte / Story  
→ Dual-SP + **MIL smash core** (Contreras/Chourio/Mitchell) + **LAD bring-back** (Tucker).

**$300 #1 (Emac, 217.85):** Snell + May · Contreras / Chourio / Tucker / Butler / …  
→ Same MIL+Tucker pattern with chalk Snell.

### Lab rules (`lab/stack_rules.py`)

1. Primary team stack: **3–5 hitters same team** (DK hard max **5** hitters/team).
2. Game stack + **1–2 bring-back** from opponent.
3. Dual elite/probable SP correlated with the smash offense (Sale+May / Snell+May).
4. Prefer stacking players with `smash_bat` tags.
5. Never exceed 5 hitters/team; pitchers excluded from cap.

Optional MC bonus: `simulate_lineups.py --stack-bonus` (default **OFF** so existing sims stay comparable).

---

## What we will NOT do

- **No overwrite** of live Sep 12 files (`projections-tonight.csv`, `projections-blend-tonight.csv`, `projections-savant-tonight.csv`, `lineups-*-tonight.csv`, `entered-lineups-tonight.csv`).
- No lineup upload / ownership confirm gate.
- No invented metrics — all FPTS/ownership/MAE/Spearman from CSV joins.
- No paid data.

---

## Files written / changed

### New (backtest folder)
- `lab/backtests/2026-09-11/actuals.csv` — name, position, ownership_pct, actual_fp, source_contest (+ dk_id)
- `lab/backtests/2026-09-11/projections.csv` — archived blend/savant join for slate scorers
- `lab/backtests/2026-09-11/our-exposure.csv` — per-player exp in each contest /20
- `lab/backtests/2026-09-11/our-entries.csv` — 40 matched hdbandit rows (rank/points/lineup)
- `lab/backtests/2026-09-11/calibration-metrics.txt` — blend_proj H/P metrics + bias flags
- `lab/backtests/2026-09-11/calibration-metrics-savant.txt` — savant_proj metrics
- `lab/backtests/2026-09-11/projections-savant-fixed.csv` — lab COPY with gates/boosts
- `lab/backtests/2026-09-11/projections-savant-fixed.summary.txt`
- `lab/backtests/2026-09-11/fix-these-response.md` — this file

### New lab modules
- `lab/slate_gates.py` — smash boost / elite SP / dead-weight gates + constants
- `lab/apply_backtest_fixes.py` — apply gates to a projections **copy** under backtests/
- `lab/stack_rules.py` — stack documentation + optional bonus helper

### Updated
- `lab/backtest.py` — name join if dk_id missing; H/P split; bias flags; writes calibration-metrics
- `lab/simulate_lineups.py` — optional `--stack-bonus` (default off)
- `lab/README.md` — “Sep 11 backtest fixes” section

### Blockers / notes
- Our 20 **identified** as `hdbandit` via LOCK EntryIds (not guesswork).
- `projections-0911-savant-archive.csv` looks like a Sep 12 overwrite (Snell proj_fp 0.6) — **ignored for calibration**; used `projections-blend-0911-archive.csv`.
- `lab/features-savant-tonight.csv` is Sep 12 slate — Savant stats for diagnosis pulled from `sources/savant-expected-*-2026.csv`.
- Meidroth (30 FPTS, 0/20) does not pass smash z-gates — still a process miss (need chalk/order awareness beyond z).
