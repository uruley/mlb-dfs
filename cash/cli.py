#!/usr/bin/env python3
"""One cash-build command. Frozen inputs only. No live collection."""

from __future__ import annotations

import argparse
import csv
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cash.builder import build_one_lineup, load_players
from cash.entries import apply_lineup_to_entries, parse_user_entries
from cash.evidence import file_sha256, load_csv, load_json, load_pitcher_evidence, schema_errors
from cash.provenance import gate_hash, package_code_hash
from cash.validate import check_freshness, collect_player_freshness, validate_delivery


def atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + f".{os.getpid()}.tmp")
    tmp.write_text(text, encoding="utf-8")
    tmp.replace(path)


class WriteLock:
    def __init__(self, path: Path):
        self.path = path
        self.fd = None

    def __enter__(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        try:
            self.fd = os.open(self.path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError as exc:
            raise RuntimeError("concurrent_writer") from exc
        os.write(self.fd, str(os.getpid()).encode())
        return self

    def __exit__(self, exc_type, exc, tb):
        if self.fd is not None:
            os.close(self.fd)
        try:
            self.path.unlink()
        except FileNotFoundError:
            pass


def _slate_ids(rows: list[dict], fallback: str) -> set[str]:
    vals = {str(r.get("slate_id")) for r in rows if r.get("slate_id")}
    return vals or ({fallback} if fallback else set())


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
    p.add_argument("--expected-gate-hash", default=None)
    p.add_argument("--contest-meta", type=Path, default=None)
    p.add_argument("--contest-id", default=None)
    p.add_argument("--code-version", default=None)
    args = p.parse_args(argv)

    out = args.out_dir
    out.mkdir(parents=True, exist_ok=True)
    run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ") + f"-{os.getpid()}"
    run_dir = out / "runs" / run_id
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        lock = WriteLock(out / ".cash-write.lock")
        lock.__enter__()
    except RuntimeError:
        atomic_write(run_dir / "status.json", json.dumps({"status": "blocked", "errors": ["concurrent_writer"]}) + "\n")
        return 2

    try:
        return _run(args, out, run_dir)
    finally:
        lock.__exit__(None, None, None)


def _run(args, out: Path, run_dir: Path) -> int:
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
    if args.entries:
        hashes["entries"] = file_sha256(args.entries)
    if args.contest_meta:
        hashes["contest_meta"] = file_sha256(args.contest_meta)

    code_hash = package_code_hash()
    ghash = gate_hash({"max_age_hours": args.max_age_hours, "slate_id": args.slate_id})
    code_version = args.code_version or code_hash

    freshness = check_freshness(
        as_of=as_of,
        retrieved_at=retrieved,
        decision_time=args.decision_time,
        max_age_hours=args.max_age_hours,
    )
    player_fresh = collect_player_freshness(
        evidence, decision_time=args.decision_time, max_age_hours=args.max_age_hours
    )
    players = load_players(
        pool,
        projs,
        evidence,
        require_posted_hitters=True,
        slate_id=args.slate_id,
        slate_date=args.slate_date,
    )
    for pl in players:
        pf = player_fresh.get(pl.dk_id)
        if pl.is_pitcher and pf and not pf.get("ok"):
            pl.exclude_reason = pl.exclude_reason or f"stale:{pf.get('reason')}"
    lineup = build_one_lineup(players)

    contest = load_json(args.contest_meta) if args.contest_meta else {"status": "missing"}
    ev_slates = {str(r.get("slate_id")) for r in evidence if r.get("slate_id")}
    report = validate_delivery(
        lineup=lineup,
        players=players,
        slate_id=args.slate_id,
        slate_date=args.slate_date,
        projection_hash=hashes["projections"],
        gate_hash=ghash,
        expected_projection_hash=args.expected_projection_hash,
        expected_gate_hash=args.expected_gate_hash,
        pool_slate_ids=_slate_ids(pool, args.slate_id),
        proj_slate_ids=_slate_ids(projs, args.slate_id),
        evidence_slate_ids=ev_slates or {args.slate_id},
        freshness=freshness,
        player_freshness=player_fresh,
        contest_meta=contest,
        schema_error_list=schema_errors(evidence),
    )

    entry_errors: list[str] = []
    entry_rows = None
    parsed_entries = None
    if args.entries:
        parsed_entries = parse_user_entries(args.entries)
        if lineup.get("status") == "ok":
            ids = [r["dk_id"] for r in lineup["lineup"]]
            try:
                entry_rows, entry_errors = apply_lineup_to_entries(
                    parsed_entries,
                    ids,
                    slate_id=args.slate_id,
                    contest_id=args.contest_id,
                )
            except ValueError as exc:
                entry_errors.append(str(exc))
        else:
            entry_errors.append("no_lineup_for_entries")
        if parsed_entries.get("errors"):
            entry_errors.extend(parsed_entries["errors"])
        if entry_errors:
            report["errors"] = list(report.get("errors") or []) + [f"entries:{e}" for e in entry_errors]
            report["ready_for_upload"] = False

    status = "ready_for_upload" if report["ready_for_upload"] else "draft_blocked"
    artifact = {
        "task": "001",
        "status": status,
        "slate_date": args.slate_date,
        "slate_id": args.slate_id,
        "code_version": code_version,
        "code_hash": code_hash,
        "gate_hash": ghash,
        "gate_origin": "in_process_cash.validate",
        "input_hashes": hashes,
        "freshness": freshness,
        "validation": report,
        "lineup": lineup,
        "written_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "max_age_hours": args.max_age_hours,
            "decision_time": args.decision_time,
            "require_posted_hitters": True,
        },
    }

    draft_path = run_dir / "lineup-1-cash.draft.json"
    atomic_write(draft_path, json.dumps(artifact, indent=2, default=str) + "\n")

    entries_hash = None
    if report["ready_for_upload"] and entry_rows is not None and parsed_entries is not None:
        dest = run_dir / "lineup-1-cash-ENTRIES-UPLOAD.csv"
        with dest.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(parsed_entries["headers"])
            w.writerows(entry_rows)
        entries_hash = file_sha256(dest)
        artifact["entries_written"] = len(entry_rows)

    if report["ready_for_upload"]:
        ready_path = run_dir / "lineup-1-cash.ready.json"
        atomic_write(ready_path, json.dumps(artifact, indent=2, default=str) + "\n")
        ready_hash = file_sha256(ready_path)
    else:
        ready_hash = None

    manifest = {
        "input_hashes": hashes,
        "code_version": code_version,
        "code_hash": code_hash,
        "gate_hash": ghash,
        "gate_origin": "in_process_cash.validate",
        "slate_date": args.slate_date,
        "slate_id": args.slate_id,
        "source_timestamps": {"as_of": as_of, "retrieved_at": retrieved},
        "decision_time": args.decision_time,
        "validation": report,
        "output_hashes": {
            "draft": file_sha256(draft_path),
            "ready": ready_hash,
            "entries": entries_hash,
        },
        "status": status,
        "run_id": run_dir.name,
    }
    atomic_write(run_dir / "manifest.json", json.dumps(manifest, indent=2, default=str) + "\n")

    summary = [
        f"cash-build {status} slate={args.slate_date} id={args.slate_id}",
        f"objective={lineup.get('objective')} solution={lineup.get('solution_status')}",
        f"errors={report.get('errors')}",
    ]
    if lineup.get("status") == "ok":
        for r in lineup["lineup"]:
            summary.append(f"  {r['slot']:3} {r['name']} {r['dk_id']} ${r['salary']} proj={r['proj']}")
        summary.append(f"salary={lineup['salary']} proj_sum={lineup['proj_sum']}")
    atomic_write(run_dir / "lineup-1-cash-summary.txt", "\n".join(summary) + "\n")

    active = {
        "status": status,
        "run_id": run_dir.name,
        "run_dir": str(run_dir),
        "ready_path": str(run_dir / "lineup-1-cash.ready.json") if report["ready_for_upload"] else None,
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "errors": report.get("errors"),
    }
    atomic_write(out / "status.json", json.dumps(active, indent=2) + "\n")
    atomic_write(out / "manifest.json", json.dumps(manifest, indent=2, default=str) + "\n")
    atomic_write(out / "lineup-1-cash.draft.json", (run_dir / "lineup-1-cash.draft.json").read_text())
    atomic_write(out / "lineup-1-cash-summary.txt", "\n".join(summary) + "\n")
    ready_pub = out / "lineup-1-cash.ready.json"
    if report["ready_for_upload"]:
        atomic_write(ready_pub, (run_dir / "lineup-1-cash.ready.json").read_text())
        if entries_hash:
            atomic_write(
                out / "lineup-1-cash-ENTRIES-UPLOAD.csv",
                (run_dir / "lineup-1-cash-ENTRIES-UPLOAD.csv").read_text(),
            )
    else:
        if ready_pub.exists():
            archive = run_dir / "previous-ready-invalidated.json"
            archive.write_text(ready_pub.read_text(), encoding="utf-8")
            ready_pub.unlink()
        upload = out / "lineup-1-cash-ENTRIES-UPLOAD.csv"
        if upload.exists():
            upload.unlink()

    print("\n".join(summary))
    return 0 if report["ready_for_upload"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
