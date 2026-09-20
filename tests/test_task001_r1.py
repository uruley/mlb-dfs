#!/usr/bin/env python3
"""R1 CLI regressions. Synthetic only."""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from cash.cli import main as cash_main
from cash.workload import apply_innings_to_pitcher_fp, resolve_skill_rate, resolve_workload
from tests.test_task001 import _tiny_slate, _write_inputs, ev


def _cli(td: Path, extra=None):
    args = [
        "--slate-date", "2026-09-18", "--slate-id", "syn-1",
        "--pool", str(td / "pool.csv"), "--projections", str(td / "proj.csv"),
        "--pitcher-evidence", str(td / "ev.json"), "--out-dir", str(td / "out"),
        "--decision-time", "2026-09-18T18:00:00+00:00",
    ]
    if extra:
        args.extend(extra)
    return cash_main(args)


class R1Regressions(unittest.TestCase):
    def test_skill_not_canceled_by_new_ip(self):
        skill, src = resolve_skill_rate({"original_expected_ip": 5.0}, 15.0, expected_ip=3.0)
        self.assertEqual(src, "frozen_original_rate")
        self.assertAlmostEqual(apply_innings_to_pitcher_fp(skill, 3.0), 9.0)
        self.assertAlmostEqual(apply_innings_to_pitcher_fp(skill, 6.0), 18.0)

    def test_announced_unknown_not_verified(self):
        d = resolve_workload({"role": "unknown", "announced_starter": True})
        self.assertFalse(d.cash_eligible)
        self.assertNotEqual(d.reason, "verified_starter")

    def test_bulk_15_pitch_cap(self):
        d = resolve_workload(ev(
            role="bulk", announced_starter=False, pitch_limit="15 pitches",
            recent_appearances=[
                {"date": "2026-09-12", "role": "bulk", "innings": "5.0"},
                {"date": "2026-09-07", "role": "bulk", "innings": "5.0"},
                {"date": "2026-09-02", "role": "bulk", "innings": "5.0"},
            ],
        ))
        self.assertLessEqual(d.expected_ip, 1.01)
        self.assertFalse(d.cash_eligible)

    def test_wrong_identity_cli_not_ready(self):
        pool, projs, evidence = _tiny_slate()
        evidence[0].update({"slate_date": "1999-01-01", "slate_id": "wrong", "game_id": "other-game", "mlb_id": "wrong"})
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            self.assertEqual(_cli(td), 2)
            self.assertFalse((td / "out" / "lineup-1-cash.ready.json").exists())

    def test_missing_mlb_id_cli_not_ready(self):
        pool, projs, evidence = _tiny_slate()
        evidence[0]["mlb_id"] = ""
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            self.assertEqual(_cli(td), 2)

    def test_future_appearances_cli_not_ready(self):
        pool, projs, evidence = _tiny_slate()
        for row in evidence:
            for a in row["recent_appearances"]:
                a["date"] = "2030-01-01"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            self.assertEqual(_cli(td), 2)

    def test_stale_player_ts_not_blessed(self):
        pool, projs, evidence = _tiny_slate()
        for row in evidence:
            row["information_as_of"] = "2020-01-01T00:00:00+00:00"
            row["retrieved_at"] = "2020-01-01T00:00:00+00:00"
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            self.assertEqual(_cli(td), 2)

    def test_foreign_locked_entries_refused(self):
        pool, projs, evidence = _tiny_slate()
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            src = td / "user.csv"
            src.write_text(
                "Entry ID,Contest ID,Slate ID,P,P,C,1B,2B,3B,SS,OF,OF,OF\n"
                "111,foreign-contest,other-slate,oldA (LOCKED),oldB (LOCKED),c,b1,b2,b3,ss,o1,o2,o3\n"
            )
            self.assertEqual(_cli(td, ["--entries", str(src)]), 2)
            self.assertFalse((td / "out" / "lineup-1-cash.ready.json").exists())

    def test_compatible_entries_keep_repeated_headers(self):
        pool, projs, evidence = _tiny_slate()
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            src = td / "user.csv"
            src.write_text("Entry ID,Contest ID,Slate ID,P,P,C,1B,2B,3B,SS,OF,OF,OF\n111,c1,syn-1,,,,,,,,,,\n")
            self.assertEqual(_cli(td, ["--entries", str(src)]), 0)
            header = (td / "out" / "lineup-1-cash-ENTRIES-UPLOAD.csv").read_text().splitlines()[0]
            self.assertEqual(header, "Entry ID,Contest ID,Slate ID,P,P,C,1B,2B,3B,SS,OF,OF,OF")

    def test_valid_cli_ready(self):
        pool, projs, evidence = _tiny_slate()
        with tempfile.TemporaryDirectory() as td:
            td = Path(td)
            _write_inputs(td, pool, projs, evidence)
            self.assertEqual(_cli(td), 0)
            ready = json.loads((td / "out" / "lineup-1-cash.ready.json").read_text())
            self.assertEqual(ready["status"], "ready_for_upload")
            self.assertEqual(ready["lineup"]["solution_status"], "optimal")


if __name__ == "__main__":
    unittest.main()
