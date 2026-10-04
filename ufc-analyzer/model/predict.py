"""Runtime predictions for the app (pure standard library).

On first use the full UFC history is replayed once (about a second) to get every fighter's current
state; the trained parameters come from model/model.json.  predict(a_espn, b_espn, ...) returns win
probabilities, method/round breakdown, the biggest drivers and data-quality flags.
"""
import datetime, json, math, os, threading, time

from model import engine, espn_hist, features, scrape
from model.engine import sigmoid
from model.learn import softmax

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.json")

_lock = threading.Lock()
_state = {"model": None, "engine": None, "fighters": None, "built": 0, "names": None}


def _load():
    with _lock:
        if _state["engine"] is not None and time.time() - _state["built"] < 6 * 3600:
            return _state
        with open(MODEL_PATH, encoding="utf-8") as f:
            model = json.load(f)
        events, fights, fighters = scrape.load_dataset()
        eng = engine.Engine(model.get("engine"))
        eng.replay(events, fights)
        names = {}
        for r in fights.values():
            names[r["f1"]] = r["n1"]
            names[r["f2"]] = r["n2"]
        _state.update(model=model, engine=eng, fighters=fighters, built=time.time(), names=names)
        return _state


def reload():
    with _lock:
        _state["engine"] = None
    return _load()


def available():
    return os.path.exists(MODEL_PATH)


def _attrs_from_espn(esp):
    """Fallback physical attributes from ESPN when a fighter has no UFCStats page yet (debutants)."""
    def inches(s):
        if not s:
            return None
        import re
        m = re.match(r"(\d+)'\s*(\d+)", s)
        if m:
            return int(m.group(1)) * 12 + int(m.group(2))
        m = re.match(r"([\d.]+)", s)
        return float(m.group(1)) if m else None
    dob = None
    if esp.get("dob"):
        try:
            dob = datetime.datetime.strptime(esp["dob"], "%m/%d/%Y").date().isoformat()
        except ValueError:
            pass
    return {"height": inches(esp.get("height")), "reach": inches(esp.get("reach")), "stance": esp.get("stance"),
            "dob": dob, "record": esp.get("record")}


def side_profile(st, ufcs_id, esp, day, div):
    eng, fighters = st["engine"], st["fighters"]
    known = fighters.get(ufcs_id) if ufcs_id else None
    # Physical attributes come from UFCStats, exactly as in training.  ESPN's bio is only used for a
    # fighter UFCStats doesn't list yet (a debutant); filling individual gaps from ESPN for listed
    # fighters would make live features differ from the ones the model was trained on.
    attrs = dict(known) if known else _attrs_from_espn(esp or {})
    f = eng.fighters.get(ufcs_id) if ufcs_id else None
    if f is None:
        f = engine.Fighter(ufcs_id or "new", eng.p["elo0"])
    # record outside the UFC before this fight, from ESPN's dated history (the same source as training)
    hist = (esp or {}).get("espn_hist")
    if hist is not None:
        w, l, _ = espn_hist.outside_before(hist, day.isoformat())
        outside = (w, l, True)
    else:
        outside = (0, 0, False)
    return features.fighter_profile(eng, f, attrs, day, div, outside), f, attrs


def predict(a, b, day=None, wc=None, rounds=3, title=False):
    """a/b: {"ufcstats_id", "name", "dob", "height", "reach", "stance", "record"} (ESPN-style fields)."""
    st = _load()
    model = st["model"]
    day = day or datetime.date.today()
    div = engine.weight_class(wc or "")
    A, fa, _ = side_profile(st, a.get("ufcstats_id"), a, day, div)
    B, fb, _ = side_profile(st, b.get("ufcstats_id"), b, day, div)
    # identity/staleness guard: ESPN knows of earlier UFC fights we can't see -> don't pretend they're a debutant
    cutoff = datetime.datetime.combine(day, datetime.time()).replace(tzinfo=datetime.timezone.utc).timestamp() - 6 * 3600
    for i, (P, f, src) in enumerate(((A, fa, a), (B, fb, b))):
        prior = [t for t in (src.get("espn_ufc_dates") or []) if t and t < cutoff]
        name = src.get("name") or "a fighter"
        if prior and P["fights"] == 0:
            return {"suppressed": f"No prediction: ESPN lists {len(prior)} earlier UFC fight(s) for {name}, but their UFCStats history couldn't be matched."}
        if prior and f.last and datetime.datetime.fromtimestamp(max(prior), datetime.timezone.utc).date() > f.last + datetime.timedelta(days=3):
            stale = True
        else:
            stale = False
        if stale:
            src["_stale"] = True
    x = features.win_features(A, B)
    wm = model["win"]
    contrib = {f: c * x[f] for f, c in zip(wm["feats"], wm["coef"])}
    z = sum(contrib.values())
    p = sigmoid(z)
    out = {"p": [round(p, 4), round(1 - p, 4)], "fair": [_am(p), _am(1 - p)]}
    # biggest drivers, in log-odds points toward A (positive) or B (negative)
    drivers = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:6]
    out["drivers"] = [{"feature": k, "label": LABELS.get(k, k), "logit": round(v, 3), "favors": 0 if v > 0 else 1}
                      for k, v in drivers if abs(v) >= 0.02]
    # method and round
    mm = model.get("method")
    if mm:
        out["method"] = method_probs(mm, A, B, p, rounds, div)
    out["flags"] = flags(A, B, fa, fb, a, b)
    out["profiles"] = [_summary(A), _summary(B)]
    out["elo"] = [round(A["elo"]), round(B["elo"])]
    out["_ctx"] = (A, B, rounds, div)   # for re-anchoring the method breakdown (stripped before JSON)
    return out


