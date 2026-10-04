"""Model predictions for a card, joined with the odds so the app can show model edge at Caesars.

    predictions(event_id) -> {"fights": {fight_id: {...}}, "model": {metadata + backtest summary}}
"""
import datetime, math, threading, time

import espn, ufcstats, value
from net import cache

try:
    from model import predict as _predict
except Exception:  # model package missing or broken: the rest of the app still works
    _predict = None

_props_lock = threading.Lock()


def available():
    return bool(_predict and _predict.available())


def _espn_side(fighter):
    """ESPN fields the model can use, plus the UFCStats id (looked up by name, cached on disk)."""
    try:
        a = espn.athlete(fighter["id"])
    except Exception:
        a = {}
    name = a.get("name") or fighter.get("name") or ""
    first, _, last = name.partition(" ")
    try:
        uid = ufcstats.find_id(name, first, last.split(" ")[-1] if last else None, fighter["id"])
    except Exception:
        uid = None
    return {"ufcstats_id": uid, "name": name, "dob": a.get("dob"), "height": a.get("height") or fighter.get("height"),
            "reach": a.get("reach") or fighter.get("reach"), "stance": a.get("stance") or fighter.get("stance"),
            "record": a.get("record") or fighter.get("record")}


def blend(model_meta, p_model, p_market):
    """Market-anchored blend fitted historically: sigmoid(a*logit(market) + b*logit(model))."""
    b = (model_meta or {}).get("blend")
    if not b or p_market is None:
        return None
    lm = math.log(p_market / (1 - p_market))
    lo = math.log(p_model / (1 - p_model))
    z = b["w_market"] * lm + b["w_model"] * lo
    return 1 / (1 + math.exp(-z))


def fight_prediction(card, f, odds_view=None):
    day = datetime.date.fromtimestamp(card["date"]) if card.get("date") else datetime.date.today()
    a, b = (_espn_side(x) for x in f["fighters"])
    pred = _predict.predict(a, b, day=day, wc=f.get("weightClass"), rounds=f.get("rounds") or 3, title=f.get("title"))
    pred["ufcstatsIds"] = [a["ufcstats_id"], b["ufcstats_id"]]
    meta = _predict._state["model"] or {}
    if odds_view:
        lines = {bk: tuple(v) for bk, v in (odds_view.get("lines") or {}).items()}
        fair = (odds_view.get("value") or {}).get("fair")
        pm = pred["p"][0]
        pred["market"] = fair[0] if fair else None
        bl = blend(meta, pm, fair[0]) if fair else None
        pred["blend"] = [round(bl, 4), round(1 - bl, 4)] if bl is not None else None
        cz = lines.get(value.TARGET_BOOK)
        sides = []
        for i in (0, 1):
            s = {}
            p_model = pred["p"][i]
            p_blend = pred["blend"][i] if pred["blend"] else None
            if cz and cz[i] is not None:
                s["caesars"] = cz[i]
                s["evModel"] = round(value.ev(p_model, cz[i]), 4)
                s["kellyModel"] = round(value.kelly(p_model, cz[i]), 4)
                if p_blend is not None:
                    s["evBlend"] = round(value.ev(p_blend, cz[i]), 4)
                    s["kellyBlend"] = round(value.kelly(p_blend, cz[i]), 4)
            sides.append(s)
        pred["sides"] = sides
    return pred


def predictions(event_id, odds=None):
    if not available():
        return {"available": False}

    def load():
        card = espn.card(event_id)
        out = {}
        for f in card["fights"]:
            try:
                ov = (odds or {}).get("fights", {}).get(f["id"]) if odds else None
                out[f["id"]] = fight_prediction(card, f, ov)
            except Exception as e:
                out[f["id"]] = {"error": f"{type(e).__name__}: {e}"}
        meta = dict(_predict._state["model"] or {})
        summary = {k: meta.get(k) for k in ("built", "trained_through", "fights", "evaluation", "description", "blend")}
        return {"available": True, "fights": out, "model": summary, "at": int(time.time() * 1000)}
    key = ("predictions", event_id, (odds or {}).get("at"))
    return cache.get(key, load, ttl=300)
