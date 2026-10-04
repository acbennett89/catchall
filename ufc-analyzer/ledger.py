"""Forward ledger: every flagged Caesars price (and every bet you log), settled against the closing
consensus and the result, so the app's real edge is measured going forward.

Closing-line value (CLV) = closing fair probability x the decimal price you got - 1.  It shows skill in
a few hundred bets, where ROI needs thousands.  The "close" is the last consensus the app saw before
the fight started, so leave the server running into fight night for the best numbers.

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
    """Add an entry.  Automatic entries are logged once per fight and side (the first time it's flagged)."""
    if fight["status"]["state"] != "pre":
        return None
    side = decision.get("side") if side is None else side
    if side is None:
        return None
    with _lock:
        doc = _load()
        if source == "auto" and any(e["fight"] == fight["id"] and e["side"] == side and e["source"] == "auto" for e in doc["entries"]):
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


def _closing(history_store, e):
    """Last consensus snapshot before the fight (market.history: [ts, czA, czB, fairA])."""
    series = history_store.get(f"{e['event']}:{e['fight']}") or []
    if not series:
        return None
    fair_a = next((s[3] for s in reversed(series) if s[3] is not None), None)
    if fair_a is None:
        return None
    return fair_a if e["side"] == 0 else 1 - fair_a


def report(history_store):
    """Entries with closing fair price, CLV, result and profit, plus summary lines."""
    with _lock:
        doc = _load()
    cards = {}
    out = []
    for e in doc["entries"]:
        e = dict(e)
        pc = _closing(history_store, e)
        d = value.to_decimal(e["price"])
        e["closeFair"] = round(pc, 4) if pc is not None else None
        e["clv"] = round(pc * d - 1, 4) if pc is not None else None
        try:
            card = cards.get(e["event"]) or espn.card(e["event"])
            cards[e["event"]] = card
            f = next((x for x in card["fights"] if x["id"] == e["fight"]), None)
        except Exception:
            f = None
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


def remove(entry_id):
    with _lock:
        doc = _load()
        n = len(doc["entries"])
        doc["entries"] = [e for e in doc["entries"] if e["id"] != entry_id]
        _save(doc)
        return n != len(doc["entries"])
