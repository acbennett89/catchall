"""Backtest the +2 network on the 2025 season.

For every target week w (5..16), the network is built from games played
before w, and each FBS-vs-FBS game in week w is "predicted" from the teams'
network strengths. A weight set is better when its strengths separate
winners from losers better (lower log loss).

    P(home wins) = logistic(k * (NS_home - NS_away) + c * home_field)

k and c are fitted once per weight set across all predictions, so each
weight set is judged by the information it carries, not by its scale.

    python backtest.py            -> writes out/backtest_network.json
"""
import json
import math
import os

from network import Network
from ratings import load

HERE = os.path.dirname(os.path.abspath(__file__))
BASE = json.load(open(os.path.join(HERE, "config.json")))


def logistic_fit(X, y, iters=50, ridge=1e-6):
    """Newton-Raphson logistic regression without intercept. Returns (beta, logloss, acc)."""
    n, k = len(X), len(X[0])
    beta = [0.0] * k
    for _ in range(iters):
        g = [0.0] * k
        H = [[ridge if i == j else 0.0 for j in range(k)] for i in range(k)]
        for xi, yi in zip(X, y):
            z = sum(b * x for b, x in zip(beta, xi))
            p = 1 / (1 + math.exp(-max(-30, min(30, z))))
            for i in range(k):
                g[i] += (yi - p) * xi[i]
                for j in range(k):
                    H[i][j] += p * (1 - p) * xi[i] * xi[j]
        step = solve(H, g)
        beta = [b + s for b, s in zip(beta, step)]
        if max(abs(s) for s in step) < 1e-10:
            break
    ll, hit = 0.0, 0
    for xi, yi in zip(X, y):
        z = sum(b * x for b, x in zip(beta, xi))
        p = min(max(1 / (1 + math.exp(-max(-30, min(30, z)))), 1e-12), 1 - 1e-12)
        ll -= yi * math.log(p) + (1 - yi) * math.log(1 - p)
        hit += (p > 0.5) == bool(yi)
    return beta, ll / n, hit / n


def solve(A, b):
    n = len(b)
    M = [row[:] + [b[i]] for i, row in enumerate(A)]
    for c in range(n):
        piv = max(range(c, n), key=lambda r: abs(M[r][c]))
        M[c], M[piv] = M[piv], M[c]
        for r in range(n):
            if r != c and M[c][c]:
                f = M[r][c] / M[c][c]
                M[r] = [a - f * bb for a, bb in zip(M[r], M[c])]
    return [M[i][n] / M[i][i] if M[i][i] else 0.0 for i in range(n)]


def collect(games, teams, cfg, min_prior_games):
    """Layer components (P, S, T) for both teams of every predictable game."""
    fbs = {t for t, v in teams.items() if v["division"] == "FBS"}
    rows = []
    for w in range(5, 17):
        train = [g for g in games if g["week"] < w and g["d1"]]
        test = [g for g in games if g["week"] == w and g["home"] in fbs and g["away"] in fbs]
        if not test:
            continue
        played = {}
        for g in train:
            for t in (g["home"], g["away"]):
                played[t] = played.get(t, 0) + 1
        net = Network(train, teams, cfg)
        for g in test:
            if min(played.get(g["home"], 0), played.get(g["away"], 0)) < min_prior_games:
                continue
            h, a = net.strength(g["home"]), net.strength(g["away"])
            rows.append({"week": w, "home": (h["P"], h["S"], h["T"]),
                         "away": (a["P"], a["S"], a["T"]),
                         "hfa": 0 if g["neutral"] else 1,
                         "y": int(g["home_pts"] > g["away_pts"])})
    return rows


def grid(step=0.05):
    n = round(1 / step)
    for i in range(n + 1):
        for j in range(n + 1 - i):
            yield round(i * step, 4), round(j * step, 4), round(1 - (i + j) * step, 4)


def evaluate(rows, weights):
    wP, wS, wT = weights
    X = [[wP * (r["home"][0] - r["away"][0]) + wS * (r["home"][1] - r["away"][1])
          + wT * (r["home"][2] - r["away"][2]), r["hfa"]] for r in rows]
    y = [r["y"] for r in rows]
    beta, ll, acc = logistic_fit(X, y)
    return {"weights": weights, "logloss": ll, "accuracy": acc, "k": beta[0], "home": beta[1],
            "_per_game": per_game_loss(X, y, beta)}


