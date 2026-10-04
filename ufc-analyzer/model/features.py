"""Matchup features from two fighters' point-in-time state (see engine.py).

Every win-model feature is a difference "A minus B" of a per-fighter quantity, so swapping the
fighters flips every sign; with no intercept the model is exactly antisymmetric:
P(A beats B) = 1 - P(B beats A).  The same function serves training and live predictions.
"""
import math

from model.engine import weight_class

# minutes of "league average" mixed into each rate (Bayesian shrinkage toward the division mean)
PRIOR_MIN = {"rate": 15.0, "acc": 20.0}
# fallback division means (per minute, per fighter) used before a division has history
FALLBACK = {"sig": 3.6, "sig_a": 8.3, "td": 0.09, "td_a": 0.24, "sub": 0.035, "kd": 0.025, "ctrl": 35.0}


def _age(dob, day):
    if not dob or not day:
        return None
    try:
        y, m, d = (int(x) for x in dob.split("-"))
        return (day.toordinal() - __import__("datetime").date(y, m, d).toordinal()) / 365.25
    except Exception:
        return None


def outside_record(attrs, ufc_results):
    """Pro record outside the UFC: total record on UFCStats minus every UFC result we have for them."""
    import re
    m = re.match(r"(\d+)-(\d+)-(\d+)", (attrs or {}).get("record") or "")
    if not m:
        return 0, 0
    w, l = int(m.group(1)) - ufc_results.get("W", 0), int(m.group(2)) - ufc_results.get("L", 0)
    return max(0, w), max(0, l)


def fighter_profile(eng, f, attrs, day, div, outside):
    """Per-fighter quantities as of `day` (f is an engine.Fighter)."""
    attrs = attrs or {}
    mins = f.secs / 60.0

    def div_mean(stat):
        v = eng.div_rate(div, stat)
        return v if v is not None else FALLBACK.get(stat, 0.0)

    def rate(num, prior_stat, per=1.0):
        prior = div_mean(prior_stat) if prior_stat in FALLBACK else 0.0
        return (num + prior * PRIOR_MIN["rate"]) / (mins + PRIOR_MIN["rate"]) * per

    t, a = f.tot, f.against
    m_sig, m_siga = div_mean("sig"), div_mean("sig_a")
    acc_prior = m_sig / m_siga if m_siga else 0.44
    m_td, m_tda = div_mean("td"), div_mean("td_a")
    td_acc_prior = m_td / m_tda if m_tda else 0.38
    k = PRIOR_MIN["acc"]

    slpm = rate(t["sig"], "sig")
    sapm = rate(a["sig"], "sig")
    str_acc = (t["sig"] + acc_prior * k * m_siga) / (t["sig_a"] + k * m_siga)
    str_def = 1 - (a["sig"] + acc_prior * k * m_siga) / (a["sig_a"] + k * m_siga)
    td15 = rate(t["td"], "td", 15)
    td_acc = (t["td"] + td_acc_prior * k * m_tda) / (t["td_a"] + k * m_tda)
    td_def = 1 - (a["td"] + td_acc_prior * k * m_tda) / (a["td_a"] + k * m_tda)
    sub15 = rate(t["sub"], "sub", 15)
    kd15 = rate(t["kd"], "kd", 15)
    kd_abs15 = rate(a["kd"], "kd", 15)
    ctrl_share = (t["ctrl"] + 60.0) / (t["ctrl"] + a["ctrl"] + 120.0)

    # recency-weighted rates (exponential decay, see engine decay_days); shrunk the same way
    dm = f.dsecs / 60.0
    dt, da = f.dtot, f.dagainst
    d_slpm = (dt["sig"] + div_mean("sig") * PRIOR_MIN["rate"]) / (dm + PRIOR_MIN["rate"])
    d_sapm = (da["sig"] + div_mean("sig") * PRIOR_MIN["rate"]) / (dm + PRIOR_MIN["rate"])
    d_td15 = (dt["td"] + div_mean("td") * PRIOR_MIN["rate"]) / (dm + PRIOR_MIN["rate"]) * 15
    d_tdabs15 = (da["td"] + div_mean("td") * PRIOR_MIN["rate"]) / (dm + PRIOR_MIN["rate"]) * 15
    d_ctrl = (dt["ctrl"] + 60.0) / (dt["ctrl"] + da["ctrl"] + 120.0)

    n = f.fights
    ow, ol = outside
    age = _age(attrs.get("dob"), day)
    layoff = (day - f.last).days if f.last else None
    hist = f.history
    form = 0.0
    wsum = 0.0
    for i, h in enumerate(reversed(hist[-5:])):
        wt = 0.7 ** i
        form += wt * (1 if h["res"] == "W" else -1 if h["res"] == "L" else 0)
        wsum += wt
    form = form / wsum if wsum else 0.0
    streak = 0
    for h in reversed(hist):
        if h["res"] == "W" and streak >= 0:
            streak += 1
        elif h["res"] == "L" and streak <= 0:
            streak -= 1
        else:
            break
    decided = f.wins + f.losses
    return {
        "elo": eng.elo_now(f, day),
        "dom": f.dom,
        "d_slpm": d_slpm, "d_sapm": d_sapm, "d_td15": d_td15, "d_tdabs15": d_tdabs15, "d_ctrl": d_ctrl,
        "fights": n,
        "debut": 1.0 if n == 0 else 0.0,
        "win_pct": (f.wins + 2.0) / (decided + 4.0),
        "outside_win_pct": (ow + 2.0) / (ow + ol + 4.0),
        "pro_fights": n + ow + ol,
        "age": age,
        "height": attrs.get("height"),
        "reach": attrs.get("reach") or (attrs.get("height") + 1.0 if attrs.get("height") else None),
        "southpaw": 1.0 if (attrs.get("stance") or "").lower() in ("southpaw", "switch") else 0.0,
        "layoff": layoff,
        "slpm": slpm, "sapm": sapm, "str_acc": str_acc, "str_def": str_def,
        "td15": td15, "td_acc": td_acc, "td_def": td_def, "sub15": sub15,
        "kd15": kd15, "kd_abs15": kd_abs15, "ctrl_share": ctrl_share,
        "ko_loss_rate": (f.losses_by["ko"] + 0.3) / (n + 3.0),
        "sub_loss_rate": (f.losses_by["sub"] + 0.3) / (n + 3.0),
        "finish_rate": (f.wins_by["ko"] + f.wins_by["sub"] + 1.0) / (f.wins + 2.0),
        "ko_win_rate": (f.wins_by["ko"] + 0.5) / (n + 3.0),
        "sub_win_rate": (f.wins_by["sub"] + 0.5) / (n + 3.0),
        "dec_rate": (f.wins_by["dec"] + f.losses_by["dec"] + 1.0) / (n + 2.0),
        "form": form, "streak": streak,
        "opp_elo": f.opp_elo_sum / n if n else eng.p["elo0"],
        "title_fights": f.title_fights, "five_rounders": f.five_rounders,
        "minutes": mins,
    }


