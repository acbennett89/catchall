"""Small, dependency-free learning and evaluation toolkit.

- L2-regularized logistic regression fitted by Newton's method (no intercept option for
  antisymmetric "A minus B" features), plus multinomial softmax scoring for exported models.
- Metrics: log loss, Brier score, accuracy, calibration table, expected calibration error.
- Bootstrap confidence intervals and a flat-stake betting backtest.

numpy/scikit-learn are only used in research scripts; everything the app needs at runtime is here.
"""
import math, random

from model.engine import sigmoid


# ---------------------------------------------------------------- linear algebra helpers
def _solve(a, b):
    """Solve a x = b for a small dense symmetric positive-definite system (Gauss-Jordan)."""
    n = len(b)
    m = [row[:] + [b[i]] for i, row in enumerate(a)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(m[r][c]))
        m[c], m[piv] = m[piv], m[c]
        d = m[c][c]
        if abs(d) < 1e-12:
            continue
        inv = 1.0 / d
        row_c = m[c]
        for j in range(c, n + 1):
            row_c[j] *= inv
        for r in range(n):
            if r != c:
                f = m[r][c]
                if f:
                    row_r = m[r]
                    for j in range(c, n + 1):
                        row_r[j] -= f * row_c[j]
    return [m[i][n] for i in range(n)]


def fit_logistic(X, y, l2=1.0, w=None, intercept=False, iters=25, tol=1e-7, offset=None):
    """Newton-IRLS for L2 logistic regression.  Returns (coef, bias).  X: list of lists.

    offset: optional per-row fixed term added to the linear predictor (e.g. logit of the market price,
    so the penalty shrinks the fitted coefficients toward "trust the market" rather than toward 50/50).
    """
    n, d = len(X), len(X[0])
    w = w or [1.0] * n
    offset = offset or [0.0] * n
    coef = [0.0] * d
    bias = 0.0
    dd = d + (1 if intercept else 0)
    for _ in range(iters):
        grad = [0.0] * dd
        hess = [[0.0] * dd for _ in range(dd)]
        for xi, yi, wi, oi in zip(X, y, w, offset):
            z = oi + bias + sum(c * v for c, v in zip(coef, xi))
            p = sigmoid(z)
            g = wi * (p - yi)
            h = wi * p * (1 - p)
            row = xi + [1.0] if intercept else xi
            for j in range(dd):
                rj = row[j]
                if rj == 0:
                    continue
                grad[j] += g * rj
                hr = h * rj
                hj = hess[j]
                for k in range(j, dd):
                    hj[k] += hr * row[k]
        for j in range(dd):
            for k in range(j):
                hess[j][k] = hess[k][j]
        for j in range(d):
            grad[j] += l2 * coef[j]
            hess[j][j] += l2
        if intercept:
            hess[d][d] += 1e-9
        step = _solve(hess, grad)
        coef = [c - s for c, s in zip(coef, step[:d])]
        if intercept:
            bias -= step[d]
        if max(abs(s) for s in step) < tol:
            break
    return coef, bias


def predict_logistic(coef, bias, x):
    return sigmoid(bias + sum(c * v for c, v in zip(coef, x)))


def softmax(zs):
    m = max(zs)
    e = [math.exp(z - m) for z in zs]
    s = sum(e)
    return [v / s for v in e]


# ---------------------------------------------------------------- metrics
def log_loss(ps, ys):
    eps = 1e-12
    return -sum(y * math.log(max(p, eps)) + (1 - y) * math.log(max(1 - p, eps)) for p, y in zip(ps, ys)) / len(ys)


def brier(ps, ys):
    return sum((p - y) ** 2 for p, y in zip(ps, ys)) / len(ys)


def accuracy(ps, ys):
    return sum((p > 0.5) == (y == 1) for p, y in zip(ps, ys)) / len(ys)