def per_game_loss(X, y, beta):
    out = []
    for xi, yi in zip(X, y):
        z = sum(b * x for b, x in zip(beta, xi))
        p = min(max(1 / (1 + math.exp(-max(-30, min(30, z)))), 1e-12), 1 - 1e-12)
        out.append(-(yi * math.log(p) + (1 - yi) * math.log(1 - p)))
    return out


def paired(a, b):
    """Mean log-loss difference (a - b) per game and its standard error."""
    d = [x - y for x, y in zip(a, b)]
    m = sum(d) / len(d)
    sd = math.sqrt(sum((x - m) ** 2 for x in d) / (len(d) - 1))
    return {"diff": m, "se": sd / math.sqrt(len(d)), "z": m / (sd / math.sqrt(len(d))) if sd else 0.0}


def free_fit(rows):
    X = [[r["home"][i] - r["away"][i] for i in range(3)] + [r["hfa"]] for r in rows]
    y = [r["y"] for r in rows]
    beta, ll, acc = logistic_fit(X, y)
    return {"coef_P_S_T_home": beta, "logloss": ll, "accuracy": acc,
            "_per_game": per_game_loss(X, y, beta)}


def strip(d):
    return {k: v for k, v in d.items() if not k.startswith("_")}


def main():
    d = load(2025)  # regular season only, as the ratings use it
    games, teams = d["games"], d["teams"]
    variants = {
        "default: rates, Laplace 1-1, FCS losses count, path exclusion": {},
        "parent-only exclusion (RPI convention)": {"exclusion": "parent"},
        "no exclusions beyond removing A": {"exclusion": "none"},
        "raw win counts summed (literal 'wins')": {"layer_mode": "count"},
        "no Laplace prior": {"record_prior": {"wins": 0, "losses": 0}},
        "FCS losses ignored": {"fcs_losses_count": False},
    }
    named = {"P only (win% alone)": (1.0, 0.0, 0.0),
             "0.50/0.30/0.20 (provisional)": (0.5, 0.3, 0.2),
             "4:2:1 halving": (4 / 7, 2 / 7, 1 / 7),
             "0.60/0.30/0.10": (0.6, 0.3, 0.1),
             "RPI-like 2:1, no tertiary": (2 / 3, 1 / 3, 0.0),
             "equal thirds": (1 / 3, 1 / 3, 1 / 3)}
    report = {"season": 2025, "note": __doc__, "thresholds": {}}
    for min_prior in (3, 5):
        block = {"variants": {}, "comparisons": {}}
        per = {}
        for name, override in variants.items():
            cfg = {**BASE, **override}
            rows = collect(games, teams, cfg, min_prior)
            ff = free_fit(rows)
            entry = {"n_games": len(rows), "free_fit": strip(ff),
                     "home_only_logloss": logistic_fit([[r["hfa"]] for r in rows],
                                                       [r["y"] for r in rows])[1]}
            per[name] = {"free": ff["_per_game"]}
            if cfg.get("layer_mode", "rate") == "rate":
                results = [evaluate(rows, w) for w in grid()]
                results.sort(key=lambda r: r["logloss"])
                mono = [r for r in results if r["weights"][0] >= r["weights"][1] >= r["weights"][2]]
                entry["best_any"] = strip(results[0])
                entry["best_monotone"] = strip(mono[0])
                entry["top10_monotone"] = [strip(r) for r in mono[:10]]
                entry["all_monotone"] = [(r["weights"], round(r["logloss"], 5)) for r in mono]
                ev = {k: evaluate(rows, w) for k, w in named.items()}
                entry["named"] = {k: strip(v) for k, v in ev.items()}
                per[name].update({k: v["_per_game"] for k, v in ev.items()})
                per[name]["best_monotone"] = mono[0]["_per_game"]
            block["variants"][name] = entry
            print(f"[min {min_prior}] {name}: n={entry['n_games']} free LL={ff['logloss']:.4f} "
                  f"coef={[round(c, 2) for c in ff['coef_P_S_T_home']]}"
                  + (f" | best mono {entry['best_monotone']['weights']} "
                     f"LL={entry['best_monotone']['logloss']:.4f}" if "best_monotone" in entry else ""))
        dflt = "default: rates, Laplace 1-1, FCS losses count, path exclusion"
        cmp = block["comparisons"]
        cmp["provisional 0.5/0.3/0.2 minus best monotone"] = paired(
            per[dflt]["0.50/0.30/0.20 (provisional)"], per[dflt]["best_monotone"])
        cmp["0.6/0.3/0.1 minus best monotone"] = paired(
            per[dflt]["0.60/0.30/0.10"], per[dflt]["best_monotone"])
        cmp["P only minus best monotone"] = paired(
            per[dflt]["P only (win% alone)"], per[dflt]["best_monotone"])
        for name in variants:
            if name != dflt:
                cmp[f"free fit: '{name}' minus default"] = paired(per[name]["free"], per[dflt]["free"])
        for k, v in cmp.items():
            print(f"    {k}: {v['diff']:+.4f} (se {v['se']:.4f}, z {v['z']:+.2f})")
        report["thresholds"][f"both teams >= {min_prior} prior D-I games"] = block
    os.makedirs(os.path.join(HERE, "out"), exist_ok=True)
    with open(os.path.join(HERE, "out", "backtest_network.json"), "w") as f:
        json.dump(report, f, indent=1)




