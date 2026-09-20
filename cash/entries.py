"""Upload Entries writer: numeric Entry IDs only; preserve locked slots."""

from __future__ import annotations

import csv
from pathlib import Path

DK_SLOTS = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]


def is_numeric_entry_id(value: str) -> bool:
    s = str(value or "").strip()
    return s.isdigit() and len(s) >= 3


def parse_user_entries(path: Path) -> list[dict]:
    rows = []
    with Path(path).open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        fieldnames = reader.fieldnames or []
        id_col = None
        for cand in ("Entry ID", "EntryID", "entry_id"):
            if cand in fieldnames:
                id_col = cand
                break
        if id_col is None and fieldnames:
            id_col = fieldnames[0]
        for raw in reader:
            eid = raw.get(id_col, "")
            if not is_numeric_entry_id(eid):
                continue
            rows.append(raw)
    return rows


def write_entries_upload(
    path: Path,
    entries: list[dict],
    lineup_ids: list[str],
    *,
    slot_headers: list[str] | None = None,
    locked_fields: dict[str, str] | None = None,
) -> int:
    """Write one output row per numeric entry. lineup_ids is 10 DK IDs in slot order."""
    if len(lineup_ids) != 10:
        raise ValueError("need 10 player ids")
    headers = slot_headers or [
        "P", "P.1", "C", "1B", "2B", "3B", "SS", "OF", "OF.1", "OF.2"
    ]
    if locked_fields:
        for k, v in locked_fields.items():
            if v and str(v) not in lineup_ids:
                raise ValueError(f"cannot preserve lock {k}={v}")

    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=["Entry ID"] + headers,
            extrasaction="ignore",
        )
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
