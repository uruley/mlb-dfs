# Cash path (Task 001)

Dedicated cash builder. Does **not** import or rewrite `build_lineups_50.py` / GPP gates.

## Command

```bash
python3 -m cash.cli \
  --slate-date YYYY-MM-DD \
  --slate-id SLATE_ID \
  --pool path/to/dk-classic-player-pool.csv \
  --projections path/to/projections.csv \
  --pitcher-evidence path/to/pitcher-evidence.json \
  --out-dir path/to/out \
  --entries path/to/user-export.csv \
  --decision-time 2026-09-18T23:00:00-05:00 \
  --expected-projection-hash HASH
```

Offline only. Collection is a separate step. Identical frozen inputs reproduce the same lineup (timestamps in the manifest may differ).

## Objective

Maximize documented provisional mean `proj_fp` under DK Classic constraints. This is **not** maximum cash probability and not a calibrated floor.

## Pitcher evidence

JSON keyed by `mlb_id` + `game_id` + `dk_id`. Role (`starter|opener|bulk|relief|unknown`) is independent of DK SP/RP and salary. Missing/conflicting workload → pitcher is cash-ineligible; a selected pitcher with unresolved evidence blocks `ready_for_upload`.

Expected IP uses comparable-role samples; small samples shrink toward an **explicit** prior (starter 5.2 baseball = 17 outs, bulk 4.1, opener 1.0). Salary is never used to classify workload.

## Outputs

| File | When written |
|------|----------------|
| `lineup-1-cash.draft.json` | always |
| `lineup-1-cash.ready.json` | only if all gates pass |
| `lineup-1-cash-ENTRIES-UPLOAD.csv` | ready + `--entries` |
| `manifest.json` | always (hashes, freshness, validation) |
| `lineup-1-cash-summary.txt` | always |

A failed rebuild does not overwrite an existing ready file.

## Tests

```bash
python3 -m unittest tests.test_task001 -v
```
