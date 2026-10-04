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
from parse import clock_secs

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


TEMPO_WHY = ("", "garbage time", "end of half/game", "leader's final drive")


def good_clock(g, cfg):
    """ESPN's game clock is usable for pace when fewer than 25% of snap-to-snap readings are 0 s."""
    c = g.get("clock") or {}
    return bool(c.get("cand")) and c["zero"] / c["cand"] < cfg["situational"]["max_zero_clock_share"]


def lead_protection(d, g, cfg):
    """Clock-burning to protect a lead (the user's situational football), checkable by hand:
    Q4, offense ahead by 1 to max_lead at the first snap, a usable game clock, clean
    snap-to-snap intervals averaging >= min_mean_secs over >= min_intervals, and runs on
    >= min_run_share of >= min_plays scrimmage plays. Returns the reason string or ''."""
    lp = cfg["situational"]["lead_protection"]
    if d["period"] != 4 or not 1 <= d["margin"] <= lp["max_lead"] or not d["plays"]:
        return ""
    iv, plays = d.get("iv") or [], d["plays"]
    runs = sum(1 for p in plays if p[3] == "R")
    if (not good_clock(g, cfg) or len(iv) < lp["min_intervals"] or sum(iv) / len(iv) < lp["min_mean_secs"]
            or len(plays) < lp["min_plays"] or runs / len(plays) < lp["min_run_share"]):
        return ""
    return (f"Q4, up {d['margin']:g}, {sum(iv) / len(iv):.1f} s/snap over {len(iv)} clean intervals, "
            f"{runs}/{len(plays)} runs")


DISCIPLINE_KEYS = ("PenPG", "PenYdsPG", "NetPenYdsPG", "OffPen100", "OffPreSnap100", "DefPen100",
                   "PenFDAllowedPG")


def is_situational_foul(row, f, drives_by_i):
    """A Q4 leader's offensive delay of game is clock management, not indiscipline."""
    d = drives_by_i.get(row[f["drive_index"]])
    return (row[f["category"]] == "Delay of Game" and row[f["penalized_unit"]] == "offense"
            and row[f["period"]] == 4 and d is not None and d["margin"] > 0)


def discipline(t, mine, fields, cfg):
    f = {k: i for i, k in enumerate(fields)}
    pen_n = pen_y = box_games = net_y = net_games = 0
    off_snaps = def_snaps = off_f = off_pre = def_f = fd = pbp_games = 0
    for g in mine:
        opp = g["away"] if g["home"] == t else g["home"]
        own_box, opp_box = (g["box"].get(t) or {}).get("pen"), (g["box"].get(opp) or {}).get("pen")
        if own_box:
            pen_n, pen_y, box_games = pen_n + own_box[0], pen_y + own_box[1], box_games + 1
            if opp_box:
                net_y, net_games = net_y + opp_box[1] - own_box[1], net_games + 1
        if not g["drives"] or "penalties" not in g:
            continue
        pbp_games += 1
        by_i = {d["i"]: d for d in g["drives"]}
        for d in g["drives"]:
            if d["kept"]:
                n = len(d["plays"]) + d.get("pen_rows", 0)
                if d["off"] == t:
                    off_snaps += n
                else:
                    def_snaps += n
        for row in g["penalties"]:
            if (row[f["status"]] != "accepted" or row[f["penalized_team_id"]] != t
                    or row[f["drive_why"]] != "" or is_situational_foul(row, f, by_i)):
                continue
            unit = row[f["penalized_unit"]]
            if unit == "offense":
                off_f += 1
                off_pre += bool(row[f["presnap"]])
            elif unit == "defense":
                def_f += 1
                fd += bool(row[f["first_down_awarded"]])
    per100 = lambda a, b: 100 * a / b if b else None
    return {"PenPG": _rate(pen_n, box_games), "PenYdsPG": _rate(pen_y, box_games),
            "NetPenYdsPG": _rate(net_y, net_games),
            "OffPen100": per100(off_f, off_snaps), "OffPreSnap100": per100(off_pre, off_snaps),
            "DefPen100": per100(def_f, def_snaps), "PenFDAllowedPG": _rate(fd, pbp_games),
            "pen_counts": {"box_games": box_games, "off_fouls": off_f, "off_presnap": off_pre,
                           "def_fouls": def_f, "def_first_downs": fd, "off_snaps": off_snaps,
                           "def_snaps": def_snaps, "pbp_games": pbp_games}}


