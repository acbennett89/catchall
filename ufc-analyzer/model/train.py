"""Train and evaluate the fight model, then export model/model.json for the app.

    python -m model.train

Protocol (time splits only):
  TUNE  2010-2015  rating settings and regularization chosen here (walk-forward)
  VAL   2016-2020  decides whether the market blend may move prices (the "gate")
  TEST  2021-now   headline numbers, reported once after everything above is fixed

Every prediction is out-of-sample: to predict year Y the model is fitted on fights before Y (and the
calibration and blend weights on earlier years' out-of-sample predictions).  The market benchmark
uses the same fights, from BestFightOdds opening lines and closing ranges.

Training uses numpy/scikit-learn for speed; the export is plain numbers that the app scores in
pure Python (model/predict.py).
"""
import json, math, os, random, sys, time

import numpy as np
from sklearn.linear_model import LogisticRegression

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import dataset, engine, espn_hist, learn, market_hist, odds_history, predict, scrape  # noqa: E402
from model.features import WIN_FEATURES, win_features  # noqa: E402
from model.predict import method_features  # noqa: E402

OUT = os.path.join(HERE, "model.json")
TRAIN_FROM = 2001
TUNE_YEARS = list(range(2010, 2016))
VAL_YEARS = list(range(2016, 2021))
TEST_YEARS = list(range(2021, 2027))   # extended to the latest year in the data by main()
OOS_YEARS = TUNE_YEARS + VAL_YEARS + TEST_YEARS
METHODS = ["ko", "sub", "dec"]
STACK_L2 = 40.0          # = penalty 20 * sum(theta^2): shrinks the blend toward "trust the market"
SYNTH_HOLD = 0.044       # Caesars-like two-way margin for synthetic prices (power method)
BET_EV, BET_MIN_P = 0.03, 0.20
MIN_UFC_FIGHTS = 2       # the app's rule: a blend-made bet needs both fighters with 2+ UFC fights
ANCHOR_KEY = {"open": "open_fair", "close": "close_fair"}


# ------------------------------------------------------------------ small helpers
def logit(p):
    p = min(max(p, 1e-6), 1 - 1e-6)
    return math.log(p / (1 - p))


def sig(z):
    return 1 / (1 + math.exp(-z)) if z >= 0 else math.exp(z) / (1 + math.exp(z))


def metrics(p, y):
    p, y = [float(v) for v in p], [int(v) for v in y]
    if not y:
        return None
    return {"n": len(y), "log_loss": round(learn.log_loss(p, y), 4), "brier": round(learn.brier(p, y), 4),
            "accuracy": round(learn.accuracy(p, y), 4), "ece": round(learn.ece(p, y) or 0, 4)}


def cluster_ci(rows, stat, reps=2000, seed=11):
    """Point estimate and event-clustered bootstrap 95% CI of stat(rows)."""
    by_day = {}
    for r in rows:
        by_day.setdefault(r["date"], []).append(r)
    days = list(by_day)
    rnd = random.Random(seed)
    vals = []
    for _ in range(reps):
        v = stat([r for _ in days for r in by_day[days[rnd.randrange(len(days))]]])
        if v is not None:
            vals.append(v)
    vals.sort()
    return {"est": round(stat(rows), 4), "ci": [round(vals[int(0.025 * len(vals))], 4), round(vals[int(0.975 * len(vals)) - 1], 4)]}


def dll(pa, pb):
    """Mean per-fight log-loss difference LL(pa) - LL(pb) over a list of rows (negative = pa better)."""
    def f(rows):
        if not rows:
            return None
        tot = 0.0
        for r in rows:
            a, b = min(max(pa(r), 1e-12), 1 - 1e-12), min(max(pb(r), 1e-12), 1 - 1e-12)
            y = r["y"]
            tot += -(y * math.log(a) + (1 - y) * math.log(1 - a)) + (y * math.log(b) + (1 - y) * math.log(1 - b))
        return tot / len(rows)
    return f


# ------------------------------------------------------------------ win model
def matrix(rows, feats):
    return np.array([[r["x"][f] for f in feats] for r in rows], dtype=float)


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


ENGINE_GRID = [
    {}, {"k": 24.0, "k_new": 48.0}, {"k": 40.0, "k_new": 80.0},
    {"finish_mult": 1.0, "dec_mult": 1.0, "split_mult": 1.0}, {"finish_mult": 1.5},
    {"dom_k": 25.0}, {"dom_k": 60.0}, {"decay_days": 365.0}, {"decay_days": 1460.0},
    {"inactive_regress": 0.0}, {"inactive_regress": 0.3},
]


