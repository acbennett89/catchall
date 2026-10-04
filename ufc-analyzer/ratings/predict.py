"""Serve the ratings model (pure standard library): adjusted efficiencies for every fighter, division
ranks, and a prediction for any matchup, all as of a date.

    from ratings import predict
    predict.predict(a_id, b_id, day, div, rounds)  -> p, ratings, drivers, flags, both fighters' cards
    predict.state_on(day)                           -> the replayed state (engine, priors, ranks)
"""
import datetime, json, math, os, threading, time

from ratings import cagepoints, dataset, fightdata, profile
from ratings.efficiency import DIMS
from ratings.features import GROUP, matchup
from ratings.learn import sigmoid

HERE = os.path.dirname(os.path.abspath(__file__))
MODEL_PATH = os.path.join(HERE, "model.json")
POOL_YEARS = 4

_lock = threading.Lock()
_state = {"built": 0}


def available():
    return os.path.exists(MODEL_PATH)


def _load():
    with _lock:
        if _state.get("data") is not None and time.time() - _state["built"] < 6 * 3600:
            return _state
        with open(MODEL_PATH, encoding="utf-8") as f:
            model = json.load(f)
        data = fightdata.load()
        _state.update(model=model, data=data, built=time.time(), asof={}, names=_names(data))
        return _state


def reload():
    with _lock:
        _state["data"] = None
    return _load()


def _names(data):
    n = {}
    for r in data["fights"]:
        n[r["f1"]] = r["n1"]
        n[r["f2"]] = r["n2"]
    return n


def _replay_until(data, day):
    """A Replay with every fight strictly before `day` applied and the ratings converged for `day`."""
    R = dataset.Replay(weights=cagepoints.load())
    t = day.toordinal()
    key = day.isoformat()
    last = None
    for r in data["fights"]:
        if r["date"] >= key:
            break
        R.apply(r, datetime.date.fromisoformat(r["date"]).toordinal())
        last = r["date"]
    R.as_of = last
    R.converge(t)
    return R


def state_on(day):
    """Engine state, priors and ranks as of `day` (a date), cached per day."""
    st = _load()
    key = day.isoformat()
    with _lock:
        hit = st["asof"].get(key)
    if hit:
        return hit
    R = _replay_until(st["data"], day)
    pool = pool_as_of(R, day)
    last_div = {f: usual_division(bs) for f, bs in R.ledger.log.items()}
    hit = {"R": R, "priors": profile.Priors(R.ledger, day), "last_div": last_div, "pool": pool, "day": day}
    hit["adjem"] = {f: R.eff.composite(f, last_div.get(f, "catch"))[2] for f in pool}
    hit["tier"] = {f: tier_of(R, f, day) for f in pool}
    hit["ranks"] = ranks(hit["adjem"], last_div, hit["tier"])
    with _lock:
        if len(st["asof"]) >= 6:
            st["asof"].pop(next(iter(st["asof"])))
        st["asof"][key] = hit
    return hit


def pool_as_of(R, day, years=POOL_YEARS):
    cut = day - datetime.timedelta(days=365 * years)
    return [f for f, bs in R.ledger.log.items() if any(cut <= b.day < day for b in bs)]


def usual_division(bouts):
    """The division a fighter belongs to: the most common of their last three bouts, ignoring catchweights."""
    recent = [b.div for b in bouts[-3:] if b.div != "catch"] or [b.div for b in bouts[-3:]]
    return max(set(recent), key=lambda d: (recent.count(d), recent[::-1].index(d) * -1)) if recent else "catch"


def tier_of(R, fid, day):
    """How much data is behind the rating: provisional < 15 effective minutes, developing 15-45, established 45+."""
    m = R.eff.effective_minutes(fid, day.toordinal())
    n = len(R.ledger.log.get(fid) or [])
    raw = R.eff.minutes.get(fid, 0.0)
    tier = "provisional" if m < 15 else "developing" if m < 45 else "established"
    return {"tier": tier, "effective_minutes": round(m, 1), "fights": n, "qualified": tier == "established" or (n >= 3 and raw >= 30)}


def ranks(adjem, last_div, tiers):
    """Division rank by AdjEM among qualified fighters; unqualified fighters get a percentile among all
    active fighters of the division but no rank."""
    by = {}
    for f, v in adjem.items():
        by.setdefault(last_div.get(f, "catch"), []).append((v, f))
    out = {}
    for div, lst in by.items():
        lst.sort(reverse=True)
        q = [(v, f) for v, f in lst if tiers[f]["qualified"]]
        n_all, n_q = len(lst), len(q)
        pos_q = {f: i + 1 for i, (_, f) in enumerate(q)}
        for i, (v, f) in enumerate(lst):
            out[f] = {"div": div, "rank": pos_q.get(f), "of": n_q, "pct": round(100.0 * (n_all - i) / n_all), "active": n_all}
    return out


