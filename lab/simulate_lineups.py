#!/usr/bin/env python3
"""Monte Carlo simulation of DK Classic MLB lineups vs each other."""

from __future__ import annotations

import argparse
import csv
import re
import sys
from pathlib import Path

import numpy as np

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"
DEFAULT_LINEUPS = DESK / "lineups-50-tonight.csv"
DEFAULT_BLEND = DESK / "projections-blend-tonight.csv"
DEFAULT_OWN = DESK / "projections-tonight.csv"
DEFAULT_POOL = DESK / "dk-classic-player-pool.csv"
DEFAULT_OUT = LAB / "sim-results-tonight.csv"
DEFAULT_SUMMARY = LAB / "sim-results-tonight-summary.txt"
DEFAULT_N = 5000
DEFAULT_SEED = 42

# "Name (id)" cell pattern
CELL_RE = re.compile(r"^(?P<name>.+?)\s*\((?P<id>\d+)\)\s*$")


def safe_float(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def parse_cell(cell: str) -> tuple[str, str]:
    cell = (cell or "").strip()
    m = CELL_RE.match(cell)
    if not m:
        raise ValueError(f"Bad lineup cell (expected 'Name (id)'): {cell!r}")
    return m.group("name").strip(), m.group("id")


def load_lineups(path: Path) -> list[list[str]]:
    """Return list of lineups; each lineup is list of 10 dk_ids (order = slots)."""
    lineups: list[list[str]] = []
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.reader(f)
        header = next(reader, None)
        if header is None:
            return lineups
        for row in reader:
            if not row or all(not c.strip() for c in row):
                continue
            ids = []
            for cell in row[:10]:
                _name, dk_id = parse_cell(cell)
                ids.append(dk_id)
            if len(ids) != 10:
                raise ValueError(f"Expected 10 players, got {len(ids)}: {row}")
            lineups.append(ids)
    return lineups


def load_projections(
    blend_path: Path, own_path: Path, pool_path: Path
) -> tuple[dict[str, float], dict[str, str]]:
    """dk_id -> proj, dk_id -> position class ('P' or 'H')."""
    proj: dict[str, float] = {}
    pos: dict[str, str] = {}

    # Positions from pool
    if pool_path.exists():
        with pool_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dk_id = str(row.get("ID", "")).strip()
                roster = (row.get("Roster Position") or row.get("Position") or "").upper()
                # Pitchers are P / SP / RP; treat as pitcher if 'P' is the only roster or primary
                if dk_id:
                    if roster in ("P", "SP", "RP") or (
                        "P" in roster.split("/") and "C" not in roster.split("/")
                    ):
                        # DK uses Roster Position like "P" for pitchers; hitters C/1B/...
                        if roster == "P" or roster.startswith("P/") or "/P" in roster:
                            pos[dk_id] = "P"
                        elif roster in ("SP", "RP"):
                            pos[dk_id] = "P"
                        else:
                            pos[dk_id] = "H"
                    else:
                        pos[dk_id] = "H"
                    # Simpler: first Position column
                    primary = (row.get("Position") or "").upper()
                    if primary in ("SP", "RP", "P"):
                        pos[dk_id] = "P"
                    else:
                        pos[dk_id] = "H"

    # Prefer blend_proj; fall back to own_proj from blend file or own file
    if blend_path.exists():
        with blend_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dk_id = str(row.get("dk_id", "")).strip()
                if not dk_id:
                    continue
                bp = safe_float(row.get("blend_proj"))
                op = safe_float(row.get("own_proj"))
                if bp is not None:
                    proj[dk_id] = bp
                elif op is not None:
                    proj[dk_id] = op

    # Fill gaps from own projections
    if own_path.exists():
        with own_path.open(newline="", encoding="utf-8") as f:
            for row in csv.DictReader(f):
                dk_id = str(row.get("dk_id", "")).strip()
                if not dk_id:
                    continue
                if dk_id not in proj:
                    op = safe_float(row.get("proj_fp"))
                    if op is not None:
                        proj[dk_id] = op
                primary = (row.get("position") or "").upper()
                if dk_id not in pos:
                    pos[dk_id] = "P" if primary in ("SP", "RP", "P") else "H"

    return proj, pos


def load_teams(pool_path: Path) -> dict[str, str]:
    """dk_id -> team abbreviation from DK pool."""
    out: dict[str, str] = {}
    if not pool_path.exists():
        return out
    with pool_path.open(newline="", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            dk_id = str(row.get("ID") or row.get("dk_id") or "").strip()
            team = (row.get("TeamAbbrev") or row.get("Team") or row.get("team") or "").strip()
            if dk_id and team:
                out[dk_id] = team
    return out


def sigma_for(proj: float, is_pitcher: bool) -> float:

    if is_pitcher:
        return max(4.0, proj * 0.40)
    return max(3.0, proj * 0.35)


def run_sims(
    lineups: list[list[str]],
    proj: dict[str, float],
    pos: dict[str, str],
    n_sims: int,
    seed: int,
    team_by_id: dict[str, str] | None = None,
    stack_bonus: bool = False,
) -> tuple[np.ndarray, list[str]]:
    """
    Returns scores array shape (n_sims, n_lineups) and list of warning strings.

    stack_bonus: optional (default False) soft additive from lab/stack_rules.py
    so existing MC stays comparable unless explicitly enabled.
    """
    warnings: list[str] = []
    n_lu = len(lineups)
    # Collect unique player ids used
    used: set[str] = set()
    for lu in lineups:
        used.update(lu)

    missing = [pid for pid in used if pid not in proj]
    if missing:
        warnings.append(f"WARNING: {len(missing)} players missing projections; using 0.0")
        for pid in missing[:10]:
            warnings.append(f"  missing proj: {pid}")

    # Precompute mu, sigma per player id
    mus: dict[str, float] = {}
    sigs: dict[str, float] = {}
    for pid in used:
        mu = float(proj.get(pid, 0.0))
        is_p = pos.get(pid, "H") == "P"
        mus[pid] = mu
        sigs[pid] = sigma_for(mu, is_p)

    rng = np.random.default_rng(seed)
    # Sample all player scores once per sim, then sum per lineup (shared player samples
    # across lineups in a given sim — more realistic for field comparison).
    player_ids = sorted(used)
    pid_index = {pid: i for i, pid in enumerate(player_ids)}
    mu_arr = np.array([mus[pid] for pid in player_ids], dtype=np.float64)
    sig_arr = np.array([sigs[pid] for pid in player_ids], dtype=np.float64)

    samples = rng.normal(mu_arr, sig_arr, size=(n_sims, len(player_ids)))
    # Fantasy points floor at 0 is optional; DK can be negative for pitchers rarely —
    # keep raw Normal samples (industry often allows slight negatives).

    scores = np.zeros((n_sims, n_lu), dtype=np.float64)
    for j, lu in enumerate(lineups):
        idx = [pid_index[pid] for pid in lu]
        scores[:, j] = samples[:, idx].sum(axis=1)

    # Optional stack bonus (default off) — see lab/stack_rules.py
    if stack_bonus:
        try:
            from stack_rules import stack_bonus_points, count_team_hitters
        except ImportError:
            from lab.stack_rules import stack_bonus_points, count_team_hitters  # type: ignore
        team_by_id = team_by_id or {}
        for j, lu in enumerate(lineups):
            hitter_teams = [
                team_by_id.get(pid, "")
                for pid in lu
                if pos.get(pid, "H") != "P" and team_by_id.get(pid)
            ]
            bonus = stack_bonus_points(count_team_hitters(hitter_teams), enabled=True)
            if bonus:
                scores[:, j] += bonus
        warnings.append("stack_bonus ENABLED (lab/stack_rules.py); not default MC")

    return scores, warnings


def summarize(scores: np.ndarray) -> list[dict]:
    """Per-lineup stats + win_rate_vs_field (#1 among the N lineups)."""
    n_sims, n_lu = scores.shape
    # Argmax per sim; ties: first max index wins (numpy default) — rare with continuous FP
    winners = np.argmax(scores, axis=1)
    win_counts = np.bincount(winners, minlength=n_lu).astype(np.float64)

    rows = []
    for j in range(n_lu):
        col = scores[:, j]
        rows.append(
            {
                "lineup_idx": j + 1,  # 1-based
                "mean": round(float(np.mean(col)), 3),
                "p50": round(float(np.percentile(col, 50)), 3),
                "p90": round(float(np.percentile(col, 90)), 3),
                "p99": round(float(np.percentile(col, 99)), 3),
                "win_rate_vs_field": round(float(win_counts[j] / n_sims), 6),
            }
        )
    return rows


def write_summary(
    path: Path,
    rows: list[dict],
    n_sims: int,
    n_lu: int,
    warnings: list[str],
    seed: int,
) -> None:
    by_mean = sorted(rows, key=lambda r: (-r["mean"], -r["p90"], r["lineup_idx"]))
    by_p90 = sorted(rows, key=lambda r: (-r["p90"], -r["mean"], r["lineup_idx"]))
    by_win = sorted(rows, key=lambda r: (-r["win_rate_vs_field"], -r["mean"], r["lineup_idx"]))

    lines = []
    lines.append("MLB DFS lab — Monte Carlo lineup simulation")
    lines.append(f"sims={n_sims}  lineups={n_lu}  seed={seed}")
    lines.append("")
    if warnings:
        lines.extend(warnings)
        lines.append("")

    lines.append("Top 5 by mean:")
    for r in by_mean[:5]:
        lines.append(
            f"  LU#{r['lineup_idx']:>2}  mean={r['mean']:.2f}  p50={r['p50']:.2f}  "
            f"p90={r['p90']:.2f}  p99={r['p99']:.2f}  win={r['win_rate_vs_field']:.3%}"
        )
    lines.append("")
    lines.append("Top 5 by p90:")
    for r in by_p90[:5]:
        lines.append(
            f"  LU#{r['lineup_idx']:>2}  p90={r['p90']:.2f}  mean={r['mean']:.2f}  "
            f"p99={r['p99']:.2f}  win={r['win_rate_vs_field']:.3%}"
        )
    lines.append("")
    lines.append("Top 5 by win_rate_vs_field:")
    for r in by_win[:5]:
        lines.append(
            f"  LU#{r['lineup_idx']:>2}  win={r['win_rate_vs_field']:.3%}  mean={r['mean']:.2f}  "
            f"p90={r['p90']:.2f}"
        )
    lines.append("")
    lines.append(f"Full CSV: {DEFAULT_OUT}")

    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(path.read_text(encoding="utf-8"))


def main() -> int:
    ap = argparse.ArgumentParser(description="Monte Carlo sim of DK Classic lineups")
    ap.add_argument("--lineups", type=Path, default=DEFAULT_LINEUPS)
    ap.add_argument("--blend", type=Path, default=DEFAULT_BLEND)
    ap.add_argument("--own", type=Path, default=DEFAULT_OWN)
    ap.add_argument("--pool", type=Path, default=DEFAULT_POOL)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--summary", type=Path, default=DEFAULT_SUMMARY)
    ap.add_argument("-n", "--sims", type=int, default=DEFAULT_N)
    ap.add_argument("--seed", type=int, default=DEFAULT_SEED)
    ap.add_argument(
        "--stack-bonus",
        action="store_true",
        default=False,
        help="Optional soft stack bonus from lab/stack_rules.py (default OFF)",
    )
    args = ap.parse_args()

    if not args.lineups.exists():
        print(f"ERROR: lineups missing: {args.lineups}", file=sys.stderr)
        return 1

    lineups = load_lineups(args.lineups)
    if not lineups:
        print("ERROR: no lineups loaded", file=sys.stderr)
        return 1

    proj, pos = load_projections(args.blend, args.own, args.pool)
    if not proj:
        print("ERROR: no projections loaded (run blend_projections.py first)", file=sys.stderr)
        return 1

    print(f"Loaded {len(lineups)} lineups, {len(proj)} player projections")
    teams = load_teams(args.pool) if args.stack_bonus else {}
    scores, warnings = run_sims(
        lineups, proj, pos, args.sims, args.seed,
        team_by_id=teams, stack_bonus=args.stack_bonus,
    )
    rows = summarize(scores)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    fields = ["lineup_idx", "mean", "p50", "p90", "p99", "win_rate_vs_field"]
    with args.out.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields)
        w.writeheader()
        w.writerows(rows)

    print(f"Wrote {args.out} ({len(rows)} lineups, N={args.sims})")
    write_summary(args.summary, rows, args.sims, len(lineups), warnings, args.seed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