def anchored_method(pred, p_anchor):
    """Method/round breakdown re-scaled to another win probability (market or blend)."""
    mm = (_state["model"] or {}).get("method")
    if not mm or "_ctx" not in pred:
        return None
    A, B, rounds, div = pred["_ctx"]
    return method_probs(mm, A, B, p_anchor, rounds, div)


def _am(p):
    if p <= 0 or p >= 1:
        return None
    return round((1 / p - 1) * 100) if p <= 0.5 else round(-100 / (1 / p - 1))


def method_probs(mm, A, B, p_a, rounds, div):
    """Full outcome table for the fight, consistent with P(A wins) = p_a.

    Method given the winner comes from the multinomial model.  A draw takes a small share of the
    decision mass (the moneyline voids on a draw, so P(A | no draw) stays p_a).  Finishes are spread
    over rounds with method-specific hazards: with F the total finish probability and c = -ln(1 - F),
    P(round r | method m) = (exp(-c*L[r-1]) - exp(-c*L[r])) / (1 - exp(-c)), so fights likely to end
    early end earlier, and knockouts come earlier than submissions.
    """
    oc = mm.get("outcome") or {}
    R = 5 if rounds >= 5 else 3
    probs = []
    for W, L in ((A, B), (B, A)):
        x = method_features(W, L, rounds)
        zs = [sum(c * x[f] for f, c in zip(mm["feats"], row)) + b for row, b in zip(mm["coef"], mm["bias"])]
        probs.append(dict(zip(mm["classes"], softmax(zs))))
    pw = (p_a, 1 - p_a)
    dec_mass = sum(pw[s] * probs[s]["dec"] for s in (0, 1))
    p_draw = oc.get("draw_rate", 0.0) * dec_mass
    keep = 1 - p_draw
    cell = [{m: keep * pw[s] * probs[s][m] for m in ("ko", "sub", "dec")} for s in (0, 1)]
    F = sum(cell[s]["ko"] + cell[s]["sub"] for s in (0, 1))
    lam = (oc.get("lambda") or {}).get(str(R))
    split = oc.get("split_share", 0.22)
    half = oc.get("first_half") or {"ko": 0.5, "sub": 0.4}
    table = []
    for s in (0, 1):
        t = {"ko_r": [], "sub_r": [], "dec_u": cell[s]["dec"] * (1 - split), "dec_s": cell[s]["dec"] * split}
        for m in ("ko", "sub"):
            if lam and lam.get(m) and 0 < F < 1:
                c = -math.log(1 - F)
                L = lam[m]
                denom = 1 - math.exp(-c)
                t[m + "_r"] = [cell[s][m] * (math.exp(-c * L[r - 1]) - math.exp(-c * L[r])) / denom for r in range(1, R + 1)]
            else:
                t[m + "_r"] = [cell[s][m] / R] * R
        table.append(t)
    ends = [sum(table[s]["ko_r"][r] + table[s]["sub_r"][r] for s in (0, 1)) for r in range(R)]
    out = {"rounds_scheduled": R, "draw": round(p_draw, 4)}
    for s, key in ((0, "a"), (1, "b")):
        t = table[s]
        out[key] = {"ko": round(sum(t["ko_r"]), 4), "sub": round(sum(t["sub_r"]), 4),
                    "dec": round(t["dec_u"] + t["dec_s"], 4), "dec_u": round(t["dec_u"], 4), "dec_s": round(t["dec_s"], 4),
                    "ko_r": [round(v, 4) for v in t["ko_r"]], "sub_r": [round(v, 4) for v in t["sub_r"]]}
    out["distance"] = round(sum(cell[s]["dec"] for s in (0, 1)) + p_draw, 4)
    out["rounds"] = [{"round": r + 1, "a": round(table[0]["ko_r"][r] + table[0]["sub_r"][r], 4),
                      "b": round(table[1]["ko_r"][r] + table[1]["sub_r"][r], 4)} for r in range(R)]
    # under k.5 rounds: every finish in rounds 1..k, plus first-half finishes in round k+1
    ou = []
    for k in range(R):
        under = sum(ends[:k]) + sum(table[s][m + "_r"][k] * half.get(m, 0.5) for s in (0, 1) for m in ("ko", "sub"))
        ou.append({"line": k + 0.5, "under": round(under, 4), "over": round(1 - under, 4)})
    out["over_under"] = ou
    return out


