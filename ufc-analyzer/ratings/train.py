"""Train and evaluate the ratings predictor walk-forward, then export ratings/model.json.

    python -m ratings.dataset ratings/data/rows.pkl     # point-in-time rows (10-15 minutes)
    python -m ratings.train [rows.pkl]

Protocol (the same windows as model/train.py so the two models can be compared):
  TUNE  2010-2015  regularization and which feature groups stay (ring rust, momentum, cardio...)
  VAL   2016-2020  confirms the choices
  TEST  2021-now   headline numbers, against the opening and closing lines

Every prediction for year Y comes from a fit on years before Y.  Feature groups are ablated on TUNE
and VAL: a group is dropped when removing it makes the walk-forward log loss better or no worse.
"""
import json, math, os, pickle, sys, time

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from ratings import features, learn  # noqa: E402
from ratings.features import ALL_FEATURES, GROUP, matchup  # noqa: E402

OUT = os.environ.get("RATINGS_OUT") or os.path.join(HERE, "model.json")
TUNE = list(range(2010, 2016))
VAL = list(range(2016, 2021))
TRAIN_FROM = 2009
C_GRID = (0.001, 0.003, 0.01, 0.03, 0.1, 0.3, 1.0)
OPTIONAL_GROUPS = ("rust", "momentum", "cardio", "matchup", "schedule", "judging", "record", "pace")


def logit(p):
    return learn.logit(p)


def sig(z):
    return learn.sigmoid(z)


def market_p(r, key):
    m = r.get("mkt")
    if not m or m.get(key) is None:
        return None
    return 1 - m[key] if r["swap"] else m[key]


def design(rows, feats):
    return np.array([[r["x"][f] for f in feats] for r in rows], dtype=float)


def fit(rows, feats, C, scale):
    X = design(rows, feats) / scale
    y = np.array([r["y"] for r in rows])
    m = LogisticRegression(C=C, fit_intercept=False, max_iter=3000)
    m.fit(np.vstack([X, -X]), np.concatenate([y, 1 - y]))
    return m.coef_[0]


def walk_forward(rows, feats, C, years, calibrate=True):
    """{row id: p} for rows in `years`, each from a fit on earlier years; calibration scale from the
    previous years' own out-of-sample predictions."""
    preds, raw = {}, {}
    by_year = {}
    for r in rows:
        by_year.setdefault(r["year"], []).append(r)
    for Y in sorted(years):
        tr = [r for r in rows if TRAIN_FROM <= r["year"] < Y and r["y"] is not None]
        te = by_year.get(Y, [])
        if len(tr) < 200 or not te:
            continue
        scale = np.sqrt((design(tr, feats) ** 2).mean(axis=0))
        scale[scale == 0] = 1.0
        coef = fit(tr, feats, C, scale)
        z = design(te, feats) / scale @ coef
        for r, zi in zip(te, z):
            raw[r["id"]] = float(zi)
    if not calibrate:
        return {k: sig(v) for k, v in raw.items()}
    # calibration: a single slope on the logit, fitted on earlier years' walk-forward logits
    byy = {}
    for r in rows:
        if r["id"] in raw and r["y"] is not None:
            byy.setdefault(r["year"], []).append(r)
    for Y in sorted(byy):
        past = [r for yr in byy if yr < Y for r in byy[yr]]
        a = 1.0
        if len(past) >= 300:
            zz = np.array([raw[r["id"]] for r in past])
            yy = np.array([r["y"] for r in past])
            m = LogisticRegression(C=100.0, fit_intercept=False).fit(np.concatenate([zz, -zz])[:, None], np.concatenate([yy, 1 - yy]))
            a = float(m.coef_[0][0])
        for r in byy[Y]:
            preds[r["id"]] = sig(a * raw[r["id"]])
    for r in rows:
        if r["id"] in raw and r["id"] not in preds:
            preds[r["id"]] = sig(raw[r["id"]])
    return preds


def ll_on(rows, preds):
    rs = [r for r in rows if r["id"] in preds and r["y"] is not None]
    return learn.log_loss([preds[r["id"]] for r in rs], [r["y"] for r in rs]), len(rs)


def dll_ci(rows, p1, p2, reps=1000):
    """Mean per-fight log-loss difference (p1 minus p2) with an event-clustered bootstrap interval."""
    rs = [r for r in rows if r["id"] in p1 and r["id"] in p2 and r["y"] is not None]
    d = [(-math.log(max(1e-12, p1[r["id"]] if r["y"] else 1 - p1[r["id"]]))) - (-math.log(max(1e-12, p2[r["id"]] if r["y"] else 1 - p2[r["id"]]))) for r in rs]
    est = sum(d) / len(d) if d else 0.0
    lo, hi = learn.cluster_bootstrap(d, [r["date"] for r in rs], lambda s: sum(s) / len(s), reps=reps) if d else (0.0, 0.0)
    return {"est": round(est, 4), "ci": [round(lo, 4), round(hi, 4)], "n": len(d)}


def metrics(rows, preds):
    rs = [r for r in rows if r["id"] in preds and r["y"] is not None]
    return learn.metrics([preds[r["id"]] for r in rs], [r["y"] for r in rs]) if rs else None


