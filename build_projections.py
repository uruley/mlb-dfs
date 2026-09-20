#!/usr/bin/env python3
"""
DK MLB Classic fantasy-point projections for 2026-09-11 main slate.
Method: own-model with FantasyPros probable-starter tags.
Transparent, reproducible salary/park/matchup proxies.
"""
from __future__ import annotations

import csv
import math
import re
from collections import defaultdict
from pathlib import Path

POOL = Path("/home/box/mlb-dfs/dk-classic-player-pool.csv")
OUT = Path("/home/box/mlb-dfs/projections-tonight.csv")
SUMMARY = Path("/home/box/mlb-dfs/projections-tonight-summary.txt")

# FantasyPros probable starters for Fri Sep 11, 2026 (exact name match in pool)
PROBABLES = {
    # team -> starter full name
    "BAL": "Chris Bassitt",
    "TOR": "Max Scherzer",
    "CIN": "Andrew Abbott",
    "MIL": "Dustin May",
    "CLE": "Parker Messick",
    "MIN": "Taj Bradley",
    "CWS": "Anthony Kay",
    "STL": "Matthew Liberatore",
    "HOU": "Miguel Ullola",
    "TB": "Drew Rasmussen",
    "KC": "Seth Lugo",
    "BOS": "Sonny Gray",
    "LAD": "Blake Snell",
    "MIA": "Ryan Gusto",
    "NYM": "Nolan McLean",
    "NYY": "Carlos Rodon",
    "PHI": "Aaron Nola",
    "ATL": "Chris Sale",
    "SD": "Robbie Ray",
    "SF": "Anthony Molina",
    "SEA": "George Kirby",
    "ATH": "Jeffrey Springs",
    "TEX": "Kumar Rocker",
    "ARI": "Merrill Kelly",
}

# Home venue run park factors (100=avg). Documented simple table blending
# Statcast 2024-26 / FanGraphs-style knowledge for tonight's home parks.
PARK_RUN = {
    "TOR": 102,  # Rogers Centre
    "MIL": 101,  # American Family Field
    "MIN": 100,  # Target Field
    "STL": 96,   # Busch Stadium (pitcher-friendly)
    "TB": 100,   # Tropicana / Steinbrenner proxy
    "BOS": 103,  # Fenway
    "MIA": 97,   # loanDepot (pitcher-friendly)
    "NYY": 101,  # Yankee Stadium (HR-friendly)
    "ATL": 100,  # Truist Park
    "SF": 94,    # Oracle Park (very pitcher-friendly)
    "ATH": 103,  # Sutter Health Park (Athletics)
    "ARI": 101,  # Chase Field
}

# Team offense strength proxy (relative index ~1.0 avg) from 2026 reputation + salary tops
TEAM_OFFENSE = {
    "LAD": 1.12, "NYY": 1.10, "PHI": 1.08, "ATL": 1.06, "HOU": 1.05,
    "NYM": 1.05, "SEA": 1.04, "SD": 1.04, "MIL": 1.03, "BOS": 1.03,
    "TB": 1.02, "CIN": 1.02, "CLE": 1.01, "KC": 1.01, "TOR": 1.00,
    "BAL": 1.00, "ARI": 0.99, "MIN": 0.98, "STL": 0.98, "TEX": 0.97,
    "SF": 0.96, "ATH": 0.95, "MIA": 0.93, "CWS": 0.90,
}

# Ace / elite SP names for opposing quality bump (beyond salary)
KNOWN_ACES = {
    "Chris Sale", "Blake Snell", "Parker Messick", "Nolan McLean",
    "Carlos Rodon", "Drew Rasmussen", "George Kirby", "Sonny Gray",
    "Robbie Ray", "Taj Bradley", "Jacob Misiorowski", "Cam Schlittler",
    "Cristopher Sanchez", "Jesus Luzardo", "Dylan Cease", "Yoshinobu Yamamoto",
    "Tarik Skubal", "Zack Wheeler", "Gerrit Cole", "Logan Gilbert",
    "Hunter Greene", "Garrett Crochet", "Jacob deGrom",
}


