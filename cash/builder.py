"""Deterministic single cash lineup from frozen inputs.

Objective (honest): maximize documented provisional mean proj_fp
subject to DK Classic roster rules. Not cash-probability or a calibrated floor.
"""

from __future__ import annotations

import itertools
from collections import Counter
from dataclasses import dataclass
from typing import Any

from cash.evidence import hash_obj, index_evidence
from cash.workload import apply_innings_to_pitcher_fp, resolve_workload

SLOTS = ["P", "P", "C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]
SALARY_CAP = 50000
MAX_HITTERS_PER_TEAM = 5
HITTER_POS = {"C", "1B", "2B", "3B", "SS", "OF"}


def primary_pos(position: str) -> str:
    return (position or "").split("/")[0].strip().upper()


def eligible_positions(position: str) -> set[str]:
    parts = {(p or "").strip().upper() for p in (position or "").split("/")}
    if "SP" in parts or "RP" in parts or "P" in parts:
        parts.add("P")
    return parts


def parse_game_id_from_info(game_info: str) -> str:
    return (game_info or "").split(" ", 1)[0]


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
    per_inning_skill: float | None = None
    workload: dict | None = None
    exclude_reason: str | None = None
    notes: str = ""


def load_players(
    pool_rows: list[dict],
    proj_rows: list[dict],
    evidence_rows: list[dict],
    *,
    require_posted_hitters: bool = True,
) -> list[Player]:
    proj_by_id = {str(r.get("dk_id") or r.get("ID") or ""): r for r in proj_rows}
    ev_idx = index_evidence(evidence_rows)
    players: list[Player] = []
    for r in pool_rows:
        dk_id = str(r.get("ID") or r.get("dk_id") or "")
        pos = r.get("Position") or r.get("position") or ""
        team = r.get("TeamAbbrev") or r.get("team") or ""
        game_info = r.get("Game Info") or r.get("game_info") or ""
        game_id = str(r.get("game_id") or parse_game_id_from_info(game_info))
        salary = int(float(r.get("Salary") or r.get("salary") or 0))
        name = r.get("Name") or r.get("name") or ""
        pr = proj_by_id.get(dk_id, {})
        raw = float(pr.get("proj_fp") or pr.get("raw_proj") or r.get("proj_fp") or 0)
        posted = str(pr.get("posted") or r.get("posted") or r.get("order_status") or "").lower() in (
            "1", "true", "yes", "posted", "confirmed", "final",
        )
        if str(r.get("posted") or "").lower() in ("1", "true", "yes"):
            posted = True
        scratched = str(r.get("scratched") or pr.get("scratched") or "").lower() in ("1", "true", "yes")
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
            notes=str(pr.get("notes") or ""),
        )
        if is_p:
            ev = ev_idx.get(dk_id) or ev_idx.get(f"{r.get('mlb_id')}:{game_id}")
            if ev is None:
                p.exclude_reason = "no_pitcher_evidence"
                p.proj = raw
            else:
                dec = resolve_workload(ev)
                p.workload = dec.as_dict()
                skill = ev.get("per_inning_skill")
                if skill is None:
                    ip = dec.expected_ip or 1.0
                    skill = raw / ip if ip else 0.0
                    p.notes = (p.notes + "; provisional_skill_from_mean").strip("; ")
                p.per_inning_skill = float(skill)
                p.proj = apply_innings_to_pitcher_fp(p.per_inning_skill, dec.expected_ip)
                if not dec.cash_eligible:
                    p.exclude_reason = dec.reason
        else:
            if scratched:
                p.exclude_reason = "scratched"
            elif require_posted_hitters and not posted:
                p.exclude_reason = "unposted_hitter"
        players.append(p)
    return players


def _legal(lineup: list[Player]) -> tuple[bool, str]:
    if len({p.dk_id for p in lineup}) != 10:
        return False, "duplicate"
    if sum(p.salary for p in lineup) > SALARY_CAP:
        return False, "salary"
    hitters = [p for p in lineup if not p.is_pitcher]
    if any(c > MAX_HITTERS_PER_TEAM for c in Counter(p.team for p in hitters).values()):
        return False, "team_hitter_cap"
    games = {p.game_id for p in lineup}
    if "" in games:
        return False, "missing_game"
    return True, "ok"


