#!/usr/bin/env python3
"""Savant-adjusted projection uplift for MLB DFS (DraftKings Classic).

Folds Baseball Savant expected stats into blend projections as a transparent,
tunable percentage nudge — does not replace salary/matchup stack logic.

Method
------
Base = blend_proj (fallback own_proj / dff_proj if blend missing).

Batters (savant_role=batter with valid xwoba):
  League anchor: mean xwOBA among joined batters with PA >= --min-pa
                 (falls back to all joined batters with valid xwoba if thin).
  z_xwoba  = (xwoba - mean_xwoba) / std_xwoba   (std floored at 1e-4)
  z_barrel = (barrel_pct - mean_barrel) / std_barrel  (same PA filter)
  raw = --xwoba-coef * z_xwoba + --barrel-coef * z_barrel
  savant_adj = blend_proj * clip(raw, -max_bat_pct, +max_bat_pct)

Pitchers (savant_role=pitcher with valid xera):
  League anchor: mean xERA among joined pitchers with PA >= --min-pa
                 (PA is batters-faced proxy from Savant).
  z_xera = (mean_xera - xera) / std_xera   # lower xERA = positive skill
  Optional hard-hit against: z_hh = (mean_hh - hard_hit_pct) / std_hh
  raw = --xera-coef * z_xera + --hh-coef * z_hh
  savant_adj = blend_proj * clip(raw, -max_pit_pct, +max_pit_pct)

No Savant match / missing key metric:
  savant_adj = 0, savant_proj = blend_proj, adj_reason = no_savant

savant_proj = max(0.1, blend_proj + savant_adj)
value       = savant_proj / (salary / 1000)

Default coefficients (CLI-overridable):
  xwoba_coef=0.08, barrel_coef=0.03, xera_coef=0.10, hh_coef=0.0
  max_bat_pct=0.18, max_pit_pct=0.20, min_pa=50

Does NOT modify build_lineups_50.py / build_projections.py or lineups-50*.
"""

from __future__ import annotations

import argparse
import csv
import math
import statistics
import sys
from pathlib import Path

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
DEFAULT_BLEND = DESK / "projections-blend-tonight.csv"
DEFAULT_FEATURES = LAB / "features-savant-tonight.csv"
DEFAULT_OUT = DESK / "projections-savant-tonight.csv"
DEFAULT_SUMMARY = LAB / "projections-savant-tonight-summary.txt"

# Defaults match method docstring
DEFAULT_XWOBA_COEF = 0.08
DEFAULT_BARREL_COEF = 0.03
DEFAULT_XERA_COEF = 0.10
DEFAULT_HH_COEF = 0.0
DEFAULT_MAX_BAT = 0.18
DEFAULT_MAX_PIT = 0.20
DEFAULT_MIN_PA = 50
STD_FLOOR = 1e-4
MIN_ANCHOR_N = 10  # if PA-filtered set thinner than this, use all joined


OUT_FIELDS = [
    "dk_id",
    "name",
    "team",
    "salary",
    "blend_proj",
    "savant_adj",
    "savant_proj",
    "value",
    "xwoba",
    "xera",
    "barrel_pct",
    "hard_hit_pct",
    "savant_role",
    "adj_reason",
]