def tune_engine(ev, fi, fr, hist, C=0.003):
    """Greedy search of rating/decay settings by walk-forward log loss on the TUNE years only."""
    best_p, best_ll = {}, None
    for delta in ENGINE_GRID:
        params = dict(best_p, **delta)
        rows, _, _ = dataset.build_rows(ev, fi, fr, engine_params=params, espn_histories=hist)
        preds = walk_forward(rows, WIN_FEATURES, C, TUNE_YEARS)
        te = [r for r in rows if r["id"] in preds]
        ll = learn.log_loss([preds[r["id"]] for r in te], [r["y"] for r in te])
        print(f"  engine {delta or 'defaults'}: {ll:.4f}")
        if best_ll is None or ll < best_ll - 1e-4:
            best_p, best_ll = params, ll
    return best_p


def gbm_challenger(rows, years):
    """Symmetrized LightGBM on the same features (out-of-sample), or {} if lightgbm isn't installed."""
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
        X, y = matrix(tr, WIN_FEATURES), np.array([r["y"] for r in tr])
        m = lgb.LGBMClassifier(n_estimators=300, learning_rate=0.03, num_leaves=15, min_child_samples=40,
                               subsample=0.8, subsample_freq=1, colsample_bytree=0.8, reg_lambda=1.0, verbose=-1)
        m.fit(np.vstack([X, -X]), np.concatenate([y, 1 - y]))
        Xt = matrix(te, WIN_FEATURES)
        p = (m.predict_proba(Xt)[:, 1] + (1 - m.predict_proba(-Xt)[:, 1])) / 2
        preds.update({r["id"]: float(v) for r, v in zip(te, p)})
    return preds


# ------------------------------------------------------------------ market
def market_p(r, key):
    """Market probability for the row's side A (rows can be oriented opposite to UFCStats f1)."""
    m = r.get("mkt")
    if not m or m.get(key) is None:
        return None
    return 1 - m[key] if r["swap"] else m[key]


def synth_price(p_fair, hold=SYNTH_HOLD):
    """Book price for a side with fair probability p_fair, re-vigged with the power method
    (q_i = p_i^(1/k), sum q_i = 1 + hold), which loads more margin on underdogs, as books do."""
    pa = min(max(p_fair, 1e-4), 1 - 1e-4)
    pb = 1 - pa
    lo, hi = 1.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if pa ** (1 / k) + pb ** (1 / k) > 1 + hold:
            hi = k
        else:
            lo = k
    q = min(0.995, pa ** (1 / ((lo + hi) / 2)))
    d = 1 / q
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


def market_price(r, side, which, hold=SYNTH_HOLD):
    """American price for side 0 (A) / 1 (B).  which: open | worst | best (closing range) | synth (closing
    fair price re-vigged to a Caesars-like margin)."""
    m = r.get("mkt")
    if not m:
        return None
    if which == "synth":
        p = market_p(r, "close_fair")
        return None if p is None else synth_price(p if side == 0 else 1 - p, hold)
    f1side = side if not r["swap"] else 1 - side
    if which == "open":
        return m.get("open1") if f1side == 0 else m.get("open2")
    rng = [v for v in (m["close1"] if f1side == 0 else m["close2"]) if v is not None]
    if not rng:
        return None
    return min(rng, key=learn.dec_odds) if which == "worst" else max(rng, key=learn.dec_odds)


# ------------------------------------------------------------------ stacker (market blend)
def stack_x(r, p_model, key, form):
    """Design row for the offset-form stacker z = L_m + b_e*(1-D2)*d + b_d*D2*d [+ alpha*L_m] where
    L_m = logit(market), d = logit(model) - L_m and D2 = a fighter with fewer than 2 UFC fights."""
    lm = logit(market_p(r, key))
    d = logit(p_model) - lm
    d2 = 1.0 if min(r["A"]["fights"], r["B"]["fights"]) < 2 else 0.0
    x = [(1 - d2) * d, d2 * d]
    if form == "S2":
        x.append(lm)
    return x, lm


def fit_stack(rows, preds, key, form="S1"):
    """Penalized toward the market (all coefficients 0 = pure market).  Mirrored rows, weight 1/2 each."""
    X, y, off = [], [], []
    for r in rows:
        x, lm = stack_x(r, preds[r["id"]], key, form)
        X += [x, [-v for v in x]]
        off += [lm, -lm]
        y += [r["y"], 1 - r["y"]]
    coef, _ = learn.fit_logistic(X, y, l2=STACK_L2, w=[0.5] * len(y), offset=off)
    return coef


