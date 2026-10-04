"""Turn cached ESPN payloads into a compact, auditable game file.

Output: data/<season>/games.json.gz, a list of games. Each game carries every
drive with its points, start field position, pre-drive margin, kept/excluded
flag and reason, and the scrimmage plays used for the five factors.

    python parse.py --season 2026
"""
import argparse
import glob
import gzip
import json
import os
import re

from fetch import HERE, read_gz

CONFIG = json.load(open(os.path.join(HERE, "config.json")))

RUSH = {"Rush", "Rushing Touchdown"}
PASS = {"Pass Reception", "Pass Incompletion", "Passing Touchdown", "Pass Completion", "Sack",
        "Pass Interception Return", "Interception", "Interception Return Touchdown"}
FUMBLE = {"Fumble Recovery (Own)", "Fumble Recovery (Opponent)", "Fumble",
          "Fumble Return Touchdown"}
SCRIMMAGE = RUSH | PASS | FUMBLE | {"Safety"}
TURNOVER = {"Pass Interception Return", "Interception", "Interception Return Touchdown",
            "Fumble Recovery (Opponent)", "Fumble Return Touchdown"}
OFFENSIVE_TD = {"Rushing Touchdown", "Passing Touchdown"}
END_OF_HALF = {"END OF HALF", "END OF GAME"}


def membership(season):
    return read_gz(os.path.join(HERE, "cache", str(season), "membership.json.gz"))


def scoreboard_events(season):
    events = {}
    for f in sorted(glob.glob(os.path.join(HERE, "cache", str(season), "scoreboards", "*.gz"))):
        week = int(re.search(r"w(\d+)_", f).group(1))
        for e in read_gz(f).get("events", []):
            if "id" in e:
                e["_week"] = week
                events[e["id"]] = e
    return events


def clock_secs(s):
    try:
        m, sec = s.split(":")
        return int(m) * 60 + int(sec)
    except (ValueError, AttributeError):
        return None


def garbage(period, margin):
    limits = CONFIG["garbage_margin"]  # by quarter, Connelly
    return period <= 4 and abs(margin) > limits[str(period)]


def classify(p):
    """Return (kind, yards, success, explosive, turnover, td) for a scrimmage play, or None."""
    t = p["type"]["text"]
    text = p.get("text", "").lower()
    if t not in SCRIMMAGE or "kneel" in text or "spike" in text:
        return None
    start = p.get("start", {})
    down, dist = start.get("down", 0), start.get("distance", 0)
    if not down or down > 4:
        return None
    if t in RUSH:
        kind = "R"
    elif t in PASS:
        kind = "P"
    else:
        kind = "P" if (" pass" in text or "sacked" in text) else "R"
    turnover = t in TURNOVER
    td = t in OFFENSIVE_TD
    yds = 0 if turnover else int(p.get("statYardage", 0) or 0)
    need = {1: 0.5, 2: 0.7}.get(down, 1.0) * dist
    success = (not turnover) and (td or yds >= need)
    ex = CONFIG["explosive"]
    explosive = (not turnover) and yds >= (ex["rush"] if kind == "R" else ex["pass"])
    return kind, yds, int(success), int(explosive), int(turnover), int(td)


def parse_drives(summary, home_id, away_id, final):
    """Drives with points from ESPN's scoringPlays (play-level running scores are unreliable)."""
    prev = summary.get("drives", {}).get("previous", [])
    if not prev:
        return [], "no play-by-play"
    sps = summary.get("scoringPlays", [])
    last = {"away": 0, "home": 0}
    for sp in sps:
        last = {"away": sp["awayScore"], "home": sp["homeScore"]}
    warning = ""
    if last != final:
        gap = max(abs(last[k] - final[k]) for k in final)
        msg = (f"scoring plays sum to {last['away']}-{last['home']} "
               f"but final is {final['away']}-{final['home']}")
        if gap > 2:
            return [], msg
        warning = msg + " (kept: gap is at most a missed PAT/2-pt)"

    # Points each scoring play added, and which drive it happened in.
    side = {home_id: "home", away_id: "away"}
    play_drive = {p["id"]: i for i, d in enumerate(prev) for p in d.get("plays", [])}
    sp_rows, before = [], {"away": 0, "home": 0}
    for sp in sps:
        after = {"away": sp["awayScore"], "home": sp["homeScore"]}
        tid = sp.get("team", {}).get("id")
        if tid not in side:
            return [], f"scoring play {sp['id']} has unknown team"
        if sp["id"] not in play_drive:
            return [], f"scoring play {sp['id']} not found in any drive"
        sp_rows.append({"drive": play_drive[sp["id"]], "team": tid,
                        "pts": after[side[tid]] - before[side[tid]], "after": after})
        before = after

    drives, score = [], {"away": 0, "home": 0}
    for i, d in enumerate(prev):
        off = d.get("team", {}).get("id")
        rows = [r for r in sp_rows if r["drive"] == i]
        pre = dict(score)
        if rows:
            score = rows[-1]["after"]
        if off not in side:
            continue
        dfn = home_id if off == away_id else away_id
        plays, first = [], None
        for p in d.get("plays", []):
            if "type" not in p or p.get("start", {}).get("team", {}).get("id") not in (off, None):
                continue
            c = classify(p)
            if c is None:
                continue
            if first is None:
                first = p
            plays.append([p["start"]["down"], p["start"]["distance"],
                          p["start"]["yardsToEndzone"], *c])
        pts = sum(r["pts"] for r in rows if r["team"] == off)
        result = d.get("result")
        period = first["period"]["number"] if first else d.get("start", {}).get("period", {}).get("number", 0)
        margin = pre[side[off]] - pre[side[dfn]]
        end_period = d.get("end", {}).get("period", {}).get("number", period)
        if not plays:
            why = "no scrimmage plays"
        elif period >= 5:
            why = "overtime"
        elif result in END_OF_HALF or (result == "END OF QUARTER" and end_period in (2, 4)):
            why = "end of half/game"
        elif garbage(period, margin):
            why = "garbage time"
        else:
            why = ""
        drives.append({
            "i": i, "off": off, "def": dfn, "period": period,
            "clock": (first or {}).get("clock", {}).get("displayValue"),
            "start_yte": plays[0][2] if plays else None,
            "result": result, "pts": pts, "margin": margin,
            "secs": clock_secs(d.get("timeElapsed", {}).get("displayValue")),
            "kept": int(not why), "why": why,
            # [down, dist, yards_to_endzone, kind, yds, success, explosive, turnover, td]
            "plays": plays,
        })
    return drives, warning


