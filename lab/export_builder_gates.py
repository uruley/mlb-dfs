#!/usr/bin/env python3
"""Export Builder-facing gate tags for tonight's slate.

Does NOT overwrite live projections (proj_fp stays put).
Writes lab/builder-gates-tonight.csv for DFS Builder to consume:
  exclude / cap_1_of_20 / smash_bat / elite_sp / exposure_target / adjusted_proj (hint only).

Usage:
  python3 /home/box/mlb-dfs/lab/export_builder_gates.py
  python3 /home/box/mlb-dfs/lab/export_builder_gates.py --profile cash \
    --out /home/box/mlb-dfs/lab/builder-gates-cash.csv
"""
from __future__ import annotations

import csv
import math
import re
import statistics
import sys
import unicodedata
from pathlib import Path

from slate_gates import CONSTANTS, PROFILES, apply_all_gates, get_profile, _f, _is_pitcher

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
DEFAULT_PROJ = DESK / "projections-tonight.csv"
DEFAULT_BATTERS = DESK / "sources" / "savant-expected-batters-2026.csv"
DEFAULT_PITCHERS = DESK / "sources" / "savant-expected-pitchers-2026.csv"
DEFAULT_OUT = LAB / "builder-gates-tonight.csv"
MIN_PA = 50
STD_FLOOR = 1e-4


def norm_name(s: str) -> str:
    s = (s or "").strip()
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = s.lower().replace(".", "").replace("'", "").replace("-", " ")
    s = re.sub(r"\s+", " ", s).strip()
    for suf in (" jr", " sr", " ii", " iii", " iv"):
        if s.endswith(suf):
            s = s[: -len(suf)].strip()
    return s


def load_savant(path: Path) -> dict[str, dict]:
    out = {}
    if not path.exists():
        return out
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            nm = (row.get("name") or "").strip()
            if not nm:
                raw = row.get("last_name, first_name") or row.get("name_savant") or ""
                if "," in raw:
                    last, first = raw.split(",", 1)
                    nm = f"{first.strip()} {last.strip()}"
                else:
                    nm = raw.strip()
            if not nm:
                continue
            out[norm_name(nm)] = row
    return out


def zscore(vals: list[float]) -> tuple[float, float]:
    if len(vals) < 2:
        return (vals[0] if vals else 0.0), STD_FLOOR
    return statistics.mean(vals), max(statistics.pstdev(vals), STD_FLOOR)


def is_probable(row: dict, pos: str) -> bool:
    src = (row.get("live_source") or row.get("source") or "").strip().lower()
    if src == "probable_sp":
        return True
    if src in ("non_starter", "not_in_order"):
        return False
    notes = (row.get("notes") or "").lower()
    if "not probable" in notes:
        return False
    if "probable sp" in notes or "live_source=probable_sp" in notes:
        return True
    sources = (row.get("sources") or "").lower()
    if "mlb-statsapi-probables" in sources and "non_starter" not in src:
        return True
    return False


def is_posted(row: dict) -> bool:
    src = (row.get("live_source") or row.get("source") or "").strip().lower()
    if src in ("posted", "posted-lineup", "posted_lineup"):
        return True
    blob = " ".join(
        [
            str(row.get("live_source") or ""),
            str(row.get("source") or ""),
            str(row.get("sources") or ""),
            str(row.get("notes") or ""),
            str(row.get("order_status") or ""),
        ]
    ).lower()
    if "posted-lineup" in blob or "posted_lineup" in blob:
        return True
    if src == "posted" or blob.split()[:1] == ["posted"]:
        return True
    if "confirmed" in blob and "unconfirmed" not in blob and "not_in_order" not in blob:
        return True
    return False


def has_order_signal(row: dict) -> bool:
    blob = " ".join(
        [
            str(row.get("live_source") or ""),
            str(row.get("source") or ""),
            str(row.get("sources") or ""),
            str(row.get("notes") or ""),
        ]
    ).lower()
    return any(
        k in blob
        for k in (
            "posted-lineup",
            "posted_lineup",
            "posted",
            "not_in_order",
            "not-in-order",
            "confirmed",
            "probable_sp",
            "non_starter",
        )
    )


def _parse_args():
    import argparse
    ap = argparse.ArgumentParser(description="Export Builder gate tags")
    ap.add_argument("--projections", type=Path, default=DEFAULT_PROJ)
    ap.add_argument("--batters", type=Path, default=DEFAULT_BATTERS)
    ap.add_argument("--pitchers", type=Path, default=DEFAULT_PITCHERS)
    ap.add_argument("--out", type=Path, default=None,
                    help="Default: builder-gates-tonight.csv (gpp) or builder-gates-cash.csv")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="gpp",
                    help="gpp = Dime/GPP; cash = $1-$3 multipliers")
    return ap.parse_args()


