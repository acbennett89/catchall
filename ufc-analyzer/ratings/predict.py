"""Serve the ratings model (pure standard library): current ratings for every active fighter, division
ranks, and a prediction for any matchup.

    from ratings import predict
    predict.fighter_card(ufcstats_id, day, div)   -> every captured metric, adjusted ratings, rank
    predict.predict(a_id, b_id, day, div, rounds)  -> p, power ratings, drivers, flags
"""
import datetime, json, math, os, threading, time

from ratings import engine, fightdata, profile, ratings
from ratings.features import ALL_FEATURES, GROUP, PER_FIGHTER, matchup
from ratings.learn import sigmoid

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.json")

_lock = threading.Lock()
_state = {"built": 0}


def available():
    return os.path.exists(MODEL_PATH)


def _load():
    with _lock:
        if _state.get("ledger") is not None and time.time() - _state["built"] < 6 * 3600:
            return _state
        with open(MODEL_PATH, encoding="utf-8") as f:
            model = json.load(f)
        data = fightdata.load()
        ledger = engine.Ledger().replay(data["fights"])
        _state.update(model=model, data=data, ledger=ledger, built=time.time(), asof={}, names=_names(data))
        return _state


def reload():
    with _lock:
        _state["ledger"] = None
    return _load()


def _names(data):
    n = {}
    for r in data["fights"]:
        n[r["f1"]] = r["n1"]
        n[r["f2"]] = r["n2"]
    return n


def state_on(day):
    """Ratings table, priors and ranks as of `day` (a date), cached per day; a day inside the history
    replays only the fights before it."""
    st = _load()
    key = day.isoformat()
    with _lock:
        hit = st["asof"].get(key)
    if hit:
        return hit
    ledger = st["ledger"]
    if ledger.as_of and key <= ledger.as_of:
        ledger = engine.Ledger().replay(st["data"]["fights"], until=key)
    pool = ratings.pool_as_of(ledger, day)
    table = ratings.compute(ledger, day, pool=pool)
    priors = profile.Priors(ledger, day)
    last_div = {f: usual_division(bs) for f, bs in ledger.log.items()}
    hit = {"ledger": ledger, "table": table, "priors": priors, "last_div": last_div, "pool": pool}
    hit["power"] = power_table(st["model"], hit, day)
    hit["ranks"] = ranks_from_power(hit["power"], last_div)
    with _lock:
        if len(st["asof"]) >= 6:
            st["asof"].pop(next(iter(st["asof"])))
        st["asof"][key] = hit
    return hit


def fighter_profile(sd, fid, attrs, day, div, outside):
    P = profile.raw_profile(sd["ledger"], fid, attrs, day, div, priors=sd["priors"], outside=outside)
    P["adj"] = dict(sd["table"].get(fid) or {})
    return P


def average_profile(sd, div):
    """A division-average fighter: the prior for every raw metric and league-average adjusted ratings."""
    # an id with no bouts gets every raw metric at the division prior
    P = profile.raw_profile(sd["ledger"], "__average__", {}, datetime.date(2100, 1, 1), div, priors=sd["priors"], outside=None)
    P["adj"] = {"rating": 0.0, "sos": 0.0, "luck": 0.0, "sos_last3": 0.0}
    for k, v in (sd["table"].get("_prior") or {}).items():
        P["adj"]["adj_" + k + "_o"] = v
        P["adj"]["adj_" + k + "_d"] = v
    P["age"] = 29.0
    P["reach"], P["height"], P["ape"] = None, None, None
    P["layoff_days"], P["log_layoff"], P["layoff_bucket"] = 180, math.log1p(180), "90-180"
    P["debut"] = 0.0
    P["ufc_fights"], P["pro_fights"] = 6, 20
    return P


def model_logit(model, x):
    w = model["win"]
    return sum(c * x.get(f, 0.0) for f, c in zip(w["feats"], w["coef"]))


def power_table(model, sd, day):
    """Power rating per fighter: the model's log-odds of beating a division-average fighter, with that
    fighter's own layoff and age neutralized (a rating is about ability, not this week's rust)."""
    out = {}
    avg_by_div = {}
    for fid in sd["pool"]:
        div = sd["last_div"].get(fid, "catch")
        if div not in avg_by_div:
            avg_by_div[div] = average_profile(sd, div)
        P = profile.raw_profile(sd["ledger"], fid, _load()["data"]["fighters"].get(fid), day, div, priors=sd["priors"])
        P["adj"] = dict(sd["table"].get(fid) or {})
        Pn = dict(P, layoff_days=180, log_layoff=math.log1p(180), layoff_vs_usual=None, off_ko_loss=0.0, off_loss=0.0, fights_24m=2)
        x = matchup(Pn, avg_by_div[div], 3, False)
        for k in list(x):
            if GROUP.get(k) in ("rust",):
                x[k] = 0.0
        out[fid] = model_logit(model, x)
    return out


