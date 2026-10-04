"""Model predictions for a card, joined with the odds so the app can show model edge at Caesars.

    predictions(event_id, odds) -> {"fights": {fight_id: {...}}, "model": {metadata + evaluation}}

Three probabilities per fight:
  model   the fight model on its own (display only: on its own it loses to the market)
  market  the no-vig consensus of the other books
  bet     the market, nudged by the model only where that blend beat the market in testing
"""
import datetime, math, threading, time

import espn, ledger, ufcstats, value
from net import cache

try:
    from model import espn_hist
    from model import predict as _predict
except Exception:  # model package missing or broken: the rest of the app still works
    _predict = None

OPEN_HOURS, CLOSE_HOURS = 168.0, 12.0   # a week or more out = early lines; inside 12 h = the close
EARLY_HOURS = 96.0   # 4+ days out counts as early lines, where the blend has beaten the market at its own prices
BET_EV, MIN_P, NEWS_GAP, MAX_CZ_OFF = 0.03, 0.20, 0.15, 0.08


def available():
    return bool(_predict and _predict.available())


def _logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def _espn_side(fighter):
    """ESPN fields the model can use, plus the UFCStats id (looked up by name, cached on disk)."""
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
    # ESPN files Dana White's Contender Series under its UFC league; those fights aren't UFC fights here
    ufc_dates = [h["date"] for h in a.get("history", []) if h.get("ufc") and h.get("result")
                 and "contender series" not in (h.get("event") or "").lower()] if a else []
    uid = _resolve_with_history(uid, name, len(ufc_dates))
    return {"ufcstats_id": uid, "name": name, "espn_hist": espn_hist.compact_history(a) if a else None,
            "espn_ufc_dates": ufc_dates, "age": a.get("age"),
            "dob": a.get("dob"), "height": a.get("height") or fighter.get("height"),
            "reach": a.get("reach") or fighter.get("reach"), "stance": a.get("stance") or fighter.get("stance"),
            "record": a.get("record") or fighter.get("record")}


def _resolve_with_history(uid, name, espn_ufc_fights):
    """If ESPN shows UFC fights but the looked-up UFCStats id has none in our history (a namesake),
    use the fighter of that name who does have UFC history (the most experienced one if several)."""
    st = _predict._load()
    eng = st["engine"]
    if not espn_ufc_fights or (uid and uid in eng.fighters and eng.fighters[uid].fights):
        return uid
    from names import similarity
    cands = [fid for fid, n in (st.get("names") or {}).items() if similarity(n, name) >= 0.95 and fid in eng.fighters]
    if not cands:
        return uid
    return max(cands, key=lambda fid: (eng.fighters[fid].fights, eng.fighters[fid].last or datetime.date.min))


def stacker(model_meta, card, now=None):
    """Blend coefficients for this far out from the fight.

    Two market-centred blends were fitted: on opening lines and on closing lines.  Each is all zeros
    (= trust the market) unless it beat the market on the validation years and held up on the test
    years.  A week or more out the opening-line blend applies, inside 12 hours the closing one, and in
    between they are mixed in proportion to log(hours to the fight).
    """
    st = (model_meta or {}).get("stack") or {}
    hours = max(0.0, ((card.get("date") or 0) - (now or time.time())) / 3600.0)

    def coef(anchor):
        s = st.get(anchor) or {}
        c = list(s.get("coef") or [])
        return (c + [0.0, 0.0, 0.0])[:3], bool(s.get("gate"))
    co, go = coef("open")
    cc, gc = coef("close")
    if hours >= OPEN_HOURS:
        w = 1.0
    elif hours <= CLOSE_HOURS:
        w = 0.0
    else:
        w = math.log(hours / CLOSE_HOURS) / math.log(OPEN_HOURS / CLOSE_HOURS)
    c = [w * a + (1 - w) * b for a, b in zip(co, cc)]
    return {"hours": round(hours, 1), "w_open": round(w, 3), "coef": c, "open_gate": go, "close_gate": gc,
            "active": any(abs(v) > 1e-12 for v in c)}


def apply_stacker(stk, p_model, p_market, low_experience):
    """z = L + alpha*L + b*(logit(model) - L), with b the low-experience weight when either fighter has <2 UFC fights."""
    lm = _logit(p_market)
    d = _logit(p_model) - lm
    b_exp, b_low, alpha = stk["coef"]
    z = lm + alpha * lm + (b_low if low_experience else b_exp) * d
    return 1 / (1 + math.exp(-z))


