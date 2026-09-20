#!/usr/bin/env python3
"""One cash-build command. Frozen inputs only. No live collection."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cash.builder import build_one_lineup, load_players
from cash.entries import parse_user_entries, write_entries_upload
from cash.evidence import file_sha256, hash_obj, load_csv, load_json, load_pitcher_evidence
from cash.validate import check_freshness, validate_delivery


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Reproducible cash lineup from frozen inputs")
    p.add_argument("--slate-date", required=True, help="YYYY-MM-DD")
    p.add_argument("--slate-id", required=True)
    p.add_argument("--pool", required=True, type=Path)
    p.add_argument("--projections", required=True, type=Path)
    p.add_argument("--pitcher-evidence", required=True, type=Path)
    p.add_argument("--out-dir", required=True, type=Path)
    p.add_argument("--entries", type=Path, help="user DraftKings export (optional)")
    p.add_argument("--decision-time", help="ISO timestamp for historical freshness")
    p.add_argument("--max-age-hours", type=float, default=6.0)
    p.add_argument("--expected-projection-hash", default=None)
    p.add_argument("--contest-meta", type=Path, default=None)
    p.add_argument("--code-version", default="task-001")
    args = p.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)

    pool = load_csv(args.pool)
    projs = load_csv(args.projections)
    evidence = load_pitcher_evidence(args.pitcher_evidence)
    ev_raw = load_json(args.pitcher_evidence)
    as_of = None
    retrieved = None
    if isinstance(ev_raw, dict):
        as_of = ev_raw.get("information_as_of") or ev_raw.get("as_of")
        retrieved = ev_raw.get("retrieved_at") or ev_raw.get("evidence_retrieval_time")

    hashes = {
        "pool": file_sha256(args.pool),
        "projections": file_sha256(args.projections),
        "pitcher_evidence": file_sha256(args.pitcher_evidence),
    }

    players = load_players(pool, projs, evidence, require_posted_hitters=True)
    lineup = build_one_lineup(players)
    freshness = check_freshness(
        as_of=as_of,
        retrieved_at=retrieved,
        decision_time=args.decision_time,
        max_age_hours=args.max_age_hours,
    )
    contest = load_json(args.contest_meta) if args.contest_meta else {"status": "missing"}
    report = validate_delivery(
        lineup=lineup,
        players=players,
        slate_id=args.slate_id,
        projection_hash=hashes["projections"],
        gate_hash=hashes["projections"],
        expected_projection_hash=args.expected_projection_hash,
        expected_slate_id=args.slate_id,
        freshness=freshness,
        contest_meta=contest,
    )

    status = "ready_for_upload" if report["ready_for_upload"] else "draft_blocked"
    artifact = {
        "task": "001",
        "status": status,
        "slate_date": args.slate_date,
        "slate_id": args.slate_id,
        "code_version": args.code_version,
        "input_hashes": hashes,
        "freshness": freshness,
        "validation": report,
        "lineup": lineup,
        "written_at": datetime.now(timezone.utc).isoformat(),
    }

    manifest = {
        "input_hashes": hashes,
        "code_version": args.code_version,
        "slate_date": args.slate_date,
        "slate_id": args.slate_id,
        "source_timestamps": {"as_of": as_of, "retrieved_at": retrieved},
        "validation": report,
        "output_hashes": {},
        "status": status,
    }

    draft_path = out / "lineup-1-cash.draft.json"
    atomic_write(draft_path, json.dumps(artifact, indent=2, default=str) + "\n")
    manifest["output_hashes"]["draft"] = file_sha256(draft_path)

    ready_path = out / "lineup-1-cash.ready.json"
    if report["ready_for_upload"]:
        atomic_write(ready_path, json.dumps(artifact, indent=2, default=str) + "\n")
        manifest["output_hashes"]["ready"] = file_sha256(ready_path)
        if args.entries and lineup.get("status") == "ok":
            ids = [r["dk_id"] for r in lineup["lineup"]]
            entries = parse_user_entries(args.entries)
            dest = out / "lineup-1-cash-ENTRIES-UPLOAD.csv"
            n = write_entries_upload(dest, entries, ids)
            manifest["entries_written"] = n
            manifest["output_hashes"]["entries"] = file_sha256(dest)
    else:
        if ready_path.exists():
            manifest["preserved_ready"] = True

    man_path = out / "manifest.json"
    atomic_write(man_path, json.dumps(manifest, indent=2, default=str) + "\n")

    summary = [
        f"cash-build {status} slate={args.slate_date} id={args.slate_id}",
        f"objective={lineup.get('objective')}",
        f"errors={report.get('errors')}",
    ]
    if lineup.get("status") == "ok":
        for r in lineup["lineup"]:
            summary.append(f"  {r['slot']:3} {r['name']} {r['dk_id']} ${r['salary']} proj={r['proj']}")
        summary.append(f"salary={lineup['salary']} proj_sum={lineup['proj_sum']}")
    atomic_write(out / "lineup-1-cash-summary.txt", "\n".join(summary) + "\n")
    print("\n".join(summary))
    return 0 if report["ready_for_upload"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
