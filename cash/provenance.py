"""Content hashes for code and in-process gate configuration."""

from __future__ import annotations

from pathlib import Path

from cash.evidence import file_sha256, hash_obj

CASH_DIR = Path(__file__).resolve().parent

GATE_CONFIG = {
    "profile": "task001-cash",
    "salary_cap": 50000,
    "max_hitters_per_team": 5,
    "min_games": 2,
    "require_posted_hitters": True,
    "gate_origin": "in_process_cash.validate",
}


def package_code_hash() -> str:
    parts = []
    for path in sorted(CASH_DIR.glob("*.py")):
        parts.append(f"{path.name}:{file_sha256(path)}")
    return hash_obj(parts)


def gate_hash(extra: dict | None = None) -> str:
    payload = dict(GATE_CONFIG)
    payload["validate_py"] = file_sha256(CASH_DIR / "validate.py")
    payload["workload_py"] = file_sha256(CASH_DIR / "workload.py")
    if extra:
        payload.update(extra)
    return hash_obj(payload)
