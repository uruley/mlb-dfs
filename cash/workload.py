"""Role and expected-innings from pregame evidence.

Salary, DK SP/RP label, hardcoded names, and yesterday FPTS are not
decisive workload evidence. They may appear on a record as roster facts only.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cash.innings import parse_innings

ROLES = ("starter", "opener", "bulk", "relief", "unknown")

# Explicit priors when comparable-role sample is thin. Documented, not silent.
PRIOR_IP = {
    "starter": 5.2,   # baseball 5.2 = 17 outs
    "bulk": 4.1,
    "opener": 1.0,
    "relief": 1.0,
}
SMALL_SAMPLE_N = 3
RESTRICTED_DEFAULT_IP = 3.0


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
        }


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


def resolve_workload(ev: dict) -> WorkloadDecision:
    """Map one pitcher-evidence record to role + expected IP.

    Availability policy: unknown/conflicting critical workload → cash ineligible.
    """
    notes: list[str] = []
    role = str(ev.get("role") or "unknown").lower().strip()
    if role not in ROLES:
        role = "unknown"
    announced = bool(ev.get("announced_starter"))
    conflicts = ev.get("conflicts") or []
    status = str(ev.get("availability_status") or ev.get("confidence") or "").lower()
    restriction = ev.get("pitch_limit") or ev.get("restriction") or ev.get("injury_return")
    sample = ev.get("recent_appearances") or []

    if conflicts or status in ("conflict", "conflicting", "unknown", "unresolved"):
        if role == "unknown" or conflicts or status in ("conflict", "conflicting", "unresolved"):
            return WorkloadDecision(
                role="unknown" if role == "unknown" else role,
                expected_ip=0.0,
                expected_outs=0,
                cash_eligible=False,
                reason="unresolved_or_conflicting_workload",
                method="blocked",
                confidence="none",
                notes=[str(c) for c in conflicts] or [status or "unresolved"],
            )

    if role == "unknown" and announced:
        role = "starter"
        notes.append("announced_starter_without_explicit_role")

    if role == "unknown":
        return WorkloadDecision(
            role="unknown",
            expected_ip=0.0,
            expected_outs=0,
            cash_eligible=False,
            reason="unknown_role",
            method="blocked",
            confidence="none",
            notes=notes,
        )

    comparable_role = "starter" if role == "starter" else role
    sample_ip, n = _mean_ip(sample, role=comparable_role)
    if sample_ip is None and role == "starter":
        sample_ip, n = _mean_ip(sample, role=None)

    if restriction:
        notes.append(f"restriction:{restriction}")
        if role == "starter":
            ip = min(RESTRICTED_DEFAULT_IP, sample_ip if sample_ip is not None else RESTRICTED_DEFAULT_IP)
            method = "restriction_cap"
            conf = "medium" if n >= SMALL_SAMPLE_N else "low"
            return WorkloadDecision(
                role="opener" if ip <= 2.0 else "starter",
                expected_ip=ip,
                expected_outs=int(round(ip * 3)),
                cash_eligible=ip >= 3.0,
                reason="restricted_starter",
                method=method,
                confidence=conf,
                notes=notes,
            )

    if role == "opener":
        ip = sample_ip if sample_ip is not None else PRIOR_IP["opener"]
        ip = min(ip, 2.0)
        return WorkloadDecision(
            role="opener",
            expected_ip=ip,
            expected_outs=int(round(ip * 3)),
            cash_eligible=False,
            reason="opener_short_workload",
            method="sample" if n else "prior_opener",
            confidence="medium" if n >= SMALL_SAMPLE_N else "low",
            notes=notes + [f"sample_n={n}"],
        )

    if role == "relief":
        ip = sample_ip if sample_ip is not None else PRIOR_IP["relief"]
        ip = min(ip, 2.0)
        return WorkloadDecision(
            role="relief",
            expected_ip=ip,
            expected_outs=int(round(ip * 3)),
            cash_eligible=False,
            reason="relief_not_cash_sp",
            method="sample" if n else "prior_relief",
            confidence="medium" if n else "low",
            notes=notes,
        )

    if role == "bulk":
        if sample_ip is not None and n >= SMALL_SAMPLE_N:
            ip, method, conf = sample_ip, "comparable_bulk_sample", "medium"
        elif sample_ip is not None:
            prior = PRIOR_IP["bulk"]
            ip = (n * sample_ip + (SMALL_SAMPLE_N - n) * prior) / SMALL_SAMPLE_N
            method, conf = "shrunk_bulk_prior", "low"
            notes.append(f"small_sample_n={n}; prior_ip={prior}")
        else:
            ip, method, conf = PRIOR_IP["bulk"], "prior_bulk", "low"
            notes.append("no comparable bulk sample; explicit prior 4.1 IP")
        return WorkloadDecision(
            role="bulk",
            expected_ip=ip,
            expected_outs=int(round(ip * 3)),
            cash_eligible=True,
            reason="verified_bulk",
            method=method,
            confidence=conf,
            notes=notes,
        )

    if sample_ip is not None and n >= SMALL_SAMPLE_N:
        ip, method, conf = sample_ip, "comparable_start_sample", "high"
    elif sample_ip is not None:
        prior = parse_innings(PRIOR_IP["starter"])
        ip = (n * sample_ip + (SMALL_SAMPLE_N - n) * prior) / SMALL_SAMPLE_N
        method, conf = "shrunk_starter_prior", "low"
        notes.append(f"small_sample_n={n}; prior_ip=5.2 baseball")
    else:
        ip = parse_innings(PRIOR_IP["starter"])
        method, conf = "prior_starter", "low"
        notes.append("no comparable starts; explicit prior 5.2 IP (17 outs)")

    return WorkloadDecision(
        role="starter",
        expected_ip=ip,
        expected_outs=int(round(ip * 3)),
        cash_eligible=True,
        reason="verified_starter",
        method=method,
        confidence=conf,
        notes=notes,
    )


def apply_innings_to_pitcher_fp(
    per_inning_skill: float,
    expected_ip: float,
    *,
    win_points: float = 0.0,
) -> float:
    """Separate workload from per-inning skill. Salary cannot change IP here."""
    return per_inning_skill * expected_ip + win_points
