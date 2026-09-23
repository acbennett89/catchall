"""Condition & provenance adjustment from a lot's own highlight bullets.

    python condition.py      learn multipliers on the tuning auctions, validate on the holdout -> condition_params.json

Comps can't see condition, but Mecum's highlights say it outright ("frame-off restoration", "NCRS Top Flight",
"numbers matching"). Each lot gets the multiplier of its strongest flag; flags are learned, not assumed."""
import json, os, re, statistics, sys, math
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)

FLAGS = {  # checked in this order; a lot takes its strongest learned flag
    "award": r"concours|ncrs|bloomington|top flight|gold award|best in class|award[- ]winning|\baward\b",
    "frame-off": r"frame[- ]off|rotisserie|body[- ]off|nut[- ]and[- ]bolt",
    "numbers matching": r"numbers[- ]matching|matching[- ]numbers",
    "documented": r"marti report|build sheet|window sticker|protect-o-plate|documented|documentation|fender tag|govier|elite marti",
    "low/actual miles": r"actual miles|one owner|single owner|original owner",
    "survivor": r"survivor|unrestored|original paint|all original|highly original",
    "restomod parts": r"\bls[1-9a]\b|coyote|crate|air ride|tremec|holley sniper|vintage air|fuel[- ]injection conversion",
    "project": r"non[- ]running|not running|barn find|sold as is|bill of sale only|project",
}


def flags(highlights):
    h = " ".join(highlights or []).lower()
    return [k for k, p in FLAGS.items() if re.search(p, h)]


def adjust(est, highlights, params):
    """Scale an estimate by the jointly-learned log effects of the lot's flags. Returns (est, [flags])."""
    fs = [f for f in flags(highlights) if f in params]
    if not fs or not est: return est, []
    m = math.exp(sum(math.log(params[f]) for f in fs))
    return {**est, "median": round(est["median"] * m), "p25": round(est["p25"] * m), "p75": round(est["p75"] * m)}, fs


def fit(data, lam):
    """Ridge regression of clipped log(price/estimate) on flag indicators (no intercept: unflagged lots stay at 1.0)."""
    keys = list(FLAGS); k = len(keys)
    X = [[1.0 if f in flags(h) else 0.0 for f in keys] for _, _, h in data]
    y = [max(-1.0, min(1.0, math.log(p / e["median"]))) for p, e, _ in data]
    # normal equations (X'X + lam I) b = X'y, solved by Gaussian elimination — 8 unknowns, no numpy needed
    A = [[sum(r[i] * r[j] for r in X) + (lam if i == j else 0) for j in range(k)] + [sum(r[i] * yy for r, yy in zip(X, y))] for i in range(k)]
    for c in range(k):
        piv = max(range(c, k), key=lambda i: abs(A[i][c])); A[c], A[piv] = A[piv], A[c]
        for i in range(k):
            if i != c and A[c][c]:
                f = A[i][c] / A[c][c]; A[i] = [a - f * b for a, b in zip(A[i], A[c])]
    beta = [A[i][k] / A[i][i] if A[i][i] else 0 for i in range(k)]
    counts = [sum(r[i] for r in X) for i in range(k)]
    return {f: round(math.exp(b), 3) for f, b, n in zip(keys, beta, counts) if n >= 25}


if __name__ == "__main__":
    import price_model as PM
    fam = PM.load(); P = {**PM.DEFAULTS, **json.load(open(os.path.join(HERE, "model_params.json")))}
    def lots(slugs):
        out = []
        for s in slugs:
            a = json.load(open(f"data/{s}/auction.json")); det = json.load(open(f"data/{s}/details.json"))
            for rows in fam.values():
                for r in rows:
                    if r["auction"] == a["name"] and r["type"] == "Auto":
                        t = dict(r); o = re.sub(r"[^\d]", "", (det.get(r["id"]) or {}).get("odometer") or "")
                        if o: t["miles"] = int(o)
                        e = PM.estimate(t, a["start"], P, fam)
                        if e: out.append((r["price"], e, (det.get(r["id"]) or {}).get("highlights") or []))
        return out
    tune, hold = lots(PM.TUNE), lots(PM.HOLD)
    print("tune", len(tune), "holdout", len(hold), flush=True)
    # pick the ridge strength by 4-fold cross-validation inside the tuning set only
    def cv(lam):
        errs = []
        for f in range(4):
            tr = [x for i, x in enumerate(tune) if i % 4 != f]; te = [x for i, x in enumerate(tune) if i % 4 == f]
            pr = fit(tr, lam)
            errs += [abs(math.log(p / adjust(e, h, pr)[0]["median"])) for p, e, h in te]
        return statistics.median(errs)
    lams = [1, 10, 30, 100, 300, 1000]
    scores = {l: cv(l) for l in lams}; print("CV median |log error| by ridge strength:", {l: round(s, 4) for l, s in scores.items()})
    params = fit(tune, min(scores, key=scores.get))
    print("learned multipliers (tune):", params)
    def ev(data, use):
        pairs = [(p, (adjust(e, h, params)[0] if use else e)["median"]) for p, e, h in data]
        return PM.fmt(PM.score(pairs))
    print("TUNE     without:", ev(tune, False)); print("TUNE     with:   ", ev(tune, True))
    print("HOLDOUT  without:", ev(hold, False)); print("HOLDOUT  with:   ", ev(hold, True))
    flagged = [(p, e, h) for p, e, h in hold if any(f in params for f in flags(h))]
    print(f"HOLDOUT flagged lots only ({len(flagged)}):\n   without:", ev(flagged, False), "\n   with:   ", ev(flagged, True))
    json.dump(params, open(os.path.join(HERE, "condition_params.json"), "w"), indent=1)
