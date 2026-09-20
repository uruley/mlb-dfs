# MLB DFS Cash / Multiplier Pipeline (repeatable)

## Goal
Single-entry $1–$3 DraftKings MLB multipliers (cash-style): one floor lineup, Upload Entries CSV that replaces user’s Entry IDs.

## Happy path (roles)
1. **User** drops Classic slate template (+ Entry export when editing).
2. **MLB Manager** saves pool (`dk-classic-player-pool.csv`), owns lock clock, delivery, and hole log.
3. **DFS Scout** — free slate intel only (weather, parks, confirmed SP notes, free proj links). No paid feeds.
4. **DFS Projections** — mean `proj_fp` for every DK ID on the slate → `projections-tonight.csv`.
5. **Mad Scientist** — cash profile gates only (lab copy / `builder-gates-cash-tonight.csv`). Never mid-slate live patches. No new cash projection model in v1.
6. **DFS Builder** — ONE cash lineup under cash rules; writes:
   - `lineup-1-cash.csv` / `lineup-1-cash-LOCK-LINEUP-UPLOAD.csv`
   - `lineup-1-cash-ENTRIES-UPLOAD.csv` (from `user-entered-tonight.csv`)
7. **MLB Manager** verifies vs MLB Stats API (probables + posted orders), attaches Entry-ID file, tells user Upload Entries.

## Hard rules
- DK Classic: P/P/C/1B/2B/3B/SS/OF/OF/OF, $50k, max 5 **hitters**/team.
- Cash: floor SP, chalk OK, 3–4 stack, posted bats only near lock.
- Docs: `DK-MLB-MULTIPLIER-CASH-RULES.md`, `DK-MLB-CLASSIC-RULES.md`.

## Anti-collision
- Manager assigns Builder as sole writer of `lineup-1-cash*`. Manager may verify/patch scratches only.
- No parallel Manager+Builder builds without an explicit “Builder stand down” or “Manager stand down”.

## Known holes (living list — append during runs)

### Found before / during 2026-09-18 audit kickoff
1. **5:30 one-shot cron never fired** — user had to ask; Manager rebuilt manually; routine deleted. Need reliable pre-lock job or Manager checklist alarm.
2. **Manager + Builder parallel builds** — overwrite race on lineup CSVs; need sole-writer rule (now in runbook).
3. **Watcher file drift** — `dfs-lineups.csv` stayed on Sep 13 20-bag until manually pointed at cash; watcher also paused for credits.
4. **No dedicated cash projection model** — v1 reuses means + cash gates only (acceptable; document so we don’t pretend otherwise).
5. **Upload path confusion** — Lineup Upload vs Upload Entries; cash edit flow must default to Entry-ID CSV.
6. **Early build before cards** — salary/TBD proxies then scratch swaps (Robles); near-lock rebuild must require posted orders.

### Audit run log 2026-09-18 ~5:46pm CT
- Mad Scientist: cash gates OK → builder-gates-cash-tonight.csv (elite_sp=12, smash tag-only). Builder pinged.

7. **Gate-before-projections race** (caught 5:48pm CT audit): Mad Scientist cut cash gates, then Projections refreshed `projections-tonight.csv`. Builder may build on stale means/gates. **Rule:** hard sequence Projections → Mad Scientist → Builder; Manager must block Builder until gates mtime ≥ projections mtime.

### Audit ~5:48–5:49pm CT
- Projections refresh landed; MS re-cut → elite_sp **14** (was 12), smash tag-only.
- Builder ordered to discard pre-refresh build and rebuild after new gates.

8. **DK RP mis-tags for starting pitchers** (Scout 09/18): Mayza, Sandlin, Hughes are MLB SPs today but DK Position=RP. Builder/Projections must always include MLB StatsAPI probables regardless of DK SP/RP label.
9. **Salary-leader ≠ probable SP**: high-salary SP pool names (Misiorowski/Schlittler/Sale/Luzardo) can be chalk noise; gate on MLB probable list.
10. **Scout timing**: brief can land after Projections/gates; for cash, Scout is advisory not a hard gate — but RP-override must be in Builder permanently.