def method_features(W, L, rounds):
    return {
        "w_ko_win_rate": W["ko_win_rate"], "w_sub_win_rate": W["sub_win_rate"], "w_dec_rate": W["dec_rate"],
        "w_kd15": W["kd15"], "w_sub15": W["sub15"], "w_slpm": W["slpm"], "w_td15": W["td15"],
        "l_ko_loss_rate": L["ko_loss_rate"], "l_sub_loss_rate": L["sub_loss_rate"], "l_dec_rate": L["dec_rate"],
        "l_kd_abs15": L["kd_abs15"], "l_sapm": L["sapm"], "l_td_def": L["td_def"],
        "five_rounds": 1.0 if rounds >= 5 else 0.0,
        "elo_gap": (W["elo"] - L["elo"]) / 100.0,
    }


def flags(A, B, fa, fb, a, b):
    out = []
    for i, (P, f, src) in enumerate(((A, fa, a), (B, fb, b))):
        name = src.get("name") or ("A" if i == 0 else "B")
        if src.get("_stale"):
            out.append({"side": i, "text": f"{name}'s most recent UFC fight isn't in the model's history yet (it updates in the background)."})
        if P.get("outside_known") == 0.0 and P["fights"] < 4:
            out.append({"side": i, "text": f"No dated pro history for {name} on ESPN, so their record outside the UFC isn't used."})
        if P["fights"] == 0:
            out.append({"side": i, "text": f"{name} has no UFC fights: the model leans on their outside record and physicals."})
        elif P["minutes"] < 20:
            out.append({"side": i, "text": f"{name} has under 20 UFC minutes: stats are mostly division averages."})
        if P.get("age") is None:
            out.append({"side": i, "text": f"No date of birth for {name}; age isn't used."})
        if P.get("layoff") and P["layoff"] > 540:
            out.append({"side": i, "text": f"{name} has been out {round(P['layoff'] / 30.4)} months."})
    return out


def _summary(P):
    keys = ("elo", "fights", "age", "slpm", "sapm", "str_acc", "str_def", "td15", "td_def", "sub15", "kd15", "kd_abs15",
            "ctrl_share", "finish_rate", "ko_loss_rate", "form", "layoff", "minutes")
    return {k: (round(P[k], 3) if isinstance(P.get(k), float) else P.get(k)) for k in keys}


LABELS = {
    "elo": "Rating (Elo)", "dom": "Dominance rating", "d_strike_diff": "Recent striking margin",
    "d_grapple_diff": "Recent wrestling margin", "d_ctrl": "Recent control time", "log_fights": "UFC experience", "debut": "UFC debut", "log_pro_fights": "Pro experience",
    "outside_win_pct": "Record outside the UFC", "win_pct": "UFC win rate", "age": "Age", "age_over_30": "Age past 30", "age_over_34": "Age past 34",
    "move_up": "Moving up a weight class", "move_down": "Moving down a weight class", "head_dmg": "Damage absorbed (career)",
    "log_five_rounders": "Five-round experience",
    "reach": "Reach", "height": "Height", "southpaw": "Southpaw/switch stance", "log_layoff": "Layoff",
    "slpm": "Strikes landed/min", "sapm": "Strikes absorbed/min", "str_acc": "Striking accuracy", "str_def": "Striking defense",
    "td15": "Takedowns/15", "td_acc": "Takedown accuracy", "td_def": "Takedown defense", "sub15": "Sub attempts/15",
    "kd15": "Knockdowns/15", "kd_abs15": "Knocked down/15", "ctrl_share": "Control time share",
    "ko_loss_rate": "KO losses", "finish_rate": "Finish rate", "form": "Recent form", "streak": "Streak",
    "opp_elo": "Strength of schedule", "strike_matchup": "Striking vs. their defense", "td_matchup": "Wrestling vs. their defense",
}