def _d(a, b, key, default=0.0):
    va, vb = a.get(key), b.get(key)
    if va is None or vb is None:
        return default
    return va - vb


def win_features(A, B):
    """Antisymmetric difference features for the win model (A - B)."""
    age_a, age_b = A.get("age"), B.get("age")
    lay = lambda p: math.log1p(p["layoff"]) if p.get("layoff") is not None else math.log1p(180)
    return {
        "elo": _d(A, B, "elo") / 100.0,
        "dom": _d(A, B, "dom") / 100.0,
        "d_strike_diff": (A["d_slpm"] - A["d_sapm"]) - (B["d_slpm"] - B["d_sapm"]),
        "d_grapple_diff": (A["d_td15"] - A["d_tdabs15"]) - (B["d_td15"] - B["d_tdabs15"]),
        "d_ctrl": A["d_ctrl"] - B["d_ctrl"],
        "log_fights": math.log1p(A["fights"]) - math.log1p(B["fights"]),
        "debut": A["debut"] - B["debut"],
        "log_pro_fights": math.log1p(A["pro_fights"]) - math.log1p(B["pro_fights"]),
        "outside_win_pct": A["outside_win_pct"] - B["outside_win_pct"],
        "win_pct": A["win_pct"] - B["win_pct"],
        "age": (age_a - age_b) if age_a and age_b else 0.0,
        "age_over_32": (max(0, age_a - 32) - max(0, age_b - 32)) if age_a and age_b else 0.0,
        "reach": _d(A, B, "reach"),
        "height": _d(A, B, "height"),
        "southpaw": A["southpaw"] - B["southpaw"],
        "log_layoff": lay(A) - lay(B),
        "slpm": A["slpm"] - B["slpm"],
        "sapm": A["sapm"] - B["sapm"],
        "str_acc": A["str_acc"] - B["str_acc"],
        "str_def": A["str_def"] - B["str_def"],
        "td15": A["td15"] - B["td15"],
        "td_acc": A["td_acc"] - B["td_acc"],
        "td_def": A["td_def"] - B["td_def"],
        "sub15": A["sub15"] - B["sub15"],
        "kd15": A["kd15"] - B["kd15"],
        "kd_abs15": A["kd_abs15"] - B["kd_abs15"],
        "ctrl_share": A["ctrl_share"] - B["ctrl_share"],
        "ko_loss_rate": A["ko_loss_rate"] - B["ko_loss_rate"],
        "finish_rate": A["finish_rate"] - B["finish_rate"],
        "form": A["form"] - B["form"],
        "streak": max(-4, min(4, A["streak"])) - max(-4, min(4, B["streak"])),
        "opp_elo": (A["opp_elo"] - B["opp_elo"]) / 100.0,
        # matchup terms: my offense against their defense, minus theirs against mine
        "strike_matchup": (A["slpm"] * (1 - B["str_def"])) - (B["slpm"] * (1 - A["str_def"])),
        "td_matchup": (A["td15"] * (1 - B["td_def"])) - (B["td15"] * (1 - A["td_def"])),
    }


WIN_FEATURES = list(win_features(*([{
    "elo": 0, "dom": 0, "d_slpm": 0, "d_sapm": 0, "d_td15": 0, "d_tdabs15": 0, "d_ctrl": 0, "fights": 0, "debut": 0, "pro_fights": 0, "outside_win_pct": 0, "win_pct": 0, "age": None, "reach": None,
    "height": None, "southpaw": 0, "layoff": None, "slpm": 0, "sapm": 0, "str_acc": 0, "str_def": 0, "td15": 0,
    "td_acc": 0, "td_def": 0, "sub15": 0, "kd15": 0, "kd_abs15": 0, "ctrl_share": 0, "ko_loss_rate": 0,
    "finish_rate": 0, "form": 0, "streak": 0, "opp_elo": 0}] * 2)).keys())


def division_of(rec):
    return weight_class(rec.get("wc"))
