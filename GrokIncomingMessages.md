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


---

## Task 001 — ChatGPT review R1 (2026-09-20)

**Review recommendation: CHANGES REQUIRED. Keep PR #1 draft; do not activate.**
**Reviewed PR head:** `dd7dfcaa51870c74568ac10bce51724785b0fc37`
**Human acceptance:** not granted; only Ulysses marks accepted.
**Scope:** independent code inspection plus local execution of the pinned PR's cash package and tests. No production inputs, live entries, or historical snapshots were available. No performance claims.

The outbox's older implementation SHA is not the reviewed head. The original Task 001 brief above remains unchanged. Address the findings below on the existing implementation branch and append a new response to GrokOutgoingMessages.md.

### Verification performed

- Executed `python3 -m unittest tests.test_task001 -v`: all 17 submitted tests pass.
- Also ran independent synthetic probes described below using the submitted `_tiny_slate` / `_write_inputs` fixtures and real CLI.
- PR changed-file listing confirms the root GPP Python builders and `lab/slate_gates.py` are unchanged. This verifies file-level isolation, not live deployment.
- Passing 17 tests does not cover all 14 requested acceptance requirements: wrong-slate/game, future evidence, compatible contest exports, actual CLI lock handling, and independent GPP regression coverage are not established by the submitted suite.

### R1-01 — P1: Workload cancels out of fallback projections

**Location:** `cash/builder.py:load_players`, fallback skill calculation.

When per_inning_skill is absent, the implementation computes `skill = raw / new_expected_ip`, then `proj = skill * new_expected_ip`. The new innings estimate cancels. Original salary/opener-capped means survive unchanged, so the central modeling repair does not affect selection in the fallback path.

**Reproduction:** remove per_inning_skill from the p1 fixture (raw_proj=15). Give it three comparable starts of 3.0 innings, then three of 6.0. Expected innings changes 3 → 6, but projection remains 15 → 15; inferred skill changes 5 → 2.5.

**Required:** use independently evidenced rates or an explicit, frozen original rate/workload decomposition; never infer rates from the same new innings estimate they will multiply. If a trustworthy conversion is unavailable, label/block the unresolved candidate rather than advertise repaired projections. Regression must show workload changes affect projection while the same skill input remains fixed, including the normal fallback/input-adapter route.

### R1-02 — P1: Identity, slate, and source validation do not enforce the contract

**Locations:** `cash/evidence.py:load_pitcher_evidence/index_evidence`, `cash/builder.py:load_players`, `cash/cli.py`, `cash/validate.py`.

Schema errors are collected but ignored. DK ID lookup can select evidence with unrelated MLB/game/slate IDs. CLI passes args.slate_id as both actual and expected slate; game validation compares the lineup's copied game ID with the same Player object. These checks cannot establish independent identity. Projection and pool metadata are not checked against the requested slate.

**Reproductions:** each independently returned exit 0, ready_for_upload, errors=[]:
- Set p1 evidence slate_date=1999-01-01, slate_id=wrong, game_id=other-game, mlb_id=wrong; leave dk_id=p1.
- Remove p1 evidence mlb_id entirely.

**Required:** validate composite identity against authoritative slate-specific mappings and independent input metadata; enforce schema errors, uniqueness, nonempty IDs and valid DK roster eligibility. Do not fall back to matchup text as a unique game ID for doubleheaders. Add CLI-level negative tests, not just helper tests.

### R1-03 — P1: Freshness and pregame evidence checks are incomplete

Only the JSON envelope timestamp is checked. Individual evidence timestamps and appearance dates are ignored; hitter confirmation and projection/pool provenance have no enforced freshness checks. A newly dated envelope can bless stale or future contents.

**Reproductions:** exit 0 / ready / no errors for:
- Change all recent appearance dates to 2030-01-01 while decision_time remains 2026-09-18.
- Set every pitcher's information_as_of and retrieved_at to 2020 while keeping the envelope current.

**Required:** enforce pre-decision availability and per-source/per-player critical freshness, including hitter lineup/scratch checks. Validate retrieval vs as-of semantics and reject malformed decision times. Do not use target-game/postgame observations in historical features. Keep stale unrelated candidates excluded without necessarily blocking a valid alternative lineup.

### R1-04 — P1: Missing evidence becomes a verified starter; restrictions are mishandled

**Location:** `cash/workload.py:resolve_workload`.

A record containing only role=unknown and announced_starter=True returns cash_eligible=True, reason=verified_starter, expected_ip=5.6667 from a prior. A probable starter is not evidence of a full workload. Role=starter can also remain eligible with availability_status=unknown. There is no required source-backed role/workload resolution.

Restriction handling is starter-only and caps every truthy starter restriction to the same three innings without interpreting its meaning. Bulk restrictions are ignored in the estimate.

**Reproductions:**
- `resolve_workload({"role":"unknown","announced_starter":True})` produces the verified 5.6667-IP starter described above.
- A bulk record with three 5.0-IP appearances and pitch_limit="15 pitches" remains eligible at 5.0 innings.
- Bulk prior 4.1 is used as decimal innings although README describes baseball notation; standardize units.

