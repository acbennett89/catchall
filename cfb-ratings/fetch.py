"""Download D-I college football data from ESPN's public API.

Writes raw JSON (gzipped) under cache/<season>/ so every derived number can be
re-checked against the source payload.

    python fetch.py --season 2026 --weeks 1-5
    python fetch.py --season 2025 --weeks 1-16 --scores-only
"""
import argparse
import gzip
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed


SITE = "https://site.api.espn.com/apis/site/v2/sports/football/college-football"
CORE = "https://sports.core.api.espn.com/v2/sports/football/leagues/college-football"
FBS_GROUP, FCS_GROUP = 80, 81
HERE = os.path.dirname(os.path.abspath(__file__))

_session = None  # requests is imported only when downloading, so parsing/rating need no extras


def session():
    global _session
    if _session is None:
        import requests
        _session = requests.Session()
    return _session


def get_json(url, tries=4):
    last = None
    for i in range(tries):
        try:
            r = session().get(url, timeout=60)
            if r.status_code == 200:
                return r.json()
            if r.status_code == 404:
                return None
            last = f"HTTP {r.status_code}"
        except Exception as e:  # network errors: retry with backoff
            last = f"{type(e).__name__}: {e}"
        time.sleep(2 ** (i + 1))
    raise RuntimeError(f"could not download {url} ({last}). Check the internet connection; a proxy "
                       "or antivirus that inspects HTTPS traffic can also block it.")


def write_gz(path, obj):
    """Write to a temporary name and rename into place, so an interrupted download never
    leaves a truncated file that later runs would trust."""
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".part"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f)
    os.replace(tmp, path)


def read_gz(path):
    with gzip.open(path, "rt", encoding="utf-8") as f:
        return json.load(f)


def ref_id(ref, kind):
    return re.search(rf"/{kind}/(\d+)", ref).group(1)


def fetch_membership(season, cache):
    """Division and conference for every FBS and FCS team, from ESPN's group tree."""
    out = {}
    for division, group in (("FBS", FBS_GROUP), ("FCS", FCS_GROUP)):
        children = get_json(f"{CORE}/seasons/{season}/types/2/groups/{group}/children?limit=100")
        for item in children["items"]:
            conf_id = ref_id(item["$ref"], "groups")
            info = get_json(f"{CORE}/seasons/{season}/types/2/groups/{conf_id}?lang=en")
            teams = get_json(f"{CORE}/seasons/{season}/types/2/groups/{conf_id}/teams?limit=200")
            for t in teams["items"]:
                tid = ref_id(t["$ref"], "teams")
                out[tid] = {
                    "division": division,
                    "conference_id": conf_id,
                    "conference": info.get("shortName") or info.get("name"),
                }
    names = get_json(f"{SITE}/teams?limit=1000")
    for t in names["sports"][0]["leagues"][0]["teams"]:
        t = t["team"]
        if t["id"] in out:
            out[t["id"]].update(name=t.get("location") or t["displayName"],
                                display=t["displayName"], abbr=t.get("abbreviation"))
    write_gz(os.path.join(cache, "membership.json.gz"), out)
    return out


def fetch_scoreboards(season, weeks, cache):
    events = {}
    for w in weeks:
        for group in (FBS_GROUP, FCS_GROUP):
            # limit above 500 silently falls back to ESPN's default page of 25.
            sb = get_json(f"{SITE}/scoreboard?dates={season}&seasontype=2&week={w}"
                          f"&groups={group}&limit=500")
            if len(sb.get("events", [])) >= 500:
                raise RuntimeError(f"week {w} group {group}: {len(sb['events'])} events, "
                                   "looks like a truncated page")
            write_gz(os.path.join(cache, "scoreboards", f"w{w:02d}_g{group}.json.gz"), sb)
            for e in sb.get("events", []):
                if "id" not in e:  # ESPN occasionally returns an empty placeholder event
                    continue
                e["_week"] = w
                events[e["id"]] = e
    return events


def fetch_summaries(event_ids, cache, workers=8):
    todo = [eid for eid in event_ids
            if not os.path.exists(os.path.join(cache, "summaries", f"{eid}.json.gz"))]
    print(f"summaries: {len(event_ids)} games, {len(todo)} to download", file=sys.stderr)

    def one(eid):
        s = get_json(f"{SITE}/summary?event={eid}")
        if s is None:
            return eid, False
        # Drop bulky fields that carry no game data.
        for k in ("news", "videos", "article", "broadcasts", "standings", "leaders"):
            s.pop(k, None)
        write_gz(os.path.join(cache, "summaries", f"{eid}.json.gz"), s)
        return eid, True

    done = 0
    ex = ThreadPoolExecutor(workers)
    futs = [ex.submit(one, e) for e in todo]
    try:
        for fut in as_completed(futs):
            fut.result()
            done += 1
            if done % 50 == 0:
                print(f"  {done}/{len(todo)}", file=sys.stderr)
    except KeyboardInterrupt:  # stop now: drop the queued downloads (finished ones are kept)
        for f in futs:
            f.cancel()
        ex.shutdown(wait=False)
        raise
    ex.shutdown()


def parse_weeks(s):
    a, _, b = s.partition("-")
    return list(range(int(a), int(b or a) + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, required=True)
    ap.add_argument("--weeks", required=True, help="e.g. 1-5")
    ap.add_argument("--scores-only", action="store_true",
                    help="skip play-by-play summaries (network backtest needs scores only)")
    args = ap.parse_args()
    cache = os.path.join(HERE, "cache", str(args.season))
    members = fetch_membership(args.season, cache)
    print(f"membership: {sum(v['division'] == 'FBS' for v in members.values())} FBS, "
          f"{sum(v['division'] == 'FCS' for v in members.values())} FCS", file=sys.stderr)
    events = fetch_scoreboards(args.season, parse_weeks(args.weeks), cache)
    final = [eid for eid, e in events.items()
             if e["competitions"][0]["status"]["type"].get("completed")]
    d1 = [eid for eid in final
          if all(c["team"]["id"] in members for c in events[eid]["competitions"][0]["competitors"])]
    print(f"scoreboards: {len(events)} events, {len(final)} final, {len(d1)} D-I vs D-I",
          file=sys.stderr)
    if not args.scores_only:
        fetch_summaries(d1, cache)


if __name__ == "__main__":
    main()
