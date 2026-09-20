#!/usr/bin/env python3
"""Build 50 DK Classic lineups from Savant-uplift projections.
Hard rules from DK-MLB-CLASSIC-RULES.md:
- max 5 hitters/team (pitchers excluded)
- $50k, 2P/C/1B/2B/3B/SS/3OF
- >=2 games
- validate every row before writing
"""
from __future__ import annotations
import csv, math, random
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/home/box/mlb-dfs")
OUT = ROOT / "lineups-50-savant-tonight.csv"
OUT_SUM = ROOT / "lineups-50-savant-tonight-summary.txt"
SLOTS = ["P","P","C","1B","2B","3B","SS","OF","OF","OF"]
CAP = 50000
N = 50
MAX_EXP = 20  # 40%
MAX_HITTERS_PER_TEAM = 5
RNG = random.Random(11)

def load():
    pool = list(csv.DictReader(open(ROOT/"dk-classic-player-pool.csv")))
    proj = {int(r["dk_id"]): r for r in csv.DictReader(open(ROOT/"projections-tonight.csv"))}
    players = []
    for p in pool:
        pid = int(p["ID"])
        if pid not in proj:
            continue
        pr = proj[pid]
        elig = set(p["Roster Position"].split("/"))
        gi = p["Game Info"]
        gk = gi.split()[0]
        away, home = gk.split("@")
        team = p["TeamAbbrev"]
        opp = home if team == away else away
        fp = float(pr["proj_fp"])
        sal = int(p["Salary"])
        players.append({
            "id": pid, "name": p["Name"], "sal": sal, "team": team, "opp": opp,
            "game": gk, "elig": elig, "pos": p["Position"],
            "is_p": ("P" in elig and p["Position"] in ("SP","RP")),
            "proj": fp, "vol": (pr.get("volatility") or "M")[0],
            "val": fp / max(sal, 1) * 1000,
            "label": f"{p['Name']} ({pid})",
        })
    return players

def hitters_of(roster):
    return [roster["C"], roster["1B"], roster["2B"], roster["3B"], roster["SS"]] + roster["OF"]

def all_players(roster):
    return roster["P"] + hitters_of(roster)

def validate(roster, pool_ids):
    plist = all_players(roster)
    if len(plist) != 10:
        return False, "count"
    if len({p["id"] for p in plist}) != 10:
        return False, "dup"
    sal = sum(p["sal"] for p in plist)
    if sal > CAP:
        return False, "salary"
    for p in roster["P"]:
        if not p["is_p"] or "P" not in p["elig"] or p["id"] not in pool_ids:
            return False, "pitcher"
    for s in ("C","1B","2B","3B","SS"):
        if s not in roster[s]["elig"] or roster[s]["id"] not in pool_ids:
            return False, f"slot-{s}"
    for p in roster["OF"]:
        if "OF" not in p["elig"] or p["id"] not in pool_ids:
            return False, "of"
    tc = Counter(h["team"] for h in hitters_of(roster))
    if any(c > MAX_HITTERS_PER_TEAM for c in tc.values()):
        return False, "team5"
    if len({p["game"] for p in plist}) < 2:
        return False, "games"
    return True, "ok"

