#!/usr/bin/env python3
"""Task 001 acceptance checks. Synthetic fixtures unless noted."""
from __future__ import annotations
import json, sys, tempfile, unittest
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from cash.builder import build_one_lineup, load_players
from cash.cli import main as cash_main
from cash.entries import is_numeric_entry_id, parse_user_entries, write_entries_upload
from cash.innings import innings_to_outs, parse_innings
from cash.validate import check_freshness
from cash.workload import apply_innings_to_pitcher_fp, resolve_workload

SLATE = dict(slate_id="syn-1", slate_date="2026-09-18")

def ev(**kw):
    base = {
        "slate_date": "2026-09-18", "slate_id": "syn-1", "game_id": "g1",
        "mlb_id": "100", "dk_id": "1", "dk_eligibility": "RP",
        "announced_starter": True, "role": "starter",
        "recent_appearances": [
            {"date": "2026-09-12", "role": "starter", "innings": "6.0", "outs": 18},
            {"date": "2026-09-07", "role": "starter", "innings": "5.2", "outs": 17},
            {"date": "2026-09-02", "role": "starter", "innings": "6.1", "outs": 19},
        ],
        "availability_status": "ok", "conflicts": [], "per_inning_skill": 3.0,
        "information_as_of": "2026-09-18T16:00:00+00:00",
        "retrieved_at": "2026-09-18T16:00:00+00:00",
    }
    base.update(kw)
    return base

class InningsTests(unittest.TestCase):
    def test_5_2_is_seventeen_outs(self):
        self.assertEqual(innings_to_outs("5.2"), 17)
        self.assertAlmostEqual(parse_innings("5.2"), 17 / 3)
        self.assertAlmostEqual(parse_innings(5.2), 17 / 3)

class WorkloadTests(unittest.TestCase):
    def test_rp_tagged_verified_starter_eligible_ignore_salary(self):
        d = resolve_workload(ev(dk_eligibility="RP", salary=4200, role="starter"))
        self.assertTrue(d.cash_eligible)
        self.assertEqual(d.role, "starter")
        self.assertFalse(d.salary_used_for_workload)
        self.assertGreaterEqual(d.expected_ip, 5.0)
    def test_expensive_opener_stays_opener(self):
        d = resolve_workload(ev(role="opener", announced_starter=True, salary=9800, dk_eligibility="RP", recent_appearances=[{"date": "2026-09-12", "role": "opener", "innings": "1.0"}]))
        self.assertEqual(d.role, "opener")
        self.assertLessEqual(d.expected_ip, 2.0)
        self.assertFalse(d.cash_eligible)
    def test_cheap_verified_starter_not_excluded(self):
        self.assertTrue(resolve_workload(ev(salary=4800, role="starter", dk_eligibility="SP")).cash_eligible)
    def test_restricted_sp_not_auto_five_plus(self):
        d = resolve_workload(ev(role="starter", dk_eligibility="SP", pitch_limit="45 pitches", salary=9000))
        self.assertLess(d.expected_ip, 5.0)
    def test_bulk_not_listed_probable(self):
        d = resolve_workload(ev(announced_starter=False, role="bulk", recent_appearances=[{"date": "2026-09-12", "role": "bulk", "innings": "4.1"}, {"date": "2026-09-07", "role": "bulk", "innings": "4.2"}, {"date": "2026-09-02", "role": "bulk", "innings": "5.0"}]))
        self.assertEqual(d.role, "bulk")
        self.assertTrue(d.cash_eligible)
    def test_unknown_blocks(self):
        d = resolve_workload(ev(role="unknown", availability_status="unresolved", conflicts=["two roles"]))
        self.assertFalse(d.cash_eligible)
        self.assertEqual(d.reason, "unresolved_or_conflicting_workload")
    def test_salary_change_does_not_change_ip(self):
        a = resolve_workload(ev(salary=4000))
        b = resolve_workload(ev(salary=12000))
        self.assertEqual(a.expected_ip, b.expected_ip)
        self.assertEqual(apply_innings_to_pitcher_fp(3.0, a.expected_ip), apply_innings_to_pitcher_fp(3.0, b.expected_ip))
    def test_announced_unknown_is_not_verified_starter(self):
        d = resolve_workload({"role": "unknown", "announced_starter": True})
        self.assertFalse(d.cash_eligible)