def decide(p_bet, p_mkt, p_model, odds_view, stk, low_experience, stale):
    """BET / WATCH / PASS for the better Caesars side, with plain reasons.

    Every BET needs EV >= 3% at the bet probability, the side above 20%, a fair price from 3+ books and
    Caesars within 8 points of it.  If the plain market price alone gives EV >= 3%, that's market value,
    a BET at any time.  Otherwise the edge comes from the blend, which is a BET only 4+ days out, with
    the opening-line blend live, both fighters with 2+ UFC fights and both fighters' latest fights in the
    history.  That is the rule backtested in model.json (backtest.*.served_rule): on 2016-2020 the blend
    beat opening lines at their own prices with this filter, while no fight-week version beat zero.  A
    model-market gap over 15 points gets a check-the-news note rather than a block: in testing those
    were the early bets that paid.
    """
    lines = {bk: tuple(v) for bk, v in (odds_view.get("lines") or {}).items()}
    v = odds_view.get("value") or {}
    cz = lines.get(value.TARGET_BOOK)
    if not cz or cz[0] is None or cz[1] is None:
        return {"action": "PASS", "reasons": [f"{value.TARGET_BOOK} hasn't priced both sides."]}
    if p_bet is None or p_mkt is None:
        return {"action": "PASS", "reasons": ["No fair price from the other books yet."]}
    evs = [value.ev(p_bet, cz[0]), value.ev(1 - p_bet, cz[1])]
    side = 0 if evs[0] >= evs[1] else 1
    p_side = p_bet if side == 0 else 1 - p_bet
    m_side = p_mkt if side == 0 else 1 - p_mkt
    f_side = None if p_model is None else (p_model if side == 0 else 1 - p_model)
    ev, ev_mkt = evs[side], value.ev(m_side, cz[side])
    blocks = []
    if v.get("books", 0) < 3:
        blocks.append(f"Fair price comes from only {v.get('books', 0)} book(s).")
    gap = abs(value.no_vig(cz[0], cz[1])[0] - p_mkt)
    if gap > MAX_CZ_OFF:
        blocks.append(f"{value.TARGET_BOOK} is {gap * 100:.0f} points off the market; check for news or a stale line first.")
    if p_side < MIN_P:
        blocks.append("Longshot under a 20% chance: historically the worst-priced bets.")
    early = stk.get("hours", 0) >= EARLY_HOURS
    blend_made = ev_mkt < BET_EV <= ev
    notes = []
    if blend_made:
        if not early:
            blocks.append(f"At the plain market price this is {ev_mkt * 100:+.1f}%. Inside 4 days of the fight only market "
                          f"value counts: the blend hasn't beaten fight-week prices in testing.")
        elif not stk.get("open_gate"):
            blocks.append("The early-line blend isn't live.")
        if low_experience:
            blocks.append("A fighter has fewer than 2 UFC fights; blend bets on newcomers didn't hold up in testing.")
        if stale:
            blocks.append("A fighter's latest fight isn't in the model's history yet.")
        if f_side is not None and abs(f_side - m_side) > NEWS_GAP:
            notes.append(f"Model and market are {abs(f_side - m_side) * 100:.0f} points apart: check for news the model can't "
                         f"see (injury, weight cut, late replacement) before betting.")
        if f_side is not None and f_side <= m_side:
            notes.append("The model doesn't rate this side above the market; the edge comes from the blend firming up "
                         "favorites, which past lines have underpriced.")
    if ev_mkt >= BET_EV:
        tier = "Market value + model agrees" if f_side is not None and f_side >= m_side else "Market value"
    elif blend_made:
        tier = "Early-line blend" if early else "Blend (fight week)"
    else:
        tier = None
    price = ("+" if cz[side] > 0 else "") + str(cz[side])
    reasons = [f"{value.TARGET_BOOK} {price}: EV {ev * 100:+.1f}% at the bet probability "
               f"({value.prob_to_american(p_side):+d}), {ev_mkt * 100:+.1f}% at the market price ({value.prob_to_american(m_side):+d})."] + notes
    action = "BET" if ev >= BET_EV and not blocks else "WATCH" if ev > 0 else "PASS"
    if action == "PASS":
        tier = None
    return {"action": action, "tier": tier, "side": side, "ev": round(ev, 4), "evMarket": round(ev_mkt, 4),
            "p": round(p_side, 4), "kelly": round(value.kelly(p_side, cz[side]), 4), "reasons": reasons + blocks}


