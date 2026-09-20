#!/usr/bin/env python3
"""Fast heuristic: 50 diversified DK MLB Classic lineups.
DK rule: max 5 hitters from one team per lineup (pitchers excluded).
"""
import csv, random, math
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path("/home/box/mlb-dfs")
SLOTS = ["P","P","C","1B","2B","3B","SS","OF","OF","OF"]
CAP = 50000
N = 50
MAX_EXP = 20  # 40%
MAX_TEAM_HITTERS = 5  # DK Classic: pitchers excluded
MAX_HITTERS_PER_TEAM = 5  # DK Classic: pitchers excluded
RNG = random.Random(7)

def load():
    pool = list(csv.DictReader(open(ROOT/"dk-classic-player-pool.csv")))
    proj = {int(r["dk_id"]): r for r in csv.DictReader(open(ROOT/"projections-tonight.csv"))}
    players = []
    for p in pool:
        pid = int(p["ID"])
        if pid not in proj: continue
        pr = proj[pid]
        elig = set(p["Roster Position"].split("/"))
        gi = p["Game Info"]; gk = gi.split()[0]
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
            "val": fp/max(sal,1)*1000,
            "label": f"{p['Name']} ({pid})",
        })
    return players

def main():
    players = load()
    by_id = {p["id"]: p for p in players}
    pitchers = sorted([p for p in players if p["is_p"] and p["elig"]=={"P"} and p["proj"]>=8.0],
                      key=lambda x: -x["proj"])
    hitters = [p for p in players if "P" not in p["elig"] and p["proj"]>=5.0]
    by_slot = defaultdict(list)
    for h in hitters:
        for s in h["elig"]:
            if s in ("C","1B","2B","3B","SS","OF"):
                by_slot[s].append(h)
    for s in by_slot:
        by_slot[s].sort(key=lambda x: (-x["proj"], -x["val"]))
        # trim for speed
        by_slot[s] = by_slot[s][:80]

    # team strength for stacks
    team_hit = defaultdict(list)
    for h in hitters:
        team_hit[h["team"]].append(h)
    for t in team_hit:
        team_hit[t].sort(key=lambda x: -x["proj"])

    strong_teams = sorted(team_hit.keys(),
        key=lambda t: sum(x["proj"] for x in team_hit[t][:4]), reverse=True)

    # pitcher pairs
    pairs = []
    for i, a in enumerate(pitchers[:18]):
        for b in pitchers[i+1:22]:
            if a["team"]==b["team"]: continue
            if a["sal"]+b["sal"] > 20000: continue
            if a["sal"]+b["sal"] < 13000: continue
            pairs.append((a,b))
    RNG.shuffle(pairs)
    print(f"pitchers={len(pitchers)} pairs={len(pairs)} hitters={len(hitters)}", flush=True)

    lineups = []
    seen = set()
    exp = Counter()
    pair_used = Counter()

    def over(pid):
        return exp[pid] >= MAX_EXP

    def score(h, stack, gpp):
        s = h["proj"]*1.2 + h["val"]*2.0
        if gpp:
            s += {"L":0,"M":0.4,"H":0.9}.get(h["vol"],0.3)
        if h["team"]==stack:
            s += 4.0
        # exposure penalty
        s -= exp[h["id"]] * 0.9
        s += RNG.uniform(-0.8, 0.8)
        return s

    def try_one(pa, pb, stack, stack_n, gpp, min_sal):
        used = {pa["id"], pb["id"]}
        sal = pa["sal"] + pb["sal"]
        roster = {"P":[pa,pb],"C":None,"1B":None,"2B":None,"3B":None,"SS":None,"OF":[]}
        team_hitters = Counter()  # hitters only; pitchers excluded
        stack_n = min(stack_n, MAX_HITTERS_PER_TEAM)

        def can_add_hitter(h):
            return team_hitters[h["team"]] < MAX_HITTERS_PER_TEAM

        # place stack players first
        stack_pool = [h for h in team_hit.get(stack, []) if h["id"] not in used and not over(h["id"])][:10]
        placed = 0
        for h in stack_pool:
            if placed >= stack_n: break
            for slot in ("C","SS","3B","2B","1B","OF"):
                if slot=="OF":
                    if len(roster["OF"])>=3: continue
                else:
                    if roster[slot] is not None: continue
                if slot not in h["elig"]: continue
                if sal + h["sal"] > CAP: continue
                # leave room
                empties = sum(1 for s in ("C","1B","2B","3B","SS") if roster[s] is None and s!=slot)
                empties += max(0, 3-len(roster["OF"])-(1 if slot=="OF" else 0))
                if sal + h["sal"] + empties*2000 > CAP: continue
                if not can_add_hitter(h): continue
                if slot=="OF":
                    roster["OF"].append(h)
                else:
                    roster[slot]=h
                used.add(h["id"]); sal += h["sal"]; placed += 1
                team_hitters[h["team"]] += 1
                break

        # fill remaining
        order = [s for s in ("C","SS","3B","2B","1B") if roster[s] is None]
        order += ["OF"]*(3-len(roster["OF"]))
        for slot in order:
            cands = []
            for h in by_slot[slot]:
                if h["id"] in used: continue
                if over(h["id"]) and len(lineups)>8: continue
                if slot not in h["elig"]: continue
                if not can_add_hitter(h): continue
                empties = sum(1 for s in ("C","1B","2B","3B","SS") if roster[s] is None and s!=slot)
                empties += max(0, 3-len(roster["OF"])-(1 if slot=="OF" else 0))
                if sal + h["sal"] + empties*2000 > CAP: continue
                cands.append((score(h, stack, gpp), h))
            if not cands:
                return None
            cands.sort(reverse=True, key=lambda x: x[0])
            # pick from top 8 weighted
            top = cands[:8]
            weights = [math.exp(min(sc,40)/5) for sc,_ in top]
            h = RNG.choices([x[1] for x in top], weights=weights, k=1)[0]
            if slot=="OF":
                roster["OF"].append(h)
            else:
                roster[slot]=h
            used.add(h["id"]); sal += h["sal"]
            team_hitters[h["team"]] += 1

        if any(roster[s] is None for s in ("C","1B","2B","3B","SS")): return None
        if len(roster["OF"])!=3: return None
        if sal > CAP: return None

        # cheap upgrades toward min_sal
        if sal < min_sal:
            for _ in range(6):
                improved=False
                for slot in ("OF","1B","3B","2B","SS","C"):
                    curs = roster["OF"] if slot=="OF" else [roster[slot]]
                    for i,cur in enumerate(curs):
                        room = CAP - sal
                        best=None; bestg=0.4
                        for h in by_slot[slot][:35]:
                            if h["id"] in used: continue
                            if over(h["id"]): continue
                            if slot not in h["elig"]: continue
                            # team cap: swapping same-team ok; new team needs room
                            if h["team"] != cur["team"] and team_hitters[h["team"]] >= MAX_HITTERS_PER_TEAM:
                                continue
                            d = h["sal"]-cur["sal"]
                            if d<=0 or d>room: continue
                            g = h["proj"]-cur["proj"]
                            if h["team"]==stack: g+=0.4
                            if g>bestg: bestg=g; best=h
                        if best:
                            sal += best["sal"]-cur["sal"]
                            used.remove(cur["id"]); used.add(best["id"])
                            team_hitters[cur["team"]] -= 1
                            team_hitters[best["team"]] += 1
                            if slot=="OF":
                                roster["OF"][i]=best
                            else:
                                roster[slot]=best
                            improved=True
                if not improved: break

        players_list = roster["P"]+[roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]
        if len({p["id"] for p in players_list})!=10: return None
        hit_only = [roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]
        tc = Counter(h["team"] for h in hit_only)
        if any(c > MAX_HITTERS_PER_TEAM for c in tc.values()): return None
        games = {p["game"] for p in roster["P"]+hit_only}
        if len(games) < 2: return None
        return roster, sal

    def key(roster):
        ids = sorted(p["id"] for p in roster["P"])
        ids += [roster[s]["id"] for s in ("C","1B","2B","3B","SS")]
        ids += sorted(p["id"] for p in roster["OF"])
        return tuple(ids)

    def row(roster):
        ps = sorted(roster["P"], key=lambda x: (-x["proj"], -x["sal"]))
        ofs = sorted(roster["OF"], key=lambda x: (-x["proj"], -x["sal"]))
        return [ps[0]["label"],ps[1]["label"],roster["C"]["label"],roster["1B"]["label"],
                roster["2B"]["label"],roster["3B"]["label"],roster["SS"]["label"],
                ofs[0]["label"],ofs[1]["label"],ofs[2]["label"]]

    def differ2(a,b):
        sa={p["id"] for p in a["P"]+[a["C"],a["1B"],a["2B"],a["3B"],a["SS"]]+a["OF"]}
        sb={p["id"] for p in b["P"]+[b["C"],b["1B"],b["2B"],b["3B"],b["SS"]]+b["OF"]}
        return len(sa-sb)>=2

    attempts=0
    while len(lineups)<N and attempts<12000:
        attempts+=1
        # cycle pairs for diversity
        pa,pb = pairs[attempts % len(pairs)]
        if over(pa["id"]) or over(pb["id"]):
            # try random unused-ish pair
            ok=[pr for pr in pairs if not over(pr[0]["id"]) and not over(pr[1]["id"])]
            if not ok: ok=pairs
            pa,pb = RNG.choice(ok)
        # stack: prefer vs SP
        stack_opts = [pa["opp"], pb["opp"]] + strong_teams[:8]
        stack = RNG.choice(stack_opts)
        stack_n = min(MAX_HITTERS_PER_TEAM, RNG.choice([3,3,4,3,4,2]))
        gpp = (len(lineups)%3)!=0
        min_sal = RNG.choice([46000,47000,47500,48000,48500,49000])
        res = try_one(pa,pb,stack,stack_n,gpp,min_sal)
        if not res: continue
        roster, sal = res
        k = key(roster)
        if k in seen: continue
        if any(not differ2(roster, prev) for prev in lineups):
            continue
        # accept
        seen.add(k)
        lineups.append(roster)
        pair_used[tuple(sorted((pa["id"],pb["id"])))] += 1
        for p in roster["P"]+[roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]:
            exp[p["id"]] += 1
        if len(lineups)%10==0:
            print(f"built {len(lineups)} attempts={attempts}", flush=True)

    # rescue if short — relax uniqueness to differ-by-1 and allow soft over-exp
    rround=0
    while len(lineups)<N and rround<8:
        rround+=1
        print(f"rescue {rround} have={len(lineups)}", flush=True)
        for _ in range(3000):
            if len(lineups)>=N: break
            attempts+=1
            pa,pb = RNG.choice(pairs)
            stack = RNG.choice(strong_teams[:10] + [pa["opp"], pb["opp"]])
            res = try_one(pa,pb,stack,RNG.choice([2,3,4]),True,45000)
            if not res: continue
            roster,sal=res
            k=key(roster)
            if k in seen: continue
            # differ by >=1
            def ids(r):
                return {p["id"] for p in r["P"]+[r["C"],r["1B"],r["2B"],r["3B"],r["SS"]]+r["OF"]}
            if any(ids(roster)==ids(prev) for prev in lineups): continue
            seen.add(k); lineups.append(roster)
            pair_used[tuple(sorted((pa["id"],pb["id"])))]+=1
            for p in roster["P"]+[roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]:
                exp[p["id"]]+=1

    if len(lineups)<N:
        # last ditch: ignore exposure entirely in try_one by resetting max
        print("last ditch", flush=True)
        global MAX_EXP
        MAX_EXP = 50
        for _ in range(5000):
            if len(lineups)>=N: break
            pa,pb = RNG.choice(pairs)
            stack = RNG.choice(strong_teams)
            res = try_one(pa,pb,stack,3,True,44000)
            if not res: continue
            roster,sal=res
            k=key(roster)
            if k in seen: continue
            seen.add(k); lineups.append(roster)
            for p in roster["P"]+[roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]:
                exp[p["id"]]+=1

    assert len(lineups)>=N, f"only {len(lineups)}"
    lineups = lineups[:N]

    # validate + write
    pool_ids = set(by_id)
    pass_n=fail_n=0
    sals=[]; projs=[]
    for roster in lineups:
        plist = roster["P"]+[roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]
        ok=True
        if len(plist)!=10 or len({p["id"] for p in plist})!=10: ok=False
        sal=sum(p["sal"] for p in plist)
        if sal>CAP: ok=False
        for p in roster["P"]:
            if not p["is_p"] or "P" not in p["elig"] or p["id"] not in pool_ids: ok=False
        for s in ("C","1B","2B","3B","SS"):
            if s not in roster[s]["elig"] or roster[s]["id"] not in pool_ids: ok=False
        for p in roster["OF"]:
            if "OF" not in p["elig"] or p["id"] not in pool_ids: ok=False
        hit_only = [roster["C"],roster["1B"],roster["2B"],roster["3B"],roster["SS"]]+roster["OF"]
        if any(c > MAX_HITTERS_PER_TEAM for c in Counter(h["team"] for h in hit_only).values()):
            ok=False
        if len({p["game"] for p in roster["P"]+hit_only}) < 2:
            ok=False
        if ok: pass_n+=1
        else: fail_n+=1
        sals.append(sal); projs.append(sum(p["proj"] for p in plist))

    out = ROOT/"lineups-50-tonight.csv"
    with open(out,"w",newline="") as f:
        w=csv.writer(f); w.writerow(SLOTS)
        for r in lineups: w.writerow(row(r))

    exp_list=[]
    for pid,c in exp.most_common():
        if pid not in by_id: continue
        p=by_id[pid]
        exp_list.append((p["name"],c,100.0*c/N,p["proj"],p["sal"]))
    over40=[e for e in exp_list if e[2]>40.0001]

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
        "",
        "top_15_player_exposures:",
    ]
    for name,c,pct,proj,sal in exp_list[:15]:
        summary.append(f"  {name}: {c}/{N} ({pct:.1f}%) proj={proj} sal={sal}")
    summary.append("")
    if over40:
        summary.append("players_over_40pct_exposure:")
        for name,c,pct,_,_ in over40:
            summary.append(f"  {name}: {c}/{N} ({pct:.1f}%)")
    else:
        summary.append("players_over_40pct_exposure: none")
    (ROOT/"lineups-50-tonight-summary.txt").write_text("\n".join(summary)+"\n")
    print("\n".join(summary), flush=True)
    print(f"WROTE {out}", flush=True)
    print(f"TOP10: {[(e[0],e[1],round(e[2],1)) for e in exp_list[:10]]}", flush=True)

if __name__=="__main__":
    main()
