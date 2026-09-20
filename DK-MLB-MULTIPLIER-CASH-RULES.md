# DraftKings MLB Multiplier / Cash profile ($1–$3)

## Contest shape
- Entry: ~$1–$3 multipliers (and similar small-field cash)
- Field: typically ~31–62 entrants
- Payout target: finish roughly top 9 → ~$3 (or site equivalent)
- Objective: **cash rate / floor**, not first place. Track ROI separately from GPP (Dime Time, etc.)

The Task 001 builder objective is narrower and honest: **max provisional mean `proj_fp`**. It does not claim calibrated cash probability. Triple-ups and 50/50s are not the same payout objective; contest metadata must be supplied or labeled missing.

## Do we need a new projection model?
**Not for Task 001.** Desk may still reuse mean `proj_fp`. Workload (expected innings) is now separate from per-inning skill. Remaining salary-derived skill rates are labeled provisional.

## Construction (Task 001 builder)
1. One lineup, deterministic, frozen inputs.
2. Pitcher cash pool = evidence role starter or bulk with resolved workload. DK SP/RP is eligibility only.
3. Posted bats required for final delivery. Scratches fail validation.
4. Hard DK rules: 10-man P/P/C/1B/2B/3B/SS/OF/OF/OF, $50k, max 5 **hitters** from one team.
5. Do not import `cap_1_of_20` exposure percentages into the single-lineup decision.

## History — superseded salary / RP rules

### SP eligibility (2026-09-18 — Mayza lesson)
Do not roster a pitcher solely because MLB StatsAPI marks them probable if DraftKings tags them **RP** and the card is RP-length.

### SP eligibility v1.1 (2026-09-20 — Alvarez/Holmes lesson)
- DK RP + probable + salary ≥ $6000 as bulk candidate.
- DK RP under $6000 excluded.

**Superseded.** Task 001: an RP-tagged arm with verified starter workload is eligible regardless of salary; an expensive opener stays an opener.
