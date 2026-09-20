"""Delivery gates. Fail closed. Never mark ready on unresolved evidence."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
from typing import Any

from cash.builder import HITTER_SLOTS, MAX_HITTERS_PER_TEAM, MIN_GAMES, SALARY_CAP, eligible_positions


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


def parse_date(value: str | None):
    if not value:
        return None
    s = str(value)[:10]
    try:
        return datetime.strptime(s, "%Y-%m-%d").date()
    except ValueError:
        return None


def check_freshness(
    *,
    as_of: str | None,
    retrieved_at: str | None,
    decision_time: str | None,
    max_age_hours: float = 6.0,
    require_decision_time: bool = False,
) -> dict[str, Any]:
    """Freshness vs decision_time (historical replay) not wall clock if provided."""
    if decision_time:
        ref = parse_iso(decision_time)
        if ref is None:
            return {"ok": False, "reason": "malformed_decision_time", "age_hours": None}
    else:
        if require_decision_time:
            return {"ok": False, "reason": "missing_decision_time", "age_hours": None}
        ref = datetime.now(timezone.utc)
    src_as = parse_iso(as_of)
    src_ret = parse_iso(retrieved_at)
    if src_as and src_ret and src_ret < src_as:
        return {"ok": False, "reason": "retrieved_before_as_of", "age_hours": None}
    src = src_as or src_ret
    if src is None:
        return {"ok": False, "reason": "missing_source_timestamp", "age_hours": None}
    age = (ref - src).total_seconds() / 3600.0
    if age < 0:
        return {"ok": False, "reason": "source_after_decision_time", "age_hours": age}
    if age > max_age_hours:
        return {"ok": False, "reason": "stale_critical_data", "age_hours": age}
    return {"ok": True, "reason": "fresh", "age_hours": age, "decision_time": ref.isoformat()}


def evidence_record_freshness(ev: dict, decision_time: str | None, max_age_hours: float) -> dict[str, Any]:
    meta = ev.get("_meta") or {}
    as_of = ev.get("information_as_of") or meta.get("information_as_of")
    retrieved = ev.get("retrieved_at") or meta.get("retrieved_at")
    base = check_freshness(
        as_of=as_of,
        retrieved_at=retrieved,
        decision_time=decision_time,
        max_age_hours=max_age_hours,
    )
    if not base["ok"]:
        return base
    ref = parse_iso(decision_time) or datetime.now(timezone.utc)
    ref_day = ref.date()
    for a in ev.get("recent_appearances") or []:
        d = parse_date(a.get("date"))
        if d is None:
            return {"ok": False, "reason": "appearance_missing_date", "age_hours": None}
        if d > ref_day:
            return {"ok": False, "reason": "future_or_postgame_appearance", "age_hours": None}
    return base


def collect_player_freshness(
    evidence_rows: list[dict],
    *,
    decision_time: str | None,
    max_age_hours: float,
) -> dict[str, dict]:
    out = {}
    for ev in evidence_rows:
        out[str(ev.get("dk_id"))] = evidence_record_freshness(ev, decision_time, max_age_hours)
    return out


def validate_delivery(
    *,
    lineup: dict,
    players: list,
    slate_id: str,
    slate_date: str,
    projection_hash: str,
    gate_hash: str | None,
    expected_projection_hash: str | None,
    expected_gate_hash: str | None,
    pool_slate_ids: set[str],
    proj_slate_ids: set[str],
    evidence_slate_ids: set[str],
    freshness: dict,
    player_freshness: dict[str, dict] | None,
    contest_meta: dict | None,
    schema_error_list: list[str] | None = None,
) -> dict[str, Any]:
    errors = []
    if schema_error_list:
        errors.extend(f"schema:{e}" for e in schema_error_list)
    if lineup.get("status") != "ok":
        errors.append(lineup.get("reason") or "no_lineup")
    if slate_id not in pool_slate_ids and pool_slate_ids:
        errors.append("wrong_slate_pool")
    if slate_id not in proj_slate_ids and proj_slate_ids:
        errors.append("wrong_slate_projections")
    if slate_id not in evidence_slate_ids and evidence_slate_ids:
        errors.append("wrong_slate_evidence")
    if expected_projection_hash and projection_hash != expected_projection_hash:
        errors.append("projection_hash_mismatch")
    if expected_gate_hash and gate_hash and gate_hash != expected_gate_hash:
        errors.append("gate_hash_mismatch")
    if not freshness.get("ok"):
        errors.append(freshness.get("reason") or "stale")

    rows = lineup.get("lineup") or []
    by_id = {p.dk_id: p for p in players}
    assigned_slots = [r.get("slot") for r in rows]
    if assigned_slots and assigned_slots != ["P", "P"] + HITTER_SLOTS:
        errors.append("slot_order")

    games = []
    teams = Counter()
    ids = []
    salary = 0
    for r in rows:
        p = by_id.get(r["dk_id"])
        if p is None:
            errors.append(f"unknown_player:{r['dk_id']}")
            continue
        ids.append(p.dk_id)
        salary += p.salary
        games.append(p.game_id)
        if p.game_id != r.get("game_id"):
            errors.append(f"lineup_game_mismatch:{p.dk_id}")
        if not p.game_id:
            errors.append(f"missing_game:{p.dk_id}")
        if p.scratched:
            errors.append(f"scratched:{p.name}")
        if p.exclude_reason:
            errors.append(f"excluded_selected:{p.dk_id}:{p.exclude_reason}")
        slot = r.get("slot")
        if slot and slot not in eligible_positions(p.position):
            errors.append(f"slot_ineligible:{p.dk_id}:{slot}")
        if p.is_pitcher:
            if not p.workload or not p.workload.get("cash_eligible"):
                errors.append(f"pitcher_workload_unresolved:{p.name}")
            pf = (player_freshness or {}).get(p.dk_id)
            if pf and not pf.get("ok"):
                errors.append(f"stale_selected_pitcher:{p.dk_id}:{pf.get('reason')}")
        else:
            teams[p.team] += 1
            if not p.posted:
                errors.append(f"unposted_or_scratched:{p.name}")
            hf = (player_freshness or {}).get(p.dk_id)
            if hf and not hf.get("ok"):
                errors.append(f"stale_selected_hitter:{p.dk_id}:{hf.get('reason')}")

    if ids and len(set(ids)) != len(ids):
        errors.append("duplicate")
    if salary > SALARY_CAP:
        errors.append("salary")
    if any(v > MAX_HITTERS_PER_TEAM for v in teams.values()):
        errors.append("team_hitter_cap")
    if games and ("" in games or len(set(games)) < MIN_GAMES):
        errors.append("min_games_or_missing")

    ready = not errors
    return {
        "ready_for_upload": ready,
        "errors": errors,
        "freshness": freshness,
        "contest_meta": contest_meta or {"status": "missing"},
        "projection_hash": projection_hash,
        "gate_hash": gate_hash,
        "gate_origin": "in_process_cash.validate",
    }
