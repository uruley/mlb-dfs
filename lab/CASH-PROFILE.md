# Cash / multiplier gate profile ($1–$3)

See desk rules: `/home/box/mlb-dfs/DK-MLB-MULTIPLIER-CASH-RULES.md`.

## v1.1 (2026-09-20) — Mayza refine after Alvarez/Holmes overcorrection

**Desk standard (Manager-approved 2026-09-20)** for next slate. No mid-slate live patches.

Reuse mean Savant-adjusted `proj_fp`. Cash edge is **gates + build rules**.

| Knob | GPP (`--profile gpp`) | Cash (`--profile cash`) |
|------|------------------------|-------------------------|
| Smash-bat ceiling boost | on (max +25%, high-proj taper) | **off** (tag-only) |
| Elite SP xERA / z | ≤3.20 / ≥0.75 | ≤3.60 / ≥0.55 (catch Woo-class) |
| Elite SP exposure | 40% / soft SP1 50% | **50% / soft SP1 60%** |
| Elite SP floor bump | none | **+5%** on adjusted_proj |
| Pitcher dead-weight floor | proj &lt; 6 | proj &lt; **10** (skipped for bulk RP candidates with opener-capped means) |
| Unknown ownership | neutral | neutral |
| DK Position=RP | GPP: probable can override RP-as-SP | **salary-gated** (see below) — not a blanket exclude |
| Elite SP salary | no min | **≥ $6500 DK SP** (true SP1/SP2; never elite-tag DK-RP) |
| Prefer ace in cash builds | n/a | soft: ≥1 SP with salary **≥ $9000** (or top-2 SP by proj) |

### DK-RP rule (replaces hard exclude)

**Problem (09/19):** Cash gates hard-excluded *all* DK-RP after Mayza (09/18). Winner arms Alvarez (25.9) and Holmes (16.7) were DK-RP MLB-probables that Projections Mayza-capped to ~3–4 FPTS; Detmers+Mize mid-tier pair lost. Mayza fix overcorrected.

**Rule v1.1 (lab, next slate — no mid-slate live patches):**

1. **Cheap opener (Mayza class):** DK `RP` AND (not MLB probable OR salary **&lt; $6000**) → hard `exclude` (`dead_weight_p: cash_dk_rp_opener`).
2. **Bulk / actual starter day (Alvarez/Holmes class):** DK `RP` AND MLB probable AND salary **≥ $6000** → tag `cash_rp_bulk_candidate`, **do not** hard-exclude for RP alone. If means still look Mayza-capped (`probable_opener` / Mayza notes / proj &lt; 8), **skip pitcher-floor exclude** so Builder can see them; bad xERA still excludes.
3. **Never** elite-tag DK-RP (elite remains DK `SP` ≥ $6500).
4. **Projections ask:** stop Mayza IP~1 caps when DK salary ≥ $6000 (or when StatsAPI role ≠ opener). Prefer bulk IP (~4.5–5.5) so floor/FPTS are honest — gates should not be the only recovery path.
5. **Build hint:** cash should prefer **≥1 true ace** (salary ≥ $9000 or top-2 SP by proj). Avoid punting both Skubal/Schlittler-class just to afford a Coors stack with mid-tier SP2.

Constants in `slate_gates.py` cash profile: `CASH_EXCLUDE_DK_RP=True` (gated), `CASH_RP_BULK_MIN_SALARY=6000`, `CASH_MIN_ELITE_SP_SALARY=6500`, `CASH_PREFER_ACE_SALARY=9000`.

## Commands

```bash
# Builder-facing cash gates (does NOT overwrite live projections)
python3 /home/box/mlb-dfs/lab/export_builder_gates.py --profile cash \
  --out /home/box/mlb-dfs/lab/builder-gates-cash.csv

# Apply cash gates to a COPY under lab/backtests (refuse live tonight names)
python3 /home/box/mlb-dfs/lab/apply_backtest_fixes.py --profile cash \
  --projections /home/box/mlb-dfs/projections-tonight.csv \
  --out /home/box/mlb-dfs/lab/backtests/projections-cash-gated.csv
```

Never patch mid-slate live files. v2: explicit starter-workload / expected-IP flag from StatsAPI when available.

## History

### Mayza lesson (2026-09-18)

Cash LU rostered Tim Mayza (DK `RP`, MLB probable opener) and got crushed.
v1 response: hard-exclude all DK-RP. Pitcher floor → 10; elite SP → DK SP ≥ $6500.

### Alvarez/Holmes overcorrection (2026-09-19)

Winner SP pair was Alvarez + Holmes (both DK-RP, Mayza-capped, gate-excluded).
Our Detmers 9.65 + Mize −5.25 lost. v1.1 salary-gates the RP exclude and asks
Projections to restore bulk means for ≥$6k probable DK-RP.
