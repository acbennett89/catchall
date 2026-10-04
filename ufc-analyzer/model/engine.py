"""Point-in-time replay of UFC history.

Walks every UFC event in date order.  Before an event's results are applied, each bout can be
inspected with both fighters' state *as of that day* (nothing from that event or later).  The same
state object is what the server uses to predict an upcoming fight, so training and serving share
one code path.

Pure standard library: this runs on the user's PC at server start (~1-2 s for the whole history).
"""
import datetime, math

SEC_PER_MIN = 60.0
DAY = 86400.0


def parse_day(s):
    return datetime.date.fromisoformat(s) if s else None


def finish_seconds(rec):
    """Fight duration in seconds from the finish round and clock (5-minute rounds)."""
    try:
        m, s = rec.get("time", "0:00").split(":")
        r = int(rec.get("round") or 1)
        return (r - 1) * 300 + int(m) * 60 + int(s)
    except Exception:
        return None


def method_class(method):
    m = (method or "").upper()
    if "KO" in m or m == "CNC" or "COULD NOT CONTINUE" in m:  # KO/TKO, doctor stoppage, injury stoppage
        return "ko"
    if "SUB" in m:
        return "sub"
    if "DEC" in m:
        return "dec"
    if "DQ" in m:
        return "dq"
    return "other"  # Overturned, Could Not Continue, Other


def weight_class(wc):
    """Normalize UFCStats bout labels ('UFC Women's Flyweight Title Bout') to a division key."""
    w = (wc or "").lower()
    women = "women" in w
    for key in ("strawweight", "flyweight", "bantamweight", "featherweight", "lightweight", "welterweight",
                "middleweight", "light heavyweight", "heavyweight", "catch weight", "open weight"):
        if key in w:
            if key == "heavyweight" and "light heavyweight" in w:
                key = "light heavyweight"
            return ("w " if women else "") + key
    return ("w " if women else "") + "other"


class Fighter:
    """Everything known about a fighter before a given date (UFC fights only)."""
    __slots__ = ("id", "fights", "wins", "losses", "draws", "nc", "last", "dates", "elo", "elo_n",
                 "secs", "tot", "against", "wins_by", "losses_by", "history", "opp_elo_sum",
                 "title_fights", "five_rounders", "divisions", "dom", "dom_n", "dsecs", "dtot", "dagainst", "dlast")

    STATS = ("kd", "sig", "sig_a", "tot", "tot_a", "td", "td_a", "sub", "rev", "ctrl",
             "head", "head_a", "body", "body_a", "leg", "leg_a", "dist", "dist_a", "clinch", "clinch_a", "ground", "ground_a")

    def __init__(self, fid, elo0):
        self.id = fid
        self.fights = self.wins = self.losses = self.draws = self.nc = 0
        self.last = None
        self.dates = []
        self.elo = elo0
        self.elo_n = 0
        self.secs = 0.0                      # cage time with usable stats
        self.tot = dict.fromkeys(self.STATS, 0.0)       # own output
        self.against = dict.fromkeys(self.STATS, 0.0)   # opponents' output against this fighter
        self.wins_by = {"ko": 0, "sub": 0, "dec": 0, "dq": 0, "other": 0}
        self.losses_by = {"ko": 0, "sub": 0, "dec": 0, "dq": 0, "other": 0}
        self.history = []                    # recent fights, newest last: dicts (see Engine._apply)
        self.opp_elo_sum = 0.0
        self.title_fights = 0
        self.five_rounders = 0
        self.divisions = {}
        self.dom = elo0                      # dominance rating: Elo on per-fight performance share
        self.dom_n = 0
        self.dsecs = 0.0                     # recency-weighted (exponentially decayed) versions
        self.dtot = dict.fromkeys(self.STATS, 0.0)
        self.dagainst = dict.fromkeys(self.STATS, 0.0)
        self.dlast = None


