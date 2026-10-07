"""AP Top 25 and College Football Playoff committee rankings, week by week.

    python polls.py                      every season with parsed data (data/<season>/)
    python polls.py --season 2025        one season
    python polls.py --season 2026 --refresh   re-download instead of using the cache

Downloads ESPN's published rankings (raw responses cached under cache/<season>/polls/) and
writes data/<season>/polls.json. The polls sit beside the ratings for reference only;
nothing in them enters any rating.

Each poll is pinned to the last game week it reflects, "after_week". ESPN names polls one
week ahead: its "Week 6" poll follows the week-5 games, and the preseason poll comes before
week 1, so its after_week is 0. The release date is checked against the game data: the poll
must come out after the middle kickoff of its week and before the middle kickoff of the next.
(The middle, not the last: a few games a season are played on a Sunday or Monday, sometimes
after the AP poll is out.) If the two readings disagree, this script stops rather than guess.
Bowl-season polls are never read: the ratings cover the regular season only.
"""
import argparse
import glob
import json
import os
import sys
from datetime import datetime

from fetch import CORE, HERE, get_json, read_gz, ref_id, write_gz

POLLS = {"1": "AP", "21": "CFP"}  # ESPN ranking ids: 1 = AP Top 25, 21 = Playoff Committee Rankings
MAX_WEEK = 20  # ESPN regular seasons run to week 15 or 16; extra weeks just come back empty


