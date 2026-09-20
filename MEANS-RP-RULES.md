# Means path — DK-RP MLB-probables

## History (superseded by Task 001 cash path)

The table below was baked into `rebuild_means_tonight.py` as of 2026-09-20. It used a **$6,000 salary discontinuity**. Task 001 cash builds must **not** use this table for role or expected innings. GPP/means file left in place so GPP is not silently changed.

| Case | Historical rule | `source` tag |
|------|-----------------|--------------|
| DK Position=SP + MLB probable | Full starter IP means | `probable_sp` |
| DK Position=RP + MLB probable + salary ≥ $6000 | ~4.5–5.5 IP bulk/starter means | `probable_bulk` |
| DK Position=RP + MLB probable + salary < $6000 | Mayza-class opener cap (~1.0–1.5 IP) | `probable_opener` |
| DK Position=RP, not MLB probable | Bullpen floor | `rp` |

## Task 001

Role and expected IP come from `pitcher-evidence.json` via `cash.workload.resolve_workload`. DK label and salary are roster facts only.
