"""Sportsbook point spreads and totals, to set beside the model's own line (reference only:
nothing here enters a rating).

    python odds.py                  every season with parsed data (data/<season>/)
    python odds.py --season 2026    one season

Two sources:

1. ESPN's odds feed: every sportsbook ESPN lists for a game. ESPN listed Caesars Sportsbook for
   2022 and 2023 games; for 2024 and 2025 only ESPN BET, and for 2026 only DraftKings. A finished
   game's lines are its closing lines and are downloaded once (cache/<season>/odds/); a game not
   yet played is re-read on every run. In-game ("Live Odds") lines are never used.
2. Caesars Sportsbook through The Odds API (the-odds-api.com, bookmaker "williamhill_us"), for
   games not yet played, when a key is set: the environment variable ODDS_API_KEY or the file
   odds_api_key.txt next to this script. The free plan has 500 credits a month; a run costs 2.
   A line read after kickoff is ignored; the last one read before kickoff is kept.

Writes data/<season>/lines.json: game id -> book -> {"home_spread", "total", "source", "read_at"}.
Spreads are from the home team's side, as ESPN lists home and away: -7 = home favored by 7.
"""
import argparse
import glob
import gzip
import json
import os
import re
import sys
import unicodedata
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from difflib import SequenceMatcher

from fetch import CORE, HERE, get_json, read_gz, session, write_gz

ODDS_API = "https://api.the-odds-api.com/v4/sports/americanfootball_ncaaf/odds"
ODDS_API_BOOK = "Caesars Sportsbook (The Odds API)"
# The book the model is compared with, best first: Caesars as ESPN listed it, then Caesars read
# live from The Odds API. Without any Caesars line, ESPN's own book that season stands in.
CAESARS = ("Caesars Sportsbook", "Caesars Sportsbook (New Jersey)", "Caesars Sportsbook (Colorado)",
           "Caesars Sportsbook (Tennessee)", ODDS_API_BOOK)
STAND_INS = ("ESPN BET", "DraftKings", "consensus")


def now_iso():
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def when(iso):
    return datetime.fromisoformat(iso.replace("Z", "+00:00"))


def espn_lines(payload):
    """book -> {"home_spread", "total"} from ESPN's odds list for one game."""
    out = {}
    for it in (payload or {}).get("items") or []:
        name = (it.get("provider") or {}).get("name") or ""
        if not name or "live" in name.lower() or name in out:
            continue
        spread, total = it.get("spread"), it.get("overUnder")
        # ESPN's "spread" is the home team's; check it against the home team's own point spread.
        home = (((it.get("homeTeamOdds") or {}).get("current") or {}).get("pointSpread") or {}).get("american")
        if home not in (None, "", "EVEN", "PK"):
            try:
                if spread is not None and abs(float(home) - float(spread)) > 1e-9:
                    continue  # the two disagree: skip this book rather than guess its sign
            except ValueError:
                pass
        if isinstance(spread, (int, float)) or isinstance(total, (int, float)):
            out[name] = {"home_spread": float(spread) if isinstance(spread, (int, float)) else None,
                         "total": float(total) if isinstance(total, (int, float)) and total > 0 else None}
    return out


def download_espn(season, finished, upcoming, workers=8):
    """game id -> ESPN odds payload. Finished games come from the cache when present."""
    cache = os.path.join(HERE, "cache", str(season), "odds")
    got, todo = {}, []
    for gid in finished:
        p = os.path.join(cache, f"{gid}.json.gz")
        if os.path.exists(p):
            got[gid] = read_gz(p)
        else:
            todo.append((gid, True))
    todo += [(gid, False) for gid in upcoming]
    print(f"{season}: ESPN lines for {len(finished) + len(upcoming)} games, {len(todo)} to download",
          file=sys.stderr)

    def one(gid, final):
        d = get_json(f"{CORE}/events/{gid}/competitions/{gid}/odds?lang=en&limit=50") or {"items": []}
        if final:
            write_gz(os.path.join(cache, f"{gid}.json.gz"), d)
        return gid, d

    with ThreadPoolExecutor(workers) as ex:
        for fut in as_completed([ex.submit(one, g, f) for g, f in todo]):
            gid, d = fut.result()
            got[gid] = d
    return got


