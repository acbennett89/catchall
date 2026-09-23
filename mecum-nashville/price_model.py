"""Class-aware comp pricing over the classified corpus, plus a backtest against the current method.

    python price_model.py backtest      tune on Glendale/Houston/Indy/Tulsa, validate on Harrisburg/Monterey/Nashville
    import price_model; price_model.estimate(lot, auction_start)   -> dict for the page

Every comp gets a weight = how alike it is (generation, trim, body, modifications, engine, transmission,
grade, mileage) x how recent. Expected = weighted median; range = weighted 25th-75th percentile.
Only sales that ended before the auction being priced are ever used."""
import json, math, os, sys, statistics, collections, time

HERE = os.path.dirname(os.path.abspath(__file__))
TAX = json.load(open(os.path.join(HERE, "taxonomy.json"), encoding="utf-8"))
HAS_GEN = set(TAX["generations"])
GRADE_RANK = {"General": 0, "none": 1, "star": 1, "Feature": 2, "Main attraction": 3}
YEAR = 365.25 * 86400

DEFAULTS = dict(lookback=5, half_life=2.0, year_decay=0.35, trim_none_vs_some=0.2, trim_disjoint=0.05,
                mod_mismatch=0.08, body_group_same=0.7, body_group_diff=0.25, body_unknown=0.7,
                ci_near=0.7, ci_far=0.4, trans_diff=0.75, grade_step=0.3, miles_k=0.6, general_p25=False)

_by_family = None


def load(path=os.path.join(HERE, "classified.jsonl")):
    global _by_family
    fam = collections.defaultdict(list)
    # comp odometers: Mecum's powertrain line first, else the scraped lot page (km converted to miles)
    op = os.path.join(HERE, "odo_cache.json")
    odo = json.load(open(op)) if os.path.exists(op) else {}
    for line in open(path, encoding="utf-8"):
        r = json.loads(line)
        if r["sold"] and r["price"] and r["end"]:
            if not r.get("miles"):
                o = odo.get(r["id"]) or {}
                if o.get("mi"): r["miles"] = round(o["mi"] * (0.621 if o.get("u") == "K" else 1))
            r["_tt"] = frozenset(r["trim_tokens"]); fam[r["family"]].append(r)
    _by_family = fam
    return fam


def wquant(pairs, q):
    tot = sum(w for _, w in pairs); acc = 0
    for p, w in pairs:
        acc += w
        if acc >= q * tot: return p
    return pairs[-1][0]


def weight(t, c, P, start):
    w = 0.5 ** ((start - c["end"]) / YEAR / P["half_life"])
    if t["year"] and c["year"]: w *= math.exp(-abs(t["year"] - c["year"]) * P["year_decay"])
    a, b = t["_tt"], c["_tt"]
    if a != b:
        if not a or not b: w *= P["trim_none_vs_some"]
        else:
            j = len(a & b) / len(a | b)
            w *= P["trim_disjoint"] if j == 0 else 0.25 + 0.75 * j
    if t["mod"] != c["mod"]: w *= P["mod_mismatch"]
    if t["body_group"] and c["body_group"]:
        if t["body"] != c["body"]: w *= P["body_group_same"] if t["body_group"] == c["body_group"] else P["body_group_diff"]
    elif t["body_group"] or c["body_group"]: w *= P["body_unknown"]
    if t["ci"] and c["ci"]:
        r = abs(t["ci"] - c["ci"]) / max(t["ci"], c["ci"])
        if r > 0.05: w *= P["ci_near"] if r <= 0.15 else P["ci_far"]
    if t["trans"] and c["trans"] and t["trans"] != c["trans"]: w *= P["trans_diff"]
    if t.get("drive") and c.get("drive") and t["drive"] != c["drive"]: w *= P.get("drive_diff", 0.55)
    d = abs(GRADE_RANK.get(t["grade"], 1) - GRADE_RANK.get(c["grade"], 1))
    if d: w *= (1 - P["grade_step"]) ** d
    if (t["year"] or 0) >= 1985 and t.get("miles"):
        if c.get("miles"): w *= math.exp(-P["miles_k"] * abs(math.log(max(t["miles"], 50) / max(c["miles"], 50))))
        else: w *= P.get("miles_unknown", 1.0)   # modern comp of unknown mileage is a weaker match
    return w


