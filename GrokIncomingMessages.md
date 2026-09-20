# Grok Incoming Messages

## Task 001 — Repair pitcher workload and make cash builds reproducible

**Status:** Ready for implementation
**Requested by:** Ulysses
**Prepared by:** ChatGPT, 2026-09-20
**Reviewed baseline:** `651353e9e742ef882c9c9190b5761c416aa45bc3`
**Handoff:** Grok implements; Ulysses returns to ChatGPT for independent review.

### Objective and boundaries

Repair the existing cash-game pipeline incrementally. First establish trustworthy pitcher role/workload inputs and a reproducible cash build. This task is an engineering repair, not evidence that the strategy is profitable.

Read this entire brief, inspect the latest repository and applicable instructions, and preserve unrelated work. Compare any changes since the reviewed baseline before implementing. Use a dedicated branch and provide a reviewable commit or PR; do not automatically merge or activate the repaired pipeline for live entries. Do not submit contests, spend money, buy feeds, or overwrite historical pre-lock artifacts. Use available free sources and local historical inputs.

Do not add more agent roles, redesign the entire system, or tune rules until a previously losing lineup becomes a winner. Do not implement the later research tasks below in this pass.

### Findings motivating this repair

1. `rebuild_means_tonight.py` estimates starter innings, strikeouts, and other components mostly from salary tiers. RP probable pitchers are classified into opener/bulk using a $6,000 cutoff.
2. `lab/process/CASH-PIPELINE-RUNBOOK.md` records Mayza's workload mistake, the blanket RP exclusion, and the subsequent Alvarez/Holmes reversal. These outcomes expose a role/workload modeling gap; they do not establish which pitchers were optimal before lock.
3. `lab/slate_gates.py` uses salary/position eligibility, a 5% elite-SP mean boost, and mean-projection cutoffs described as floors. A mean cutoff or boost is not a downside estimate.
4. Cash documentation conflicts: some sections prohibit all RP pitchers while newer sections allow price-qualified RP pitchers. The exporter still emits 20-lineup exposure hints although the runbook calls for one cash lineup.
5. The runbook records stale gates, multiple writers, an old watcher target, scheduling failures, and polluted entry exports.
6. The committed repository has a cash-lineup summary but no clearly identified dedicated cash-builder implementation or raw contest CSVs. Locate the actual local cash builder and preserve its relevant behavior; if it is agent-generated/ad hoc, bring the reproducible implementation into version control. Do not pretend missing inputs were reviewed.

Relevant files: `rebuild_means_tonight.py`, `lab/slate_gates.py`, `lab/export_builder_gates.py`, `lab/export_cash_gates.py`, `lab/CASH-PROFILE.md`, `DK-MLB-MULTIPLIER-CASH-RULES.md`, `lab/process/CASH-PIPELINE-RUNBOOK.md`, `lineup-1-cash-summary.txt`.

### A. Explicit pitcher evidence and role resolution

Create a structured pitcher-evidence input keyed by stable MLB player ID and game ID, mapped explicitly to slate-specific DK ID. Position eligibility, announced starting role, and expected workload are separate facts.

Capture at least:
- Slate date/ID, game ID, MLB player ID, DK ID and DK roster eligibility.
- Announced starter status; role: starter, opener, bulk, relief, or unknown.
- Recent dated appearances, starts, outs recorded, pitches where available, and days of rest.
- Available pitch-limit, injury-return, role-change, and bulk-assignment information, with source and timestamp.
- Evidence retrieval time, information-as-of time where known, conflicts/missing fields, and a reasoned confidence/availability status.
- Expected innings and the method/evidence supporting that estimate.

Use documented available source fields. Do not invent an API field that supplies expected innings or proves a bulk role. If role information requires a manually entered source-backed note, support that honestly. A probable-pitcher listing identifies who starts, not how many innings they will pitch. A bulk pitcher may follow an opener and need not appear as probable.

Handle innings as outs/3: baseball notation 5.2 means five innings and two outs, not 5.2 decimal innings.

Resolve conflicts explicitly; insufficient workload evidence makes a pitcher unavailable for the cash candidate pool with a clear reason. Missing unrelated players need not block an otherwise valid build. Block final delivery if a selected player's critical evidence is unresolved or no valid lineup can be built.

### B. Replace the workload shortcuts

- Remove DK salary, DK SP/RP label, hardcoded player-name lists, and yesterday's fantasy score as decisive role/workload evidence.
- Estimate starter/bulk workload from pregame evidence, such as recent comparable-role starts, pitch counts, rest, restrictions, and appropriate sample-size fallback. Document weights and fallback assumptions.
- Small samples must not silently become confident full-start estimates. Any prior must be explicit and sensitivity-checkable.
- Support verified full-workload RP-tagged starters and genuine openers tagged SP. Actual DK roster eligibility still governs legal selection.
- Remove the $6,000 opener/bulk discontinuity and blanket RP exclusion from the cash path.
- Do not replace these with another price cutoff or automatic $9,000 ace requirement.
- Integrate expected innings into pitcher fantasy-point calculations. Separate workload from per-inning skill estimates so changing salary alone cannot change expected innings.
- Keep any unrepaired skill-rate/salary proxy clearly labeled as provisional. Do not describe this limited repair as a complete projection-model replacement.
- Remove the cash-only 5% elite mean inflation as a purported floor measure. Preserve raw projected means separately from any explicit selection preference. Audit xERA exclusions and elite bypasses; do not represent them as verified workload or downside protection.
- Preserve GPP behavior unless a shared change is required for correctness; disclose and test any such impact.

