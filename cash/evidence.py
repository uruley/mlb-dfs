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
VALID_ELIG = {"SP", "RP", "P"}


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
    elig = str(rec.get("dk_eligibility") or "").upper()
    if elig and not any(tok in VALID_ELIG for tok in elig.replace("/", " ").split()):
        errs.append(f"bad_dk_eligibility:{elig}")
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
    seen = set()
    for r in rows:
        rec = dict(r)
        rec["_meta"] = meta
        errs = validate_pitcher_record(rec)
        key = (
            str(rec.get("slate_date")),
            str(rec.get("slate_id")),
            str(rec.get("game_id")),
            str(rec.get("mlb_id")),
            str(rec.get("dk_id")),
        )
        if key in seen:
            errs.append("duplicate_identity")
        seen.add(key)
        rec["_schema_errors"] = errs
        out.append(rec)
    return out


def index_evidence(rows: list[dict], *, slate_id: str, slate_date: str) -> dict[str, dict]:
    """Index only schema-valid rows whose slate matches the request.

    Composite key required. DK ID alone is not identity.
    """
    idx: dict[str, dict] = {}
    for r in rows:
        if r.get("_schema_errors"):
            continue
        if str(r.get("slate_id")) != str(slate_id):
            continue
        if str(r.get("slate_date")) != str(slate_date):
            continue
        dk = str(r.get("dk_id"))
        mlb = str(r.get("mlb_id"))
        game = str(r.get("game_id"))
        idx[f"{slate_date}|{slate_id}|{game}|{mlb}|{dk}"] = r
    return idx


def lookup_evidence(
    idx: dict[str, dict],
    *,
    slate_date: str,
    slate_id: str,
    game_id: str,
    mlb_id: str,
    dk_id: str,
) -> dict | None:
    if not (slate_date and slate_id and game_id and mlb_id and dk_id):
        return None
    return idx.get(f"{slate_date}|{slate_id}|{game_id}|{mlb_id}|{dk_id}")


def schema_errors(rows: list[dict]) -> list[str]:
    out = []
    for r in rows:
        for e in r.get("_schema_errors") or []:
            out.append(f"{r.get('dk_id')}:{e}")
    return out