def usual_division(bouts):
    """The division a fighter belongs to: the most common of their last three bouts, ignoring catchweights."""
    recent = [b.div for b in bouts[-3:] if b.div != "catch"] or [b.div for b in bouts[-3:]]
    return max(set(recent), key=lambda d: (recent.count(d), recent[::-1].index(d) * -1)) if recent else "catch"


def ranks_from_power(power, last_div):
    by = {}
    for f, v in power.items():
        by.setdefault(last_div.get(f, "catch"), []).append((v, f))
    out = {}
    for div, lst in by.items():
        lst.sort(reverse=True)
        n = len(lst)
        for i, (v, f) in enumerate(lst):
            out[f] = {"div": div, "rank": i + 1, "of": n, "pct": round(100.0 * (n - i) / n)}
    return out


def predict(a_id, b_id, day=None, div=None, rounds=3, title=False, attrs=None, outside=None):
    """attrs: {fid: attributes} overrides (ESPN fallbacks for debutants); outside: {fid: (w, l, fin, known)}."""
    st = _load()
    day = day or datetime.date.today()
    sd = state_on(day)
    div = div or sd["last_div"].get(a_id) or sd["last_div"].get(b_id) or "catch"
    attrs = attrs or {}
    outside = outside or {}
    P = [fighter_profile(sd, fid, attrs.get(fid) or st["data"]["fighters"].get(fid), day, div, outside.get(fid)) for fid in (a_id, b_id)]
    x = matchup(P[0], P[1], rounds, title)
    w = st["model"]["win"]
    contrib = {f: c * x.get(f, 0.0) for f, c in zip(w["feats"], w["coef"])}
    z = sum(contrib.values())
    p = sigmoid(z)
    groups = {}
    for f, v in contrib.items():
        groups[GROUP.get(f, "other")] = groups.get(GROUP.get(f, "other"), 0.0) + v
    drivers = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:8]
    return {
        "p": [round(p, 4), round(1 - p, 4)],
        "logit": round(z, 4),
        "power": [round(sd["power"].get(a_id, 0.0), 3), round(sd["power"].get(b_id, 0.0), 3)],
        "rank": [sd["ranks"].get(a_id), sd["ranks"].get(b_id)],
        "groups": {k: round(v, 3) for k, v in sorted(groups.items(), key=lambda kv: -abs(kv[1]))},
        "drivers": [{"feature": f, "label": LABELS.get(f, f), "logit": round(v, 3), "favors": 0 if v > 0 else 1} for f, v in drivers if abs(v) >= 0.02],
        "profiles": [card(P[0], sd, a_id), card(P[1], sd, b_id)],
        "flags": flags(P, (a_id, b_id), st),
    }


def card(P, sd, fid):
    """The per-fighter page: every captured metric plus the adjusted ratings, rank and percentile."""
    keep = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items() if k not in ("adj",)}
    keep["adj"] = {k: round(v, 3) for k, v in P["adj"].items() if isinstance(v, (int, float))}
    keep["power"] = round(sd["power"].get(fid, 0.0), 3)
    keep["rank"] = sd["ranks"].get(fid)
    keep["style"] = style_of(P, sd["priors"].get(P.get("div")))
    return keep


def style_of(P, prior=None):
    """Soft style archetype from the stat mix, each score relative to the division average (1.0 =
    average): a fighter is a "wrestler" for attempting and landing takedowns and holding control well
    above the division, a "kicker" for a leg-strike share well above it, and so on."""
    pr = prior or {}
    rel = lambda v, k, d: v / ((pr.get(k) or d) or d)
    s = {}
    s["wrestler"] = 0.5 * rel(P["td_att_15"], "td_a_15", 3.5) + 0.5 * rel(P["ctrl_15"] * 60, "ctrl_15", 170)   # prior ctrl is seconds per 15
    s["grappler"] = 0.6 * rel(P["sub_15"], "sub_15", 0.4) + 0.4 * rel(P["ground_15"], "ground_15", 0.4)
    s["volume_striker"] = rel(P["attempts_pm"] * 15, "sig_a_15", 130) * (0.5 + 0.5 * P["share_dist"])
    s["power_striker"] = 0.6 * rel(P["kd_15"], "kd_15", 0.3) + 0.4 * rel(P["ko_win_share"], "ko_win_share", 0.35)
    s["kicker"] = rel(P["leg_15"], "leg_15", 5.0)
    s["clinch"] = rel(P["clinch_15"] if "clinch_15" in P else P["share_clinch"] * P["slpm"] * 15, "clinch_15", 5.0)
    # counter striker: below-average volume with above-average accuracy and defense (average fighter = 1.0)
    avg_def = 1 - (pr.get("sig_acc") or 0.46)
    s["counter"] = (1.5 - 0.5 * min(2.0, rel(P["attempts_pm"] * 15, "sig_a_15", 130))) * rel(P["sig_acc"], "sig_acc", 0.46) * (P["sig_def"] / avg_def)
    top = sorted(s.items(), key=lambda kv: -kv[1])
    return {"scores": {k: round(v, 2) for k, v in s.items()}, "primary": top[0][0], "secondary": top[1][0]}