### C. One reproducible cash-build command

Deliver one documented CLI command with explicit slate date, input locations, and output directory. Avoid hardcoded September dates and mandatory `/home/box` paths. Separate live data collection from building: the build must be rerunnable offline from frozen inputs.

The cash builder must:
- Produce one lineup deterministically from identical inputs/configuration; use a fixed documented tie-break or seed if needed.
- State its actual objective. Maximizing a documented provisional mean is acceptable for this repair; do not claim maximum cash probability or a calibrated floor.
- Separate configurable construction preferences from player projections. Do not mechanically import `cap_1_of_20` or exposure percentages into a single-lineup decision.
- Report selected pitcher workload evidence and excluded pitchers with reasons.
- Validate salary, slots, duplicate players, applicable DK team/game constraints, slate membership, and posted hitter orders for final delivery.
- Validate game-specific eligibility/status and avoid team-only joins that confuse doubleheaders.
- Require an explicit freshness policy for critical pre-lock information and record the age of the checks. Do not quietly turn unknown status into confirmed.
- Distinguish a research/draft output from a deliverable upload. Drafts with unresolved information must never receive a ready-for-upload status.
- Record exact contest metadata when supplied; label missing metadata. Do not claim triple-ups and 50/50s have the same payout objective.
- Preserve numeric real Entry IDs only when creating Upload Entries files; exclude instructions and player-pool sections. Match each entry to its actual compatible slate/contest, retain required identifiers, and preserve locked slots. If a post-lock update cannot safely preserve locks, refuse it.
- Run all validation before publishing final output. Use a single writer and atomic publication so a failure cannot leave a newly labeled ready file containing stale/partial results.

Save a manifest including input hashes, code version, configuration, slate/game identifiers, source timestamps, validation results, and output hashes. Gates must reference the exact projection input hash; comparing modification times alone is insufficient. Never silently fall back to a stale `tonight` file. Historical replay must evaluate freshness relative to the historical decision time, not today's clock.

### D. Focused acceptance checks

Use small offline fixtures and meaningful regression tests. Synthetic fixtures verify software behavior only; label them as synthetic.

Required cases:
1. RP-tagged probable with verified normal starter workload remains eligible independent of salary.
2. RP-tagged expensive opener remains classified as opener; high price cannot grant full innings.
3. Low-priced verified starter is not excluded solely for being under $6,000.
4. SP-tagged restricted/opener pitcher does not automatically receive five-plus innings.
5. Announced bulk pitcher not listed as probable is recognized separately; cash availability depends on evidence and documented policy.
6. Unknown/conflicting selected-player workload blocks final delivery and explains why.
7. 5.2 baseball innings converts to 17 outs / 3 innings correctly.
8. Changing salary alone does not change workload classification or expected innings.
9. Wrong-slate, wrong-game/doubleheader, stale critical data, or projection/gate hash mismatch cannot yield a final-ready file.
10. Unposted/scratched selected hitter fails final validation.
11. Entry export with four real Entry IDs plus instructions/player-pool rows produces exactly four compatible entry rows; locked slots are preserved or the update is refused.
12. Identical frozen inputs reproduce the same lineup and substantive results; generated timestamps may differ.
13. Failed builds do not overwrite a good historical artifact or leave a stale output advertised as ready.
14. Cash-path changes do not silently alter the GPP path.

If authentic pre-lock September 18–19 source snapshots are available locally, replay them and compare role/workload decisions. Do not use later game logs, season statistics including the target game's outcome, or postgame knowledge as pregame features. If suitable snapshots are unavailable, report that limitation and stop short of historical performance claims.

### E. Deliverables for ChatGPT review

Commit implementation, focused tests/fixtures, and updated cash documentation on the implementation branch. Reconcile superseded RP rules instead of leaving contradictory instructions. Keep the original historical record clearly marked as history.

Create `GrokOutgoingMessages.md` with:
- Task ID, completion status, branch and implementation commit(s).
- Files changed and concise rationale.
- Exact build/test commands and actual results, including failures.
- Evidence schema, workload method, freshness policy, and remaining proxies.
- A small before/after table for representative opener, starter, bulk, and unknown cases.
- Location of reproducible sample inputs, manifest, validation report, and candidate output.
- Whether historical replays used authentic pre-lock evidence; missing inputs and blockers.
- Whether the actual live cash builder was located and integrated.
- GPP effects, unresolved risks, and explicit confirmation that live activation/contest submission did not occur.

Do not claim tests passed unless executed. Do not report profits or improved cash rates based on synthetic cases, selected winning players, or one/two slates. Keep this incoming brief intact; place responses in the outgoing file.

### Later work — record, do not implement in Task 001

- Replace remaining salary-derived skill estimates with independently grounded, calibrated projections.
- Evaluate hitter plate appearances, handedness, opposing starter/bullpen mix, and documented environment inputs.
- Build contest-specific payout evaluation with actual field size, paid places, ties, and fees.
- Replace independent normal lineup simulations and fixed stack bonuses with validated outcome distributions and correlations if justified.
- Benchmark on untouched later slates against simple baselines; preserve all pre-lock snapshots.
- Track cash-line margin, fees/payouts/ROI, and operational errors by contest type.
- Do not use "players who actually scored 20+" as evidence of systematic mean underprojection; selecting on the outcome creates bias.

**Definition of done:** A reviewer can reproduce the candidate cash build, trace each selected pitcher's workload to pregame evidence, verify all delivery gates, and inspect the changes without relying on an agent's narrative. This does not require or establish a profitable strategy.
