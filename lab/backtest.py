#!/usr/bin/env python3
"""Projection backtest for Ulysses's MLB DFS desk.

Folder convention:
  /home/box/mlb-dfs/lab/backtests/YYYY-MM-DD/
    projections.csv   # dk_id + projection column (blend_proj / savant_proj / proj_fp)
    actuals.csv       # dk_id and/or name + actual_fp

Metrics: MAE, RMSE, Spearman rank correlation, top-20% overlap.
Splits hitters vs pitchers when position is available.
Optional bias flags: low-salary hitter overproj, OF smash underproj.

Usage:
  python3 /home/box/mlb-dfs/lab/backtest.py --demo
  python3 /home/box/mlb-dfs/lab/backtest.py --date 2026-09-11
  python3 /home/box/mlb-dfs/lab/backtest.py --date 2026-09-11 --proj-col savant_proj
"""

from __future__ import annotations

import argparse
import csv
import math
import random
import re
import sys
import unicodedata
from pathlib import Path

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
BACKTESTS = LAB / "backtests"
DEFAULT_BLEND = DESK / "projections-blend-tonight.csv"


def safe_float(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


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


def is_pitcher(pos: str) -> bool:
    p = (pos or "").upper().strip()
    if not p:
        return False
    if p in ("P", "SP", "RP"):
        return True
    parts = re.split(r"[/,]", p)
    return any(x.strip() in ("P", "SP", "RP") for x in parts) and not any(
        x.strip() in ("C", "1B", "2B", "3B", "SS", "OF", "DH") for x in parts
    )


def load_projections(path: Path, prefer_col: str | None = None) -> dict[str, dict]:
    """dk_id -> proj row. Prefer prefer_col, else savant_proj, blend_proj, proj_fp."""
    out: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        fields = reader.fieldnames or []
        proj_col = None
        candidates = []
        if prefer_col:
            candidates.append(prefer_col)
        candidates.extend(["savant_proj", "blend_proj", "proj_fp"])
        for cand in candidates:
            if cand in fields:
                proj_col = cand
                break
        if proj_col is None:
            for c in fields:
                if "proj" in c.lower():
                    proj_col = c
                    break
        if proj_col is None:
            raise ValueError(f"No projection column in {path}: {fields}")
        for row in reader:
            dk_id = str(row.get("dk_id") or row.get("ID") or "").strip()
            proj = safe_float(row.get(proj_col))
            name = (row.get("name") or "").strip()
            if proj is None:
                continue
            if not dk_id and not name:
                continue
            key = dk_id or f"name:{norm_name(name)}"
            out[key] = {
                "dk_id": dk_id,
                "name": name,
                "name_norm": norm_name(name),
                "team": (row.get("team") or "").strip(),
                "pos": (row.get("pos") or row.get("position") or "").strip(),
                "salary": safe_float(row.get("salary")),
                "blend_proj": proj,
                "proj_col": proj_col,
                "proj_fp": safe_float(row.get("proj_fp")),
                "savant_proj": safe_float(row.get("savant_proj")),
                "raw_blend": safe_float(row.get("blend_proj")),
            }
    return out


def load_actuals(path: Path) -> dict[str, dict]:
    """Return map keyed by dk_id when present, else name:<norm>.

    Values: {dk_id, name, name_norm, actual_fp, position, ownership_pct}
    """
    out: dict[str, dict] = {}
    with path.open(newline="", encoding="utf-8-sig") as f:
        for row in csv.DictReader(f):
            dk_id = str(row.get("dk_id") or row.get("ID") or "").strip()
            name = (row.get("name") or row.get("Player") or "").strip()
            val = safe_float(row.get("actual_fp"))
            if val is None:
                for k, v in row.items():
                    if k and ("actual" in k.lower() or k.lower() in ("fp", "fpts")):
                        val = safe_float(v)
                        if val is not None:
                            break
            if val is None:
                continue
            if not dk_id and not name:
                continue
            key = dk_id or f"name:{norm_name(name)}"
            out[key] = {
                "dk_id": dk_id,
                "name": name,
                "name_norm": norm_name(name),
                "actual_fp": val,
                "position": (row.get("position") or row.get("pos") or row.get("Roster Position") or "").strip(),
                "ownership_pct": safe_float(row.get("ownership_pct") or row.get("%Drafted")),
            }
    return out


def index_by_name(rows: dict[str, dict]) -> dict[str, dict]:
    by_name: dict[str, dict] = {}
    for r in rows.values():
        nn = r.get("name_norm") or norm_name(r.get("name") or "")
        if nn and nn not in by_name:
            by_name[nn] = r
    return by_name


def join_pairs(
    projs: dict[str, dict], acts: dict[str, dict]
) -> list[dict]:
    """Join on dk_id first, then normalized name. Return list of joined dicts."""
    proj_by_name = index_by_name(projs)
    used_proj = set()
    joined: list[dict] = []
    for key, a in acts.items():
        p = None
        if a["dk_id"] and a["dk_id"] in projs:
            p = projs[a["dk_id"]]
        elif a["name_norm"] and a["name_norm"] in proj_by_name:
            p = proj_by_name[a["name_norm"]]
        if p is None:
            continue
        pk = p["dk_id"] or f"name:{p['name_norm']}"
        if pk in used_proj:
            continue
        used_proj.add(pk)
        pos = p.get("pos") or a.get("position") or ""
        joined.append(
            {
                "dk_id": p.get("dk_id") or a.get("dk_id") or "",
                "name": p.get("name") or a.get("name") or "",
                "team": p.get("team") or "",
                "pos": pos,
                "salary": p.get("salary"),
                "proj": p["blend_proj"],
                "actual": a["actual_fp"],
                "is_pitcher": is_pitcher(pos),
                "ownership_pct": a.get("ownership_pct"),
            }
        )
    return joined


def mae(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return float("nan")
    return sum(abs(a - p) for p, a in pairs) / len(pairs)


def rmse(pairs: list[tuple[float, float]]) -> float:
    if not pairs:
        return float("nan")
    return math.sqrt(sum((a - p) ** 2 for p, a in pairs) / len(pairs))


def rankdata(vals: list[float]) -> list[float]:
    """Average ranks for ties (1-based)."""
    n = len(vals)
    order = sorted(range(n), key=lambda i: vals[i])
    ranks = [0.0] * n
    i = 0
    while i < n:
        j = i
        while j + 1 < n and vals[order[j + 1]] == vals[order[i]]:
            j += 1
        avg = (i + j) / 2.0 + 1.0
        for k in range(i, j + 1):
            ranks[order[k]] = avg
        i = j + 1
    return ranks


def spearman(pairs: list[tuple[float, float]]) -> float:
    if len(pairs) < 2:
        return float("nan")
    px = [p for p, _ in pairs]
    ax = [a for _, a in pairs]
    rx, ra = rankdata(px), rankdata(ax)
    n = len(pairs)
    mx, ma = sum(rx) / n, sum(ra) / n
    num = sum((x - mx) * (y - ma) for x, y in zip(rx, ra))
    denx = math.sqrt(sum((x - mx) ** 2 for x in rx))
    deny = math.sqrt(sum((y - ma) ** 2 for y in ra))
    if denx == 0 or deny == 0:
        return float("nan")
    return num / (denx * deny)


def top_pct_overlap(pairs: list[tuple[float, float]], pct: float = 0.2) -> float:
    """Fraction of proj-top-pct that also land in actual-top-pct."""
    if not pairs:
        return float("nan")
    n = len(pairs)
    k = max(1, int(round(n * pct)))
    proj_idx = sorted(range(n), key=lambda i: pairs[i][0], reverse=True)[:k]
    act_idx = sorted(range(n), key=lambda i: pairs[i][1], reverse=True)[:k]
    return len(set(proj_idx) & set(act_idx)) / k


def compute_metrics(pairs: list[tuple[float, float]]) -> dict:
    return {
        "n": len(pairs),
        "mae": mae(pairs),
        "rmse": rmse(pairs),
        "spearman": spearman(pairs),
        "top20_overlap": top_pct_overlap(pairs, 0.2),
    }


def fmt(v: float, digits: int = 4) -> str:
    if v != v:  # nan
        return "n/a"
    return f"{v:.{digits}f}"


def format_report(
    title: str,
    overall: dict,
    hitters: dict,
    pitchers: dict,
    extra_lines: list[str] | None = None,
    proj_col: str = "blend_proj",
) -> str:
    lines = [title, "=" * len(title)]
    lines.append(f"proj_column:     {proj_col}")
    lines.append("")
    lines.append("--- Overall ---")
    lines.append(f"n_matched:       {overall['n']}")
    lines.append(f"MAE:             {fmt(overall['mae'])}")
    lines.append(f"RMSE:            {fmt(overall['rmse'])}")
    lines.append(f"Spearman:        {fmt(overall['spearman'])}")
    lines.append(f"Top-20% overlap: {fmt(overall['top20_overlap'])}")
    lines.append("")
    lines.append("--- Hitters ---")
    lines.append(f"n_matched:       {hitters['n']}")
    lines.append(f"MAE:             {fmt(hitters['mae'])}")
    lines.append(f"RMSE:            {fmt(hitters['rmse'])}")
    lines.append(f"Spearman:        {fmt(hitters['spearman'])}")
    lines.append(f"Top-20% overlap: {fmt(hitters['top20_overlap'])}")
    lines.append("")
    lines.append("--- Pitchers ---")
    lines.append(f"n_matched:       {pitchers['n']}")
    lines.append(f"MAE:             {fmt(pitchers['mae'])}")
    lines.append(f"RMSE:            {fmt(pitchers['rmse'])}")
    lines.append(f"Spearman:        {fmt(pitchers['spearman'])}")
    lines.append(f"Top-20% overlap: {fmt(pitchers['top20_overlap'])}")
    if extra_lines:
        lines.append("")
        lines.extend(extra_lines)
    return "\n".join(lines) + "\n"


def bias_flags(joined: list[dict]) -> list[str]:
    """Detect systematic biases from joined rows (evidence-based)."""
    lines = ["--- Bias flags (descriptive) ---"]
    hitters = [j for j in joined if not j["is_pitcher"]]
    pitchers = [j for j in joined if j["is_pitcher"]]

    # Low-salary hitter overprojection: salary < 4000, mean (proj - actual)
    low = [j for j in hitters if j["salary"] is not None and j["salary"] < 4000]
    mid = [j for j in hitters if j["salary"] is not None and 4000 <= j["salary"] < 5000]
    high = [j for j in hitters if j["salary"] is not None and j["salary"] >= 5000]
    for label, group in (("low-sal (<4k)", low), ("mid-sal (4–5k)", mid), ("high-sal (≥5k)", high)):
        if len(group) < 5:
            continue
        bias = sum(j["proj"] - j["actual"] for j in group) / len(group)
        lines.append(
            f"hitter {label}: n={len(group)} mean(proj-actual)={bias:+.3f} "
            f"{'(OVER-proj)' if bias > 1.0 else '(UNDER-proj)' if bias < -1.0 else '(near-neutral)'}"
        )

    # OF smash underproj: OF with actual >= 20
    of_smash = [
        j
        for j in hitters
        if "OF" in (j["pos"] or "").upper() and j["actual"] >= 20
    ]
    if of_smash:
        bias = sum(j["proj"] - j["actual"] for j in of_smash) / len(of_smash)
        names = ", ".join(
            f"{j['name']}(proj={j['proj']:.1f},act={j['actual']:.0f})"
            for j in sorted(of_smash, key=lambda x: -x["actual"])[:8]
        )
        lines.append(
            f"OF smash (actual≥20): n={len(of_smash)} mean(proj-actual)={bias:+.3f} "
            f"{'(UNDER-proj)' if bias < -1 else ''}"
        )
        lines.append(f"  examples: {names}")

    # Pitcher mean bias
    if pitchers:
        bias = sum(j["proj"] - j["actual"] for j in pitchers) / len(pitchers)
        lines.append(f"pitchers overall: n={len(pitchers)} mean(proj-actual)={bias:+.3f}")

    return lines


def run_folder(
    folder: Path,
    out: Path | None = None,
    proj_col: str | None = None,
) -> int:
    if not folder.exists():
        print(f"ERROR: backtest folder missing: {folder}", file=sys.stderr)
        print("Expected projections.csv + actuals.csv.", file=sys.stderr)
        return 1
    proj_path = folder / "projections.csv"
    act_path = folder / "actuals.csv"
    if not proj_path.exists() or not act_path.exists():
        print(f"ERROR: {folder} missing projections.csv and/or actuals.csv", file=sys.stderr)
        return 1
    try:
        projs = load_projections(proj_path, prefer_col=proj_col)
        acts = load_actuals(act_path)
    except ValueError as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1

    joined = join_pairs(projs, acts)
    if not joined:
        print("ERROR: no joinable proj/actual rows (dk_id or name)", file=sys.stderr)
        return 1

    used_col = next(iter(projs.values()))["proj_col"] if projs else (proj_col or "?")

    all_pairs = [(j["proj"], j["actual"]) for j in joined]
    hit_pairs = [(j["proj"], j["actual"]) for j in joined if not j["is_pitcher"]]
    pit_pairs = [(j["proj"], j["actual"]) for j in joined if j["is_pitcher"]]

    overall = compute_metrics(all_pairs)
    hitters = compute_metrics(hit_pairs)
    pitchers = compute_metrics(pit_pairs)
    extras = [f"folder: {folder}", f"join: dk_id then normalized name"]
    extras.extend(bias_flags(joined))

    report = format_report(
        f"MLB DFS backtest — {folder.name}",
        overall,
        hitters,
        pitchers,
        extras,
        proj_col=used_col,
    )
    out_path = out or (folder / "calibration-metrics.txt")
    out_path.write_text(report, encoding="utf-8")
    print(report)
    print(f"Wrote {out_path}")
    return 0


def invent_demo_actuals(
    blend: Path, seed: int = 42, sample_n: int = 80
) -> tuple[Path, dict]:
    """Build a tiny backtest folder from tonight's blend + gaussian noise."""
    rng = random.Random(seed)
    projs = load_projections(blend)
    ids = list(projs.keys())
    if not ids:
        raise ValueError(f"No usable rows in {blend}")
    rng.shuffle(ids)
    ids = ids[: min(sample_n, len(ids))]
    demo = BACKTESTS / "demo"
    demo.mkdir(parents=True, exist_ok=True)
    with (demo / "projections.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dk_id", "name", "team", "blend_proj"])
        w.writeheader()
        for dk_id in ids:
            r = projs[dk_id]
            w.writerow(
                {
                    "dk_id": r["dk_id"] or dk_id,
                    "name": r["name"],
                    "team": r["team"],
                    "blend_proj": r["blend_proj"],
                }
            )
    with (demo / "actuals.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["dk_id", "actual_fp"])
        w.writeheader()
        for dk_id in ids:
            p = projs[dk_id]["blend_proj"]
            noise = rng.gauss(0, max(2.0, abs(p) * 0.25))
            w.writerow(
                {
                    "dk_id": projs[dk_id]["dk_id"] or dk_id,
                    "actual_fp": f"{p + noise:.3f}",
                }
            )
    return demo, {"seed": seed, "sample_n": len(ids), "blend": str(blend)}


def main() -> int:
    ap = argparse.ArgumentParser(description="MLB DFS projection backtest")
    ap.add_argument("--date", type=str, default=None, help="YYYY-MM-DD folder under lab/backtests/")
    ap.add_argument("--folder", type=Path, default=None, help="Explicit backtest folder")
    ap.add_argument("--demo", action="store_true", help="Synthetic demo from tonight's blend")
    ap.add_argument("--blend", type=Path, default=DEFAULT_BLEND)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--sample-n", type=int, default=80)
    ap.add_argument("--out", type=Path, default=None)
    ap.add_argument(
        "--proj-col",
        type=str,
        default=None,
        help="Projection column to score (default: savant_proj > blend_proj > proj_fp)",
    )
    args = ap.parse_args()

    if args.demo:
        if not args.blend.exists():
            print(f"ERROR: blend missing for demo: {args.blend}", file=sys.stderr)
            return 1
        print(f"Demo mode: inventing actuals from {args.blend}")
        demo, meta = invent_demo_actuals(args.blend, seed=args.seed, sample_n=args.sample_n)
        projs = load_projections(demo / "projections.csv")
        acts = load_actuals(demo / "actuals.csv")
        joined = join_pairs(projs, acts)
        pairs = [(j["proj"], j["actual"]) for j in joined]
        metrics = compute_metrics(pairs)
        report = format_report(
            "MLB DFS backtest DEMO results",
            metrics,
            compute_metrics([]),
            compute_metrics([]),
            [
                f"source_blend: {meta['blend']}",
                f"demo_folder:  {demo}",
                f"seed:         {meta['seed']}",
                f"sample_n:     {meta['sample_n']}",
                "note: actuals are synthetic (proj + noise); not real slate results.",
            ],
            proj_col="blend_proj",
        )
        out_path = args.out or (BACKTESTS / "demo-results.txt")
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(report, encoding="utf-8")
        print(report)
        print(f"Wrote {out_path}")
        return 0

    folder = args.folder
    if folder is None and args.date:
        folder = BACKTESTS / args.date
    if folder is None:
        feat = LAB / "features-savant-tonight.csv"
        if feat.exists():
            with feat.open(newline="", encoding="utf-8") as f:
                rows = list(csv.DictReader(f))
            matched = sum(
                1
                for r in rows
                if r.get("match_kind", r.get("match", "")) not in ("", "unmatched")
            )
            print("backtest v1: no --demo/--date; Savant features smoke check")
            print(f"  {feat}: rows={len(rows)} matched≈{matched}")
            print("  Use --demo or --date YYYY-MM-DD for projection metrics.")
            return 0
        ap.print_help()
        return 1

    return run_folder(folder, args.out, proj_col=args.proj_col)


if __name__ == "__main__":
    raise SystemExit(main())
