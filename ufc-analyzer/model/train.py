"""Train and evaluate the fight model, then export model/model.json for the app.

    python -m model.train

Everything reported is out-of-sample.  Walk-forward by calendar year: to predict year Y the model
is fitted only on fights before Y.  Hyperparameters (regularization, Elo settings) are chosen on
2012-2018 and the headline numbers are reported on 2019 onward, so the tuning doesn't flatter them.
The market benchmark uses the same fights (those with BestFightOdds history).

Training uses numpy/scikit-learn for speed; the export is plain coefficients that the app scores in
pure Python (model/predict.py).
"""
import json, math, os, sys, time

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import dataset, learn, market_hist, odds_history, scrape  # noqa: E402
from model.features import WIN_FEATURES  # noqa: E402
from model.predict import method_features  # noqa: E402

OUT = os.path.join(HERE, "model.json")
TRAIN_FROM = 2001
TUNE_YEARS = list(range(2012, 2019))
REPORT_YEARS = list(range(2019, 2027))
METHODS = ["ko", "sub", "dec"]


# ------------------------------------------------------------------ win model
def matrix(rows, feats, key="x"):
    return np.array([[r[key][f] for f in feats] for r in rows], dtype=float)


def fit_win(rows, feats, C):
    """Antisymmetric logistic model: scale features (no centering) and fit with no intercept on the
    rows plus their mirror images, so P(A beats B) = 1 - P(B beats A) exactly."""
    X = matrix(rows, feats)
    y = np.array([r["y"] for r in rows], dtype=float)
    scale = np.sqrt((X ** 2).mean(axis=0))
    scale[scale == 0] = 1.0
    Xs = X / scale
    m = LogisticRegression(C=C, fit_intercept=False, max_iter=5000).fit(np.vstack([Xs, -Xs]), np.concatenate([y, 1 - y]))
    return {"feats": list(feats), "coef": (m.coef_[0] / scale).tolist(), "scale": scale.tolist()}


def predict_win(model, rows):
    z = matrix(rows, model["feats"]) @ np.array(model["coef"])
    return 1 / (1 + np.exp(-z))


def walk_forward(rows, feats, C, years):
    preds = {}
    for Y in years:
        tr = [r for r in rows if TRAIN_FROM <= r["year"] < Y and r["y"] is not None]
        te = [r for r in rows if r["year"] == Y and r["y"] is not None]
        if len(tr) < 500 or not te:
            continue
        m = fit_win(tr, feats, C)
        preds.update({r["id"]: float(p) for r, p in zip(te, predict_win(m, te))})
    return preds


def metrics(p, y):
    p, y = [float(v) for v in p], [int(v) for v in y]
    if not y:
        return None
    return {"n": len(y), "log_loss": round(learn.log_loss(p, y), 4), "brier": round(learn.brier(p, y), 4),
            "accuracy": round(learn.accuracy(p, y), 4), "ece": round(learn.ece(p, y) or 0, 4)}


# ------------------------------------------------------------------ market helpers
def market_p(r, key):
    """Market probability for the row's side A (rows can be oriented opposite to UFCStats f1)."""
    m = r.get("mkt")
    if not m or m.get(key) is None:
        return None
    return 1 - m[key] if r["swap"] else m[key]


def market_price(r, side, which):
    """American price for side 0 (A) / 1 (B): which = 'open' | 'worst' | 'best' (closing range)."""
    m = r.get("mkt")
    if not m:
        return None
    f1side = side if not r["swap"] else 1 - side
    if which == "open":
        return m.get("open1") if f1side == 0 else m.get("open2")
    rng = [v for v in (m["close1"] if f1side == 0 else m["close2"]) if v is not None]
    if not rng:
        return None
    key = learn.dec_odds
    return min(rng, key=key) if which == "worst" else max(rng, key=key)


def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


# ------------------------------------------------------------------ method + rounds
def method_rows(rows):
    out = []
    for r in rows:
        if r["y"] is None or r["kind"] not in METHODS:
            continue
        W, L = (r["A"], r["B"]) if r["y"] == 1 else (r["B"], r["A"])
        out.append((method_features(W, L, r["rounds"]), METHODS.index(r["kind"]), r))
    return out


def fit_method(mrows, C=0.3):
    feats = list(mrows[0][0].keys())
    X = np.array([[x[f] for f in feats] for x, _, _ in mrows])
    y = np.array([c for _, c, _ in mrows])
    mu, sd = X.mean(axis=0), X.std(axis=0)
    sd[sd == 0] = 1.0
    m = LogisticRegression(C=C, max_iter=5000).fit((X - mu) / sd, y)
    coef = m.coef_ / sd                       # back to raw feature units
    bias = m.intercept_ - (m.coef_ * (mu / sd)).sum(axis=1)
    return {"feats": feats, "classes": METHODS, "coef": coef.tolist(), "bias": bias.tolist()}


