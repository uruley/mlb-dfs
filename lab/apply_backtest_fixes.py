#!/usr/bin/env python3
"""Apply Sep 11 backtest gates/boosts to a projections COPY under lab/backtests/.

NEVER writes to live tonight files (projections-tonight.csv, etc.).

Usage:
  python3 /home/box/mlb-dfs/lab/apply_backtest_fixes.py \
    --projections /home/box/mlb-dfs/projections-blend-0911-archive.csv \
    --out /home/box/mlb-dfs/lab/backtests/2026-09-11/projections-savant-fixed.csv
"""

from __future__ import annotations

import argparse
import csv
import math
import re
import statistics
import sys
import unicodedata
from pathlib import Path

from slate_gates import (
    CONSTANTS,
    PROFILES,
    apply_all_gates,
    get_profile,
    _f,
    _is_pitcher,
)

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
DEFAULT_PROJ = DESK / "projections-blend-0911-archive.csv"
DEFAULT_BATTERS = DESK / "sources" / "savant-expected-batters-2026.csv"
DEFAULT_PITCHERS = DESK / "sources" / "savant-expected-pitchers-2026.csv"
DEFAULT_OUT = LAB / "backtests" / "2026-09-11" / "projections-savant-fixed.csv"
STD_FLOOR = 1e-4
MIN_PA = 50


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
    mu = statistics.mean(vals)
    sd = statistics.pstdev(vals)
    return mu, max(sd, STD_FLOOR)