def _greedy_lineup(pitchers: list[Player], hitters: list[Player]) -> list[Player] | None:
    if len(pitchers) < 2:
        return None
    for i, p1 in enumerate(pitchers):
        for p2 in pitchers[i + 1 :]:
            chosen = [p1, p2]
            used = {p1.dk_id, p2.dk_id}
            team_n: Counter[str] = Counter()
            sal = p1.salary + p2.salary
            ok = True
            for slot in ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]:
                pick = None
                for h in hitters:
                    if h.dk_id in used:
                        continue
                    if slot not in eligible_positions(h.position):
                        continue
                    if sal + h.salary > SALARY_CAP:
                        continue
                    if team_n[h.team] + 1 > MAX_HITTERS_PER_TEAM:
                        continue
                    pick = h
                    break
                if pick is None:
                    ok = False
                    break
                chosen.append(pick)
                used.add(pick.dk_id)
                team_n[pick.team] += 1
                sal += pick.salary
            if ok:
                legal, _ = _legal(chosen)
                if legal:
                    return chosen
    return None


def build_one_lineup(players: list[Player], *, seed: str = "task001") -> dict[str, Any]:
    """Deterministic sort + greedy fill. Exact search only on tiny slates."""
    pool = [p for p in players if not p.exclude_reason]
    pitchers = [p for p in pool if p.is_pitcher]
    hitters = [p for p in pool if not p.is_pitcher]
    pitchers.sort(key=lambda p: (-p.proj, p.dk_id))
    hitters.sort(key=lambda p: (-p.proj, p.dk_id))

    by_slot: dict[str, list[Player]] = {s: [] for s in HITTER_POS}
    for h in hitters:
        for pos in eligible_positions(h.position):
            if pos in by_slot:
                by_slot[pos].append(h)

    best: tuple | None = None
    best_lu: list[Player] | None = None
    n_checked = 0

    greedy = _greedy_lineup(pitchers, hitters)
    if greedy is not None and len(hitters) > 16:
        best_lu = greedy
        best = (round(sum(p.proj for p in greedy), 4), ",".join(sorted(p.dk_id for p in greedy)))
        n_checked = 1
        p_pairs = []
    else:
        p_pairs = list(itertools.combinations(pitchers[:12], 2))

    for p1, p2 in p_pairs:
        if p1.dk_id == p2.dk_id:
            continue
        remain_sal = SALARY_CAP - p1.salary - p2.salary
        used = {p1.dk_id, p2.dk_id}

        def pick(slots_left: list[str], chosen: list[Player], sal_left: int):
            nonlocal best, best_lu, n_checked
            if not slots_left:
                n_checked += 1
                lu = [p1, p2] + chosen
                ok, why = _legal(lu)
                if not ok:
                    return
                score = sum(p.proj for p in lu)
                ids = ",".join(sorted(p.dk_id for p in lu))
                key = (round(score, 4), ids)
                if best is None or key > best:
                    best = key
                    best_lu = lu
                return
            slot = slots_left[0]
            cands = [c for c in by_slot[slot] if c.dk_id not in used and c.salary <= sal_left][:8]
            if not cands:
                return
            for c in cands:
                used.add(c.dk_id)
                pick(slots_left[1:], chosen + [c], sal_left - c.salary)
                used.remove(c.dk_id)

        pick(["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"], [], remain_sal)

    if best_lu is None:
        return {
            "status": "blocked",
            "reason": "no_valid_lineup",
            "n_checked": n_checked,
            "excluded_pitchers": [
                {"dk_id": p.dk_id, "name": p.name, "reason": p.exclude_reason, "workload": p.workload}
                for p in players if p.is_pitcher and p.exclude_reason
            ],
        }

    assigned: list[tuple[str, Player]] = [("P", best_lu[0]), ("P", best_lu[1])]
    bats = best_lu[2:]
    taken = set()
    for slot in ["C", "1B", "2B", "3B", "SS", "OF", "OF", "OF"]:
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
            "proj": round(p.proj, 4),
            "raw_proj": round(p.raw_proj, 4),
            "workload": p.workload,
        }
        for slot, p in assigned
    ]
    return {
        "status": "ok",
        "objective": "max_provisional_mean_proj_fp",
        "seed": seed,
        "salary": sum(p.salary for _, p in assigned),
        "proj_sum": round(sum(p.proj for _, p in assigned), 4),
        "lineup": lineup_rows,
        "n_checked": n_checked,
        "tie_break": "proj desc then sorted dk_id set",
        "excluded_pitchers": [
            {"dk_id": p.dk_id, "name": p.name, "reason": p.exclude_reason, "workload": p.workload}
            for p in players if p.is_pitcher and p.exclude_reason
        ],
        "selected_pitcher_workload": [p.workload for p in best_lu if p.is_pitcher],
        "lineup_hash": hash_obj([r["dk_id"] for r in lineup_rows] + [round(sum(p.proj for _, p in assigned), 4)]),
    }
