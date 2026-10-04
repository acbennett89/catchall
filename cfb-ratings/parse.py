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
    # Fumbles and safeties on punts/kickoffs (muffs, return safeties) are special teams.
    if t in FUMBLE | {"Safety"} and ("punt" in text or "kick" in text):
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


PAT_KNOWN = {61, 62, 43, 15, 16}  # ESPN pointAfterAttempt ids: kick good/missed/blocked, 2-pt pass/rush


def typed_points(sp, play):
    """Points a scoring play is worth from its type and extra-point result.

    Returns (points, pat_unknown). ESPN's running score on scoring plays is
    occasionally wrong even when the final reconciles, so points are rebuilt
    from what the play was rather than from score differences.
    """
    st = (sp.get("scoringType") or {}).get("name")
    if st == "touchdown":
        pa = (play or {}).get("pointAfterAttempt")
        if pa and pa.get("id") in PAT_KNOWN:
            return 6 + int(pa.get("value") or 0), False
        return 6, True
    if st == "field-goal":
        return 3, False
    if st in ("safety", "defensive-two-point-conversion"):
        return 2, False
    if (sp.get("type") or {}).get("text") in ("Two Point Rush", "Two Point Pass"):
        return 2, False
    return 0, False


def score_rows(summary, side, final, play_drive):
    """Scoring plays with rebuilt points, reconciled to the final score.

    1. Points from play type + extra-point result (typed_points).
    2. Touchdowns whose extra point ESPN marks "Not Available" share whatever
       points the team still needs to reach its final score (exactly 1 each
       when every unknown kick was good).
    3. If that can't reconcile, fall back to ESPN's running-score changes, but
       only if every change is a legal score for the scorer, the other team's
       score is unchanged, and the total reconciles.
    Returns (rows, method, corrections) or (None, reason, []).
    """
    playmap = {p["id"]: p for d in summary["drives"]["previous"] for p in d.get("plays", [])}
    rows = []
    for sp in summary.get("scoringPlays", []):
        tid = (sp.get("team") or {}).get("id")
        if tid not in side:
            return None, f"scoring play {sp['id']} has unknown team", []
        if sp["id"] not in play_drive:
            return None, f"scoring play {sp['id']} not found in any drive", []
        pts, unknown = typed_points(sp, playmap.get(sp["id"]))
        rows.append({"id": sp["id"], "drive": play_drive[sp["id"]], "team": tid,
                     "type": (sp.get("scoringType") or {}).get("name"), "pts": pts,
                     "pat_unknown": unknown, "espn_after": (sp["awayScore"], sp["homeScore"])})
    method = "play type"
    for tid, s in side.items():
        mine = [r for r in rows if r["team"] == tid]
        unknown = [r for r in mine if r["pat_unknown"]]
        gap = final[s] - sum(r["pts"] for r in mine)
        if (not unknown and gap != 0) or (unknown and not 0 <= gap <= 2 * len(unknown)):
            return running_rows(rows, side, final)
        for r in unknown:
            r["pts"] += gap / len(unknown)
        if unknown:
            method = "play type; unreported extra points shared to reach the final"
    # Record where ESPN's running score disagreed with the rebuilt points.
    corrections, before = [], {"away": 0, "home": 0}
    for r in rows:
        after = {"away": r["espn_after"][0], "home": r["espn_after"][1]}
        s = side[r["team"]]
        espn = after[s] - before[s]
        if espn != r["pts"]:
            corrections.append(f"scoring play {r['id']}: ESPN running score +{espn}, rebuilt {r['pts']:g}")
        before = after
    return rows, method, corrections


def running_rows(rows, side, final):
    before = {"away": 0, "home": 0}
    for r in rows:
        after = {"away": r["espn_after"][0], "home": r["espn_after"][1]}
        s = side[r["team"]]
        other = "home" if s == "away" else "away"
        delta = after[s] - before[s]
        if delta not in (2, 3, 6, 7, 8) or after[other] != before[other]:
            return None, "scoring plays can't be reconciled to the final score", []
        r["pts"] = delta
        before = after
    if before != final:
        return None, "scoring plays can't be reconciled to the final score", []
    return rows, "ESPN running score (play types did not reconcile)", []


