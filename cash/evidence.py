"""Pitcher-evidence schema load/validate. Keyed by mlb_id + game_id + dk_id."""

from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path
from typing import Any

REQUIRED = (
    "slate_date",
    "slate_id",
    "game_id",
    "mlb_id",
    "dk_id",
    "dk_eligibility",
    "role",
    "announced_starter",
)


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()
    h.update(Path(path).read_bytes())
    return h.hexdigest()


def dumps_stable(obj: Any) -> str:
    return json.dumps(obj, sort_keys=True, default=str, separators=(",", ":"))


def hash_obj(obj: Any) -> str:
    return hashlib.sha256(dumps_stable(obj).encode()).hexdigest()


def load_json(path: Path) -> Any:
    return json.loads(Path(path).read_text())


def load_csv(path: Path) -> list[dict[str, str]]:
    with Path(path).open(newline="", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def validate_pitcher_record(rec: dict) -> list[str]:
    errs = []
    for k in REQUIRED:
        if rec.get(k) in (None, ""):
            errs.append(f"missing:{k}")
    role = str(rec.get("role") or "").lower()
    if role and role not in ("starter", "opener", "bulk", "relief", "unknown"):
        errs.append(f"bad_role:{role}")
    return errs


def load_pitcher_evidence(path: Path) -> list[dict]:
    data = load_json(path)
    if isinstance(data, dict) and "pitchers" in data:
        rows = data["pitchers"]
        meta = {k: v for k, v in data.items() if k != "pitchers"}
    elif isinstance(data, list):
        rows = data
        meta = {}
    else:
        raise ValueError("pitcher evidence must be a list or {pitchers: []}")
    out = []
    for r in rows:
        rec = dict(r)
        rec["_meta"] = meta
        errs = validate_pitcher_record(rec)
        rec["_schema_errors"] = errs
        out.append(rec)
    return out


def index_evidence(rows: list[dict]) -> dict[str, dict]:
    idx = {}
    for r in rows:
        idx[str(r.get("dk_id"))] = r
        idx[f"{r.get('mlb_id')}:{r.get('game_id')}"] = r
    return idx
