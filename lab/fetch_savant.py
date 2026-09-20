#!/usr/bin/env python3
"""Fetch Baseball Savant expected-stats + exit-velo/barrels CSVs (free, no API key).

Method
------
1. GET Baseball Savant leaderboard CSV endpoints with csv=true and a browser-like
   User-Agent (Chrome desktop). Endpoints:
   - /leaderboard/expected_statistics  → xBA, xSLG, xwOBA (batters); + xERA (pitchers)
   - /leaderboard/statcast             → barrel%, hard-hit% (ev95percent), avg EV
2. Prefer season year (default 2026). If empty/blocked, fall back to year-1 and
   document in NOTES.
3. Prefer denser min=1 pulls when qualified (min=q) is thin; try min in (q, 1, 50).
4. Attach MLB team abbrev via free StatsAPI roster (player_id → currentTeam),
   normalizing AZ→ARI so DK joins work. ATH already matches DK.
5. Merge expected + exit-velo on player_id; write sources CSVs + NOTES.

Outputs (canonical)
-------------------
- /home/box/mlb-dfs/sources/savant-expected-batters-2026.csv
- /home/box/mlb-dfs/sources/savant-expected-pitchers-2026.csv
- Matching *.NOTE.md beside each CSV

Join step is separate: lab/join_savant_features.py → lab/features-savant-tonight.csv

Stdlib + optional pandas. Uses urllib (no paid APIs).
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

DESK = Path("/home/box/mlb-dfs")
SOURCES = DESK / "sources"

USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/120.0.0.0 Safari/537.36"
)

EXPECTED_BASE = "https://baseballsavant.mlb.com/leaderboard/expected_statistics"
STATCAST_BASE = "https://baseballsavant.mlb.com/leaderboard/statcast"
STATSAPI_PLAYERS = "https://statsapi.mlb.com/api/v1/sports/1/players"
STATSAPI_TEAMS = "https://statsapi.mlb.com/api/v1/teams?sportId=1"

MIN_OPTIONS = ("1", "q", "50")  # prefer denser DFS-friendly min=1
THIN_THRESHOLD = 50

# StatsAPI / Savant → DK Classic pool abbrevs
TEAM_MAP = {
    "AZ": "ARI",
    "OAK": "ATH",
    "WSN": "WSH",
    "WAS": "WSH",
    "CHW": "CWS",
    "KCR": "KC",
    "SDP": "SD",
    "SFG": "SF",
    "TBR": "TB",
    "TBD": "TB",
    "ANA": "LAA",
}


def norm_team(t: str) -> str:
    t = (t or "").strip().upper()
    return TEAM_MAP.get(t, t)


def http_get(url: str, timeout: int = 90) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/csv,application/json,text/plain,*/*",
            "Accept-Language": "en-US,en;q=0.9",
            "Referer": "https://baseballsavant.mlb.com/",
        },
        method="GET",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return resp.read()


def expected_url(player_type: str, year: int, min_pa: str) -> str:
    return (
        f"{EXPECTED_BASE}?type={player_type}&year={year}"
        f"&position=&team=&min={min_pa}&csv=true"
    )


def statcast_url(player_type: str, year: int, min_pa: str) -> str:
    return (
        f"{STATCAST_BASE}?type={player_type}&year={year}"
        f"&position=&team=&min={min_pa}&csv=true"
    )


def parse_csv_rows(raw: bytes) -> list[dict[str, str]]:
    text = raw.decode("utf-8-sig", errors="replace")
    if not text.strip() or "<html" in text[:300].lower():
        return []
    # Savant quotes "last_name, first_name" oddly in some clients; DictReader handles
    reader = csv.DictReader(io.StringIO(text))
    rows: list[dict[str, str]] = []
    for row in reader:
        # Normalize key whitespace / BOM leftovers
        clean = {(k or "").strip().lstrip("\ufeff"): (v or "").strip() for k, v in row.items()}
        # Fix split name header if csv module split on comma inside unquoted mess
        if "last_name, first_name" not in clean:
            # reconstruct from common broken keys
            ln = clean.pop("last_name", "") or clean.pop('"last_name', "")
            fn = clean.pop("first_name", "") or clean.pop('first_name"', "")
            if ln or fn:
                clean["last_name, first_name"] = f"{ln.strip(' \"')}, {fn.strip(' \"')}".strip(", ")
        if not any(clean.values()):
            continue
        rows.append(clean)
    return rows


def count_data_rows(raw: bytes) -> int:
    return len(parse_csv_rows(raw))


def download_best(
    url_fn, player_type: str, year: int
) -> tuple[bytes | None, str | None, int, list[str]]:
    log: list[str] = []
    best_raw: bytes | None = None
    best_min: str | None = None
    best_n = 0
    for min_pa in MIN_OPTIONS:
        url = url_fn(player_type, year, min_pa)
        try:
            raw = http_get(url)
            n = count_data_rows(raw)
            log.append(f"  year={year} type={player_type} min={min_pa}: {n} rows ({url_fn.__name__})")
            if n > best_n:
                best_raw, best_min, best_n = raw, min_pa, n
            if min_pa == "1" and n >= THIN_THRESHOLD:
                break
            if min_pa == "q" and n >= 200:
                break
        except urllib.error.HTTPError as e:
            log.append(f"  year={year} type={player_type} min={min_pa}: HTTP {e.code}")
        except Exception as e:  # noqa: BLE001
            log.append(f"  year={year} type={player_type} min={min_pa}: ERROR {e}")
    if best_n == 0:
        return None, None, 0, log
    return best_raw, best_min, best_n, log


def load_playerid_team_map(season: int) -> dict[str, str]:
    """MLBAM player_id → DK-normalized team abbrev via StatsAPI."""
    out: dict[str, str] = {}
    try:
        teams_raw = http_get(f"{STATSAPI_TEAMS}&season={season}")
        teams = json.loads(teams_raw.decode("utf-8"))["teams"]
        tid_map = {t["id"]: norm_team(t.get("abbreviation", "")) for t in teams}
        players_raw = http_get(f"{STATSAPI_PLAYERS}?season={season}")
        people = json.loads(players_raw.decode("utf-8"))["people"]
        for p in people:
            pid = str(p.get("id", "")).strip()
            ct = p.get("currentTeam") or {}
            ab = tid_map.get(ct.get("id"), "")
            if pid and ab:
                out[pid] = ab
    except Exception as e:  # noqa: BLE001
        print(f"WARN: StatsAPI team map failed: {e}", file=sys.stderr)
    return out


def display_name(last_first: str) -> str:
    """'Crow-Armstrong, Pete' → 'Pete Crow-Armstrong'."""
    s = (last_first or "").strip().strip('"')
    if "," in s:
        last, first = s.split(",", 1)
        return f"{first.strip()} {last.strip()}".strip()
    return s


def merge_expected_ev(
    expected_rows: list[dict[str, str]],
    ev_rows: list[dict[str, str]],
    team_map: dict[str, str],
    player_type: str,
) -> list[dict[str, str]]:
    ev_by_id = {}
    for r in ev_rows:
        pid = str(r.get("player_id", "")).strip()
        if pid:
            ev_by_id[pid] = r

    out: list[dict[str, str]] = []
    for r in expected_rows:
        pid = str(r.get("player_id", "")).strip()
        lf = r.get("last_name, first_name", "")
        ev = ev_by_id.get(pid, {})
        row = {
            "player_id": pid,
            "name": display_name(lf),
            "name_savant": lf.strip().strip('"'),
            "team": team_map.get(pid, ""),
            "year": r.get("year", ""),
            "role": player_type,
            "pa": r.get("pa", ""),
            "bip": r.get("bip", ""),
            "ba": r.get("ba", ""),
            "xba": r.get("est_ba", ""),
            "slg": r.get("slg", ""),
            "xslg": r.get("est_slg", ""),
            "woba": r.get("woba", ""),
            "xwoba": r.get("est_woba", ""),
            "era": r.get("era", ""),
            "xera": r.get("xera", ""),
            "attempts": ev.get("attempts", ""),
            "avg_hit_speed": ev.get("avg_hit_speed", ""),
            "hard_hit_pct": ev.get("ev95percent", ""),  # Statcast hard-hit %
            "barrels": ev.get("barrels", ""),
            "barrel_pct": ev.get("brl_percent", ""),
            "barrel_pa": ev.get("brl_pa", ""),
            # K%/BB%/whiff% not on these free boards — left blank, noted in NOTE
            "k_pct": "",
            "bb_pct": "",
            "whiff_pct": "",
        }
        out.append(row)
    # Also include EV-only players missing from expected (rare)
    exp_ids = {r["player_id"] for r in out}
    for pid, ev in ev_by_id.items():
        if pid in exp_ids:
            continue
        lf = ev.get("last_name, first_name", "")
        out.append(
            {
                "player_id": pid,
                "name": display_name(lf),
                "name_savant": lf.strip().strip('"'),
                "team": team_map.get(pid, ""),
                "year": "",
                "role": player_type,
                "pa": "",
                "bip": "",
                "ba": "",
                "xba": "",
                "slg": "",
                "xslg": "",
                "woba": "",
                "xwoba": "",
                "era": "",
                "xera": "",
                "attempts": ev.get("attempts", ""),
                "avg_hit_speed": ev.get("avg_hit_speed", ""),
                "hard_hit_pct": ev.get("ev95percent", ""),
                "barrels": ev.get("barrels", ""),
                "barrel_pct": ev.get("brl_percent", ""),
                "barrel_pa": ev.get("brl_pa", ""),
                "k_pct": "",
                "bb_pct": "",
                "whiff_pct": "",
            }
        )
    return out


FIELDNAMES = [
    "player_id",
    "name",
    "name_savant",
    "team",
    "year",
    "role",
    "pa",
    "bip",
    "ba",
    "xba",
    "slg",
    "xslg",
    "woba",
    "xwoba",
    "era",
    "xera",
    "attempts",
    "avg_hit_speed",
    "hard_hit_pct",
    "barrels",
    "barrel_pct",
    "barrel_pa",
    "k_pct",
    "bb_pct",
    "whiff_pct",
]


def write_csv(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=FIELDNAMES, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow(r)


def write_note(
    path: Path,
    *,
    player_type: str,
    year_requested: int,
    year_used: int,
    min_exp: str,
    min_ev: str,
    rows: int,
    with_team: int,
    fallback: bool,
    log: list[str],
) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    csv_name = path.name.replace(".NOTE.md", ".csv")
    lines = [
        f"# SOURCE NOTE — Baseball Savant expected + barrels ({player_type})",
        "",
        f"- **Fetched:** {now}",
        f"- **File:** `{csv_name}`",
        f"- **Year requested:** {year_requested}",
        f"- **Year saved:** {year_used}"
        + (" (FALLBACK — requested year empty/failed)" if fallback else ""),
        f"- **Expected-stats min:** min={min_exp}",
        f"- **Exit-velo/barrels min:** min={min_ev}",
        f"- **Rows:** {rows} (with team attached: {with_team})",
        f"- **UA:** browser-like Chrome desktop",
        f"- **Expected URL pattern:** `{EXPECTED_BASE}?type={player_type}&year=…&min=…&csv=true`",
        f"- **Statcast URL pattern:** `{STATCAST_BASE}?type={player_type}&year=…&min=…&csv=true`",
        f"- **Team map:** MLB StatsAPI sports/1/players + teams (AZ→ARI, OAK→ATH)",
        "",
        "## Fields",
        "",
        "- **Expected:** xba (`est_ba`), xslg (`est_slg`), xwoba (`est_woba`); pitchers also xera",
        "- **Contact quality:** hard_hit_pct (`ev95percent`), barrel_pct (`brl_percent`), avg_hit_speed",
        "- **Not on these free boards:** k_pct / bb_pct / whiff_pct (columns present but blank)",
        "",
        "## Attempt log",
        "",
    ]
    lines.extend(f"- {ln.strip()}" for ln in log)
    lines.extend(
        [
            "",
            "Free public CSV; no paid API. Re-run: "
            "`python3 /home/box/mlb-dfs/lab/fetch_savant.py`",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def fetch_type(
    player_type: str,
    year: int,
    out_csv: Path,
    out_note: Path,
    team_map: dict[str, str],
) -> tuple[int, int]:
    print(f"Fetching Savant {player_type} expected + exit-velo for {year}…")
    log: list[str] = []
    raw_e, min_e, n_e, log_e = download_best(expected_url, player_type, year)
    log.extend(log_e)
    raw_v, min_v, n_v, log_v = download_best(statcast_url, player_type, year)
    log.extend(log_v)
    year_used = year
    fallback = False

    if n_e == 0:
        fb = year - 1
        print(f"  {year} expected empty — falling back to {fb}")
        raw_e2, min_e2, n_e2, log_e2 = download_best(expected_url, player_type, fb)
        log.extend(log_e2)
        if n_e2 > 0:
            raw_e, min_e, n_e = raw_e2, min_e2, n_e2
            year_used = fb
            fallback = True
            raw_v2, min_v2, n_v2, log_v2 = download_best(statcast_url, player_type, fb)
            log.extend(log_v2)
            if n_v2 > 0:
                raw_v, min_v, n_v = raw_v2, min_v2, n_v2

    if n_e == 0 or raw_e is None:
        print(f"ERROR: no usable Savant expected data for {player_type}", file=sys.stderr)
        write_note(
            out_note,
            player_type=player_type,
            year_requested=year,
            year_used=year_used,
            min_exp="none",
            min_ev="none",
            rows=0,
            with_team=0,
            fallback=fallback,
            log=log,
        )
        # still write empty stub CSV with header
        write_csv(out_csv, [])
        return 0, year_used

    exp_rows = parse_csv_rows(raw_e)
    ev_rows = parse_csv_rows(raw_v) if raw_v and n_v else []
    merged = merge_expected_ev(exp_rows, ev_rows, team_map, player_type)
    # stamp year_used
    for r in merged:
        if not r.get("year"):
            r["year"] = str(year_used)
    write_csv(out_csv, merged)
    with_team = sum(1 for r in merged if r.get("team"))
    write_note(
        out_note,
        player_type=player_type,
        year_requested=year,
        year_used=year_used,
        min_exp=min_e or "none",
        min_ev=min_v or "none",
        rows=len(merged),
        with_team=with_team,
        fallback=fallback,
        log=log,
    )
    print(
        f"  Wrote {out_csv} ({len(merged)} rows, year={year_used}, "
        f"min_exp={min_e}, min_ev={min_v}, team={with_team})"
    )
    print(f"  Note  {out_note}")
    return len(merged), year_used


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Fetch Baseball Savant expected-stats + barrels CSVs"
    )
    ap.add_argument("--year", type=int, default=2026)
    ap.add_argument("--sources", type=Path, default=SOURCES)
    args = ap.parse_args()
    sources: Path = args.sources
    sources.mkdir(parents=True, exist_ok=True)

    print("Loading StatsAPI player→team map…")
    team_map = load_playerid_team_map(args.year)
    print(f"  team map size: {len(team_map)}")

    # Canonical plural filenames (desk contract 2026-09-11)
    batter_csv = sources / "savant-expected-batters-2026.csv"
    pitcher_csv = sources / "savant-expected-pitchers-2026.csv"
    batter_note = sources / "savant-expected-batters-2026.NOTE.md"
    pitcher_note = sources / "savant-expected-pitchers-2026.NOTE.md"

    bn, by = fetch_type("batter", args.year, batter_csv, batter_note, team_map)
    pn, py = fetch_type("pitcher", args.year, pitcher_csv, pitcher_note, team_map)

    # Also emit singular aliases (user / Manager contract paths)
    aliases = [
        (batter_csv, sources / "savant-expected-batter-2026.csv",
         batter_note, sources / "savant-expected-batter-2026.NOTE.md"),
        (pitcher_csv, sources / "savant-expected-pitcher-2026.csv",
         pitcher_note, sources / "savant-expected-pitcher-2026.NOTE.md"),
    ]
    for src_csv, alias_csv, src_note, alias_note in aliases:
        if src_csv.exists():
            alias_csv.write_bytes(src_csv.read_bytes())
            print(f"  Alias {alias_csv.name}")
        if src_note.exists():
            alias_note.write_text(src_note.read_text(encoding="utf-8"), encoding="utf-8")

    # Combined NOTE pointer for index
    combo = sources / "savant-2026-ytd.NOTE.md"
    combo.write_text(
        "\n".join(
            [
                "# Baseball Savant / Statcast YTD features (2026)",
                "",
                f"- Batters: `savant-expected-batters-2026.csv` ({bn} rows, year={by})",
                f"- Pitchers: `savant-expected-pitchers-2026.csv` ({pn} rows, year={py})",
                "- Join: `python3 /home/box/mlb-dfs/lab/join_savant_features.py`",
                "- See per-file `.NOTE.md` for URLs, min filters, field caveats.",
                "- Free data only (Savant CSV + StatsAPI team map).",
                "",
            ]
        ),
        encoding="utf-8",
    )
    print(f"  Combo note {combo}")

    if bn == 0 and pn == 0:
        return 1
    print(f"Done. batters={bn} (yr={by}) pitchers={pn} (yr={py})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
