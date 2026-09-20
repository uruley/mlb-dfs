# DraftKings MLB Classic — hard rules (enforce every build)

Source notes: DK upload errors (2026-09-11) + common DK Classic MLB rules (rotoballer / industry standard mirroring DK). Prefer official DK contest rules page when available.

## Roster
- Slots: P, P, C, 1B, 2B, 3B, SS, OF, OF, OF (10 players)
- Salary cap: $50,000 (must be ≤ 50000)
- Use DK player IDs in upload cells: `Name (id)`

## Team / slate constraints (CRITICAL)
- **Max 5 hitters from one MLB team** per lineup. Pitchers do NOT count toward this limit.
- Players must come from the same slate/template.
- Typically must include players from at least 2 different games (standard DK Classic).

## Upload CSV
- Header exactly: `P,P,C,1B,2B,3B,SS,OF,OF,OF`
- No projections columns; lineup rows only
- Up to 500 lineups per file; duplicates skipped by DK

## Builder checklist before writing lineups-*.csv
1. Salary ≤ 50000 for every row
2. Valid positions / eligibility
3. Unique 10 players
4. Team hitter counts ≤ 5 for every team
5. ≥ 2 games represented
6. Validate all rows; do not ship if any fail