def parse_game(game_info: str):
    """Return away, home, venue_team(=home)."""
    m = re.match(r"([A-Z]+)@([A-Z]+)", game_info)
    if not m:
        return None, None, None
    away, home = m.group(1), m.group(2)
    return away, home, home


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def primary_pos(position: str) -> str:
    # Use first listed for multi-pos
    return position.split("/")[0]


def hitter_baseline(salary: int, pos: str) -> float:
    """Salary-based DK FP baseline for likely starters; position tweaks."""
    # Rough curve: min-salary ~2.5, mid 4k ~7, star 6k ~11-12
    s = salary
    if s <= 2500:
        base = 2.2 + (s - 2000) / 500 * 0.8
    elif s <= 3500:
        base = 3.0 + (s - 2500) / 1000 * 2.5
    elif s <= 4500:
        base = 5.5 + (s - 3500) / 1000 * 2.8
    elif s <= 5500:
        base = 8.3 + (s - 4500) / 1000 * 2.2
    else:
        base = 10.5 + (s - 5500) / 1000 * 1.8

    p = primary_pos(pos)
    if p == "C":
        base *= 0.92  # catcher playing-time / production haircut
    elif p == "OF":
        base *= 1.02
    elif p in ("SS", "2B"):
        base *= 1.01
    return base


def project_hitter(row, opp_sp_sal, opp_sp_name, park_run, team_off, salary_rank, n_hitters_team):
    sal = int(row["Salary"])
    pos = row["Position"]
    base = hitter_baseline(sal, pos)

    # Batting-order / PT proxy: higher salary rank within team → better slot
    # rank 1 = best; scale 1.12 .. 0.55
    if n_hitters_team <= 1:
        order_mult = 1.0
    else:
        # salary_rank 0-based among hitters on team (0 = highest salary)
        pct = salary_rank / max(n_hitters_team - 1, 1)
        order_mult = 1.14 - 0.60 * pct  # top ~1.14, bottom ~0.54
        # Deep bench / barely rostered
        if sal <= 2200 and salary_rank >= 10:
            order_mult *= 0.55
        elif sal <= 2500 and salary_rank >= 8:
            order_mult *= 0.70

    # Park
    park_mult = park_run / 100.0
    # Soften extreme parks
    park_mult = 1.0 + (park_mult - 1.0) * 0.85

    # Offense environment
    off_mult = 0.92 + 0.08 * team_off  # mild

    # Opposing SP quality (higher salary / ace → suppress bats)
    if opp_sp_sal is None:
        sp_mult = 1.0
    else:
        # 5k SP ~1.05 (weak), 11k ~0.88 (elite)
        sp_mult = 1.08 - (opp_sp_sal - 5000) / 1000 * 0.035
        sp_mult = clamp(sp_mult, 0.86, 1.10)
        if opp_sp_name in KNOWN_ACES:
            sp_mult *= 0.97

    proj = base * order_mult * park_mult * off_mult * sp_mult

    # Cap nonsense
    if sal >= 5800:
        proj = clamp(proj, 0.5, 16.5)
    elif sal >= 4800:
        proj = clamp(proj, 0.5, 14.5)
    else:
        proj = clamp(proj, 0.3, 12.5)

    # Volatility
    if sal <= 3200 and order_mult > 0.85:
        vol = "High"  # cheap likely starter boom/bust
    elif sal >= 5500:
        vol = "Medium"
    elif sal <= 2500:
        vol = "High"
    else:
        vol = "Medium"
    if primary_pos(pos) == "C" and sal < 4000:
        vol = "High"

    notes = []
    if park_run >= 103:
        notes.append("hitter park")
    elif park_run <= 96:
        notes.append("pitcher park")
    if opp_sp_sal and opp_sp_sal >= 9500:
        notes.append(f"vs elite SP ({opp_sp_name})")
    elif opp_sp_sal and opp_sp_sal <= 6000:
        notes.append(f"vs soft SP ({opp_sp_name})")
    if salary_rank <= 2:
        notes.append("top-order proxy")
    elif salary_rank >= 12:
        notes.append("bench PT risk")

    return round(proj, 1), vol, "; ".join(notes)


