# Production Projections (Tonight)

**Active:** Savant uplift on posted-lineup + MLB StatsAPI probable SPs → `projections-tonight.csv` (`proj_fp` = `savant_proj`)

**As of:** 2026-09-12 19:01 UTC

**Slate:** 2026-09-12 · 5 games · 481 players

## Source pipeline

1. Live 9/12 posted-lineup + MLB probable-SP base (Builder already used this)
   - Backup: `projections-tonight-interim-0912.csv`
2. DFF blend **skipped** (on-disk DFF is 2026-09-11, wrong slate)
3. `lab/fetch_savant.py` → `sources/savant-expected-{batters,pitchers}-2026.csv`
4. `lab/join_savant_features.py` → `lab/features-savant-tonight.csv` (435/481 matched)
5. `lab/project_with_savant.py` → `projections-savant-tonight.csv`
6. Custom publish (not the 9/11 1115-row `publish_savant_projections.py`) → production

## Files

| Role | Path |
|------|------|
| **Production** | `projections-tonight.csv` |
| Interim pre-Savant (9/12 live) | `projections-tonight-interim-0912.csv` |
| Blend (lab/sim default) | `projections-blend-tonight.csv` (`blend_proj` = savant) |
| Savant intermediate | `projections-savant-tonight.csv` |
| Own-model backup (9/12 pre-Savant) | `projections-tonight-own-backup.csv` |
| Summary | `projections-tonight-summary.txt` |
| MLB schedule / probables | `sources/mlb-statsapi-schedule-2026-09-12.csv` |

## Schema

Desk columns: `dk_id,name,position,team,salary,game_info,proj_fp,volatility,sources,notes`

Builder extras kept: `pos,source,game,savant_adj` (`source` = probable_sp|posted|posted_ln|not_in_order|non_starter).

## Lineups

**`lineups-50-tonight.csv` / lock files are NOT auto-rebuilt.**

Builder must rebuild lineups from the new production projections.

`build_lineups_50.py` / `build_projections.py` were not modified.

## MLB probable SPs (StatsAPI 2026-09-12)

LAD Tyler Glasnow · LAA Walbert Urena · BOS Ranger Suarez · CLE Daniel Espino · SD Michael King · SF Cesar Perdomo · MIN Connor Prielipp · WSH Andrew Alvarez · KC Randy Dobnak · MIA Tyler Phillips

## Republish

Re-run fetch → join → project_with_savant, then rebuild production from savant + interim (do not run `lab/publish_savant_projections.py` — it still assumes the 9/11 1115-row slate).