def main():
    players = load()
    by_id = {p["id"]: p for p in players}
    pool_ids = set(by_id)
    pitchers = sorted(
        [p for p in players if p["is_p"] and p["elig"] == {"P"} and p["proj"] >= 8.0],
        key=lambda x: -x["proj"],
    )
    hitters = [p for p in players if "P" not in p["elig"] and p["proj"] >= 5.0]
    by_slot = defaultdict(list)
    for h in hitters:
        for s in h["elig"]:
            if s in ("C","1B","2B","3B","SS","OF"):
                by_slot[s].append(h)
    for s in by_slot:
        by_slot[s].sort(key=lambda x: (-x["proj"], -x["val"]))
        by_slot[s] = by_slot[s][:100]

    team_hit = defaultdict(list)
    for h in hitters:
        team_hit[h["team"]].append(h)
    for t in team_hit:
        team_hit[t].sort(key=lambda x: -x["proj"])
    strong_teams = sorted(
        team_hit.keys(),
        key=lambda t: sum(x["proj"] for x in team_hit[t][:4]),
        reverse=True,
    )

    pairs = []
    for i, a in enumerate(pitchers[:20]):
        for b in pitchers[i+1:24]:
            if a["team"] == b["team"]:
                continue
            if not (12000 <= a["sal"] + b["sal"] <= 20000):
                continue
            pairs.append((a, b))
    RNG.shuffle(pairs)
    print(f"pitchers={len(pitchers)} pairs={len(pairs)} hitters={len(hitters)}", flush=True)

    lineups = []
    seen = set()
    exp = Counter()
    pair_used = Counter()

    def over(pid):
        return exp[pid] >= MAX_EXP

    def score(h, stack, gpp):
        s = h["proj"] * 1.2 + h["val"] * 2.0
        if gpp:
            s += {"L": 0, "M": 0.4, "H": 0.9}.get(h["vol"], 0.3)
        if h["team"] == stack:
            s += 4.0
        s -= exp[h["id"]] * 0.9
        s += RNG.uniform(-0.8, 0.8)
        return s

    def try_one(pa, pb, stack, stack_n, gpp, min_sal):
        used = {pa["id"], pb["id"]}
        sal = pa["sal"] + pb["sal"]
        roster = {"P":[pa,pb],"C":None,"1B":None,"2B":None,"3B":None,"SS":None,"OF":[]}
        team_hitters = Counter()
        stack_n = min(stack_n, MAX_HITTERS_PER_TEAM)

        def can_add(h):
            return team_hitters[h["team"]] < MAX_HITTERS_PER_TEAM

        stack_pool = [h for h in team_hit.get(stack, []) if h["id"] not in used and not over(h["id"])][:12]
        placed = 0
        for h in stack_pool:
            if placed >= stack_n:
                break
            for slot in ("C","SS","3B","2B","1B","OF"):
                if slot == "OF":
                    if len(roster["OF"]) >= 3:
                        continue
                elif roster[slot] is not None:
                    continue
                if slot not in h["elig"]:
                    continue
                if not can_add(h):
                    continue
                empties = sum(1 for s in ("C","1B","2B","3B","SS") if roster[s] is None and s != slot)
                empties += max(0, 3 - len(roster["OF"]) - (1 if slot == "OF" else 0))
                if sal + h["sal"] + empties * 2000 > CAP:
                    continue
                if slot == "OF":
                    roster["OF"].append(h)
                else:
                    roster[slot] = h
                used.add(h["id"]); sal += h["sal"]; placed += 1
                team_hitters[h["team"]] += 1
                break

        order = [s for s in ("C","SS","3B","2B","1B") if roster[s] is None]
        order += ["OF"] * (3 - len(roster["OF"]))
        for slot in order:
            cands = []
            for h in by_slot[slot]:
                if h["id"] in used:
                    continue
                if over(h["id"]) and len(lineups) > 5:
                    continue
                if slot not in h["elig"]:
                    continue
                if not can_add(h):
                    continue
                empties = sum(1 for s in ("C","1B","2B","3B","SS") if roster[s] is None and s != slot)
                empties += max(0, 3 - len(roster["OF"]) - (1 if slot == "OF" else 0))
                if sal + h["sal"] + empties * 2000 > CAP:
                    continue
                cands.append((score(h, stack, gpp), h))
            if not cands:
                return None
            cands.sort(reverse=True, key=lambda x: x[0])
            top = cands[:8]
            weights = [math.exp(min(sc, 40) / 5) for sc, _ in top]
            h = RNG.choices([x[1] for x in top], weights=weights, k=1)[0]
            if slot == "OF":
                roster["OF"].append(h)
            else:
                roster[slot] = h
            used.add(h["id"]); sal += h["sal"]
            team_hitters[h["team"]] += 1

        if any(roster[s] is None for s in ("C","1B","2B","3B","SS")):
            return None
        if len(roster["OF"]) != 3 or sal > CAP:
            return None

        # salary upgrades without breaking team cap
        if sal < min_sal:
            for _ in range(6):
                improved = False
                for slot in ("OF","1B","3B","2B","SS","C"):
                    curs = roster["OF"] if slot == "OF" else [roster[slot]]
                    for i, cur in enumerate(curs):
                        room = CAP - sal
                        best = None; bestg = 0.35
                        for h in by_slot[slot][:40]:
                            if h["id"] in used or over(h["id"]):
                                continue
                            if slot not in h["elig"]:
                                continue
                            if h["team"] != cur["team"] and team_hitters[h["team"]] >= MAX_HITTERS_PER_TEAM:
                                continue
                            d = h["sal"] - cur["sal"]
                            if d <= 0 or d > room:
                                continue
                            g = h["proj"] - cur["proj"]
                            if h["team"] == stack:
                                g += 0.4
                            if g > bestg:
                                bestg = g; best = h
                        if best:
                            sal += best["sal"] - cur["sal"]
                            used.remove(cur["id"]); used.add(best["id"])
                            team_hitters[cur["team"]] -= 1
                            team_hitters[best["team"]] += 1
                            if slot == "OF":
                                roster["OF"][i] = best
                            else:
                                roster[slot] = best
                            improved = True
                if not improved:
                    break

        ok, reason = validate(roster, pool_ids)
        if not ok:
            return None
        return roster, sal

    def key(roster):
        ids = sorted(p["id"] for p in roster["P"])
        ids += [roster[s]["id"] for s in ("C","1B","2B","3B","SS")]
        ids += sorted(p["id"] for p in roster["OF"])
        return tuple(ids)

    def differ2(a, b):
        sa = {p["id"] for p in all_players(a)}
        sb = {p["id"] for p in all_players(b)}
        return len(sa - sb) >= 2

    attempts = 0
    while len(lineups) < N and attempts < 15000:
        attempts += 1
        pa, pb = pairs[attempts % len(pairs)]
        if over(pa["id"]) or over(pb["id"]):
            okp = [pr for pr in pairs if not over(pr[0]["id"]) and not over(pr[1]["id"])]
            pa, pb = RNG.choice(okp or pairs)
        stack = RNG.choice([pa["opp"], pb["opp"]] + strong_teams[:8])
        stack_n = min(MAX_HITTERS_PER_TEAM, RNG.choice([2,3,3,4,4,3]))
        gpp = (len(lineups) % 3) != 0
        min_sal = RNG.choice([46000,47000,47500,48000,48500,49000])
        res = try_one(pa, pb, stack, stack_n, gpp, min_sal)
        if not res:
            continue
        roster, sal = res
        k = key(roster)
        if k in seen:
            continue
        if any(not differ2(roster, prev) for prev in lineups):
            continue
        seen.add(k)
        lineups.append(roster)
        pair_used[tuple(sorted((pa["id"], pb["id"])))] += 1
        for p in all_players(roster):
            exp[p["id"]] += 1
        if len(lineups) % 10 == 0:
            print(f"built {len(lineups)} attempts={attempts}", flush=True)

    # rescue rounds
    for rround in range(1, 10):
        if len(lineups) >= N:
            break
        print(f"rescue {rround} have={len(lineups)}", flush=True)
        for _ in range(4000):
            if len(lineups) >= N:
                break
            pa, pb = RNG.choice(pairs)
            stack = RNG.choice(strong_teams[:12] + [pa["opp"], pb["opp"]])
            res = try_one(pa, pb, stack, RNG.choice([2,3,4]), True, 45000)
            if not res:
                continue
            roster, sal = res
            k = key(roster)
            if k in seen:
                continue
            if any({p["id"] for p in all_players(roster)} == {p["id"] for p in all_players(prev)} for prev in lineups):
                continue
            seen.add(k); lineups.append(roster)
            for p in all_players(roster):
                exp[p["id"]] += 1

    if len(lineups) < N:
        global MAX_EXP
        print("last ditch relax exposure", flush=True)
        MAX_EXP = 30
        for _ in range(8000):
            if len(lineups) >= N:
                break
            pa, pb = RNG.choice(pairs)
            stack = RNG.choice(strong_teams)
            res = try_one(pa, pb, stack, 3, True, 44000)
            if not res:
                continue
            roster, sal = res
            k = key(roster)
            if k in seen:
                continue
            seen.add(k); lineups.append(roster)
            for p in all_players(roster):
                exp[p["id"]] += 1

    assert len(lineups) >= N, f"only {len(lineups)}"
    lineups = lineups[:N]

    # FINAL VALIDATION — do not write if any fail
    pass_n = fail_n = 0
    fails = []
    sals = []; projs = []
    for i, roster in enumerate(lineups, 1):
        ok, reason = validate(roster, pool_ids)
        if ok:
            pass_n += 1
        else:
            fail_n += 1
            fails.append((i, reason))
        plist = all_players(roster)
        sals.append(sum(p["sal"] for p in plist))
        projs.append(sum(p["proj"] for p in plist))

    if fail_n:
        raise SystemExit(f"VALIDATION FAILED: {fail_n} bad rows: {fails[:10]}")

    # write only after all pass
    with open(OUT, "w", newline="") as f:
        w = csv.writer(f)
        w.writerow(SLOTS)
        for roster in lineups:
            ps = sorted(roster["P"], key=lambda x: (-x["proj"], -x["sal"]))
            ofs = sorted(roster["OF"], key=lambda x: (-x["proj"], -x["sal"]))
            w.writerow([
                ps[0]["label"], ps[1]["label"],
                roster["C"]["label"], roster["1B"]["label"], roster["2B"]["label"],
                roster["3B"]["label"], roster["SS"]["label"],
                ofs[0]["label"], ofs[1]["label"], ofs[2]["label"],
            ])

    # recount exposure from final set
    exp = Counter()
    for roster in lineups:
        for p in all_players(roster):
            exp[p["id"]] += 1
    exp_list = []
    for pid, c in exp.most_common():
        p = by_id[pid]
        exp_list.append((p["name"], c, 100.0 * c / N, p["proj"], p["sal"]))
    over40 = [e for e in exp_list if e[2] > 40.0001]

    summary = [
        f"lineup_count: {len(lineups)}",
        f"salary_min: {min(sals)}",
        f"salary_avg: {sum(sals)/len(sals):.1f}",
        f"salary_max: {max(sals)}",
        f"proj_fp_sum_min: {min(projs):.2f}",
        f"proj_fp_sum_avg: {sum(projs)/len(projs):.2f}",
        f"proj_fp_sum_max: {max(projs):.2f}",
        f"unique_lineups: {len(seen)}",
        f"unique_pitcher_pairs: {len(pair_used)}",
        f"validation_pass: {pass_n}",
        f"validation_fail: {fail_n}",
        f"max_hitters_per_team_enforced: {MAX_HITTERS_PER_TEAM}",
        f"min_games_enforced: 2",
        "",
        "top_15_player_exposures:",
    ]
    for name, c, pct, proj, sal in exp_list[:15]:
        summary.append(f"  {name}: {c}/{N} ({pct:.1f}%) proj={proj} sal={sal}")
    summary.append("")
    if over40:
        summary.append("players_over_40pct_exposure:")
        for name, c, pct, _, _ in over40:
            summary.append(f"  {name}: {c}/{N} ({pct:.1f}%)")
    else:
        summary.append("players_over_40pct_exposure: none")
    OUT_SUM.write_text("\n".join(summary) + "\n")
    print("\n".join(summary), flush=True)
    print(f"WROTE {OUT}", flush=True)

if __name__ == "__main__":
    main()