def project_sp_starter(row, park_run, opp_offense, is_home):
    sal = int(row["Salary"])
    name = row["Name"]

    # Expected IP by salary tier
    if sal >= 10500:
        ip = 6.4
    elif sal >= 9500:
        ip = 6.1
    elif sal >= 8500:
        ip = 5.9
    elif sal >= 7500:
        ip = 5.7
    elif sal >= 6500:
        ip = 5.5
    elif sal >= 5500:
        ip = 5.3
    else:
        ip = 5.0

    # K/IP proxy
    if sal >= 10000 or name in KNOWN_ACES:
        k_per_ip = 1.15
    elif sal >= 8500:
        k_per_ip = 1.00
    elif sal >= 7000:
        k_per_ip = 0.90
    else:
        k_per_ip = 0.80
    if name in ("Chris Sale", "Blake Snell", "Drew Rasmussen", "George Kirby", "Parker Messick"):
        k_per_ip += 0.08

    ks = ip * k_per_ip

    # WHIP / ER proxies
    if sal >= 10000:
        whip_h, whip_bb, er_per_ip = 0.85, 0.28, 0.45
    elif sal >= 8500:
        whip_h, whip_bb, er_per_ip = 0.95, 0.32, 0.55
    elif sal >= 7000:
        whip_h, whip_bb, er_per_ip = 1.05, 0.35, 0.65
    else:
        whip_h, whip_bb, er_per_ip = 1.15, 0.40, 0.75

    # Park: high run park hurts pitchers
    park_adj = park_run / 100.0
    er_per_ip *= (0.55 + 0.45 * park_adj)
    whip_h *= (0.70 + 0.30 * park_adj)

    # Opponent offense
    er_per_ip *= (0.85 + 0.15 * opp_offense)
    whip_h *= (0.88 + 0.12 * opp_offense)
    # Mild K suppress vs good offenses
    ks *= (1.06 - 0.06 * opp_offense)

    # Win chance
    team = row["TeamAbbrev"]
    team_str = TEAM_OFFENSE.get(team, 1.0)
    # Pitcher quality + team + home
    w_base = 0.22 + (sal - 5000) / 1000 * 0.04
    w_base += (team_str - 1.0) * 0.25
    if is_home:
        w_base += 0.04
    w_base -= (opp_offense - 1.0) * 0.20
    w_chance = clamp(w_base, 0.12, 0.58)

    # DK scoring
    fp = (
        ip * 2.25
        + ks * 2.0
        + w_chance * 4.0
        - er_per_ip * ip * 2.0
        - whip_h * ip * 0.6
        - whip_bb * ip * 0.6
    )
    # Tiny CG/SHO expectancy for aces
    if sal >= 10000:
        fp += 0.15

    if sal >= 10000:
        fp = clamp(fp, 12.0, 27.0)
    elif sal >= 8000:
        fp = clamp(fp, 10.0, 22.0)
    else:
        fp = clamp(fp, 7.0, 18.0)

    vol = "Low" if sal >= 9000 and name in KNOWN_ACES else ("Medium" if sal >= 7000 else "High")
    notes = [f"probable SP (FantasyPros); IP~{ip:.1f}"]
    if park_run <= 96:
        notes.append("pitcher park boost")
    elif park_run >= 103:
        notes.append("hitter park risk")
    if opp_offense >= 1.06:
        notes.append("tough offense")
    elif opp_offense <= 0.94:
        notes.append("soft offense")
    return round(fp, 1), vol, "; ".join(notes)


def project_sp_nonstarter(row):
    sal = int(row["Salary"])
    # Not expected to pitch tonight
    proj = 0.5 if sal < 8000 else 0.8
    return proj, "High", "not probable starter tonight"