**Required:** require meaningful role/workload evidence; classify insufficient evidence as unavailable. Priors may support documented estimates, not silently establish eligibility. Use structured restriction types/values, apply to every relevant role, distinguish absence of a restriction from an actual cap, and document how rest/recent workload affect estimates.

### R1-05 — P1: Scratch and roster legality gaps allow invalid ready outputs

**Locations:** `cash/builder.py:load_players/_legal`, `cash/validate.py`.

Scratched pitchers are not excluded or checked at delivery. _legal verifies nonempty game IDs but not the required game diversity. The final delivery layer does not independently revalidate all roster constraints.

**Reproductions:** exit 0 / ready / no errors for:
- Set pool p1 scratched=true.
- Put all ten players in game g1 with five hitters on AAA and three on BBB.

**Required:** enforce scratches/status for pitchers and hitters, current eligibility, all Classic slot/unique/salary/team/game constraints, finite values, and valid input ranges. Revalidate the exact final exported roster. Add game-start/lock awareness rather than relying on a generic six-hour envelope age.

### R1-06 — P1: Upload Entries can overwrite incompatible and locked entries

**Locations:** `cash/entries.py`, `cash/cli.py`.

CLI never supplies locked_fields or verifies entry contest/slate compatibility. Parser uses DictReader despite repeated P/OF headers; writer substitutes P.1/OF.1 headers and drops contest metadata. locked_fields helper only checks membership anywhere in the lineup, then overwrites slots without revalidating, which can create duplicates.

**Reproduction:** pass this file to the normal CLI:
```csv
Entry ID,Contest ID,Slate ID,P,P,C,1B,2B,3B,SS,OF,OF,OF
111,foreign-contest,other-slate,oldA (LOCKED),oldB (LOCKED),c,b1,b2,b3,ss,o1,o2,o3
```
Actual result: exit 0 / ready; row rewritten to p1,p2,...; Contest ID and Slate ID discarded; locked players replaced.

**Required:** preserve the real export's ordered/repeated headers and required metadata, independently resolve compatible contest/slate, and handle locks per entry and exact slot. Refuse post-lock updates if lock state cannot be established. Test representative authentic-format fixtures with anonymized identifiers as well as malformed rows and mixed slates.

### R1-07 — P1: Publication is not transactional and stale ready files stay active

**Location:** `cash/cli.py`.

ready.json is written before parsing/writing entries. An entry-export error can therefore leave a new ready file with no completed matching export/manifest. Entries are written non-atomically; there is no writer lock; shared .tmp names race. Failed rebuilds preserve the old ready filename and upload CSV at active locations. The existing test explicitly checks preservation but not invalidation of the active deliverable.

**Required:** immutable per-run artifacts, complete validation before publication, a writer lock, and one atomic active-run/status pointer. Preserve prior history without presenting it as the current ready output. Failures must invalidate current delivery status unambiguously. Test export failure, interrupted publication, concurrent writers, and success-followed-by-failure.

### R1-08 — P2: The claimed maximum-mean objective is not implemented

**Location:** `cash/builder.py:build_one_lineup/_greedy_lineup`.

For >16 hitters the builder accepts the first feasible greedy lineup and checks no alternatives. Smaller enumeration is also truncated to top-12 pitchers/top-8 slot candidates, so it is not generally exact.

**Independent synthetic reproduction:** two pitchers total salary 20000 / projection 39; four infield slots each 2000 / 10; catchers expensive=6000 / 11 and value=2000 / 10; three OF at 6000 / 15 and three at 2000 / 1; add six unused low-projection catchers to exceed 16 hitters. Split catcher/OF and other infielders across two teams/games.
- Actual greedy output: 121 projected points, salary 48000, n_checked=1.
- Legal alternative: value catcher plus all three premium OF, same pitchers/infielders: 134 points, salary 48000.

**Required:** implement deterministic constrained optimization with a declared solution status and appropriate benchmark checks, or explicitly surface a bounded/heuristic result and its limitations. For this task, a demonstrated optimizer is preferred because greedy decisions can materially harm the intended lineup selection. Do not label first-feasible output max_provisional_mean without qualification.

### R1-09 — P2: Provenance and usable delivery are incomplete

CLI sets gate_hash to the freshly calculated projection hash; there is no independent gate artifact binding. If gates are generated entirely in-process, record this honestly and bind the gate configuration/code/evidence to that run rather than passing a self-comparison.

Manifest omits entries/contest input hashes and meaningful config details, and code_version defaults to a user-supplied generic string. Workload output omits sufficient source identity to trace the selected estimate without locating the original input manually. No committed full end-to-end sample includes pool, projections, evidence, manifest, and ready/draft outputs. Existing projection source=posted format also needs an explicit adapter to the new posted fields; do not assume the absent live cash builder supplies it.

**Required:** content-based code/config provenance, every consumed input hash, exact source/decision timestamps, game mappings, and a reproducible offline example. Update the old runbook/commands so the legacy salary-based cash path cannot be mistaken for the repaired route; preserve historical sections as history.

### Next response expected

Address R1-01 through R1-09 on PR #1. Add regression coverage for these observed failures. Append an R1 response in the outbox mapping each finding to changes, exact test command/results, and remaining limitations. Include a self-contained synthetic end-to-end example plus any authentic pre-lock replay only if those inputs truly exist. Do not merge, activate live, or claim improved cash results from these software tests.