def fighter_profile(sd, fid, attrs, day, div, outside):
    R = sd["R"]
    P = profile.raw_profile(R.ledger, fid, attrs, day, div, priors=sd["priors"], outside=outside)
    P["eff"] = R.eff_profile(fid, div, day.toordinal())
    return P


def model_logit(model, x):
    w = model["win"]
    return sum(c * x.get(f, 0.0) for f, c in zip(w["feats"], w["coef"]))


def predict(a_id, b_id, day=None, div=None, rounds=3, title=False, attrs=None, outside=None):
    """attrs: {fid: attributes} overrides (ESPN fallbacks for debutants); outside: {fid: (w, l, fin, known)}."""
    st = _load()
    day = day or datetime.date.today()
    sd = state_on(day)
    R = sd["R"]
    div = div or sd["last_div"].get(a_id) or sd["last_div"].get(b_id) or "catch"
    attrs = attrs or {}
    outside = outside or {}
    P = [fighter_profile(sd, fid, attrs.get(fid) or st["data"]["fighters"].get(fid), day, div, outside.get(fid)) for fid in (a_id, b_id)]
    ea, eb, rb = R.matchup(a_id, b_id, div)
    P[0]["eff"]["exp_on_opp"], P[1]["eff"]["exp_on_opp"] = ea, eb
    P[0]["eff"]["rb"] = P[1]["eff"]["rb"] = rb
    x = matchup(P[0], P[1], rounds, title)
    w = st["model"]["win"]
    contrib = {f: c * x.get(f, 0.0) for f, c in zip(w["feats"], w["coef"])}
    z = sum(contrib.values())
    p = sigmoid(z)
    groups = {}
    for f, v in contrib.items():
        g = GROUP.get(f, "other")
        groups[g] = groups.get(g, 0.0) + v
    drivers = sorted(contrib.items(), key=lambda kv: -abs(kv[1]))[:8]
    adjem = [P[0]["eff"]["adjem"], P[1]["eff"]["adjem"]]
    # the ratings-only pick, KenPom style: log5 on each fighter's chance against an average opponent
    pa, pb = sigmoid(adjem[0]), sigmoid(adjem[1])
    log5 = pa * (1 - pb) / (pa * (1 - pb) + pb * (1 - pa)) if (pa * (1 - pb) + pb * (1 - pa)) > 0 else 0.5
    return {
        "p": [round(p, 4), round(1 - p, 4)],
        "logit": round(z, 4),
        "adjem": [round(v, 3) for v in adjem],
        "log5": [round(log5, 4), round(1 - log5, 4)],
        "rank": [sd["ranks"].get(a_id), sd["ranks"].get(b_id)],
        "tier": [sd["tier"].get(a_id) or tier_of(R, a_id, day), sd["tier"].get(b_id) or tier_of(R, b_id, day)],
        "groups": {k: round(v, 3) for k, v in sorted(groups.items(), key=lambda kv: -abs(kv[1]))},
        "drivers": [{"feature": f, "label": LABELS.get(f, f), "logit": round(v, 3), "favors": 0 if v > 0 else 1} for f, v in drivers if abs(v) >= 0.02],
        "expected": {"a_on_b": {k: round(v * 15, 2) for k, v in ea.items()}, "b_on_a": {k: round(v * 15, 2) for k, v in eb.items()},
                     "baseline": {k: round(v * 15, 2) for k, v in rb.items()}},   # per 15 minutes
        "profiles": [card(P[0], sd, a_id), card(P[1], sd, b_id)],
        "flags": flags(P, (a_id, b_id), st, sd),
        "div": div,
    }


def card(P, sd, fid):
    """The per-fighter page: every captured metric, the adjusted ratios as indices (100 = average) and
    in natural units, the composites, rank and tier."""
    keep = {k: (round(v, 3) if isinstance(v, float) else v) for k, v in P.items() if k != "eff"}
    e = P["eff"]
    rb = e.get("rb") or {}
    keep["adj"] = {
        "index_o": {k: round(100 * v) for k, v in e["O"].items()},
        "index_d": {k: round(100 * v) for k, v in e["D"].items()},
        "o15": {k: round(e["O"][k] * rb.get(k, 0.0) * (15 if k != "pow" else 100), 2) for k in e["O"]},   # per 15 min (pow: per 100 head strikes)
        "d15": {k: round(e["D"][k] * rb.get(k, 0.0) * (15 if k != "pow" else 100), 2) for k in e["D"]},
        "adjo": round(e["adjo"], 3), "adjd": round(e["adjd"], 3), "adjem": round(e["adjem"], 3),
        "pyth": round(sigmoid(e["adjem"]), 3), "bt": round(e["bt"], 3), "sos": round(e["sos"], 3), "sos_last3": round(e["sos_last3"], 3),
        "luck": round(e["luck"], 3), "pyth_share": round(e["pyth_share"], 3), "eff_min": round(e["eff_min"], 1),
    }
    keep["rank"] = sd["ranks"].get(fid)
    keep["tier"] = sd["tier"].get(fid)
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
    s["clinch"] = rel(P["clinch_15"], "clinch_15", 5.0)
    avg_def = 1 - (pr.get("sig_acc") or 0.46)
    s["counter"] = (1.5 - 0.5 * min(2.0, rel(P["attempts_pm"] * 15, "sig_a_15", 130))) * rel(P["sig_acc"], "sig_acc", 0.46) * (P["sig_def"] / avg_def)
    top = sorted(s.items(), key=lambda kv: -kv[1])
    return {"scores": {k: round(v, 2) for k, v in s.items()}, "primary": top[0][0], "secondary": top[1][0]}


