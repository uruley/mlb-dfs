#!/usr/bin/env python3
"""
Rebuild MEAN DK MLB Classic projections for 2026-09-19 main slate.
Free data only: MLB StatsAPI probablePitcher + lineups hydrate,
salary/park/matchup proxies (desk own-model). No Savant uplift.

Cash SP v1.1 / MLB Manager + Mad Scientist (2026-09-20):
  DK-RP + MLB probable + salary >= $6000 = bulk candidate — use ~4.5–5.5 IP
  starter/bulk means (Alvarez/Holmes 09/19). Tag source probable_bulk.
  DK-RP under $6000 (Mayza-class cheap openers) stay IP-capped (~1.0–1.5).
  Elite SP tags remain DK Position=SP only (gates own that; means just project).
"""
from __future__ import annotations

import csv
import json
import math
import re
import unicodedata
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

ROOT = Path("/home/box/mlb-dfs")
POOL = ROOT / "dk-classic-player-pool.csv"
OUT = ROOT / "projections-tonight.csv"
SUMMARY = ROOT / "projections-tonight-summary.txt"
SCHED_JSON = ROOT / "sources/mlb-statsapi-schedule-lineups-2026-09-19.json"
LINEUPS_CSV = ROOT / "sources/mlb-statsapi-lineups-2026-09-19.csv"
SCHED_CSV = ROOT / "sources/mlb-statsapi-schedule-2026-09-19.csv"
SLATE_DATE = "2026-09-19"
CASH_RP_BULK_MIN_SALARY = 6000  # Cash SP v1.1: DK-RP MLB-probable bulk floor

NAME_TO_ABBR = {
    "Arizona Diamondbacks": "ARI", "Athletics": "ATH", "Atlanta Braves": "ATL",
    "Baltimore Orioles": "BAL", "Boston Red Sox": "BOS", "Chicago Cubs": "CHC",
    "Chicago White Sox": "CWS", "Cincinnati Reds": "CIN", "Cleveland Guardians": "CLE",
    "Colorado Rockies": "COL", "Detroit Tigers": "DET", "Houston Astros": "HOU",
    "Kansas City Royals": "KC", "Los Angeles Angels": "LAA", "Los Angeles Dodgers": "LAD",
    "Miami Marlins": "MIA", "Milwaukee Brewers": "MIL", "Minnesota Twins": "MIN",
    "New York Mets": "NYM", "New York Yankees": "NYY", "Philadelphia Phillies": "PHI",
    "Pittsburgh Pirates": "PIT", "San Diego Padres": "SD", "San Francisco Giants": "SF",
    "Seattle Mariners": "SEA", "St. Louis Cardinals": "STL", "Tampa Bay Rays": "TB",
    "Texas Rangers": "TEX", "Toronto Blue Jays": "TOR", "Washington Nationals": "WSH",
}

# Home venue run park factors (100=avg) for tonight's slate homes
PARK_RUN = {
    "HOU": 100,  # Daikin (roof)
    "SD": 94,    # Petco (pitcher)
    "LAA": 99,   # Angel Stadium
    "ARI": 101,  # Chase (roof)
    "COL": 118,  # Coors
    "LAD": 98,   # Dodger Stadium
    "TEX": 100,  # Globe Life (roof)
    "STL": 96,   # Busch
}

TEAM_OFFENSE = {
    "LAD": 1.12, "NYY": 1.10, "PHI": 1.07, "ATL": 1.05, "HOU": 1.05,
    "NYM": 1.04, "SEA": 1.04, "SD": 1.04, "MIL": 1.03, "BOS": 1.03,
    "TOR": 1.02, "DET": 1.02, "TB": 1.01, "CLE": 1.01, "BAL": 1.00,
    "ARI": 0.99, "MIN": 0.98, "STL": 0.98, "TEX": 0.97, "LAA": 0.97,
    "SF": 0.96, "ATH": 0.95, "WSH": 0.94, "MIA": 0.93, "CWS": 0.92,
    "COL": 0.91,
}

KNOWN_ACES = {
    "Dylan Cease", "Tyler Glasnow", "Gerrit Cole", "Paul Skenes", "Bryan Woo",
    "Nick Pivetta", "Tarik Skubal", "Yoshinobu Yamamoto", "Blake Snell",
    "Jacob Misiorowski", "Ranger Suarez", "Cade Cavalli", "Joe Ryan",
    "Cam Schlittler", "Eury Perez", "Reid Detmers",
}

