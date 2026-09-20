# SOURCE NOTE — Baseball Savant expected + barrels (pitcher)

- **Fetched:** 2026-09-12 19:00 UTC
- **File:** `savant-expected-pitchers-2026.csv`
- **Year requested:** 2026
- **Year saved:** 2026
- **Expected-stats min:** min=1
- **Exit-velo/barrels min:** min=1
- **Rows:** 852 (with team attached: 852)
- **UA:** browser-like Chrome desktop
- **Expected URL pattern:** `https://baseballsavant.mlb.com/leaderboard/expected_statistics?type=pitcher&year=…&min=…&csv=true`
- **Statcast URL pattern:** `https://baseballsavant.mlb.com/leaderboard/statcast?type=pitcher&year=…&min=…&csv=true`
- **Team map:** MLB StatsAPI sports/1/players + teams (AZ→ARI, OAK→ATH)

## Fields

- **Expected:** xba (`est_ba`), xslg (`est_slg`), xwoba (`est_woba`); pitchers also xera
- **Contact quality:** hard_hit_pct (`ev95percent`), barrel_pct (`brl_percent`), avg_hit_speed
- **Not on these free boards:** k_pct / bb_pct / whiff_pct (columns present but blank)

## Attempt log

- year=2026 type=pitcher min=1: 852 rows (expected_url)
- year=2026 type=pitcher min=1: 852 rows (statcast_url)

Free public CSV; no paid API. Re-run: `python3 /home/box/mlb-dfs/lab/fetch_savant.py`