def _sides(pred, lines):
    """Per-side Caesars price with EV and Kelly under the model and under the bet probability."""
    cz = lines.get(value.TARGET_BOOK)
    sides = []
    for i in (0, 1):
        s = {}
        if cz and cz[i] is not None:
            s["caesars"] = cz[i]
            s["evModel"] = round(value.ev(pred["p"][i], cz[i]), 4)
            s["kellyModel"] = round(value.kelly(pred["p"][i], cz[i]), 4)
            if pred.get("blend"):
                s["evBlend"] = round(value.ev(pred["blend"][i], cz[i]), 4)
                s["kellyBlend"] = round(value.kelly(pred["blend"][i], cz[i]), 4)
        sides.append(s)
    return sides


def fight_prediction(card, f, odds_view=None):
    day = datetime.date.fromtimestamp(card["date"]) if card.get("date") else datetime.date.today()
    a, b = (_espn_side(x) for x in f["fighters"])
    # scheduled rounds: UFCStats' own record once the bout is in the history (ESPN only guesses 5 for
    # title fights and main events, and misses five-round co-mains)
    rounds = _predict.scheduled_rounds(a["ufcstats_id"], b["ufcstats_id"], day) or f.get("rounds") or 3
    pred = _predict.predict(a, b, day=day, wc=f.get("weightClass"), rounds=rounds, title=f.get("title"))
    pred["ufcstatsIds"] = [a["ufcstats_id"], b["ufcstats_id"]]
    if pred.get("suppressed"):
        pred.pop("_ctx", None)
        return pred
    meta = _predict._state["model"] or {}
    stk = stacker(meta, {"date": f.get("date") or card.get("date")})   # hours to this fight's segment
    low = min(pred["profiles"][0]["fights"] or 0, pred["profiles"][1]["fights"] or 0) < 2
    stale = any("isn't in the model's history" in x["text"] for x in pred.get("flags", []))
    pred["blendState"] = {"hours": stk["hours"], "wOpen": stk["w_open"], "active": stk["active"],
                          "openGate": stk["open_gate"], "closeGate": stk["close_gate"], "lowExperience": low}
    pred["methodAnchor"] = "model"
    if odds_view:
        lines = {bk: tuple(v) for bk, v in (odds_view.get("lines") or {}).items()}
        fair = (odds_view.get("value") or {}).get("fair")
        pm = pred["p"][0]
        pred["market"] = fair[0] if fair else None
        bet = apply_stacker(stk, pm, fair[0], low) if fair else None
        pred["blend"] = [round(bet, 4), round(1 - bet, 4)] if bet is not None else None
        if bet is not None:
            # props are priced from the bet probability (= market unless the blend is live), never the raw model's
            m2 = _predict.anchored_method(pred, bet)
            if m2:
                pred["method"] = m2
                pred["methodAnchor"] = "blend" if stk["active"] else "market"
        pred["decision"] = decide(bet, fair[0] if fair else None, pm, odds_view, stk, low, stale)
        if pred["decision"].get("action") in ("BET", "WATCH"):
            try:
                ledger.record(card.get("id"), card, f, pred["decision"], dict(pred, sides=_sides(pred, lines)))
            except Exception:
                pass  # the ledger is a convenience; never break predictions over it
        pred["sides"] = _sides(pred, lines)
    pred.pop("_ctx", None)
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
        summary = {k: meta.get(k) for k in ("built", "trained_through", "fights", "windows", "evaluation", "stack",
                                            "backtest", "method_eval", "description")}
        summary["stack"] = {k: {kk: vv for kk, vv in v.items() if kk != "fits_by_year"}
                            for k, v in (summary.get("stack") or {}).items()}
        return {"available": True, "fights": out, "model": summary, "at": int(time.time() * 1000)}
    # one cached result per event: recomputed when the odds behind it change (or after 5 minutes)
    at = (odds or {}).get("at")
    with _keys_lock:
        prev = _last_key.get(event_id)
        key = ("predictions", event_id, at)
        if prev and prev != key:
            cache.drop(prev)
        _last_key[event_id] = key
    return cache.get(key, load, ttl=300)


_last_key, _keys_lock = {}, threading.Lock()
