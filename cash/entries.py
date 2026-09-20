"""Upload Entries writer: numeric Entry IDs only; preserve locked slots."""

from __future__ import annotations

import csv
import re
from pathlib import Path

DK_SLOTS = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]
META_NAMES = {
    "entry id",
    "entryid",
    "entry_id",
    "contest id",
    "contestid",
    "contest name",
    "slate id",
    "slateid",
    "ticket id",
    "entry fee",
}


def is_numeric_entry_id(value: str) -> bool:
    s = str(value or "").strip()
    return s.isdigit() and len(s) >= 3


def _norm(h: str) -> str:
    return re.sub(r"\.\d+$", "", str(h or "")).strip().lower()


def _is_slot_header(h: str) -> bool:
    base = re.sub(r"\.\d+$", "", str(h or "")).strip().upper()
    return base in {"P", "C", "1B", "2B", "3B", "SS", "OF"}


def _parse_cell(value: str) -> tuple[str, bool]:
    raw = str(value or "").strip()
    locked = bool(re.search(r"\(LOCKED\)|\bLOCKED\b", raw, re.I))
    pid = re.sub(r"\s*\(LOCKED\)\s*", "", raw, flags=re.I).strip()
    return pid, locked


def parse_user_entries(path: Path) -> dict:
    """Parse an authentic DK export without collapsing repeated headers."""
    with Path(path).open(newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    if not rows:
        return {"headers": [], "entries": [], "errors": ["empty_export"]}
    headers = rows[0]
    slot_idx = [i for i, h in enumerate(headers) if _is_slot_header(h)]
    id_idx = next((i for i, h in enumerate(headers) if _norm(h) in {"entry id", "entryid", "entry_id"}), 0)
    slate_idx = next((i for i, h in enumerate(headers) if _norm(h) in {"slate id", "slateid"}), None)
    contest_idx = next((i for i, h in enumerate(headers) if _norm(h) in {"contest id", "contestid"}), None)
    entries = []
    errors = []
    for raw in rows[1:]:
        if not raw or all(not c.strip() for c in raw):
            continue
        eid = raw[id_idx] if id_idx < len(raw) else ""
        if not is_numeric_entry_id(eid):
            continue
        cells = list(raw) + [""] * max(0, len(headers) - len(raw))
        slots = []
        locks = {}
        for order, i in enumerate(slot_idx[:10]):
            pid, locked = _parse_cell(cells[i] if i < len(cells) else "")
            slots.append(pid)
            if locked:
                locks[order] = pid
        entries.append(
            {
                "entry_id": eid,
                "cells": cells,
                "slots": slots,
                "locks": locks,
                "slate_id": cells[slate_idx] if slate_idx is not None and slate_idx < len(cells) else "",
                "contest_id": cells[contest_idx] if contest_idx is not None and contest_idx < len(cells) else "",
            }
        )
    if slot_idx and len(slot_idx) < 10:
        errors.append("incomplete_slot_headers")
    return {
        "headers": headers,
        "entries": entries,
        "errors": errors,
        "slot_idx": slot_idx,
        "id_idx": id_idx,
        "slate_idx": slate_idx,
        "contest_idx": contest_idx,
    }


def apply_lineup_to_entries(
    parsed: dict,
    lineup_ids: list[str],
    *,
    slate_id: str,
    contest_id: str | None = None,
) -> tuple[list[list[str]], list[str]]:
    if len(lineup_ids) != 10:
        raise ValueError("need 10 player ids")
    errors = list(parsed.get("errors") or [])
    out_rows = []
    headers = parsed["headers"]
    for e in parsed["entries"]:
        if e.get("slate_id") and str(e["slate_id"]) != str(slate_id):
            errors.append(f"incompatible_slate:{e['entry_id']}:{e['slate_id']}")
            continue
        if contest_id and e.get("contest_id") and str(e["contest_id"]) != str(contest_id):
            errors.append(f"incompatible_contest:{e['entry_id']}:{e['contest_id']}")
            continue
        new_slots = list(lineup_ids)
        for order, pid in (e.get("locks") or {}).items():
            if not pid:
                errors.append(f"lock_unreadable:{e['entry_id']}:{order}")
                new_slots = None
                break
            if pid not in lineup_ids:
                errors.append(f"cannot_preserve_lock:{e['entry_id']}:{pid}")
                new_slots = None
                break
            new_slots[order] = pid
        if new_slots is None:
            continue
        if len(set(new_slots)) != 10:
            errors.append(f"lock_creates_duplicate:{e['entry_id']}")
            continue
        cells = list(e["cells"])
        if len(cells) < len(headers):
            cells += [""] * (len(headers) - len(cells))
        for order, i in enumerate(parsed["slot_idx"][:10]):
            cells[i] = new_slots[order]
        out_rows.append(cells)
    return out_rows, errors


def write_entries_upload(
    path: Path,
    entries,
    lineup_ids: list[str],
    *,
    slot_headers: list[str] | None = None,
    locked_fields: dict[str, str] | None = None,
    parsed: dict | None = None,
    slate_id: str | None = None,
    contest_id: str | None = None,
) -> int:
    """Write upload CSV. Prefer parsed authentic-format path when provided."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if parsed is not None:
        rows, errors = apply_lineup_to_entries(
            parsed, lineup_ids, slate_id=slate_id or "", contest_id=contest_id
        )
        if errors:
            raise ValueError(";".join(errors))
        with path.open("w", newline="", encoding="utf-8") as f:
            w = csv.writer(f)
            w.writerow(parsed["headers"])
            w.writerows(rows)
        return len(rows)

    if len(lineup_ids) != 10:
        raise ValueError("need 10 player ids")
    headers = slot_headers or ["P", "P.1", "C", "1B", "2B", "3B", "SS", "OF", "OF.1", "OF.2"]
    if locked_fields:
        for k, v in locked_fields.items():
            if v and str(v) not in lineup_ids:
                raise ValueError(f"cannot preserve lock {k}={v}")
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["Entry ID"] + headers, extrasaction="ignore")
        w.writeheader()
        for e in entries:
            eid = e.get("Entry ID") or e.get("EntryID") or e.get("entry_id")
            row = {"Entry ID": eid}
            for h, pid in zip(headers, lineup_ids):
                row[h] = pid
            if locked_fields:
                row.update(locked_fields)
            w.writerow(row)
    return len(entries)