# MLB fullName -> DK pool Name aliases
NAME_ALIASES = {
    "enrique hernandez": "kike hernandez",
    "enrique hernández": "kike hernandez",
    "kiké hernandez": "kike hernandez",
    "kike hernández": "kike hernandez",
    "luis robert jr": "luis robert jr.",
    "luis robert jr.": "luis robert jr.",
    "jazz chisholm jr": "jazz chisholm jr.",
    "ronald acuna jr": "ronald acuna jr.",
    "vladimir guerrero jr": "vladimir guerrero jr.",
    "bobby witt jr": "bobby witt jr.",
    "fernando tatis jr": "fernando tatis jr.",
    "ceddanne rajaee": "ceddanne rajaee",
    "eury perez": "eury perez",
    "jose soriano": "jose soriano",
}


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKD", str(s))
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    s = re.sub(r"\s+(jr|sr|ii|iii|iv)$", lambda m: " " + m.group(1), s)
    return s


def clamp(x, lo, hi):
    return max(lo, min(hi, x))


def primary_pos(position: str) -> str:
    return position.split("/")[0]


def is_dk_rp(position: str) -> bool:
    """True if DK Position is RP or starts with RP (Mayza rule)."""
    p = (position or "").strip().upper()
    return p == "RP" or p.startswith("RP")


def is_dk_sp(position: str) -> bool:
    """True SP-eligible for full starter IP (primary SP, not RP*)."""
    p = (position or "").strip().upper()
    if is_dk_rp(p):
        return False
    return p == "SP" or p.startswith("SP/")


def is_pitcher(position: str) -> bool:
    p = primary_pos(position).upper()
    return p in ("SP", "RP") or is_dk_rp(position) or is_dk_sp(position)


def parse_game(game_info: str):
    m = re.match(r"([A-Z]+)@([A-Z]+)", game_info)
    if not m:
        return None, None, None
    away, home = m.group(1), m.group(2)
    return away, home, home


def hitter_baseline(salary: int, pos: str) -> float:
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
        base *= 0.92
    elif p == "OF":
        base *= 1.02
    elif p in ("SS", "2B"):
        base *= 1.01
    return base


def project_hitter(row, opp_sp_sal, opp_sp_name, park_run, team_off, order_slot, in_order, salary_rank, n_hitters):
    sal = int(row["Salary"])
    pos = row["Position"]
    base = hitter_baseline(sal, pos)

    notes = []
    if in_order and order_slot is not None:
        slot_mult = {
            1: 1.14, 2: 1.12, 3: 1.16, 4: 1.14, 5: 1.08,
            6: 1.02, 7: 0.96, 8: 0.90, 9: 0.86,
        }.get(int(order_slot), 0.95)
        order_mult = slot_mult
        notes.append(f"posted lineup slot {order_slot}")
        source = "posted"
    else:
        if n_hitters <= 1:
            order_mult = 0.75
        else:
            pct = salary_rank / max(n_hitters - 1, 1)
            if salary_rank <= 8:
                order_mult = 1.10 - 0.28 * (salary_rank / 8.0)
                notes.append(f"salary-rank starter proxy #{salary_rank+1}")
                source = "salary_rank"
            else:
                order_mult = 0.55 - 0.25 * min((salary_rank - 9) / max(n_hitters - 10, 1), 1.0)
                order_mult = clamp(order_mult, 0.20, 0.55)
                notes.append("bench PT risk")
                source = "bench"
        if sal <= 2200 and salary_rank >= 10:
            order_mult *= 0.70

    park_mult = park_run / 100.0
    park_mult = 1.0 + (park_mult - 1.0) * 0.85
    off_mult = 0.92 + 0.08 * team_off

    if opp_sp_sal is None:
        sp_mult = 1.0
    else:
        sp_mult = 1.08 - (opp_sp_sal - 5000) / 1000 * 0.035
        sp_mult = clamp(sp_mult, 0.86, 1.10)
        if opp_sp_name in KNOWN_ACES:
            sp_mult *= 0.97

    if park_run >= 110:
        park_mult = 1.0 + (park_run / 100.0 - 1.0) * 0.95

    proj = base * order_mult * park_mult * off_mult * sp_mult

    if not in_order and source == "bench":
        proj = clamp(proj, 0.2, 4.5)
    elif sal >= 5800:
        proj = clamp(proj, 0.5, 16.5)
    elif sal >= 4800:
        proj = clamp(proj, 0.5, 14.5)
    else:
        proj = clamp(proj, 0.3, 12.5)

    if park_run >= 110:
        notes.append("Coors boost")
    elif park_run >= 103:
        notes.append("hitter park")
    elif park_run <= 96:
        notes.append("pitcher park")
    if opp_sp_sal and opp_sp_sal >= 9500:
        notes.append(f"vs elite SP ({opp_sp_name})")
    elif opp_sp_sal and opp_sp_sal <= 6000:
        notes.append(f"vs soft SP ({opp_sp_name})")

    vol = "Medium"
    if sal <= 3200 and order_mult > 0.85:
        vol = "High"
    elif sal <= 2500:
        vol = "High"
    elif sal >= 5500:
        vol = "Medium"
    if primary_pos(pos) == "C" and sal < 4000:
        vol = "High"
    if park_run >= 110:
        vol = "High"

    return round(proj, 2), vol, "; ".join(notes), source


