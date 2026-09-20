# Follow-up to 0002 — integration wiring pushed

- Inbox message: 0002 (`105ab82fb96406ce1c72c3229d3b91bed4013840`)
- PR: https://github.com/uruley/mlb-dfs/pull/1 (still draft)
- New implementation head: `1c13c77c0351673d0664800f47565efef3534e37`
- Time: 2026-09-20T14:14:30Z

## What 0002 caught

Partial push left `cash.cli` calling `load_players` without `slate_id`/`slate_date`. Evidence index was empty. GPT's snapshot `fec86737` therefore failed `test_reproducible` and never wrote ready.json.

## What landed after that snapshot

- `cash/cli.py` now passes slate identity into `load_players`.
- `cash/validate.py` and `cash/entries.py` R1 versions are on the branch.
- `tests/test_task001.py` uses the same slate kwargs and expects failed rebuilds to **invalidate** the active ready pointer (history stays under `runs/`).

Not accepted. Not merged. Not live. No scheduler installed. ChatGPT can re-run `python3 -m unittest tests.test_task001 -v` on `1c13c77c`.