def method_predict(mm, x):
    zs = [sum(c * x[f] for f, c in zip(mm["feats"], row)) + b for row, b in zip(mm["coef"], mm["bias"])]
    return learn.softmax(zs)


def round_dist(rows):
    """Historical finish-round mix and finish-time CDF by scheduled rounds (finishes only)."""
    out = {}
    for sched in (3, 5):
        fin = [r for r in rows if r["kind"] in ("ko", "sub") and r["rounds"] == sched and r["secs"] and r["round"]]
        if len(fin) < 50:
            continue
        counts = [0] * sched
        for r in fin:
            counts[min(sched, int(r["round"])) - 1] += 1
        share = [(c + 1) / (len(fin) + sched) for c in counts]
        cdf = [sum(1 for r in fin if r["secs"] < k * 300 + 150) / len(fin) for k in range(sched)]
        out[str(sched)] = {"share": [round(s, 4) for s in share], "cdf_half": [round(c, 4) for c in cdf], "n": len(fin)}
    return out



# ------------------------------------------------------------------ tuning, challenger, uncertainty
ENGINE_GRID = [
    {},
    {"k": 24.0, "k_new": 48.0},
    {"k": 40.0, "k_new": 80.0},
    {"finish_mult": 1.0, "dec_mult": 1.0, "split_mult": 1.0},
    {"finish_mult": 1.5},
    {"dom_k": 25.0},
    {"dom_k": 60.0},
    {"decay_days": 365.0},
    {"decay_days": 1460.0},
    {"inactive_regress": 0.0},
    {"inactive_regress": 0.3},
]


def tune_engine(ev, fi, fr, C=0.1):
    """Pick rating/decay settings by walk-forward log loss on the tuning years only (greedy, one knob group at a time)."""
    best_p, best_ll = {}, None
    for delta in ENGINE_GRID:
        params = dict(best_p, **delta)
        rows, _, _ = dataset.build_rows(ev, fi, fr, engine_params=params)
        preds = walk_forward(rows, WIN_FEATURES, C, TUNE_YEARS)
        te = [r for r in rows if r["id"] in preds]
        ll = learn.log_loss([preds[r["id"]] for r in te], [r["y"] for r in te])
        print(f"  engine {delta or 'defaults'}: {ll:.4f}")
        if best_ll is None or ll < best_ll - 1e-4:
            best_p, best_ll = params, ll
    return best_p, best_ll


def gbm_challenger(rows, years):
    """Symmetrized LightGBM on the same features; returns out-of-sample predictions (or {} if unavailable)."""
    try:
        import lightgbm as lgb
    except Exception:
        return {}
    preds = {}
    for Y in years:
        tr = [r for r in rows if TRAIN_FROM <= r["year"] < Y and r["y"] is not None]
        te = [r for r in rows if r["year"] == Y and r["y"] is not None]
        if len(tr) < 500 or not te:
            continue
        X = matrix(tr, WIN_FEATURES)
        y = np.array([r["y"] for r in tr])
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)
        m.fit(np.vstack([X, -X]), np.concatenate([y, 1 - y]))
        Xt = matrix(te, WIN_FEATURES)
        p = (m.predict_proba(Xt)[:, 1] + (1 - m.predict_proba(-Xt)[:, 1])) / 2
        preds.update({r["id"]: float(v) for r, v in zip(te, p)})
    return preds


def paired_ci(rows, pa, pb, reps=1000, seed=11):
    """Bootstrap CI (clustered by event date) of log loss(pa) - log loss(pb) over the given rows."""
    import random
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    days = list(by_day)
    rnd = random.Random(seed)

    def ll(p, y):
        p = min(max(p, 1e-12), 1 - 1e-12)
        return -(y * math.log(p) + (1 - y) * math.log(1 - p))
    diffs = []
    for _ in range(reps):
        tot, n = 0.0, 0
        for _ in days:
            for r in by_day[days[rnd.randrange(len(days))]]:
                tot += ll(pa(r), r["y"]) - ll(pb(r), r["y"])
                n += 1
        diffs.append(tot / n)
    diffs.sort()
    point = sum(ll(pa(r), r["y"]) - ll(pb(r), r["y"]) for r in rows) / len(rows)
    return {"diff": round(point, 4), "ci": [round(diffs[int(0.025 * reps)], 4), round(diffs[int(0.975 * reps) - 1], 4)]}

# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    ev, fi, fr = scrape.load_dataset()
    print("tuning rating settings on", TUNE_YEARS[0], "-", TUNE_YEARS[-1])
    engine_params, _ = tune_engine(ev, fi, fr)
    print("engine params:", engine_params)
    rows, eng, _ = dataset.build_rows(ev, fi, fr, engine_params=engine_params)
    last_date = max(r["date"] for r in rows)
    print(f"{len(rows)} fights through {last_date}; replay {time.time() - t0:.1f}s")
    mk = market_hist.join(fi, odds_history.load())
    for r in rows:
        if r["id"] in mk:
            r["mkt"] = mk[r["id"]]
    print(f"market history joined for {sum('mkt' in r for r in rows)} fights")
    report = {"built": time.strftime("%Y-%m-%d"), "trained_through": last_date, "fights": len(rows)}

    # 1. choose regularization on the tuning years
    grid = {}
    for C in (0.003, 0.01, 0.03, 0.1, 0.3, 1.0):
        preds = walk_forward(rows, WIN_FEATURES, C, TUNE_YEARS)
        te = [r for r in rows if r["id"] in preds]
        grid[C] = learn.log_loss([preds[r["id"]] for r in te], [r["y"] for r in te])
        print(f"  tune C={C:<6} log loss {grid[C]:.4f}")
    C = min(grid, key=grid.get)
    print(f"chosen C={C}")

    # 2. out-of-sample predictions for every year from 2012 (tuning years included, for the blend)
    preds = walk_forward(rows, WIN_FEATURES, C, TUNE_YEARS + REPORT_YEARS)
    elo_preds = walk_forward(rows, ["elo"], 1.0, TUNE_YEARS + REPORT_YEARS)
    rep = [r for r in rows if r["id"] in preds and r["year"] in REPORT_YEARS]
    y = [r["y"] for r in rep]
    report["evaluation"] = {"period": f"{REPORT_YEARS[0]}-{last_date[:4]}", "C": C,
                            "model": metrics([preds[r["id"]] for r in rep], y),
                            "elo_only": metrics([elo_preds[r["id"]] for r in rep], y)}
    # same fights, with market history
    both = [r for r in rep if market_p(r, "close_fair") is not None]
    yb = [r["y"] for r in both]
    report["evaluation"]["vs_market"] = {
        "model": metrics([preds[r["id"]] for r in both], yb),
        "market_close": metrics([market_p(r, "close_fair") for r in both], yb),
        "market_open": metrics([market_p(r, "open_fair") for r in both if market_p(r, "open_fair") is not None],
                               [r["y"] for r in both if market_p(r, "open_fair") is not None]),
    }
    gbm = gbm_challenger(rows, REPORT_YEARS)
    if gbm:
        g = [r for r in rep if r["id"] in gbm]
        report["evaluation"]["gbm_challenger"] = metrics([gbm[r["id"]] for r in g], [r["y"] for r in g])
    report["evaluation"]["model_minus_close"] = paired_ci(both, lambda r: preds[r["id"]], lambda r: market_p(r, "close_fair"))
    op = [r for r in both if market_p(r, "open_fair") is not None]
    report["evaluation"]["model_minus_open"] = paired_ci(op, lambda r: preds[r["id"]], lambda r: market_p(r, "open_fair"))
    print(json.dumps(report["evaluation"], indent=1))

    # 3. market-anchored blends, fitted walk-forward on earlier years' out-of-sample model predictions.
    #    The closing-line blend is the honest "best estimate" on fight night; betting at opening lines
    #    must use a blend of the OPENING line (the close isn't known yet when you'd bet the open).
    def blend_walk(key):
        out, fits = {}, []
        for Y in REPORT_YEARS:
            tr = [r for r in rows if r["id"] in preds and r["year"] < Y and market_p(r, key) is not None]
            te = [r for r in rows if r["id"] in preds and r["year"] == Y and market_p(r, key) is not None]
            if len(tr) < 300 or not te:
                continue
            w = fit_blend(tr, key)
            fits.append((Y, [round(v, 4) for v in w]))
            for r in te:
                z = w[0] * logit(market_p(r, key)) + w[1] * logit(preds[r["id"]])
                out[r["id"]] = 1 / (1 + math.exp(-z))
        return out, fits

    def fit_blend(tr, key):
        X = np.array([[logit(market_p(r, key)), logit(preds[r["id"]])] for r in tr])
        yy = np.array([r["y"] for r in tr])
        bm = LogisticRegression(C=10.0, fit_intercept=False).fit(np.vstack([X, -X]), np.concatenate([yy, 1 - yy]))
        return bm.coef_[0].tolist()

    blend_preds, blend_fits = blend_walk("close_fair")
    blend_open_preds, blend_open_fits = blend_walk("open_fair")
    bb = [r for r in both if r["id"] in blend_preds]
    bo = [r for r in rep if r["id"] in blend_open_preds]
    report["evaluation"]["blend"] = {
        "fights": len(bb),
        "blend": metrics([blend_preds[r["id"]] for r in bb], [r["y"] for r in bb]),
        "market_close": metrics([market_p(r, "close_fair") for r in bb], [r["y"] for r in bb]),
        "blend_minus_close": paired_ci(bb, lambda r: blend_preds[r["id"]], lambda r: market_p(r, "close_fair")) if bb else None,
        "weights_by_year": blend_fits,
        "open_blend": metrics([blend_open_preds[r["id"]] for r in bo], [r["y"] for r in bo]),
        "market_open": metrics([market_p(r, "open_fair") for r in bo], [r["y"] for r in bo]),
        "open_blend_minus_open": paired_ci(bo, lambda r: blend_open_preds[r["id"]], lambda r: market_p(r, "open_fair")) if bo else None,
        "open_weights_by_year": blend_open_fits,
    }
    print(json.dumps(report["evaluation"]["blend"], indent=1))

    # 4. betting backtests (flat 1 unit) on report years.  Prices: the opening line, or the worst /
    #    best price in the closing range (Caesars' own history isn't published; worst is the cautious proxy).
    def bets_for(prob_of, which):
        out = []
        for r in rep:
            p = prob_of(r)
            if p is None:
                continue
            for side, ps in ((0, p), (1, 1 - p)):
                o = market_price(r, side, which)
                if o is None:
                    continue
                won = (r["y"] == 1) if side == 0 else (r["y"] == 0)
                out.append({"p": ps, "odds": o, "won": 1 if won else 0})
        return out
    strategies = [
        ("model", "open", lambda r: preds.get(r["id"])),
        ("model", "worst", lambda r: preds.get(r["id"])),
        ("model", "best", lambda r: preds.get(r["id"])),
        ("blend", "open", lambda r: blend_open_preds.get(r["id"])),
        ("blend", "worst", lambda r: blend_preds.get(r["id"])),
        ("blend", "best", lambda r: blend_preds.get(r["id"])),
        ("market", "worst", lambda r: market_p(r, "close_fair")),  # sanity check: should lose about the vig
    ]
    bt = {}
    for label, which, fn in strategies:
        bets = bets_for(fn, which)
        for th in (0.0, 0.03, 0.05, 0.10):
            bt[f"{label}|{which}|{th}"] = learn.backtest(bets, threshold=th)
    report["evaluation"]["backtest"] = bt
    for k, v in bt.items():
        print(f"  {k:22s} {v}")

    # 5. calibration of the model on report years
    report["evaluation"]["calibration"] = [list(row) for row in learn.calibration([preds[r["id"]] for r in rep], y)]

    # 6. method model (walk-forward check on report years, then final fit)
    mrows = method_rows(rows)
    mm_tr = [m for m in mrows if TRAIN_FROM <= m[2]["year"] < REPORT_YEARS[0]]
    mm_te = [m for m in mrows if m[2]["year"] in REPORT_YEARS]
    mm = fit_method(mm_tr)
    base = [sum(1 for m in mm_tr if m[1] == k) / len(mm_tr) for k in range(3)]
    ll_m = -sum(math.log(max(1e-9, method_predict(mm, x)[c])) for x, c, _ in mm_te) / len(mm_te)
    ll_b = -sum(math.log(max(1e-9, base[c])) for _, c, _ in mm_te) / len(mm_te)
    report["evaluation"]["method"] = {"fights": len(mm_te), "log_loss": round(ll_m, 4), "base_rate_log_loss": round(ll_b, 4),
                                      "base_rates": dict(zip(METHODS, [round(b, 3) for b in base]))}
    print(report["evaluation"]["method"])

    # 7. final fits on everything and export
    final_rows = [r for r in rows if r["year"] >= TRAIN_FROM and r["y"] is not None]
    win = fit_win(final_rows, WIN_FEATURES, C)
    method = fit_method([m for m in mrows if m[2]["year"] >= TRAIN_FROM])
    method["round_dist"] = round_dist([r for r in rows if r["year"] >= 2010])
    blend = None
    tr = [r for r in rows if r["id"] in preds and market_p(r, "close_fair") is not None]
    tro = [r for r in rows if r["id"] in preds and market_p(r, "open_fair") is not None]
    if len(tr) >= 300:
        w = fit_blend(tr, "close_fair")
        wo = fit_blend(tro, "open_fair") if len(tro) >= 300 else None
        blend = {"w_market": w[0], "w_model": w[1], "fights": len(tr),
                 "open": {"w_market": wo[0], "w_model": wo[1], "fights": len(tro)} if wo else None}
    model = dict(report, engine=dict(eng.p), win=win, method=method, blend=blend,
                 description="Logistic model on point-in-time differences (Elo, experience, age, reach, striking/grappling rates, durability, form); "
                             "method of victory from a multinomial model; finish rounds from historical mix.")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1)
    print(f"wrote {OUT} in {time.time() - t0:.0f}s")
    return model, rows, preds


if __name__ == "__main__":
    main()