def apply_stack(coef, r, p_model, key, form="S1"):
    x, lm = stack_x(r, p_model, key, form)
    return sig(lm + sum(c * v for c, v in zip(coef, x)))


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
    coef = m.coef_ / sd
    bias = m.intercept_ - (m.coef_ * (mu / sd)).sum(axis=1)
    return {"feats": feats, "classes": METHODS, "coef": coef.tolist(), "bias": bias.tolist()}


def method_predict(mm, x):
    zs = [sum(c * x[f] for f, c in zip(mm["feats"], row)) + b for row, b in zip(mm["coef"], mm["bias"])]
    return learn.softmax(zs)


def outcome_params(rows, fights):
    """Shapes for the props table: per method and format, the cumulative round hazard Lambda (so that a
    fight with finish probability F and c = -ln(1-F) finishes in round r with probability proportional to
    exp(-c*L[r-1]) - exp(-c*L[r])), each method's share of finishes in a round's first half, the draw
    rate among decision-bound fights and the split/majority share of decisions."""
    out = {"lambda": {}, "first_half": {}, "finish_rate": {}}
    for sched in (3, 5):
        bound = [r for r in rows if r["rounds"] == sched and r["result"] in ("f1", "f2", "draw")]
        fin_all = [r for r in bound if r["kind"] in ("ko", "sub")]
        if len(fin_all) < 100:
            continue
        F = len(fin_all) / len(bound)
        c = -math.log(1 - F)
        out["finish_rate"][str(sched)] = round(F, 4)
        for m in ("ko", "sub"):
            fin = [r for r in fin_all if r["kind"] == m and r["round"]]
            counts = [0] * sched
            for r in fin:
                counts[min(sched, int(r["round"])) - 1] += 1
            share = [(k + 0.5) / (len(fin) + 0.5 * sched) for k in counts]
            cum, lam = 0.0, [0.0]
            for s_ in share:
                cum += s_
                lam.append(-math.log(1 - min(cum, 0.999999) * (1 - math.exp(-c))) / c)
            lam[-1] = 1.0
            out["lambda"].setdefault(str(sched), {})[m] = [round(v, 5) for v in lam]
    for m in ("ko", "sub"):
        fin = [r for r in rows if r["kind"] == m and r["secs"] and r["round"] and r["year"] >= 2010]
        half = sum(1 for r in fin if r["secs"] - (int(r["round"]) - 1) * 300 < 150)
        out["first_half"][m] = round((half + 10) / (len(fin) + 20), 4)
    decs = [r for r in rows if r["year"] >= 2010 and r["result"] in ("f1", "f2") and r["kind"] == "dec"]
    draws = [r for r in rows if r["year"] >= 2010 and r["result"] == "draw"]
    out["draw_rate"] = round(len(draws) / (len(decs) + len(draws)), 4)
    split = sum(1 for r in decs if (fights[r["id"]].get("method") or "").upper().startswith(("S-DEC", "M-DEC")))
    out["split_share"] = round(split / len(decs), 4)
    return out


def outcome_eval(rows, mm, preds, blend, years):
    """Log loss of how the fight ends (finish in round 1..R, or goes the distance) and of goes-the-distance
    alone, against base rates by format from the years before VAL."""
    def end_class(r, R):
        return int(r["round"]) - 1 if r["kind"] in ("ko", "sub") and r["round"] else R
    base = {}
    for R in (3, 5):
        tr = [r for r in rows if TRAIN_FROM <= r["year"] < VAL_YEARS[0] and r["rounds"] == R and r["result"] in ("f1", "f2", "draw")]
        cnt = [0.5] * (R + 1)
        for r in tr:
            cnt[min(R, end_class(r, R))] += 1
        base[R] = [c / sum(cnt) for c in cnt]
    te = [r for r in rows if r["year"] in years and r["rounds"] in (3, 5) and r["result"] in ("f1", "f2", "draw") and r["id"] in preds]
    if not te:
        return None
    ll = llb = dl = dlb = 0.0
    for r in te:
        R = r["rounds"]
        pa = blend.get(r["id"], preds[r["id"]])
        t = predict.method_probs(mm, r["A"], r["B"], pa, R, r["div"])
        probs = [x["a"] + x["b"] for x in t["rounds"]] + [t["distance"]]
        k = min(R, end_class(r, R))
        ll -= math.log(max(1e-9, probs[k]))
        llb -= math.log(max(1e-9, base[R][k]))
        went = 1 if k == R else 0
        pd, pdb = min(max(t["distance"], 1e-6), 1 - 1e-6), base[R][R]
        dl -= math.log(pd if went else 1 - pd)
        dlb -= math.log(pdb if went else 1 - pdb)
    n = len(te)
    return {"fights": n, "end_log_loss": round(ll / n, 4), "end_base_log_loss": round(llb / n, 4),
            "distance_log_loss": round(dl / n, 4), "distance_base_log_loss": round(dlb / n, 4)}


