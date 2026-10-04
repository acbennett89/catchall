"""Opponent-adjusted ratings for every active fighter as of a date: the KenPom page.

For each stat pair below, engine.adjust() iterates a fighter's offense against the adjusted defense of
every opponent they faced (and the reverse), so a 4.0 SLpM against elite defenders rates above a 4.0
against punching bags.  The pool is every fighter with a UFC bout in the last POOL_YEARS; the prior
for each stat is the league rate (per-minute rates vary little by division: 3.4-4.0 SLpM) except
knockdowns, which use the division's.

Output per fighter: adj_* offense/defense numbers, net ratings, strength of schedule and luck.
"""
import datetime

from ratings import engine
from ratings.engine import per_min, recency_weight

POOL_YEARS = 4
HALF_LIFE = 540.0

# name -> (stat key, per-15 scale?) ; offense = fighter's own, defense = what they allow
ADJ_STATS = {
    "sig": ("sig", 1.0),        # significant strikes landed per minute
    "head": ("head", 1.0),      # head strikes landed per minute (damage)
    "kd": ("kd", 15.0),         # knockdowns per 15
    "td": ("td", 15.0),         # takedowns per 15
    "ctrl": ("ctrl", 0.25),     # control minutes per 15 (ctrl is seconds: /60*15)
    "sub": ("sub", 15.0),       # submission attempts per 15
    "ground": ("ground", 1.0),  # ground strikes landed per minute
}


def pool_as_of(ledger, day, years=POOL_YEARS):
    cut = day - datetime.timedelta(days=365 * years)
    return [f for f, bs in ledger.log.items() if any(cut <= b.day < day for b in bs)]


def league_rate(bouts, key, scale):
    tot = sum((b.me.get(key) or 0) for b in bouts)
    mins = sum(b.minutes for b in bouts)
    return tot / max(mins, 1.0) * scale


def compute(ledger, day, pool=None, half_life=HALF_LIFE):
    """{fid: {"adj_sig_o", "adj_sig_d", ..., "net_strike", "net_grapple", "net_damage", "sos", "luck", "n"}}"""
    pool = pool or pool_as_of(ledger, day)
    logs = {f: ledger.before(f, day) for f in pool}
    allb = [b for bs in logs.values() for b in bs if (day - b.day).days <= 365 * 6]
    out = {f: {"n": len(logs[f])} for f in pool}
    adj = {}
    for name, (key, scale) in ADJ_STATS.items():
        prior = league_rate(allb, key, scale)
        res = engine.adjust(lambda f: logs[f], pool, lambda b, k=key, s=scale: per_min(k, b) * s,
                            lambda b, k=key, s=scale: per_min(k, b, "them") * s, prior, day, half_life=half_life)
        adj[name] = res
        for f, (o, d) in res.items():
            out[f]["adj_" + name + "_o"] = o
            out[f]["adj_" + name + "_d"] = d
        out.setdefault("_prior", {})[name] = prior
    prior = out.pop("_prior")
    # composite margins: positive = better than an average fighter
    for f in pool:
        r = out[f]
        r["net_strike"] = (r["adj_sig_o"] - prior["sig"]) - (r["adj_sig_d"] - prior["sig"])
        r["net_head"] = (r["adj_head_o"] - prior["head"]) - (r["adj_head_d"] - prior["head"])
        r["net_td"] = (r["adj_td_o"] - prior["td"]) - (r["adj_td_d"] - prior["td"])
        r["net_ctrl"] = (r["adj_ctrl_o"] - prior["ctrl"]) - (r["adj_ctrl_d"] - prior["ctrl"])
        r["net_sub"] = (r["adj_sub_o"] - prior["sub"]) - (r["adj_sub_d"] - prior["sub"])
        r["net_ground"] = (r["adj_ground_o"] - prior["ground"]) - (r["adj_ground_d"] - prior["ground"])
        r["net_kd"] = (r["adj_kd_o"] - prior["kd"]) - (r["adj_kd_d"] - prior["kd"])
    # one number per fighter before any fitting: each margin relative to the league rate (so +0.5 on
    # striking = half a league-average fighter's output better, net of what they allow), fixed weights.
    # The predictor fits its own weights on the individual ratings; this composite feeds strength of
    # schedule and the pre-model rank.
    rel = lambda r, k, p: (r[k] / prior[p]) if prior.get(p) else 0.0
    for f in pool:
        r = out[f]
        r["rating"] = (0.45 * rel(r, "net_strike", "sig") + 0.15 * rel(r, "net_head", "head") + 0.12 * rel(r, "net_td", "td")
                       + 0.10 * rel(r, "net_ctrl", "ctrl") + 0.06 * rel(r, "net_sub", "sub") + 0.08 * rel(r, "net_kd", "kd")
                       + 0.04 * rel(r, "net_ground", "ground"))
    # strength of schedule: recency-weighted mean rating of opponents faced (unrated opponents = average)
    for f in pool:
        ws = vs = 0.0
        for b in logs[f]:
            w = recency_weight((day - b.day).days, half_life)
            vs += w * out.get(b.opp, {}).get("rating", 0.0)
            ws += w
        out[f]["sos"] = vs / ws if ws else 0.0
        out[f]["sos_last3"] = sum(out.get(b.opp, {}).get("rating", 0.0) for b in logs[f][-3:]) / max(len(logs[f][-3:]), 1)
    # luck: wins beyond what the per-fight stat margins say (KenPom's luck = record minus expected record)
    for f in pool:
        exp = act = 0.0
        n = 0
        for b in logs[f]:
            w = recency_weight((day - b.day).days, half_life)
            exp += w * expected_win(b)
            act += w * (1.0 if b.won else 0.5 if b.result == "draw" else 0.0)
            n += w
        out[f]["luck"] = (act - exp) / n if n else 0.0
    out["_prior"] = prior
    return out


def expected_win(b):
    """P(win) from this bout's own stat margins (logistic on strike, control, knockdown and takedown
    differentials per minute; coefficients from a quick fit on 2010+ fights, fixed so luck is stable)."""
    m = max(b.minutes, 0.5)
    sd = ((b.me.get("sig") or 0) - (b.them.get("sig") or 0)) / m
    cd = ((b.me.get("ctrl") or 0) - (b.them.get("ctrl") or 0)) / 60.0 / m
    kd = (b.me.get("kd") or 0) - (b.them.get("kd") or 0)
    td = ((b.me.get("td") or 0) - (b.them.get("td") or 0)) / m * 15
    z = 0.9 * sd + 2.2 * cd + 1.1 * kd + 0.25 * td
    import math
    return 1 / (1 + math.exp(-z))


def ranks(table, ledger, day, div_of):
    """Division rank and percentile of each fighter's rating among active fighters of that division.
    div_of(fid) -> division key of the fighter's most recent bout."""
    by_div = {}
    for f, r in table.items():
        if f.startswith("_"):
            continue
        by_div.setdefault(div_of(f), []).append((r["rating"], f))
    out = {}
    for div, lst in by_div.items():
        lst.sort(reverse=True)
        n = len(lst)
        for i, (_, f) in enumerate(lst):
            out[f] = {"div": div, "rank": i + 1, "of": n, "pct": round(100.0 * (n - i) / n)}
    return out