def project_rp(row, is_probable_starter=False, park_run=100, opp_offense=1.0, is_home=True):
    if is_probable_starter:
        # Misclassified as RP but starting (e.g. Anthony Kay)
        return project_sp_starter(row, park_run, opp_offense, is_home)

    sal = int(row["Salary"])
    name = row["Name"]

    # High-salary RPs may be bulk/opener/closer
    if sal >= 8000:
        ip = 1.0
        ks = 1.3
        er = 0.45
        h, bb = 0.8, 0.35
        w = 0.08
        vol = "High"
        notes = "high-sal RP / bulk-or-closer usage"
    elif sal >= 6500:
        ip = 0.8
        ks = 1.0
        er = 0.40
        h, bb = 0.7, 0.30
        w = 0.05
        vol = "High"
        notes = "elevated RP leverage"
    elif sal >= 5500:
        ip = 0.6
        ks = 0.75
        er = 0.35
        h, bb = 0.55, 0.25
        w = 0.03
        vol = "Medium"
        notes = "mid RP"
    elif sal >= 4500:
        ip = 0.45
        ks = 0.55
        er = 0.28
        h, bb = 0.45, 0.22
        w = 0.02
        vol = "Medium"
        notes = "low-mid RP"
    else:
        ip = 0.30
        ks = 0.35
        er = 0.22
        h, bb = 0.35, 0.18
        w = 0.01
        vol = "Low"
        notes = "deep bullpen floor"

    fp = ip * 2.25 + ks * 2.0 + w * 4.0 - er * 2.0 - h * 0.6 - bb * 0.6
    fp = clamp(fp, 0.2, 8.5)
    return round(fp, 1), vol, notes


