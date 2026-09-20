# Fix-these brief — Sep 11 DK backtest (both Dime Times)

Data:
- contest-standings-195514318.csv ($100, 1189 entries) — our 20 matched
- contest-standings-195514320.csv ($300, 3561 entries) — our 20 matched
- Paths: /home/box/mlb-dfs/lab/backtests/2026-09-11/dk-results/
- Our results summary: /home/box/mlb-dfs/lab/backtests/2026-09-11/results-summary-both.txt

Performance:
- $100: avg 98 vs field 108; best #113 (143); ~2/20 top-20%
- $300: avg 95 vs field 105; best #99 (161); ~5/20 top-20%
- Pattern: mid-pack floor, rare upside; not enough smash correlation

## Fix these (priority order)

1. **Smash-bat underweight**
   Actual monsters we owned 0–2/20: Kyle Tucker (35), Brice Turang (34), Chase Meidroth (30), Garrett Mitchell (30), William Contreras (29), Jackson Chourio (26).
   Action: raise ceiling / ownership-aware boost for high xwOBA + barrel bats in confirmed orders; don't let salary-proxy midtiers crowd them out at 40% cap.

2. **Chalk SP thin when they go off**
   Snell / May / Sale smashed; we had ~1–2 max on several. Rodón/Bradley did well when rostered.
   Action: when Savant xERA + K indicators are elite AND probable, allow SP exposure up toward the 40% cap (or a soft 50% for clear SP1); dual-SP correlation with opposing stacks.

3. **Dead-weight kill list**
   High exposure flops: Jorge Mateo (~5/20 @ 2 FPTS), Yandy Díaz / JJ Bleday (4/20 @ 0 on $300 sheet), Anthony Molina (4/20 @ −5.9 FPTS).
   Action: hard floor — if posted but projection < X or pitcher non-elite RP-as-SP, exclude from optimizer or cap at 1/20. Molina-type "probable" soft arms need a SP quality gate (xERA/K%/salary tier).

4. **Projection calibration**
   Run real backtest (not --demo): join Sep 11 projections-tonight / savant archive to DK FPTS from standings Player column.
   Report MAE / Spearman / top-20% overlap for hitters vs pitchers separately; flag systematic bias (overproject low-salary hitters, underproject OF smash).

5. **Stack / correlation**
   Winner #1 was Sale+May with Contreras/Chourio/Tucker/Mitchell — game stacks + bring-back.
   Action: add simple stack rules or sim bonus for 3–5 hitters same game/team (still max 5 hitters/team DK rule).

## Deliverables requested
- Write /home/box/mlb-dfs/lab/backtests/2026-09-11/fix-these-response.md
- Update lab scoring / project_with_savant or blend weights if evidence supports
- Do NOT overwrite tonight's live projections unless explicitly better for a future slate
- Free data only