class Engine:
    """Chronological replay with Elo ratings and cumulative stats.

    Elo: expected = 1 / (1 + 10^((Rb - Ra)/400)); update K * mult * (result - expected), where mult
    rewards finishes (finish_mult) and early finishes slightly more, and K shrinks with experience.
    """

    def __init__(self, params=None):
        p = {"elo0": 1500.0, "k": 32.0, "k_new": 64.0, "k_decay_fights": 6, "finish_mult": 1.25,
             "dec_mult": 0.9, "split_mult": 0.6, "inactive_regress_days": 540, "inactive_regress": 0.15,
             "history": 8, "dom_k": 40.0, "decay_days": 730.0}
        p.update(params or {})
        self.p = p
        self.fighters = {}
        self.div_tot = {}    # division -> [secs, {stat: total}] across all fighters, point-in-time
        self.as_of = None

    def get(self, fid):
        f = self.fighters.get(fid)
        if f is None:
            f = self.fighters[fid] = Fighter(fid, self.p["elo0"])
        return f

    def elo_now(self, f, day):
        """Rating regressed toward the mean after a long layoff (applied lazily, not stored)."""
        if f.last is None or day is None:
            return f.elo
        idle = (day - f.last).days
        if idle <= self.p["inactive_regress_days"]:
            return f.elo
        w = min(1.0, (idle - self.p["inactive_regress_days"]) / 365.0) * self.p["inactive_regress"]
        return f.elo + (self.p["elo0"] - f.elo) * w

    def replay(self, events, fights, until=None, on_event=None):
        """Apply every event dated before `until` (ISO date) in order.

        on_event(event, bouts, day) is called before each event's results are applied, with bouts as
        a list of fight records, so callers can read pre-fight state via self.get(...).
        """
        evs = sorted((e for e in events.values() if e.get("date")), key=lambda e: (e["date"], e["id"]))
        for e in evs:
            if until and e["date"] >= until:
                break
            bouts = [fights[i] for i in e.get("fights", []) if i in fights]
            day = parse_day(e["date"])
            if on_event:
                on_event(e, bouts, day)
            for r in bouts:
                self._apply(r, day)
            self.as_of = e["date"]
        return self

    def _apply(self, r, day):
        a, b = self.get(r["f1"]), self.get(r["f2"])
        res = r.get("result")
        kind = method_class(r.get("method"))
        secs = finish_seconds(r)
        div = weight_class(r.get("wc"))
        ra, rb = self.elo_now(a, day), self.elo_now(b, day)
        # --- Elo
        if res in ("f1", "f2", "draw"):
            score = 1.0 if res == "f1" else 0.0 if res == "f2" else 0.5
            exp_a = 1.0 / (1.0 + 10 ** ((rb - ra) / 400.0))
            mult = 1.0
            if res != "draw":
                if kind in ("ko", "sub"):
                    early = 1.0 + 0.1 * max(0, (r.get("rounds") or 3) - (r.get("round") or 1)) / 2.0
                    mult = self.p["finish_mult"] * early
                elif kind == "dec":
                    mult = self.p["split_mult"] if (r.get("method") or "").upper().startswith(("S-DEC", "M-DEC")) else self.p["dec_mult"]
            ka, kb = self._k(a), self._k(b)
            a.elo = ra + ka * mult * (score - exp_a)
            b.elo = rb + kb * mult * ((1 - score) - (1 - exp_a))
            a.elo_n += 1
            b.elo_n += 1
        # --- records and stats
        s1, s2 = r.get("s1") or {}, r.get("s2") or {}
        has_stats = bool(s1) and bool(s2) and s1.get("sig_a") is not None and secs
        for me, them, my, their, won, opp_elo in ((a, b, s1, s2, res == "f1", rb), (b, a, s2, s1, res == "f2", ra)):
            me.fights += 1
            if res == "nc":
                me.nc += 1
            elif res == "draw":
                me.draws += 1
            elif won:
                me.wins += 1
                me.wins_by[kind] += 1
            else:
                me.losses += 1
                me.losses_by[kind] += 1
            me.opp_elo_sum += opp_elo
            if r.get("title"):
                me.title_fights += 1
            if (r.get("rounds") or 3) >= 5:
                me.five_rounders += 1
            me.divisions[div] = me.divisions.get(div, 0) + 1
            if has_stats:
                me.secs += secs
                for k in Fighter.STATS:
                    me.tot[k] += my.get(k) or 0
                    me.against[k] += their.get(k) or 0
            me.history.append({
                "date": day, "res": "nc" if res == "nc" else "D" if res == "draw" else "W" if won else "L",
                "kind": kind, "secs": secs, "opp": them.id, "opp_elo": opp_elo, "rounds": r.get("rounds") or 3,
                "round": r.get("round"), "div": div,
                "sig": my.get("sig") if has_stats else None, "sig_vs": their.get("sig") if has_stats else None,
                "td": my.get("td") if has_stats else None, "td_vs": their.get("td") if has_stats else None,
                "kd": my.get("kd") if has_stats else None, "kd_vs": their.get("kd") if has_stats else None,
                "ctrl": my.get("ctrl") if has_stats else None, "ctrl_vs": their.get("ctrl") if has_stats else None,
            })
            if len(me.history) > self.p["history"]:
                me.history.pop(0)
            me.last = day
            me.dates.append(day)
        if has_stats:
            # dominance: share of "performance" (sig strikes + weighted knockdowns, takedowns, control)
            def perf(x):
                return (x.get("sig") or 0) + 10 * (x.get("kd") or 0) + 5 * (x.get("td") or 0) + (x.get("ctrl") or 0) / 30.0
            pa, pb = perf(s1), perf(s2)
            share = (pa + 1.0) / (pa + pb + 2.0)
            exp_d = 1.0 / (1.0 + 10 ** ((b.dom - a.dom) / 400.0))
            kd_ = self.p["dom_k"]
            a.dom, b.dom = a.dom + kd_ * (share - exp_d), b.dom + kd_ * ((1 - share) - (1 - exp_d))
            a.dom_n += 1
            b.dom_n += 1
            # recency-weighted totals
            for me, my, their in ((a, s1, s2), (b, s2, s1)):
                self._decay(me, day)
                me.dsecs += secs
                for k in Fighter.STATS:
                    me.dtot[k] += my.get(k) or 0
                    me.dagainst[k] += their.get(k) or 0
            d = self.div_tot.setdefault(div, [0.0, dict.fromkeys(Fighter.STATS, 0.0)])
            d[0] += 2 * secs
            for k in Fighter.STATS:
                d[1][k] += (s1.get(k) or 0) + (s2.get(k) or 0)

    def _decay(self, f, day):
        if f.dlast is not None and day is not None:
            w = math.exp(-(day - f.dlast).days / self.p["decay_days"])
            if w < 1.0:
                f.dsecs *= w
                for k in Fighter.STATS:
                    f.dtot[k] *= w
                    f.dagainst[k] *= w
        f.dlast = day

    def _k(self, f):
        n = f.elo_n
        frac = min(1.0, n / float(self.p["k_decay_fights"]))
        return self.p["k_new"] + (self.p["k"] - self.p["k_new"]) * frac

    def div_rate(self, div, stat, per=SEC_PER_MIN):
        """Division average of a stat per minute (per fighter), point-in-time; None before any data."""
        d = self.div_tot.get(div)
        if not d or d[0] <= 0:
            return None
        return d[1][stat] / d[0] * per


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sigmoid(x):
    if x >= 0:
        return 1.0 / (1.0 + math.exp(-x))
    z = math.exp(x)
    return z / (1.0 + z)