def project_sp_starter(row, park_run, opp_offense, is_home):
    sal = int(row["Salary"])
    name = row["Name"]

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
    elif sal >= 4500:
        ip = 5.0
    else:
        ip = 4.7

    if sal >= 10000 or name in KNOWN_ACES:
        k_per_ip = 1.15
    elif sal >= 8500:
        k_per_ip = 1.00
    elif sal >= 7000:
        k_per_ip = 0.90
    else:
        k_per_ip = 0.80
    if name in ("Dylan Cease", "Tyler Glasnow", "Gerrit Cole", "Bryan Woo",
                "Tarik Skubal", "Joe Ryan", "Cam Schlittler"):
        k_per_ip += 0.08

    ks = ip * k_per_ip

    if sal >= 10000:
        whip_h, whip_bb, er_per_ip = 0.85, 0.28, 0.45
    elif sal >= 8500:
        whip_h, whip_bb, er_per_ip = 0.95, 0.32, 0.55
    elif sal >= 7000:
        whip_h, whip_bb, er_per_ip = 1.05, 0.35, 0.65
    else:
        whip_h, whip_bb, er_per_ip = 1.15, 0.40, 0.75

    park_adj = park_run / 100.0
    er_scale = 0.55 + 0.45 * park_adj
    if park_run >= 110:
        er_scale = 0.40 + 0.70 * park_adj
    er_per_ip *= er_scale
    whip_h *= (0.70 + 0.30 * park_adj)
    if park_run >= 110:
        whip_h *= 1.12

    er_per_ip *= (0.85 + 0.15 * opp_offense)
    whip_h *= (0.88 + 0.12 * opp_offense)
    ks *= (1.06 - 0.06 * opp_offense)

    team = row["TeamAbbrev"]
    team_str = TEAM_OFFENSE.get(team, 1.0)
    w_base = 0.22 + (sal - 5000) / 1000 * 0.04
    w_base += (team_str - 1.0) * 0.25
    if is_home:
        w_base += 0.04
    w_base -= (opp_offense - 1.0) * 0.20
    if park_run >= 110:
        w_base -= 0.06
    w_chance = clamp(w_base, 0.10, 0.58)

    fp = (
        ip * 2.25
        + ks * 2.0
        + w_chance * 4.0
        - er_per_ip * ip * 2.0
        - whip_h * ip * 0.6
        - whip_bb * ip * 0.6
    )
    if sal >= 10000:
        fp += 0.15

    if sal >= 10000:
        fp = clamp(fp, 12.0, 27.0)
    elif sal >= 8000:
        fp = clamp(fp, 10.0, 22.0)
    elif sal >= 5000:
        fp = clamp(fp, 7.0, 18.0)
    else:
        fp = clamp(fp, 5.5, 15.0)

    vol = "Low" if sal >= 9000 and name in KNOWN_ACES else ("Medium" if sal >= 7000 else "High")
    notes = [f"probable SP (MLB StatsAPI {SLATE_DATE}); IP~{ip:.1f}"]
    if park_run <= 96:
        notes.append("pitcher park boost")
    elif park_run >= 110:
        notes.append("Coors risk")
    elif park_run >= 103:
        notes.append("hitter park risk")
    if opp_offense >= 1.06:
        notes.append("tough offense")
    elif opp_offense <= 0.94:
        notes.append("soft offense")
    return round(fp, 2), vol, "; ".join(notes)


