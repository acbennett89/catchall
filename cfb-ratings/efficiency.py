"""Opponent-adjusted efficiency, KenPom-style, solved by iterative averaging.

Model for one team-game observation (team X on offense against team Y):

    y = AdjO[X] + AdjD[Y] - mu + h * v          (v = +1 home, -1 away, 0 neutral)

At the fixed point every rating is a plain weighted average of game lines,
so it can be checked by hand:

    AdjO[X] = ( sum_g w_g * (y_g - (AdjD[opp_g] - mu) - h*v_g) + r * prior ) / ( sum_g w_g + r )

where w is drives (or plays) and r * prior is one phantom game at the team's
division (FBS/FCS) average.
"""
from collections import defaultdict


def _mean(v):
    v = list(v)
    return sum(v) / len(v) if v else 0.0


def solve(obs, division, prior_weight, max_iter=500, tol=1e-9, use_hfa=True,
          fixed_h=None, center="FBS"):
    """obs: dicts with off, def, y (rate), w (weight), v (venue), game.

    fixed_h:  hold the home-field term at this value instead of estimating it.
    center:   division whose average team is the zero point. O and D are only
              identified up to a shared constant (O+c, D-c predict identical
              games); we pin mean(O - D) over this division's teams to 0, then
              shift O, D and mu together so the division's average defense
              equals mu. AdjO is then exactly "points per drive against an
              average FBS defense on a neutral field".
    """
    teams = {o["off"] for o in obs} | {o["def"] for o in obs}
    core = [o for o in obs if division[o["off"]] == center and division[o["def"]] == center] or obs
    mu = sum(o["w"] * o["y"] for o in core) / sum(o["w"] for o in core)
    centered = [t for t in teams if division[t] == center] or list(teams)
    by_off, by_def = defaultdict(list), defaultdict(list)
    for o in obs:
        by_off[o["off"]].append(o)
        by_def[o["def"]].append(o)
    divs = {division[t] for t in teams}
    O = {t: mu for t in teams}
    D = {t: mu for t in teams}
    h = fixed_h if fixed_h is not None else 0.0
    hv = sum(o["w"] * o["v"] ** 2 for o in obs)
    delta, it = float("inf"), 0
    for it in range(1, max_iter + 1):
        pO = {d: _mean(O[t] for t in teams if division[t] == d) for d in divs}
        newO = {}
        for t in teams:
            num = sum(o["w"] * (o["y"] - (D[o["def"]] - mu) - h * o["v"]) for o in by_off[t])
            den = sum(o["w"] for o in by_off[t])
            newO[t] = (num + prior_weight * pO[division[t]]) / (den + prior_weight)
        pD = {d: _mean(D[t] for t in teams if division[t] == d) for d in divs}
        newD = {}
        for t in teams:
            num = sum(o["w"] * (o["y"] - (newO[o["off"]] - mu) - h * o["v"]) for o in by_def[t])
            den = sum(o["w"] for o in by_def[t])
            newD[t] = (num + prior_weight * pD[division[t]]) / (den + prior_weight)
        newh = h
        if fixed_h is None:
            newh = 0.0
            if use_hfa and hv:
                newh = sum(o["w"] * o["v"] * (o["y"] - newO[o["off"]] - newD[o["def"]] + mu)
                           for o in obs) / hv
        c = (_mean(newO[t] for t in centered) - _mean(newD[t] for t in centered)) / 2
        newO = {t: x - c for t, x in newO.items()}
        newD = {t: x + c for t, x in newD.items()}
        delta = max([abs(newO[t] - O[t]) for t in teams] + [abs(newD[t] - D[t]) for t in teams]
                    + [abs(newh - h)])
        O, D, h = newO, newD, newh
        if delta < tol:
            break
    # Final reparametrization (predictions unchanged): shift O, D and mu together so
    # the average FBS defense sits exactly at mu. Then AdjO is literally "points per
    # drive against an average FBS defense, neutral field", AdjD the mirror, and mu is
    # what an average FBS offense scores against an average FBS defense.
    m = _mean(O[t] for t in centered)
    s = m - mu
    O = {t: x + s for t, x in O.items()}
    D = {t: x + s for t, x in D.items()}
    mu = m + s
    prior_O = {d: _mean(O[t] for t in teams if division[t] == d) for d in divs}
    prior_D = {d: _mean(D[t] for t in teams if division[t] == d) for d in divs}
    return {"mu": mu, "O": O, "D": D, "h": h, "iterations": it, "converged": delta < tol,
            "final_delta": delta, "prior_weight": prior_weight, "h_fixed": fixed_h is not None,
            "center": center,
            "prior_O": prior_O, "prior_D": prior_D, "division": division,
            "by_off": by_off, "by_def": by_def}