def when(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def download(season, refresh=False):
    """[(season_type, espn_week, ranking_id, payload)] for the preseason and regular season.

    The list of rankings for a week is always re-read: during a season the AP poll for a week
    appears on Sunday and the CFP ranking on Tuesday, so a cached list would miss the second.
    A released ranking itself does not change, so its payload is cached (unless --refresh)."""
    cache = os.path.join(HERE, "cache", str(season), "polls")
    out = []
    for stype, weeks in ((1, range(1, 3)), (2, range(1, MAX_WEEK + 1))):
        for w in weeks:
            idx = get_json(f"{CORE}/seasons/{season}/types/{stype}/weeks/{w}/rankings?lang=en")
            if not idx or not idx.get("items"):
                continue  # nothing released for this week (yet)
            write_gz(os.path.join(cache, f"t{stype}_w{w:02d}.json.gz"), idx)  # kept for the record
            for it in idx["items"]:
                rid = it["$ref"].split("/rankings/")[1].split("?")[0]
                if rid not in POLLS:
                    continue
                p = os.path.join(cache, f"t{stype}_w{w:02d}_r{rid}.json.gz")
                d = None
                if not (os.path.exists(p) and not refresh):
                    d = get_json(it["$ref"].replace("http://", "https://"))
                    if d and d.get("ranks"):
                        write_gz(p, d)
                if not (d and d.get("ranks")) and os.path.exists(p):
                    d = read_gz(p)  # ESPN listed it but did not return it this time: use the saved copy
                if not (d and d.get("ranks")):
                    raise SystemExit(f"{season}: ESPN lists the {POLLS[rid]} ranking for season type {stype} "
                                     f"week {w} but did not return it; run again later")
                out.append((stype, w, rid, d))
    return out


def middle_kickoffs(games):
    """week -> the median kickoff of that week's regular-season games."""
    by = {}
    for g in games:
        by.setdefault(g["week"], []).append(when(g["date"]))
    return {w: sorted(ts)[len(ts) // 2] for w, ts in by.items()}


def pin(stype, espn_week, released, middle):
    """The game week a poll reflects, or None if that week's games are not in the data yet.

    ESPN's label says one thing (preseason = 0, "Week N" = N - 1); the release date says the
    other (the latest week whose middle kickoff came before release). They must agree."""
    label = 0 if stype == 1 or espn_week == 1 else espn_week - 1
    if label > max(middle):
        return None
    by_date = max((w for w, t in middle.items() if t < when(released)), default=0)
    if by_date != label:
        raise SystemExit(f"poll week mismatch: ESPN season type {stype} week {espn_week} released "
                         f"{released} reads as after week {label}, but the game dates say after week "
                         f"{by_date}. Check the data before trusting either.")
    return label


def parse(season, raw, middle, teams):
    polls, waiting = [], []
    for stype, w, rid, d in raw:
        after = pin(stype, w, d["date"], middle)
        if after is None:
            waiting.append(f"{POLLS[rid]} ESPN week {w}")
            continue
        ranks = []
        for r in d["ranks"]:
            tid = ref_id(r["team"]["$ref"], "teams")
            if teams.get(tid, {}).get("division") != "FBS":
                raise SystemExit(f"{POLLS[rid]} after week {after}: ranked team {tid} is not an FBS team in the data")
            ranks.append({"rank": r["current"], "team": tid, "name": teams[tid].get("name", tid),
                          "record": (r.get("record") or {}).get("summary"),
                          "points": r.get("points"), "first_place_votes": r.get("firstPlaceVotes")})
        polls.append({"poll": POLLS[rid], "after_week": after, "released": d["date"],
                      "espn": {"season_type": stype, "week": w, "headline": d.get("headline")},
                      "ranks": sorted(ranks, key=lambda x: (x["rank"], x["name"]))})
    # One poll of each kind per game week (the later release wins if ESPN ever lists two).
    keep = {}
    for p in sorted(polls, key=lambda p: p["released"]):
        keep[(p["poll"], p["after_week"])] = p
    return sorted(keep.values(), key=lambda p: (p["after_week"], p["poll"])), waiting


def check(season, polls):
    """The AP poll comes out every week from the preseason on, and the committee every week once
    it starts; a hole means ESPN skipped one, so stop rather than show an older poll for that week."""
    ap_ = [p["after_week"] for p in polls if p["poll"] == "AP"]
    cfp = [p["after_week"] for p in polls if p["poll"] == "CFP"]
    for kind, weeks in (("AP", ap_), ("CFP", cfp)):
        if weeks and weeks != list(range(weeks[0], weeks[-1] + 1)):
            raise SystemExit(f"{season}: {kind} polls follow weeks {weeks}: one is missing; run again later")
    if ap_ and ap_[0] != 0:
        raise SystemExit(f"{season}: no preseason AP poll")
    return ap_, cfp


def write(season, refresh=False):
    from ratings import load
    data = load(season)
    raw = download(season, refresh)
    polls, waiting = parse(season, raw, middle_kickoffs(data["games"]), data["teams"])
    out = {"season": season,
           "source": f"{CORE}/seasons/{season}/types/<1 preseason | 2 regular season>/weeks/<w>/rankings/<1 AP | 21 CFP>",
           "rule": "after_week = the last game week a poll reflects: ESPN's 'Week N' poll follows week "
                   "N-1 and the preseason poll is 0; checked against the release date, which must fall "
                   "after the middle kickoff of that week and before the middle kickoff of the next",
           "polls": polls}
    ap_, cfp = check(season, polls)
    with open(os.path.join(HERE, "data", str(season), "polls.json"), "w") as f:
        json.dump(out, f, indent=1)
    span = lambda w: f" (after weeks {w[0]}-{w[-1]})" if w else ""
    print(f"{season}: {len(ap_)} AP polls{span(ap_)}, {len(cfp)} CFP rankings{span(cfp)}" +
          (f"; not yet in the game data: {', '.join(waiting)}" if waiting else ""))


def load_polls(season):
    """Parsed polls for a season, or None if polls.py has not been run for it."""
    p = os.path.join(HERE, "data", str(season), "polls.json")
    return json.load(open(p)) if os.path.exists(p) else None


def latest(polls, kind, week):
    """The newest poll of a kind that reflects games through `week` at most, or None."""
    got = [p for p in (polls or {}).get("polls", []) if p["poll"] == kind and p["after_week"] <= week]
    return max(got, key=lambda p: p["after_week"]) if got else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, action="append", help="season(s); default: every parsed season")
    ap.add_argument("--refresh", action="store_true", help="re-download instead of using cache/")
    a = ap.parse_args()
    seasons = a.season or sorted(int(os.path.basename(os.path.dirname(p)))
                                 for p in glob.glob(os.path.join(HERE, "data", "*", "games.json.gz")))
    for s in seasons:
        write(s, a.refresh)


if __name__ == "__main__":
    sys.exit(main())