def main() -> int:
    ap = argparse.ArgumentParser(description="Apply lab backtest gates to a projections COPY")
    ap.add_argument("--projections", type=Path, default=DEFAULT_PROJ)
    ap.add_argument("--batters", type=Path, default=DEFAULT_BATTERS)
    ap.add_argument("--pitchers", type=Path, default=DEFAULT_PITCHERS)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--proj-col", type=str, default=None, help="Override proj column")
    ap.add_argument("--profile", choices=sorted(PROFILES), default="gpp",
                    help="gpp = Dime/GPP; cash = $1-$3 multiplier floors")
    args = ap.parse_args()
    profile = args.profile
    cfg = get_profile(profile)

    # Safety: refuse to write into live tonight filenames
    banned = {
        "projections-tonight.csv",
        "projections-blend-tonight.csv",
        "projections-savant-tonight.csv",
        "projections-tonight-own-backup.csv",
    }
    if args.out.name in banned or "tonight" in args.out.name and "0911" not in args.out.name and "fixed" not in args.out.name:
        if args.out.resolve().parent == DESK and "tonight" in args.out.name:
            print(f"REFUSING to overwrite live tonight file: {args.out}", file=sys.stderr)
            return 2

    if not args.projections.exists():
        print(f"ERROR: projections missing: {args.projections}", file=sys.stderr)
        return 1

    batters = load_savant(args.batters)
    pitchers = load_savant(args.pitchers)

    with args.projections.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fields = list(reader.fieldnames or [])

    # Optional position map from Sep 11 own archive (blend file often lacks pos)
    pos_by_name: dict[str, str] = {}
    own_backup = DESK / "projections-tonight-own-backup-0911.csv"
    if own_backup.exists():
        with own_backup.open(newline="", encoding="utf-8-sig") as f:
            for r in csv.DictReader(f):
                pos_by_name[norm_name(r.get("name") or "")] = (r.get("position") or "").strip()

    # Choose proj column
    proj_col = args.proj_col
    if proj_col is None:
        for c in ("savant_proj", "blend_proj", "proj_fp"):
            if c in fields:
                proj_col = c
                break
    if proj_col is None:
        print(f"ERROR: no proj column in {fields}", file=sys.stderr)
        return 1

    # Build league anchors from Savant
    xwoba_vals = []
    barrel_vals = []
    xera_vals = []
    for r in batters.values():
        pa = _f(r.get("pa"), 0) or 0
        xw = _f(r.get("xwoba"))
        br = _f(r.get("barrel_pct"))
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

    out_fields = fields + [
        c
        for c in (
            "base_proj",
            "adjusted_proj",
            "adj_mult",
            "gate_tags",
            "gate_action",
            "exposure_target",
            "gate_notes",
            "z_xwoba",
            "z_barrel",
            "z_xera",
            "xera",
            "xwoba",
            "barrel_pct",
        )
        if c not in fields
    ]

    n_smash = n_elite = n_dead = n_excl = 0
    out_rows = []
    for row in rows:
        proj = _f(row.get(proj_col))
        if proj is None:
            continue
        name = (row.get("name") or "").strip()
        nn = norm_name(name)
        pos = (row.get("pos") or row.get("position") or pos_by_name.get(nn) or "").strip()
        sav = None
        z_xwoba = z_barrel = z_xera = xera = xwoba = barrel = None
        is_p = _is_pitcher(pos)
        # If no pos, infer pitcher from Savant pitcher table + salary SP tier
        if not pos and nn in pitchers and nn not in batters:
            is_p = True
            pos = "SP"
        elif not pos and nn in pitchers and (_f(row.get("salary"), 0) or 0) >= 6000:
            # Ambiguous name; high salary → treat as pitcher
            is_p = True
            pos = "SP"

        if is_p:
            sav = pitchers.get(nn)
            if sav:
                xera = _f(sav.get("xera"))
                if xera is not None:
                    z_xera = (mu_e - xera) / sd_e  # lower better
            row = {**row, "pa": (sav or {}).get("pa"), "pos": pos or "SP"}
            probable = pos.upper() in ("SP", "P") or pos.upper().startswith("SP")
            if not pos or pos.upper() == "P":
                probable = True  # Classic P slot / unknown → allow elite gate
        else:
            if nn in batters:
                sav = batters[nn]
                xwoba = _f(sav.get("xwoba"))
                barrel = _f(sav.get("barrel_pct"))
                if xwoba is not None:
                    z_xwoba = (xwoba - mu_x) / sd_x
                if barrel is not None:
                    z_barrel = (barrel - mu_b) / sd_b
                row = {
                    **row,
                    "pa": sav.get("pa"),
                    "pos": pos or "H",
                    "order_unknown_ok": True,
                }
            probable = None

        own = _f(row.get("own_proj"))
        gate = apply_all_gates(
            row,
            proj=proj,
            z_xwoba=z_xwoba,
            z_barrel=z_barrel,
            z_xera=z_xera,
            xera=xera,
            ownership_proj=own,
            probable=probable,
                    profile=profile,
        )
        if "smash_bat" in gate.tags:
            n_smash += 1
        if "elite_sp" in gate.tags:
            n_elite += 1
        if "dead_weight" in gate.tags:
            n_dead += 1
        if gate.action == "exclude":
            n_excl += 1

        out = dict(row)
        out["base_proj"] = f"{proj:.4f}"
        out["adjusted_proj"] = f"{(gate.adjusted_proj or proj):.4f}"
        out["adj_mult"] = f"{gate.adj_mult:.4f}"
        out["gate_tags"] = "|".join(gate.tags)
        out["gate_action"] = gate.action
        out["exposure_target"] = "" if gate.exposure_target is None else f"{gate.exposure_target:.2f}"
        out["gate_notes"] = gate.notes
        out["z_xwoba"] = "" if z_xwoba is None else f"{z_xwoba:.3f}"
        out["z_barrel"] = "" if z_barrel is None else f"{z_barrel:.3f}"
        out["z_xera"] = "" if z_xera is None else f"{z_xera:.3f}"
        out["xera"] = "" if xera is None else f"{xera:.3f}"
        out["xwoba"] = "" if xwoba is None else f"{xwoba:.3f}"
        out["barrel_pct"] = "" if barrel is None else f"{barrel:.3f}"
        # Also update savant_proj-like column for downstream if present
        if "savant_proj" in fields:
            out["savant_proj"] = out["adjusted_proj"]
        out_rows.append(out)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=out_fields, extrasaction="ignore")
        w.writeheader()
        for r in out_rows:
            w.writerow({k: r.get(k, "") for k in out_fields})

    summary = args.out.with_suffix(".summary.txt")
    summary.write_text(
        "\n".join(
            [
                f"apply_backtest_fixes profile={profile} → {args.out}",
                f"source: {args.projections}",
                f"proj_col: {proj_col}",
                f"rows: {len(out_rows)}",
                f"smash_bat tags: {n_smash}",
                f"elite_sp tags: {n_elite}",
                f"dead_weight tags: {n_dead}",
                f"exclude actions: {n_excl}",
                f"anchors: xwoba μ={mu_x:.3f} σ={sd_x:.3f} (n={len(xwoba_vals)}); "
                f"barrel μ={mu_b:.3f} σ={sd_b:.3f}; xera μ={mu_e:.3f} σ={sd_e:.3f} (n={len(xera_vals)})",
                f"profile={profile} constants: {cfg}",
                "NOTE: lab copy only — live tonight projections untouched.",
            ]
        )
        + "\n",
        encoding="utf-8",
    )
    print(summary.read_text())
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
