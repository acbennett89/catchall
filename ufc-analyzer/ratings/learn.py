"""Small pure-Python learning helpers for the ratings model (so serving needs no packages): logistic
regression by Newton's method, metrics, bootstrap intervals.  Training itself may use numpy/sklearn
for speed; this is the reference the shipped coefficients must reproduce."""
import math, random


def sigmoid(z):
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def fit_logistic(X, y, l2=1.0, iters=50, tol=1e-8):
    """No intercept (features are antisymmetric differences).  Ridge penalty l2 * sum(coef^2) / 2."""
    k = len(X[0])
    w = [0.0] * k
    for _ in range(iters):
        g = [l2 * w[j] for j in range(k)]
        H = [[l2 if i == j else 0.0 for j in range(k)] for i in range(k)]
        for x, t in zip(X, y):
            p = sigmoid(sum(wi * xi for wi, xi in zip(w, x)))
            d = p - t
            s = p * (1 - p)
            for i in range(k):
                g[i] += d * x[i]
                xi = x[i] * s
                if xi:
                    Hi = H[i]
                    for j in range(k):
                        Hi[j] += xi * x[j]
        step = _solve(H, g)
        w = [wi - si for wi, si in zip(w, step)]
        if max(abs(s) for s in step) < tol:
            break
    return w


def _solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        p = M[c][c] or 1e-12
        for r in range(n):
            if r != c:
                f = M[r][c] / p
                if f:
                    Mr, Mc = M[r], M[c]
                    for j in range(c, n + 1):
                        Mr[j] -= f * Mc[j]
    return [M[i][n] / (M[i][i] or 1e-12) for i in range(n)]


def log_loss(p, y):
    return -sum(math.log(max(1e-12, pi if yi else 1 - pi)) for pi, yi in zip(p, y)) / len(y)


def brier(p, y):
    return sum((pi - yi) ** 2 for pi, yi in zip(p, y)) / len(y)


def accuracy(p, y):
    return sum(1 for pi, yi in zip(p, y) if (pi >= 0.5) == bool(yi)) / len(y)


def metrics(p, y):
    return {"n": len(y), "log_loss": round(log_loss(p, y), 4), "brier": round(brier(p, y), 4), "accuracy": round(accuracy(p, y), 4)}


def cluster_bootstrap(items, clusters, stat, reps=1000, seed=7):
    """95% interval of stat(subset) resampling whole clusters (event dates) with replacement."""
    rnd = random.Random(seed)
    by = {}
    for it, c in zip(items, clusters):
        by.setdefault(c, []).append(it)
    keys = list(by)
    vals = []
    for _ in range(reps):
        sample = [it for _ in keys for it in by[rnd.choice(keys)]]
        vals.append(stat(sample))
    vals.sort()
    return vals[int(0.025 * reps)], vals[int(0.975 * reps)]
