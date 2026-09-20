# Night contest 195543450 — Sep 12 DK $100 Dime Time

**Desk handle:** `hdbandit`  
**Identity:** 20/20 EntryIds from `lineups-40-late-ENTRIES-UPLOAD.csv` (Contest ID `195543450` only): `5251905651`–`5251905670`.  
**Contest 195543451:** skipped (not in yet).  
**Data:** Free only (DK standings CSV + late-lock `projections-late.csv` + Savant expected stats already on desk).  
**Live tonight / late projection and lineup files were NOT overwritten.**

Manager one-liner (`results-195543450-summary.txt`) used rounded field size/avg. **CSV numbers below win where they differ.**

---

## Contest recap (from standings CSV)

| | CSV (authoritative) | Manager / one-liner |
|--|--------------------:|--------------------:|
| Field n | **1189** unique EntryIds | ~1185 |
| Our n | **20** / 20 matched | 20 |
| Our avg | **116.38** | 116.4 |
| Field avg | **114.52** | 114.9 |
| Best | **#67 / 174.65** (`hdbandit (3/20)`, EntryId `5251905653`) | #67 / 174.7 |
| Worst | **#1060 / 64.55** (`hdbandit (11/20)`, EntryId `5251905661`) | #1060 / 64.6 (one-liner 64.5) |
| Top 20% | **2/20** (ranks 67, 221; cut rank ≤ 237.8) | 2/20 |

Winner (21-way tie at 209.55; first row `csurunnerccr (6/20)`):

`P Bryan Woo / P Shane Drohan · C William Contreras · 1B Jake Bauers · 2B Brice Turang · 3B Weston Wilson · SS J.P. Crawford · OF Randy Arozarena / Christian Yelich / Garrett Mitchell`

