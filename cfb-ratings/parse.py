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
from penalties import TABLE_FIELDS, parse_game_penalties, penalty_table

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


KNEEL = re.compile(r"\bkneel(s|ed|ing|down)?\b|\btakes a knee\b")   # not "McKneely"/"Kneeland"
SPIKE = re.compile(r"\bspiked?\b")
NULLIFIED = re.compile(r"\bno play\b|\bnullified\b")                    # stat-crew text says so


def classify(p):
    """Return (kind, yards, success, explosive, turnover, td) for a scrimmage play, or None."""
    t = p["type"]["text"]
    text = p.get("text", "").lower()
    if t not in SCRIMMAGE or KNEEL.search(text) or SPIKE.search(text):
        return None
    # A snap the text says was wiped out by a penalty did not happen (both sides alike).
    if NULLIFIED.search(text):
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


OOB = re.compile(r"out of bounds|out-of-bounds|\bran ob\b|\bpushed ob\b|\bob at\b|\bforced ob\b")


def is_snap(p, off):
    st = p.get("start", {})
    return ((p.get("type") or {}).get("text") in SCRIMMAGE and 1 <= (st.get("down") or 0) <= 4
            and (st.get("team") or {}).get("id") in (off, None))


def clean_intervals(plays, off, scoring_ids):
    """Game-clock seconds from each snap to the very next snap, kept only when nothing
    stopped the clock in between. Returns (clean intervals, candidates, zero-second count).

    Skipped: kneels/spikes, incompletions, scores, turnovers, a penalty on the snap,
    out of bounds, anything other than a snap by the same offense in the same quarter
    coming next (timeouts, penalties, reviews, end of quarter), a first down in the final
    2:00 of Q2/Q4 (when first downs stop the clock), and readings of 2 s or less or over
    60 s (clock not updated).
    """
    out, cand, zero = [], 0, 0
    for j, p in enumerate(plays):
        if not is_snap(p, off):
            continue
        text = (p.get("text") or "").lower()
        t = p["type"]["text"]
        per = p.get("period", {}).get("number")
        clk = clock_secs(p.get("clock", {}).get("displayValue"))
        nxt = plays[j + 1] if j + 1 < len(plays) else None
        end = p.get("end", {})
        first_down = "1st down" in text or (end.get("down") == 1 and (end.get("team") or {}).get("id") == off
                                            and not p.get("scoringPlay"))
        if (KNEEL.search(text) or SPIKE.search(text) or t == "Pass Incompletion" or "incomplete" in text
                or p.get("scoringPlay") or p.get("id") in scoring_ids or t in TURNOVER
                or "penalty" in text or p.get("isPenalty") or OOB.search(text)
                or nxt is None or not is_snap(nxt, off) or nxt.get("period", {}).get("number") != per
                or (first_down and per in (2, 4) and clk is not None and clk <= 120)):
            continue
        c2 = clock_secs(nxt.get("clock", {}).get("displayValue"))
        if clk is None or c2 is None:
            continue
        iv = clk - c2
        cand += 1
        zero += iv == 0
        if 2 < iv <= 60:
            out.append(iv)
    return out, cand, zero


def parse_drives(summary, home_id, away_id, final):
    """Drives with offensive points rebuilt from ESPN's scoring plays."""
    prev = summary.get("drives", {}).get("previous", [])
    if not prev:
        return [], "no play-by-play", None
    side = {home_id: "home", away_id: "away"}
    play_drive = {p["id"]: i for i, d in enumerate(prev) for p in d.get("plays", [])}
    rows, method, corrections = score_rows(summary, side, final, play_drive)
    if rows is None:
        return [], method, None
    notes = [] if method == "play type" else [method]
    notes += corrections

    eoh = CONFIG["end_of_half_seconds"]
    scoring_ids = {r["id"] for r in rows}
    clock_cand = clock_zero = 0
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
        raw, seen = [], set()
        for p in d.get("plays", []):
            if "type" not in p:
                continue
            st = p.get("start", {})
            key = (p.get("period", {}).get("number"), p.get("clock", {}).get("displayValue"),
                   p.get("text"), st.get("down"), st.get("distance"), st.get("yardsToEndzone"))
            if key in seen:  # ESPN occasionally lists the same snap twice
                continue
            seen.add(key)
            raw.append(p)
        intervals, cand, zero = clean_intervals(raw, off, scoring_ids)
        clock_cand += cand
        clock_zero += zero
        pen_rows = sum(1 for p in raw if p["type"]["text"] == "Penalty"
                       and (p.get("start", {}).get("team") or {}).get("id") in (off, None))
        plays, first = [], None
        for p in raw:
            if p.get("start", {}).get("team", {}).get("id") not in (off, None):
                continue
            st = p.get("start", {})
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
            "iv": intervals,       # clean snap-to-snap game-clock seconds (pace)
            "pen_rows": pen_rows,  # snaps that were only a penalty (pre-snap fouls etc.)
        })
    # The leader's last regulation drive is clock-killing by definition (the user's
    # "burning clock to protect a lead"); ESPN often leaves its result blank, so it is
    # identified by position and score, not by the result text.
    live = [d for d in drives if d["plays"] and d["period"] <= 4]
    if live and live[-1]["period"] == 4 and live[-1]["margin"] > 0 and live[-1]["why"] == "":
        live[-1]["why"], live[-1]["kept"] = "leader's final drive", 0
    return drives, "; ".join(notes), {"cand": clock_cand, "zero": clock_zero}


def box_penalties(display):
    """'7-61' -> [7, 61]; None when missing or implausible (ESPN once printed '743-37')."""
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)\s*$", display or "")
    if not m:
        return None
    n, y = int(m.group(1)), int(m.group(2))
    if n > 30 or (n and not 0 <= y / n <= 25):
        return None
    return [n, y]


def box_stats(summary):
    out = {}
    for t in summary.get("boxscore", {}).get("teams", []):
        stats = {s["name"]: s.get("displayValue") for s in t.get("statistics", [])}
        try:
            to = int(stats.get("turnovers") or 0)
        except ValueError:
            to = None
        pen = stats.get("totalPenaltiesYards")
        out[t["team"]["id"]] = {"turnovers": to, "pen": box_penalties(pen), "pen_raw": pen}
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
            g["drives"], g["pbp_note"], g["clock"] = parse_drives(s, home, away, final)
            g["box"] = box_stats(s)
            g["market_home_margin"] = market_margin(s)
            why = {d["i"]: d["why"] for d in g["drives"]}
            g["penalties"] = [row + [why.get(row[1])]
                              for row in penalty_table(parse_game_penalties(s, game_id=eid))]
        elif g["d1"]:
            g["pbp_note"] = "no summary downloaded"
        games.append(g)
    out = os.path.join(HERE, "data", str(season))
    os.makedirs(out, exist_ok=True)
    with gzip.open(os.path.join(out, "games.json.gz"), "wt", encoding="utf-8") as f:
        json.dump({"season": season, "teams": members, "games": games, "upcoming": upcoming,
                   "penalty_fields": list(TABLE_FIELDS) + ["drive_why"]},
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
