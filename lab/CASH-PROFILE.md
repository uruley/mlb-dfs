# Cash / multiplier gate profile ($1–$3)

See desk rules: `DK-MLB-MULTIPLIER-CASH-RULES.md`.

## Task 001 cash builder (2026-09-20) — current

Use `python3 -m cash.cli` (see `cash/README.md`). Workload and cash eligibility come from pitcher-evidence JSON, not DK salary and not the $6,000 RP cutoff.

`lab/slate_gates.py` **GPP profile is unchanged**. The cash constants still in that file (`CASH_RP_BULK_MIN_SALARY=6000`, `ELITE_SP_FLOOR_BOOST=0.05`) apply only if you invoke `--profile cash` on the old exporter. Do not treat that exporter as the Task 001 cash path.

Honest objective of the new builder: maximize provisional mean `proj_fp`. Not cash probability. The former +5% elite mean bump is **not** applied on this path.

## History (do not use as live cash rules)

### v1.1 (2026-09-20) — Mayza refine after Alvarez/Holmes overcorrection

Salary-gated RP exclude ($6k). Marked superseded by Task 001.

### Mayza lesson (2026-09-18)

Cash LU rostered Tim Mayza (DK `RP`, MLB probable opener) and got crushed.
v1 response: hard-exclude all DK-RP.

### Alvarez/Holmes overcorrection (2026-09-19)

Winner SP pair was Alvarez + Holmes (both DK-RP). v1.1 salary-gated the RP exclude.

Task 001 replaces that heuristic with explicit role/workload evidence.
