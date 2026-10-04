"""The adjusted-efficiency engine: KenPom's opponent adjustment in count form.

A "possession" is a minute of shared cage time.  For each dimension d (significant strikes, head
strikes, knockdowns, takedowns, control, submission attempts, ..., finishes) a fighter has an offensive
ratio O (output against an average defender, relative to the division-era average) and a defensive
ratio D (what an average attacker produces against them, relative to average; lower is better).

    expected count of i on j = exposure x rbar[division, d] x O[i, d] x D[j, d]

Ratings are gamma-Poisson shrunk observed / expected, iterated to a fixed point: O from the opponents'
D, then D from the opponents' O, with exponential time decay and K_d "minutes at average" of prior.
Division-era baselines rbar are decayed per-division rates frozen into each fight at fight time, so a
2012 fight is judged against 2012 output.  Composites turn the ratios into cage points per 15 minutes
(AdjO, AdjD, AdjEM = AdjO - AdjD) with a weight per dimension fitted once from what wins fights.

Pure Python at serving time (warm sweeps on the saved state); numpy is used when available for the
training replay.  Both paths implement the same arithmetic.
"""
import math

try:
    import numpy as np
except Exception:  # serving never needs numpy
    np = None

# dimension: (count key, exposure, prior K in exposure units, label)
#   exposure "min" = fight minutes; "head" = head strikes landed (power) / absorbed (chin)
DIMS = [
    ("sig", "min", 12.0), ("sig_a", "min", 8.0), ("tot", "min", 12.0), ("head", "min", 12.0),
    ("dist", "min", 12.0), ("clinch", "min", 25.0), ("ground", "min", 40.0), ("kd", "min", 60.0),
    ("td", "min", 12.0), ("td_a", "min", 6.0), ("ctrl", "min", 8.0), ("sub", "min", 25.0),
    ("fin", "min", 60.0), ("pow", "head", 300.0),
]
ND = len(DIMS)
DIM_INDEX = {d[0]: i for i, d in enumerate(DIMS)}
CLIP = (0.2, 5.0)
# typical modern UFC rates per unit exposure (per minute; 'pow' per head strike landed): the baseline
# prior for the first fights of the data and for new divisions
TYPICAL_RATE = [3.5, 7.5, 4.5, 2.1, 2.8, 0.35, 0.35, 0.02, 0.09, 0.25, 0.17, 0.025, 0.02, 0.009]
assert len(TYPICAL_RATE) == ND
TAU = 1500.0          # days: e-folding time of a fight's weight
TAU_DIV = 1500.0      # days: for the division-era baselines
K_DIV = 600.0         # minutes of global rate mixed into a division's baseline
# default cage-point weights per unit of each dimension's natural rate (per 15 minutes), replaced by the
# fitted in-fight weights in ratings/data/cagepoints.json when present
DEFAULT_WEIGHTS = {"sig": 0.045, "head": 0.02, "ground": 0.02, "kd": 1.0, "td": 0.08, "ctrl": 0.15, "sub": 0.3}


def side_vectors(me, them, minutes, finished_win):
    """(counts, exposures) for one fighter's side of a fight.  Control is in minutes; 'fin' is the finish
    win (1/0) at risk for the fight's minutes; 'pow' is knockdowns per head strike landed."""
    y = [0.0] * ND
    e = [0.0] * ND
    for i, (key, exp, _) in enumerate(DIMS):
        if key == "fin":
            y[i] = 1.0 if finished_win else 0.0
            e[i] = minutes
        elif key == "pow":
            y[i] = float(me.get("kd") or 0)
            e[i] = float(me.get("head") or 0)
        elif key == "ctrl":
            y[i] = (me.get("ctrl") or 0) / 60.0
            e[i] = minutes
        else:
            y[i] = float(me.get(key) or 0)
            e[i] = minutes
    return y, e


