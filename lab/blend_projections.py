#!/usr/bin/env python3
"""Blend own-model projections with DailyFantasyFuel free CSV for DK Classic."""

from __future__ import annotations

import argparse
import csv
import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

DESK = Path("/home/box/mlb-dfs")
DEFAULT_OWN = DESK / "projections-tonight.csv"
DEFAULT_DFF = DESK / "sources" / "dailyfantasyfuel-tonight.csv"
DEFAULT_POOL = DESK / "dk-classic-player-pool.csv"
DEFAULT_OUT = DESK / "projections-blend-tonight.csv"

# DK / industry team abbrev aliases
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
}

DFF_WEIGHT = 0.55
OWN_WEIGHT = 0.45
FUZZY_THRESHOLD = 0.85


def norm_team(t: str) -> str:
    t = (t or "").strip().upper()
    return TEAM_MAP.get(t, t)


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


def safe_float(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def load_own(path: Path) -> dict[tuple[str, str], dict]:
    by_key: dict[tuple[str, str], dict] = {}
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            name = row.get("name", "").strip()
            team = norm_team(row.get("team", ""))
            key = (norm_name(name), team)
            by_key[key] = row
    return by_key


def load_pool_salary(path: Path) -> dict[str, int]:
    """dk_id -> salary from DK player pool (authoritative)."""
    out: dict[str, int] = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dk_id = str(row.get("ID", "")).strip()
            sal = safe_float(row.get("Salary"), None)
            if dk_id and sal is not None:
                out[dk_id] = int(sal)
    return out


def match_dff_to_own(
    dff_rows: list[dict], own: dict[tuple[str, str], dict]
) -> tuple[dict[str, dict], int, int, list[str]]:
    """Return dk_id -> dff match info, exact count, fuzzy count, unmatched notes."""
    matched: dict[str, dict] = {}
    exact = fuzzy = 0
    notes: list[str] = []

    for row in dff_rows:
        full = f"{row.get('first_name', '').strip()} {row.get('last_name', '').strip()}".strip()
        team = norm_team(row.get("team", ""))
        nk = norm_name(full)
        key = (nk, team)
        own_row = own.get(key)
        match_kind = "exact"

        if own_row is None:
            # fuzzy within same team
            cands = [(k, v) for k, v in own.items() if k[1] == team]
            best = None
            best_sc = 0.0
            for (on, _ot), v in cands:
                sc = SequenceMatcher(None, nk, on).ratio()
                if sc > best_sc:
                    best_sc = sc
                    best = v
            if best is not None and best_sc >= FUZZY_THRESHOLD:
                own_row = best
                match_kind = f"fuzzy:{best_sc:.2f}"
                fuzzy += 1
            else:
                notes.append(f"unmatched DFF: {full} ({team})")
                continue
        else:
            exact += 1

        dk_id = str(own_row["dk_id"]).strip()
        matched[dk_id] = {
            "dff_proj": safe_float(row.get("ppg_projection")),
            "dff_own": safe_float(row.get("ownership_projection")),
            "dff_value": safe_float(row.get("value_projection")),
            "match_kind": match_kind,
            "dff_name": full,
            "dff_team": team,
        }
    return matched, exact, fuzzy, notes


def blend_proj(own_p, dff_p, dff_w: float = DFF_WEIGHT, own_w: float = OWN_WEIGHT) -> tuple[float | None, str]:
    has_own = own_p is not None
    has_dff = dff_p is not None
    if has_own and has_dff:
        return dff_w * dff_p + own_w * own_p, "own+dff"
    if has_dff:
        return dff_p, "dff"
    if has_own:
        return own_p, "own"
    return None, "none"


def main() -> int:
    ap = argparse.ArgumentParser(description="Blend own + DFF projections for DK Classic")
    ap.add_argument("--own", type=Path, default=DEFAULT_OWN)
    ap.add_argument("--dff", type=Path, default=DEFAULT_DFF)
    ap.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dff-weight", type=float, default=DFF_WEIGHT)
    args = ap.parse_args()

    dff_w = float(args.dff_weight)
    own_w = 1.0 - dff_w

    if not args.own.exists():
        print(f"ERROR: own projections missing: {args.own}", file=sys.stderr)
        return 1
    if not args.dff.exists():
        print(f"ERROR: DFF CSV missing: {args.dff}", file=sys.stderr)
        return 1

    own = load_own(args.own)
    pool_sal = load_pool_salary(args.pool)

    with args.dff.open(newline="", encoding="utf-8") as f:
        dff_rows = list(csv.DictReader(f))

    dff_by_id, exact, fuzzy, unmatched = match_dff_to_own(dff_rows, own)
    dff_total = len(dff_rows)
    matched_n = exact + fuzzy
    match_rate = matched_n / dff_total if dff_total else 0.0

    # Emit one row per own-model player (full slate), enriching with DFF when present
    out_rows = []
    both = own_only = dff_only_count = 0  # dff_only shouldn't happen if we key off own

    for key, row in own.items():
        dk_id = str(row["dk_id"]).strip()
        name = row.get("name", "").strip()
        team = norm_team(row.get("team", ""))
        salary = pool_sal.get(dk_id)
        if salary is None:
            salary = int(safe_float(row.get("salary"), 0) or 0)

        own_p = safe_float(row.get("proj_fp"))
        dff_info = dff_by_id.get(dk_id)
        dff_p = dff_info["dff_proj"] if dff_info else None
        bp, sources = blend_proj(own_p, dff_p, dff_w, own_w)

        if sources == "own+dff":
            both += 1
        elif sources == "own":
            own_only += 1
        elif sources == "dff":
            dff_only_count += 1

        value = None
        if bp is not None and salary and salary > 0:
            value = round(bp / (salary / 1000.0), 3)

        notes_parts = []
        if row.get("notes"):
            notes_parts.append(row["notes"].strip())
        if dff_info and dff_info["match_kind"].startswith("fuzzy"):
            notes_parts.append(f"matched DFF via {dff_info['match_kind']} ({dff_info['dff_name']})")

        out_rows.append(
            {
                "dk_id": dk_id,
                "name": name,
                "team": team,
                "salary": salary,
                "own_proj": "" if own_p is None else round(own_p, 3),
                "dff_proj": "" if dff_p is None else round(dff_p, 3),
                "blend_proj": "" if bp is None else round(bp, 3),
                "value": "" if value is None else value,
                "sources": sources,
                "notes": "; ".join(notes_parts),
            }
        )

    # Sort: blend_proj desc, then salary desc
    def sort_key(r):
        bp = r["blend_proj"]
        bp_v = float(bp) if bp != "" else -1e9
        return (-bp_v, -int(r["salary"] or 0))

    out_rows.sort(key=sort_key)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = [
        "dk_id",
        "name",
        "team",
        "salary",
        "own_proj",
        "dff_proj",
        "blend_proj",
        "value",
        "sources",
        "notes",
    ]
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(out_rows)

    print(f"DFF players: {dff_total}")
    print(f"Matched to DK IDs: {matched_n} (exact={exact}, fuzzy={fuzzy})")
    print(f"Match rate: {match_rate:.1%} ({matched_n}/{dff_total})")
    print(f"Blend rows written: {len(out_rows)} -> {args.out}")
    print(f"  both sources: {both}")
    print(f"  own only: {own_only}")
    print(f"  dff only: {dff_only_count}")
    print(f"  blend weights: DFF={dff_w:.2f}, own={own_w:.2f}")
    if unmatched:
        print(f"Unmatched DFF ({len(unmatched)}):")
        for u in unmatched[:20]:
            print(f"  {u}")
        if len(unmatched) > 20:
            print(f"  ... +{len(unmatched) - 20} more")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
