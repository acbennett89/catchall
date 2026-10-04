"""Runtime predictions for the app (pure standard library).

On first use the full UFC history is replayed once (about a second) to get every fighter's current
state; the trained parameters come from model/model.json.  predict(a_espn, b_espn, ...) returns win
probabilities, method/round breakdown, the biggest drivers and data-quality flags.
"""
import datetime, json, math, os, threading, time

from model import dataset, engine, features, scrape
from model.engine import sigmoid
from model.learn import softmax

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.json")

_lock = threading.Lock()
_state = {"model": None, "engine": None, "fighters": None, "outside": None, "built": 0, "names": None}


def _load():
    with _lock:
        if _state["engine"] is not None and time.time() - _state["built"] < 6 * 3600:
            return _state
        with open(MODEL_PATH, encoding="utf-8") as f:
            model = json.load(f)
        events, fights, fighters = scrape.load_dataset()
        eng = engine.Engine(model.get("engine"))
        eng.replay(events, fights)
        totals = dataset.ufc_results(fights)
        names = {}
        for r in fights.values():
            names[r["f1"]] = r["n1"]
            names[r["f2"]] = r["n2"]
        _state.update(model=model, engine=eng, fighters=fighters, built=time.time(), names=names,
                      outside={fid: features.outside_record(fighters.get(fid), totals.get(fid, {})) for fid in totals})
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
    attrs = dict(fighters.get(ufcs_id) or {}) if ufcs_id else {}
    fallback = _attrs_from_espn(esp or {})
    for k, v in fallback.items():
        if attrs.get(k) in (None, "") and v not in (None, ""):
            attrs[k] = v
    f = eng.fighters.get(ufcs_id) if ufcs_id else None
    if f is None:
        f = engine.Fighter(ufcs_id or "new", eng.p["elo0"])
    if ufcs_id in st["outside"]:
        outside = st["outside"][ufcs_id]
    else:
        # not in the UFC dataset: their whole pro record is "outside" (ESPN record like "12-2-0")
        import re
        m = re.match(r"(\d+)-(\d+)", (esp or {}).get("record") or attrs.get("record") or "")
        outside = (int(m.group(1)), int(m.group(2))) if m else (0, 0)
    return features.fighter_profile(eng, f, attrs, day, div, outside), f, attrs


def predict(a, b, day=None, wc=None, rounds=3, title=False):
    """a/b: {"ufcstats_id", "name", "dob", "height", "reach", "stance", "record"} (ESPN-style fields)."""
    st = _load()
    model = st["model"]
    day = day or datetime.date.today()
    div = engine.weight_class(wc or "")
    A, fa, _ = side_profile(st, a.get("ufcstats_id"), a, day, div)
    B, fb, _ = side_profile(st, b.get("ufcstats_id"), b, day, div)
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
    return out


def _am(p):
    if p <= 0 or p >= 1:
        return None
    return round((1 / p - 1) * 100) if p <= 0.5 else round(-100 / (1 / p - 1))


def method_probs(mm, A, B, p_a, rounds, div):
    """P(winner wins by ko/sub/dec | winner) from a multinomial model on winner/loser profiles."""
    res = {}
    for side, (W, L, pw) in enumerate(((A, B, p_a), (B, A, 1 - p_a))):
        x = method_features(W, L, rounds)
        zs = [sum(c * x[f] for f, c in zip(mm["feats"], row)) + b for row, b in zip(mm["coef"], mm["bias"])]
        probs = dict(zip(mm["classes"], softmax(zs)))
        res[side] = {k: pw * v for k, v in probs.items()}
    out = {
        "a": {k: round(v, 4) for k, v in res[0].items()},
        "b": {k: round(v, 4) for k, v in res[1].items()},
    }
    dist = sum(res[s].get("dec", 0) for s in (0, 1))
    out["distance"] = round(dist, 4)
    rd = mm.get("round_dist", {}).get(str(rounds)) or mm.get("round_dist", {}).get("3")
    if rd:
        # split each side's finish probability across rounds using the historical finish-round mix
        rounds_out = []
        for r_i, share in enumerate(rd["share"], 1):
            rounds_out.append({"round": r_i,
                               "a": round((res[0].get("ko", 0) + res[0].get("sub", 0)) * share, 4),
                               "b": round((res[1].get("ko", 0) + res[1].get("sub", 0)) * share, 4)})
        out["rounds"] = rounds_out
        finish = 1 - dist
        cdf = rd.get("cdf_half")  # P(finish happens before r.5 rounds | finish), r = 0..rounds-1
        if cdf:
            out["over_under"] = [{"line": i + 0.5, "under": round(finish * c, 4), "over": round(1 - finish * c, 4)}
                                 for i, c in enumerate(cdf)]
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
    "outside_win_pct": "Record outside the UFC", "win_pct": "UFC win rate", "age": "Age", "age_over_32": "Age past 32",
    "reach": "Reach", "height": "Height", "southpaw": "Southpaw/switch stance", "log_layoff": "Layoff",
    "slpm": "Strikes landed/min", "sapm": "Strikes absorbed/min", "str_acc": "Striking accuracy", "str_def": "Striking defense",
    "td15": "Takedowns/15", "td_acc": "Takedown accuracy", "td_def": "Takedown defense", "sub15": "Sub attempts/15",
    "kd15": "Knockdowns/15", "kd_abs15": "Knocked down/15", "ctrl_share": "Control time share",
    "ko_loss_rate": "KO losses", "finish_rate": "Finish rate", "form": "Recent form", "streak": "Streak",
    "opp_elo": "Strength of schedule", "strike_matchup": "Striking vs. their defense", "td_matchup": "Wrestling vs. their defense",
}