def drive_offense(d, side):
    """Offense = the team that snapped most of the drive's plays (ESPN's label is sometimes wrong)."""
    counts = {}
    for p in d.get("plays", []):
        tid = (p.get("start", {}).get("team") or {}).get("id")
        if tid in side and (p.get("type") or {}).get("text") in SCRIMMAGE | {"Penalty"}:
            counts[tid] = counts.get(tid, 0) + 1
    label = (d.get("team") or {}).get("id")
    if counts:
        best = max(counts, key=counts.get)
        if counts[best] > counts.get(label, 0):
            return best, label
    return label, label


def parse_drives(summary, home_id, away_id, final):
    """Drives with offensive points rebuilt from ESPN's scoring plays."""
    prev = summary.get("drives", {}).get("previous", [])
    if not prev:
        return [], "no play-by-play"
    side = {home_id: "home", away_id: "away"}
    play_drive = {p["id"]: i for i, d in enumerate(prev) for p in d.get("plays", [])}
    rows, method, corrections = score_rows(summary, side, final, play_drive)
    if rows is None:
        return [], method
    notes = [] if method == "play type" else [method]
    notes += corrections

    eoh = CONFIG["end_of_half_seconds"]
    drives, score = [], {"away": 0, "home": 0}
    for i, d in enumerate(prev):
        drive_rows = [r for r in rows if r["drive"] == i]
        pre = dict(score)
        for r in drive_rows:
            score[side[r["team"]]] += r["pts"]
        off, label = drive_offense(d, side)
        if off not in side:
            continue
        if off != label:
            notes.append(f"drive {i}: offense relabeled from plays (ESPN said team {label})")
        dfn = home_id if off == away_id else away_id
        plays, first, seen = [], None, set()
        for p in d.get("plays", []):
            if "type" not in p or p.get("start", {}).get("team", {}).get("id") not in (off, None):
                continue
            st = p.get("start", {})
            key = (p.get("period", {}).get("number"), p.get("clock", {}).get("displayValue"),
                   p.get("text"), st.get("down"), st.get("distance"), st.get("yardsToEndzone"))
            if key in seen:  # ESPN occasionally lists the same snap twice
                continue
            seen.add(key)
            c = classify(p)
            if c is None:
                continue
            if first is None:
                first = p
            plays.append([st["down"], st["distance"], st["yardsToEndzone"], *c])
        # Offensive points: touchdowns and field goals the offense scored. Safeties
        # credited to the offense come from punt/kick returns, i.e. special teams.
        pts = sum(r["pts"] for r in drive_rows if r["team"] == off and r["type"] != "safety")
        result = d.get("result")
        period = first["period"]["number"] if first else d.get("start", {}).get("period", {}).get("number", 0)
        clock = (first or {}).get("clock", {}).get("displayValue")
        left = clock_secs(clock)
        margin = pre[side[off]] - pre[side[dfn]]
        # Decided by the situation at the drive's first snap, never by how it ended,
        # so failed and successful late drives are treated alike.
        if not plays:
            why = "no scrimmage plays"
        elif period >= 5:
            why = "overtime"
        elif period in (2, 4) and left is not None and left <= eoh:
            why = "end of half/game"
        elif garbage(period, margin):
            why = "garbage time"
        else:
            why = ""
        drives.append({
            "i": i, "off": off, "def": dfn, "period": period, "clock": clock,
            "start_yte": plays[0][2] if plays else None,
            "result": result, "pts": pts, "margin": margin,
            "secs": clock_secs(d.get("timeElapsed", {}).get("displayValue")),
            "kept": int(not why), "why": why,
            # [down, dist, yards_to_endzone, kind, yds, success, explosive, turnover, td]
            "plays": plays,
        })
    return drives, "; ".join(notes)


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
    print(f"{len(games)} final games, {len(d1)} D-I vs D-I, {len(with_pbp)} with usable drives, "
          f"{sum(1 for g in with_pbp if g['pbp_note'])} kept with data notes")
    for g in d1:
        if not g["drives"]:
            print(f"  dropped from efficiency: {g['id']} {g['away_name']} at {g['home_name']}: {g['pbp_note']}")


if __name__ == "__main__":
    main()
