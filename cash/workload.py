"""Role and expected-innings from pregame evidence.

Salary, DK SP/RP label, hardcoded names, and yesterday FPTS are not
decisive workload evidence. They may appear on a record as roster facts only.

Priors may fill an estimate after eligibility is established. They do not
themselves make a pitcher cash-eligible.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from cash.innings import parse_innings

ROLES = ("starter", "opener", "bulk", "relief", "unknown")

# Explicit priors in baseball notation. Convert with parse_innings.
PRIOR_IP_BASEBALL = {
    "starter": "5.2",  # 17 outs
    "bulk": "4.1",
    "opener": "1.0",
    "relief": "1.0",
}
SMALL_SAMPLE_N = 3
PITCHES_PER_INNING = 15.0
CASH_MIN_IP = 3.0
BLOCK_STATUS = {"conflict", "conflicting", "unknown", "unresolved", "out", "scratched"}


@dataclass
class Restriction:
    present: bool
    type: str | None
    pitches: float | None
    max_ip: float | None
    raw: Any = None

    def cap_ip(self, ip: float) -> float:
        if not self.present:
            return ip
        cap = self.max_ip
        if cap is None and self.pitches is not None:
            cap = self.pitches / PITCHES_PER_INNING
        if cap is None:
            return ip
        return min(ip, cap)


@dataclass
class WorkloadDecision:
    role: str
    expected_ip: float
    expected_outs: int
    cash_eligible: bool
    reason: str
    method: str
    confidence: str
    salary_used_for_workload: bool = False
    notes: list[str] = field(default_factory=list)
    source: dict[str, Any] = field(default_factory=dict)
    restriction: dict[str, Any] = field(default_factory=dict)

    def as_dict(self) -> dict[str, Any]:
        return {
            "role": self.role,
            "expected_ip": round(self.expected_ip, 4),
            "expected_outs": self.expected_outs,
            "cash_eligible": self.cash_eligible,
            "reason": self.reason,
            "method": self.method,
            "confidence": self.confidence,
            "salary_used_for_workload": self.salary_used_for_workload,
            "notes": list(self.notes),
            "source": dict(self.source),
            "restriction": dict(self.restriction),
        }


def parse_restriction(ev: dict) -> Restriction:
    raw = ev.get("restriction")
    if isinstance(raw, dict):
        pitches = raw.get("pitches", raw.get("pitch_limit"))
        max_ip = raw.get("max_ip")
        if pitches not in (None, ""):
            pitches = float(pitches)
        else:
            pitches = None
        if max_ip not in (None, ""):
            max_ip = parse_innings(max_ip) if isinstance(max_ip, str) else float(max_ip)
        else:
            max_ip = None
        present = bool(raw.get("type") or pitches is not None or max_ip is not None)
        return Restriction(present, raw.get("type"), pitches, max_ip, raw)
    pl = ev.get("pitch_limit")
    if pl not in (None, "", False):
        pitches = None
        if isinstance(pl, (int, float)) and not isinstance(pl, bool):
            pitches = float(pl)
        else:
            m = re.search(r"(\d+(?:\.\d+)?)", str(pl))
            if m:
                pitches = float(m.group(1))
        return Restriction(True, "pitch_limit", pitches, None, pl)
    if ev.get("injury_return"):
        return Restriction(True, "injury_return", None, None, ev.get("injury_return"))
    return Restriction(False, None, None, None, None)


def _blocked(role: str, reason: str, notes: list[str], source: dict) -> WorkloadDecision:
    return WorkloadDecision(
        role=role,
        expected_ip=0.0,
        expected_outs=0,
        cash_eligible=False,
        reason=reason,
        method="blocked",
        confidence="none",
        notes=notes,
        source=source,
    )


def _mean_ip(appearances: list[dict], role: str | None = None) -> tuple[float | None, int]:
    vals = []
    for a in appearances or []:
        if role and str(a.get("role") or "").lower() != role:
            continue
        raw = a.get("innings")
        if raw in (None, ""):
            if a.get("outs") not in (None, ""):
                vals.append(int(a["outs"]) / 3.0)
            continue
        try:
            vals.append(parse_innings(raw))
        except ValueError:
            continue
    if not vals:
        return None, 0
    return sum(vals) / len(vals), len(vals)


def _source(ev: dict) -> dict[str, Any]:
    meta = ev.get("_meta") or {}
    return {
        "dk_id": ev.get("dk_id"),
        "mlb_id": ev.get("mlb_id"),
        "game_id": ev.get("game_id"),
        "slate_id": ev.get("slate_id"),
        "slate_date": ev.get("slate_date"),
        "information_as_of": ev.get("information_as_of") or meta.get("information_as_of"),
        "retrieved_at": ev.get("retrieved_at") or meta.get("retrieved_at"),
    }


def resolve_workload(ev: dict) -> WorkloadDecision:
    """Map one pitcher-evidence record to role + expected IP.

    A probable/announced starter is not full-workload evidence.
    """
    notes: list[str] = []
    source = _source(ev)
    role = str(ev.get("role") or "unknown").lower().strip()
    if role not in ROLES:
        role = "unknown"
    announced = bool(ev.get("announced_starter"))
    conflicts = ev.get("conflicts") or []
    status = str(ev.get("availability_status") or "").lower().strip()
    restriction = parse_restriction(ev)
    sample = ev.get("recent_appearances") or []

    if restriction.present:
        notes.append(f"restriction:{restriction.type}:{restriction.raw}")

    if conflicts or status in {"conflict", "conflicting", "unresolved"}:
        return _blocked(
            role if role != "unknown" else "unknown",
            "unresolved_or_conflicting_workload",
            [str(c) for c in conflicts] or [status or "unresolved"],
            source,
        )

    if status in BLOCK_STATUS:
        return _blocked(role, "availability_not_confirmed", [status or "unknown"], source)

    if role == "unknown":
        extra = ["announced_starter_is_not_workload"] if announced else []
        return _blocked("unknown", "unknown_role", notes + extra, source)

    sample_ip, n = _mean_ip(sample, role=role)
    if sample_ip is None and role == "starter":
        sample_ip, n = _mean_ip(sample, role=None)
        if n:
            notes.append("starter_sample_unlabeled_appearances")

    explicit_ip = ev.get("expected_innings")
    has_sample = n > 0
    has_explicit = explicit_ip not in (None, "")
    source_backed = has_sample or has_explicit or restriction.present

    if role in ("opener", "relief"):
        if has_explicit:
            ip = parse_innings(explicit_ip)
            method = "explicit_expected_innings"
        elif sample_ip is not None:
            ip, method = sample_ip, "sample"
        else:
            ip = parse_innings(PRIOR_IP_BASEBALL[role])
            method = f"prior_{role}_ineligible"
        ip = restriction.cap_ip(min(ip, 2.0))
        return WorkloadDecision(
            role=role,
            expected_ip=ip,
            expected_outs=int(round(ip * 3)),
            cash_eligible=False,
            reason="opener_short_workload" if role == "opener" else "relief_not_cash_sp",
            method=method,
            confidence="medium" if n >= SMALL_SAMPLE_N else "low",
            notes=notes + [f"sample_n={n}"],
            source=source,
            restriction={
                "present": restriction.present,
                "type": restriction.type,
                "pitches": restriction.pitches,
                "max_ip": restriction.max_ip,
            },
        )

    if not source_backed:
        prior = parse_innings(PRIOR_IP_BASEBALL[role])
        notes.append(f"prior_{role}_ip={PRIOR_IP_BASEBALL[role]}_not_used_for_eligibility")
        return WorkloadDecision(
            role=role,
            expected_ip=prior,
            expected_outs=int(round(prior * 3)),
            cash_eligible=False,
            reason="insufficient_workload_evidence",
            method="prior_not_eligible",
            confidence="none",
            notes=notes,
            source=source,
            restriction={"present": False},
        )

    if has_explicit:
        ip = parse_innings(explicit_ip)
        method, conf = "explicit_expected_innings", "medium"
    elif sample_ip is not None and n >= SMALL_SAMPLE_N:
        ip, method, conf = sample_ip, f"comparable_{role}_sample", "high" if role == "starter" else "medium"
    elif sample_ip is not None:
        prior = parse_innings(PRIOR_IP_BASEBALL[role])
        ip = (n * sample_ip + (SMALL_SAMPLE_N - n) * prior) / SMALL_SAMPLE_N
        method, conf = f"shrunk_{role}_prior", "low"
        notes.append(f"small_sample_n={n}; prior={PRIOR_IP_BASEBALL[role]}")
    else:
        ip = parse_innings(PRIOR_IP_BASEBALL[role])
        method, conf = f"restriction_or_prior_{role}", "low"

    ip = restriction.cap_ip(ip)
    if restriction.present:
        method = method + "+restriction_cap"

    eligible = ip >= CASH_MIN_IP
    reason = f"verified_{role}" if eligible else f"short_workload_{role}"
    if restriction.present and role == "starter":
        reason = "restricted_starter" if eligible else "restricted_starter_short"

    return WorkloadDecision(
        role=role,
        expected_ip=ip,
        expected_outs=int(round(ip * 3)),
        cash_eligible=eligible,
        reason=reason,
        method=method,
        confidence=conf,
        notes=notes,
        source=source,
        restriction={
            "present": restriction.present,
            "type": restriction.type,
            "pitches": restriction.pitches,
            "max_ip": restriction.max_ip,
        },
    )


def apply_innings_to_pitcher_fp(
    per_inning_skill: float,
    expected_ip: float,
    *,
    win_points: float = 0.0,
) -> float:
    """Separate workload from per-inning skill. Salary cannot change IP here."""
    return per_inning_skill * expected_ip + win_points


def resolve_skill_rate(ev: dict, raw_proj: float, expected_ip: float) -> tuple[float | None, str]:
    """Independent rate. Never infer skill from the new expected_ip."""
    skill = ev.get("per_inning_skill")
    if skill not in (None, ""):
        return float(skill), "evidenced_per_inning_skill"
    original_ip = ev.get("original_expected_ip") or ev.get("frozen_expected_ip")
    if original_ip not in (None, "") and raw_proj:
        if isinstance(original_ip, str):
            oip = parse_innings(original_ip)
        else:
            oip = float(original_ip)
        if oip > 0:
            return raw_proj / oip, "frozen_original_rate"
    return None, "unresolved_skill_rate"
