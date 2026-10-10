"""Sportsbook point spreads and totals, to set beside the model's own line (reference only:
nothing here enters a rating).

    python odds.py                  every season with parsed data (data/<season>/)
    python odds.py --season 2026    one season

Two sources:

1. ESPN's odds feed: every sportsbook ESPN lists for a game. ESPN listed Caesars Sportsbook for
   2022 and 2023 games (its state desks, New Jersey, Colorado and Tennessee, and a generic entry);
   for 2024 and 2025 mostly ESPN BET, and for 2026 only DraftKings. A finished game's lines are
   downloaded once (cache/<season>/odds/): its "closing" line is the value ESPN shows after the
   game. A game not yet played is re-read on every run; a read at or after kickoff is marked
   after_kickoff (shown, never starred). In-game ("Live Odds") entries are never used.
2. Caesars Sportsbook through The Odds API (the-odds-api.com, bookmaker "williamhill_us"), for
   games not yet played, when a key is set: the environment variable ODDS_API_KEY or the file
   odds_api_key.txt next to this script. The Odds API offers Caesars on paid plans only (its free
   plan leaves it out); a run costs 2 credits. Only reads before kickoff are kept, the last one
   winning, in cache/<season>/odds_api_lines.json, which git ignores and the installer keeps:
   a line for a game already played cannot be read again.

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
# The book the model is compared with, best first: Caesars' state desks as ESPN listed them (they
# agree with each other and with the market), then ESPN's generic "Caesars Sportsbook" entry (often
# stale in 2022-23: used only without a state desk), then Caesars read from The Odds API. Without a
# Caesars line, ESPN's own book that season stands in. betting.book_line also passes over a line
# 3+ points from the other books' median (a stale entry).
CAESARS = ("Caesars Sportsbook (New Jersey)", "Caesars Sportsbook (Colorado)", "Caesars Sportsbook (Tennessee)",
           "Caesars Sportsbook", ODDS_API_BOOK)
STAND_INS = ("ESPN BET", "DraftKings", "consensus")
PROJECTIONS = ("accuscore", "teamrankings", "numberfire")  # ESPN lists these, but they are models, not books


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
    """The key from ODDS_API_KEY or odds_api_key.txt. Notepad and PowerShell may save the file
    with a byte-order mark or as UTF-16; only the key's letters and digits are kept."""
    key = os.environ.get("ODDS_API_KEY", "")
    p = os.path.join(HERE, "odds_api_key.txt")
    if not key.strip() and os.path.exists(p):
        raw = open(p, "rb").read()
        key = raw.decode("utf-16") if raw[:2] in (b"\xff\xfe", b"\xfe\xff") else raw.decode("utf-8-sig", "replace")
    key = re.sub(r"[^A-Za-z0-9]", "", key)
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
    # Only the games build.py predicts: the next week with an FBS game (the latest week's own
    # games when it is still in progress). Later weeks are re-read once they come up.
    last = max((g["week"] for g in data["games"] if g["d1"]), default=0)
    soon = [u for u in data.get("upcoming", []) if fbs(u) and u["week"] >= last]
    nxt = min((u["week"] for u in soon), default=None)
    upcoming = [u for u in soon if u["week"] == nxt]
    start = {u["id"]: when(u["date"]) for u in upcoming}
    path = os.path.join(HERE, "data", str(season), "lines.json")
    old = json.load(open(path, encoding="utf-8"))["games"] if os.path.exists(path) else {}

    lines, stamp, read = {}, now_iso(), datetime.now(timezone.utc)
    for gid, payload in download_espn(season, finished, [u["id"] for u in upcoming]).items():
        books = espn_lines(payload)
        final = gid in set(finished)
        late = not final and read >= start[gid]  # this game's current line may be from after kickoff
        lines[gid] = {b: {**v, "source": "ESPN " + ("closing" if final else "current"),
                          "read_at": None if final else stamp, **({"after_kickoff": True} if late else {})}
                      for b, v in books.items()}

    # Caesars read from The Odds API: kept in cache/ (never reset by the installer), last read before kickoff.
    kept_path = os.path.join(HERE, "cache", str(season), "odds_api_lines.json")
    kept = json.load(open(kept_path, encoding="utf-8")) if os.path.exists(kept_path) else {}
    for gid, books in old.items():  # reads an older version of this script left in lines.json
        if ODDS_API_BOOK in books:
            kept.setdefault(gid, books[ODDS_API_BOOK])
    key, note = odds_api_key(), ""
    events = None
    if key and upcoming:
        try:
            events, left = download_odds_api(key)
        except Exception as e:  # a bad key or an outage: keep ESPN's lines and the Caesars lines already read
            note = f"; Caesars lines not read from The Odds API ({str(e).replace(key, '***')})"
    if events is not None:
        pairs, unmatched = match_odds_api(events, upcoming, teams)
        n = 0
        for gid, (ev, swapped) in pairs.items():
            if read >= min(start[gid], when(ev["commence_time"])):
                continue  # kicked off: an in-game line, not a pregame one
            c = caesars_from_event(ev, ev["away_team"] if swapped else ev["home_team"], stamp)
            if c:
                kept[gid] = c
                n += 1
        has_caesars = any(bk.get("key") == "williamhill_us" for ev in events for bk in ev.get("bookmakers") or [])
        note = (f"; Caesars from The Odds API for {n} games ({left} credits left this month)" +
                ("" if has_caesars or not events else
                 "; The Odds API sent no Caesars (williamhill_us) lines: Caesars needs a paid Odds API plan") +
                (f"; {len(unmatched)} Odds API games not matched to ESPN's schedule" if unmatched else ""))
        for u in unmatched[:10]:
            print("  not matched:", u, file=sys.stderr)
    elif upcoming and not key:
        note = "; no Odds API key, so games not yet played have no Caesars line (see odds.py)"
    if kept:
        os.makedirs(os.path.dirname(kept_path), exist_ok=True)
        with open(kept_path + ".part", "w", encoding="utf-8") as f:
            json.dump(kept, f, indent=0, sort_keys=True)
        os.replace(kept_path + ".part", kept_path)
    for gid, c in kept.items():
        if gid in lines:
            lines[gid][ODDS_API_BOOK] = c

    out = {"season": season, "source": {"espn": f"{CORE}/events/<id>/competitions/<id>/odds",
                                        "odds_api": ODDS_API + " (bookmaker williamhill_us)"},
           "rule": "home_spread is the home team's point spread (negative = home favored); a finished "
                   "game's ESPN lines are the values ESPN shows after it (closing); a game not yet played "
                   "has the current line, marked after_kickoff when read at or after kickoff; Caesars read "
                   "from The Odds API is the last line read before kickoff",
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