class Efficiency:
    def __init__(self, tau=TAU, tau_div=TAU_DIV, k_div=K_DIV, k_mult=1.0, weights=None):
        self.tau, self.tau_div, self.k_div = tau, tau_div, k_div
        self.K = [d[2] * k_mult for d in DIMS]
        self.weights = dict(weights or DEFAULT_WEIGHTS)
        self.fidx = {}
        self.ids = []
        self.O = []           # per fighter: list of ND ratios
        self.D = []
        self.sides = []       # (fi, oi, y, e, rb, t)
        self.div_count = {}   # division -> [ND]
        self.div_exp = {}     # division -> [ND]
        self.div_last = {}
        self.g_count = [0.0] * ND
        self.g_exp = [0.0] * ND
        self.g_last = None
        self.minutes = {}     # fighter -> effective (undecayed) minutes
        self._w_cache = (None, None)

    # ------------------------------------------------------------ state
    def idx(self, fid):
        i = self.fidx.get(fid)
        if i is None:
            i = self.fidx[fid] = len(self.ids)
            self.ids.append(fid)
            self.O.append([1.0] * ND)
            self.D.append([1.0] * ND)
        return i

    def _decay(self, store_c, store_e, last, t):
        if last is not None and t > last:
            w = math.exp(-(t - last) / self.tau_div)
            for k in range(ND):
                store_c[k] *= w
                store_e[k] *= w

    def rbar(self, div):
        """Division-era baseline rate per dimension (count per unit exposure): the division's decayed
        rate shrunk toward the global decayed rate, itself shrunk toward typical UFC rates while the
        history is short (so the first fights of the data don't see a baseline of zero)."""
        dc, de = self.div_count.get(div), self.div_exp.get(div)
        out = []
        for k in range(ND):
            gk = (self.g_count[k] + self.k_div * TYPICAL_RATE[k]) / (self.g_exp[k] + self.k_div)
            if dc is None:
                out.append(gk)
            else:
                out.append((dc[k] + self.k_div * gk) / (de[k] + self.k_div))
        return out

    def add_fight(self, f1, f2, y1, e1, y2, e2, div, t):
        """Both sides of one fight (t = ordinal day).  Baselines are frozen before the fight is added."""
        if div not in self.div_count:
            self.div_count[div] = [0.0] * ND
            self.div_exp[div] = [0.0] * ND
            self.div_last[div] = None
        self._decay(self.div_count[div], self.div_exp[div], self.div_last[div], t)
        self.div_last[div] = t
        self._decay(self.g_count, self.g_exp, self.g_last, t)
        self.g_last = t
        rb = self.rbar(div)
        i, j = self.idx(f1), self.idx(f2)
        self.sides.append((i, j, y1, e1, rb, t))
        self.sides.append((j, i, y2, e2, rb, t))
        for k in range(ND):
            self.div_count[div][k] += y1[k] + y2[k]
            self.div_exp[div][k] += e1[k] + e2[k]
            self.g_count[k] += y1[k] + y2[k]
            self.g_exp[k] += e1[k] + e2[k]
        self.minutes[f1] = self.minutes.get(f1, 0.0) + e1[0]
        self.minutes[f2] = self.minutes.get(f2, 0.0) + e2[0]
        self._w_cache = (None, None)

    # ------------------------------------------------------------ the adjustment
    def sweep(self, today, n=10, tol=1e-4):
        """n iterations of observed/expected (or until the largest change is under tol)."""
        if not self.sides:
            return 0
        if np is not None:
            return self._sweep_np(today, n, tol)
        return self._sweep_py(today, n, tol)

    def _weights(self, today):
        if self._w_cache[0] == today:
            return self._w_cache[1]
        w = [math.exp(-(today - s[5]) / self.tau) for s in self.sides]
        self._w_cache = (today, w)
        return w

    def _sweep_py(self, today, n, tol):
        w = self._weights(today)
        nf = len(self.ids)
        K = self.K
        lo, hi = CLIP
        it = 0
        for it in range(1, n + 1):
            numO = [[0.0] * ND for _ in range(nf)]
            denO = [[0.0] * ND for _ in range(nf)]
            for (fi, oi, y, e, rb, _), ws in zip(self.sides, w):
                if ws < 1e-4:
                    continue
                Do = self.D[oi]
                no, do = numO[fi], denO[fi]
                for k in range(ND):
                    if e[k] > 0:
                        no[k] += ws * y[k] / rb[k]
                        do[k] += ws * e[k] * Do[k]
            newO = [[min(hi, max(lo, (numO[f][k] + K[k]) / (denO[f][k] + K[k]))) for k in range(ND)] for f in range(nf)]
            numD = [[0.0] * ND for _ in range(nf)]
            denD = [[0.0] * ND for _ in range(nf)]
            for (fi, oi, y, e, rb, _), ws in zip(self.sides, w):
                if ws < 1e-4:
                    continue
                Of = newO[fi]
                nd, dd = numD[oi], denD[oi]
                for k in range(ND):
                    if e[k] > 0:
                        nd[k] += ws * y[k] / rb[k]
                        dd[k] += ws * e[k] * Of[k]
            newD = [[min(hi, max(lo, (numD[f][k] + K[k]) / (denD[f][k] + K[k]))) for k in range(ND)] for f in range(nf)]
            delta = 0.0
            for f in range(nf):
                for k in range(ND):
                    delta = max(delta, abs(newO[f][k] - self.O[f][k]), abs(newD[f][k] - self.D[f][k]))
            self.O, self.D = newO, newD
            if delta < tol:
                break
        return it

    def _sweep_np(self, today, n, tol):
        arr = getattr(self, "_np", None)
        if arr is None or arr[0] != len(self.sides):
            fi = np.array([s[0] for s in self.sides]); oi = np.array([s[1] for s in self.sides])
            y = np.array([s[2] for s in self.sides], dtype=float); e = np.array([s[3] for s in self.sides], dtype=float)
            rb = np.array([s[4] for s in self.sides], dtype=float); t = np.array([s[5] for s in self.sides], dtype=float)
            self._np = arr = (len(self.sides), fi, oi, y, e, rb, t)
        _, fi, oi, y, e, rb, t = arr
        w = np.exp(-(today - t) / self.tau)
        ynorm = (y / rb) * w[:, None]
        we = e * w[:, None]
        nf = len(self.ids)
        O = np.array(self.O, dtype=float) if nf else np.ones((0, ND))
        D = np.array(self.D, dtype=float) if nf else np.ones((0, ND))
        K = np.array(self.K)
        it = 0
        for it in range(1, n + 1):
            num = np.zeros((nf, ND)); den = np.zeros((nf, ND))
            np.add.at(num, fi, ynorm); np.add.at(den, fi, we * D[oi])
            newO = np.clip((num + K) / (den + K), *CLIP)
            num = np.zeros((nf, ND)); den = np.zeros((nf, ND))
            np.add.at(num, oi, ynorm); np.add.at(den, oi, we * newO[fi])
            newD = np.clip((num + K) / (den + K), *CLIP)
            delta = max(float(np.abs(newO - O).max()), float(np.abs(newD - D).max()))
            O, D = newO, newD
            if delta < tol:
                break
        self.O = O.tolist()
        self.D = D.tolist()
        return it

    # ------------------------------------------------------------ composites
    def ratios(self, fid):
        i = self.fidx.get(fid)
        if i is None:
            return [1.0] * ND, [1.0] * ND
        return self.O[i], self.D[i]

    def composite(self, fid, div):
        """AdjO, AdjD (cage points per 15 minutes vs an average opponent of the division) and AdjEM."""
        O, D = self.ratios(fid)
        rb = self.rbar(div)
        ao = ad = 0.0
        for key, wgt in self.weights.items():
            k = DIM_INDEX[key]
            ao += wgt * rb[k] * O[k] * 15.0
            ad += wgt * rb[k] * D[k] * 15.0
        return ao, ad, ao - ad

    def expected(self, a, b, div):
        """Expected per-minute output of a on b and of b on a, per dimension (the matchup, in natural
        units: how the fight looks)."""
        Oa, Da = self.ratios(a)
        Ob, Db = self.ratios(b)
        rb = self.rbar(div)
        return [rb[k] * Oa[k] * Db[k] for k in range(ND)], [rb[k] * Ob[k] * Da[k] for k in range(ND)]

    def effective_minutes(self, fid, today):
        i = self.fidx.get(fid)
        if i is None:
            return 0.0
        return sum(math.exp(-(today - s[5]) / self.tau) * s[3][0] for s in self.sides if s[0] == i)


