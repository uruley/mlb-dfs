#!/usr/bin/env python3
"""Export Builder gates for the late 2026-09-12 slate.

Reads frozen /home/box/mlb-dfs/projections-late.csv (never writes it).

Posted detection (late file uses source=posted, not posted-lineup):
  posted_order=1 iff source in {posted, posted-lineup, posted_lineup}
  smash_bat only when posted_order=1
  source=not_in_order must NOT get smash (order_unknown_ok=False)

probable from source=probable_sp; RP-as-SP exclude skipped when probable
(slate_gates.dead_weight_gate already skips rp_as_sp when probable=True).

Writes:
  lab/builder-gates-late.csv
  lab/builder-gates-late.summary.txt
  lab/backtests/2026-09-12/projections-late-gated.csv
    proj_fp = smash adjusted_proj; excludes floored to 0.1
  /home/box/mlb-dfs/projections-late-gated.csv  (desk alias copy)
"""
from __future__ import annotations

import csv
import shutil
import statistics
import sys
import unicodedata
import re
from pathlib import Path

from slate_gates import CONSTANTS, apply_all_gates, _f, _is_pitcher

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
PROJ = DESK / "projections-late.csv"
BATTERS = DESK / "sources" / "savant-expected-batters-2026.csv"
PITCHERS = DESK / "sources" / "savant-expected-pitchers-2026.csv"
GATES_OUT = LAB / "builder-gates-late.csv"
GATED_OUT = LAB / "backtests" / "2026-09-12" / "projections-late-gated.csv"
GATED_ALIAS = DESK / "projections-late-gated.csv"
MIN_PA = 50
STD_FLOOR = 1e-4
EXCLUDE_FLOOR = 0.1

POSTED_SOURCES = {"posted", "posted-lineup", "posted_lineup"}
FROZEN_TONIGHT = {
    "projections-tonight.csv",
    "projections-tonight-gated.csv",
    "projections-tonight-ungated.csv",
    "dk-classic-player-pool.csv",
    "projections-late.csv",
}


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


def source_of(row: dict) -> str:
    return (row.get("source") or row.get("live_source") or "").strip().lower()


def is_posted(row: dict) -> bool:
    return source_of(row) in POSTED_SOURCES


def is_probable(row: dict) -> bool:
    return source_of(row) == "probable_sp"