def flags(P, ids, st):
    out = []
    names = st["names"]
    for i, (p, fid) in enumerate(zip(P, ids)):
        name = names.get(fid, "Fighter A" if i == 0 else "Fighter B")
        if p["debut"]:
            out.append({"side": i, "text": f"{name} is making their UFC debut: ratings are the division average plus their regional record."})
        elif p["ufc_fights"] < 3:
            out.append({"side": i, "text": f"{name} has {p['ufc_fights']} UFC fight(s); ratings lean on the division prior."})
        if p["layoff_days"] and p["layoff_days"] > 365:
            out.append({"side": i, "text": f"{name} has been out {p['layoff_days'] // 30} months: ring rust applies (fighters off a year or more win 43% of the time)."})
        if p["off_ko_loss"]:
            out.append({"side": i, "text": f"{name} is coming off a KO/TKO loss (next-fight win rate 45%)."})
        if p["ko_losses_3y"] >= 2:
            out.append({"side": i, "text": f"{name} has been knocked out {p['ko_losses_3y']} times in three years."})
        if p["age"] and p["age"] >= 36:
            out.append({"side": i, "text": f"{name} is {p['age']:.0f}: fighters 36+ win 41% of the time."})
        if not p["reach"]:
            out.append({"side": i, "text": f"No reach on record for {name}."})
    return out


LABELS = {
    "rating": "Overall adjusted rating", "adj_sig_o": "Adj. striking offense", "adj_sig_d": "Adj. striking defense",
    "adj_head_o": "Adj. head strikes landed", "adj_head_d": "Adj. head strikes absorbed", "adj_kd_o": "Adj. knockdown rate",
    "adj_kd_d": "Adj. knockdowns taken", "adj_td_o": "Adj. takedown offense", "adj_td_d": "Adj. takedown defense",
    "adj_ctrl_o": "Adj. control", "adj_ctrl_d": "Adj. control conceded", "adj_sub_o": "Adj. submission threat",
    "adj_sub_d": "Adj. submission exposure", "sos": "Strength of schedule", "luck": "Luck", "str_diff": "Strike differential",
    "sig_acc": "Striking accuracy", "sig_def": "Striking defense", "kd_15": "Knockdowns per 15", "kd_abs_15": "Knockdowns absorbed",
    "head_abs_15": "Head strikes absorbed", "dist_net": "Distance striking margin", "td_15": "Takedowns per 15", "td_acc": "Takedown accuracy",
    "td_def": "Takedown defense", "ctrl_diff": "Control time margin", "sub_15": "Submission attempts", "ground_15": "Ground strikes",
    "ko_loss_share": "KO losses (chin)", "finished_share": "Gets finished", "ko_losses_3y": "Recent KO losses", "finish_rate": "Finish rate",
    "ko_15": "KO rate", "dec_win_pct": "Wins decisions", "win_pct": "Win rate", "pace": "Pace", "fade": "Cardio (late-round output)",
    "opp_fade": "Drains opponents", "late_diff": "Late-round margin", "champ_round_min": "Championship-round minutes", "age": "Age",
    "age_over_32": "Age past 32", "age_under_25": "Youth", "reach": "Reach", "height": "Height", "ape": "Reach-to-height",
    "southpaw": "Southpaw", "switch": "Switch stance", "log_ufc_fights": "UFC experience", "log_pro_fights": "Pro experience",
    "outside_win_pct": "Record outside the UFC", "title_fights": "Title fights", "five_round_fights": "Five-round fights", "debut": "UFC debut",
    "log_layoff": "Layoff", "layoff_over_1y": "Out over a year", "layoff_over_2y": "Out over two years", "layoff_vs_usual": "Layoff vs usual gap",
    "fights_24m": "Activity (2 years)", "off_ko_loss": "Coming off a KO loss", "off_loss": "Coming off a loss", "age_x_layoff": "Older and off a long layoff",
    "last5_wins": "Last-5 record", "streak": "Streak", "last3_finishes": "Recent finishes", "str_diff_trend": "Striking trend", "sos_last3": "Recent opposition",
    "wrestler_vs_td_def": "Wrestling vs takedown defense", "volume_vs_defense": "Volume vs striking defense", "power_vs_chin": "Power vs chin",
    "sub_vs_ground": "Submissions vs ground game", "reach_vs_distance": "Reach at distance", "five_x_cardio": "Cardio over five rounds", "five_x_rating": "Rating over five rounds",
}