def estimate(t, start, P=DEFAULTS, fam=None):
    fam = fam or _by_family
    if "_tt" not in t: t = {**t, "_tt": frozenset(t.get("trim_tokens") or [])}
    pool = fam.get(t["family"], [])
    tiers = []
    # a real generation label (not a bare year, which means the car fell outside every documented generation)
    if t.get("gen") and not str(t["gen"]).isdigit(): tiers.append(("same generation", lambda c: c["gen"] == t["gen"], P["lookback"]))
    else: tiers.append(("within 3 model years", lambda c: t["year"] and c["year"] and abs(c["year"] - t["year"]) <= 3, P["lookback"]))
    tiers.append(("within 6 model years", lambda c: t["year"] and c["year"] and abs(c["year"] - t["year"]) <= 6, P["lookback"]))
    tiers.append(("within 6 model years, 10-year lookback", lambda c: t["year"] and c["year"] and abs(c["year"] - t["year"]) <= 6, 10))
    for label, keep, look in tiers:
        lo_t = start - look * YEAR
        cs = [(c, weight(t, c, P, start)) for c in pool if lo_t <= c["end"] < start and c["id"] != t["id"] and keep(c)]
        cs = [(c, w) for c, w in cs if w > 1e-4]
        if not cs: continue
        sw = sum(w for _, w in cs); eff = sw * sw / sum(w * w for _, w in cs)
        if eff < 3 and label != tiers[-1][0]: continue
        pairs = sorted(((c["price"], w) for c, w in cs), key=lambda x: x[0])
        med, p25, p75 = wquant(pairs, .5), wquant(pairs, .25), wquant(pairs, .75)
        exp_ = p25 if P["general_p25"] and t["grade"] == "General" else med
        top = sorted(cs, key=lambda x: -x[1])[:8]
        # whiskers: weighted 10th-90th percentile, not min/max — with hundreds of comps one far-off car would set the scale
        return {"median": round(exp_), "p25": round(p25), "p75": round(p75), "lo": round(wquant(pairs, .10)), "hi": round(wquant(pairs, .90)), "n": len(cs), "eff": round(eff, 1),
                "tier": f"{label} · {len(cs)} comps, {eff:.0f} effective", "top": top}
    return None


# ---------------------------------------------------------------- backtest
TUNE = ["glendale-2026", "houston-2026", "indy-2026", "tulsa-2026"]
HOLD = ["harrisburg-2026", "monterey-2026", "nashville-2026"]


def test_lots(slugs, fam_rows):
    by_id = {}
    for rows in fam_rows.values():
        for r in rows: by_id[r["id"]] = r
    out = []
    for s in slugs:
        a = json.load(open(os.path.join(HERE, "data", s, "auction.json")))
        old = json.load(open(os.path.join(HERE, "data", s, "comps.json")))
        for lid, r in by_id.items():
            if r["auction"] == a["name"] and r["type"] == "Auto":
                o = old.get(lid) or {}
                out.append((r, a["start"], o.get("median") if o.get("n") else None, s))
    return out


def score(pairs):
    pairs = [(h, e) for h, e in pairs if e]
    a = [abs(h - e) / h for h, e in pairs]; s = [(h - e) / h for h, e in pairs]; lg = [abs(math.log(e / h)) for h, e in pairs]
    return {"n": len(pairs), "median_miss": statistics.median(a), "mean_miss": statistics.mean(a), "bias": statistics.median(s),
            "within_25pct": sum(1 for x in a if x <= .25) / len(a), "median_log": statistics.median(lg)}


def fmt(sc):
    return (f"n={sc['n']:5}  typical miss {sc['median_miss']:.0%}  mean miss {sc['mean_miss']:.0%}  bias {sc['bias']:+.0%}  "
            f"within ±25%: {sc['within_25pct']:.0%}")


def run(tests, P):
    new, old, both_new, both_old, inr = [], [], [], [], 0
    for r, start, o, _ in tests:
        e = estimate(r, start, P)
        if e:
            new.append((r["price"], e["median"])); inr += e["p25"] <= r["price"] <= e["p75"]
            if o: both_new.append((r["price"], e["median"])); both_old.append((r["price"], o))
        if o: old.append((r["price"], o))
    return score(both_new), score(both_old), score(new), inr / max(1, len(new))


if __name__ == "__main__" and sys.argv[1:2] == ["backtest"]:
    t0 = time.time(); fam = load(); print("loaded", sum(len(v) for v in fam.values()), "sold vehicles in", round(time.time() - t0), "s", flush=True)
    tune, hold = test_lots(TUNE, fam), test_lots(HOLD, fam)
    print("test lots: tune", len(tune), "holdout", len(hold), flush=True)
    variants = {
        "defaults": {},
        "3yr lookback": {"lookback": 3},
        "no grade weight": {"grade_step": 0.0},
        "strong grade": {"grade_step": 0.5},
        "general -> p25": {"general_p25": True},
        "strict trim": {"trim_none_vs_some": 0.08, "trim_disjoint": 0.02},
        "loose trim": {"trim_none_vs_some": 0.4, "trim_disjoint": 0.15},
        "faster recency": {"half_life": 1.0},
    }
    best = None
    for name, ov in variants.items():
        P = {**DEFAULTS, **ov}
        nb, ob, na, cov = run(tune, P)
        print(f"TUNE  {name:16} new: {fmt(nb)}  | range hit {cov:.0%}", flush=True)
        if best is None or nb["median_log"] < best[1]: best = (name, nb["median_log"], P)
    print(f"TUNE  {'current method':16} old: {fmt(ob)}")
    name, _, P = best
    nb, ob, na, cov = run(hold, P)
    print(f"\nHOLDOUT with '{name}':\n  new     {fmt(nb)}  | range hit {cov:.0%}\n  current {fmt(ob)}\n  new on all holdout lots (incl. ones current couldn't price): {fmt(na)}")
    json.dump({k: v for k, v in P.items()}, open(os.path.join(HERE, "model_params.json"), "w"), indent=1)
    print("saved model_params.json; done in", round(time.time() - t0), "s")