def project_sp_nonstarter(row):
    sal = int(row["Salary"])
    # Non-probable SPs ~0.5–0.8 per desk guidance
    if sal >= 9000:
        fp = 0.80
    elif sal >= 7000:
        fp = 0.70
    elif sal >= 5000:
        fp = 0.60
    else:
        fp = 0.50
    return round(fp, 2), "High", f"non-probable SP tonight (~{fp:.1f})"


def project_bulk_rp(row, park_run=100, opp_offense=1.0, is_home=False):
    """
    Cash SP v1.1: MLB-probable DK-RP with salary >= CASH_RP_BULK_MIN_SALARY.
    Restore ~4.5–5.5 IP starter/bulk means (Alvarez/Holmes threw bulk 09/19).
    """
    sal = int(row["Salary"])
    if sal >= 8500:
        ip = 5.5
    elif sal >= 7500:
        ip = 5.3
    elif sal >= 6500:
        ip = 5.0
    else:
        ip = 4.7  # $6000–$6499 bulk floor

    if sal >= 8500:
        k_per_ip, whip_h, whip_bb, er_per_ip, w = 0.95, 1.00, 0.34, 0.60, 0.32
    elif sal >= 7000:
        k_per_ip, whip_h, whip_bb, er_per_ip, w = 0.88, 1.08, 0.36, 0.68, 0.28
    else:
        k_per_ip, whip_h, whip_bb, er_per_ip, w = 0.82, 1.12, 0.38, 0.72, 0.24

    park_adj = park_run / 100.0
    er_scale = 0.85 + 0.15 * park_adj
    if park_run >= 110:
        er_scale *= 1.12
        whip_h *= 1.10
    er_per_ip *= er_scale
    er_per_ip *= (0.85 + 0.15 * opp_offense)
    whip_h *= (0.88 + 0.12 * opp_offense)
    if not is_home:
        w *= 0.92

    ks = ip * k_per_ip
    fp = (
        ip * 2.25
        + ks * 2.0
        + w * 4.0
        - er_per_ip * ip * 2.0
        - whip_h * ip * 0.6
        - whip_bb * ip * 0.6
    )
    fp = clamp(fp, 6.0, 22.0)
    notes = (
        f"probable bulk/RP (MLB StatsAPI {SLATE_DATE}) DK=RP salary>=${CASH_RP_BULK_MIN_SALARY} — "
        f"Cash SP v1.1 bulk means IP~{ip:.1f} (not Mayza opener cap)"
    )
    if park_run >= 110:
        notes += "; Coors risk"
    return round(fp, 2), "Medium", notes


def project_opener_rp(row, park_run=100, opp_offense=1.0):
    """
    Mayza-class: MLB-probable DK-RP with salary < CASH_RP_BULK_MIN_SALARY.
    Cap roughly ≤1.0–1.5 IP equivalent FP (cheap opener risk).
    """
    sal = int(row["Salary"])
    # Opener: ~1.0–1.5 IP max, elevated K rate for short stint
    if sal >= 5500:
        ip, ks, er, h, bb, w = 1.1, 1.15, 0.48, 0.85, 0.32, 0.04
    elif sal >= 4500:
        ip, ks, er, h, bb, w = 1.05, 1.05, 0.46, 0.82, 0.31, 0.035
    else:
        ip, ks, er, h, bb, w = 1.0, 1.00, 0.45, 0.80, 0.30, 0.03

    # Mild park/offense adjustment (short outing)
    park_adj = park_run / 100.0
    er *= (0.70 + 0.30 * park_adj)
    if park_run >= 110:
        er *= 1.15
        h *= 1.10
    er *= (0.90 + 0.10 * opp_offense)

    fp = ip * 2.25 + ks * 2.0 + w * 4.0 - er * 2.0 - h * 0.6 - bb * 0.6
    # Hard cap: opener/relief ceiling (~1.0–1.5 IP equiv)
    fp = clamp(fp, 0.8, 6.5)

    notes = (
        f"probable opener/RP (MLB StatsAPI {SLATE_DATE}) but DK=RP salary<${CASH_RP_BULK_MIN_SALARY} — "
        f"Mayza-class capped opener IP~{ip:.1f}"
    )
    if park_run >= 110:
        notes += "; Coors risk"
    return round(fp, 2), "High", notes