def safe_float(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def clip(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


def mean_std(vals: list[float]) -> tuple[float, float]:
    if not vals:
        return 0.0, STD_FLOOR
    if len(vals) == 1:
        return vals[0], STD_FLOOR
    m = statistics.fmean(vals)
    # population-ish sample std; floor tiny
    s = statistics.stdev(vals)
    return m, max(s, STD_FLOOR)


def load_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def base_proj(row: dict) -> float | None:
    for col in ("blend_proj", "own_proj", "dff_proj", "proj_fp"):
        v = safe_float(row.get(col))
        if v is not None:
            return v
    return None


def fmt_num(v: float | None, nd: int = 4) -> str:
    if v is None:
        return ""
    return f"{v:.{nd}f}"


def build_anchors(
    feats: list[dict], min_pa: int
) -> dict:
    """Compute league anchors for batters (xwoba, barrel) and pitchers (xera, hh)."""

    def collect(role: str, metric: str, pa_thr: int | None):
        out = []
        for r in feats:
            if (r.get("savant_role") or "").strip() != role:
                continue
            v = safe_float(r.get(metric))
            if v is None:
                continue
            if pa_thr is not None:
                pa = safe_float(r.get("pa"), 0.0) or 0.0
                if pa < pa_thr:
                    continue
            out.append(v)
        return out

    bat_xw_pa = collect("batter", "xwoba", min_pa)
    bat_xw_all = collect("batter", "xwoba", None)
    bat_xw = bat_xw_pa if len(bat_xw_pa) >= MIN_ANCHOR_N else bat_xw_all
    bat_xw_src = f"PA>={min_pa}" if len(bat_xw_pa) >= MIN_ANCHOR_N else "all_joined_batters"

    bat_br_pa = collect("batter", "barrel_pct", min_pa)
    bat_br_all = collect("batter", "barrel_pct", None)
    bat_br = bat_br_pa if len(bat_br_pa) >= MIN_ANCHOR_N else bat_br_all
    bat_br_src = f"PA>={min_pa}" if len(bat_br_pa) >= MIN_ANCHOR_N else "all_joined_batters"

    pit_xe_pa = collect("pitcher", "xera", min_pa)
    pit_xe_all = collect("pitcher", "xera", None)
    pit_xe = pit_xe_pa if len(pit_xe_pa) >= MIN_ANCHOR_N else pit_xe_all
    pit_xe_src = f"PA>={min_pa}" if len(pit_xe_pa) >= MIN_ANCHOR_N else "all_joined_pitchers"

    pit_hh_pa = collect("pitcher", "hard_hit_pct", min_pa)
    pit_hh_all = collect("pitcher", "hard_hit_pct", None)
    pit_hh = pit_hh_pa if len(pit_hh_pa) >= MIN_ANCHOR_N else pit_hh_all
    pit_hh_src = f"PA>={min_pa}" if len(pit_hh_pa) >= MIN_ANCHOR_N else "all_joined_pitchers"

    mx, sx = mean_std(bat_xw)
    mb, sb = mean_std(bat_br)
    me, se = mean_std(pit_xe)
    mh, sh = mean_std(pit_hh)

    return {
        "bat_xwoba_mean": mx,
        "bat_xwoba_std": sx,
        "bat_xwoba_n": len(bat_xw),
        "bat_xwoba_src": bat_xw_src,
        "bat_barrel_mean": mb,
        "bat_barrel_std": sb,
        "bat_barrel_n": len(bat_br),
        "bat_barrel_src": bat_br_src,
        "pit_xera_mean": me,
        "pit_xera_std": se,
        "pit_xera_n": len(pit_xe),
        "pit_xera_src": pit_xe_src,
        "pit_hh_mean": mh,
        "pit_hh_std": sh,
        "pit_hh_n": len(pit_hh),
        "pit_hh_src": pit_hh_src,
    }


def adjust_player(
    blend: float,
    feat: dict | None,
    anchors: dict,
    *,
    xwoba_coef: float,
    barrel_coef: float,
    xera_coef: float,
    hh_coef: float,
    max_bat: float,
    max_pit: float,
) -> tuple[float, str, dict]:
    """Return (savant_adj, adj_reason, feature snapshot)."""
    snap = {
        "xwoba": None,
        "xera": None,
        "barrel_pct": None,
        "hard_hit_pct": None,
        "savant_role": "",
    }
    if not feat:
        return 0.0, "no_savant", snap

    role = (feat.get("savant_role") or "").strip()
    snap["savant_role"] = role
    snap["xwoba"] = safe_float(feat.get("xwoba"))
    snap["xera"] = safe_float(feat.get("xera"))
    snap["barrel_pct"] = safe_float(feat.get("barrel_pct"))
    snap["hard_hit_pct"] = safe_float(feat.get("hard_hit_pct"))

    match_kind = (feat.get("match_kind") or "").strip()
    if not role or match_kind == "unmatched":
        return 0.0, "no_savant", snap

    if role == "batter":
        xw = snap["xwoba"]
        if xw is None:
            return 0.0, "no_savant_xwoba", snap
        z_xw = (xw - anchors["bat_xwoba_mean"]) / anchors["bat_xwoba_std"]
        z_br = 0.0
        br_note = ""
        if snap["barrel_pct"] is not None and barrel_coef != 0.0:
            z_br = (snap["barrel_pct"] - anchors["bat_barrel_mean"]) / anchors["bat_barrel_std"]
            br_note = f"+{barrel_coef}*z_barrel({z_br:+.2f})"
        raw = xwoba_coef * z_xw + barrel_coef * z_br
        pct = clip(raw, -max_bat, max_bat)
        adj = blend * pct
        reason = (
            f"batter:z_xwoba={z_xw:+.2f}*{xwoba_coef}{br_note};"
            f"pct={pct:+.4f};clip=±{max_bat}"
        )
        return adj, reason, snap

    if role == "pitcher":
        xe = snap["xera"]
        if xe is None:
            return 0.0, "no_savant_xera", snap
        z_xe = (anchors["pit_xera_mean"] - xe) / anchors["pit_xera_std"]
        z_hh = 0.0
        hh_note = ""
        if snap["hard_hit_pct"] is not None and hh_coef != 0.0:
            z_hh = (anchors["pit_hh_mean"] - snap["hard_hit_pct"]) / anchors["pit_hh_std"]
            hh_note = f"+{hh_coef}*z_hh({z_hh:+.2f})"
        raw = xera_coef * z_xe + hh_coef * z_hh
        pct = clip(raw, -max_pit, max_pit)
        adj = blend * pct
        reason = (
            f"pitcher:z_xera={z_xe:+.2f}*{xera_coef}{hh_note};"
            f"pct={pct:+.4f};clip=±{max_pit}"
        )
        return adj, reason, snap

    return 0.0, "no_savant", snap


def percentile(sorted_vals: list[float], p: float) -> float:
    if not sorted_vals:
        return float("nan")
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    k = (len(sorted_vals) - 1) * p
    f = math.floor(k)
    c = math.ceil(k)
    if f == c:
        return sorted_vals[int(k)]
    return sorted_vals[f] * (c - k) + sorted_vals[c] * (k - f)


def write_summary(
    path: Path,
    *,
    args: argparse.Namespace,
    anchors: dict,
    rows: list[dict],
    n_blend: int,
    n_feat: int,
    n_matched_feat: int,
) -> None:
    adjs = [safe_float(r["savant_adj"], 0.0) or 0.0 for r in rows]
    nonzero = [a for a in adjs if abs(a) > 1e-12]
    abs_adjs = sorted(abs(a) for a in nonzero)
    adjs_sorted = sorted(nonzero)

    bat_adj = [
        r
        for r in rows
        if r.get("savant_role") == "batter" and abs(safe_float(r["savant_adj"], 0) or 0) > 1e-12
    ]
    pit_adj = [
        r
        for r in rows
        if r.get("savant_role") == "pitcher" and abs(safe_float(r["savant_adj"], 0) or 0) > 1e-12
    ]

    by_delta = sorted(
        rows,
        key=lambda r: safe_float(r["savant_adj"], 0.0) or 0.0,
        reverse=True,
    )
    top_pos = [r for r in by_delta if (safe_float(r["savant_adj"], 0) or 0) > 0][:10]
    top_neg = [r for r in reversed(by_delta) if (safe_float(r["savant_adj"], 0) or 0) < 0][:10]

    lines: list[str] = []
    lines.append("Savant-adjusted projection uplift — summary")
    lines.append("=" * 48)
    lines.append("")
    lines.append("Method")
    lines.append("------")
    lines.append("Base = blend_proj (fallback own/dff).")
    lines.append(
        f"Batters: savant_adj = blend * clip({args.xwoba_coef}*z_xwoba"
        f" + {args.barrel_coef}*z_barrel, ±{args.max_bat_pct})"
    )
    lines.append(
        f"Pitchers: savant_adj = blend * clip({args.xera_coef}*z_xera"
        f" + {args.hh_coef}*z_hh_against, ±{args.max_pit_pct})"
    )
    lines.append("  (z_xera / z_hh inverted so lower xERA / hard-hit = positive)")
    lines.append("savant_proj = max(0.1, blend_proj + savant_adj)")
    lines.append("value = savant_proj / (salary/1000)")
    lines.append("No match / missing key metric → adj=0, reason=no_savant*")
    lines.append("")
    lines.append("Constants used")
    lines.append("--------------")
    lines.append(f"  xwoba_coef   = {args.xwoba_coef}")
    lines.append(f"  barrel_coef  = {args.barrel_coef}")
    lines.append(f"  xera_coef    = {args.xera_coef}")
    lines.append(f"  hh_coef      = {args.hh_coef}")
    lines.append(f"  max_bat_pct  = {args.max_bat_pct}")
    lines.append(f"  max_pit_pct  = {args.max_pit_pct}")
    lines.append(f"  min_pa       = {args.min_pa}")
    lines.append(f"  std_floor    = {STD_FLOOR}")
    lines.append("")
    lines.append("League anchors")
    lines.append("--------------")
    lines.append(
        f"  batter xwOBA: mean={anchors['bat_xwoba_mean']:.4f} "
        f"std={anchors['bat_xwoba_std']:.4f} n={anchors['bat_xwoba_n']} "
        f"({anchors['bat_xwoba_src']})"
    )
    lines.append(
        f"  batter barrel%: mean={anchors['bat_barrel_mean']:.4f} "
        f"std={anchors['bat_barrel_std']:.4f} n={anchors['bat_barrel_n']} "
        f"({anchors['bat_barrel_src']})"
    )
    lines.append(
        f"  pitcher xERA: mean={anchors['pit_xera_mean']:.4f} "
        f"std={anchors['pit_xera_std']:.4f} n={anchors['pit_xera_n']} "
        f"({anchors['pit_xera_src']})"
    )
    lines.append(
        f"  pitcher hard_hit%: mean={anchors['pit_hh_mean']:.4f} "
        f"std={anchors['pit_hh_std']:.4f} n={anchors['pit_hh_n']} "
        f"({anchors['pit_hh_src']})"
    )
    lines.append("")
    lines.append("Coverage")
    lines.append("--------")
    lines.append(f"  blend rows:           {n_blend}")
    lines.append(f"  features rows:        {n_feat}")
    lines.append(f"  features matched:     {n_matched_feat}")
    lines.append(f"  output rows:          {len(rows)}")
    lines.append(f"  nonzero savant_adj:   {len(nonzero)}")
    lines.append(f"    batters adjusted:   {len(bat_adj)}")
    lines.append(f"    pitchers adjusted:  {len(pit_adj)}")
    lines.append(f"  zero adj (pass-thru): {len(rows) - len(nonzero)}")
    lines.append("")
    lines.append("Adjustment distribution (nonzero only)")
    lines.append("--------------------------------------")
    if nonzero:
        mean_abs = sum(abs(a) for a in nonzero) / len(nonzero)
        lines.append(f"  n:        {len(nonzero)}")
        lines.append(f"  mean adj: {statistics.fmean(nonzero):+.4f}")
        lines.append(f"  mean |adj|: {mean_abs:.4f}")
        lines.append(f"  min/max:  {min(nonzero):+.4f} / {max(nonzero):+.4f}")
        lines.append(f"  p10 adj:  {percentile(adjs_sorted, 0.10):+.4f}")
        lines.append(f"  p50 adj:  {percentile(adjs_sorted, 0.50):+.4f}")
        lines.append(f"  p90 adj:  {percentile(adjs_sorted, 0.90):+.4f}")
        lines.append(f"  p10 |adj|: {percentile(abs_adjs, 0.10):.4f}")
        lines.append(f"  p90 |adj|: {percentile(abs_adjs, 0.90):.4f}")
    else:
        lines.append("  (none)")
    lines.append("")
    lines.append("Top 10 positive deltas (blend → savant)")
    lines.append("---------------------------------------")
    for r in top_pos:
        b = safe_float(r["blend_proj"], 0) or 0
        s = safe_float(r["savant_proj"], 0) or 0
        a = safe_float(r["savant_adj"], 0) or 0
        lines.append(
            f"  {r['name']:<22} {r['team']:<4} {r['savant_role']:<7} "
            f"{b:6.2f} → {s:6.2f}  (Δ{a:+.3f})  {r['adj_reason'][:60]}"
        )
    lines.append("")
    lines.append("Top 10 negative deltas (blend → savant)")
    lines.append("---------------------------------------")
    for r in top_neg:
        b = safe_float(r["blend_proj"], 0) or 0
        s = safe_float(r["savant_proj"], 0) or 0
        a = safe_float(r["savant_adj"], 0) or 0
        lines.append(
            f"  {r['name']:<22} {r['team']:<4} {r['savant_role']:<7} "
            f"{b:6.2f} → {s:6.2f}  (Δ{a:+.3f})  {r['adj_reason'][:60]}"
        )
    lines.append("")
    lines.append("Inputs / outputs")
    lines.append("----------------")
    lines.append(f"  blend:    {args.blend}")
    lines.append(f"  features: {args.features}")
    lines.append(f"  out:      {args.out}")
    lines.append(f"  summary:  {path}")
    lines.append("")
    lines.append(
        "Backtest tip: copy projections-savant-tonight.csv into "
        "lab/backtests/YYYY-MM-DD/projections.csv (keep savant_proj; "
        "or alias as blend_proj). Or: "
        "python3 backtest.py --demo --blend …/projections-savant-tonight.csv "
        "(demo prefers savant_proj when present)."
    )
    lines.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fold Baseball Savant x-stats into blend projections"
    )
    ap.add_argument("--blend", type=Path, default=DEFAULT_BLEND)
    ap.add_argument("--features", type=Path, default=DEFAULT_FEATURES)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    ap.add_argument("--xwoba-coef", type=float, default=DEFAULT_XWOBA_COEF)
    ap.add_argument("--barrel-coef", type=float, default=DEFAULT_BARREL_COEF)
    ap.add_argument("--xera-coef", type=float, default=DEFAULT_XERA_COEF)
    ap.add_argument(
        "--hh-coef",
        type=float,
        default=DEFAULT_HH_COEF,
        help="Pitcher hard-hit-against coef (default 0 = off)",
    )
    ap.add_argument("--max-bat-pct", type=float, default=DEFAULT_MAX_BAT)
    ap.add_argument("--max-pit-pct", type=float, default=DEFAULT_MAX_PIT)
    ap.add_argument("--min-pa", type=int, default=DEFAULT_MIN_PA)
    args = ap.parse_args()

    if not args.blend.exists():
        print(f"ERROR: blend missing: {args.blend}", file=sys.stderr)
        return 1
    if not args.features.exists():
        print(f"ERROR: features missing: {args.features}", file=sys.stderr)
        return 1

    blend_rows = load_csv(args.blend)
    feat_rows = load_csv(args.features)
    feat_by_id: dict[str, dict] = {}
    for r in feat_rows:
        dk = str(r.get("dk_id") or "").strip()
        if dk:
            feat_by_id[dk] = r

    n_matched_feat = sum(
        1
        for r in feat_rows
        if (r.get("match_kind") or "").strip() not in ("", "unmatched")
    )

    anchors = build_anchors(feat_rows, args.min_pa)

    out_rows: list[dict] = []
    skipped = 0
    for row in blend_rows:
        dk = str(row.get("dk_id") or "").strip()
        bp = base_proj(row)
        if not dk or bp is None:
            skipped += 1
            continue
        sal = safe_float(row.get("salary"), 0.0) or 0.0
        feat = feat_by_id.get(dk)
        adj, reason, snap = adjust_player(
            bp,
            feat,
            anchors,
            xwoba_coef=args.xwoba_coef,
            barrel_coef=args.barrel_coef,
            xera_coef=args.xera_coef,
            hh_coef=args.hh_coef,
            max_bat=args.max_bat_pct,
            max_pit=args.max_pit_pct,
        )
        sp = max(0.1, bp + adj)
        value = sp / (sal / 1000.0) if sal > 0 else 0.0
        out_rows.append(
            {
                "dk_id": dk,
                "name": (row.get("name") or "").strip(),
                "team": (row.get("team") or "").strip(),
                "salary": int(sal) if sal == int(sal) else sal,
                "blend_proj": f"{bp:.4f}",
                "savant_adj": f"{adj:.6f}",
                "savant_proj": f"{sp:.4f}",
                "value": f"{value:.4f}",
                "xwoba": fmt_num(snap["xwoba"], 4),
                "xera": fmt_num(snap["xera"], 2),
                "barrel_pct": fmt_num(snap["barrel_pct"], 1),
                "hard_hit_pct": fmt_num(snap["hard_hit_pct"], 1),
                "savant_role": snap["savant_role"],
                "adj_reason": reason,
            }
        )

    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=OUT_FIELDS)
        w.writeheader()
        w.writerows(out_rows)

    write_summary(
        args.summary,
        args=args,
        anchors=anchors,
        rows=out_rows,
        n_blend=len(blend_rows),
        n_feat=len(feat_rows),
        n_matched_feat=n_matched_feat,
    )

    nonzero = sum(
        1 for r in out_rows if abs(safe_float(r["savant_adj"], 0) or 0) > 1e-12
    )
    print(f"Wrote {args.out}  rows={len(out_rows)} nonzero_adj={nonzero} skipped={skipped}")
    print(f"Wrote {args.summary}")
    print(
        "Anchors: "
        f"xwOBA μ={anchors['bat_xwoba_mean']:.4f} (n={anchors['bat_xwoba_n']}, {anchors['bat_xwoba_src']}); "
        f"xERA μ={anchors['pit_xera_mean']:.3f} (n={anchors['pit_xera_n']}, {anchors['pit_xera_src']})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