def odds_api_key():
    key = os.environ.get("ODDS_API_KEY", "").strip()
    p = os.path.join(HERE, "odds_api_key.txt")
    if not key and os.path.exists(p):
        key = open(p, encoding="utf-8").read().strip()
    return key or None


# Short names spelled out, so "UCF Knights" and "Central Florida Knights" read alike.
ALIASES = {"ucf": "central florida", "byu": "brigham young", "smu": "southern methodist",
           "tcu": "texas christian", "utep": "texas el paso", "utsa": "texas san antonio",
           "unlv": "nevada las vegas", "uconn": "connecticut", "umass": "massachusetts",
           "ole miss": "mississippi", "app state": "appalachian state", "southern miss": "southern mississippi",
           "ul monroe": "louisiana monroe", "fiu": "florida international", "fau": "florida atlantic",
           "lsu": "louisiana state", "usc": "southern california", "uab": "alabama birmingham",
           "niu": "northern illinois", "wku": "western kentucky", "nc state": "north carolina state",
           "sam houston": "sam houston state", "ulm": "louisiana monroe", "ecu": "east carolina",
           "miami oh": "miami ohio", "pitt": "pittsburgh"}


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = s.replace("&", " and ").replace("'", "").replace("st.", "state")
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    for short, full in sorted(ALIASES.items(), key=lambda kv: -len(kv[0])):
        if s == short or s.startswith(short + " "):
            s = full + s[len(short):]
            break
    return s.replace("sam houston state state", "sam houston state")


def similarity(a, b):
    a, b = norm(a), norm(b)
    if not a or not b:
        return 0.0
    return 1.0 if a == b else SequenceMatcher(None, a, b).ratio()


def match_odds_api(events, upcoming, teams, hours=6):
    """Pair each Odds API event with the ESPN game it is: kickoff within `hours`, and both team
    names alike (home and away may be swapped at a neutral site). The most alike pairs are taken
    first, and each game and event is used once. Returns ({game id: (event, swapped)},
    [unmatched event descriptions])."""
    names = lambda t: [x for x in (teams.get(t, {}).get("display"), teams.get(t, {}).get("name")) if x]
    side = lambda n, t: max((similarity(n, x) for x in names(t)), default=0.0)
    cands = []
    for i, ev in enumerate(events):
        t = when(ev["commence_time"])
        for g in upcoming:
            if abs((when(g["date"]) - t).total_seconds()) > hours * 3600:
                continue
            for swapped in (False, True):
                h, a = (g["away"], g["home"]) if swapped else (g["home"], g["away"])
                sh, sa = side(ev["home_team"], h), side(ev["away_team"], a)
                if min(sh, sa) >= 0.6 and (sh + sa) / 2 >= 0.75:
                    cands.append(((sh + sa) / 2, i, g["id"], swapped))
    pairs, used = {}, set()
    for score, i, gid, swapped in sorted(cands, key=lambda c: -c[0]):
        if i in used or gid in pairs:
            continue
        pairs[gid] = (events[i], swapped)
        used.add(i)
    unmatched = [f"{ev.get('away_team')} at {ev.get('home_team')} ({ev.get('commence_time')})"
                 for i, ev in enumerate(events) if i not in used]
    return pairs, unmatched


def caesars_from_event(ev, home_name_in_event, read_at):
    """{"home_spread", "total"} for the ESPN home team from one Odds API event, or None."""
    for bk in ev.get("bookmakers") or []:
        if bk.get("key") != "williamhill_us":
            continue
        out = {"home_spread": None, "total": None}
        for m in bk.get("markets") or []:
            if m.get("key") == "spreads":
                for o in m.get("outcomes") or []:
                    if o.get("name") == home_name_in_event and isinstance(o.get("point"), (int, float)):
                        out["home_spread"] = float(o["point"])
            elif m.get("key") == "totals":
                for o in m.get("outcomes") or []:
                    if o.get("name") == "Over" and isinstance(o.get("point"), (int, float)):
                        out["total"] = float(o["point"])
        if out["home_spread"] is not None or out["total"] is not None:
            return {**out, "source": "The Odds API (williamhill_us)", "read_at": read_at,
                    "book_update": bk.get("last_update")}
    return None