def project_rp(row, park_run=100):
    """Ordinary non-probable RP bullpen floor."""
    sal = int(row["Salary"])
    if sal >= 8000:
        ip, ks, er, h, bb, w = 1.0, 1.3, 0.45, 0.8, 0.35, 0.08
        notes = "high-sal RP / bulk-or-closer usage"
        vol = "High"
    elif sal >= 6500:
        ip, ks, er, h, bb, w = 0.8, 1.0, 0.40, 0.7, 0.30, 0.05
        notes = "elevated RP leverage"
        vol = "High"
    elif sal >= 5500:
        ip, ks, er, h, bb, w = 0.6, 0.75, 0.35, 0.55, 0.25, 0.03
        notes = "mid RP"
        vol = "Medium"
    elif sal >= 4500:
        ip, ks, er, h, bb, w = 0.45, 0.55, 0.28, 0.45, 0.22, 0.02
        notes = "low-mid RP"
        vol = "Medium"
    else:
        ip, ks, er, h, bb, w = 0.30, 0.35, 0.22, 0.35, 0.18, 0.01
        notes = "deep bullpen floor"
        vol = "Low"
    fp = ip * 2.25 + ks * 2.0 + w * 4.0 - er * 2.0 - h * 0.6 - bb * 0.6
    fp = clamp(fp, 0.2, 8.5)
    return round(fp, 2), vol, notes


def build_name_index(pool_rows):
    idx = {}
    for r in pool_rows:
        n = norm(r["Name"])
        idx[n] = r
        n2 = re.sub(r"\s+jr$", " jr", n)
        idx[n2] = r
    return idx


def resolve_pool_row(full_name: str, team: str, name_index, by_team_name):
    n = norm(full_name)
    alias = NAME_ALIASES.get(n) or NAME_ALIASES.get(n.replace(" jr", " jr."))
    if alias:
        n = norm(alias)
    r = name_index.get(n)
    if r and r["TeamAbbrev"] == team:
        return r
    parts = n.split()
    if len(parts) >= 2:
        last = parts[-1]
        first = parts[0]
        cands = by_team_name.get(team, [])
        hits = [x for x in cands if norm(x["Name"]).endswith(last) and norm(x["Name"]).startswith(first[:1])]
        if len(hits) == 1:
            return hits[0]
        hits2 = [x for x in cands if last in norm(x["Name"]) and first[:3] in norm(x["Name"])]
        if len(hits2) == 1:
            return hits2[0]
    if r and r["TeamAbbrev"] == team:
        return r
    for key in (n, n + " jr", n.replace(" jr", "")):
        rr = name_index.get(key)
        if rr and rr["TeamAbbrev"] == team:
            return rr
    return None


def load_probables_and_lineups(slate_teams):
    data = json.loads(SCHED_JSON.read_text())
    probables = {}  # team -> fullName
    lineups = defaultdict(dict)  # team -> {norm_name: slot}
    lineup_raw = defaultdict(list)

    for date in data["dates"]:
        for g in date["games"]:
            away_name = g["teams"]["away"]["team"]["name"]
            home_name = g["teams"]["home"]["team"]["name"]
            away = NAME_TO_ABBR[away_name]
            home = NAME_TO_ABBR[home_name]
            asp = g["teams"]["away"].get("probablePitcher") or {}
            hsp = g["teams"]["home"].get("probablePitcher") or {}
            if away in slate_teams and asp.get("fullName"):
                probables[away] = asp["fullName"]
            if home in slate_teams and hsp.get("fullName"):
                probables[home] = hsp["fullName"]
            lu = g.get("lineups") or {}
            for side, team in (("awayPlayers", away), ("homePlayers", home)):
                if team not in slate_teams:
                    continue
                for i, p in enumerate(lu.get(side) or [], 1):
                    fn = p.get("fullName") or ""
                    lineups[team][norm(fn)] = i
                    lineup_raw[team].append((i, fn))

    return probables, lineups, lineup_raw


