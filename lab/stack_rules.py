#!/usr/bin/env python3
"""Simple stack / correlation rules for DK MLB Classic (lab-side).

DK hard rule: max 5 hitters per MLB team (pitchers do not count).
See /home/box/mlb-dfs/DK-MLB-CLASSIC-RULES.md.

Sep 11 winner pattern (#1 $100 Dime Time):
  Sale + May SP combo with Contreras / Chourio / Tucker / Mitchell —
  game stacks (MIL smash) + bring-back (LAD Tucker) + chalk dual-SP.

Recommended patterns (documentation + helpers; sim bonus optional elsewhere):
  1. Primary team stack: 3–5 hitters same team (prefer high-total / smash bats)
  2. Game stack: 3–4 hitters from one game + opposing bring-back 1–2
  3. Dual-SP correlation: two elite/probable SPs whose offenses are stacked
     or weakly correlated (Sale+May style)
  4. Bring-back: 1–2 hitters from opponent of primary stack
  5. Avoid mini-stacks of dead-weight (see slate_gates.dead_weight_gate)

Optional Monte Carlo stack bonus (default OFF — keep existing MC comparable):
  If a lineup has >= MIN_STACK_HITTERS from one team, add STACK_BONUS_PTS
  to that lineup's sampled total (simulates correlated upside, not true joint dist).
"""

from __future__ import annotations

from collections import Counter
from typing import Iterable

# Soft scoring constants (documentation / optional sim)
MIN_STACK_HITTERS = 3
MAX_STACK_HITTERS = 5  # DK hard cap
STACK_BONUS_PTS = 2.5  # per hitter above (MIN_STACK_HITTERS-1) when bonus enabled
BRING_BACK_BONUS_PTS = 1.5
DUAL_SP_BONUS_PTS = 1.0


def count_team_hitters(teams: Iterable[str]) -> Counter:
    """Count hitters by team (pass only hitter team codes)."""
    return Counter(t for t in teams if t)


def valid_team_hitter_cap(team_hitter_counts: Counter, max_per_team: int = MAX_STACK_HITTERS) -> bool:
    return all(c <= max_per_team for c in team_hitter_counts.values())


def primary_stack_size(team_hitter_counts: Counter) -> tuple[str | None, int]:
    if not team_hitter_counts:
        return None, 0
    team, n = team_hitter_counts.most_common(1)[0]
    return team, n


def stack_bonus_points(
    team_hitter_counts: Counter,
    *,
    bring_back_teams: Iterable[str] | None = None,
    dual_elite_sp: bool = False,
    enabled: bool = False,
) -> float:
    """Optional additive bonus for sim. Default enabled=False."""
    if not enabled:
        return 0.0
    bonus = 0.0
    team, n = primary_stack_size(team_hitter_counts)
    if team and n >= MIN_STACK_HITTERS:
        bonus += STACK_BONUS_PTS * (n - (MIN_STACK_HITTERS - 1))
    if bring_back_teams:
        bb = sum(1 for t in bring_back_teams if t and t != team)
        if bb >= 1 and n >= MIN_STACK_HITTERS:
            bonus += BRING_BACK_BONUS_PTS * min(bb, 2)
    if dual_elite_sp:
        bonus += DUAL_SP_BONUS_PTS
    return bonus


def describe_rules() -> str:
    return """Sep 11 stack ideas (lab):
1. 3–5 same-team hitters (DK max 5) around smash bats (high xwOBA/barrel).
2. Game stack + 1–2 bring-back from opponent (Tucker-style).
3. Dual elite/probable SP (Sale+May) correlated with the smash offense.
4. Prefer stacking teams with multiple smash_bat tags from slate_gates.
5. Never exceed 5 hitters/team; pitchers excluded from the cap.
"""