def download_odds_api(key):
    r = session().get(ODDS_API, timeout=60, params={
        "apiKey": key, "regions": "us", "markets": "spreads,totals", "bookmakers": "williamhill_us",
        "oddsFormat": "american", "dateFormat": "iso"})
    if r.status_code != 200:
        raise RuntimeError(f"The Odds API answered HTTP {r.status_code}: {r.text[:200]}")
    left = r.headers.get("x-requests-remaining")
    return r.json(), left


def write(season):
    from ratings import load
    data = load(season)
    teams = data["teams"]
    fbs = lambda g: "FBS" in (teams[g["home"]]["division"], teams[g["away"]]["division"])
    finished = [g["id"] for g in data["games"] if g["d1"] and fbs(g)]
    upcoming = [u for u in data.get("upcoming", []) if fbs(u)]
    path = os.path.join(HERE, "data", str(season), "lines.json")
    old = json.load(open(path, encoding="utf-8"))["games"] if os.path.exists(path) else {}

    lines, stamp = {}, now_iso()
    for gid, payload in download_espn(season, finished, [u["id"] for u in upcoming]).items():
        books = espn_lines(payload)
        final = gid in set(finished)
        lines[gid] = {b: {**v, "source": "ESPN " + ("closing" if final else "current"),
                          "read_at": None if final else stamp} for b, v in books.items()}
    # Caesars lines read live in earlier runs stay: the last one read before kickoff.
    for gid, books in old.items():
        if ODDS_API_BOOK in books and gid in lines:
            lines[gid][ODDS_API_BOOK] = books[ODDS_API_BOOK]

    key, note = odds_api_key(), ""
    events = None
    if key and upcoming:
        try:
            events, left = download_odds_api(key)
        except Exception as e:  # a bad key or an outage: keep ESPN's lines and the Caesars lines already read
            note = f"; Caesars lines not read from The Odds API ({e})"
    if events is not None:
        pairs, unmatched = match_odds_api(events, upcoming, teams)
        start = {u["id"]: when(u["date"]) for u in upcoming}
        read = datetime.now(timezone.utc)
        n = 0
        for gid, (ev, swapped) in pairs.items():
            if read >= start[gid]:
                continue  # kicked off: an in-game line, not a pregame one
            c = caesars_from_event(ev, ev["away_team"] if swapped else ev["home_team"], stamp)
            if c:
                lines.setdefault(gid, {})[ODDS_API_BOOK] = c
                n += 1
        note = (f"; Caesars from The Odds API for {n} games ({left} credits left this month)" +
                (f"; {len(unmatched)} Odds API games not matched to ESPN's schedule" if unmatched else ""))
        if unmatched:
            for u in unmatched[:10]:
                print("  not matched:", u, file=sys.stderr)
    elif upcoming and not key:
        note = "; no Odds API key, so games not yet played have no Caesars line (see odds.py)"

    out = {"season": season, "source": {"espn": f"{CORE}/events/<id>/competitions/<id>/odds",
                                        "odds_api": ODDS_API + " (bookmaker williamhill_us)"},
           "rule": "home_spread is the home team's point spread (negative = home favored); finished "
                   "games carry ESPN's closing lines; Caesars read from The Odds API is the last line "
                   "read before kickoff",
           "games": {g: lines[g] for g in sorted(lines)}}
    with open(path + ".part", "w", encoding="utf-8") as f:
        json.dump(out, f, indent=0, sort_keys=True)
    os.replace(path + ".part", path)
    caesars = sum(1 for g in finished if any(b in lines.get(g, {}) for b in CAESARS))
    print(f"{season}: lines for {sum(1 for g in finished if lines.get(g))} of {len(finished)} finished games "
          f"({caesars} with Caesars), {sum(1 for u in upcoming if lines.get(u['id']))} of {len(upcoming)} "
          f"upcoming{note}")


def load_lines(season):
    """data/<season>/lines.json's games, or {} if odds.py has not been run for the season."""
    p = os.path.join(HERE, "data", str(season), "lines.json")
    return json.load(open(p, encoding="utf-8"))["games"] if os.path.exists(p) else {}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, action="append", help="season(s); default: every parsed season")
    a = ap.parse_args()
    seasons = a.season or sorted(int(os.path.basename(os.path.dirname(p)))
                                 for p in glob.glob(os.path.join(HERE, "data", "*", "games.json.gz")))
    for s in seasons:
        write(s)


if __name__ == "__main__":
    sys.exit(main())