def drive_weight(d, cfg):
    return cfg["situational"]["lead_protection"]["weight"] if d.get("lp") else 1.0


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
    # Lead-protection tags (descriptive; they only change the ratings if the
    # configured weight is below 1.0, which is off by default -- see ADVERSARIAL_REVIEW).
    for g in games:
        for d in g["drives"]:
            d["lp"] = lead_protection(d, g, cfg) if d["kept"] else ""
    ppd_obs, sr_obs, tempo_games = [], [], []
    for g in games:
        if not g["drives"]:
            continue
        for team, opp in ((g["home"], g["away"]), (g["away"], g["home"])):
            kept = [d for d in g["drives"] if d["off"] == team and d["kept"]]
            w = sum(drive_weight(d, cfg) for d in kept)
            if w:
                ppd_obs.append({"game": g["id"], "off": team, "def": opp, "v": venue(g, team),
                                "w": w, "y": sum(drive_weight(d, cfg) * d["pts"] for d in kept) / w})
            pw = sum(drive_weight(d, cfg) * len(d["plays"]) for d in kept)
            if pw:
                sr_obs.append({"game": g["id"], "off": team, "def": opp, "v": venue(g, team),
                               "w": pw, "y": sum(drive_weight(d, cfg) * p[5] for d in kept
                                                 for p in d["plays"]) / pw})
        poss = [d for d in g["drives"] if d["why"] in TEMPO_WHY]
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
        w = l = cw = cl = pf = pa = apf = apa = 0
        for g in mine:
            us, them = (g["home_pts"], g["away_pts"]) if g["home"] == t else (g["away_pts"], g["home_pts"])
            pf += us
            pa += them
            # Garbage-adjusted score: final score minus offensive points scored on
            # garbage-time drives (each removed drive is listed in the trace).
            apf += us - sum(d["pts"] for d in g["drives"] if d["off"] == t and d["why"] == "garbage time")
            apa += them - sum(d["pts"] for d in g["drives"] if d["def"] == t and d["why"] == "garbage time")
            if us == them:
                continue  # ties can't happen in modern CFB; network.py skips them too
            won = us > them
            w += won
            l += not won
            if g["conf_game"]:
                cw += won
                cl += not won
        e = cfg["pythag_exp"]
        pyth_raw = pf ** e / (pf ** e + pa ** e) if pf + pa else None
        pyth = apf ** e / (apf ** e + apa ** e) if apf + apa else None
        r.update(W=w, L=l, confW=cw, confL=cl, PF=pf, PA=pa, adjPF=apf, adjPA=apa,
                 pythag=pyth, luck=(w / len(mine) - pyth) if mine and pyth is not None else None,
                 pythag_raw=pyth_raw,
                 luck_raw=(w / len(mine) - pyth_raw) if mine and pyth_raw is not None else None)

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

        # Neutral pace: clean snap-to-snap seconds in Q1-Q3 with the score within 14
        # (not the final 2:00 of Q2), games with a usable clock. Display only.
        sit = cfg["situational"]
        iv, nplays, nruns = [], 0, 0
        for g in mine:
            if not good_clock(g, cfg):
                continue
            for d in side_drives(g, t, "off"):
                if d["period"] in (1, 2, 3) and abs(d["margin"]) <= sit["neutral_margin"] and not (
                        d["period"] == 2 and (clock_secs(d["clock"]) or 999) <= 120):
                    iv += d.get("iv") or []
                    nplays += len(d["plays"])
                    nruns += sum(1 for p in d["plays"] if p[3] == "R")
        enough = len(iv) >= sit["min_pace_intervals"]
        r.update(NeutralPace=sum(iv) / len(iv) if enough else None, pace_intervals=len(iv),
                 NeutralRunRate=nruns / nplays if enough and nplays else None,
                 LP_drives=sum(1 for g in mine for d in side_drives(g, t, "off") if d.get("lp")),
                 Q4_lead_drives=sum(1 for g in mine for d in side_drives(g, t, "off")
                                    if d["kept"] and d["period"] == 4 and 1 <= d["margin"] <= 21))

        # Discipline (descriptive, not part of the rating). Per-game counts come from the
        # box score; rates come from the play-by-play on kept drives only, per 100 snaps,
        # with situational fouls (a Q4 leader's offensive delay of game) left out.
        r.update(discipline(t, mine, data.get("penalty_fields") or [], cfg))

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
                 # Per game, so a sixth game played isn't an advantage over five.
                 NetPerGame=res["net_resume"] / len(mine) if mine else None,
                 SchedNS=res["schedule_ratio"],
                 BestWin=(res["best_win"] or {}).get("value"),
                 BestWinOpp=(res["best_win"] or {}).get("opp"),
                 WorstLoss=(res["worst_loss"] or {}).get("cost"),
                 WorstLossOpp=(res["worst_loss"] or {}).get("opp"))
        out[t] = r

    # ranks among eligible teams
    elig = [r for r in out.values() if r["eligible"] and r.get("AdjEM") is not None]
    for key, rev in (("AdjEM", True), ("AdjO", True), ("AdjD", False), ("AdjT", True),
                     ("SOS", True), ("NCSOS", True), ("NetResume", True), ("NetPerGame", True), ("WVT", True),
                     ("Luck", True), ("SchedNS", True), ("NeutralPace", False),
                     ("PenPG", False), ("OffPen100", False), ("DefPen100", False)):
        src = "luck" if key == "Luck" else key
        ranked = sorted((r for r in elig if r.get(src) is not None),
                        key=lambda r: r[src], reverse=rev)
        for i, r in enumerate(ranked, 1):
            r[f"rk_{key}"] = i

    # conference averages beside each discipline value (officiating differs by conference)
    for key in DISCIPLINE_KEYS:
        by_conf = {}
        for r in elig:
            if r.get(key) is not None:
                by_conf.setdefault(r["conference"], []).append(r[key])
        for r in out.values():
            v = by_conf.get(r["conference"])
            r[f"{key}_conf"] = sum(v) / len(v) if v else None

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