# ------------------------------------------------------------------ betting backtest
def bets_for(rows, prob_of, which, hold=SYNTH_HOLD):
    """One candidate per fight: the side with the higher EV at the given prices."""
    out = []
    for r in rows:
        p = prob_of(r)
        if p is None:
            continue
        pc = market_p(r, "close_fair")
        best = None
        for side, ps in ((0, p), (1, 1 - p)):
            o = market_price(r, side, which, hold)
            if o is None:
                continue
            e = ps * learn.dec_odds(o) - 1
            if best is None or e > best[0]:
                won = (r["y"] == 1) if side == 0 else (r["y"] == 0)
                best = (e, {"p": ps, "odds": o, "won": 1 if won else 0, "cluster": r["date"], "year": r["year"],
                            "pc": None if pc is None else (pc if side == 0 else 1 - pc)})
        if best:
            out.append(best[1])
    return out


def rule_bets(rows, bet_p, key, which, blend_bets, min_fights=MIN_UFC_FIGHTS, max_gap=None):
    """The app's BET rule (modelapi.decide) on history, one side per fight: EV >= 3% at the bet
    probability and a side >= 20%.  A bet the plain market price doesn't already make (EV < 3% at the
    market fair price) is allowed only with blend_bets (early lines), and needs both fighters with
    min_fights UFC fights (and, with max_gap, the model within max_gap of the market)."""
    out = []
    for r in rows:
        pb, pm, pf = bet_p(r), market_p(r, key), None
        if max_gap is not None:
            pf = r.get("_pmodel")
        if pb is None or pm is None:
            continue
        best = None
        for side in (0, 1):
            o = market_price(r, side, which)
            if o is not None:
                e = (pb if side == 0 else 1 - pb) * learn.dec_odds(o) - 1
                if best is None or e > best[0]:
                    best = (e, side, o)
        if not best:
            continue
        e, side, o = best
        ps, ms = (pb, pm) if side == 0 else (1 - pb, 1 - pm)
        fs = None if pf is None else (pf if side == 0 else 1 - pf)
        e_m = ms * learn.dec_odds(o) - 1
        if e < BET_EV or ps < BET_MIN_P:
            continue
        if e_m < BET_EV:
            if not blend_bets or min(r["A"]["fights"], r["B"]["fights"]) < min_fights:
                continue
            if max_gap is not None and fs is not None and abs(fs - ms) > max_gap:
                continue
        pc = market_p(r, "close_fair")
        won = (r["y"] == 1) if side == 0 else (r["y"] == 0)
        out.append({"p": ps, "odds": o, "won": 1 if won else 0, "cluster": r["date"], "year": r["year"],
                    "pc": None if pc is None else (pc if side == 0 else 1 - pc),
                    "kind": "market" if e_m >= BET_EV else "blend"})
    return out


def run_backtest(bets):
    """Pre-registered rule (EV >= 3%, side >= 20%), with per-year ROI, drawdown and closing-line value."""
    res = learn.backtest(bets, threshold=BET_EV, min_prob=BET_MIN_P)
    if not res.get("bets"):
        return res
    placed = [b for b in bets if b["p"] * learn.dec_odds(b["odds"]) - 1 >= BET_EV and b["p"] >= BET_MIN_P]
    by_year = {}
    for b in placed:
        by_year.setdefault(b["year"], []).append(b)
    res["roi_by_year"] = {y: round(sum((learn.dec_odds(b["odds"]) - 1) if b["won"] else -1 for b in bs) / len(bs), 3)
                          for y, bs in sorted(by_year.items())}
    bank = peak = dd = 0.0
    for b in sorted(placed, key=lambda b: b["cluster"]):
        bank += (learn.dec_odds(b["odds"]) - 1) if b["won"] else -1
        peak = max(peak, bank)
        dd = max(dd, peak - bank)
    res["max_drawdown_units"] = round(dd, 1)
    kinds = {}
    for b in placed:
        if b.get("kind"):
            kinds[b["kind"]] = kinds.get(b["kind"], 0) + 1
    if kinds:
        res["by_kind"] = kinds
    clv = [b["pc"] * learn.dec_odds(b["odds"]) - 1 for b in placed if b.get("pc") is not None]
    if clv:
        lo, hi = learn.bootstrap(lambda idx: sum(clv[i] for i in idx) / len(idx), len(clv), reps=800)
        res["clv"] = {"mean": round(sum(clv) / len(clv), 4), "ci": [round(lo, 4), round(hi, 4)],
                      "beat_close": round(sum(1 for v in clv if v > 0) / len(clv), 3)}
    return res


