"""The raw material for the ratings: every UFC fight in date order with both fighters' stats, the
round-by-round stats where scraped, fighter attributes, ESPN pre-UFC records and the betting market.

Nothing here is a rating; this only reads model/data and ratings/data and normalizes units.
"""
import datetime, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

from model import espn_hist, market_hist, odds_history, scrape  # noqa: E402
from ratings import rounds as rounds_mod  # noqa: E402

ROUND_SECS = 300
DECISIONS = ("U-DEC", "S-DEC", "M-DEC")


def method_class(m):
    """ko | sub | dec | other (overturned, DQ, no contest...).  CNC (could not continue) counts as ko."""
    m = (m or "").upper()
    if m.startswith("KO") or m.startswith("TKO") or m == "CNC":
        return "ko"
    if m.startswith("SUB"):
        return "sub"
    if "DEC" in m:
        return "dec"
    return "other"


def division(wc):
    """Weight class string -> division key ('lightweight', 'w strawweight', 'catch'...)."""
    s = (wc or "").lower().replace("ufc", "").replace("title", "").replace("bout", "").replace("interim", "")
    s = s.replace("tournament", "").replace("ultimate fighter", "").replace("tuf", "")
    w = "w " if "women" in s else ""
    for d in ("strawweight", "flyweight", "bantamweight", "featherweight", "lightweight", "welterweight",
              "middleweight", "light heavyweight", "heavyweight"):
        if d in s and not (d == "heavyweight" and "light heavyweight" in s):
            return w + d
    if "open" in s or "super" in s:
        return "heavyweight"
    return "catch"


def fight_seconds(r):
    """How long the fight lasted, from the finish round and clock (5-minute rounds; the old 1-round
    formats are treated as one long round)."""
    try:
        m, s = (r.get("time") or "0:00").split(":")
        rnd = int(r.get("round") or 1)
        return max(1, (rnd - 1) * ROUND_SECS + int(m) * 60 + int(s))
    except ValueError:
        return None


def parse_day(s):
    return datetime.date.fromisoformat(s) if s else None


def load():
    """All sources, keyed and ready.  Fights come back sorted by (date, event, order)."""
    events, fights, fighters = scrape.load_dataset()
    rounds = rounds_mod.load()
    hist = espn_hist.load()
    out = []
    for r in fights.values():
        if not r.get("date") or not r.get("s1") or not r.get("s2"):
            continue
        rr = rounds.get(r["id"])
        out.append(dict(r, kind=method_class(r.get("method")), div=division(r.get("wc")), secs=fight_seconds(r),
                        rounds_data=rr if isinstance(rr, list) else None))
    out.sort(key=lambda r: (r["date"], r["event"], -(r.get("order") or 0)))
    return {"events": events, "fights": out, "fighters": fighters, "espn": hist}


def market():
    """{fight id: open/close market dict} from BestFightOdds history."""
    _, fights, _ = scrape.load_dataset()
    return market_hist.join(fights, odds_history.load())
