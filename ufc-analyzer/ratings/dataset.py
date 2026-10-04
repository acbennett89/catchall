"""Training rows for the ratings predictor: for every fight from SINCE on, both fighters' raw profiles,
adjusted efficiencies, composites, results strength and the matchup expectations as they stood the day
before the fight.

One replay drives everything (the same code path serving uses): fights are applied date by date; before
a date's fights are applied, the efficiency engine is swept so every rating reflects only earlier
fights.  Rows are oriented by a hash of the fight id (UFCStats lists the winner first) so side A wins
about half the time.
"""
import datetime, hashlib, math, os, pickle, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import espn_hist  # noqa: E402  (ESPN dated histories: shared raw data, not the other model)
from ratings import cagepoints, efficiency, engine, fightdata, profile  # noqa: E402
from ratings.efficiency import DIMS, Efficiency, BradleyTerry, side_vectors  # noqa: E402

SINCE = "2009-01-01"
SWEEPS_PER_DATE = 40   # cap; convergence to 1e-4 usually takes 3-12 from a warm start


def swap_for(fid):
    return int(hashlib.md5(fid.encode()).hexdigest()[:8], 16) % 2 == 1


def outside_for(espn, fid, day_iso):
    h = espn.get(fid)
    if not h:
        return None
    w, l, fin = espn_hist.outside_before(h["hist"], day_iso)
    return (w, l, fin, True)


class Replay:
    """Everything point in time: the bout ledger (raw metrics), the efficiency engine, Bradley-Terry
    strength, expected-win (luck) accumulators and opponents faced."""

    def __init__(self, weights=None, infight=None, tau=efficiency.TAU):
        self.ledger = engine.Ledger()
        self.eff = Efficiency(tau=tau, weights=weights)
        self.bt = BradleyTerry(tau=tau)
        self.infight = infight or cagepoints.load() or {}
        self.pyth = {}        # fid -> [expected wins, decided fights, actual wins]
        self.opps = {}        # fid -> [(opp, t)]
        self.as_of = None

    def apply(self, r, t):
        """Add one fight's results (t = ordinal day)."""
        if r["result"] not in ("f1", "f2", "draw"):
            return
        self.ledger._add(r)
        m = r["secs"] / 60.0
        fin1 = r["result"] == "f1" and r["kind"] in ("ko", "sub")
        fin2 = r["result"] == "f2" and r["kind"] in ("ko", "sub")
        y1, e1 = side_vectors(r["s1"], r["s2"], m, fin1)
        y2, e2 = side_vectors(r["s2"], r["s1"], m, fin2)
        self.eff.add_fight(r["f1"], r["f2"], y1, e1, y2, e2, r["div"], t)
        y = 1.0 if r["result"] == "f1" else 0.0 if r["result"] == "f2" else 0.5
        self.bt.add(r["f1"], r["f2"], y, t)
        p1 = cagepoints.win_prob(self.infight, r) if self.infight else 0.5
        for fid, won, pw in ((r["f1"], y, p1), (r["f2"], 1 - y, 1 - p1)):
            a = self.pyth.setdefault(fid, [0.0, 0, 0.0])
            if r["result"] != "draw":
                a[0] += pw
                a[1] += 1
                a[2] += won
        self.opps.setdefault(r["f1"], []).append((r["f2"], t))
        self.opps.setdefault(r["f2"], []).append((r["f1"], t))

    def settle(self, t, sweeps=SWEEPS_PER_DATE):
        """Bring the ratings up to date for day t (after a date's fights are applied): iterate to
        convergence from the warm start, so training rows see the same fixed point serving computes."""
        self.eff.sweep(t, n=sweeps, tol=1e-4)
        self.bt.sweep(t, n=5)

    def converge(self, t):
        self.eff.sweep(t, n=200, tol=1e-4)
        self.bt.sweep(t, n=20)

    def eff_profile(self, fid, div, t):
        """The engine's view of a fighter as of ordinal day t, in division div."""
        O, D = self.eff.ratios(fid)
        ao, ad, em = self.eff.composite(fid, div)
        out = {"O": {d[0]: O[k] for k, d in enumerate(DIMS)}, "D": {d[0]: D[k] for k, d in enumerate(DIMS)},
               "adjo": ao, "adjd": ad, "adjem": em, "bt": self.bt.get(fid), "eff_min": self.eff.effective_minutes(fid, t)}
        a = self.pyth.get(fid)
        out["pyth_share"] = ((a[0] + 1.0) / (a[1] + 2.0)) if a else 0.5
        out["luck"] = ((a[2] - a[0]) / (a[1] + 2.0)) if a else 0.0
        opps = self.opps.get(fid) or []
        ws = vs = 0.0
        for opp, to in opps:
            w = math.exp(-(t - to) / self.eff.tau)
            vs += w * self.eff.composite(opp, div)[2]
            ws += w
        out["sos"] = vs / ws if ws else 0.0
        out["sos_last3"] = (sum(self.eff.composite(opp, div)[2] for opp, _ in opps[-3:]) / len(opps[-3:])) if opps else 0.0
        return out

    def matchup(self, a, b, div):
        """Expected per-minute output each way, by dimension, plus the division baseline."""
        ea, eb = self.eff.expected(a, b, div)
        rb = self.eff.rbar(div)
        return ({d[0]: ea[k] for k, d in enumerate(DIMS)}, {d[0]: eb[k] for k, d in enumerate(DIMS)}, {d[0]: rb[k] for k, d in enumerate(DIMS)})


