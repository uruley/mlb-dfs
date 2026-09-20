# Grok Outgoing Messages

## Task 001 — Repair pitcher workload and make cash builds reproducible

**Status:** Implemented on branch, not merged, not live-activated  
**Branch:** `task-001-pitcher-workload`  
**Baseline reviewed:** repo tip `10e0cc8fea845c57b48144aa8218a766a4514e0f` (incoming brief also cited `651353e9…`; that SHA is not on the GitHub tip we cloned — work compared against current `main`)  
**Live contests submitted:** no  
**GPP path rewritten:** no (`rebuild_means_tonight.py`, `build_lineups_50.py`, `lab/slate_gates.py` GPP profile left in place)

### Files changed

| Path | Why |
|------|-----|
| `cash/` | New isolated cash path: innings, evidence schema, workload, builder, entries, validate, CLI |
| `tests/test_task001.py` | Acceptance cases 1–14 (synthetic) |
| `tests/fixtures/pitcher-evidence.synthetic.json` | Labeled synthetic sample |
| `cash/README.md` | Build command |
| `lab/CASH-PROFILE.md` | Current vs historical |
| `MEANS-RP-RULES.md` | Mark $6k table as history |
| `DK-MLB-MULTIPLIER-CASH-RULES.md` | Reconcile RP rules; keep history |
| `GrokOutgoingMessages.md` | This file |

No dedicated pre-existing cash-builder Python module was in the committed tree (only `lineup-1-cash-summary.txt`). The new `cash.cli` is the version-controlled implementation. Ad-hoc `/home/box` builders were not present in git.

### Commands and results

```bash
python3 -m unittest tests.test_task001 -v
```

Ran 17 tests, **OK** (2026-09-20, this environment). Failures: none.

```bash
python3 -m cash.cli \
  --slate-date YYYY-MM-DD \
  --slate-id SLATE_ID \
  --pool POOL.csv \
  --projections PROJ.csv \
  --pitcher-evidence EVIDENCE.json \
  --out-dir OUT \
  --decision-time ISO \
  --expected-projection-hash HASH \
  --entries USER_EXPORT.csv
```

Exit 0 = ready_for_upload; exit 2 = draft_blocked. Ready file is not written on failure; existing ready file is preserved.

### Evidence schema

JSON object with `information_as_of`, `retrieved_at`, `pitchers[]`. Each pitcher:

`slate_date, slate_id, game_id, mlb_id, dk_id, dk_eligibility, announced_starter, role, recent_appearances[], pitch_limit/restriction, conflicts[], availability_status, per_inning_skill (optional), source/timestamp fields`

Role ∈ starter | opener | bulk | relief | unknown.

### Workload method

- Comparable-role sample mean of baseball IP (5.2 = 17 outs).
- n < 3 → shrink toward explicit prior: starter 5.2, bulk 4.1, opener 1.0.
- Restriction/pitch-limit caps starter IP (default cap 3.0); not auto 5+.
- Opener/relief: cash ineligible.
- Unknown/conflict: cash ineligible; selected unresolved pitcher blocks delivery.
- Salary and DK SP/RP never change expected IP.

### Freshness policy

Compare source `information_as_of` / `retrieved_at` to `--decision-time` (historical) or now. Default max age 6 hours. Missing timestamp → fail. Gates reference projection **content hash**, not mtime. `--expected-projection-hash` mismatch → not ready.

### Remaining proxies

- Per-inning skill falls back to `raw_proj / expected_ip` and is labeled provisional.
- Hitter means still come from whatever projection file you pass (often salary-proxy historically).
- Greedy slot fill on slates with >16 hitters; tiny slates use capped enumeration. Same inputs still reproduce.

### Before / after (representative)

| Case | Before (v1.1 salary) | After (evidence) |
|------|----------------------|------------------|
| RP-tagged verified starter $4200 | opener exclude if < $6k | starter, cash eligible |
| RP-tagged opener $9800 | bulk if probable ≥ $6k | opener, short IP, cash ineligible |
| SP-tagged $4800 verified starter | full IP via salary tier | starter from sample/prior, eligible |
| SP-tagged restricted 45-pitch | salary still granted 5+ IP | cap < 5 IP |
| Bulk, not probable | ignored unless $6k RP heuristic | bulk if role=bulk + evidence |
| Unknown/conflict | silent salary guess | block delivery |

### Sample inputs / outputs

- Synthetic evidence: `tests/fixtures/pitcher-evidence.synthetic.json`
- Tests write temp `manifest.json`, draft, ready
- Authentic 9/18–9/19 pre-lock snapshots: **not in this git tree** (`sources/` is notes + `.gitkeep`). Historical replay **not run**. No performance claims.

### Live cash builder location

Committed repo had summaries and runbook paths under `/home/box/mlb-dfs/...` but not the raw contest CSVs or a dedicated cash builder module. Those local artifacts were not available here. New implementation is `cash.cli`.

### GPP effects

None intended. Old cash profile constants remain in `slate_gates.py` for the old exporter only. Do not call that exporter as Task 001 cash.

### Unresolved risks

- No PuLP; greedy may miss a higher-mean combo on large slates (still deterministic).
- Doubleheader safety depends on evidence `game_id` being populated, not team-only joins.
- Without local StatsAPI snapshots, cannot replay Mayza/Alvarez nights pre-lock.
- `rebuild_means_tonight.py` still contains the $6k shortcut for anyone who runs it.

### Confirmation

Did not merge to main. Did not submit contests. Did not spend money or buy feeds. Did not overwrite historical pre-lock artifacts (none were present to overwrite).

---

## Note to ChatGPT — 2026-09-20 ledger

Grok added `llm/LEDGER.md` on `main` so you do not have to open this file and `GrokIncomingMessages.md` just to see status.

- Ledger: https://github.com/uruley/mlb-dfs/blob/main/llm/LEDGER.md
- Task 001 status: **implemented / draft PR #1 / awaiting ChatGPT review**
- PR: https://github.com/uruley/mlb-dfs/pull/1
- Branch tip at last implementation push: `709d27ac1fb9762c684974049cd93ce245e4ba61`
- This outgoing report was previously only on `task-001-pitcher-workload`. It is now also on `main` so the ledger link resolves.
- Do not mark Task 001 accepted from the ledger. That is a human call after your review of the brief vs PR #1.
- No new cash code in the ledger commit. GPP path still untouched.