def trace(model, team):
    """Game-by-game reconstruction of AdjO and AdjD for one team."""
    mu, h, r = model["mu"], model["h"], model["prior_weight"]
    div = model["division"][team]
    off_lines, def_lines = [], []
    for o in model["by_off"][team]:
        opp_adj = model["D"][o["def"]] - mu
        off_lines.append({"game": o["game"], "opp": o["def"], "w": o["w"], "raw": o["y"],
                          "opp_AdjD": model["D"][o["def"]], "opp_adjustment": -opp_adj,
                          "venue": o["v"], "hfa_adjustment": -h * o["v"],
                          "adjusted": o["y"] - opp_adj - h * o["v"]})
    for o in model["by_def"][team]:
        opp_adj = model["O"][o["off"]] - mu
        def_lines.append({"game": o["game"], "opp": o["off"], "w": o["w"], "raw": o["y"],
                          "opp_AdjO": model["O"][o["off"]], "opp_adjustment": -opp_adj,
                          "venue": -o["v"], "hfa_adjustment": -h * o["v"],
                          "adjusted": o["y"] - opp_adj - h * o["v"]})

    def recompute(lines, prior):
        w = sum(x["w"] for x in lines)
        return (sum(x["w"] * x["adjusted"] for x in lines) + r * prior) / (w + r)

    adj_o = recompute(off_lines, model["prior_O"][div])
    adj_d = recompute(def_lines, model["prior_D"][div])
    return {
        "offense": {"lines": off_lines, "prior": {"weight": r, "value": model["prior_O"][div],
                                                  "division": div},
                    "recomputed": adj_o, "stored": model["O"][team],
                    "check_ok": abs(adj_o - model["O"][team]) < 1e-6},
        "defense": {"lines": def_lines, "prior": {"weight": r, "value": model["prior_D"][div],
                                                  "division": div},
                    "recomputed": adj_d, "stored": model["D"][team],
                    "check_ok": abs(adj_d - model["D"][team]) < 1e-6},
        "mu": mu, "h": h,
    }


def solve_tempo(games, division, prior_games=1, max_iter=500, tol=1e-9):
    """Possessions per team per game: poss_g = AdjT[X] + AdjT[Y] - muT."""
    teams = {g["a"] for g in games} | {g["b"] for g in games}
    muT = _mean(g["poss"] for g in games)
    by_team = defaultdict(list)
    for g in games:
        by_team[g["a"]].append((g, g["b"]))
        by_team[g["b"]].append((g, g["a"]))
    T = {t: muT for t in teams}
    divs = {division[t] for t in teams}
    delta, it = float("inf"), 0
    for it in range(1, max_iter + 1):
        prior = {d: _mean(T[t] for t in teams if division[t] == d) for d in divs}
        newT = {}
        for t in teams:
            rows = by_team[t]
            newT[t] = (sum(g["poss"] - (T[o] - muT) for g, o in rows)
                       + prior_games * prior[division[t]]) / (len(rows) + prior_games)
        shift = _mean(newT[g["a"]] + newT[g["b"]] for g in games) / 2 - muT
        newT = {t: x - shift for t, x in newT.items()}
        delta = max(abs(newT[t] - T[t]) for t in teams)
        T = newT
        if delta < tol:
            break
    prior = {d: _mean(T[t] for t in teams if division[t] == d) for d in divs}
    return {"muT": muT, "T": T, "iterations": it, "converged": delta < tol, "prior": prior,
            "prior_games": prior_games, "division": division, "by_team": by_team}


def trace_tempo(model, team):
    muT, T = model["muT"], model["T"]
    lines = [{"game": g["game"], "opp": o, "poss": g["poss"], "opp_AdjT": T[o],
              "adjusted": g["poss"] - (T[o] - muT)} for g, o in model["by_team"][team]]
    prior = model["prior"][model["division"][team]]
    val = (sum(x["adjusted"] for x in lines) + model["prior_games"] * prior) / (
        len(lines) + model["prior_games"])
    return {"lines": lines, "prior": prior, "recomputed": val, "stored": T[team],
            "check_ok": abs(val - T[team]) < 1e-6}