Scout brief: lab/process/scout-brief-2026-09-18.md

11. **Builder latency / silent stall** (5:51pm CT): after HOLD+rebuild orders, cash files stayed at Manager 22:39Z while gates were 22:48Z; user had to ask “did we get lineup yet?”. Need Builder SLA ping or Manager timeout takeover (~5–10 min).

### Audit complete ~5:52pm CT — Builder cash LU
- Woo / Mayza (RP→SP override worked) + SEA×4 + COL×3, $49.8k, all posted — MLB verify PASS.
12. **Entry-ID file pollution**: Builder reported “1212/1212 Entry-IDs filled” but file was the full slate export (1213 rows) with only 4 real Entry IDs. Manager rewrote clean 4-row `lineup-1-cash-ENTRIES-UPLOAD.csv` from `user-entered-tonight.csv`. **Rule:** fill only rows whose Entry ID is numeric; never treat Instructions/player-pool rows as entries.

13. **Mayza hole (2026-09-18 live):** Scout HARD “RP→SP probable override” put Tim Mayza in cash; DK card was RP (short outs). He got rocked. **Cash rule:** no RP-tagged arms on probable-override alone; require DK SP (or proven starter workload). Override still OK to *recognize* them as pitching today for GPP/notes, not for cash SP2.

14. **Lab fix shipped 2026-09-18 night:** `slate_gates` cash profile `CASH_EXCLUDE_DK_RP=True` — DK RP never elite-tagged / always exclude for cash even if MLB probable. Re-exported `builder-gates-cash-tonight.csv`: Mayza `exclude` (`cash_dk_rp_opener`); 0 RP-probable keeps. Also flag: Projections had assumed IP~5.0 for RP probable — soften that assumption next slate.

15. Mad Scientist follow-up: cash PITCHER_FLOOR 8→10; elite_sp requires DK SP + salary≥$6500. Mayza still exclude. Next builds use updated builder-gates-cash-tonight.csv.

## Lock delivery rules (2026-09-19)
1. **Sole lock file:** `lineup-1-cash-ENTRIES-UPLOAD.csv` (Upload Entries). Bare Lineup Upload only as secondary.
2. **Sole writer:** DFS Builder writes cash lineup files; Manager only MLB-verifies + delivers (no parallel builds).
3. **Hard stop before deliver:** refuse if any pitcher is DK `Position=RP` or not today’s MLB probable SP.
4. **Pre-lock verify:** when user pastes/exports entries, one confirm vs MLB cards — prefer that over a continuous 30‑min watcher (credits).
5. **User tip:** if multiple CSVs landed in chat, only trust the file Manager labels “Upload Entries” after verify.

16. **Pitcher selection postmortem 2026-09-19 Triple Up:** Our Detmers (9.65) + Mize (−5.25) vs winner Alvarez (25.9) + Holmes (16.7). Winner pair were DK **RP** hard-excluded by Mayza cash rule; our proj capped them ~3–4 FPTS. Overcorrection: blanket CASH_EXCLUDE_DK_RP blocked the actual winning starters. Also avoided Skubal/Schlittler to fund SEA/COL stack. Next: smarter opener-vs-bulk rule + don’t auto-punt aces for chalk bats.

17. **Cash SP v1.1 (approved 2026-09-20):** After Alvarez/Holmes beat us while excluded as RP:
- DK RP + (not probable OR sal<$6k) → hard exclude (Mayza)
- DK RP + probable + sal≥$6k → keep as cash_rp_bulk_candidate (never elite)
- Projections: bulk IP ~4.5–5.5 for those arms (no IP~1 cap)
- Builder soft: prefer ≥1 ace (≥$9k); don’t punt both top SPs for Coors+mid pair
