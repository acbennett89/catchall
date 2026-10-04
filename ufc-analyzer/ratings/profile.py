"""Raw (unadjusted) per-fighter metrics as of a date, from the ledger: physical, style, striking,
grappling, durability, pace and cardio, finishing and judging, experience, ring rust and momentum.

Every rate is recency-weighted (half-life HALF_LIFE days) and exposure-weighted (minutes), and shrunk
toward the division prior with PRIOR_MIN minutes of pseudo-exposure, so a debutant sits at the division
average and a 20-fight veteran at their own number.  Opponent-adjusted versions live in ratings.py.
"""
import datetime, math

from ratings import engine
from ratings.engine import recency_weight

HALF_LIFE = 540.0      # days: a fight 18 months ago counts half
PRIOR_MIN = 30.0       # minutes of division-average pseudo-exposure
LAYOFF_BUCKETS = ((90, "<90"), (180, "90-180"), (365, "180-365"), (730, "365-730"), (10 ** 9, ">730"))

# stats that are "per minute of cage time" rates (landed/absorbed/attempted), per 15 minutes in the output
RATE_STATS = ("sig", "sig_a", "tot", "tot_a", "head", "head_a", "body", "body_a", "leg", "leg_a",
              "dist", "dist_a", "clinch", "clinch_a", "ground", "ground_a", "td", "td_a", "sub", "rev", "kd", "ctrl")


def wrate(bouts, day, num, den, prior, prior_w=PRIOR_MIN, side="me"):
    """Weighted ratio sum(w*num)/sum(w*den) with the prior mixed in (den in the same units as prior_w)."""
    sn = sd = 0.0
    for b in bouts:
        w = recency_weight((day - b.day).days, HALF_LIFE)
        s = b.me if side == "me" else b.them
        n = num(b, s)
        d = den(b, s)
        if n is None or d is None:
            continue
        sn += w * n
        sd += w * d
    return (sn + prior * prior_w) / (sd + prior_w)


class Priors:
    """Division (or league) averages for every raw rate, computed from the ledger as of a date."""

    def __init__(self, ledger, day, since_years=8):
        self.by_div = {}
        self.league = {}
        cut = day - datetime.timedelta(days=365 * since_years)
        acc = {}
        for fid, bouts in ledger.log.items():
            for b in bouts:
                if not (cut <= b.day < day):
                    continue
                for key in ("league", b.div):
                    a = acc.setdefault(key, {"min": 0.0, "fights": 0, "n": {}, "kd_abs": 0.0, "won_ko": 0, "won_sub": 0, "wins": 0,
                                             "dec": 0, "split": 0, "finished": 0, "dist": 0, "heights": [], "reaches": [], "ages": []})
                    a["min"] += b.minutes
                    a["fights"] += 1
                    for k in RATE_STATS:
                        a["n"][k] = a["n"].get(k, 0.0) + (b.me.get(k) or 0)
                    a["kd_abs"] += (b.them.get("kd") or 0)
                    if b.won:
                        a["wins"] += 1
                        a["won_ko"] += b.kind == "ko"
                        a["won_sub"] += b.kind == "sub"
                    if b.kind == "dec":
                        a["dec"] += 1
                        a["split"] += b.split
                    if b.result == "loss" and b.kind in ("ko", "sub"):
                        a["finished"] += 1
                    a["dist"] += b.kind == "dec"
        for key, a in acc.items():
            m = max(a["min"], 1.0)
            p = {k + "_15": a["n"][k] / m * 15 for k in RATE_STATS}
            p["kd_abs_15"] = a["kd_abs"] / m * 15
            p["sig_acc"] = a["n"]["sig"] / max(a["n"]["sig_a"], 1)
            p["td_acc"] = a["n"]["td"] / max(a["n"]["td_a"], 1)
            p["ko_win_share"] = a["won_ko"] / max(a["wins"], 1)
            p["sub_win_share"] = a["won_sub"] / max(a["wins"], 1)
            p["dist_share"] = a["dist"] / max(a["fights"], 1)
            p["split_share"] = a["split"] / max(a["dec"], 1)
            p["finished_share"] = a["finished"] / max(a["fights"], 1)
            p["minutes_per_fight"] = a["min"] / max(a["fights"], 1)
            if key == "league":
                self.league = p
            else:
                self.by_div[key] = p

    def get(self, div):
        return self.by_div.get(div) or self.league


