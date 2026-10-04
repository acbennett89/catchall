"""The ratings model (KenPom-style power ratings) for a card: per-fight prediction, both fighters'
rating cards with division rank, and a division leaderboard.

    predictions(event_id) -> {"fights": {fight_id: {...}}, "model": {metadata + evaluation}}
    leaderboard(div)      -> ranked active fighters of a division
"""
import datetime, math, time

import espn, ufcstats
from model import espn_hist
from modelapi import card_day
from net import cache
from ratings import fightdata

try:
    from ratings import predict as _predict
except Exception:  # package missing or broken: the rest of the app still works
    _predict = None


def available():
    return bool(_predict and _predict.available())


def _side(fighter):
    """UFCStats id (by name, cached), ESPN bio fallbacks for debutants, and the pre-UFC record."""
    try:
        a = espn.athlete(fighter["id"])
    except Exception:
        a = {}
    name = a.get("name") or fighter.get("name") or ""
    first, _, last = name.partition(" ")
    try:
        uid = ufcstats.find_id(name, first, last.split(" ")[-1] if last else None, fighter["id"], a.get("record") or fighter.get("record"))
    except Exception:
        uid = None
    attrs = None
    if a:
        from model.predict import parse_espn_dob
        attrs = {"dob": parse_espn_dob(a.get("dob"), a.get("age")), "height": _inches(a.get("height")), "reach": _inches(a.get("reach")),
                 "stance": a.get("stance"), "record": a.get("record")}
    hist = espn_hist.compact_history(a) if a else None
    return {"ufcstats_id": uid or f"espn:{fighter['id']}", "name": name, "attrs": attrs, "hist": hist}


def _inches(s):
    import re
    if not s:
        return None
    m = re.match(r"(\d+)'\s*(\d+)", s)
    if m:
        return int(m.group(1)) * 12 + int(m.group(2))
    m = re.match(r"([\d.]+)", s)
    return float(m.group(1)) if m else None


def fight_prediction(card, f):
    day = card_day(card.get("date"))
    a, b = (_side(x) for x in f["fighters"])
    st = _predict._load()
    attrs = {}
    outside = {}
    for s in (a, b):
        if s["attrs"] and s["ufcstats_id"] not in st["data"]["fighters"]:
            attrs[s["ufcstats_id"]] = s["attrs"]
        if s["hist"]:
            w, l, fin = espn_hist.outside_before(s["hist"], day.isoformat())
            outside[s["ufcstats_id"]] = (w, l, fin, True)
    hist = _hist_bout(st, a["ufcstats_id"], b["ufcstats_id"], day)
    if hist:
        day = min(day, hist[0])
    rounds = (hist[1] if hist else None) or f.get("rounds") or 3
    div = fightdata.division(f.get("weightClass") or "")
    if div == "catch":
        sd = _predict.state_on(day)
        div = sd["last_div"].get(a["ufcstats_id"]) or sd["last_div"].get(b["ufcstats_id"]) or "catch"
    pred = _predict.predict(a["ufcstats_id"], b["ufcstats_id"], day=day, div=div, rounds=rounds, title=bool(f.get("title")), attrs=attrs, outside=outside)
    pred["ids"] = [a["ufcstats_id"], b["ufcstats_id"]]
    pred["names"] = [a["name"], b["name"]]
    pred["div"] = div
    return pred


def _hist_bout(st, a_id, b_id, day):
    for r in st["data"]["fights"]:
        if {r["f1"], r["f2"]} == {a_id, b_id} and abs((fightdata.parse_day(r["date"]) - day).days) <= 1:
            return fightdata.parse_day(r["date"]), r.get("rounds")
    return None


def predictions(event_id):
    if not available():
        return {"available": False}

    def load():
        card = espn.card(event_id)
        out = {}
        for f in card["fights"]:
            try:
                out[f["id"]] = fight_prediction(card, f)
            except Exception as e:
                out[f["id"]] = {"error": f"{type(e).__name__}: {e}"}
        meta = dict(_predict._load()["model"])
        summary = {k: meta.get(k) for k in ("built", "trained_through", "fights", "windows", "evaluation", "ablation", "blend_model_for_comparison", "description")}
        summary["importance"] = (meta.get("win") or {}).get("importance", [])[:15]
        summary["cagepoints"] = _cagepoints()
        return {"available": True, "fights": out, "model": summary, "at": int(time.time() * 1000)}
    return cache.get(("ratings", event_id), load, ttl=600)


def _cagepoints():
    try:
        from ratings import cagepoints
        c = cagepoints.load()
        return {k: round(v, 4) for k, v in c.items()} if c else None
    except Exception:
        return None


def leaderboard(div=None, top=25):
    """Active fighters of a division ranked by adjusted efficiency margin (qualified first, provisional
    fighters listed after with no rank)."""
    if not available():
        return {"available": False}
    st = _predict._load()
    sd = _predict.state_on(datetime.date.today())
    R = sd["R"]
    rows = []
    for fid, rk in sd["ranks"].items():
        if div and rk["div"] != div:
            continue
        bouts = R.ledger.log.get(fid) or []
        e = R.eff_profile(fid, rk["div"], sd["day"].toordinal())
        rows.append({"id": fid, "name": st["names"].get(fid), "div": rk["div"], "rank": rk["rank"], "of": rk["of"], "pct": rk["pct"],
                     "adjem": round(e["adjem"], 2), "adjo": round(e["adjo"], 2), "adjd": round(e["adjd"], 2), "pyth": round(1 / (1 + math.exp(-e["adjem"])), 3),
                     "bt": round(e["bt"], 2), "sos": round(e["sos"], 2), "luck": round(e["luck"], 2), "tier": sd["tier"][fid]["tier"],
                     "fights": len(bouts), "last": bouts[-1].date if bouts else None})
    rows.sort(key=lambda r: (r["div"], r["rank"] is None, r["rank"] or 0, -r["adjem"]))
    if div:
        rows = rows[:top]
    return {"available": True, "divisions": sorted({r["div"] for r in sd["ranks"].values()}), "rows": rows, "asof": R.as_of}
