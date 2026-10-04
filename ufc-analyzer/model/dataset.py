"""Build the training table: one row per decided UFC fight, features as of fight day.

Rows are oriented deterministically-at-random (hash of the fight id), because UFCStats lists the
winner first; without this the label would leak through the order.
"""
import hashlib

from model import engine, features, scrape


def orient_swap(fight_id):
    return int(hashlib.md5(fight_id.encode()).hexdigest(), 16) % 2 == 1


def ufc_results(fights):
    """fighter id -> {"W": n, "L": n} over the whole UFC dataset (for outside-record estimates)."""
    out = {}
    for r in fights.values():
        for fid, side in ((r["f1"], "f1"), (r["f2"], "f2")):
            d = out.setdefault(fid, {"W": 0, "L": 0})
            if r["result"] == side:
                d["W"] += 1
            elif r["result"] in ("f1", "f2"):
                d["L"] += 1
    return out


def build_rows(events=None, fights=None, fighters=None, engine_params=None, since="1997-01-01"):
    if events is None:
        events, fights, fighters = scrape.load_dataset()
    eng = engine.Engine(engine_params)
    totals = ufc_results(fights)
    outside = {fid: features.outside_record(fighters.get(fid), totals.get(fid, {})) for fid in totals}
    rows = []

    def on_event(e, bouts, day):
        for r in bouts:
            div = features.division_of(r)
            fa, fb = eng.get(r["f1"]), eng.get(r["f2"])
            A = features.fighter_profile(eng, fa, fighters.get(r["f1"]), day, div, outside.get(r["f1"], (0, 0)))
            B = features.fighter_profile(eng, fb, fighters.get(r["f2"]), day, div, outside.get(r["f2"], (0, 0)))
            swap = orient_swap(r["id"])
            if swap:
                A, B = B, A
            res = r["result"]
            if res in ("f1", "f2"):
                y = 1 if (res == "f1") != swap else 0
            else:
                y = None
            kind = engine.method_class(r.get("method"))
            rows.append({
                "id": r["id"], "date": r["date"], "year": int(r["date"][:4]), "div": div,
                "a": r["f2"] if swap else r["f1"], "b": r["f1"] if swap else r["f2"],
                "na": r["n2"] if swap else r["n1"], "nb": r["n1"] if swap else r["n2"], "swap": swap,
                "y": y, "result": res, "kind": kind, "round": r.get("round"), "secs": engine.finish_seconds(r),
                "rounds": r.get("rounds") or (5 if r.get("title") else 3), "title": bool(r.get("title")),
                "order": r.get("order"), "x": features.win_features(A, B), "A": A, "B": B,
            })
    eng.replay(events, fights, on_event=on_event)
    return [r for r in rows if r["date"] >= since], eng, outside