Our best lineup (#67, 174.65): Woo + Mahle · Baldwin · Olson · Young · Riley · Montgomery · Acuña / Harris II / Justin Crawford. Cashed because Woo (24.5) + Mahle (20.15) + Acuña (26) + Harris II (34) + Young (30) all hit; not the winning MIL 5-stack.

---

## Calibration (late `proj_fp` × standings actuals)

Join: 122/122 scorers matched (`dk_id` then normalized name). Source: `projections-late.csv` copied to `lab/backtests/2026-09-12/projections.csv` (not live tonight). Metrics from `backtest.py` helpers → `calibration-195543450.txt`.

### Late lock `proj_fp` (primary)

| Split | n | MAE | RMSE | Spearman | Top-20% overlap |
|-------|--:|----:|-----:|---------:|----------------:|
| **Overall** | 122 | **6.5260** | **8.5722** | **0.4000** | **0.2500** |
| Hitters | 106 | 6.5182 | 8.4573 | 0.3470 | 0.3333 |
| Pitchers | 16 | 6.5775 | 9.2973 | 0.5197 | 0.3333 |

### Lock-time `adjusted_proj` (gated copy; not re-fit)

| Split | n | MAE | RMSE | Spearman | Top-20% overlap |
|-------|--:|----:|-----:|---------:|----------------:|
| Overall | 122 | 6.7833 | 8.7291 | 0.4089 | 0.3333 |
| Hitters | 106 | 6.8143 | 8.6401 | 0.3530 | 0.3333 |
| Pitchers | 16 | 6.5775 | 9.2973 | 0.5197 | 0.3333 |

Gated smash boost **worsened MAE** (+0.26) and slightly **helped rank** (ρ 0.400→0.409, top-20% 0.25→0.33). That is the Schwarber/Vargas problem: ceiling tags are directionally right, full +25% on already-high raw proj is not.

### Bias flags (late `proj_fp`)

- Low-sal hitters (&lt;$4k): n=65, mean(proj−actual)=**+0.016** (near-neutral)
- Mid-sal (4–5k): n=27, **+0.923** (near-neutral)
- High-sal (≥$5k): n=14, **+1.619** (OVER-proj)
- **OF smash (actual ≥20):** n=4, mean(proj−actual)=**−18.817** (UNDER-proj) — Mitchell 9.2→38, Harris II 11.3→34, Acuña 14.4→26, Arozarena 10.8→23
- Pitchers: n=16, mean(proj−actual)=**+5.086** (overproj; Jump −5.7, Drohan 2.05 vs 16–17 proj)

Same failure mode as Sep 11: ceiling OF under-projected. New wrinkle: high-sal smash we *did* roster also over-projected.

---

## What gates got right

| Player | Exp | Actual | DK own% | late proj → lock adj | Gate | Why this is a hit |
|--------|----:|-------:|--------:|----------------------|------|-------------------|
| Bryan Woo | **11/20** | **24.5** | 57.36 | 18.32 → 18.32 | not `elite_sp` (xERA **3.55**, z_xera **0.694** — just misses 3.20 / 0.75) | Process still maxed the clear SP1. Tag missed; exposure did not. |
| Brice Turang | **9/20** | **23** | 34.99 | 12.56 → 13.95 | `smash_bat` (z_xwoba 1.01) | Tagged + we used him. Core of winning MIL stack. |
| Ronald Acuña Jr. | **7/20** | **26** | 15.98 | 14.45 → 17.69 | `smash_bat` (z_xwoba 1.48, z_barrel 1.14) | Tagged + we used him. |
| Garrett Mitchell | 4/20 | **38** | 11.77 | 9.24 → 11.09 | `smash_bat` (z_xwoba 1.29, barrel 11.9%) | **Tag was right.** Exposure too thin vs boosted Vargas. |
| Michael Harris II | 2/20 | **34** | 4.21 | 11.28 → 12.77 | `smash_bat` | Same: tagged, under-used. |

Woo/Turang/Acuña were the requested “gates got right” trio. Woo is a process win, not an `elite_sp` constant win.

---

## What failed

| Player | Exp | Actual | DK own% | late proj → lock adj | Gate | What went wrong |
|--------|----:|-------:|--------:|----------------------|------|-----------------|
| Miguel Vargas | **11/20** | **5** | 12.28 | 14.40 → **18.00** | `smash_bat` max +25% (own treated as 0.0) | Highest hitter exposure. Season xwOBA 0.382 is real; full boost on a 14.4 raw proj made him look like the 1B/3B. |
| Bryson Stott | **6/20** | **0** | 7.49 | 10.32 → 11.05 | `smash_bat` (z_xwoba **0.648** only; barrel z −0.36) | Weak smash. PHI chalk-ish filler next to Schwarber. |
| Kyle Schwarber | **5/20** | **0** | 12.78 | 15.03 → **18.79** | `smash_bat` max +25% (z_xwoba 1.60, barrel 16.9%) | High-proj chalk-ish smash. Already #1 raw hitter; did not need a ceiling bump. |
| Shane Drohan | 4/20 | **2.05** | **43.06** | 16.73 → 16.73 | not elite (xERA 3.69, z 0.572) | Chalk dud. We only had 4/20 — not the main leak. Winner still paired him with Woo. |
| Gage Jump | 4/20 | **−5.7** | 17.91 | 15.86 → 15.86 | no dead-weight | xERA **4.51**, salary **$6800** — slips under `MOLINA_SAL_MIN` 7000. |

### Underowned / smash we missed (actual ≥20, exp 0)

| Player | Actual | DK own% | late proj | Gate note |
|--------|-------:|--------:|----------:|-----------|
| Michael Arroyo | **30** | 7.32 | 6.09 | `smash_skip_low_pa`; Savant row is junk (xwOBA 0.005). `source=bench`. Not a z-gate miss — no signal. |
| J.P. Crawford | **25** | 19.18 | 7.91 | z_xwoba **0.492** (misses 0.50 by 0.008) + `tbd_team` / unconfirmed. SEA stack piece. |
| Weston Wilson | **25** | 8.58 | 7.55 | z_xwoba −1.32. Cheap SEA 3B. Winner stack, not a smash profile. |

Arozarena (23, 26.49% own, 1/20): z_xwoba **1.113** would smash, but lock file is `source=tbd_team` → `smash_skip_unconfirmed`. Confirmed-order veto did its job given the data at lock; late SEA orders were not posted. Do **not** relax that (Sep 11 Yandy/Bleday caveat still stands).

---

## Do smash / elite-SP / dead-weight need a tweak?

### Smash-bat — yes, small, evidence-based

Lock-time smash treated **missing ownership as 0%** (`own=0.0`, `own_factor=1.096`). Every high-z posted bat got the low-own extra; Schwarber/Vargas/`Elly` hit the +25% cap.

That inverted priority vs Mitchell-class:

| | lock adj | actual | our exp |
|--|--------:|-------:|--------:|
| Schwarber | 18.79 | 0 | 5/20 |
| Vargas | 18.00 | 5 | 11/20 |
| Mitchell | 11.09 | 38 | 4/20 |
| Harris II | 12.77 | 34 | 2/20 |

Sep 11 already said ceiling OF are under-projected (Tucker/Mitchell/Chourio). Sep 12 repeats that **and** shows full smash boost on already-high raw proj (14+) overweights chalk-ish duds. Acuña (14.45→26, 7/20) is the counterexample — he stays tagged; we only taper the *size* of the bump.

**Implemented in `lab/slate_gates.py` (does not rewrite live/late projection files):**

1. **Unknown ownership → `own_factor = 1.0`** (do not pretend own=0%).
2. **`SMASH_HIGH_PROJ = 14.0`**, **`SMASH_HIGH_PROJ_FACTOR = 0.50`** — if raw proj ≥ 14, keep half the computed boost.

Replay on this slate (own unknown, same z):

| Player | raw proj | lock adj | new adj | still tagged? |
|--------|--------:|--------:|--------:|:-------------:|
| Schwarber | 15.03 | 18.79 | **16.91** | yes |
| Vargas | 14.40 | 18.00 | **16.20** | yes |
| Acuña | 14.45 | 17.69 | **15.93** | yes |
| Harper | 14.44 | 18.05 | **16.25** | yes |
| Mitchell | 9.24 | 11.09 | **10.93** | yes |
| Harris II | 11.28 | 12.77 | **12.64** | yes |
| Turang | 12.56 | 13.95 | **13.83** | yes |

Mitchell/Harris barely move (they were never ≥14). High-proj smash lose ~1.8–2.1 pts of invented ceiling. Tag set unchanged.

**Not changed (evidence too thin / would add noise):**

- `SMASH_Z_XWOBA` 0.50 — Crawford at 0.492 is one near-miss, not a threshold error.
- Confirmed-order requirement — Arozarena skip was correct given `tbd_team`.
- Arroyo — no Savant signal; cannot invent a “low-own smash” tag from a bench/low-PA row.

### Elite-SP — no constant change

Woo (xERA 3.55 / z 0.694) missed `ELITE_XERA_MAX` 3.20 and `ELITE_Z_XERA` 0.75. We still used him **11/20**. Widening the band to catch Woo would be one-slate retuning; Sep 11 elites (Snell/Sale) were well inside 3.20. Leave constants. Document as a near-miss for the next slate.

### Dead-weight — no constant change

Jump (xERA 4.51, $6800, −5.7, 4/20) slips under `MOLINA_SAL_MIN` 7000. One arm, modest exposure. Lowering salary to 6500 is tempting and not justified on n=1. Stott/Vargas were above `HITTER_FLOOR` 5.0 — floor is not the failure mode.

---

## Stack note (DK Classic max 5 hitters/team)

Winner = **Woo + Drohan** + **MIL smash 5-max** (Bauers / Turang / Contreras / Yelich / Mitchell) + **SEA bring-back** (Wilson / Crawford / Arozarena). Pitchers do not count toward the 5.

That is the Sep 11 stack rule executed cleanly: primary team 3–5 smash bats + 1–2 bring-back from the SP’s game. We had Turang 9/20 and Mitchell only 4/20; we never built the MIL 5 + SEA Woo bring-back. Our #67 cashed on ATL (Acuña/Harris) + Woo/Mahle + Young luck, not the winning correlation.

`lab/stack_rules.py` already encodes 3–5 + bring-back + max 5 hitters/team. No rule change — the leak was smash *ranking* (Vargas 18.00 vs Mitchell 11.09), not the stack spec.

---

## Files

### New (backtest folder only)

- `lab/backtests/2026-09-12/actuals-195543450.csv` — name, position, ownership_pct, actual_fp, dk_id, source_contest (122 unique; 0 FPTS conflicts)
- `lab/backtests/2026-09-12/actuals.csv` / `projections.csv` — same join, so `backtest.py --date 2026-09-12` works (`proj_fp` / `blend_proj` alias)
- `lab/backtests/2026-09-12/our-entries-195543450.csv` — 20 hdbandit rows
- `lab/backtests/2026-09-12/our-exposure-195543450.csv` — standings exposure + late proj + lock gate tags
- `lab/backtests/2026-09-12/calibration-195543450.txt` — MAE/RMSE/Spearman/top-20% H/P
- `lab/backtests/2026-09-12/calibration-195543450-adjusted.txt` — same on lock `adjusted_proj`
- `lab/backtests/2026-09-12/night-195543450-notes.md` — this file

### Changed

- `lab/slate_gates.py` — unknown-own fix + `SMASH_HIGH_PROJ` / `SMASH_HIGH_PROJ_FACTOR` (documented above)
- `lab/README.md` — pointer under Sep 11 fixes

### Explicitly not touched

- `projections-tonight.csv`, `projections-blend-tonight.csv`, `projections-savant-tonight.csv`
- `projections-late.csv`, `projections-late-gated.csv` (desk + lock-time lab copy)
- `lineups-*-tonight.csv`, `lineups-*-late.csv`, lock upload CSVs
- Contest `195543451`

### Blockers / notes

- Field n **1189** vs manager ~1185 — unique `EntryId` count in the standings file.
- Field avg **114.52** vs manager 114.9 — mean of those 1189 `Points`.
- `projections-late-gated.csv` is the **lock-time** gated copy (old constants, own=0.0). Left as the historical artifact.
- No paid data. No invented FPTS/ownership/MAE.
