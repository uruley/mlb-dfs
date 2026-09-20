# Synthetic end-to-end example (not a real slate)

Files: pool.csv, proj.csv, ev.json.

```bash
python3 -m cash.cli --slate-date 2026-09-18 --slate-id syn-1 \
  --pool tests/fixtures/e2e-syn1/pool.csv \
  --projections tests/fixtures/e2e-syn1/proj.csv \
  --pitcher-evidence tests/fixtures/e2e-syn1/ev.json \
  --out-dir /tmp/cash-e2e \
  --decision-time 2026-09-18T18:00:00+00:00
```