def resume_backtest(games, teams, cfg):
    """Should losses count? Compare resume variants as predictors of later games.

    Each week, every team's resume is computed from earlier games; the next
    week's FBS-vs-FBS winners are predicted from the difference. Resume
    metrics aren't built to predict, but a resume that ignores losses
    should not carry *less* information about team quality than one that
    counts them -- if it does, ignoring losses is discarding signal.
    """
    fbs = {t for t, v in teams.items() if v["division"] == "FBS"}
    feats = {"win value total (losses ignored)": lambda r, n: r["win_value_total"],
             "net resume (wins - loss costs)": lambda r, n: r["net_resume"],
             "win value per game": lambda r, n: r["win_value_total"] / n,
             "net resume per game": lambda r, n: r["net_resume"] / n}
    X = {k: [] for k in feats}
    y = []
    for w in range(5, 17):
        train = [g for g in games if g["week"] < w and g["d1"]]
        test = [g for g in games if g["week"] == w and g["home"] in fbs and g["away"] in fbs]
        played = {}
        for g in train:
            for t in (g["home"], g["away"]):
                played[t] = played.get(t, 0) + 1
        net = Network(train, teams, cfg)
        cache = {}
        for g in test:
            if min(played.get(g["home"], 0), played.get(g["away"], 0)) < 3:
                continue
            for t in (g["home"], g["away"]):
                if t not in cache:
                    cache[t] = net.resume(t, with_trees=False)
            for k, fn in feats.items():
                X[k].append([fn(cache[g["home"]], played[g["home"]])
                             - fn(cache[g["away"]], played[g["away"]]), 0 if g["neutral"] else 1])
            y.append(int(g["home_pts"] > g["away_pts"]))
    out = {"n_games": len(y)}
    per = {}
    for k in feats:
        beta, ll, acc = logistic_fit(X[k], y)
        out[k] = {"logloss": ll, "accuracy": acc}
        per[k] = per_game_loss(X[k], y, beta)
    out["comparisons"] = {
        "net total minus win-only total": paired(per["net resume (wins - loss costs)"],
                                                 per["win value total (losses ignored)"]),
        "net per game minus win-only per game": paired(per["net resume per game"],
                                                       per["win value per game"]),
    }
    return out


def run_resume_backtest():
    d = load(2025)  # regular season only, as the ratings use it
    out = resume_backtest(d["games"], d["teams"], BASE)
    for k, v in out.items():
        print(k, v)
    with open(os.path.join(HERE, "out", "backtest_resume.json"), "w") as f:
        json.dump(out, f, indent=1)


if __name__ == "__main__":
    main()
    run_resume_backtest()
