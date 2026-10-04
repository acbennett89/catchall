"""Cage points: what wins a fight, fitted once on the tuning years (2008-2015) and frozen.

A mirrored, intercept-free ridge logistic regression of the fight winner on the two fighters' per-15-
minute stat margins (significant strikes, head strikes, ground strikes, knockdowns, takedowns, control
minutes, submission attempts, total strikes).  The coefficients are:

  * the weights that turn adjusted ratios into AdjO / AdjD / AdjEM (cage points per 15 minutes), so
    AdjEM is in log-odds units and Pyth = sigmoid(AdjEM) is the chance of beating an average fighter;
  * the in-fight model behind "luck": P(win | the fight's own stat line), summed into expected wins.

    python -m ratings.cagepoints      -> ratings/data/cagepoints.json
"""
import json, os, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from ratings import fightdata  # noqa: E402

PATH = os.path.join(HERE, "data", "cagepoints.json")
STATS = ("sig", "head", "ground", "kd", "td", "ctrl", "sub", "tot")
FIT_YEARS = (2008, 2015)


def margins(r):
    """Per-15-minute margins of f1 over f2 for the fitted stats (control in minutes)."""
    m = max(r["secs"] / 60.0, 0.5)
    out = []
    for k in STATS:
        a, b = (r["s1"].get(k) or 0), (r["s2"].get(k) or 0)
        if k == "ctrl":
            a, b = a / 60.0, b / 60.0
        out.append((a - b) / m * 15.0)
    return out


def load():
    try:
        with open(PATH, encoding="utf-8") as f:
            d = json.load(f)
        return {k: v for k, v in zip(d["stats"], d["coef"])}
    except Exception:
        return None


def win_prob(coef, r, side=0):
    """P(side wins) from the fight's own stat line (side 0 = f1)."""
    import math
    z = sum(coef.get(k, 0.0) * v for k, v in zip(STATS, margins(r)))
    if side:
        z = -z
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def fit(fights, years=FIT_YEARS, C=0.05):
    import numpy as np
    from sklearn.linear_model import LogisticRegression
    rows = [r for r in fights if years[0] <= int(r["date"][:4]) <= years[1] and r["result"] in ("f1", "f2") and r["kind"] in ("ko", "sub", "dec")]
    X = np.array([margins(r) for r in rows])
    y = np.array([1.0 if r["result"] == "f1" else 0.0 for r in rows])
    sd = X.std(axis=0) + 1e-9
    m = LogisticRegression(C=C, fit_intercept=False, max_iter=3000).fit(np.vstack([X, -X]) / sd, np.concatenate([y, 1 - y]))
    coef = (m.coef_[0] / sd).tolist()
    p = 1 / (1 + np.exp(-(X @ np.array(coef))))
    acc = float(((p > 0.5) == (y > 0.5)).mean())
    return {"stats": list(STATS), "coef": [round(c, 5) for c in coef], "fit_years": list(years), "n": len(rows), "accuracy": round(acc, 4),
            "note": "logit per unit of per-15-minute margin; control in minutes"}


if __name__ == "__main__":
    d = fightdata.load()
    out = fit(d["fights"])
    os.makedirs(os.path.dirname(PATH), exist_ok=True)
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1)
    print(json.dumps(out))
