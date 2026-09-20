# DraftKings MLB Multiplier / Cash profile ($1–$3)

## Contest shape
- Entry: ~$1–$3 multipliers (and similar small-field cash)
- Field: typically ~31–62 entrants
- Payout target: finish roughly top 9 → ~$3 (or site equivalent)
- Objective: **cash rate / floor**, not first place. Track ROI separately from GPP (Dime Time, etc.)

## Do we need a new projection model?
**Not for v1.** Desk uses the same mean `proj_fp` / Savant-adjusted projections.
Cash edge comes from **build rules + gates**, not a second fantasy-point model.
Later (v2): add floor metrics (sim p10 / downside) if live ROI lags.

## Construction (Builder)
1. Floor-first SP: prioritize elite/low-xERA probable starters; keep all MLB probables in pool; raise pitcher floor harder than hitter ceiling.
2. Chalk OK: do not force contrarian pivots; high-owned confirmed bats are fine.
3. Stacks: prefer 3–4 hitters from the best game environment; avoid max-5 leverage stacks unless salary forces it.
4. Uniques: for a 20-entry bag aim ~8–12 core lineups with light pivots (C / value OF / SP2), not 20 maximally different GPP builds.
5. Exposure: still ~40% max on any one player (user preference).
6. Hard DK rules unchanged: 10-man P/P/C/1B/2B/3B/SS/OF/OF/OF, $50k, max 5 **hitters** from one team (pitchers excluded from that count).

## Gates (Mad Scientist — cash profile, separate from GPP)
- Soften or disable smash-bat ceiling boost (especially for bats already high-proj).
- Strengthen elite-SP / pitcher-floor preference.
- Dead-weight: still drop true non-starters / scratches; do **not** exclude MLB probable SPs.
- Unknown ownership → treat as neutral (never as “low-owned leverage”).
- Apply cash gates only to subsequent builds — never mid-slate live file patches.

## Desk flow
Scout → Projections (shared means) → Mad Scientist **cash profile** → Builder **multiplier pack** → user enters $1–$3 mults → lineup watcher → results zip → calibrate **floors / cash rate**, not GPP ceilings.

## Bankroll
Concentrate volume in $1–$3 mults on main Classic slates. Optional thin GPP sleeve kept separate in tracking.

## SP eligibility (updated 2026-09-18 — Mayza lesson)
For **cash/multipliers**, do **not** roster a pitcher solely because MLB StatsAPI marks them probable if DraftKings tags them **RP** and their recent card is RP-length (sub-~3 IP / RP FPPG).
- Prefer DK **SP** + MLB probable.
- RP-tagged probables (openers / bulk-then-RP days: Mayza, similar) are **GPP-only / exclude from cash** unless there is clear evidence of a traditional starter workload.
- Still keep true SP-tagged MLB probables even if soft xERA.

## Lab enforcement
Cash gates (`lab/slate_gates.py` profile `cash`, `CASH_EXCLUDE_DK_RP`): DK `Position=RP` → `gate_action=exclude` even when MLB probable. Builder must honor exclude.

## SP eligibility v1.1 (2026-09-20 — Alvarez/Holmes lesson)
- DK **SP** + MLB probable: primary cash pool; elite only if DK SP and sal ≥ $6500.
- DK **RP** + MLB probable + salary **≥ $6000**: allowed as **bulk candidate** (not elite).
- DK **RP** under $6000 or not probable: **exclude** (Mayza/opener junk).
- Prefer at least one ace (sal ≥ ~$9000 / top projected SP); do not auto-punt both studs for a Coors stack + two mid SPs.
