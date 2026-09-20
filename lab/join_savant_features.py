#!/usr/bin/env python3
"""Join Baseball Savant expected stats onto tonight's DK Classic player pool."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
SOURCES = DESK / "sources"

DEFAULT_POOL = DESK / "dk-classic-player-pool.csv"
# Prefer enriched plural outputs from fetch_savant.py; fall back to singular.
BATTER_CANDIDATES = [
    SOURCES / "savant-expected-batters-2026.csv",
    SOURCES / "savant-expected-batter-2026.csv",
]
PITCHER_CANDIDATES = [
    SOURCES / "savant-expected-pitchers-2026.csv",
    SOURCES / "savant-expected-pitcher-2026.csv",
]
DEFAULT_OUT = LAB / "features-savant-tonight.csv"

TEAM_MAP = {
    "OAK": "ATH",
    "WSN": "WSH",
    "WAS": "WSH",
    "CHW": "CWS",
    "KCR": "KC",
    "SDP": "SD",
    "SFG": "SF",
    "TBR": "TB",
    "TBD": "TB",
    "ANA": "LAA",
    "ARI": "AZ",  # some sources use ARI; DK slate uses AZ sometimes — map both ways below
    "AZ": "AZ",
    "FLA": "MIA",
}

# Bidirectional team equivalence for matching
TEAM_EQ = {
    "ARI": "AZ",
    "AZ": "AZ",
    "OAK": "ATH",
    "ATH": "ATH",
}

FUZZY_THRESHOLD = 0.88
FUZZY_NAME_ONLY = 0.93


def norm_team(t: str) -> str:
    t = (t or "").strip().upper()
    t = TEAM_MAP.get(t, t)
    return TEAM_EQ.get(t, t)


def teams_match(a: str, b: str) -> bool:
    if not a or not b:
        return False
    return norm_team(a) == norm_team(b)


def strip_accents(s: str) -> str:
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))


def norm_name(s: str) -> str:
    s = strip_accents(s or "")
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    for suf in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return s


def savant_display_name(raw: str) -> str:
    """Convert 'Last, First' → 'First Last' (no-op if already First Last)."""
    raw = (raw or "").strip().strip('"')
    if "," in raw:
        last, first = raw.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return raw


def safe_float(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def resolve_path(cands: list[Path], explicit: Path | None) -> Path | None:
    if explicit is not None:
        return explicit if explicit.exists() else None
    for p in cands:
        if p.exists():
            return p
    return None


def name_key_from_row(row: dict) -> tuple[str, str]:
    """Return (display_name, norm_name) from enriched or raw Savant row."""
    if row.get("name") and "," not in row.get("name", ""):
        display = row["name"].strip()
    else:
        raw = (
            row.get("name_savant")
            or row.get("last_name, first_name")
            or row.get("name")
            or ""
        )
        if not raw:
            for k in row:
                if "last_name" in k and "first_name" in k:
                    raw = row[k]
                    break
        display = savant_display_name(raw)
    return display, norm_name(display)


def load_savant(path: Path, role_default: str) -> list[dict]:
    rows: list[dict] = []
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            display, nk = name_key_from_row(row)
            if not nk:
                continue
            role = (row.get("role") or role_default).strip().lower()
            team = norm_team(row.get("team", "") or "")
            # Enriched fetch already renamed est_* → x*; raw Savant uses est_*
            xba = safe_float(row.get("xba") if row.get("xba") not in (None, "") else row.get("est_ba"))
            xslg = safe_float(row.get("xslg") if row.get("xslg") not in (None, "") else row.get("est_slg"))
            xwoba = safe_float(row.get("xwoba") if row.get("xwoba") not in (None, "") else row.get("est_woba"))
            xera = safe_float(row.get("xera"))
            feat = {
                "savant_name": display,
                "savant_id": str(row.get("player_id", "")).strip(),
                "role": role if role in ("batter", "pitcher") else role_default,
                "norm": nk,
                "team": team,
                "xba": xba,
                "xslg": xslg,
                "xwoba": xwoba,
                "xera": xera,
                "pa": safe_float(row.get("pa")),
                "hard_hit_pct": safe_float(row.get("hard_hit_pct")),
                "barrel_pct": safe_float(row.get("barrel_pct")),
                "avg_hit_speed": safe_float(row.get("avg_hit_speed")),
            }
            rows.append(feat)
    return rows


def load_pool(path: Path) -> list[dict]:
    out: list[dict] = []
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = (row.get("Name") or "").strip()
            team = norm_team(row.get("TeamAbbrev") or "")
            dk_id = str(row.get("ID") or "").strip()
            if not dk_id or not name:
                continue
            pos = (row.get("Roster Position") or row.get("Position") or "").strip()
            position = (row.get("Position") or "").strip()
            is_pitcher = (
                pos == "P"
                or "P" in pos.split("/")
                or position in ("SP", "RP", "P")
            )
            salary = str(row.get("Salary") or "").strip()
            out.append(
                {
                    "dk_id": dk_id,
                    "name": name,
                    "team": team,
                    "salary": salary,
                    "norm": norm_name(name),
                    "pos": pos,
                    "is_pitcher": is_pitcher,
                }
            )
    return out


def match_one(
    pool_row: dict, savant_by_norm: dict[str, list[dict]], all_savant: list[dict]
) -> tuple[dict | None, str, float]:
    nk = pool_row["norm"]
    team = pool_row["team"]
    prefer_pitcher = pool_row["is_pitcher"]

    cands = savant_by_norm.get(nk, [])
    if cands:
        role_cands = [
            c for c in cands if (c["role"] == "pitcher") == prefer_pitcher
        ] or cands
        team_cands = [c for c in role_cands if teams_match(c["team"], team)]
        chosen = (team_cands or role_cands)[0]
        conf = 1.0
        kind = "exact"
        if team_cands:
            kind = "exact+team"
        elif len(cands) > 1:
            kind = "exact+role"
            conf = 0.95
        return chosen, kind, conf

    best = None
    best_sc = 0.0
    for s in all_savant:
        sc = SequenceMatcher(None, nk, s["norm"]).ratio()
        role_ok = (s["role"] == "pitcher") == prefer_pitcher
        if not role_ok:
            sc *= 0.98
        if teams_match(s["team"], team):
            sc = min(1.0, sc + 0.03)
        if sc > best_sc:
            best_sc = sc
            best = s

    thresh = (
        FUZZY_THRESHOLD
        if (best and teams_match(best.get("team", ""), team))
        else FUZZY_NAME_ONLY
    )
    if best is not None and best_sc >= thresh:
        return best, f"fuzzy:{best_sc:.2f}", round(best_sc, 4)
    return None, "unmatched", 0.0


def fmt(v, nd=3):
    if v is None:
        return ""
    if nd == 0:
        return int(v)
    return f"{v:.{nd}f}"


def main() -> int:
    ap = argparse.ArgumentParser(description="Join Savant x-stats onto DK pool")
    ap.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    ap.add_argument("--batter", type=Path, default=None)
    ap.add_argument("--pitcher", type=Path, default=None)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = ap.parse_args()

    if not args.pool.exists():
        print(f"ERROR: DK pool missing: {args.pool}", file=sys.stderr)
        return 1

    batter_path = resolve_path(BATTER_CANDIDATES, args.batter)
    pitcher_path = resolve_path(PITCHER_CANDIDATES, args.pitcher)
    if batter_path is None and pitcher_path is None:
        print("ERROR: no Savant CSVs found (batters/pitchers)", file=sys.stderr)
        return 1

    batters = load_savant(batter_path, "batter") if batter_path else []
    pitchers = load_savant(pitcher_path, "pitcher") if pitcher_path else []
    all_savant = batters + pitchers
    if not all_savant:
        print("ERROR: no Savant rows loaded", file=sys.stderr)
        return 1

    print(f"Using batter CSV:  {batter_path}")
    print(f"Using pitcher CSV: {pitcher_path}")

    by_norm: dict[str, list[dict]] = {}
    for s in all_savant:
        by_norm.setdefault(s["norm"], []).append(s)

    pool = load_pool(args.pool)
    fieldnames = [
        "dk_id",
        "name",
        "team",
        "salary",
        "savant_name",
        "savant_id",
        "savant_role",
        "xba",
        "xslg",
        "xwoba",
        "xera",
        "pa",
        "hard_hit_pct",
        "barrel_pct",
        "avg_hit_speed",
        "match_kind",
        "match_confidence",
    ]

    out_rows: list[dict] = []
    matched = exact = fuzzy = 0

    for p in pool:
        feat, kind, conf = match_one(p, by_norm, all_savant)
        if feat is None:
            out_rows.append(
                {
                    "dk_id": p["dk_id"],
                    "name": p["name"],
                    "team": p["team"],
                    "salary": p.get("salary", ""),
                    "savant_name": "",
                    "savant_id": "",
                    "savant_role": "",
                    "xba": "",
                    "xslg": "",
                    "xwoba": "",
                    "xera": "",
                    "pa": "",
                    "hard_hit_pct": "",
                    "barrel_pct": "",
                    "avg_hit_speed": "",
                    "match_kind": "unmatched",
                    "match_confidence": 0.0,
                }
            )
            continue
        matched += 1
        if kind.startswith("exact"):
            exact += 1
        else:
            fuzzy += 1
        out_rows.append(
            {
                "dk_id": p["dk_id"],
                "name": p["name"],
                "team": p["team"],
                "salary": p.get("salary", ""),
                "savant_name": feat["savant_name"],
                "savant_id": feat["savant_id"],
                "savant_role": feat["role"],
                "xba": fmt(feat["xba"], 3),
                "xslg": fmt(feat["xslg"], 3),
                "xwoba": fmt(feat["xwoba"], 3),
                "xera": fmt(feat["xera"], 2),
                "pa": fmt(feat["pa"], 0),
                "hard_hit_pct": fmt(feat["hard_hit_pct"], 1),
                "barrel_pct": fmt(feat["barrel_pct"], 1),
                "avg_hit_speed": fmt(feat["avg_hit_speed"], 1),
                "match_kind": kind,
                "match_confidence": f"{conf:.4f}",
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        w.writerows(out_rows)

    rate = matched / len(pool) if pool else 0.0
    print(
        f"Pool={len(pool)} Savant={len(all_savant)} "
        f"(bat={len(batters)} pit={len(pitchers)})"
    )
    print(
        f"Matched={matched} ({rate:.1%}) exact={exact} fuzzy={fuzzy} "
        f"unmatched={len(pool) - matched}"
    )
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