class BradleyTerry:
    """Results-only strength: P(i beats j) = sigmoid(theta_i - theta_j), ridge toward 0, decayed weights,
    solved by diagonal Newton sweeps (warm-started, so a few sweeps per event keep it current)."""

    def __init__(self, tau=TAU, lam=1.0):
        self.tau, self.lam = tau, lam
        self.theta = {}
        self.fights = []   # (i, j, y, t)

    def add(self, i, j, y, t):
        self.fights.append((i, j, y, t))
        self.theta.setdefault(i, 0.0)
        self.theta.setdefault(j, 0.0)

    def sweep(self, today, n=5):
        for _ in range(n):
            g, h = {}, {}
            for i, j, y, t in self.fights:
                w = math.exp(-(today - t) / self.tau)
                if w < 1e-4:
                    continue
                z = self.theta[i] - self.theta[j]
                p = 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))
                g[i] = g.get(i, 0.0) + w * (p - y)
                g[j] = g.get(j, 0.0) - w * (p - y)
                hh = w * p * (1 - p)
                h[i] = h.get(i, 0.0) + hh
                h[j] = h.get(j, 0.0) + hh
            for f in self.theta:
                self.theta[f] -= (g.get(f, 0.0) + self.lam * self.theta[f]) / (h.get(f, 0.0) + self.lam)

    def get(self, fid):
        return self.theta.get(fid, 0.0)
