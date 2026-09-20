#!/usr/bin/env python3
"""Reusable slate gates / boosts learned from Sep 11–12 DK Dime Time backtests.

Used by apply_backtest_fixes.py. Does NOT touch live tonight projection files.

Formulas (documented constants from 2026-09-11 + 2026-09-12 night 195543450)
---------------------------------------------------------------------------

A) Smash-bat boost (confirmed-order + high xwOBA/barrel):
   Eligible if:
     - role is hitter (not P/SP/RP)
     - confirmed_order True (or order_status in confirmed/posted) when provided
     - PA >= MIN_PA (default 50)
     - z_xwoba >= SMASH_Z_XWOBA (default 0.5) OR z_barrel >= SMASH_Z_BARREL (default 0.75)
   Multiplier on ceiling / proj:
     raw = SMASH_XWOBA_COEF * max(0, z_xwoba) + SMASH_BARREL_COEF * max(0, z_barrel)
     # ownership-aware: low-owned smash get more boost so 40% cap doesn't crowd them out
     # Sep 12: missing ownership must NOT be treated as 0% (that max-boosted Schwarber/Vargas)
     own = ownership_proj if provided else own_proj if present else UNKNOWN
     own_factor = 1.0 if own is UNKNOWN else 1.0 + SMASH_OWN_SLOPE * max(0, SMASH_OWN_ANCHOR - own) / 100
     boost_pct = clip(raw * own_factor, 0, SMASH_MAX_BOOST)
     # Sep 12 high-proj taper: already-high raw proj (Schwarber 15 / Vargas 14.4 @ 0–5 FPTS)
     # crowded out Mitchell-class (9.24 → 38). Keep half the boost when proj >= SMASH_HIGH_PROJ.
     if proj >= SMASH_HIGH_PROJ: boost_pct *= SMASH_HIGH_PROJ_FACTOR
     adjusted = proj * (1 + boost_pct)
   Tag: smash_bat

B) Elite probable SP:
   Eligible if:
     - probable SP (or pos SP)
     - xERA <= ELITE_XERA_MAX (default 3.20) OR z_xera >= ELITE_Z_XERA (default 0.75)
   Tags: elite_sp
   Recommend exposure: TARGET_SP_EXPOSURE (0.40), soft SP1 TARGET_SP1_EXPOSURE (0.50)
   Does not silently rewrite live files — caller applies to lab copy only.

C) Dead-weight gate:
   Hitters: posted/confirmed AND proj < HITTER_FLOOR (default 5.0) → cap_1_of_20; proj < 4.0 → exclude
   Pitchers: (RP rostered as SP OR xERA >= BAD_XERA_MIN (5.0) OR proj < PITCHER_FLOOR)
             AND not elite_sp → exclude or cap_1_of_20
   Molina-type soft probable: SP quality gate fails if xERA >= MOLINA_XERA (4.5)
     or (xERA >= 4.2 and PA < 250)
     and salary >= MOLINA_SAL_MIN (7000) without elite z → exclude
   Tag: dead_weight / exclude / cap_1_of_20

Profiles (see PROFILES / get_profile)
-------------------------------------
- gpp  (default): Sep 11-12 Dime Time / GPP ceiling gates
- cash: $1-$3 MLB multipliers — soft/off smash boost, stronger SP floor,
  chalk OK, unknown ownership neutral; DK Position=RP excluded even if MLB
  probable (opener risk — Mayza 2026-09-18). GPP keeps probable override.
  Same mean proj_fp; no mid-slate live file writes.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# --- Tunable constants (Sep 11 evidence) ---
MIN_PA = 50

SMASH_Z_XWOBA = 0.50
SMASH_Z_BARREL = 0.75
SMASH_XWOBA_COEF = 0.10
SMASH_BARREL_COEF = 0.05
SMASH_OWN_ANCHOR = 12.0  # pct; below this get extra boost
SMASH_OWN_SLOPE = 0.8
SMASH_MAX_BOOST = 0.25  # +25% ceiling max
# Sep 12 night 195543450: high-proj smash (Schwarber 15.03→0, Vargas 14.40→5)
# got a full 25% bump and outranked Mitchell-class (9.24→38). Taper only.
SMASH_HIGH_PROJ = 14.0
SMASH_HIGH_PROJ_FACTOR = 0.50

ELITE_XERA_MAX = 3.20
ELITE_Z_XERA = 0.75
TARGET_SP_EXPOSURE = 0.40
TARGET_SP1_EXPOSURE = 0.50

HITTER_FLOOR = 5.0  # cap/exclude below; Sep11 Mateo blend~4.7 @ 2 FPTS
PITCHER_FLOOR = 6.0
BAD_XERA_MIN = 5.0
MOLINA_XERA = 4.50  # soft-SP exclude; 4.2 was too hot (would kill May @ 4.24)
MOLINA_SAL_MIN = 7000.0
CAP_1_OF_20 = 1

# ---------------------------------------------------------------------------
# Profiles: gpp (default) vs cash ($1-$3 multipliers)
# ---------------------------------------------------------------------------
# Cash profile (DK-MLB-MULTIPLIER-CASH-RULES.md):
# - disable smash-bat ceiling boost (floor contests don't need GPP leverage)
# - stronger elite-SP / pitcher-floor preference
# - unknown ownership already neutral in smash_bat_boost
# - dead-weight drops true non-starters
# - GPP: MLB probable SPs never RP-as-SP excluded
# - CASH (Mayza 2026-09-18 / refined 2026-09-20): cheap DK-RP openers excluded;
#   MLB-probable DK-RP with salary >= CASH_RP_BULK_MIN_SALARY allowed (Alvarez/Holmes
#   2026-09-19 overcorrection). Never elite-tag DK-RP.
# - never applied as a mid-slate live overwrite (callers write lab/ copies only)

PROFILES = {
    "gpp": {
        "SMASH_Z_XWOBA": SMASH_Z_XWOBA,
        "SMASH_Z_BARREL": SMASH_Z_BARREL,
        "SMASH_XWOBA_COEF": SMASH_XWOBA_COEF,
        "SMASH_BARREL_COEF": SMASH_BARREL_COEF,
        "SMASH_OWN_ANCHOR": SMASH_OWN_ANCHOR,
        "SMASH_OWN_SLOPE": SMASH_OWN_SLOPE,
        "SMASH_MAX_BOOST": SMASH_MAX_BOOST,
        "SMASH_HIGH_PROJ": SMASH_HIGH_PROJ,
        "SMASH_HIGH_PROJ_FACTOR": SMASH_HIGH_PROJ_FACTOR,
        "ELITE_XERA_MAX": ELITE_XERA_MAX,
        "ELITE_Z_XERA": ELITE_Z_XERA,
        "TARGET_SP_EXPOSURE": TARGET_SP_EXPOSURE,
        "TARGET_SP1_EXPOSURE": TARGET_SP1_EXPOSURE,
        "HITTER_FLOOR": HITTER_FLOOR,
        "PITCHER_FLOOR": PITCHER_FLOOR,
        "BAD_XERA_MIN": BAD_XERA_MIN,
        "MOLINA_XERA": MOLINA_XERA,
        "MOLINA_SAL_MIN": MOLINA_SAL_MIN,
        "MIN_PA": MIN_PA,
        "ELITE_SP_FLOOR_BOOST": 0.0,
        "CASH_EXCLUDE_DK_RP": False,
        "CASH_RP_BULK_MIN_SALARY": 0,
        "CASH_MIN_ELITE_SP_SALARY": 0,
        "CASH_PREFER_ACE_SALARY": 0,
    },
    "cash": {
        "SMASH_Z_XWOBA": SMASH_Z_XWOBA,
        "SMASH_Z_BARREL": SMASH_Z_BARREL,
        "SMASH_XWOBA_COEF": 0.0,
        "SMASH_BARREL_COEF": 0.0,
        "SMASH_OWN_ANCHOR": SMASH_OWN_ANCHOR,
        "SMASH_OWN_SLOPE": 0.0,
        "SMASH_MAX_BOOST": 0.0,
        "SMASH_HIGH_PROJ": SMASH_HIGH_PROJ,
        "SMASH_HIGH_PROJ_FACTOR": 0.0,
        "ELITE_XERA_MAX": 3.60,
        "ELITE_Z_XERA": 0.55,
        "TARGET_SP_EXPOSURE": 0.50,
        "TARGET_SP1_EXPOSURE": 0.60,
        "HITTER_FLOOR": HITTER_FLOOR,
        "PITCHER_FLOOR": 10.0,  # hardened after Mayza cash flop 2026-09-18
        "BAD_XERA_MIN": BAD_XERA_MIN,
        "MOLINA_XERA": MOLINA_XERA,
        "MOLINA_SAL_MIN": MOLINA_SAL_MIN,
        "MIN_PA": MIN_PA,
        "ELITE_SP_FLOOR_BOOST": 0.05,
        # Mayza 09/18: exclude cheap DK-RP openers. 09/19 postmortem: do NOT
        # blanket-exclude all DK-RP — Alvarez/Holmes were DK-RP bulk starters.
        "CASH_EXCLUDE_DK_RP": True,  # still on, but salary-gated below
        "CASH_RP_BULK_MIN_SALARY": 6000,  # MLB-probable DK-RP at/above = bulk candidate
        "CASH_MIN_ELITE_SP_SALARY": 6500,  # elite tag: true DK SP only, high salary
        "CASH_PREFER_ACE_SALARY": 9000,  # build hint: prefer ≥1 SP at/above this
    },
}


# Alias: $1–$3 DK multipliers use the cash gate profile
PROFILES["multiplier"] = PROFILES["cash"]


def get_profile(name: str = "gpp") -> dict:
    """Return a copy of named gate constants. Raises on unknown profile."""
    key = (name or "gpp").strip().lower()
    if key not in PROFILES:
        raise ValueError(f"unknown gate profile {name!r}; choose from {sorted(PROFILES)}")
    return dict(PROFILES[key])


def _cfg(profile: str | dict | None) -> dict:
    if profile is None:
        return get_profile("gpp")
    if isinstance(profile, dict):
        base = get_profile("gpp")
        base.update(profile)
        return base
    return get_profile(str(profile))


def _f(x, default=None):
    try:
        if x is None or str(x).strip() == "":
            return default
        return float(x)
    except (TypeError, ValueError):
        return default


def _clip(x, lo, hi):
    return max(lo, min(hi, x))



def _is_dk_rp_only(pos: str) -> bool:
    """True when DK primary position is RP (opener/reliever), not SP."""
    p = (pos or "").upper().strip()
    if p == "RP" or p.startswith("RP/") or p.endswith("/RP"):
        # pure RP or multi with RP but not SP
        if "SP" in p:
            return False
        return "RP" in p
    return p == "RP"

def _is_pitcher(pos: str) -> bool:
    p = (pos or "").upper()
    return p in ("P", "SP", "RP") or (
        "P" in p.split("/") and not any(h in p for h in ("C", "1B", "2B", "3B", "SS", "OF"))
    )


def _confirmed(row: dict) -> bool:
    if row.get("confirmed_order") in (True, "1", "true", "True", "yes", "Y"):
        return True
    st = (row.get("order_status") or row.get("lineup_status") or "").lower()
    if st in ("confirmed", "posted", "final", "probable"):
        # probable alone is not confirmed for smash boost — require confirmed/posted
        return st in ("confirmed", "posted", "final")
    # If no order info provided, treat as eligible (caller filters) but tag soft
    return row.get("order_unknown_ok", True)


@dataclass
class GateResult:
    dk_id: str = ""
    name: str = ""
    tags: list[str] = field(default_factory=list)
    adj_mult: float = 1.0
    adjusted_proj: float | None = None
    action: str = "keep"  # keep | exclude | cap_1_of_20
    exposure_target: float | None = None
    notes: str = ""



def _is_cash_rp_bulk_candidate(row: dict, *, probable: bool | None, salary: float, cfg: dict) -> bool:
    """MLB-probable DK-RP priced like a starter/bulk day (not Mayza-class opener).

    2026-09-19: Alvarez ($6500) / Holmes ($6300) were hard-excluded as openers but
    threw bulk and won cash. Heuristic until we have reliable IP/workload flags:
    probable + DK RP + salary >= CASH_RP_BULK_MIN_SALARY.
    """
    min_sal = cfg.get("CASH_RP_BULK_MIN_SALARY") or 0
    if not min_sal:
        return False
    if not probable:
        return False
    return salary >= min_sal


def _looks_opener_capped(row: dict, proj: float) -> bool:
    """True when means look Mayza-capped (~1 IP) rather than starter workload."""
    src = f"{row.get('source') or ''} {row.get('sources') or ''} {row.get('notes') or ''}".lower()
    if "probable_opener" in src or "mayza" in src or "opener workload" in src or "ip~1" in src:
        return True
    # crushed proj on a high-salary probable is another opener-cap smell
    return proj < 8.0


def smash_bat_boost(
    row: dict,
    *,
    z_xwoba: float | None,
    z_barrel: float | None,
    proj: float,
    ownership_proj: float | None = None,
    profile: str | dict | None = None,
) -> GateResult:
    """Apply smash-bat ceiling multiplier. See module docstring for formula."""
    cfg = _cfg(profile)
    res = GateResult(
        dk_id=str(row.get("dk_id") or ""),
        name=str(row.get("name") or ""),
        adjusted_proj=proj,
    )
    if _is_pitcher(str(row.get("pos") or row.get("position") or "")):
        return res
    # Cash profile: smash boost disabled (tag-only for stack hints if z clears)
    if cfg["SMASH_MAX_BOOST"] <= 0:
        zx = z_xwoba if z_xwoba is not None else -999.0
        zb = z_barrel if z_barrel is not None else -999.0
        if (zx >= cfg["SMASH_Z_XWOBA"] or zb >= cfg["SMASH_Z_BARREL"]) and _confirmed(row):
            res.tags.append("smash_bat")
            res.notes = "smash tag-only (cash profile: boost disabled)"
        return res
    pa = _f(row.get("pa"), 0) or 0
    min_pa = cfg["MIN_PA"]
    if pa < min_pa and row.get("pa") not in (None, ""):
        if pa and pa < min_pa:
            res.notes = "smash_skip_low_pa"
            return res
    zx = z_xwoba if z_xwoba is not None else -999.0
    zb = z_barrel if z_barrel is not None else -999.0
    if zx < cfg["SMASH_Z_XWOBA"] and zb < cfg["SMASH_Z_BARREL"]:
        return res
    if not _confirmed(row):
        res.notes = "smash_skip_unconfirmed"
        return res

    raw = cfg["SMASH_XWOBA_COEF"] * max(0.0, zx) + cfg["SMASH_BARREL_COEF"] * max(0.0, zb)
    own = ownership_proj if ownership_proj is not None else _f(row.get("own_proj"))
    if own is None:
        # unknown own is neutral — never treat as low-owned leverage
        own_factor = 1.0
        own_note = "unknown"
    else:
        own_factor = 1.0 + cfg["SMASH_OWN_SLOPE"] * max(0.0, cfg["SMASH_OWN_ANCHOR"] - own) / 100.0
        own_note = f"{own:.1f}"
    boost_pct = _clip(raw * own_factor, 0.0, cfg["SMASH_MAX_BOOST"])
    high_taper = False
    if proj >= cfg["SMASH_HIGH_PROJ"] and cfg["SMASH_HIGH_PROJ_FACTOR"] < 1.0:
        boost_pct *= cfg["SMASH_HIGH_PROJ_FACTOR"]
        high_taper = True
    res.adj_mult = 1.0 + boost_pct
    res.adjusted_proj = proj * res.adj_mult
    res.tags.append("smash_bat")
    res.notes = (
        f"smash boost_pct={boost_pct:.3f} z_xwoba={zx:.2f} z_barrel={zb:.2f} "
        f"own={own_note} own_factor={own_factor:.3f}"
        + (" high_proj_taper" if high_taper else "")
    )
    return res


def elite_sp_tag(
    row: dict,
    *,
    xera: float | None,
    z_xera: float | None,
    probable: bool | None = None,
    profile: str | dict | None = None,
) -> GateResult:
    cfg = _cfg(profile)
    res = GateResult(
        dk_id=str(row.get("dk_id") or ""),
        name=str(row.get("name") or ""),
    )
    pos = str(row.get("pos") or row.get("position") or "").upper()
    # Cash: never elite-tag DK RP (Mayza / openers) even if MLB probable
    if cfg.get("CASH_EXCLUDE_DK_RP") and _is_dk_rp_only(pos):
        return res
    # Cash: elite SP1/SP2 only from DK SP (or SP/…) with real SP salary
    if cfg.get("CASH_EXCLUDE_DK_RP"):
        salary = _f(row.get("salary"), 0) or 0
        min_sal = cfg.get("CASH_MIN_ELITE_SP_SALARY") or 0
        if "SP" not in pos:
            return res
        if min_sal and salary < min_sal:
            return res
    is_sp = pos in ("P", "SP") or "SP" in pos
    if not is_sp and not _is_pitcher(pos):
        return res
    if probable is False:
        return res
    if probable is None:
        probable = row.get("probable") in (True, "1", "true", "True", "yes") or pos == "SP"
    if not probable and pos != "SP":
        return res

    elite = False
    if xera is not None and xera <= cfg["ELITE_XERA_MAX"]:
        elite = True
    if z_xera is not None and z_xera >= cfg["ELITE_Z_XERA"]:
        elite = True
    if not elite:
        return res
    res.tags.append("elite_sp")
    res.exposure_target = cfg["TARGET_SP_EXPOSURE"]
    res.notes = (
        f"elite_sp xera={xera} z_xera={z_xera}; "
        f"target_exp={cfg['TARGET_SP_EXPOSURE']:.0%} soft_sp1={cfg['TARGET_SP1_EXPOSURE']:.0%}"
    )
    return res


def dead_weight_gate(
    row: dict,
    *,
    proj: float,
    xera: float | None = None,
    is_elite_sp: bool = False,
    probable: bool | None = None,
    profile: str | dict | None = None,
) -> GateResult:
    cfg = _cfg(profile)
    res = GateResult(
        dk_id=str(row.get("dk_id") or ""),
        name=str(row.get("name") or ""),
        adjusted_proj=proj,
    )
    pos = str(row.get("pos") or row.get("position") or "").upper()
    salary = _f(row.get("salary"), 0) or 0

    if _is_pitcher(pos):
        reasons = []
        skip_floor = False
        # Cash RP rule (refined 2026-09-20 after Alvarez/Holmes overcorrection):
        # - cheap DK-RP / non-probable → hard exclude (Mayza opener class)
        # - MLB-probable DK-RP with salary >= CASH_RP_BULK_MIN_SALARY → allow
        #   (bulk/starter day heuristic); never elite-tag DK-RP
        if cfg.get("CASH_EXCLUDE_DK_RP") and _is_dk_rp_only(pos):
            bulk = _is_cash_rp_bulk_candidate(
                row, probable=probable, salary=salary, cfg=cfg
            )
            if not bulk:
                res.tags.append("dead_weight")
                res.action = "exclude"
                res.notes = "dead_weight_p: cash_dk_rp_opener"
                return res
            res.tags.append("cash_rp_bulk_candidate")
            # If Projections still Mayza-capped means, don't dead-weight on floor alone
            # (otherwise Alvarez/Holmes stay excluded on proj~3–4). Bad xERA still kills.
            if _looks_opener_capped(row, proj):
                res.notes = (
                    f"cash_rp_bulk_candidate sal={salary:.0f}; "
                    "opener-capped means — skip floor exclude; prefer restored bulk IP"
                )
                # still apply bad xERA below; skip early return so xERA can fire
                skip_floor = True
            else:
                skip_floor = False
                res.notes = f"cash_rp_bulk_candidate sal={salary:.0f}"
        else:
            skip_floor = False
        if is_elite_sp:
            return res
        # GPP: never RP-as-SP exclude when MLB probable; cash already handled above
        if not probable:
            if _is_dk_rp_only(pos):
                reasons.append("rp_as_sp")
            if pos == "RP" and salary >= cfg["MOLINA_SAL_MIN"]:
                reasons.append("rp_sp_salary")
        if xera is not None and xera >= cfg["BAD_XERA_MIN"]:
            reasons.append(f"xera>={cfg['BAD_XERA_MIN']}")
        if proj < cfg["PITCHER_FLOOR"] and not skip_floor:
            reasons.append(f"proj<{cfg['PITCHER_FLOOR']}")
        pa = _f(row.get("pa"), 9999) or 9999
        if (
            pos in ("SP", "P", "RP")
            and xera is not None
            and salary >= cfg["MOLINA_SAL_MIN"]
            and (
                xera >= cfg["MOLINA_XERA"]
                or (xera >= 4.20 and pa < 250)
            )
            and not probable
        ):
            reasons.append(f"soft_sp_xera={xera:.2f}_pa={pa:.0f}")
        if reasons:
            res.tags.append("dead_weight")
            if any(
                r.startswith("rp_") or r.startswith("xera") or r.startswith("soft_sp")
                for r in reasons
            ):
                res.action = "exclude"
            else:
                res.action = "cap_1_of_20"
            res.notes = "dead_weight_p: " + ",".join(reasons)
        return res

    if proj < cfg["HITTER_FLOOR"]:
        res.tags.append("dead_weight")
        res.action = "exclude" if proj < 4.0 else "cap_1_of_20"
        res.notes = f"dead_weight_h: proj={proj:.2f}<{cfg['HITTER_FLOOR']}"
    return res


def apply_all_gates(
    row: dict,
    *,
    proj: float,
    z_xwoba: float | None = None,
    z_barrel: float | None = None,
    z_xera: float | None = None,
    xera: float | None = None,
    ownership_proj: float | None = None,
    probable: bool | None = None,
    profile: str | dict | None = "gpp",
) -> GateResult:
    """Compose smash boost -> elite SP tag -> dead-weight gate.

    profile: "gpp" (default) or "cash" ($1-$3 multipliers). See PROFILES.
    """
    cfg = _cfg(profile)
    smash = smash_bat_boost(
        row,
        z_xwoba=z_xwoba,
        z_barrel=z_barrel,
        proj=proj,
        ownership_proj=ownership_proj,
        profile=cfg,
    )
    adj = smash.adjusted_proj if smash.adjusted_proj is not None else proj
    elite = elite_sp_tag(
        row, xera=xera, z_xera=z_xera, probable=probable, profile=cfg
    )
    if "elite_sp" in elite.tags and cfg.get("ELITE_SP_FLOOR_BOOST", 0) > 0:
        bump = cfg["ELITE_SP_FLOOR_BOOST"]
        adj = adj * (1.0 + bump)
        smash.adj_mult = (adj / proj) if proj else smash.adj_mult
        extra = f"cash_floor_boost={bump:.0%}"
        elite.notes = (elite.notes + "; " + extra) if elite.notes else extra
    dead = dead_weight_gate(
        row,
        proj=adj,
        xera=xera,
        is_elite_sp="elite_sp" in elite.tags,
        probable=probable,
        profile=cfg,
    )

    out = GateResult(
        dk_id=str(row.get("dk_id") or ""),
        name=str(row.get("name") or ""),
        tags=[],
        adj_mult=smash.adj_mult,
        adjusted_proj=adj,
        action=dead.action,
        exposure_target=elite.exposure_target,
        notes="; ".join(n for n in (smash.notes, elite.notes, dead.notes) if n),
    )
    out.tags.extend(smash.tags)
    out.tags.extend(elite.tags)
    out.tags.extend(dead.tags)
    if dead.action != "keep":
        out.action = dead.action
    return out



# Export constants for response docs (GPP defaults). Prefer get_profile(name).
CONSTANTS = get_profile("gpp")