def main() -> int:
    if not PROJ.exists():
        print(f"ERROR: missing {PROJ}", file=sys.stderr)
        return 1

    batters = load_savant(BATTERS)
    pitchers = load_savant(PITCHERS)

    with PROJ.open(newline="", encoding="utf-8-sig") as f:
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

    gate_fields = [
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
    n_posted = n_prob = 0
    gate_rows = []
    gated_proj_rows = []

    for row in rows:
        proj = _f(row.get("proj_fp") or row.get("savant_proj") or row.get("blend_proj"))
        if proj is None:
            continue
        name = (row.get("name") or "").strip()
        nn = norm_name(name)
        pos = (row.get("position") or row.get("pos") or "").strip()
        is_p = _is_pitcher(pos)
        src = source_of(row)
        posted = is_posted(row)
        probable = is_probable(row)
        if posted:
            n_posted += 1
        if probable:
            n_prob += 1

        z_xwoba = z_barrel = z_xera = xera = xwoba = barrel = None
        work = dict(row)
        work["pos"] = pos

        if is_p:
            sav = pitchers.get(nn)
            if sav:
                xera = _f(sav.get("xera"))
                if xera is not None:
                    z_xera = (mu_e - xera) / sd_e
                work["pa"] = sav.get("pa")
        else:
            sav = batters.get(nn)
            if sav:
                xwoba = _f(sav.get("xwoba"))
                barrel = _f(sav.get("barrel_pct"))
                if xwoba is not None:
                    z_xwoba = (xwoba - mu_x) / sd_x
                if barrel is not None:
                    z_barrel = (barrel - mu_b) / sd_b
                work["pa"] = sav.get("pa")
            # Smash ONLY on posted / posted-lineup. not_in_order / tbd / bench → no smash.
            work["confirmed_order"] = posted
            work["order_status"] = "posted" if posted else (
                "not_in_order" if src == "not_in_order" else src
            )
            work["order_unknown_ok"] = False

        gate = apply_all_gates(
            work,
            proj=proj,
            z_xwoba=z_xwoba,
            z_barrel=z_barrel,
            z_xera=z_xera,
            xera=xera,
            ownership_proj=_f(row.get("own_proj")),
            probable=probable,
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

        adj = gate.adjusted_proj if gate.adjusted_proj is not None else proj
        max20 = ""
        if gate.action == "exclude":
            max20 = "0"
        elif gate.action == "cap_1_of_20":
            max20 = "1"
        elif gate.exposure_target is not None:
            max20 = str(int(round(gate.exposure_target * 20)))

        gate_rows.append(
            {
                "dk_id": row.get("dk_id") or "",
                "name": name,
                "team": row.get("team") or "",
                "position": pos,
                "salary": row.get("salary") or "",
                "proj_fp": f"{proj:.2f}",
                "adjusted_proj": f"{adj:.2f}",
                "gate_tags": "|".join(tags),
                "gate_action": gate.action,
                "exposure_target": ""
                if gate.exposure_target is None
                else f"{gate.exposure_target:.2f}",
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

        gated_fp = EXCLUDE_FLOOR if gate.action == "exclude" else adj
        gated_proj_rows.append(
            {
                "dk_id": row.get("dk_id") or "",
                "name": name,
                "position": pos,
                "team": row.get("team") or "",
                "salary": row.get("salary") or "",
                "game_info": row.get("game_info") or "",
                "proj_fp": f"{gated_fp:.2f}",
                "pos": row.get("pos") or pos,
                "source": row.get("source") or "",
                "game": row.get("game") or "",
                "savant_adj": row.get("savant_adj") or "",
                "ungated_proj": f"{proj:.2f}",
                "adjusted_proj": f"{adj:.2f}",
                "gate_tags": "|".join(tags),
                "gate_action": gate.action,
                "exposure_target": ""
                if gate.exposure_target is None
                else f"{gate.exposure_target:.2f}",
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

    gated_fields = [
        "dk_id",
        "name",
        "position",
        "team",
        "salary",
        "game_info",
        "proj_fp",
        "pos",
        "source",
        "game",
        "savant_adj",
        "ungated_proj",
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

    gated_proj_rows.sort(key=lambda r: (-float(r["proj_fp"]), r["name"]))

    GATES_OUT.parent.mkdir(parents=True, exist_ok=True)
    with GATES_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=gate_fields)
        w.writeheader()
        w.writerows(gate_rows)

    if GATED_OUT.name in FROZEN_TONIGHT or GATED_OUT.resolve() == PROJ.resolve():
        print(f"REFUSING to overwrite frozen file: {GATED_OUT}", file=sys.stderr)
        return 2
    GATED_OUT.parent.mkdir(parents=True, exist_ok=True)
    with GATED_OUT.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=gated_fields)
        w.writeheader()
        w.writerows(gated_proj_rows)

    if GATED_ALIAS.name not in FROZEN_TONIGHT:
        shutil.copy2(GATED_OUT, GATED_ALIAS)

    smash = [r for r in gate_rows if r["smash_bat"] == "1"]
    elite = [r for r in gate_rows if r["elite_sp"] == "1"]
    excl = [r for r in gate_rows if r["gate_action"] == "exclude"]
    cap = [r for r in gate_rows if r["gate_action"] == "cap_1_of_20"]

    smash_src = {}
    late_by_id = {r.get("dk_id"): r for r in rows}
    for r in smash:
        s = (late_by_id.get(r["dk_id"], {}).get("source") or "")
        smash_src[s] = smash_src.get(s, 0) + 1

    def top_lines(rs, key, n=12):
        rs = sorted(rs, key=lambda r: -float(r[key]))
        return "\n".join(
            f"  {r['name']:22} {r['team']:3} {r['position']:6} ${r['salary']:<6} "
            f"proj={r['proj_fp']:>6} adj={r['adjusted_proj']:>6} {r['gate_action']} {r['gate_tags']}"
            for r in rs[:n]
        )

    excl_notable = [
        r
        for r in excl
        if r["position"] in ("SP", "P")
        or r["smash_bat"] == "1"
        or float(r["proj_fp"]) >= 4.0
        or r["probable"] == "1"
    ]
    cap_notable = [r for r in cap if r["position"] not in ("RP",)]

    summary = GATES_OUT.with_suffix(".summary.txt")
    summary.write_text(
        "\n".join(
            [
                "Builder gates — late slate (Sep 12)",
                f"source: {PROJ} (FROZEN — not overwritten)",
                f"out: {GATES_OUT}",
                f"gated: {GATED_OUT}",
                f"alias: {GATED_ALIAS}",
                f"rows: {len(gate_rows)}",
                f"posted_order=1: {n_posted} (source in posted/posted-lineup)",
                f"probable_sp: {n_prob}",
                f"smash_bat: {n_smash}  sources={smash_src}",
                f"elite_sp: {n_elite}",
                f"dead_weight: {n_dead}",
                f"exclude: {n_excl} (many are already-dead non-starters / RPs)",
                f"cap_1_of_20: {n_cap}",
                f"anchors: xwoba μ={mu_x:.3f} σ={sd_x:.3f} n={len(xwoba_vals)}; "
                f"xera μ={mu_e:.3f} σ={sd_e:.3f} n={len(xera_vals)}",
                f"constants: {CONSTANTS}",
                "",
                "POSTED DETECTION FIX",
                "- Late file uses source=posted (not posted-lineup).",
                "- posted_order=1 iff source in {posted, posted-lineup, posted_lineup}.",
                "- smash only when posted_order=1; order_unknown_ok=False.",
                "- source=not_in_order / tbd_team / bench do NOT get smash.",
                "- probable from source=probable_sp; RP-as-SP exclude skipped when probable.",
                "- Woo (xERA 3.55) is de facto SP1: keep, not elite (shy of 3.20 / z 0.75).",
                "- Leahy xERA 4.86 / Singer xERA 5.23 excludes are intended.",
                "- gated proj_fp = smash adjusted_proj; excludes floored to 0.1.",
                "- projections-late.csv was NOT overwritten.",
                "",
                "HOW BUILDER SHOULD USE",
                "- gate_action=exclude → do not roster (max_lineups_of_20=0).",
                "- gate_action=cap_1_of_20 → at most 1 of 20 lineups.",
                "- elite_sp → aim exposure_target 0.40 (8/20); soft 50% (10/20) for clear SP1.",
                "- smash_bat → prefer in 3–5 hitter stacks (max 5 hitters/team). Prefer adjusted_proj.",
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
    print(f"Wrote {GATES_OUT}")
    print(f"Wrote {GATED_OUT}")
    print(f"Copied {GATED_ALIAS}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