def calibration(ps, ys, bins=10):
    """Rows of (bin_low, bin_high, n, mean_pred, observed) over the favourite's probability."""
    rows = []
    fav = [(p, y) if p >= 0.5 else (1 - p, 1 - y) for p, y in zip(ps, ys)]
    edges = [0.5 + 0.5 * i / bins for i in range(bins + 1)]
    for lo, hi in zip(edges, edges[1:]):
        sel = [(p, y) for p, y in fav if lo <= p < hi or (hi == 1.0 and p == 1.0)]
        if sel:
            rows.append((round(lo, 3), round(hi, 3), len(sel), sum(p for p, _ in sel) / len(sel), sum(y for _, y in sel) / len(sel)))
    return rows


def ece(ps, ys, bins=10):
    rows = calibration(ps, ys, bins)
    n = sum(r[2] for r in rows)
    return sum(r[2] * abs(r[3] - r[4]) for r in rows) / n if n else None


def bootstrap(values_fn, n_items, reps=1000, seed=7):
    """Percentile CI of a statistic computed on resampled item indices.  values_fn(indices) -> float."""
    rnd = random.Random(seed)
    stats = []
    for _ in range(reps):
        idx = [rnd.randrange(n_items) for _ in range(n_items)]
        v = values_fn(idx)
        if v is not None:
            stats.append(v)
    stats.sort()
    if not stats:
        return None, None
    return stats[int(0.025 * len(stats))], stats[int(0.975 * len(stats)) - 1]


# ---------------------------------------------------------------- betting
def dec_odds(american):
    return 1 + american / 100.0 if american > 0 else 1 + 100.0 / -american


def backtest(bets, threshold=0.0, stake="flat", kelly_frac=0.25, min_prob=0.0, placebo=200, seed=5):
    """bets: dicts {p: probability of the side, odds: American price, won: 0/1, cluster: event key}.

    Bets every side with EV = p * dec - 1 >= threshold (and p >= min_prob).  ROI's CI resamples whole
    events (fights on one card share information).  The placebo percentile is where the ROI falls
    among random picks of the same number of sides from the same pool: ~50 means no better than luck.
    """
    placed = []
    for b in bets:
        d = dec_odds(b["odds"])
        e = b["p"] * d - 1
        if e < threshold or b["p"] < min_prob:
            continue
        f = max(0.0, (b["p"] * d - 1) / (d - 1)) * kelly_frac if stake == "kelly" else 1.0
        placed.append((f, d, b["won"], e, b.get("cluster")))
    if not placed:
        return {"bets": 0}
    staked = sum(p[0] for p in placed)
    profit = sum(p[0] * (p[1] - 1) if p[2] else -p[0] for p in placed)
    clusters = {}
    for i, p in enumerate(placed):
        clusters.setdefault(p[4] if p[4] is not None else i, []).append(i)
    keys = list(clusters)
    rnd = random.Random(seed)
    rois = []
    for _ in range(800):
        idx = [i for _ in keys for i in clusters[keys[rnd.randrange(len(keys))]]]
        s = sum(placed[i][0] for i in idx)
        if s:
            rois.append(sum(placed[i][0] * (placed[i][1] - 1) if placed[i][2] else -placed[i][0] for i in idx) / s)
    rois.sort()
    roi = profit / staked
    out = {"bets": len(placed), "staked": round(staked, 2), "profit": round(profit, 2), "roi": round(roi, 4),
           "roi_ci": [round(rois[int(0.025 * len(rois))], 4), round(rois[int(0.975 * len(rois)) - 1], 4)] if rois else None,
           "p_roi_pos": round(sum(1 for v in rois if v > 0) / len(rois), 3) if rois else None,
           "win_rate": round(sum(1 for p in placed if p[2]) / len(placed), 4),
           "avg_ev": round(sum(p[3] for p in placed) / len(placed), 4),
           "avg_odds": round(sum(p[1] for p in placed) / len(placed), 3)}
    if placebo and len(bets) > len(placed):
        pool = [(dec_odds(b["odds"]), b["won"]) for b in bets]
        beat = 0
        for _ in range(placebo):
            pick = rnd.sample(pool, len(placed))
            r = sum((d - 1) if w else -1 for d, w in pick) / len(pick)
            beat += r < roi
        out["placebo_pct"] = round(100.0 * beat / placebo, 1)
    return out
