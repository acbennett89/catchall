"""The odds side of a card: every book's moneyline per fight, the no-vig market price, Caesars' edge
against it, Caesars props worth a look, and how Caesars' line has moved since this app first saw it.
"""
import time

import bfo, espn, value
from net import cache, DiskStore

history = DiskStore("odds_history")


def _track(event_id, fight_id, cz, fair):
    """Append a Caesars/fair snapshot when it changes; return the series [[ts, czA, czB, fairA], ...]."""
    key = f"{event_id}:{fight_id}"
    series = list(history.get(key) or [])
    snap = [int(time.time()), cz[0] if cz else None, cz[1] if cz else None, round(fair, 4) if fair else None]
    if not series or series[-1][1:3] != snap[1:3] or (snap[3] and series[-1][3] and abs(series[-1][3] - snap[3]) >= 0.01):
        series.append(snap)
        history.put(key, series[-200:])
    return series


def fight_odds(event_id, fight, match, track=True):
    lines = {}
    if match:
        for book, pair in match["ml"].items():
            if pair[0] is not None or pair[1] is not None:
                lines[book] = tuple(pair)
    dk = [f.get("dkMoneyline") for f in fight["fighters"]]
    if "DraftKings" not in lines and all(v is not None for v in dk):
        lines["DraftKings"] = (int(dk[0]), int(dk[1]))
    read = value.assess(lines)
    cz = lines.get(value.TARGET_BOOK)
    out = {
        "source": "bestfightodds" if match else ("espn" if lines else None),
        "bfoEvent": match["event"] if match else None,
        "bfoUrl": match["eventUrl"] if match else None,
        "lines": {b: list(v) for b, v in lines.items()},
        "value": read,
        "props": [],
    }
    if match:
        props = []
        for p in match["props"]:
            plines = {b: tuple(v) for b, v in p["odds"].items()}
            for side in value.assess_prop(p["labels"], plines):
                side["type"] = p["type"]
                props.append(side)
        props.sort(key=lambda s: (s["ev"] is None, -(s["ev"] if s["ev"] is not None else s["vsMarket"] or -1)))
        out["props"] = props
    if track and fight["status"]["state"] == "pre" and (cz or read["fair"]):
        out["movement"] = _track(event_id, fight["id"], cz, read["fair"][0] if read["fair"] else None)
    return out


def card_odds(event_id):
    def load():
        card = espn.card(event_id)
        try:
            matches = bfo.odds_for_card(card)
            err = None
        except Exception as e:  # BFO down: still show ESPN's DraftKings lines
            matches, err = {}, str(e)
        fights = {f["id"]: fight_odds(event_id, f, matches.get(f["id"])) for f in card["fights"]}
        return {"event": event_id, "fights": fights, "at": int(time.time() * 1000), "error": err,
                "target": value.TARGET_BOOK, "past": card["state"] == "post"}

    def ttl(v):
        return 6 * 3600 if v["past"] else 45
    return cache.get(("card-odds", event_id), load, ttl=ttl)