def shuffle_pct(rows, preds, fits, anchor, form, which, observed, reps=100, seed=9):
    """Percentile of the observed ROI among ROIs with the model's predictions shuffled within each year,
    using each year's own stacker.  ~50 would mean the model's information doesn't matter."""
    if observed is None or not fits:
        return None
    key = ANCHOR_KEY[anchor]
    coef_by_year = dict(fits)
    yrs = {}
    for r in rows:
        if r["id"] in preds and market_p(r, key) is not None and r["year"] in coef_by_year:
            yrs.setdefault(r["year"], []).append(r)
    rnd = random.Random(seed)
    beat = 0
    for _ in range(reps):
        fake = {}
        for yr, rr in yrs.items():
            ps = [preds[r["id"]] for r in rr]
            rnd.shuffle(ps)
            fake.update({r["id"]: p for r, p in zip(rr, ps)})
        bets = bets_for([r for rr in yrs.values() for r in rr],
                        lambda r: apply_stack(coef_by_year[r["year"]], r, fake[r["id"]], key, form), which)
        res = learn.backtest(bets, threshold=BET_EV, min_prob=BET_MIN_P, placebo=0)
        beat += (res.get("roi") if res.get("bets") else -1.0) < observed
    return round(100.0 * beat / reps, 1)


# ------------------------------------------------------------------ train/serve parity
def parity_check(ev, fi, fr, hist, params, rows, n_events=3):
    """The serving path (predict.side_profile) must reproduce training features for the latest events."""
    by_id = {r["id"]: r for r in rows}
    last = sorted((e for e in ev.values() if e.get("date")), key=lambda e: e["date"])[-n_events:]
    worst, checked = 0.0, 0
    for e in last:
        eng = engine.Engine(params).replay(ev, fi, until=e["date"])
        st = {"engine": eng, "fighters": fr}
        day = engine.parse_day(e["date"])
        for fid in e.get("fights", []):
            r = by_id.get(fid)
            if not r:
                continue
            sides = []
            for uid in (r["a"], r["b"]):
                h = hist.get(uid)
                P, _, _ = predict.side_profile(st, uid, {"ufcstats_id": uid, "espn_hist": h["hist"] if h else None}, day, r["div"])
                sides.append(P)
            x = win_features(*sides)
            worst = max(worst, max(abs(x[k] - r["x"][k]) for k in x))
            checked += 1
    return {"fights": checked, "max_abs_diff": worst}