def main():
    rows = list(csv.DictReader(POOL.open()))
    assert len(rows) == 1115, len(rows)

    # Index game home parks and opponents
    # For each team, find opposing probable SP salary/name
    name_to_row = {r["Name"]: r for r in rows}
    team_prob_sp = {}
    for team, pname in PROBABLES.items():
        r = name_to_row.get(pname)
        if r:
            team_prob_sp[team] = (pname, int(r["Salary"]))
        else:
            team_prob_sp[team] = (pname, 7000)

    # Hitters by team sorted by salary desc for rank
    hitters_by_team = defaultdict(list)
    for r in rows:
        if r["Position"] not in ("SP", "RP"):
            hitters_by_team[r["TeamAbbrev"]].append(r)
    for t in hitters_by_team:
        hitters_by_team[t].sort(key=lambda x: -int(x["Salary"]))
    hitter_rank = {}
    for t, lst in hitters_by_team.items():
        for i, r in enumerate(lst):
            hitter_rank[r["ID"]] = (i, len(lst))

    out_rows = []
    for r in rows:
        away, home, venue = parse_game(r["Game Info"])
        team = r["TeamAbbrev"]
        opp = home if team == away else away
        park_run = PARK_RUN.get(venue, 100)
        is_home = team == home
        sal = int(r["Salary"])
        pos = r["Position"]
        name = r["Name"]
        is_prob = PROBABLES.get(team) == name

        opp_sp_name, opp_sp_sal = team_prob_sp.get(opp, (None, None))
        opp_off = TEAM_OFFENSE.get(opp, 1.0)
        team_off = TEAM_OFFENSE.get(team, 1.0)

        sources = "own-model"
        if is_prob:
            sources = "own-model+fantasypros-probables"

        if pos == "SP":
            if is_prob:
                proj, vol, notes = project_sp_starter(r, park_run, opp_off, is_home)
            else:
                proj, vol, notes = project_sp_nonstarter(r)
                # If somehow high-sal and only SP on team tonight ambiguity — already handled via PROBABLES
        elif pos == "RP":
            if is_prob:
                sources = "own-model+fantasypros-probables"
                proj, vol, notes = project_rp(
                    r, is_probable_starter=True, park_run=park_run,
                    opp_offense=opp_off, is_home=is_home
                )
            else:
                proj, vol, notes = project_rp(r)
        else:
            rank, n = hitter_rank[r["ID"]]
            proj, vol, notes = project_hitter(
                r, opp_sp_sal, opp_sp_name, park_run, team_off, rank, n
            )

        out_rows.append({
            "dk_id": r["ID"],
            "name": name,
            "position": pos,
            "team": team,
            "salary": sal,
            "game_info": r["Game Info"],
            "proj_fp": proj,
            "volatility": vol,
            "sources": sources,
            "notes": notes,
        })

    out_rows.sort(key=lambda x: (-x["proj_fp"], x["name"]))

    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "dk_id", "name", "position", "team", "salary", "game_info",
                "proj_fp", "volatility", "sources", "notes",
            ],
        )
        w.writeheader()
        w.writerows(out_rows)

    # Summary
    sps = [x for x in out_rows if x["position"] == "SP" or (
        x["position"] == "RP" and x["name"] in PROBABLES.values()
    )]
    # True starters only for top SP list
    starters = [x for x in out_rows if x["name"] in PROBABLES.values()]
    starters_sorted = sorted(starters, key=lambda x: -x["proj_fp"])
    hitters = [x for x in out_rows if x["position"] not in ("SP", "RP")]
    # exclude Anthony Kay from hitters already

    top10 = out_rows[:10]
    top5_sp = starters_sorted[:5]
    top5_hit = hitters[:5]

    lines = []
    lines.append("DK MLB Classic Projections — 2026-09-11")
    lines.append("=" * 50)
    lines.append(f"Slate date: 2026-09-11")
    lines.append(f"Games: 12 (BAL@TOR, CIN@MIL, CLE@MIN, CWS@STL, HOU@TB, KC@BOS,")
    lines.append(f"        LAD@MIA, NYM@NYY, PHI@ATL, SD@SF, SEA@ATH, TEX@ARI)")
    lines.append(f"Player count: {len(out_rows)}")
    lines.append("")
    lines.append("Method: OWN MODEL (public full-slate DK FP feeds unavailable/thin).")
    lines.append("  - Probable starters tagged from FantasyPros (2026-09-11 grid).")
    lines.append("  - Hitters: salary→FP curve × order proxy × park × opp SP × team offense.")
    lines.append("  - SP starters: IP/K/WHIP/W from salary tier + park + opp offense.")
    lines.append("  - Non-starting SPs: near-zero (not pitching tonight).")
    lines.append("  - RP: IP/K floor by salary tier; Anthony Kay treated as SP (probable).")
    lines.append("  - Sources tags: own-model or own-model+fantasypros-probables")
    lines.append("  - Park factors: documented simple table (Rogers 102, Fenway 103,")
    lines.append("    Oracle 94, Busch 96, Yankee 101, loanDepot 97, etc.).")
    lines.append("")
    lines.append("Top 10 overall by proj_fp:")
    for i, p in enumerate(top10, 1):
        lines.append(
            f"  {i:2}. {p['name']:22} {p['position']:6} {p['team']:3} "
            f"${p['salary']:<5} {p['proj_fp']:5.1f}  [{p['sources']}]"
        )
    lines.append("")
    lines.append("Top 5 SP (probable starters):")
    for i, p in enumerate(top5_sp, 1):
        lines.append(
            f"  {i}. {p['name']:22} {p['team']:3} ${p['salary']:<5} {p['proj_fp']:5.1f}  {p['notes'][:60]}"
        )
    lines.append("")
    lines.append("Top 5 hitters:")
    for i, p in enumerate(top5_hit, 1):
        lines.append(
            f"  {i}. {p['name']:22} {p['position']:6} {p['team']:3} "
            f"${p['salary']:<5} {p['proj_fp']:5.1f}"
        )
    lines.append("")
    lines.append("Caveats:")
    lines.append("  - No paid/optimizer projection blend; public scrapes were incomplete for this slate.")
    lines.append("  - Probables can change; refresh if FantasyPros/team announce scratches.")
    lines.append("  - Hitter PT/order inferred from salary rank within team (no confirmed lineups).")
    lines.append("  - Non-starting SPs intentionally ~0.5–0.8 FP.")
    lines.append("  - Caps applied to avoid unrealistic ceilings without component stats.")
    lines.append("")
    lines.append(f"Output: {OUT}")

    SUMMARY.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {len(out_rows)} rows -> {OUT}")


if __name__ == "__main__":
    main()