def build_rows(data=None, since=SINCE, log=print, market=None, replay=None):
    data = data or fightdata.load()
    fights = data["fights"]
    R = replay or Replay()
    rows = []
    by_date = {}
    for r in fights:
        by_date.setdefault(r["date"], []).append(r)
    dates = sorted(by_date)
    t0 = time.time()
    for i, date in enumerate(dates):
        day = fightdata.parse_day(date)
        t = day.toordinal()
        todays = by_date[date]
        if date >= since:
            priors = profile.Priors(R.ledger, day)
            for r in todays:
                if r["result"] not in ("f1", "f2", "draw"):
                    continue
                sides = []
                for fid in (r["f1"], r["f2"]):
                    P = profile.raw_profile(R.ledger, fid, data["fighters"].get(fid), day, r["div"], priors=priors,
                                            outside=outside_for(data["espn"], fid, date))
                    P["eff"] = R.eff_profile(fid, r["div"], t)
                    sides.append(P)
                ea, eb, rb = R.matchup(r["f1"], r["f2"], r["div"])
                sides[0]["eff"]["exp_on_opp"], sides[1]["eff"]["exp_on_opp"] = ea, eb
                sides[0]["eff"]["rb"] = sides[1]["eff"]["rb"] = rb
                swap = swap_for(r["id"])
                A, B = (sides[1], sides[0]) if swap else (sides[0], sides[1])
                a, b = (r["f2"], r["f1"]) if swap else (r["f1"], r["f2"])
                y = None if r["result"] == "draw" else (1 if (r["result"] == "f1") != swap else 0)
                rows.append({"id": r["id"], "date": date, "year": int(date[:4]), "a": a, "b": b, "swap": swap, "y": y,
                             "A": A, "B": B, "div": r["div"], "rounds": r.get("rounds") or 3, "title": bool(r.get("title")),
                             "kind": r["kind"], "round": r.get("round"), "secs": r["secs"], "result": r["result"],
                             "mkt": (market or {}).get(r["id"])})
        for r in todays:
            R.apply(r, t)
        R.settle(t)
        R.as_of = date
        if i % 100 == 0 and date >= since:
            log(f"  {date}: {len(rows)} rows, {time.time() - t0:.0f}s")
    return rows, R


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "rows.pkl")
    data = fightdata.load()
    rows, _ = build_rows(data, market=fightdata.market())
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(rows, f)
    print(f"wrote {len(rows)} rows to {out}")
