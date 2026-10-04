"""Assemble every metric in METRICS.md from a parsed season.

    from ratings import load, rate
    data = load(2026)
    result = rate(data, cfg)                 # all games
    result = rate(data, cfg, through_week=4) # walk-forward / holdout
"""
import gzip
import json
import math
import os
from collections import defaultdict

from efficiency import solve, solve_tempo, trace, trace_tempo
from network import Network

HERE = os.path.dirname(os.path.abspath(__file__))


def load(season):
    with gzip.open(os.path.join(HERE, "data", str(season), "games.json.gz"), "rt") as f:
        return json.load(f)


def load_config():
    with open(os.path.join(HERE, "config.json")) as f:
        return json.load(f)


def venue(g, team):
    if g["neutral"]:
        return 0
    return 1 if team == g["home"] else -1


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def _rate(num, den):
    return num / den if den else None


def side_drives(g, team, role):
    return [d for d in g["drives"] if d[role] == team]


def rate(data, cfg, through_week=None):
    teams = data["teams"]
    division = {t: v["division"] for t, v in teams.items()}
    games = [g for g in data["games"] if g["d1"]
             and (through_week is None or g["week"] <= through_week)]

    # ---- efficiency observations -----------------------------------------
    # garbage_filter=false is a validation switch: count garbage-time drives too.
    if not cfg.get("garbage_filter", True):
        for g in games:
            for d in g["drives"]:
                if d["why"] == "garbage time":
                    d["kept"] = 1
    ppd_obs, sr_obs, tempo_games = [], [], []
    for g in games:
        if not g["drives"]:
            continue
        for team, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
            kept = [d for d in g["drives"] if d["off"] == team and d["kept"]]
            if kept:
                ppd_obs.append({"game": g["id"], "off": team, "def": opp, "v": venue(g, team),
                                "w": len(kept), "y": sum(d["pts"] for d in kept) / len(kept)})
            plays = [p for d in kept for p in d["plays"]]
            if plays:
                sr_obs.append({"game": g["id"], "off": team, "def": opp, "v": venue(g, team),
                               "w": len(plays), "y": sum(p[5] for p in plays) / len(plays)})
        poss = [d for d in g["drives"] if d["why"] in ("", "garbage time", "end of half/game")]
        n_home = sum(1 for d in poss if d["off"] == g["home"])
        n_away = sum(1 for d in poss if d["off"] == g["away"])
        if n_home and n_away:
            tempo_games.append({"game": g["id"], "a": g["home"], "b": g["away"],
                                "poss": (n_home + n_away) / 2})

    sv = cfg["solver"]
    # Home field is estimated from the unshrunk fit and then held fixed: with the
    # regression-to-mean prior on, strong teams (who host most games) keep a
    # positive residual that the solver would otherwise credit to home field.
    ppd0 = solve(ppd_obs, division, 0, sv["max_iter"], sv["tol"])
    ppd = solve(ppd_obs, division, cfg["prior_drives"], sv["max_iter"], sv["tol"],
                fixed_h=ppd0["h"])
    sr0 = solve(sr_obs, division, 0, sv["max_iter"], sv["tol"])
    sr = solve(sr_obs, division, cfg["prior_plays"], sv["max_iter"], sv["tol"], fixed_h=sr0["h"])
    tempo = solve_tempo(tempo_games, division, 1, sv["max_iter"], sv["tol"])
    muT = tempo["muT"]

    def adj_em(t):
        if t not in ppd["O"]:
            return None
        return (ppd["O"][t] - ppd["D"][t]) * muT

    # ---- per-team aggregates ---------------------------------------------
    net = Network(games, teams, cfg)
    out = {}
    for t in (t for t, v in teams.items() if v["division"] == "FBS"):
        mine = [g for g in games if t in (g["home"], g["away"])]
        r = {"id": t, "name": teams[t].get("name", t), "conference": teams[t]["conference"],
             "games": len(mine), "eligible": len(mine) >= cfg["min_games"]}
        w = l = cw = cl = pf = pa = 0
        for g in mine:
            us, them = (g["home_pts"], g["away_pts"]) if g["home"] == t else (g["away_pts"], g["home_pts"])
            pf += us
            pa += them
            won = us > them
            w += won
            l += not won
            if g["conf_game"]:
                cw += won
                cl += not won
        e = cfg["pythag_exp"]
        pyth = pf ** e / (pf ** e + pa ** e) if pf + pa else None
        r.update(W=w, L=l, confW=cw, confL=cl, PF=pf, PA=pa,
                 pythag=pyth, luck=(w / len(mine) - pyth) if mine and pyth is not None else None)

        # efficiency
        if t in ppd["O"]:
            r.update(AdjO=ppd["O"][t], AdjD=ppd["D"][t], AdjEM_drive=ppd["O"][t] - ppd["D"][t],
                     AdjEM=adj_em(t), AdjSR_O=sr["O"].get(t), AdjSR_D=sr["D"].get(t),
                     AdjT=tempo["T"].get(t))
            tr = trace(ppd, t)
            # game-level adjusted margins -> standard error of AdjEM
            off = {x["game"]: x["adjusted"] for x in tr["offense"]["lines"]}
            dfn = {x["game"]: x["adjusted"] for x in tr["defense"]["lines"]}
            ems = [(off[gid] - dfn[gid]) * muT for gid in off if gid in dfn]
            if len(ems) >= 2:
                m = sum(ems) / len(ems)
                sd = math.sqrt(sum((x - m) ** 2 for x in ems) / (len(ems) - 1))
                r["AdjEM_se"] = sd / math.sqrt(len(ems))
            r["eff_games"] = len(off)

        # raw efficiency and five factors (kept drives only)
        o_dr = [d for g in mine for d in side_drives(g, t, "off") if d["kept"]]
        d_dr = [d for g in mine for d in side_drives(g, t, "def") if d["kept"]]
        for tag, drs in (("O", o_dr), ("D", d_dr)):
            plays = [p for d in drs for p in d["plays"]]
            opps = [d for d in drs if any(p[0] == 1 and p[2] <= 40 for p in d["plays"])]
            r[f"PPD_{tag}"] = _rate(sum(d["pts"] for d in drs), len(drs))
            r[f"drives_{tag}"] = len(drs)
            r[f"SR_{tag}"] = _rate(sum(p[5] for p in plays), len(plays))
            r[f"XPL_{tag}"] = _rate(sum(p[6] for p in plays), len(plays))
            r[f"YPP_{tag}"] = _rate(sum(p[4] for p in plays), len(plays))
            r[f"FP_{tag}"] = _rate(sum(100 - d["start_yte"] for d in drs), len(drs))
            r[f"FIN_{tag}"] = _rate(sum(d["pts"] for d in opps), len(opps))
            r[f"opps_{tag}"] = len(opps)
            r[f"plays_{tag}"] = len(plays)
        secs = sum(d["secs"] or 0 for d in o_dr)
        r["sec_per_play"] = _rate(secs, r["plays_O"])
        give = take = nbox = 0
        for g in mine:
            opp = g["away"] if g["home"] == t else g["home"]
            if g["box"].get(t, {}).get("turnovers") is not None and \
                    g["box"].get(opp, {}).get("turnovers") is not None:
                give += g["box"][t]["turnovers"]
                take += g["box"][opp]["turnovers"]
                nbox += 1
        r.update(TO_give=_rate(give, nbox), TO_take=_rate(take, nbox),
                 TO_margin=_rate(take - give, nbox))

        # KenPom-style SOS
        opp_em, opp_o, opp_d, nc_em = [], [], [], []
        for g in mine:
            opp = g["away"] if g["home"] == t else g["home"]
            if opp in ppd["O"]:
                opp_em.append(adj_em(opp))
                opp_o.append(ppd["O"][opp])
                opp_d.append(ppd["D"][opp])
                if not g["conf_game"]:
                    nc_em.append(adj_em(opp))
        r.update(SOS=_rate(sum(opp_em), len(opp_em)), OppO=_rate(sum(opp_o), len(opp_o)),
                 OppD=_rate(sum(opp_d), len(opp_d)), NCSOS=_rate(sum(nc_em), len(nc_em)))

        # +2 network resume
        res = net.resume(t, with_trees=False)
        r.update(WVT=res["win_value_total"], AvgWV=res["avg_win_value"],
                 LCT=res["loss_cost_total"], NetResume=res["net_resume"],
                 SchedNS=res["schedule_ratio"],
                 BestWin=(res["best_win"] or {}).get("value"),
                 BestWinOpp=(res["best_win"] or {}).get("opp"),
                 WorstLoss=(res["worst_loss"] or {}).get("cost"),
                 WorstLossOpp=(res["worst_loss"] or {}).get("opp"))
        out[t] = r

    # ranks among eligible teams
    elig = [r for r in out.values() if r["eligible"] and r.get("AdjEM") is not None]
    for key, rev in (("AdjEM", True), ("AdjO", True), ("AdjD", False), ("AdjT", True),
                     ("SOS", True), ("NCSOS", True), ("NetResume", True), ("WVT", True),
                     ("Luck", True), ("SchedNS", True)):
        src = "luck" if key == "Luck" else key
        ranked = sorted((r for r in elig if r.get(src) is not None),
                        key=lambda r: r[src], reverse=rev)
        for i, r in enumerate(ranked, 1):
            r[f"rk_{key}"] = i

    return {"teams": out, "ppd": ppd, "sr": sr, "tempo": tempo, "net": net, "games": games,
            "muT": muT, "hfa_points": 2 * ppd["h"] * muT, "through_week": through_week}


def predict(result, home, away, neutral):
    """Expected home margin and possessions from the efficiency model."""
    ppd, tempo, muT = result["ppd"], result["tempo"], result["muT"]
    if home not in ppd["O"] or away not in ppd["O"]:
        return None
    poss = tempo["T"].get(home, muT) + tempo["T"].get(away, muT) - muT
    em = (ppd["O"][home] - ppd["D"][home]) - (ppd["O"][away] - ppd["D"][away])
    hfa = 0 if neutral else 2 * ppd["h"]
    return {"margin": (em + hfa) * poss, "poss": poss, "em_diff_drive": em,
            "hfa_drive": hfa}