def main(rows_path=None):
    t0 = time.time()
    rows_path = rows_path or os.path.join(HERE, "data", "rows.pkl")
    with open(rows_path, "rb") as f:
        rows = pickle.load(f)
    rows = [r for r in rows if r["y"] is not None]
    for r in rows:
        r["x"] = matchup(r["A"], r["B"], r["rounds"], r["title"])
    last_year = max(r["year"] for r in rows)
    TEST = list(range(2021, last_year + 1))
    print(f"{len(rows)} rows 2009-{last_year}; market for {sum(1 for r in rows if r.get('mkt'))}")
    report = {"built": time.strftime("%Y-%m-%d"), "trained_through": max(r["date"] for r in rows), "fights": len(rows),
              "windows": {"tune": [TUNE[0], TUNE[-1]], "val": [VAL[0], VAL[-1]], "test": [TEST[0], TEST[-1]]}}

    # 1. regularization on TUNE with every feature
    feats = list(ALL_FEATURES)
    grid = {}
    for C in C_GRID:
        p = walk_forward(rows, feats, C, TUNE)
        grid[C] = ll_on([r for r in rows if r["year"] in TUNE], p)[0]
        print(f"  tune C={C:<6} log loss {grid[C]:.4f}")
    C = min(grid, key=grid.get)
    report["C"] = C

    # 2. group ablations: drop a group when the model does no worse without it (TUNE decides, VAL confirms)
    base_tune = walk_forward(rows, feats, C, TUNE)
    base_val = walk_forward(rows, feats, C, VAL)
    abl = {}
    kept = list(feats)
    for g in OPTIONAL_GROUPS:
        without = [f for f in kept if GROUP[f] != g]
        pt = walk_forward(rows, without, C, TUNE)
        pv = walk_forward(rows, without, C, VAL)
        dt = dll_ci([r for r in rows if r["year"] in TUNE], base_tune, pt, reps=400)   # negative = the group helps
        dv = dll_ci([r for r in rows if r["year"] in VAL], base_val, pv, reps=400)
        keep = dt["est"] < 0 and dv["est"] < 0
        abl[g] = {"tune_with_minus_without": dt, "val_with_minus_without": dv, "kept": keep, "features": [f for f in kept if GROUP[f] == g]}
        print(f"  group {g:10s} tune {dt['est']:+.4f} {dt['ci']}  val {dv['est']:+.4f} {dv['ci']}  -> {'keep' if keep else 'drop'}")
        if not keep:
            kept = without
            base_tune = walk_forward(rows, kept, C, TUNE)
            base_val = walk_forward(rows, kept, C, VAL)
    report["ablation"] = abl
    report["feats"] = kept

    # 3. out-of-sample predictions on every year with the kept features, plus baselines
    years = TUNE + VAL + TEST
    preds = walk_forward(rows, kept, C, years)
    rating_only = walk_forward(rows, ["rating"], 1.0, years)
    raw_only = walk_forward(rows, [f for f in kept if GROUP[f] not in ("adjusted", "schedule")], C, years)
    ev = {}
    for name, yrs in (("val", VAL), ("test", TEST)):
        rs = [r for r in rows if r["year"] in yrs]
        withm = [r for r in rs if market_p(r, "open_fair") is not None and market_p(r, "close_fair") is not None]
        mo = {r["id"]: market_p(r, "open_fair") for r in withm}
        mc = {r["id"]: market_p(r, "close_fair") for r in withm}
        ev[name] = {"years": f"{yrs[0]}-{yrs[-1]}", "model": metrics(rs, preds), "rating_only": metrics(rs, rating_only),
                    "without_adjusted": metrics(rs, raw_only),
                    "with_market": {"model": metrics(withm, preds), "market_open": metrics(withm, mo), "market_close": metrics(withm, mc),
                                    "model_minus_open": dll_ci(withm, preds, mo), "model_minus_close": dll_ci(withm, preds, mc)}}
        print(name, json.dumps(ev[name], indent=0))
    report["evaluation"] = ev
    # the other model's headline, for the record (same windows; its rows differ slightly)
    try:
        with open(os.path.join(os.path.dirname(HERE), "model", "model.json"), encoding="utf-8") as f:
            other = json.load(f)["evaluation"]
        report["blend_model_for_comparison"] = {k: {"model": other[k]["model"], "with_market": {kk: other[k]["with_market"][kk] for kk in ("model", "market_open", "market_close")}} for k in ("val", "test")}
    except Exception:
        pass

    # 4. final fit on everything; standardized coefficients double as feature importances
    final_rows = [r for r in rows if r["year"] >= TRAIN_FROM]
    scale = np.sqrt((design(final_rows, kept) ** 2).mean(axis=0))
    scale[scale == 0] = 1.0
    coef = fit(final_rows, kept, C, scale)
    zz = np.array([logit(preds[r["id"]]) for r in rows if r["id"] in preds])   # already calibrated per year
    a = 1.0
    raw_all = walk_forward(rows, kept, C, years, calibrate=False)
    z0 = np.array([logit(raw_all[r["id"]]) for r in rows if r["id"] in raw_all])
    y0 = np.array([r["y"] for r in rows if r["id"] in raw_all])
    m = LogisticRegression(C=100.0, fit_intercept=False).fit(np.concatenate([z0, -z0])[:, None], np.concatenate([y0, 1 - y0]))
    a = float(m.coef_[0][0])
    importance = sorted(((kept[i], round(float(abs(coef[i])), 4)) for i in range(len(kept))), key=lambda kv: -kv[1])
    model = dict(report, win={"feats": kept, "coef": [float(a * c / s) for c, s in zip(coef, scale)], "scale": [float(s) for s in scale],
                              "calibration_scale": a, "importance": importance},
                 description="Opponent-adjusted (KenPom-style) fighter ratings: striking, grappling, damage, control and submission "
                             "efficiencies adjusted for the quality of opposition, plus pace, cardio, durability, physical, experience, "
                             "ring rust and momentum terms; logistic predictor on fighter differences.")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1)
    print(f"wrote {OUT} in {time.time() - t0:.0f}s; top features {importance[:8]}")
    return model


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else None)