def _tiny_slate(scratch=False, unposted=False, extra_game="g1"):
    pool = [
        {"ID": "p1", "Name": "Starter A", "Position": "RP", "TeamAbbrev": "AAA", "Salary": "4000", "Game Info": "AAA@BBB", "game_id": extra_game, "mlb_id": "1", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "p2", "Name": "Starter B", "Position": "SP", "TeamAbbrev": "BBB", "Salary": "5000", "Game Info": "AAA@BBB", "game_id": "g1", "mlb_id": "2", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "c1", "Name": "Catch", "Position": "C", "TeamAbbrev": "AAA", "Salary": "3000", "Game Info": "AAA@BBB", "game_id": "g1", "posted": "true", "scratched": "true" if scratch else "false", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "b1", "Name": "First", "Position": "1B", "TeamAbbrev": "AAA", "Salary": "3000", "Game Info": "AAA@BBB", "game_id": "g1", "posted": "false" if unposted else "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "b2", "Name": "Second", "Position": "2B", "TeamAbbrev": "BBB", "Salary": "3000", "Game Info": "AAA@BBB", "game_id": "g1", "posted": "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "b3", "Name": "Third", "Position": "3B", "TeamAbbrev": "BBB", "Salary": "3000", "Game Info": "AAA@BBB", "game_id": "g1", "posted": "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "b4", "Name": "Short", "Position": "SS", "TeamAbbrev": "CCC", "Salary": "3000", "Game Info": "CCC@DDD", "game_id": "g2", "posted": "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "o1", "Name": "OF1", "Position": "OF", "TeamAbbrev": "CCC", "Salary": "3000", "Game Info": "CCC@DDD", "game_id": "g2", "posted": "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "o2", "Name": "OF2", "Position": "OF", "TeamAbbrev": "CCC", "Salary": "3000", "Game Info": "CCC@DDD", "game_id": "g2", "posted": "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
        {"ID": "o3", "Name": "OF3", "Position": "OF", "TeamAbbrev": "DDD", "Salary": "3000", "Game Info": "CCC@DDD", "game_id": "g2", "posted": "true", "slate_id": "syn-1", "slate_date": "2026-09-18"},
    ]
    projs = [{"dk_id": i, "proj_fp": "15" if i=="p1" else "14" if i=="p2" else "8", "slate_id": "syn-1"} for i in ["p1","p2","c1","b1","b2","b3","b4","o1","o2","o3"]]
    evidence = [ev(dk_id="p1", mlb_id="1", game_id=extra_game, dk_eligibility="RP", role="starter"), ev(dk_id="p2", mlb_id="2", game_id="g1", dk_eligibility="SP", role="starter")]
    return pool, projs, evidence

def _lp(pool, projs, evidence):
    return load_players(pool, projs, evidence, **SLATE)

class BuilderTests(unittest.TestCase):
    def test_unknown_selected_blocks_ready_via_exclude(self):
        pool, projs, evidence = _tiny_slate()
        evidence[0]["role"] = "unknown"; evidence[0]["availability_status"] = "unresolved"; evidence[0]["conflicts"] = ["notes disagree"]
        self.assertEqual(build_one_lineup(_lp(pool, projs, evidence))["status"], "blocked")
    def test_unposted_hitter_excluded(self):
        pool, projs, evidence = _tiny_slate(unposted=True)
        self.assertEqual(build_one_lineup(_lp(pool, projs, evidence))["status"], "blocked")
    def test_scratched_hitter_excluded(self):
        pool, projs, evidence = _tiny_slate(scratch=True)
        self.assertEqual(build_one_lineup(_lp(pool, projs, evidence))["status"], "blocked")
    def test_reproducible(self):
        pool, projs, evidence = _tiny_slate()
        a = build_one_lineup(_lp(pool, projs, evidence))
        b = build_one_lineup(_lp(pool, projs, evidence))
        self.assertEqual(a["status"], "ok")
        self.assertEqual(a["lineup_hash"], b["lineup_hash"])

class FreshnessAndExportTests(unittest.TestCase):
    def test_stale_fails(self):
        r = check_freshness(as_of="2026-09-18T12:00:00+00:00", retrieved_at="2026-09-18T12:00:00+00:00", decision_time="2026-09-19T12:00:00+00:00", max_age_hours=6)
        self.assertFalse(r["ok"]); self.assertEqual(r["reason"], "stale_critical_data")
    def test_hash_mismatch_via_cli(self):
        pool, projs, evidence = _tiny_slate()
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); _write_inputs(td, pool, projs, evidence)
            code = cash_main(["--slate-date","2026-09-18","--slate-id","syn-1","--pool",str(td/"pool.csv"),"--projections",str(td/"proj.csv"),"--pitcher-evidence",str(td/"ev.json"),"--out-dir",str(td/"out"),"--expected-projection-hash","deadbeef","--decision-time","2026-09-18T18:00:00+00:00"])
            self.assertEqual(code, 2)
            man = json.loads((td/"out"/"manifest.json").read_text())
            self.assertIn("projection_hash_mismatch", man["validation"]["errors"])
            self.assertFalse((td/"out"/"lineup-1-cash.ready.json").exists())
    def test_entries_numeric_only(self):
        self.assertTrue(is_numeric_entry_id("12345678"))
        self.assertFalse(is_numeric_entry_id("Instructions"))
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); src = td/"user.csv"
            src.write_text("Entry ID,P,Contest\nInstructions,do not use,x\n111,old1,c\n222,old2,c\n333,old3,c\n444,old4,c\nPlayer Pool,,,,\n")
            parsed = parse_user_entries(src)
            self.assertEqual(len(parsed["entries"]), 4)
            dest = td/"out.csv"
            self.assertEqual(write_entries_upload(dest, [{"Entry ID": e["entry_id"]} for e in parsed["entries"]], [f"id{i}" for i in range(10)]), 4)
            self.assertEqual(len(dest.read_text().strip().splitlines()), 5)
    def test_lock_refuse(self):
        with tempfile.TemporaryDirectory() as td:
            with self.assertRaises(ValueError):
                write_entries_upload(Path(td)/"out.csv", [{"Entry ID": "111"}], [f"id{i}" for i in range(10)], locked_fields={"P": "LOCKED_ID"})
    def test_failed_build_invalidates_active_ready(self):
        pool, projs, evidence = _tiny_slate()
        with tempfile.TemporaryDirectory() as td:
            td = Path(td); _write_inputs(td, pool, projs, evidence)
            code = cash_main(["--slate-date","2026-09-18","--slate-id","syn-1","--pool",str(td/"pool.csv"),"--projections",str(td/"proj.csv"),"--pitcher-evidence",str(td/"ev.json"),"--out-dir",str(td/"out"),"--decision-time","2026-09-18T18:00:00+00:00"])
            self.assertEqual(code, 0)
            ready = td/"out"/"lineup-1-cash.ready.json"
            original = ready.read_text()
            evidence[0]["role"] = "unknown"; evidence[0]["conflicts"] = ["x"]; evidence[0]["availability_status"] = "unresolved"
            (td/"ev.json").write_text(json.dumps({"information_as_of": "2026-09-18T16:00:00+00:00", "retrieved_at": "2026-09-18T16:00:00+00:00", "pitchers": evidence}))
            cash_main(["--slate-date","2026-09-18","--slate-id","syn-1","--pool",str(td/"pool.csv"),"--projections",str(td/"proj.csv"),"--pitcher-evidence",str(td/"ev.json"),"--out-dir",str(td/"out"),"--decision-time","2026-09-18T18:00:00+00:00"])
            self.assertFalse(ready.exists())
            status = json.loads((td/"out"/"status.json").read_text())
            self.assertEqual(status["status"], "draft_blocked")
            history = list((td/"out"/"runs").glob("*/lineup-1-cash.ready.json"))
            self.assertTrue(history)
            self.assertEqual(history[0].read_text(), original)

def _write_inputs(td: Path, pool, projs, evidence):
    import csv
    with (td/"pool.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(dict.fromkeys(k for row in pool for k in row))); w.writeheader(); w.writerows(pool)
    with (td/"proj.csv").open("w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=list(projs[0].keys())); w.writeheader(); w.writerows(projs)
    (td/"ev.json").write_text(json.dumps({"information_as_of": "2026-09-18T16:00:00+00:00", "retrieved_at": "2026-09-18T16:00:00+00:00", "pitchers": evidence}))

if __name__ == "__main__":
    unittest.main()