# ------------------------------------------------------------------ main
def main():
    t0 = time.time()
    ev, fi, fr = scrape.load_dataset()
    hist = espn_hist.load()
    print(f"tuning rating settings on {TUNE_YEARS[0]}-{TUNE_YEARS[-1]}")
    params = tune_engine(ev, fi, fr, hist)
    print("engine params:", params)
    rows, eng, _ = dataset.build_rows(ev, fi, fr, engine_params=params, espn_histories=hist)
    last_date = max(r["date"] for r in rows)
    global TEST_YEARS, OOS_YEARS
    TEST_YEARS = list(range(2021, int(last_date[:4]) + 1))
    OOS_YEARS = TUNE_YEARS + VAL_YEARS + TEST_YEARS
    mk = market_hist.join(fi, odds_history.load())
    for r in rows:
        if r["id"] in mk:
            r["mkt"] = mk[r["id"]]
    print(f"{len(rows)} fights through {last_date}; market history for {sum('mkt' in r for r in rows)}")
    report = {"built": time.strftime("%Y-%m-%d"), "trained_through": last_date, "fights": len(rows),
              "windows": {"tune": [TUNE_YEARS[0], TUNE_YEARS[-1]], "val": [VAL_YEARS[0], VAL_YEARS[-1]],
                          "test": [TEST_YEARS[0], int(last_date[:4])]}}

    # 1. regularization, chosen on TUNE only
    grid = {}
    for C in (0.0003, 0.001, 0.003, 0.01, 0.03, 0.1):
        p = walk_forward(rows, WIN_FEATURES, C, TUNE_YEARS)
        te = [r for r in rows if r["id"] in p]
        grid[C] = learn.log_loss([p[r["id"]] for r in te], [r["y"] for r in te])
        print(f"  tune C={C:<6} log loss {grid[C]:.4f}")
    C = min(grid, key=grid.get)
    report["C"] = C

    # 2. out-of-sample predictions 2010+, with a calibration scale fitted for each year on earlier years
    raw = walk_forward(rows, WIN_FEATURES, C, OOS_YEARS)
    by_year = {}
    for r in rows:
        if r["id"] in raw:
            by_year.setdefault(r["year"], []).append(r)

    def fit_scale(rs):
        z = np.array([logit(raw[r["id"]]) for r in rs])
        yy = np.array([r["y"] for r in rs])
        m = LogisticRegression(C=100.0, fit_intercept=False).fit(np.concatenate([z, -z])[:, None], np.concatenate([yy, 1 - yy]))
        return float(m.coef_[0][0])
    preds = {}
    for Y in sorted(by_year):
        past = [r for yr in by_year if yr < Y for r in by_year[yr]]
        a = fit_scale(past) if len(past) >= 300 else 1.0
        for r in by_year[Y]:
            preds[r["id"]] = sig(a * logit(raw[r["id"]]))
    elo_preds = walk_forward(rows, ["elo"], 1.0, OOS_YEARS)
    gbm = gbm_challenger(rows, VAL_YEARS)

    def window(years):
        return [r for r in rows if r["id"] in preds and r["year"] in years]
    val, test = window(VAL_YEARS), window(TEST_YEARS)
    ev_rep = {}
    for name, rs in (("val", val), ("test", test)):
        y = [r["y"] for r in rs]
        withm = [r for r in rs if market_p(r, "close_fair") is not None and market_p(r, "open_fair") is not None]
        ym = [r["y"] for r in withm]
        e_ = [r for r in rs if r["id"] in elo_preds]
        ev_rep[name] = {
            "years": f"{min(r['year'] for r in rs)}-{max(r['year'] for r in rs)}",
            "model": metrics([preds[r["id"]] for r in rs], y),
            "model_uncalibrated": metrics([raw[r["id"]] for r in rs], y),
            "elo_only": metrics([elo_preds[r["id"]] for r in e_], [r["y"] for r in e_]),
            "with_market": {
                "model": metrics([preds[r["id"]] for r in withm], ym),
                "market_open": metrics([market_p(r, "open_fair") for r in withm], ym),
                "market_close": metrics([market_p(r, "close_fair") for r in withm], ym),
                "model_minus_open": cluster_ci(withm, dll(lambda r: preds[r["id"]], lambda r: market_p(r, "open_fair"))),
                "model_minus_close": cluster_ci(withm, dll(lambda r: preds[r["id"]], lambda r: market_p(r, "close_fair"))),
            },
            "calibration": [list(row) for row in learn.calibration([preds[r["id"]] for r in rs], y)],
        }
    if gbm:
        g = [r for r in val if r["id"] in gbm]
        ev_rep["val"]["gbm_challenger"] = metrics([gbm[r["id"]] for r in g], [r["y"] for r in g])
        ev_rep["val"]["logistic_same_fights"] = metrics([preds[r["id"]] for r in g], [r["y"] for r in g])
    report["evaluation"] = ev_rep
    print(json.dumps({k: {kk: vv for kk, vv in v.items() if kk != "calibration"} for k, v in ev_rep.items()}, indent=1))

    # 3. market-centred stackers per anchor, walk-forward from 2016; gate decided on VAL, confirmed on TEST
    stack, stack_preds = {}, {}
    for anchor, key in ANCHOR_KEY.items():
        have = [r for r in rows if r["id"] in preds and market_p(r, key) is not None]
        res = {}
        for form in ("S1", "S2"):
            sp, fits = {}, []
            for Y in VAL_YEARS + TEST_YEARS:
                tr = [r for r in have if r["year"] < Y]
                te = [r for r in have if r["year"] == Y]
                if len(tr) < 300 or not te:
                    continue
                coef = fit_stack(tr, preds, key, form)
                fits.append((Y, [round(c, 4) for c in coef]))
                sp.update({r["id"]: apply_stack(coef, r, preds[r["id"]], key, form) for r in te})
            res[form] = {"preds": sp, "fits": fits}
        hv = [r for r in have if r["year"] in VAL_YEARS]
        ht = [r for r in have if r["year"] in TEST_YEARS]
        s2_vs_s1 = cluster_ci(hv, dll(lambda r: res["S2"]["preds"][r["id"]], lambda r: res["S1"]["preds"][r["id"]]))
        alpha_pos = sum(1 for yr, c in res["S2"]["fits"] if yr in VAL_YEARS and c[2] > 0)
        form = "S2" if s2_vs_s1["ci"][1] < 0 and (alpha_pos >= 4 or alpha_pos <= 1) else "S1"
        sp = res[form]["preds"]
        val_dll = cluster_ci(hv, dll(lambda r: sp[r["id"]], lambda r: market_p(r, key)))
        test_dll = cluster_ci(ht, dll(lambda r: sp[r["id"]], lambda r: market_p(r, key)))
        gate = val_dll["ci"][1] < 0 and test_dll["est"] <= 0
        enc = {name: cluster_ci(rs, lambda s: fit_stack(s, preds, key, "S1")[0] if s else None, reps=200)
               for name, rs in (("val", hv), ("test", ht))}
        final = fit_stack(have, preds, key, form) if gate else [0.0] * (3 if form == "S2" else 2)
        stack[anchor] = {"form": form, "coef": final, "gate": gate, "val_minus_market": val_dll, "test_minus_market": test_dll,
                         "val_s2_minus_s1": s2_vs_s1, "model_weight_b": enc, "fits_by_year": res[form]["fits"],
                         "fights": len(have),
                         "val_metrics": metrics([sp[r["id"]] for r in hv], [r["y"] for r in hv]),
                         "test_metrics": metrics([sp[r["id"]] for r in ht], [r["y"] for r in ht]),
                         "market_val_metrics": metrics([market_p(r, key) for r in hv], [r["y"] for r in hv]),
                         "market_test_metrics": metrics([market_p(r, key) for r in ht], [r["y"] for r in ht])}
        stack_preds[anchor] = (sp, form, res[form]["fits"])
        print(anchor, json.dumps({k: v for k, v in stack[anchor].items() if k != "fits_by_year"}, indent=1))
    report["stack"] = stack

    # 4. betting backtests: one side per fight, pre-registered rule
    bt = {}
    scenarios = [
        ("open", "open", "open"),                  # P1: blend on the opening line, bet the opening price (upper bound)
        ("worst_close", "close", "worst"),         # P2: blend on the close, least generous closing price (Caesars proxy)
        ("synthetic_caesars", "close", "synth"),   # P3: closing fair price re-vigged to a 4.4% Caesars-like margin
        ("best_close", "close", "best"),           # P4: line-shopping ceiling, not attainable at one book
    ]
    for name, rs in (("val", val), ("test", test)):
        rs_m = [r for r in rs if r.get("mkt")]
        out = {}
        for label, anchor, which in scenarios:
            sp, form, fits = stack_preds[anchor]
            blend = run_backtest(bets_for(rs_m, lambda r: sp.get(r["id"]), which))
            blend["placebo_shuffle_pct"] = shuffle_pct(rs_m, preds, fits, anchor, form, which, blend.get("roi"))
            out[label] = {"gate_open": stack[anchor]["gate"], "blend": blend,
                          "raw_model": run_backtest(bets_for(rs_m, lambda r: preds.get(r["id"]), which))}
        out["sanity_market_at_worst_close"] = run_backtest(bets_for(rs_m, lambda r: market_p(r, "close_fair"), "worst"))
        # the rule the app actually applies (modelapi.decide): 4+ days out, blend bets for fighters with 2+
        # UFC fights, tested at opening prices; in fight week, market value only.  No Caesars history
        # exists, so fight-week market value is tested at the best price across books (a ceiling).
        # Variants show what the filters do; the rule was chosen on VAL.
        sp_o, sp_c = stack_preds["open"][0], stack_preds["close"][0]
        for r in rs_m:
            r["_pmodel"] = preds.get(r["id"])
        bo, bc = (lambda r: sp_o.get(r["id"])), (lambda r: sp_c.get(r["id"]))
        out["served_rule"] = {
            "early_open": run_backtest(rule_bets(rs_m, bo, "open_fair", "open", blend_bets=True)),
            "early_open_any_experience": run_backtest(rule_bets(rs_m, bo, "open_fair", "open", blend_bets=True, min_fights=0)),
            "early_open_gap15": run_backtest(rule_bets(rs_m, bo, "open_fair", "open", blend_bets=True, max_gap=0.15)),
            "fight_week_best": run_backtest(rule_bets(rs_m, bc, "close_fair", "best", blend_bets=False)),
            "fight_week_blend_synthetic": run_backtest(rule_bets(rs_m, bc, "close_fair", "synth", blend_bets=True)),
        }
        sp = stack_preds["close"][0]
        for h in (0.03, 0.06):
            out[f"synthetic_caesars_hold_{h}"] = run_backtest(bets_for(rs_m, lambda r: sp.get(r["id"]), "synth", hold=h))
        bt[name] = out
    report["backtest"] = bt
    for name in bt:
        for k, v in bt[name].items():
            if k == "served_rule":
                for kk, b in v.items():
                    print(f"  {name:4s} rule:{kk:16s} {b.get('bets')} bets ROI {b.get('roi')} {b.get('roi_ci')} "
                          f"CLV {(b.get('clv') or {}).get('mean')} kinds {b.get('by_kind')}")
            elif "blend" in v:
                b, rm = v["blend"], v["raw_model"]
                print(f"  {name:4s} {k:18s} blend {b.get('bets')} bets ROI {b.get('roi')} {b.get('roi_ci')} "
                      f"CLV {(b.get('clv') or {}).get('mean')} shuffle {b.get('placebo_shuffle_pct')} | raw {rm.get('bets')} ROI {rm.get('roi')}")
            else:
                print(f"  {name:4s} {k:18s} {v.get('bets')} bets ROI {v.get('roi')} {v.get('roi_ci')}")

    if os.environ.get("TRAIN_DUMP"):   # intermediate predictions for offline analysis
        import pickle
        with open(os.environ["TRAIN_DUMP"], "wb") as f:
            pickle.dump({"rows": rows, "preds": preds, "stack_preds": {k: v[0] for k, v in stack_preds.items()}}, f)

    # 5. method model: checked on VAL/TEST, then fitted on everything
    mrows = method_rows(rows)
    mm_tr = [m for m in mrows if TRAIN_FROM <= m[2]["year"] < VAL_YEARS[0]]
    mm = fit_method(mm_tr)
    base = [sum(1 for m in mm_tr if m[1] == k) / len(mm_tr) for k in range(3)]
    meth = {}
    for name, yrs in (("val", VAL_YEARS), ("test", TEST_YEARS)):
        te = [m for m in mrows if m[2]["year"] in yrs]
        meth[name] = {"fights": len(te),
                      "log_loss": round(-sum(math.log(max(1e-9, method_predict(mm, x)[c])) for x, c, _ in te) / len(te), 4),
                      "base_rate_log_loss": round(-sum(math.log(max(1e-9, base[c])) for _, c, _ in te) / len(te), 4)}
    meth["base_rates"] = dict(zip(METHODS, [round(b, 3) for b in base]))
    # the whole outcome table (finish round / distance), with round shapes fitted before VAL only and the
    # win chance from the closing-line blend, as the props table uses it
    oc_tr = outcome_params([r for r in rows if TRAIN_FROM <= r["year"] < VAL_YEARS[0]], fi)
    meth["outcome_val"] = outcome_eval(rows, dict(mm, outcome=oc_tr), preds, stack_preds["close"][0], VAL_YEARS)
    meth["outcome_test"] = outcome_eval(rows, dict(mm, outcome=oc_tr), preds, stack_preds["close"][0], TEST_YEARS)
    report["method_eval"] = meth
    print("method", meth)

    # 6. train/serve parity on the latest events
    report["parity"] = parity_check(ev, fi, fr, hist, params, rows)
    print("parity", report["parity"])

    # 7. final fits on everything and export
    final_rows = [r for r in rows if r["year"] >= TRAIN_FROM and r["y"] is not None]
    win = fit_win(final_rows, WIN_FEATURES, C)
    a_final = fit_scale([r for yr in by_year for r in by_year[yr]])
    win["calibration_scale"] = a_final
    win["coef"] = [c * a_final for c in win["coef"]]
    method = fit_method([m for m in mrows if m[2]["year"] >= TRAIN_FROM])
    method["outcome"] = outcome_params([r for r in rows if r["year"] >= 2001], fi)
    model = dict(report, engine=dict(eng.p), win=win, method=method,
                 description="Logistic model on point-in-time differences (Elo and dominance ratings, experience, record outside the UFC, "
                             "age, reach, striking/grappling rates, durability, form); market-centred blend gated on validation years; "
                             "method of victory from a multinomial model; finish rounds from method-specific hazards.")
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(model, f, indent=1)
    print(f"wrote {OUT} in {time.time() - t0:.0f}s")
    return model


if __name__ == "__main__":
    main()