def flags(P, ids, st, sd):
    out = []
    names = st["names"]
    for i, (p, fid) in enumerate(zip(P, ids)):
        name = names.get(fid, "Fighter A" if i == 0 else "Fighter B")
        t = sd["tier"].get(fid)
        if p["debut"]:
            out.append({"side": i, "text": f"{name} is making their UFC debut: ratings are the division average plus their regional record."})
        elif t and t["tier"] == "provisional":
            out.append({"side": i, "text": f"{name} has {t['effective_minutes']:.0f} minutes of UFC data: a provisional rating, unranked."})
        elif p["ufc_fights"] < 3:
            out.append({"side": i, "text": f"{name} has {p['ufc_fights']} UFC fight(s); the rating leans on the division prior."})
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


DIM_LABELS = {"sig": "Sig. strikes", "sig_a": "Strike attempts", "tot": "Total strikes", "head": "Head strikes", "dist": "Distance strikes",
              "clinch": "Clinch strikes", "ground": "Ground strikes", "kd": "Knockdowns", "td": "Takedowns", "td_a": "Takedown attempts",
              "ctrl": "Control (min)", "sub": "Sub attempts", "fin": "Finishes", "pow": "Power (KD per 100 head strikes)"}

LABELS = {
    "adjem": "Adjusted efficiency margin", "adjo": "Adjusted offense", "adjd": "Adjusted defense", "bt": "Results strength (Bradley-Terry)",
    "pyth_share": "Performance-implied win share", "sos": "Strength of schedule", "luck": "Luck", "log_eff_min": "Data behind the rating",
    "str_diff": "Strike differential", "sig_acc": "Striking accuracy", "sig_def": "Striking defense", "kd_15": "Knockdowns per 15",
    "kd_abs_15": "Knockdowns absorbed", "head_abs_15": "Head strikes absorbed", "dist_net": "Distance striking margin", "td_15": "Takedowns per 15",
    "td_acc": "Takedown accuracy", "td_def": "Takedown defense", "ctrl_diff": "Control time margin", "sub_15": "Submission attempts",
    "ground_15": "Ground strikes", "ko_loss_share": "KO losses (chin)", "finished_share": "Gets finished", "ko_losses_3y": "Recent KO losses",
    "finish_rate": "Finish rate", "ko_15": "KO rate", "dec_win_pct": "Wins decisions", "win_pct": "Win rate", "pace": "Pace",
    "fade": "Cardio (late-round output)", "opp_fade": "Drains opponents", "late_diff": "Late-round margin", "champ_round_min": "Championship-round minutes",
    "age": "Age", "age_over_32": "Age past 32", "age_under_25": "Youth", "reach": "Reach", "height": "Height", "ape": "Reach-to-height",
    "southpaw": "Southpaw", "switch": "Switch stance", "log_ufc_fights": "UFC experience", "log_pro_fights": "Pro experience",
    "outside_win_pct": "Record outside the UFC", "outside_finish": "Finishes outside the UFC", "title_fights": "Title fights",
    "five_round_fights": "Five-round fights", "debut": "UFC debut", "log_layoff": "Layoff", "layoff_over_1y": "Out over a year",
    "layoff_over_2y": "Out over two years", "layoff_vs_usual": "Layoff vs usual gap", "fights_24m": "Activity (2 years)",
    "off_ko_loss": "Coming off a KO loss", "off_loss": "Coming off a loss", "age_x_layoff": "Older and off a long layoff",
    "last5_wins": "Last-5 record", "streak": "Streak", "last3_finishes": "Recent finishes", "str_diff_trend": "Striking trend",
    "sos_last3": "Recent opposition", "five_x_cardio": "Cardio over five rounds", "five_x_adjem": "Efficiency over five rounds",
}
for _k, _lab in DIM_LABELS.items():
    LABELS["mult_" + _k] = f"{_lab}: expected each way"
    LABELS["add_" + _k] = f"{_lab}: offense and defense margin"
