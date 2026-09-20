"""Deterministic single cash lineup from frozen inputs.

Objective (honest): maximize documented provisional mean proj_fp
subject to DK Classic roster rules. Not cash-probability or a calibrated floor.

Search: exact constrained enumeration with branch-and-bound. If the node
budget is exhausted the result is labeled heuristic_bounded, never
max_provisional_mean without qualification.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from typing import Any

from cash.evidence import hash_obj, index_evidence, lookup_evidence
from cash.workload import apply_innings_to_pitcher_fp, resolve_skill_rate, resolve_workload

SLOTS = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]
HITTER_SLOTS = ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]
SALARY_CAP = 50000
MAX_HITTERS_PER_TEAM = 5
MIN_GAMES = 2
HITTER_POS = {"C", "1B", "2B", "3B", "SS", "OF"}
MAX_SEARCH_NODES = 250000


def eligible_positions(position: str) -> set[str]:
    parts = {(p or "").strip().upper() for p in (position or "").split("/")}
    if "SP" in parts or "RP" in parts or "P" in parts:
        parts.add("P")
    return parts


def _truthy(val: Any) -> bool:
    return str(val or "").lower() in ("1", "true", "yes", "posted", "confirmed", "final")


@dataclass
class Player:
    dk_id: str
    name: str
    position: str
    team: str
    salary: int
    game_id: str
    game_info: str
    raw_proj: float
    proj: float
    posted: bool
    scratched: bool
    is_pitcher: bool
    mlb_id: str = ""
    slate_id: str = ""
    slate_date: str = ""
    per_inning_skill: float | None = None
    skill_source: str = ""
    workload: dict | None = None
    exclude_reason: str | None = None
    notes: str = ""
    evidence_errors: list | None = None


def load_players(
    pool_rows: list[dict],
    proj_rows: list[dict],
    evidence_rows: list[dict],
    *,
    require_posted_hitters: bool = True,
    slate_id: str | None = None,
    slate_date: str | None = None,
) -> list[Player]:
    proj_by_id = {str(r.get("dk_id") or r.get("ID") or ""): r for r in proj_rows}
    req_slate = str(slate_id or "")
    req_date = str(slate_date or "")
    ev_idx = index_evidence(evidence_rows, slate_id=req_slate, slate_date=req_date) if req_slate and req_date else {}
    players: list[Player] = []
    for r in pool_rows:
        dk_id = str(r.get("ID") or r.get("dk_id") or "")
        pos = r.get("Position") or r.get("position") or ""
        team = r.get("TeamAbbrev") or r.get("team") or ""
        game_info = r.get("Game Info") or r.get("game_info") or ""
        game_id = str(r.get("game_id") or "").strip()
        salary = int(float(r.get("Salary") or r.get("salary") or 0))
        name = r.get("Name") or r.get("name") or ""
        mlb_id = str(r.get("mlb_id") or r.get("MLBID") or "").strip()
        row_slate = str(r.get("slate_id") or req_slate)
        row_date = str(r.get("slate_date") or req_date)
        pr = proj_by_id.get(dk_id, {})
        raw = float(pr.get("proj_fp") or pr.get("raw_proj") or r.get("proj_fp") or 0)
        posted = _truthy(pr.get("posted") or r.get("posted") or r.get("order_status"))
        scratched = _truthy(r.get("scratched") or pr.get("scratched"))
        is_p = bool(eligible_positions(pos) & {"P", "SP", "RP"})
        p = Player(
            dk_id=dk_id,
            name=name,
            position=pos,
            team=team,
            salary=salary,
            game_id=game_id,
            game_info=game_info,
            raw_proj=raw,
            proj=raw,
            posted=posted,
            scratched=scratched,
            is_pitcher=is_p,
            mlb_id=mlb_id,
            slate_id=row_slate,
            slate_date=row_date,
            notes=str(pr.get("notes") or ""),
        )
        if req_slate and row_slate and row_slate != req_slate:
            p.exclude_reason = "wrong_slate_pool_row"
        if req_date and row_date and row_date != req_date:
            p.exclude_reason = "wrong_slate_date_pool_row"
        proj_slate = str(pr.get("slate_id") or req_slate)
        if req_slate and pr and proj_slate and proj_slate != req_slate:
            p.exclude_reason = "wrong_slate_projection"
        if not game_id:
            p.exclude_reason = "missing_game_id"
        if scratched:
            p.exclude_reason = "scratched"
        if is_p:
            ev = lookup_evidence(
                ev_idx,
                slate_date=req_date,
                slate_id=req_slate,
                game_id=game_id,
                mlb_id=mlb_id,
                dk_id=dk_id,
            )
            if ev is None:
                p.exclude_reason = p.exclude_reason or "no_pitcher_evidence"
            else:
                p.evidence_errors = list(ev.get("_schema_errors") or [])
                dec = resolve_workload(ev)
                p.workload = dec.as_dict()
                skill, skill_src = resolve_skill_rate(ev, raw, dec.expected_ip)
                if skill is None:
                    p.exclude_reason = p.exclude_reason or skill_src
                    p.skill_source = skill_src
                    p.proj = raw
                else:
                    p.per_inning_skill = float(skill)
                    p.skill_source = skill_src
                    p.proj = apply_innings_to_pitcher_fp(p.per_inning_skill, dec.expected_ip)
                    if skill_src != "evidenced_per_inning_skill":
                        p.notes = (p.notes + f"; {skill_src}").strip("; ")
                if not dec.cash_eligible:
                    p.exclude_reason = p.exclude_reason or dec.reason
        else:
            if p.exclude_reason:
                pass
            elif require_posted_hitters and not posted:
                p.exclude_reason = "unposted_hitter"
        players.append(p)
    return players


def _legal(lineup: list[Player]) -> tuple[bool, str]:
    if len(lineup) != 10:
        return False, "size"
    if len({p.dk_id for p in lineup}) != 10:
        return False, "duplicate"
    if any(p.exclude_reason for p in lineup):
        return False, "excluded_selected"
    if any(p.scratched for p in lineup):
        return False, "scratched"
    if not all(isinstance(p.salary, int) and p.salary > 0 for p in lineup):
        return False, "bad_salary"
    if any(p.proj != p.proj or p.proj == float("inf") for p in lineup):
        return False, "nonfinite_proj"
    if sum(p.salary for p in lineup) > SALARY_CAP:
        return False, "salary"
    hitters = [p for p in lineup if not p.is_pitcher]
    if len(hitters) != 8:
        return False, "hitter_count"
    if any(c > MAX_HITTERS_PER_TEAM for c in Counter(p.team for p in hitters).values()):
        return False, "team_hitter_cap"
    games = {p.game_id for p in lineup}
    if "" in games or None in games:
        return False, "missing_game"
    if len(games) < MIN_GAMES:
        return False, "min_games"
    return True, "ok"


def _optimize(pitchers: list[Player], hitters: list[Player]) -> tuple[list[Player] | None, int, str]:
    pitchers = sorted(pitchers, key=lambda p: (-p.proj, p.dk_id))
    hitters = sorted(hitters, key=lambda p: (-p.proj, p.dk_id))
    by_slot: dict[str, list[Player]] = {s: [] for s in HITTER_POS}
    for h in hitters:
        for pos in eligible_positions(h.position):
            if pos in by_slot:
                by_slot[pos].append(h)
    for s in by_slot:
        by_slot[s].sort(key=lambda p: (-p.proj, p.dk_id))

    best_key: tuple | None = None
    best_lu: list[Player] | None = None
    n_checked = 0
    nodes = 0
    truncated = False

    slot_best = [max((h.proj for h in by_slot[s]), default=0.0) for s in HITTER_SLOTS]

    def bound(slot_i: int, cur_proj: float) -> float:
        return cur_proj + sum(slot_best[slot_i:])

    def rec(slot_i: int, chosen: list[Player], used: set[str], sal: int, team_n: Counter, proj: float):
        nonlocal best_key, best_lu, n_checked, nodes, truncated
        nodes += 1
        if nodes > MAX_SEARCH_NODES:
            truncated = True
            return
        if best_key is not None and bound(slot_i, proj) + 1e-9 < best_key[0]:
            return
        if slot_i == len(HITTER_SLOTS):
            n_checked += 1
            lu = chosen
            ok, _ = _legal(lu)
            if not ok:
                return
            ids = ",".join(sorted(p.dk_id for p in lu))
            key = (round(sum(p.proj for p in lu), 4), ids)
            if best_key is None or key > best_key:
                best_key = key
                best_lu = list(lu)
            return
        slot = HITTER_SLOTS[slot_i]
        for h in by_slot[slot]:
            if h.dk_id in used:
                continue
            if sal + h.salary > SALARY_CAP:
                continue
            if team_n[h.team] + 1 > MAX_HITTERS_PER_TEAM:
                continue
            used.add(h.dk_id)
            team_n[h.team] += 1
            rec(slot_i + 1, chosen + [h], used, sal + h.salary, team_n, proj + h.proj)
            team_n[h.team] -= 1
            used.remove(h.dk_id)
            if truncated:
                return

    for i, p1 in enumerate(pitchers):
        for p2 in pitchers[i + 1 :]:
            if p1.dk_id == p2.dk_id:
                continue
            rec(
                0,
                [p1, p2],
                {p1.dk_id, p2.dk_id},
                p1.salary + p2.salary,
                Counter(),
                p1.proj + p2.proj,
            )
            if truncated:
                break
        if truncated:
            break

    status = "heuristic_bounded" if truncated else "optimal"
    return best_lu, n_checked, status


def build_one_lineup(players: list[Player], *, seed: str = "task001") -> dict[str, Any]:
    pool = [p for p in players if not p.exclude_reason]
    pitchers = [p for p in pool if p.is_pitcher]
    hitters = [p for p in pool if not p.is_pitcher]
    best_lu, n_checked, sol = _optimize(pitchers, hitters)

    if best_lu is None:
        return {
            "status": "blocked",
            "reason": "no_valid_lineup",
            "n_checked": n_checked,
            "solution_status": sol,
            "objective": "max_provisional_mean_proj_fp",
            "excluded_pitchers": [
                {"dk_id": p.dk_id, "name": p.name, "reason": p.exclude_reason, "workload": p.workload}
                for p in players
                if p.is_pitcher and p.exclude_reason
            ],
        }

    assigned: list[tuple[str, Player]] = [("P", best_lu[0]), ("P", best_lu[1])]
    bats = best_lu[2:]
    taken: set[str] = set()
    for slot in HITTER_SLOTS:
        for b in bats:
            if b.dk_id in taken:
                continue
            if slot in eligible_positions(b.position):
                assigned.append((slot, b))
                taken.add(b.dk_id)
                break

    lineup_rows = [
        {
            "slot": slot,
            "dk_id": p.dk_id,
            "name": p.name,
            "position": p.position,
            "team": p.team,
            "salary": p.salary,
            "game_id": p.game_id,
            "mlb_id": p.mlb_id,
            "proj": round(p.proj, 4),
            "raw_proj": round(p.raw_proj, 4),
            "skill_source": p.skill_source,
            "per_inning_skill": p.per_inning_skill,
            "workload": p.workload,
        }
        for slot, p in assigned
    ]
    obj = "max_provisional_mean_proj_fp" if sol == "optimal" else "bounded_heuristic_provisional_mean"
    return {
        "status": "ok",
        "objective": obj,
        "solution_status": sol,
        "seed": seed,
        "salary": sum(p.salary for _, p in assigned),
        "proj_sum": round(sum(p.proj for _, p in assigned), 4),
        "lineup": lineup_rows,
        "n_checked": n_checked,
        "tie_break": "proj desc then sorted dk_id set",
        "excluded_pitchers": [
            {"dk_id": p.dk_id, "name": p.name, "reason": p.exclude_reason, "workload": p.workload}
            for p in players
            if p.is_pitcher and p.exclude_reason
        ],
        "selected_pitcher_workload": [p.workload for p in best_lu if p.is_pitcher],
        "lineup_hash": hash_obj([r["dk_id"] for r in lineup_rows] + [round(sum(p.proj for _, p in assigned), 4)]),
    }