def _age(attrs, day):
    dob = (attrs or {}).get("dob")
    if not dob:
        return None
    try:
        d = datetime.date.fromisoformat(dob[:10])
    except ValueError:
        return None
    return (day - d).days / 365.25


def _bucket(days):
    for lim, name in LAYOFF_BUCKETS:
        if days < lim:
            return name
    return ">730"


def raw_profile(ledger, fid, attrs, day, div, prior_div=None, priors=None, outside=None):
    """All raw metrics for one fighter as of `day` (a date), in the division `div` of the coming fight.

    outside: (wins, losses, finishes, known) from ESPN's dated history before the fight, or None.
    """
    bouts = ledger.before(fid, day)
    P = priors.get(prior_div or div) if priors else {}
    pr = lambda k, d=0.0: P.get(k, d)
    W = lambda b: recency_weight((day - b.day).days, HALF_LIFE)
    mins = lambda b, s: b.minutes
    per15 = {k: wrate(bouts, day, lambda b, s, k=k: (s.get(k) or 0) * 15.0, mins, pr(k + "_15")) for k in RATE_STATS}
    against = {k: wrate(bouts, day, lambda b, s, k=k: (s.get(k) or 0) * 15.0, mins, pr(k + "_15"), side="them")
               for k in ("sig", "sig_a", "head", "td", "td_a", "kd", "ctrl", "sub", "ground", "ground_a", "dist", "dist_a", "clinch")}
    out = {"fights": len(bouts), "minutes": sum(b.minutes for b in bouts), "div": div}
    # --- physical
    out["age"] = _age(attrs, day)
    out["height"] = (attrs or {}).get("height")
    out["reach"] = (attrs or {}).get("reach")
    out["ape"] = (out["reach"] / out["height"]) if out["reach"] and out["height"] else None
    st = ((attrs or {}).get("stance") or "").lower()
    out["stance"] = "southpaw" if "south" in st else "switch" if "switch" in st else "orthodox" if "orth" in st else None
    # --- striking
    out["slpm"] = per15["sig"] / 15
    out["sapm"] = against["sig"] / 15
    out["str_diff"] = out["slpm"] - out["sapm"]
    out["sig_acc"] = wrate(bouts, day, lambda b, s: s.get("sig"), lambda b, s: s.get("sig_a"), pr("sig_acc"), prior_w=60)
    out["sig_def"] = 1 - wrate(bouts, day, lambda b, s: s.get("sig"), lambda b, s: s.get("sig_a"), pr("sig_acc"), prior_w=60, side="them")
    out["head_15"], out["body_15"], out["leg_15"] = per15["head"], per15["body"], per15["leg"]
    out["head_abs_15"] = against["head"]
    out["kd_15"] = per15["kd"]
    out["kd_abs_15"] = against["kd"]
    out["dist_net"] = (per15["dist"] - against["dist"]) / 15
    out["attempts_pm"] = per15["sig_a"] / 15
    out["pace"] = (per15["sig_a"] + against["sig_a"]) / 15    # both fighters' attempts per minute: the tempo
    # --- grappling
    out["td_15"], out["td_att_15"] = per15["td"], per15["td_a"]
    out["td_acc"] = wrate(bouts, day, lambda b, s: s.get("td"), lambda b, s: s.get("td_a"), pr("td_acc"), prior_w=8)
    out["td_def"] = 1 - wrate(bouts, day, lambda b, s: s.get("td"), lambda b, s: s.get("td_a"), pr("td_acc"), prior_w=8, side="them")
    out["td_conceded_15"] = against["td"]
    out["ctrl_15"] = per15["ctrl"] / 60      # minutes of control per 15
    out["ctrl_abs_15"] = against["ctrl"] / 60
    out["ctrl_diff"] = out["ctrl_15"] - out["ctrl_abs_15"]
    out["sub_15"], out["sub_abs_15"] = per15["sub"], against["sub"]
    out["rev_15"] = per15["rev"]
    out["ground_15"], out["ground_abs_15"] = per15["ground"], against["ground"]
    # --- style shares (of the fighter's own landed strikes / offensive events)
    landed = max(per15["dist"] + per15["clinch"] + per15["ground"], 1e-6)
    out["share_dist"], out["share_clinch"], out["share_ground"] = per15["dist"] / landed, per15["clinch"] / landed, per15["ground"] / landed
    targets = max(per15["head"] + per15["body"] + per15["leg"], 1e-6)
    out["share_head"], out["share_body"], out["share_leg"] = per15["head"] / targets, per15["body"] / targets, per15["leg"] / targets
    out["grapple_share"] = (per15["td_a"] * 10 + per15["sub"] * 6) / (per15["td_a"] * 10 + per15["sub"] * 6 + per15["sig_a"] + 1e-6)
    out["ctrl_share"] = min(1.0, out["ctrl_15"] / 15)
    # --- results, finishing, judging (recency weighted counts)
    wins = sum(W(b) for b in bouts if b.won)
    losses = sum(W(b) for b in bouts if b.result == "loss")
    n_w = sum(W(b) for b in bouts)
    out["win_pct"] = (wins + 0.5 * 4) / (n_w + 4)
    out["ko_win_share"] = (sum(W(b) for b in bouts if b.won and b.kind == "ko") + pr("ko_win_share") * 2) / (wins + 2)
    out["sub_win_share"] = (sum(W(b) for b in bouts if b.won and b.kind == "sub") + pr("sub_win_share") * 2) / (wins + 2)
    out["finish_rate"] = out["ko_win_share"] + out["sub_win_share"]
    out["ko_loss_share"] = (sum(W(b) for b in bouts if b.result == "loss" and b.kind == "ko") + 0.35 * 2) / (losses + 2)
    out["sub_loss_share"] = (sum(W(b) for b in bouts if b.result == "loss" and b.kind == "sub") + 0.2 * 2) / (losses + 2)
    out["finished_share"] = (sum(W(b) for b in bouts if b.result == "loss" and b.kind in ("ko", "sub")) + pr("finished_share") * 3) / (n_w + 3)
    out["ko_losses_3y"] = sum(1 for b in bouts if b.result == "loss" and b.kind == "ko" and (day - b.day).days <= 3 * 365)
    out["ko_losses"] = sum(1 for b in bouts if b.result == "loss" and b.kind == "ko")
    out["dist_share"] = (sum(W(b) for b in bouts if b.kind == "dec") + pr("dist_share") * 3) / (n_w + 3)
    decs = [b for b in bouts if b.kind == "dec"]
    out["dec_win_pct"] = (sum(W(b) for b in decs if b.won) + 1) / (sum(W(b) for b in decs) + 2)
    out["split_share"] = (sum(W(b) for b in decs if b.split) + pr("split_share") * 2) / (sum(W(b) for b in decs) + 2)
    out["avg_fight_min"] = (sum(W(b) * b.minutes for b in bouts) + pr("minutes_per_fight") * 2) / (n_w + 2)
    wmin = sum(W(b) * b.minutes for b in bouts)
    out["ko_15"] = sum(W(b) for b in bouts if b.won and b.kind == "ko") * 15 / (wmin + 30)      # KO wins per 15 minutes
    out["sub_15w"] = sum(W(b) for b in bouts if b.won and b.kind == "sub") * 15 / (wmin + 30)   # submission wins per 15
    # --- pace and cardio (round data)
    fades = [(W(b), f) for b in bouts for f in [engine.fade(b)] if f is not None]
    out["fade"] = (sum(w * f for w, f in fades) + 1.0 * 2) / (sum(w for w, _ in fades) + 2)
    ofades = [(W(b), f) for b in bouts for f in [_opp_fade(b)] if f is not None]
    out["opp_fade"] = (sum(w * f for w, f in ofades) + 1.0 * 2) / (sum(w for w, _ in ofades) + 2)
    late = [(W(b), v) for b in bouts for v in [_late_diff(b)] if v is not None]
    out["late_diff"] = (sum(w * v for w, v in late)) / (sum(w for w, _ in late) + 2)
    out["five_round_fights"] = sum(1 for b in bouts if b.rounds >= 5)
    out["champ_round_min"] = sum(max(0.0, b.minutes - 15.0) for b in bouts)
    out["rounds_fought"] = sum(math.ceil(b.minutes / 5.0) for b in bouts)
    # --- experience and schedule
    out["ufc_fights"] = len(bouts)
    out["title_fights"] = sum(1 for b in bouts if b.title)
    out["main_events"] = sum(1 for b in bouts if b.order == 0)
    out["years_in_ufc"] = (day - bouts[0].day).days / 365.25 if bouts else 0.0
    out["debut"] = 1.0 if not bouts else 0.0
    if outside and outside[3]:
        ow, ol, ofin = outside[0], outside[1], outside[2]
        out["outside_wins"], out["outside_losses"] = ow, ol
        out["outside_win_pct"] = (ow + 3) / (ow + ol + 4)
        out["outside_finish_share"] = (ofin + 1) / (ow + 2)
        out["outside_known"] = 1.0
    else:
        out["outside_wins"], out["outside_losses"], out["outside_win_pct"], out["outside_finish_share"], out["outside_known"] = 0, 0, 0.75, 0.5, 0.0
    out["pro_fights"] = len(bouts) + out["outside_wins"] + out["outside_losses"]
    # --- ring rust
    last = bouts[-1] if bouts else None
    out["layoff_days"] = (day - last.day).days if last else None
    out["layoff_bucket"] = _bucket(out["layoff_days"]) if last else "debut"
    out["log_layoff"] = math.log1p(out["layoff_days"]) if last else math.log1p(180)
    gaps = [(bouts[i].day - bouts[i - 1].day).days for i in range(1, len(bouts))]
    out["usual_gap"] = sorted(gaps)[len(gaps) // 2] if gaps else None
    out["layoff_vs_usual"] = (out["layoff_days"] / out["usual_gap"]) if out["usual_gap"] else None
    out["fights_12m"] = sum(1 for b in bouts if (day - b.day).days <= 365)
    out["fights_24m"] = sum(1 for b in bouts if (day - b.day).days <= 730)
    out["off_ko_loss"] = 1.0 if last and last.result == "loss" and last.kind == "ko" else 0.0
    out["off_sub_loss"] = 1.0 if last and last.result == "loss" and last.kind == "sub" else 0.0
    out["off_loss"] = 1.0 if last and last.result == "loss" else 0.0
    # --- momentum (last 5)
    l5 = bouts[-5:]
    out["last5_wins"] = sum(1 for b in l5 if b.won)
    out["last5_n"] = len(l5)
    streak = 0
    for b in reversed(bouts):
        if b.result == "draw":
            break
        if streak == 0:
            streak = 1 if b.won else -1
        elif (streak > 0) == b.won:
            streak += 1 if b.won else -1
        else:
            break
    out["streak"] = streak
    out["last3_finishes"] = sum(1 for b in bouts[-3:] if b.won and b.kind in ("ko", "sub"))
    recent = bouts[-3:]
    if recent:
        rm = sum(b.minutes for b in recent)
        r_diff = sum((b.me.get("sig") or 0) - (b.them.get("sig") or 0) for b in recent) / max(rm, 1)
        out["recent_str_diff"] = r_diff
        out["str_diff_trend"] = r_diff - out["str_diff"]
    else:
        out["recent_str_diff"], out["str_diff_trend"] = 0.0, 0.0
    return out


def _opp_fade(b):
    """The opponent's fade in this bout (did this fighter drain them?)."""
    if not b.them_r:
        return None
    return engine.fade_ratio([(r.get("sig") or 0) for r in b.them_r], b.secs)


def _late_diff(b):
    """Strike differential per minute from round 3 on (None without round data or a short fight)."""
    if not b.me_r or len(b.me_r) < 3:
        return None
    secs = b.secs - 2 * engine.ROUND_SECS
    if secs < 60:
        return None
    mine = sum((r.get("sig") or 0) for r in b.me_r[2:])
    theirs = sum((r.get("sig") or 0) for r in b.them_r[2:])
    return (mine - theirs) / (secs / 60.0)
