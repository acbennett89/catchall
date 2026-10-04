"""Walk-forward validation of the efficiency ratings.

For each target week, ratings are fit on games from earlier weeks only, then
used to predict that week's games. Nothing from the target week leaks in.

Compared against:
  * raw (unadjusted) points-per-drive margin plus the same home-field edge
  * average scoring margin (points per game) plus home-field edge
  * the sportsbook line ESPN displays (a strong outside benchmark)

    python validate.py              -> out/validation.json
"""
import copy
import json
import math
import os

from ratings import HERE, load, load_config, predict, rate


def evaluate(season, weeks, cfg, label):
    data = load(season)
    fbs = {t for t, v in data["teams"].items() if v["division"] == "FBS"}
    rows = []
    for w in weeks:
        target = [g for g in data["games"] if g["week"] == w and g["d1"]
                  and (g["home"] in fbs or g["away"] in fbs)]
        if not target:
            continue
        res = rate(copy.deepcopy(data), cfg, through_week=w - 1)
        T, muT, h = res["teams"], res["muT"], res["ppd"]["h"]
        for g in target:
            p = predict(res, g["home"], g["away"], g["neutral"])
            if p is None:
                continue
            actual = g["home_pts"] - g["away_pts"]
            hfa = 0 if g["neutral"] else 2 * h * muT
            row = {"week": w, "game": g["id"], "actual": actual, "model": p["margin"],
                   "market": g.get("market_home_margin"),
                   "fbs_vs_fbs": g["home"] in fbs and g["away"] in fbs}
            th, ta = T.get(g["home"]), T.get(g["away"])
            if th and ta and th.get("PPD_O") is not None and ta.get("PPD_O") is not None \
                    and th["drives_O"] and ta["drives_O"]:
                raw_em = (th["PPD_O"] - th["PPD_D"]) - (ta["PPD_O"] - ta["PPD_D"])
                row["raw_ppd"] = raw_em * muT + hfa
                mov = lambda r: (r["PF"] - r["PA"]) / r["games"]
                row["avg_margin"] = (mov(th) - mov(ta)) / 2 + hfa
            rows.append(row)
    return summarize(rows, label)


def summarize(rows, label):
    out = {"label": label, "n": len(rows), "methods": {}}
    # Baselines exist only where both teams have raw stats (FBS vs FBS), so the
    # like-for-like comparison is on the games every method could predict.
    common = [r for r in rows if r.get("raw_ppd") is not None and r.get("avg_margin") is not None]
    out["same_games"] = {"n": len(common)}
    for m in ("model", "raw_ppd", "avg_margin"):
        if common:
            out["same_games"][m + "_MAE"] = sum(abs(r[m] - r["actual"]) for r in common) / len(common)
            out["same_games"][m + "_straight_up"] = sum(
                (r[m] > 0) == (r["actual"] > 0) for r in common if r[m] != 0) / len(common)
    for m in ("model", "raw_ppd", "avg_margin", "market"):
        sub = [r for r in rows if r.get(m) is not None]
        if not sub:
            continue
        err = [r[m] - r["actual"] for r in sub]
        decided = [r for r in sub if r[m] != 0]
        out["methods"][m] = {
            "n": len(sub),
            "MAE": sum(abs(e) for e in err) / len(err),
            "RMSE": math.sqrt(sum(e * e for e in err) / len(err)),
            "bias": sum(err) / len(err),
            "straight_up": sum((r[m] > 0) == (r["actual"] > 0) for r in decided) / len(decided),
        }
    both = [r for r in rows if r.get("market") is not None]
    if both:
        # head-to-head on the same games, model vs market
        out["same_games_vs_market"] = {
            "n": len(both),
            "model_MAE": sum(abs(r["model"] - r["actual"]) for r in both) / len(both),
            "market_MAE": sum(abs(r["market"] - r["actual"]) for r in both) / len(both),
            "model_minus_market_MAE_se": se_paired(
                [abs(r["model"] - r["actual"]) - abs(r["market"] - r["actual"]) for r in both]),
        }
    err = [r["model"] - r["actual"] for r in rows]
    out["sigma"] = math.sqrt(sum(e * e for e in err) / len(err)) if err else None
    out["calibration"] = calibration(rows, out["sigma"])
    return out


def se_paired(d):
    m = sum(d) / len(d)
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
    return {"mean": m, "se": sd / math.sqrt(len(d))}


def calibration(rows, sigma):
    if not sigma:
        return []
    bins = [(0.5, 0.6), (0.6, 0.7), (0.7, 0.8), (0.8, 0.9), (0.9, 1.01)]
    out = []
    for lo, hi in bins:
        sel = []
        for r in rows:
            p = 0.5 * (1 + math.erf(r["model"] / sigma / math.sqrt(2)))
            fav_p, fav_won = (p, r["actual"] > 0) if p >= 0.5 else (1 - p, r["actual"] < 0)
            if lo <= fav_p < hi:
                sel.append((fav_p, fav_won))
        if sel:
            out.append({"bin": f"{lo:.1f}-{min(hi, 1):.1f}", "n": len(sel),
                        "predicted": sum(p for p, _ in sel) / len(sel),
                        "actual": sum(w for _, w in sel) / len(sel)})
    return out


def main():
    base = load_config()
    report = {"efficiency_2025": {}, "holdout_2026": None}
    variants = {"default (prior 12 drives, garbage filter on)": {},
                "prior 0": {"prior_drives": 0, "prior_plays": 0},
                "prior 6": {"prior_drives": 6, "prior_plays": 32},
                "prior 24": {"prior_drives": 24, "prior_plays": 130},
                "garbage filter off": {"garbage_filter": False}}
    for name, ov in variants.items():
        cfg = {**base, **ov}
        r = evaluate(2025, range(4, 17), cfg, name)
        report["efficiency_2025"][name] = r
        mm, sg = r["methods"], r["same_games"]
        print(f"2025 {name}: n={r['n']} model MAE {mm['model']['MAE']:.2f} "
              f"SU {mm['model']['straight_up']:.3f} sigma {r['sigma']:.1f} | same {sg['n']} games: "
              f"model {sg['model_MAE']:.2f} raw PPD {sg['raw_ppd_MAE']:.2f} "
              f"avg margin {sg['avg_margin_MAE']:.2f} | market n={mm['market']['n']}")
    r = evaluate(2024, range(4, 17), base, "2024 default")
    report["efficiency_2024"] = {"default (prior 12 drives, garbage filter on)": r}
    mm, sg = r["methods"], r["same_games"]
    print(f"2024 default: n={r['n']} model MAE {mm['model']['MAE']:.2f} SU {mm['model']['straight_up']:.3f} "
          f"| same {sg['n']} games: model {sg['model_MAE']:.2f} raw PPD {sg['raw_ppd_MAE']:.2f} "
          f"avg margin {sg['avg_margin_MAE']:.2f}")
    h = evaluate(2026, range(3, 6), base, "2026 weeks 3-5 holdout (default)")
    report["holdout_2026"] = h
    mm, sg = h["methods"], h["same_games"]
    print(f"2026 holdout: n={h['n']} model MAE {mm['model']['MAE']:.2f} SU {mm['model']['straight_up']:.3f}"
          f" sigma {h['sigma']:.1f} | same {sg['n']} games: model {sg['model_MAE']:.2f} "
          f"raw {sg['raw_ppd_MAE']:.2f} avg margin {sg['avg_margin_MAE']:.2f} | vs market "
          f"{json.dumps(h.get('same_games_vs_market'))}")
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "validation.json"), "w") as f:
        json.dump(report, f, indent=1)


if __name__ == "__main__":
    main()
