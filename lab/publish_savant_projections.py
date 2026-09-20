#!/usr/bin/env python3
"""Publish Savant-uplifted projections as tonight's production files.

Reads:
  - projections-tonight.csv (own-model schema) → backup if needed
  - projections-blend-tonight.csv → backup if needed
  - projections-savant-tonight.csv (savant_proj)

Writes:
  - projections-tonight.csv          (own schema, proj_fp = savant_proj)
  - projections-blend-tonight.csv    (blend_proj = savant_proj, value recomputed)
  - projections-tonight-summary.txt
  - PRODUCTION-PROJECTIONS.md

Does NOT touch lineups-50*, build_lineups_50.py, or build_projections.py.
"""

from __future__ import annotations

import csv
import shutil
from datetime import datetime, timezone
from pathlib import Path

DESK = Path("/home/box/mlb-dfs")
LAB = DESK / "lab"

OWN_PROD = DESK / "projections-tonight.csv"
OWN_BACKUP = DESK / "projections-tonight-own-backup.csv"
BLEND = DESK / "projections-blend-tonight.csv"
BLEND_BACKUP = DESK / "projections-blend-tonight-pre-savant.csv"
SAVANT = DESK / "projections-savant-tonight.csv"
SUMMARY = DESK / "projections-tonight-summary.txt"
SUMMARY_BACKUP = DESK / "projections-tonight-summary-pre-savant.txt"
PROD_MD = DESK / "PRODUCTION-PROJECTIONS.md"

OWN_FIELDS = [
    "dk_id",
    "name",
    "position",
    "team",
    "salary",
    "game_info",
    "proj_fp",
    "volatility",
    "sources",
    "notes",
]


def _f(x, default=0.0) -> float:
    try:
        if x is None or x == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _read_csv(path: Path) -> list[dict]:
    with path.open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _write_csv(path: Path, fields: list[str], rows: list[dict]) -> None:
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: r.get(k, "") for k in fields})


def backup_if_missing(src: Path, dst: Path) -> str:
    if not src.exists():
        return f"SKIP (missing source): {src}"
    if dst.exists():
        return f"EXISTS (kept): {dst}"
    shutil.copy2(src, dst)
    return f"CREATED: {dst}"