def box_stats(summary):
    out = {}
    for t in summary.get("boxscore", {}).get("teams", []):
        stats = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
        try:
            to = int(stats.get("turnovers") or 0)
        except ValueError:
            to = None
        out[t["team"]["id"]] = {"turnovers": to}
    return out


def market_margin(summary):
    """Expected home margin from the sportsbook line ESPN shows (benchmark only)."""
    for p in summary.get("pickcenter") or []:
        if isinstance(p.get("spread"), (int, float)):
            return -float(p["spread"])
    return None


def build(season):
    members = membership(season)
    events = scoreboard_events(season)
    games, upcoming = [], []
    for eid, e in sorted(events.items(), key=lambda kv: kv[1]["date"]):
        comp = e["competitions"][0]
        cs = {c["homeAway"]: c for c in comp["competitors"]}
        if not comp["status"]["type"].get("completed"):
            if cs["home"]["team"]["id"] in members and cs["away"]["team"]["id"] in members:
                upcoming.append({
                    "id": eid, "week": e["_week"], "date": e["date"],
                    "neutral": int(bool(comp.get("neutralSite"))),
                    "home": cs["home"]["team"]["id"], "away": cs["away"]["team"]["id"]})
            continue
        home, away = cs["home"]["team"]["id"], cs["away"]["team"]["id"]
        final = {"home": int(cs["home"].get("score") or 0), "away": int(cs["away"].get("score") or 0)}
        g = {
            "id": eid, "week": e["_week"], "date": e["date"],
            "neutral": int(bool(comp.get("neutralSite"))),
            "conf_game": int(bool(comp.get("conferenceCompetition"))),
            "home": home, "away": away, "home_pts": final["home"], "away_pts": final["away"],
            "home_name": cs["home"]["team"].get("location") or cs["home"]["team"]["displayName"],
            "away_name": cs["away"]["team"].get("location") or cs["away"]["team"]["displayName"],
            "d1": int(home in members and away in members),
            "drives": [], "pbp_note": "", "box": {},
        }
        path = os.path.join(HERE, "cache", str(season), "summaries", f"{eid}.json.gz")
        if g["d1"] and os.path.exists(path):
            s = read_gz(path)
            g["drives"], g["pbp_note"] = parse_drives(s, home, away, final)
            g["box"] = box_stats(s)
            g["market_home_margin"] = market_margin(s)
        elif g["d1"]:
            g["pbp_note"] = "no summary downloaded"
        games.append(g)
    out = os.path.join(HERE, "data", str(season))
    os.makedirs(out, exist_ok=True)
    with gzip.open(os.path.join(out, "games.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"season": season, "teams": members, "games": games, "upcoming": upcoming},
                  f, separators=(",", ":"))
    return games


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    args = ap.parse_args()
    games = build(args.season)
    d1 = [g for g in games if g["d1"]]
    with_pbp = [g for g in d1 if g["drives"]]
    notes = [(g["id"], g["away_name"], g["home_name"], g["pbp_note"]) for g in d1 if g["pbp_note"]]
    print(f"{len(games)} final games, {len(d1)} D-I vs D-I, {len(with_pbp)} with usable drives")
    for n in notes:
        print("  no drives:", *n)


if __name__ == "__main__":
    main()