def main() -> int:
    args = _parse_args()
    profile = args.profile
    proj_path = args.projections
    batters_path = args.batters
    pitchers_path = args.pitchers
    out_path = args.out or (
        LAB / "builder-gates-cash.csv" if profile == "cash" else DEFAULT_OUT
    )
    cfg = get_profile(profile)
    if not proj_path.exists():
        print(f"ERROR: missing {proj_path}", file=sys.stderr)
        return 1

    batters = load_savant(batters_path)
    pitchers = load_savant(pitchers_path)

    with proj_path.open(newline="", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f))

    xwoba_vals, barrel_vals, xera_vals = [], [], []
    for r in batters.values():
        pa = _f(r.get("pa"), 0) or 0
        xw, br = _f(r.get("xwoba")), _f(r.get("barrel_pct"))
        if pa >= MIN_PA and xw is not None:
            xwoba_vals.append(xw)
        if pa >= MIN_PA and br is not None:
            barrel_vals.append(br)
    for r in pitchers.values():
        pa = _f(r.get("pa"), 0) or 0
        xe = _f(r.get("xera"))
        if pa >= MIN_PA and xe is not None:
            xera_vals.append(xe)
    mu_x, sd_x = zscore(xwoba_vals)
    mu_b, sd_b = zscore(barrel_vals)
    mu_e, sd_e = zscore(xera_vals)

    out_fields = [
        "dk_id",
        "name",
        "team",
        "position",
        "salary",
        "proj_fp",
        "adjusted_proj",
        "gate_tags",
        "gate_action",
        "exposure_target",
        "max_lineups_of_20",
        "smash_bat",
        "elite_sp",
        "gate_notes",
        "z_xwoba",
        "z_barrel",
        "z_xera",
        "xwoba",
        "xera",
        "barrel_pct",
        "probable",
        "posted_order",
    ]

    n_smash = n_elite = n_dead = n_excl = n_cap = 0
    out_rows = []
    for row in rows:
        proj = _f(row.get("proj_fp") or row.get("savant_proj") or row.get("blend_proj"))
        if proj is None:
            continue
        name = (row.get("name") or "").strip()
        nn = norm_name(name)
        pos = (row.get("position") or row.get("pos") or "").strip()
        is_p = _is_pitcher(pos)
        z_xwoba = z_barrel = z_xera = xera = xwoba = barrel = None
        posted = is_posted(row)
        probable = is_probable(row, pos)
        order_known = has_order_signal(row)

        if is_p:
            sav = pitchers.get(nn)
            if sav:
                xera = _f(sav.get("xera"))
                if xera is not None:
                    z_xera = (mu_e - xera) / sd_e
            row = {**row, "pa": (sav or {}).get("pa"), "pos": pos or "SP"}
        else:
            sav = batters.get(nn)
            if sav:
                xwoba = _f(sav.get("xwoba"))
                barrel = _f(sav.get("barrel_pct"))
                if xwoba is not None:
                    z_xwoba = (xwoba - mu_x) / sd_x
                if barrel is not None:
                    z_barrel = (barrel - mu_b) / sd_b
                row = {**row, "pa": sav.get("pa"), "pos": pos or "H"}
            row["confirmed_order"] = posted
            row["order_status"] = "posted" if posted else ("not_in_order" if order_known else "")
            row["order_unknown_ok"] = (not order_known)

        gate = apply_all_gates(
            row,
            proj=proj,
            z_xwoba=z_xwoba,
            z_barrel=z_barrel,
            z_xera=z_xera,
            xera=xera,
            ownership_proj=_f(row.get("own_proj")),
            probable=probable,
            profile=profile,
        )
        tags = gate.tags
        if "smash_bat" in tags:
            n_smash += 1
        if "elite_sp" in tags:
            n_elite += 1
        if "dead_weight" in tags:
            n_dead += 1
        if gate.action == "exclude":
            n_excl += 1
        if gate.action == "cap_1_of_20":
            n_cap += 1

        max20 = ""
        if gate.action == "exclude":
            max20 = "0"
        elif gate.action == "cap_1_of_20":
            max20 = "1"
        elif gate.exposure_target is not None:
            max20 = str(int(round(gate.exposure_target * 20)))

        out_rows.append(
            {
                "dk_id": row.get("dk_id") or "",
                "name": name,
                "team": row.get("team") or "",
                "position": pos,
                "salary": row.get("salary") or "",
                "proj_fp": f"{proj:.2f}",
                "adjusted_proj": f"{(gate.adjusted_proj if gate.adjusted_proj is not None else proj):.2f}",
                "gate_tags": "|".join(tags),
                "gate_action": gate.action,
                "exposure_target": "" if gate.exposure_target is None else f"{gate.exposure_target:.2f}",
                "max_lineups_of_20": max20,
                "smash_bat": "1" if "smash_bat" in tags else "0",
                "elite_sp": "1" if "elite_sp" in tags else "0",
                "gate_notes": gate.notes,
                "z_xwoba": "" if z_xwoba is None else f"{z_xwoba:.3f}",
                "z_barrel": "" if z_barrel is None else f"{z_barrel:.3f}",
                "z_xera": "" if z_xera is None else f"{z_xera:.3f}",
                "xwoba": "" if xwoba is None else f"{xwoba:.3f}",
                "xera": "" if xera is None else f"{xera:.3f}",
                "barrel_pct": "" if barrel is None else f"{barrel:.3f}",
                "probable": "1" if probable else "0",
                "posted_order": "1" if posted else "0",
            }
        )

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields)
        w.writeheader()
        w.writerows(out_rows)

    smash = [r for r in out_rows if r["smash_bat"] == "1"]
    elite = [r for r in out_rows if r["elite_sp"] == "1"]
    excl = [r for r in out_rows if r["gate_action"] == "exclude"]
    cap = [r for r in out_rows if r["gate_action"] == "cap_1_of_20"]

    def top_lines(rows, key, n=12):
        rows = sorted(rows, key=lambda r: -float(r[key]))
        return "\n".join(
            f"  {r['name']:22} {r['team']:3} {r['position']:6} ${r['salary']:<6} "
            f"proj={r['proj_fp']:>6} adj={r['adjusted_proj']:>6} {r['gate_action']} {r['gate_tags']}"
            for r in rows[:n]
        )

    # Don't list every excluded RP — only SP/probable-ish or hitters
    excl_notable = [
        r
        for r in excl
        if r["position"] in ("SP", "P")
        or r["smash_bat"] == "1"
        or float(r["proj_fp"]) >= 4.0
        or r["probable"] == "1"
    ]
    cap_notable = [r for r in cap if r["position"] not in ("RP",)]

    summary = out_path.with_suffix(".summary.txt")
    summary.write_text(
        "\n".join(
            [
                f"Builder gates — {profile} (Sep 12)",
                f"source: {proj_path}",
                f"out: {out_path}",
                f"rows: {len(out_rows)}",
                f"smash_bat: {n_smash}",
                f"elite_sp: {n_elite}",
                f"dead_weight: {n_dead}",
                f"exclude: {n_excl} (many are already-dead non-starters / RPs)",
                f"cap_1_of_20: {n_cap}",
                f"anchors: xwoba μ={mu_x:.3f} σ={sd_x:.3f} n={len(xwoba_vals)}; "
                f"xera μ={mu_e:.3f} σ={sd_e:.3f} n={len(xera_vals)}",
                f"profile={profile} constants: {cfg}",
                "",
                "HOW BUILDER SHOULD USE",
                "- Do NOT need to change proj_fp unless you want smash adjusted_proj as a ceiling hint.",
                "- gate_action=exclude → do not roster (max_lineups_of_20=0).",
                "- gate_action=cap_1_of_20 → at most 1 of 20 lineups.",
                "- elite_sp → aim exposure_target from profile (cash 50%/SP1 60%; gpp 40%/50%).",
                "- smash_bat → GPP: ceiling stacks; cash: tag-only (no proj boost). Max 5 hitters/team.",
                "- Live projections-tonight.csv was NOT overwritten.",
                "",
                "ELITE SP",
                top_lines(elite, "proj_fp") or "  (none)",
                "",
                "SMASH BATS (top by adjusted_proj)",
                top_lines(smash, "adjusted_proj") or "  (none)",
                "",
                "NOTABLE EXCLUDES (SP / posted-ish / proj>=4)",
                top_lines(excl_notable, "proj_fp", 20) or "  (none)",
                "",
                "HITTER CAP_1_OF_20",
                top_lines(cap_notable, "proj_fp", 15) or "  (none)",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary.read_text())
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