def main():
    rows = list(csv.DictReader(POOL.open()))
    n_pool = len(rows)
    slate_teams = {r["TeamAbbrev"] for r in rows}
    games = sorted({r["Game Info"] for r in rows})

    name_index = build_name_index(rows)
    by_team_name = defaultdict(list)
    for r in rows:
        by_team_name[r["TeamAbbrev"]].append(r)

    probables, lineups, lineup_raw = load_probables_and_lineups(slate_teams)

    # Map probable fullName -> pool row / dk name
    team_prob_sp = {}  # team -> (dk_name, salary, pool_row or None, dk_pos)
    probable_dk_ids = set()
    unmatched_sp = []
    for team, pname in sorted(probables.items()):
        prow = resolve_pool_row(pname, team, name_index, by_team_name)
        if prow:
            team_prob_sp[team] = (prow["Name"], int(prow["Salary"]), prow, prow["Position"])
            probable_dk_ids.add(prow["ID"])
        else:
            unmatched_sp.append((team, pname))
            team_prob_sp[team] = (pname, 7000, None, "SP")

    # Posted lineup: map dk_id -> slot via name match
    posted_slot = {}  # dk_id -> slot
    posted_miss = []
    for team, slots in lineup_raw.items():
        for slot, fn in slots:
            prow = resolve_pool_row(fn, team, name_index, by_team_name)
            if prow and not is_pitcher(prow["Position"]):
                posted_slot[prow["ID"]] = slot
            elif prow is None:
                posted_miss.append((team, slot, fn))

    # Hitter salary ranks
    hitters_by_team = defaultdict(list)
    for r in rows:
        if not is_pitcher(r["Position"]):
            hitters_by_team[r["TeamAbbrev"]].append(r)
    for t in hitters_by_team:
        hitters_by_team[t].sort(key=lambda x: -int(x["Salary"]))
    hitter_rank = {}
    for t, lst in hitters_by_team.items():
        for i, r in enumerate(lst):
            hitter_rank[r["ID"]] = (i, len(lst))

    out_rows = []
    dk_rp_probables = []  # for summary
    true_sp_probables = []

    for r in rows:
        away, home, venue = parse_game(r["Game Info"])
        team = r["TeamAbbrev"]
        opp = home if team == away else away
        park_run = PARK_RUN.get(venue, 100)
        is_home = team == home
        sal = int(r["Salary"])
        pos = r["Position"]
        name = r["Name"]

        is_prob = r["ID"] in probable_dk_ids and team_prob_sp.get(team, (None,))[0] == name
        if team in team_prob_sp and team_prob_sp[team][0] == name:
            is_prob = True

        opp_sp_name, opp_sp_sal = None, None
        if opp in team_prob_sp:
            opp_sp_name, opp_sp_sal = team_prob_sp[opp][0], team_prob_sp[opp][1]
            # Hitter matchup: cheap DK-RP openers are soft; bulk RPs (>=$6k) stay full salary
            if (team_prob_sp[opp][2] is not None and is_dk_rp(team_prob_sp[opp][3])
                    and (opp_sp_sal or 0) < CASH_RP_BULK_MIN_SALARY):
                opp_sp_sal = min(opp_sp_sal, 5500)  # Mayza-class opener = softer matchup

        opp_off = TEAM_OFFENSE.get(opp, 1.0)
        team_off = TEAM_OFFENSE.get(team, 1.0)

        if is_dk_sp(pos):
            if is_prob:
                proj, vol, notes = project_sp_starter(r, park_run, opp_off, is_home)
                source = "probable_sp"
                sources = "own-model+mlb-statsapi-probables"
                true_sp_probables.append(name)
            else:
                proj, vol, notes = project_sp_nonstarter(r)
                source = "non_starter"
                sources = "own-model"
        elif is_dk_rp(pos):
            if is_prob:
                # Cash SP v1.1: >=$6k bulk means; <$6k Mayza opener cap
                if sal >= CASH_RP_BULK_MIN_SALARY:
                    proj, vol, notes = project_bulk_rp(
                        r, park_run=park_run, opp_offense=opp_off, is_home=is_home
                    )
                    source = "probable_bulk"
                    sources = "own-model+mlb-statsapi-probables+cash-sp-v1.1-bulk"
                else:
                    proj, vol, notes = project_opener_rp(
                        r, park_run=park_run, opp_offense=opp_off
                    )
                    source = "probable_opener"
                    sources = "own-model+mlb-statsapi-probables+mayza-rp-cap"
                dk_rp_probables.append({
                    "name": name, "team": team, "position": pos,
                    "salary": sal, "proj_fp": proj, "notes": notes,
                    "source": source,
                })
            else:
                proj, vol, notes = project_rp(r, park_run=park_run)
                source = "rp"
                sources = "own-model"
        else:
            rank, n = hitter_rank[r["ID"]]
            in_order = r["ID"] in posted_slot
            slot = posted_slot.get(r["ID"])
            proj, vol, notes, hsrc = project_hitter(
                r, opp_sp_sal, opp_sp_name, park_run, team_off, slot, in_order, rank, n
            )
            source = hsrc
            if in_order:
                sources = "own-model+mlb-statsapi-lineups"
            else:
                sources = "own-model+salary-rank"

        game_key = f"{away}@{home}" if away and home else ""
        out_rows.append({
            "dk_id": r["ID"],
            "name": name,
            "position": pos,
            "team": team,
            "salary": sal,
            "game_info": r["Game Info"],
            "proj_fp": proj,
            "adjusted_proj": proj,
            "source": source,
            "sources": sources,
            "game": game_key,
            "volatility": vol,
            "notes": notes,
            "probable": 1 if is_prob else 0,
        })

    # Coverage checks
    pool_ids = {r["ID"] for r in rows}
    out_ids = {r["dk_id"] for r in out_rows}
    missing = pool_ids - out_ids
    extra = out_ids - pool_ids
    # uniqueness
    if len(out_ids) != len(out_rows):
        raise SystemExit("DUPLICATE dk_id in output")
    if missing or extra or len(out_rows) != n_pool:
        raise SystemExit(
            f"COVERAGE FAIL missing={len(missing)} extra={len(extra)} "
            f"out={len(out_rows)} pool={n_pool}"
        )

    out_rows.sort(key=lambda x: (-x["proj_fp"], x["name"]))

    fieldnames = [
        "dk_id", "name", "position", "team", "salary", "game_info",
        "proj_fp", "adjusted_proj", "source", "sources", "game",
        "volatility", "notes", "probable",
    ]
    with OUT.open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    true_sps = [x for x in out_rows if x["source"] == "probable_sp"]
    openers = [x for x in out_rows if x["source"] == "probable_opener"]
    bulks = [x for x in out_rows if x["source"] == "probable_bulk"]
    starters_sorted = sorted(true_sps, key=lambda x: -x["proj_fp"])
    openers_sorted = sorted(openers, key=lambda x: -x["proj_fp"])
    bulks_sorted = sorted(bulks, key=lambda x: -x["proj_fp"])
    all_mlb_prob = sorted(true_sps + openers + bulks, key=lambda x: -x["proj_fp"])
    top5 = out_rows[:5]
    top10 = out_rows[:10]
    now = datetime.now(ZoneInfo("America/Chicago")).strftime("%Y-%m-%d %H:%M %Z")

    posted_teams = sorted(t for t in slate_teams if t in lineup_raw and lineup_raw[t])
    salary_proxy_teams = sorted(slate_teams - set(posted_teams))

    lines = []
    lines.append("DK MLB Classic Projections — MEAN rebuild (process audit)")
    lines.append("=" * 64)
    lines.append(f"Slate date: {SLATE_DATE}")
    lines.append(f"Updated: {now}")
    lines.append(f"Games ({len(games)}): " + "; ".join(g.split(" 09/")[0] for g in games))
    lines.append(f"Player count: {len(out_rows)} (100% dk_id overlap with pool; missing=0 extra=0)")
    lines.append("")
    lines.append("Method:")
    lines.append("  Own-model MEAN projections (free data only; no Savant uplift).")
    lines.append(f"  1. MLB StatsAPI schedule hydrate=probablePitcher,lineups for {SLATE_DATE}.")
    lines.append(f"  2. True DK-SP probables tagged probable_sp ({len(true_sps)}); "
                 f"DK-RP MLB-probables: probable_bulk ({len(bulks)}) salary>=${CASH_RP_BULK_MIN_SALARY}; probable_opener ({len(openers)}) Mayza-class <$6k — Cash SP v1.1.")
    lines.append("  3. Non-probable SPs ~0.5–0.8.")
    lines.append(f"  4. Posted batting orders used for {len(posted_teams)} teams "
                 f"({', '.join(posted_teams)}).")
    if salary_proxy_teams:
        lines.append(f"  5. Salary-rank / role proxies for teams without posted LU: "
                     f"{', '.join(salary_proxy_teams)}.")
    else:
        lines.append("  5. All slate teams had posted lineups.")
    lines.append("  6. Hitters: salary→FP × order/slot × park × opp SP × team offense.")
    lines.append("  7. DK-SP starters: IP/K/WHIP/W from salary tier + park + opp offense.")
    lines.append("  8. Cash SP v1.1: DK-RP MLB-probable salary>=$6000 → ~4.5–5.5 IP bulk; <$6000 opener-capped.")
    lines.append("  Sources: probable_sp | probable_bulk | probable_opener | posted | salary_rank | non_starter | rp")
    lines.append("")
    lines.append(f"MLB probable TRUE DK-SPs (StatsAPI, slate only) — {len(starters_sorted)}:")
    for p in starters_sorted:
        lines.append(
            f"  {p['team']:3} {p['name']:22} {p['position']:3} ${p['salary']:<5} "
            f"{p['proj_fp']:5.2f}  {p['notes'][:75]}"
        )
    lines.append("")
    lines.append(f"DK-RP MLB-probables BULK (Cash SP v1.1, salary>=${CASH_RP_BULK_MIN_SALARY}) — {len(bulks_sorted)}:")
    if bulks_sorted:
        for p in bulks_sorted:
            lines.append(
                f"  {p['team']:3} {p['name']:22} {p['position']:3} ${p['salary']:<5} "
                f"{p['proj_fp']:5.2f}  {p['notes'][:80]}"
            )
    else:
        lines.append("  (none)")
    lines.append(f"DK-RP MLB-probables CAPPED as openers (Mayza-class <$6k) — {len(openers_sorted)}:")
    if openers_sorted:
        for p in openers_sorted:
            lines.append(
                f"  {p['team']:3} {p['name']:22} {p['position']:3} ${p['salary']:<5} "
                f"{p['proj_fp']:5.2f}  {p['notes'][:80]}"
            )
    else:
        lines.append("  (none)")
    if unmatched_sp:
        lines.append(f"  UNMATCHED in pool: {unmatched_sp}")
    if posted_miss:
        lines.append(f"  Lineup name misses ({len(posted_miss)}): {posted_miss[:12]}...")
    lines.append("")
    lines.append("Top 5 overall by proj_fp:")
    for i, p in enumerate(top5, 1):
        lines.append(
            f"  {i:2}. {p['name']:22} {p['position']:6} {p['team']:3} "
            f"${p['salary']:<5} {p['proj_fp']:5.2f}  [{p['source']}]"
        )
    lines.append("")
    lines.append("Top 10 overall by proj_fp:")
    for i, p in enumerate(top10, 1):
        lines.append(
            f"  {i:2}. {p['name']:22} {p['position']:6} {p['team']:3} "
            f"${p['salary']:<5} {p['proj_fp']:5.2f}  [{p['source']}]"
        )
    lines.append("")
    lines.append(f"Output: {OUT}")
    lines.append("Backup: /home/box/mlb-dfs/projections-tonight-pre-0919.csv")
    lines.append("Note: Cash gates / Mad Scientist NOT applied in this MEAN pass.")

    SUMMARY.write_text("\n".join(lines) + "\n")
    print("\n".join(lines))
    print(f"\nWrote {len(out_rows)} rows -> {OUT}")
    print(f"True SP probables: {len(starters_sorted)}; DK-RP openers: {len(openers_sorted)}; "
          f"posted teams: {len(posted_teams)}; salary-proxy: {salary_proxy_teams}")


if __name__ == "__main__":
    main()
