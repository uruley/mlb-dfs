"""Delivery gates. Fail closed. Never mark ready on unresolved evidence."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from cash.evidence import file_sha256


def parse_iso(ts: str | None) -> datetime | None:
    if not ts:
        return None
    s = str(ts).replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(s)
    except ValueError:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt


def check_freshness(
    *,
    as_of: str | None,
    retrieved_at: str | None,
    decision_time: str | None,
    max_age_hours: float = 6.0,
) -> dict[str, Any]:
    """Freshness vs decision_time (historical replay) not wall clock if provided."""
    ref = parse_iso(decision_time) or datetime.now(timezone.utc)
    src = parse_iso(as_of) or parse_iso(retrieved_at)
    if src is None:
        return {"ok": False, "reason": "missing_source_timestamp", "age_hours": None}
    age = (ref - src).total_seconds() / 3600.0
    if age < 0:
        return {"ok": False, "reason": "source_after_decision_time", "age_hours": age}
    if age > max_age_hours:
        return {"ok": False, "reason": "stale_critical_data", "age_hours": age}
    return {"ok": True, "reason": "fresh", "age_hours": age}


def validate_delivery(
    *,
    lineup: dict,
    players: list,
    slate_id: str,
    projection_hash: str,
    gate_hash: str | None,
    expected_projection_hash: str | None,
    expected_slate_id: str | None,
    freshness: dict,
    contest_meta: dict | None,
) -> dict[str, Any]:
    errors = []
    if lineup.get("status") != "ok":
        errors.append(lineup.get("reason") or "no_lineup")
    if expected_slate_id and slate_id != expected_slate_id:
        errors.append("wrong_slate")
    if expected_projection_hash and projection_hash != expected_projection_hash:
        errors.append("projection_hash_mismatch")
    if gate_hash and expected_projection_hash and gate_hash != expected_projection_hash:
        errors.append("gate_hash_mismatch")
    if not freshness.get("ok"):
        errors.append(freshness.get("reason") or "stale")

    rows = lineup.get("lineup") or []
    by_id = {p.dk_id: p for p in players}
    for r in rows:
        p = by_id.get(r["dk_id"])
        if p is None:
            errors.append(f"unknown_player:{r['dk_id']}")
            continue
        if p.game_id and r.get("game_id") and p.game_id != r["game_id"]:
            errors.append(f"wrong_game:{p.name}")
        if not p.is_pitcher and (p.scratched or not p.posted):
            errors.append(f"unposted_or_scratched:{p.name}")
        if p.is_pitcher and (not p.workload or not p.workload.get("cash_eligible")):
            errors.append(f"pitcher_workload_unresolved:{p.name}")

    ready = not errors
    return {
        "ready_for_upload": ready,
        "errors": errors,
        "freshness": freshness,
        "contest_meta": contest_meta or {"status": "missing"},
        "projection_hash": projection_hash,
    }
