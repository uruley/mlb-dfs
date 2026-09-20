# SOURCE NOTE — Daily Fantasy Fuel (tonight)

- **Date:** 2026-09-11
- **File:** `dailyfantasyfuel-tonight.csv`
- **Method:** CSV already on disk at desk drop (Ulysses → MLB Manager). Exact export URL/session not recorded on this box.
- **Rows:** 340 players · **Teams:** 24 (12-game slate)

## Field quality
| Field | Fill | Notes |
|-------|------|-------|
| `ppg_projection` / `value_projection` | 100% | Primary free proj signal |
| `L5` / `L10` / `szn_fppg_avg` | ~100% | 1 blank szn |
| `spread` / `over_under` / `implied_team_score` | 100% | Vegas from DFF |
| `ownership_projection` | **0%** | Always blank — do not use for ownership |
| `confirmed_order` | 215/340 (63%) | 125 blank — unconfirmed batting orders |
| `starting_pitcher` | 23 `YES` | Rest blank (not tagged SP starter) |
| `injury_status` | 11 tagged | 8 DTD, 3 O; 329 blank (blank ≠ healthy) |
| `slate` | blank column | Unused in this export |

## Caveats for sim lab
1. **Ownership unusable** — column present but empty for all rows.
2. **Orders partial** — treat blank `confirmed_order` as unconfirmed.
3. **Injury blanks** — only DTD/O flagged; most players blank.
4. **Hand / SP tags** — useful for starters tagged YES; non-starters not explicitly marked NO.

Ready for blend with own-model under `/home/box/mlb-dfs/lab`. Scout standing by for next free CSV pulls when asked.