def main() -> None:
    status = []

    # 1) Backups
    status.append(backup_if_missing(OWN_PROD, OWN_BACKUP))
    status.append(backup_if_missing(BLEND, BLEND_BACKUP))
    if SUMMARY.exists():
        status.append(backup_if_missing(SUMMARY, SUMMARY_BACKUP))
    else:
        status.append(f"SKIP (no summary yet): {SUMMARY}")

    if not OWN_BACKUP.exists():
        raise SystemExit(f"Own backup missing and could not be created: {OWN_BACKUP}")
    if not SAVANT.exists():
        raise SystemExit(f"Savant file missing: {SAVANT}")
    if not BLEND_BACKUP.exists() and not BLEND.exists():
        raise SystemExit("Blend file/backup missing")

    own_rows = _read_csv(OWN_BACKUP)
    savant_rows = _read_csv(SAVANT)
    # Prefer pre-savant blend for sources/notes if available; else current blend
    blend_src = BLEND_BACKUP if BLEND_BACKUP.exists() else BLEND
    blend_rows = _read_csv(blend_src)

    own_by_id = {r["dk_id"]: r for r in own_rows}
    savant_by_id = {r["dk_id"]: r for r in savant_rows}
    blend_by_id = {r["dk_id"]: r for r in blend_rows}

    # Coverage: all dk_ids from savant (pool)
    ids = list(savant_by_id.keys())
    if len(ids) != 1115:
        # still proceed but note
        status.append(f"NOTE: savant rows={len(ids)} (expected 1115)")

    # 2) New production projections-tonight.csv
    new_own: list[dict] = []
    missing_own_meta = 0
    for dk_id in ids:
        s = savant_by_id[dk_id]
        o = own_by_id.get(dk_id)
        b = blend_by_id.get(dk_id, {})
        savant_proj = _f(s.get("savant_proj"))
        savant_adj = _f(s.get("savant_adj"))
        proj_fp = round(savant_proj, 1)

        if o:
            position = o.get("position", "")
            game_info = o.get("game_info", "")
            volatility = o.get("volatility", "")
            prior_notes = o.get("notes", "") or ""
            prior_sources = o.get("sources", "") or ""
            name = o.get("name") or s.get("name", "")
            team = o.get("team") or s.get("team", "")
            salary = o.get("salary") or s.get("salary", "")
        else:
            missing_own_meta += 1
            position = ""
            game_info = ""
            volatility = ""
            prior_notes = (b.get("notes") or "") if b else ""
            prior_sources = (b.get("sources") or "") if b else "blend"
            name = s.get("name", "")
            team = s.get("team", "")
            salary = s.get("salary", "")

        # sources
        if "savant" in prior_sources.lower():
            sources = prior_sources
        elif prior_sources:
            sources = f"{prior_sources};savant-uplift"
        else:
            sources = "savant-uplift+blend"

        # Prefer a clean production tag
        sources = "savant-uplift+blend"

        adj_tag = f"savant_adj={savant_adj:+.4f};"
        if prior_notes.startswith("savant_adj="):
            # strip previous adj tag
            rest = prior_notes.split(";", 1)
            prior_notes = rest[1] if len(rest) > 1 else ""
        notes = adj_tag + (prior_notes if prior_notes else "")

        new_own.append(
            {
                "dk_id": dk_id,
                "name": name,
                "position": position,
                "team": team,
                "salary": salary,
                "game_info": game_info,
                "proj_fp": f"{proj_fp:.1f}",
                "volatility": volatility,
                "sources": sources,
                "notes": notes,
            }
        )

    new_own.sort(key=lambda r: (-_f(r["proj_fp"]), r["name"]))
    _write_csv(OWN_PROD, OWN_FIELDS, new_own)
    status.append(f"WROTE {OWN_PROD} rows={len(new_own)} missing_own_meta={missing_own_meta}")

    # 3) Update blend: blend_proj = savant_proj, recompute value, append sources
    blend_fields = list(blend_rows[0].keys()) if blend_rows else [
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
    new_blend: list[dict] = []
    for row in blend_rows:
        dk_id = row["dk_id"]
        s = savant_by_id.get(dk_id)
        out = dict(row)
        if s:
            savant_proj = _f(s.get("savant_proj"))
            salary = _f(out.get("salary") or s.get("salary"))
            out["blend_proj"] = f"{savant_proj:.4f}".rstrip("0").rstrip(".") if False else f"{savant_proj:.4f}"
            # keep similar precision style; use 4 decimals like savant file
            out["blend_proj"] = f"{savant_proj:.4f}"
            value = savant_proj / (salary / 1000.0) if salary else 0.0
            # original blend used ~3 decimals often; keep 4 for consistency with savant value col
            out["value"] = f"{value:.4f}".rstrip("0").rstrip(".")
            # nicer: match prior blend style (~3 decimals) but 4 is fine
            out["value"] = f"{value:.4f}"
            src = out.get("sources") or ""
            if "savant" not in src.lower():
                out["sources"] = (src + "+savant") if src else "savant"
            # prepend note tag
            adj = _f(s.get("savant_adj"))
            prior_n = out.get("notes") or ""
            if prior_n.startswith("savant_adj="):
                rest = prior_n.split(";", 1)
                prior_n = rest[1] if len(rest) > 1 else ""
            out["notes"] = f"savant_adj={adj:+.4f};" + prior_n
        new_blend.append(out)

    # Also include any savant ids missing from blend (should be none)
    for dk_id in ids:
        if dk_id not in blend_by_id:
            s = savant_by_id[dk_id]
            savant_proj = _f(s.get("savant_proj"))
            salary = _f(s.get("salary"))
            value = savant_proj / (salary / 1000.0) if salary else 0.0
            new_blend.append(
                {
                    "dk_id": dk_id,
                    "name": s.get("name", ""),
                    "team": s.get("team", ""),
                    "salary": s.get("salary", ""),
                    "own_proj": "",
                    "dff_proj": "",
                    "blend_proj": f"{savant_proj:.4f}",
                    "value": f"{value:.4f}",
                    "sources": "savant",
                    "notes": f"savant_adj={_f(s.get('savant_adj')):+.4f};",
                }
            )

    new_blend.sort(key=lambda r: (-_f(r.get("blend_proj")), r.get("name", "")))
    _write_csv(BLEND, blend_fields, new_blend)
    status.append(f"WROTE {BLEND} rows={len(new_blend)}")

    # 4) Summary
    projs = [_f(r["proj_fp"]) for r in new_own]
    mean_proj = sum(projs) / len(projs) if projs else 0.0
    top10 = new_own[:10]
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    lines = []
    lines.append("DK MLB Classic Projections — PRODUCTION (Savant uplift)")
    lines.append("=" * 50)
    lines.append(f"Updated: {now}")
    lines.append("Active: Savant uplift → projections-tonight.csv (proj_fp = savant_proj)")
    lines.append("Pipeline: blend → lab/project_with_savant.py → lab/publish_savant_projections.py")
    lines.append(f"Backup own-model: {OWN_BACKUP}")
    lines.append(f"Backup blend:     {BLEND_BACKUP}")
    if SUMMARY_BACKUP.exists():
        lines.append(f"Backup summary:   {SUMMARY_BACKUP}")
    lines.append("")
    lines.append(f"Coverage: {len(new_own)} players (dk_ids from savant/pool)")
    lines.append(f"Mean proj_fp: {mean_proj:.3f}")
    lines.append("")
    lines.append("Top 10 by proj_fp:")
    for i, r in enumerate(top10, 1):
        lines.append(
            f"  {i:2d}. {r['name']:<22} {r['position']:<4} {r['team']:<3} "
            f"${r['salary']:<5}  {r['proj_fp']:>5}  [{r['sources']}]"
        )
    lines.append("")
    lines.append("Notes: lineups-50 NOT auto-rebuilt; Builder must rebuild.")
    lines.append("Do not modify lineups-50 / build_lineups_50.py / build_projections.py via this publish.")
    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")
    status.append(f"WROTE {SUMMARY}")

    # 5) PRODUCTION-PROJECTIONS.md
    md = f"""# Production Projections (Tonight)

**Active:** Savant uplift → `projections-tonight.csv` (`proj_fp` = `savant_proj`)

**As of:** {now}

## Source pipeline

1. Own / DFF blend → `projections-blend-tonight.csv` (pre-publish backup kept)
2. `lab/project_with_savant.py` → `projections-savant-tonight.csv`
3. `lab/publish_savant_projections.py` → publishes Savant into production + blend

## Files

| Role | Path |
|------|------|
| **Production** | `projections-tonight.csv` |
| Blend (lab/sim default) | `projections-blend-tonight.csv` (`blend_proj` = savant) |
| Savant intermediate | `projections-savant-tonight.csv` |
| Own-model backup | `projections-tonight-own-backup.csv` |
| Blend pre-Savant backup | `projections-blend-tonight-pre-savant.csv` |
| Summary | `projections-tonight-summary.txt` |

## Lineups

**`lineups-50-tonight.csv` / `lineups-50-tonight-fixed.csv` are NOT auto-rebuilt.**

Builder must rebuild lineups from the new production projections when ready.

`build_lineups_50.py` and `build_projections.py` are untouched by this publish step.

## Republish

```bash
/home/box/mlb-dfs/.venv/bin/python /home/box/mlb-dfs/lab/publish_savant_projections.py
```

Backups are created only if missing (safe to re-run).
"""
    PROD_MD.write_text(md, encoding="utf-8")
    status.append(f"WROTE {PROD_MD}")

    print("publish_savant_projections — done")
    for s in status:
        print(" ", s)
    print(f" top1: {new_own[0]['name']} {new_own[0]['proj_fp']}")
    print(f" rows own={len(new_own)} blend={len(new_blend)} savant={len(savant_rows)}")


if __name__ == "__main__":
    main()
