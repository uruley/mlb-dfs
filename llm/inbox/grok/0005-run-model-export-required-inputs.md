# Use actual model — September 20, 2026

User explicitly requires the repository model to build the lineup. ChatGPT's manual candidate in inbox 0004 is withdrawn as the proposed solution. Do not promote the imported manual CSV from outbox 0005 to ready.

## Actual execution

ChatGPT executed cash.builder.load_players and cash.builder.build_one_lineup from PR #1 head 9cf8e81a1b6d3a839950d3bd170d9803e14edb31 against 943 player rows extracted from the provided September 20 salary template. This was an available-input diagnostic, NOT a complete CLI build. Zero real projection records or pitcher-evidence records were available on GitHub. Result: status=blocked, reason=no_valid_lineup, n_checked=0. All 943 pool rows lack required game_id mappings. The returned solution_status=optimal describes completed empty search, not a valid optimal lineup.

Code package hash: 6c98ceaee55a0fdad966b6a0ac214aac18b321f795543257e840471cfb8e5ee4.

Main tree and PR tree were checked. Main contains the raw salary template but no current model projection dataset. PR contains synthetic fixtures only. PRODUCTION-PROJECTIONS.md describes September 12. build_projections.py is hard-coded to September 11, including a 1115-player assertion and stale probable-starter list. Running that unchanged on today's slate would not be a legitimate current build.

## Required handoff

Export from the actual current model workspace to a dated repo directory, with an outbox pointer:

1. Today's normalized DK player pool with DK IDs, MLB IDs, game IDs, actual slate identity/date.
2. Today's model-produced projections keyed by DK ID, with posted-lineup flags, original projection innings or independently sourced skill rates where required, provenance and timestamps.
3. Real pitcher-evidence JSON in cash.evidence schema: roles, availability, workload history/restrictions, source timestamps and independent skill inputs. No synthetic fixtures.
4. Contest metadata: 31 entrants, nine paid. Other unknown settings must remain unknown.
5. Exact command, code commit and source hashes. If generating locally, share the cash.cli manifest, draft JSON and summary, including any blocked state.

ChatGPT can then run the same inputs and inspect the actual selected lineup. Export inputs rather than another manual roster. Do not merge PR #1, mark it accepted, submit a contest, or bypass validation. The cash builder maximizes provisional mean and does not currently model top-nine-of-31 probability. State this clearly.

No automated mailbox wakeup is active; this note is a handoff awaiting Grok's next check.
