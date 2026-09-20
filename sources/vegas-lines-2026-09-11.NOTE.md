# Vegas lines — 2026-09-11

## Primary free sources used
1. **ESPN public scoreboard API** (no account / no key)  
   URL: `https://site.api.espn.com/apis/site/v2/sports/baseball/mlb/scoreboard?dates=20260911`  
   Provider embedded: **DraftKings** moneylines, run lines, totals.  
   Method: `curl` / urllib JSON parse of `competitions[].odds[0].moneyline|pointSpread|total`.

2. **VSIN free games page**  
   URL: `https://data.vsin.com/mlb/games/?gamedate=2026-09-11`  
   Used for: EST Score → `implied_away` / `implied_home`, plus free weather blurbs.  
   Method: WebFetch of public HTML tables (Money / OU / EST Score).

## Cross-checks
- DailyFantasyFuel CSV at `sources/dailyfantasyfuel-tonight.csv` has spread / over_under / implied_team_score. Totals and run-line sides broadly match ESPN/VSIN (TEX@ARI total: DFF 9 vs ESPN/VSIN **8.5** — prefer market 8.5).  
- FanDuel Research odds page returned **403** (skipped; not free/scrapable here).  
- The Odds API requires a key — not used.

## Column notes
- `spread` = **away team run line** (e.g. BAL +1.5, LAD -1.5).
- `ml_*` = American odds from DraftKings via ESPN (close).
- `implied_*` = VSIN **EST Score** (model estimate, not pure vig-implied from ML).
- Athletics coded as **ATH** (desk); ESPN/VSIN also use ATH.

## Weather (free, from VSIN + ESPN AccuWeather snippets)
- BAL@TOR: VSIN=CLEAR SKY 69F Wind SSW 6 MPH (Rogers Centre); ESPN=n/a
- CIN@MIL: VSIN=CLEAR SKY 75F Wind S 10 MPH; ESPN=Sunny 72F
- CLE@MIN: VSIN=BROKEN CLOUDS 80F Wind SSW 18 MPH; ESPN=Partly sunny 81F
- CWS@STL: VSIN=OVERCAST CLOUDS 79F Wind SE 9 MPH; ESPN=Intermittent clouds 77F
- HOU@TB: VSIN=Played Indoors (Tropicana Field); ESPN=Intermittent clouds 85F
- KC@BOS: VSIN=OVERCAST CLOUDS 73F Wind NW 10 MPH; ESPN=Mostly sunny 72F
- LAD@MIA: VSIN=MODERATE RAIN 81F Wind SW 5 MPH; ESPN=Thunderstorms 82F
- NYM@NYY: VSIN=OVERCAST CLOUDS 74F Wind NW 6 MPH; ESPN=Sunny 78F
- PHI@ATL: VSIN=FEW CLOUDS 88F Wind NNE 5 MPH; ESPN=Cloudy 82F
- SD@SF: VSIN=SCATTERED CLOUDS 60F Wind WSW 8 MPH; ESPN=7 60F
- SEA@ATH: VSIN=CLEAR SKY 67F Wind S 10 MPH (Sutter Health Park); ESPN=n/a
- TEX@ARI: VSIN=FEW CLOUDS 94F Wind ENE 8 MPH; ESPN=Partly sunny 104F

## Notable vs DFF
- **TEX@ARI total**: market ESPN/VSIN **8.5** vs DFF **9** — use 8.5 for Vegas table.
- **TEX@ARI run line**: ESPN DK has away TEX **-1.5** (ARI home +1.5) while DFF lists TEX **+1.5** / ARI **-1.5**. ML is a pick'em (TEX -102 / ARI -118); RL side can flip across books — flag for desk.
- CLE@MIN and CWS@STL have both MLs negative (two-way juice / near pick'em).

## Coverage
- All 12 slate games: BAL@TOR, CIN@MIL, CLE@MIN, CWS@STL, HOU@TB, KC@BOS, LAD@MIA, NYM@NYY, PHI@ATL, SD@SF, SEA@ATH, TEX@ARI.
- Scraped_at (UTC): 2026-09-11T16:54:55Z

## Caveats
- Lines move; this is a snapshot, not live.
- VSIN EST ≠ sportsbook implied runs from ML (use DFF implied_team_score for alternate).
- MLB Stats API weather is pulled separately by desk; VSIN/ESPN weather here is supplemental only.
- No paid walls used.
