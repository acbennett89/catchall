"""Point-in-time fighter ledger and KenPom-style opponent adjustment.

The ledger replays every fight in date order and keeps, per fighter, the list of their fights with
both sides' stats (the "game log").  Ratings are computed from the log as it stood before a given
date, so training rows and live predictions see the same thing.

KenPom adjusts a team's offensive efficiency game by game for the defense it faced (and vice versa),
iterating until the ratings are consistent.  The MMA translation: a fighter's rate in a fight (e.g.
significant strikes landed per minute) is scaled by how much better or worse than average the opponent
is at preventing that thing, then averaged over fights with recency and exposure weights, with the
fighter's own prior (division average) mixed in while the sample is small.  adjust() does this for
any pair of (offense, defense) rates.
"""
import datetime, math

from ratings.fightdata import ROUND_SECS, parse_day

# per-fight stat keys stored for both sides
STAT_KEYS = ("kd", "sig", "sig_a", "tot", "tot_a", "td", "td_a", "sub", "rev", "ctrl",
             "head", "head_a", "body", "body_a", "leg", "leg_a", "dist", "dist_a", "clinch", "clinch_a", "ground", "ground_a")


class Bout:
    """One fighter's view of one fight."""
    __slots__ = ("fid", "date", "day", "opp", "secs", "rounds", "div", "title", "me", "them", "me_r", "them_r",
                 "result", "kind", "round", "split", "order")

    def __init__(self, fid, date, opp, secs, rounds, div, title, me, them, me_r, them_r, result, kind, rnd, split, order):
        self.fid, self.date, self.day, self.opp = fid, date, parse_day(date), opp
        self.secs, self.rounds, self.div, self.title = secs, rounds, div, title
        self.me, self.them, self.me_r, self.them_r = me, them, me_r, them_r
        self.result, self.kind, self.round, self.split, self.order = result, kind, rnd, split, order

    @property
    def won(self):
        return self.result == "win"

    @property
    def minutes(self):
        return self.secs / 60.0


class Ledger:
    """fighter id -> [Bout, ...] in date order, built by replay()."""

    def __init__(self):
        self.log = {}
        self.as_of = None

    def replay(self, fights, until=None):
        """fights: fightdata.load()['fights'] (sorted).  Bouts dated on or after `until` are left out."""
        for r in fights:
            if until and r["date"] >= until:
                break
            self._add(r)
            self.as_of = r["date"]
        return self

    def _add(self, r):
        if r["result"] not in ("f1", "f2", "draw"):
            return  # no contests, overturned results: nothing learned about either fighter
        rd = r.get("rounds_data")
        split = (r.get("method") or "").upper().startswith(("S-DEC", "M-DEC"))
        for i, me, them in ((0, "s1", "s2"), (1, "s2", "s1")):
            fid_me, fid_them = (r["f1"], r["f2"]) if i == 0 else (r["f2"], r["f1"])
            result = "draw" if r["result"] == "draw" else "win" if (r["result"] == "f1") == (i == 0) else "loss"
            me_r = [x["s"][i] for x in rd] if rd else None
            them_r = [x["s"][1 - i] for x in rd] if rd else None
            b = Bout(r["id"], r["date"], fid_them, r["secs"], r.get("rounds") or 3, r["div"], bool(r.get("title")),
                     r[me], r[them], me_r, them_r, result, r["kind"], r.get("round"), split, r.get("order"))
            self.log.setdefault(fid_me, []).append(b)

    def before(self, fid, day):
        """Bouts of a fighter strictly before `day` (a date)."""
        return [b for b in self.log.get(fid, []) if b.day < day]


# ------------------------------------------------------------------ weights
def recency_weight(days_ago, half_life):
    return 0.5 ** (max(0.0, days_ago) / half_life)


def exposure_weight(minutes, cap=15.0):
    """Short fights say less about rates than long ones: weight by minutes, capped at one 3-round fight."""
    return min(minutes, cap) / cap


# ------------------------------------------------------------------ opponent adjustment
def adjust(bouts_of, fighters, rate_for, rate_against, prior, day, half_life=540.0, prior_minutes=30.0, iters=12):
    """KenPom-style adjusted offense and defense for one stat.

    bouts_of(fid) -> bouts before `day`; rate_for(bout) and rate_against(bout) give the fighter's own
    rate of the stat and the rate they allowed in that bout (per minute, say); prior is the league
    (division-neutral) average.  Returns {fid: (adj_off, adj_def)} where adj_off is what the fighter
    would produce against an average defense and adj_def what they would allow to an average offense.

    Iteration: adj_off_i = weighted mean over bouts of rate_for * prior / adj_def_opp, shrunk toward
    the prior by prior_minutes of pseudo-exposure; adj_def symmetric.  Opponents missing from the pool
    count as average.
    """
    off = {f: prior for f in fighters}
    de = {f: prior for f in fighters}
    if prior <= 0:   # nobody does this (synthetic data, or a stat absent from the pool): nothing to adjust
        return {f: (0.0, 0.0) for f in fighters}
    logs = {f: bouts_of(f) for f in fighters}
    floor = 0.05 * prior   # an opponent rated near zero would otherwise blow the ratio up
    for _ in range(iters):
        new_off, new_de = {}, {}
        for f in fighters:
            so = sd = w_tot = 0.0
            for b in logs[f]:
                w = recency_weight((day - b.day).days, half_life) * b.minutes
                if w <= 0:
                    continue
                od = max(de.get(b.opp, prior), floor)
                oo = max(off.get(b.opp, prior), floor)
                so += w * rate_for(b) * (prior / od)
                sd += w * rate_against(b) * (prior / oo)
                w_tot += w
            new_off[f] = (so + prior * prior_minutes) / (w_tot + prior_minutes)
            new_de[f] = (sd + prior * prior_minutes) / (w_tot + prior_minutes)
        delta = max((abs(new_off[f] - off[f]) + abs(new_de[f] - de[f]) for f in fighters), default=0.0)
        off, de = new_off, new_de
        if delta < 1e-6:
            break
    return {f: (off[f], de[f]) for f in fighters}


# ------------------------------------------------------------------ per-bout rates
def per_min(stat, b, side="me"):
    s = (b.me if side == "me" else b.them).get(stat) or 0
    return s / max(b.minutes, 0.5)


def per_15(stat, b, side="me"):
    return per_min(stat, b, side) * 15.0


def share(num, den, b, side="me", floor=1):
    s = b.me if side == "me" else b.them
    n, d = s.get(num) or 0, s.get(den) or 0
    return (n / d) if d >= floor else None


def round_output(bout, stat="sig"):
    """Per-round landed counts for the fighter (None when round data is missing)."""
    if not bout.me_r:
        return None
    return [(r.get(stat) or 0) for r in bout.me_r]


def fade(bout, stat="sig"):
    """Late-round output relative to round 1, per minute, for fights that went past round 1.  1.0 = no
    fade, 0.7 = landed 30% less per minute in rounds 2+ than in round 1."""
    rr = round_output(bout, stat)
    return fade_ratio(rr, bout.secs)


def fade_ratio(per_round, secs, smooth=2.0):
    """(later rounds per minute + smooth) / (round 1 per minute + smooth), so quiet first rounds don't
    explode the ratio; None when the fight didn't go at least a minute into round 2."""
    if not per_round or len(per_round) < 2:
        return None
    later_secs = secs - ROUND_SECS
    if later_secs < 60:
        return None
    r1 = per_round[0] / 5.0
    later = sum(per_round[1:]) / (later_secs / 60.0)
    return (later + smooth) / (r1 + smooth)
