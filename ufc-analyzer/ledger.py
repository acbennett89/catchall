"""Forward ledger: every flagged Caesars price (and every bet you log), settled against the closing
consensus and the result, so the app's real edge is measured going forward.

Closing-line value (CLV) = closing fair probability x the decimal price you got - 1.  It shows skill in
a few hundred bets, where ROI needs thousands.  The "close" is the last consensus the app saw before
the fight started; the server keeps checking prices for cards with open entries, so leave it running
into fight night.  An entry gets no CLV if the app saw no price within an hour of the fight's start.

    cache/ledger.json   {"entries": [...]}
"""
import json, os, threading, time, uuid

import espn, value
from net import CACHE_DIR

PATH = os.path.join(CACHE_DIR, "ledger.json")
_lock = threading.Lock()


def _load():
    try:
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {"entries": []}


def _save(doc):
    os.makedirs(CACHE_DIR, exist_ok=True)
    tmp = PATH + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(doc, f, indent=1)
    os.replace(tmp, PATH)


def record(event_id, card, fight, decision, pred, source="auto", price=None, stake=None, side=None):
    """Add an entry.  Automatic entries are logged once per fight, side and action (the first WATCH and
    the first BET each get one, at the price when it was flagged)."""
    if fight["status"]["state"] != "pre":
        return None
    side = decision.get("side") if side is None else side
    if side is None:
        return None
    with _lock:
        doc = _load()
        if source == "auto" and any(e["fight"] == fight["id"] and e["side"] == side and e["source"] == "auto"
                                    and e.get("action") == decision.get("action") for e in doc["entries"]):
            return None
        e = {"id": uuid.uuid4().hex[:10], "ts": int(time.time()), "source": source, "event": event_id,
             "eventName": card.get("name"), "eventDate": card.get("date"), "fight": fight["id"],
             "fighters": [x["name"] for x in fight["fighters"]], "side": side,
             "price": price if price is not None else (pred.get("sides") or [{}, {}])[side].get("caesars"),
             "stake": stake, "action": decision.get("action"), "tier": decision.get("tier"),
             "ev": decision.get("ev"), "evMarket": decision.get("evMarket"),
             "pMarket": pred.get("market") if side == 0 or pred.get("market") is None else 1 - pred["market"],
             "pModel": pred["p"][side] if pred.get("p") else None,
             "pBet": pred["blend"][side] if pred.get("blend") else None}
        if e["price"] is None:
            return None
        doc["entries"].append(e)
        _save(doc)
        return e


CLOSE_WITHIN = 3600   # the last price seen must be from within an hour of the fight's scheduled start


def _closing(history_store, e, start):
    """(closing fair probability for the entry's side, when it was seen) from the last consensus the app
    saw before the fight (market.history "<key>:last", else the change series [ts, czA, czB, fairA])."""
    key = f"{e['event']}:{e['fight']}"
    last = history_store.get(key + ":last")
    seen = history_store.stamp(key + ":last") if last else None
    fair_a = last[3] if last else None
    if fair_a is None:
        series = history_store.get(key) or []
        fair_a = next((s[3] for s in reversed(series) if s[3] is not None), None)
        seen = history_store.stamp(key)
    if fair_a is None or not seen or (start and seen < start - CLOSE_WITHIN):
        return None, seen
    return (fair_a if e["side"] == 0 else 1 - fair_a), seen


def report(history_store):
    """Entries with closing fair price, CLV, result and profit, plus summary lines."""
    with _lock:
        doc = _load()
    cards = {}
    out = []
    for e in doc["entries"]:
        e = dict(e)
        d = value.to_decimal(e["price"])
        try:
            card = cards.get(e["event"]) or espn.card(e["event"])
            cards[e["event"]] = card
            f = next((x for x in card["fights"] if x["id"] == e["fight"]), None)
        except Exception:
            f = None
        # CLV only once the fight has started: before that the "close" would just be today's price
        started = bool(f and f["status"]["state"] != "pre")
        pc, seen = _closing(history_store, e, (f or {}).get("date")) if started else (None, None)
        e["closeFair"] = round(pc, 4) if pc is not None else None
        e["clv"] = round(pc * d - 1, 4) if pc is not None else None
        e["closeSeen"] = int(seen) if seen else None
        e["started"] = started
        if not started:
            now_fair, _ = _closing(history_store, e, None)
            e["fairNow"] = round(now_fair, 4) if now_fair is not None else None
        e["result"] = None
        if f and f["status"]["state"] == "post":
            winners = [i for i, x in enumerate(f["fighters"]) if x["winner"]]
            e["result"] = "push" if not winners else "won" if winners[0] == e["side"] else "lost"
        units = 1.0 if not e.get("stake") else float(e["stake"])
        e["profit"] = None if e["result"] is None else 0.0 if e["result"] == "push" else round(units * (d - 1), 2) if e["result"] == "won" else -units
        out.append(e)

    def summary(rows):
        clv = [r["clv"] for r in rows if r["clv"] is not None]
        settled = [r for r in rows if r["profit"] is not None and r["result"] != "push"]
        staked = sum((1.0 if not r.get("stake") else float(r["stake"])) for r in settled)
        return {"entries": len(rows), "withClose": len(clv), "clv": round(sum(clv) / len(clv), 4) if clv else None,
                "beatClose": round(sum(1 for v in clv if v > 0) / len(clv), 3) if clv else None,
                "settled": len(settled), "profit": round(sum(r["profit"] for r in settled), 2) if settled else 0.0,
                "roi": round(sum(r["profit"] for r in settled) / staked, 4) if staked else None}
    out.sort(key=lambda r: -r["ts"])
    return {"entries": out, "summary": {"all": summary(out),
                                        "flagged_bets": summary([r for r in out if r["source"] == "auto" and r["action"] == "BET"]),
                                        "flagged_watch": summary([r for r in out if r["source"] == "auto" and r["action"] == "WATCH"]),
                                        "your_bets": summary([r for r in out if r["source"] == "user"])}}


def open_events(within=4 * 86400):
    """Ledger events dated from 12 hours ago to `within` seconds ahead (cards whose closes are still to come)."""
    now = time.time()
    with _lock:
        doc = _load()
    seen, out = set(), []
    for e in doc["entries"]:
        d = e.get("eventDate") or 0
        if e["event"] not in seen and now - 12 * 3600 < d < now + within:
            seen.add(e["event"])
            out.append(e)
    return out


def remove(entry_id):
    with _lock:
        doc = _load()
        n = len(doc["entries"])
        doc["entries"] = [e for e in doc["entries"] if e["id"] != entry_id]
        _save(doc)
        return n != len(doc["entries"])
