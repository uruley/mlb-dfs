# Cash path (Task 001 / R1)

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

Maximize documented provisional mean `proj_fp` under DK Classic constraints when `solution_status=optimal`. This is **not** maximum cash probability and not a calibrated floor. If the node budget is exhausted the objective is labeled `bounded_heuristic_provisional_mean`.

## Pitcher evidence

JSON keyed by `slate_date + slate_id + game_id + mlb_id + dk_id`. Role (`starter|opener|bulk|relief|unknown`) is independent of DK SP/RP and salary. Announced/probable starter is not full-workload evidence. Missing/conflicting/unknown availability → cash-ineligible.

Expected IP uses comparable-role samples. Priors (starter 5.2 baseball = 17 outs, bulk 4.1, opener 1.0) may fill an estimate after eligibility is established; they do not grant eligibility. Restrictions are structured (pitch count / max IP) and apply to every relevant role. `4.1` is baseball notation.

Pitcher fantasy points use an independent per-inning skill rate (evidence field or frozen original IP). Skill is never inferred from the new expected IP.

## Outputs

| File | When written |
|------|----------------|
| `runs/<id>/...` | immutable per-run artifacts |
| `status.json` | only active delivery pointer |
| `lineup-1-cash.draft.json` | always (copy of current run draft) |
| `lineup-1-cash.ready.json` | only if current run is ready; deleted on failure |
| `lineup-1-cash-ENTRIES-UPLOAD.csv` | ready + compatible `--entries` |
| `manifest.json` | always (hashes, freshness, validation) |
| `lineup-1-cash-summary.txt` | always |

A failed rebuild preserves history under `runs/` and **invalidates** the active ready pointer.

## Tests

```bash
python3 -m unittest tests.test_task001 -v
```

Synthetic e2e inputs: `tests/fixtures/e2e-syn1/`.
