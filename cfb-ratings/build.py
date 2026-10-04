"""Build the published ratings and a full derivation trace for every FBS team.

    python build.py
      out/ratings.csv          one row per FBS team (eligible teams ranked)
      out/ratings.json         same rows + model constants, conferences, predictions
      out/traces/<id>.json     every number for one team, back to drives and plays
"""
import copy
import csv
import json
import math
import os
from collections import defaultdict

from efficiency import trace, trace_tempo
from ratings import (DISCIPLINE_KEYS, HERE, drive_weight, good_clock, is_situational_foul, load,
                     load_config, phi, predict, rate, venue)
from validate import evaluate

OUT = os.path.join(HERE, "out")

COLUMNS = [
    ("rk_AdjEM", "Rk"), ("name", "Team"), ("conference", "Conf"), ("W", "W"), ("L", "L"),
    ("games", "G"), ("eligible", "Eligible"),
    ("AdjEM", "AdjEM"), ("AdjEM_se", "AdjEM_SE"), ("AdjO", "AdjO"), ("rk_AdjO", "AdjO_Rk"),
    ("AdjD", "AdjD"), ("rk_AdjD", "AdjD_Rk"), ("AdjT", "AdjT"), ("AdjSR_O", "AdjSR_O"),
    ("AdjSR_D", "AdjSR_D"), ("PPD_O", "PPD_O"), ("PPD_D", "PPD_D"),
    ("SR_O", "SR_O"), ("SR_D", "SR_D"), ("XPL_O", "Explosive_O"), ("XPL_D", "Explosive_D"),
    ("YPP_O", "YPP_O"), ("YPP_D", "YPP_D"), ("FP_O", "FieldPos_O"), ("FP_D", "FieldPos_D"),
    ("FIN_O", "PtsPerOpp_O"), ("FIN_D", "PtsPerOpp_D"), ("TO_margin", "TO_Margin_pg"),
    ("sec_per_play", "SecPerPlay"), ("NeutralPace", "NeutralPace_s_per_snap"),
    ("NeutralRunRate", "NeutralRunRate"), ("LP_drives", "LeadProtectionDrives"),
    ("adjPF", "PF_garbage_adj"), ("adjPA", "PA_garbage_adj"),
    ("pythag", "PythagW%_garbage_adj"), ("luck", "Luck"), ("luck_raw", "Luck_raw_scores"),
    ("PenPG", "Pen_pg"), ("PenYdsPG", "PenYds_pg"), ("NetPenYdsPG", "NetPenYds_pg"),
    ("OffPen100", "OffPen_per100"), ("OffPen100_conf", "OffPen_per100_confavg"),
    ("OffPreSnap100", "OffPreSnap_per100"), ("DefPen100", "DefPen_per100"),
    ("DefPen100_conf", "DefPen_per100_confavg"), ("PenFDAllowedPG", "PenFirstDownsAllowed_pg"),
    ("SOS", "SOS_AdjEM"), ("rk_SOS", "SOS_Rk"), ("NCSOS", "NCSOS_AdjEM"),
    ("OppO", "Opp_AdjO"), ("OppD", "Opp_AdjD"),
    ("WVT", "WinValueTotal"), ("AvgWV", "AvgWinValue"), ("LCT", "LossCostTotal"),
    ("NetResume", "NetResume"), ("NetPerGame", "NetResumePerGame"), ("rk_NetPerGame", "Resume_Rk"),
    ("SchedNS", "SchedStrengthRatio"),
    ("BestWin", "BestWinValue"), ("BestWinOpp", "BestWinOpp"),
    ("WorstLoss", "WorstLossCost"), ("WorstLossOpp", "WorstLossOpp"),
]


def name_of(teams, t):
    return teams.get(t, {}).get("name", t)


def opp_status(opp, teams, eligible):
    """How an opponent's rating may be shown inside another team's trace."""
    if teams.get(opp, {}).get("division") != "FBS":
        return "internal: FCS team (FCS teams are rated only to adjust FBS numbers)"
    if opp not in eligible:
        return "internal: FBS team below the game minimum (not a published rating)"
    return "published"


def team_trace(t, res, data, cfg, sigma, eligible):
    teams = data["teams"]
    row = res["teams"][t]
    ppd, sr, tempo, muT = res["ppd"], res["sr"], res["tempo"], res["muT"]
    mine = [g for g in res["games"] if t in (g["home"], g["away"])]
    nm = lambda x: name_of(teams, x)
    schedule = []
    for g in mine:
        home = g["home"] == t
        opp = g["away"] if home else g["home"]
        us, them = (g["home_pts"], g["away_pts"]) if home else (g["away_pts"], g["home_pts"])
        g_us = sum(d["pts"] for d in g["drives"] if d["off"] == t and d["why"] == "garbage time")
        g_them = sum(d["pts"] for d in g["drives"] if d["def"] == t and d["why"] == "garbage time")
        schedule.append({"game": g["id"], "week": g["week"], "date": g["date"][:10],
                         "garbage_pts_us": g_us, "garbage_pts_them": g_them,
                         "adj_us": us - g_us, "adj_them": them - g_them,
                         "opp": opp, "opp_name": nm(opp),
                         "opp_division": teams.get(opp, {}).get("division"),
                         "site": "N" if g["neutral"] else ("H" if home else "A"),
                         "us": us, "them": them, "result": "W" if us > them else "L",
                         "conf_game": bool(g["conf_game"]),
                         "used_in_efficiency": bool(g["drives"]),
                         "clock": {**(g.get("clock") or {}), "usable": good_clock(g, cfg)},
                         "box_penalties": {"us": (g["box"].get(t) or {}).get("pen"),
                                           "them": (g["box"].get(opp) or {}).get("pen"),
                                           "rejected": [(g["box"].get(x) or {}).get("pen_raw")
                                                        for x in (t, opp) if (g["box"].get(x) or {}).get("pen") is None
                                                        and (g["box"].get(x) or {}).get("pen_raw")]},
                         "note": g["pbp_note"]})
    tr = {"team": {"id": t, "name": row["name"], "conference": row["conference"]},
          "summary": row, "schedule": schedule,
          "eligibility": {"games": row["games"], "min_games": cfg["min_games"],
                          "eligible": row["eligible"],
                          "rule": "completed D-I games (FBS or FCS opponents)"}}

    if t in ppd["O"]:
        e = trace(ppd, t)
        for side in ("offense", "defense"):
            for ln in e[side]["lines"]:
                ln["opp_name"] = nm(ln["opp"])
                ln["opp_status"] = opp_status(ln["opp"], teams, eligible)
        em_games = []
        dmap = {x["game"]: x for x in e["defense"]["lines"]}
        for x in e["offense"]["lines"]:
            if x["game"] in dmap:
                em_games.append({"game": x["game"], "opp_name": x["opp_name"],
                                 "adj_off": x["adjusted"], "adj_def": dmap[x["game"]]["adjusted"],
                                 "adj_margin_per_game": (x["adjusted"] - dmap[x["game"]]["adjusted"]) * muT})
        tr["efficiency"] = {
            "formula": "AdjEM = (AdjO - AdjD) * muT; AdjO/AdjD = weighted mean of adjusted game "
                       "values plus one phantom game at the division average",
            "mu": ppd["mu"], "h": ppd["h"], "muT": muT, "AdjO": ppd["O"][t], "AdjD": ppd["D"][t],
            "AdjEM": row["AdjEM"], "AdjEM_se": row.get("AdjEM_se"),
            "offense": e["offense"], "defense": e["defense"], "game_margins": em_games}
        s = trace(sr, t)
        for side, k_old, k_new in (("offense", "opp_AdjD", "opp_AdjSR_D"), ("defense", "opp_AdjO", "opp_AdjSR_O")):
            for ln in s[side]["lines"]:
                ln[k_new] = ln.pop(k_old)
                ln["opp_name"] = nm(ln["opp"])
                ln["opp_status"] = opp_status(ln["opp"], teams, eligible)
        tr["success_rate_adjusted"] = {"mu": sr["mu"], "h": sr["h"], "offense": s["offense"],
                                       "defense": s["defense"], "AdjSR_O": sr["O"][t], "AdjSR_D": sr["D"][t]}
        if t in tempo["T"]:
            tt = trace_tempo(tempo, t)
            for ln in tt["lines"]:
                ln["opp_name"] = nm(ln["opp"])
                ln["opp_status"] = opp_status(ln["opp"], teams, eligible)
            tr["tempo"] = {"muT": muT, **tt}

    # five factors, game by game
    fac = []
    for g in mine:
        opp = g["away"] if g["home"] == t else g["home"]
        line = {"game": g["id"], "opp_name": nm(opp)}
        for tag, role in (("O", "off"), ("D", "def")):
            drs = [d for d in g["drives"] if d[role] == t and d["kept"]]
            plays = [p for d in drs for p in d["plays"]]
            opps = [d for d in drs if any(p[0] == 1 and p[2] <= 40 for p in d["plays"])]
            line[tag] = {"drives": len(drs), "points": sum(d["pts"] for d in drs),
                         "plays": len(plays), "successes": sum(p[5] for p in plays),
                         "explosive": sum(p[6] for p in plays), "yards": sum(p[4] for p in plays),
                         "start_yardline_sum": sum(100 - d["start_yte"] for d in drs),
                         "scoring_opps": len(opps), "opp_points": sum(d["pts"] for d in opps)}
        line["turnovers_given"] = g["box"].get(t, {}).get("turnovers")
        line["turnovers_taken"] = g["box"].get(opp, {}).get("turnovers")
        fac.append(line)
    tr["factors"] = {"definitions": {
        "SR": "successes / plays (1st down: 50% of distance, 2nd: 70%, 3rd/4th: 100%)",
        "Explosive": f"plays gaining >= {cfg['explosive']['rush']} (rush) / "
                     f"{cfg['explosive']['pass']} (pass) yards / plays",
        "FieldPos": "start_yardline_sum / drives (own goal line = 0)",
        "PtsPerOpp": "opp_points / scoring_opps (drives with a 1st down at or inside opp 40)",
        "TO_margin": "(taken - given) / games"}, "games": fac}

    tr["luck"] = {"PF": row["PF"], "PA": row["PA"], "adjPF": row["adjPF"], "adjPA": row["adjPA"],
                  "exponent": cfg["pythag_exp"], "pythag": row["pythag"], "pythag_raw": row["pythag_raw"],
                  "actual": row["W"] / row["games"] if row["games"] else None,
                  "luck": row["luck"], "luck_raw": row["luck_raw"],
                  "rule": "garbage-adjusted score = final score minus offensive points on garbage-time "
                          "drives (per-game removals listed in the schedule)"}

    sit = cfg["situational"]
    lp_rows = []
    for g in mine:
        for d in g["drives"]:
            if d["off"] == t and d.get("lp"):
                lp_rows.append({"game": g["id"], "opp_name": nm(g["away"] if g["home"] == t else g["home"]),
                                "drive": d["i"], "clock": d["clock"], "reason": d["lp"], "points": d["pts"],
                                "intervals": [x[2] for x in d.get("iv") or []]})
    tr["situational"] = {
        "neutral_pace": row.get("NeutralPace"), "neutral_run_rate": row.get("NeutralRunRate"),
        "pace_intervals": row.get("pace_intervals"), "min_pace_intervals": sit["min_pace_intervals"],
        "pace_rule": f"mean clean snap-to-snap seconds, Q1-Q3, score within {sit['neutral_margin']}, "
                     "not the final 2:00 of Q2, games whose clock is usable",
        "lead_protection_rule": sit["lead_protection"], "lead_protection_drives": lp_rows,
        "q4_lead_drives": row.get("Q4_lead_drives"), "usable_clock_games": row.get("usable_clock_games"),
        "weight_note": ("weight 1.0: tagged drives count fully (default; no tested adjustment "
                        "improved accuracy)" if sit["lead_protection"]["weight"] == 1.0 else
                        f"weight {sit['lead_protection']['weight']}: tagged drives are down-weighted in AdjO/AdjD/AdjSR")}

    pf = {k: i for i, k in enumerate(data.get("penalty_fields") or [])}
    fouls = []
    for g in mine:
        if "penalties" not in g:
            continue
        by_i = {d["i"]: d for d in g["drives"]}
        for rw in g["penalties"]:
            if rw[pf["penalized_team_id"]] != t:
                continue
            fouls.append({"game": g["id"], "opp_name": nm(g["away"] if g["home"] == t else g["home"]),
                          **{k: rw[pf[k]] for k in ("period", "clock", "category", "penalized_unit",
                                                    "presnap", "yards", "status", "first_down_awarded",
                                                    "dialect", "yards_method", "drive_why")},
                          "situational": is_situational_foul(rw, pf, by_i)})
    tr["discipline"] = {k: row.get(k) for k in DISCIPLINE_KEYS}
    tr["discipline"].update({f"{k}_conf": row.get(f"{k}_conf") for k in DISCIPLINE_KEYS},
                            counts=row.get("pen_counts"), fouls=fouls,
                            rules={"per_game": "box score accepted penalties (sanity-checked)",
                                   "rates": "accepted fouls on kept drives per 100 snaps; a Q4 "
                                            "leader's offensive delay of game is situational and "
                                            "left out", "rating": "descriptive only; not in the rating"})

    sos_lines = []
    for g in mine:
        opp = g["away"] if g["home"] == t else g["home"]
        if opp in ppd["O"]:
            sos_lines.append({"opp_name": nm(opp), "opp_AdjEM": (ppd["O"][opp] - ppd["D"][opp]) * muT,
                              "opp_AdjO": ppd["O"][opp], "opp_AdjD": ppd["D"][opp],
                              "conf_game": bool(g["conf_game"]),
                              "opp_status": opp_status(opp, teams, eligible)})
    tr["sos_efficiency"] = {"SOS": row["SOS"], "NCSOS": row["NCSOS"], "opponents": sos_lines}

    resume = res["net"].resume(t, with_trees=True)
    label_tree(resume, teams)
    tr["network"] = {"refs": resume["refs"],
                     "weights": cfg["net_weights"], "record_prior": cfg["record_prior"],
                     "exclusion": cfg.get("exclusion", "path"),
                     "win_value_total": resume["win_value_total"],
                     "loss_cost_total": resume["loss_cost_total"],
                     "net_resume": resume["net_resume"],
                     "net_per_game": row.get("NetPerGame"),
                     "avg_win_value": resume["avg_win_value"],
                     "schedule_ns_ratio": resume["schedule_ratio"],
                     "wins": resume["wins"], "losses": resume["losses"]}

    drives = []
    for g in mine:
        for d in g["drives"]:
            if t not in (d["off"], d["def"]):
                continue
            drives.append([g["id"], d["i"], "O" if d["off"] == t else "D", d["period"], d["clock"],
                           None if d["start_yte"] is None else 100 - d["start_yte"],
                           d["result"], d["pts"], d["margin"], d["kept"], d["why"], len(d["plays"]),
                           d.get("lp") or "", d.get("runs"), d.get("pen_rows"), d.get("secs"),
                           d.get("clock_src"), [x[2] for x in d.get("iv") or []],
                           drive_weight(d, cfg) if d["kept"] else None])
    tr["drives"] = {"columns": ["game", "drive#", "side", "qtr", "clock", "start_yardline",
                                "result", "points", "margin_at_start", "kept", "excluded_reason",
                                "scrimmage_plays", "lead_protection", "runs", "penalty_only_snaps",
                                "elapsed_secs", "clock_source", "clean_intervals_s", "weight"],
                    "rows": drives}
    return tr


def label_tree(resume, teams):
    for r in resume["wins"] + resume["losses"]:
        r["opp_name"] = name_of(teams, r["opp"])
        tree = r.get("tree")
        if not tree:
            continue
        tree["primary"]["name"] = name_of(teams, tree["primary"]["team"])
        for gm in tree["primary"]["games"]:
            gm["opp_name"] = name_of(teams, gm["opp"])
        for c in tree["secondary"]:
            c["name"] = name_of(teams, c["team"])
            for d in c["tertiary"]:
                d["name"] = name_of(teams, d["team"])


def main():
    cfg = load_config()
    data = load(cfg["season"])
    res = rate(copy.deepcopy(data), cfg)
    teams = data["teams"]

    # out-of-sample sigma for win probabilities: this season's walk-forward weeks
    last_week = max(g["week"] for g in data["games"] if g["d1"])
    holdout = evaluate(cfg["season"], range(3, last_week + 1), cfg, "walk-forward")
    sigma = holdout["sigma"]

    os.makedirs(os.path.join(OUT, "traces"), exist_ok=True)
    # Rated teams by rank, then unrated teams alphabetically (never by an unpublished rating).
    rows = sorted(res["teams"].values(),
                  key=lambda r: (not r["eligible"], r.get("rk_AdjEM") or 999, r["name"]))
    with open(os.path.join(OUT, "ratings.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([c for _, c in COLUMNS])
        identity = {"name", "conference", "W", "L", "games", "eligible"}
        for r in rows:
            out = []
            for k, _ in COLUMNS:
                # The 5-game rule: teams below it get no published numbers.
                v = r.get(k) if (r["eligible"] or k in identity) else None
                if k in ("BestWinOpp", "WorstLossOpp") and v:
                    v = name_of(teams, v)
                out.append(round(v, 4) if isinstance(v, float) else v)
            w.writerow(out)

    eligible = {t for t, r in res["teams"].items() if r["eligible"]}
    bad = []
    for r in rows:
        tr = team_trace(r["id"], res, data, cfg, sigma, eligible)
        checks = [tr["efficiency"][s]["check_ok"] for s in ("offense", "defense")] if "efficiency" in tr else []
        checks += [tr["success_rate_adjusted"][s]["check_ok"] for s in ("offense", "defense")] \
            if "success_rate_adjusted" in tr else []
        checks += [tr["tempo"]["check_ok"]] if "tempo" in tr else []
        if not all(checks):
            bad.append(r["name"])
        if not r["eligible"]:
            # The game minimum: no published rating, resume or ranking for this team.
            for g in tr["schedule"]:
                for k in ("garbage_pts_us", "garbage_pts_them", "adj_us", "adj_them"):
                    g.pop(k, None)
            tr = {"team": tr["team"], "schedule": tr["schedule"], "eligibility": tr["eligibility"],
                  "summary": {k: r[k] for k in ("id", "name", "conference", "W", "L", "games", "eligible")},
                  "note": f"{r['name']} has played {r['games']} of the {cfg['min_games']} games "
                          "required for a rating. Its internal estimate is used only to adjust its "
                          "opponents' numbers and is not published."}
        with open(os.path.join(OUT, "traces", f"{r['id']}.json"), "w") as f:
            json.dump(tr, f, separators=(",", ":"), default=float)

    # Internal-input derivations. Every FCS team and every FBS team below the game minimum
    # appears as an opponent in some rated team's trace; its own lines are written here,
    # labeled, with no AdjEM, rank or resume, so each rated number traces to the end.
    idir = os.path.join(OUT, "traces", "internal")
    os.makedirs(idir, exist_ok=True)
    index = {}
    for t in res["ppd"]["O"]:
        e, s_, = trace(res["ppd"], t), trace(res["sr"], t)
        checks = [e["offense"]["check_ok"], e["defense"]["check_ok"],
                  s_["offense"]["check_ok"], s_["defense"]["check_ok"]]
        tt = trace_tempo(res["tempo"], t) if t in res["tempo"]["T"] else None
        if tt:
            checks.append(tt["check_ok"])
        if not all(checks):
            bad.append(name_of(teams, t))
        if t in eligible:
            continue
        for side in ("offense", "defense"):
            for ln in e[side]["lines"] + s_[side]["lines"]:
                ln["opp_name"] = name_of(teams, ln["opp"])
                ln["opp_status"] = opp_status(ln["opp"], teams, eligible)
        if tt:
            for ln in tt["lines"]:
                ln["opp_name"] = name_of(teams, ln["opp"])
                ln["opp_status"] = opp_status(ln["opp"], teams, eligible)
        div = teams.get(t, {}).get("division")
        index[t] = name_of(teams, t)
        with open(os.path.join(idir, f"{t}.json"), "w") as f:
            json.dump({"team": {"id": t, "name": name_of(teams, t), "division": div,
                                "conference": teams.get(t, {}).get("conference")},
                       "internal": True,
                       "note": ("Internal input, not a published rating: " +
                                ("FCS teams are rated only to adjust FBS numbers." if div == "FCS" else
                                 f"fewer than {cfg['min_games']} games played.") +
                                " These lines exist so every rated team's numbers can be traced to the end."),
                       "efficiency": {"mu": res["ppd"]["mu"], "h": res["ppd"]["h"],
                                      "offense": e["offense"], "defense": e["defense"]},
                       "success_rate_adjusted": {"offense": s_["offense"], "defense": s_["defense"]},
                       "tempo": tt}, f, separators=(",", ":"), default=float)
    with open(os.path.join(idir, "index.json"), "w") as f:
        json.dump(index, f)

    # Anchors: every input to the global constants, so they can be recomputed.
    ppd_ = res["ppd"]
    net_rows = []
    for a in res["net"].fbs:
        for b, won, gid in res["net"].fbs_games[a]:
            net_rows.append([gid, a, b, int(won), res["net"].strength(b, a)["ns"]])
    with open(os.path.join(OUT, "anchors.json"), "w") as f:
        json.dump({
            "mu": {"value": ppd_["mu"], "rule": "mean AdjO over all FBS teams (= mean FBS AdjD); "
                                               "includes teams below the game minimum (internal)"},
            "teams": [{"id": t, "name": name_of(teams, t), "division": ppd_["division"][t],
                       "AdjO": ppd_["O"][t], "AdjD": ppd_["D"][t],
                       "status": "published" if t in eligible else "internal"} for t in sorted(ppd_["O"])],
            "phantom_game": {"weight": cfg["prior_drives"], "AdjO_by_division": ppd_["prior_O"],
                             "AdjD_by_division": ppd_["prior_D"],
                             "rule": "mean AdjO / AdjD of the division's teams (the teams list above)"},
            "home_field": {"h_per_drive": ppd_["h"], "rule": "estimated by the unshrunk fit (prior 0) "
                                                            "and held fixed; ratings.rate() reproduces it"},
            "muT": {"value": res["muT"], "rule": "mean possessions per team per game over these games",
                    "games": [[g["game"], g["a"], g["b"], g["poss"]] for g in res["tempo"]["games"]]},
            "network": {**res["net"].references(),
                        "columns": ["game", "team", "opponent", "team_won", "opponent_NS"],
                        "rows": net_rows,
                        "rule": "NS_win = mean opponent_NS where team_won = 1; NS_loss = mean where 0; "
                                "NS_all = mean of all rows"},
        }, f, separators=(",", ":"), default=float)

    # conference ratings (published members only)
    conf = defaultdict(list)
    for r in res["teams"].values():
        if r.get("AdjEM") is not None and r["eligible"]:
            conf[r["conference"]].append(r["AdjEM"])
    conferences = sorted(({"conference": c, "teams": len(v), "avg_AdjEM": sum(v) / len(v)}
                          for c, v in conf.items()), key=lambda x: -x["avg_AdjEM"])

    # next week's predictions
    upcoming = [u for u in data.get("upcoming", []) if u["week"] > last_week]
    nxt = min((u["week"] for u in upcoming), default=None)
    preds = []
    for u in upcoming:
        if u["week"] != nxt:
            continue
        fbs_sides = [x for x in (u["home"], u["away"]) if teams[x]["division"] == "FBS"]
        if not fbs_sides or any(x not in eligible for x in fbs_sides):
            continue  # a prediction would expose an unpublished rating
        p = predict(res, u["home"], u["away"], u["neutral"])
        if p is None:
            continue
        preds.append({"game": u["id"], "date": u["date"][:10], "home": name_of(teams, u["home"]),
                      "away": name_of(teams, u["away"]), "neutral": bool(u["neutral"]),
                      "home_margin": p["margin"], "home_win_prob": phi(p["margin"] / sigma),
                      "possessions": p["poss"], "em_diff_per_drive": p["em_diff_drive"],
                      "hfa_per_drive": p["hfa_drive"]})
    preds.sort(key=lambda x: x["date"])

    meta = {
        "season": cfg["season"], "through_week": last_week,
        "games_used": len(res["games"]),
        "games_with_drives": sum(1 for g in res["games"] if g["drives"]),
        "mu_ppd": res["ppd"]["mu"], "h_per_drive": res["ppd"]["h"],
        "hfa_points": res["hfa_points"], "muT": res["muT"],
        "prior_drives": cfg["prior_drives"], "sigma_points": sigma,
        "net_refs": res["net"].references(), "net_weights": cfg["net_weights"],
        "min_games": cfg["min_games"],
        "eligible": sum(r["eligible"] for r in res["teams"].values()),
        "fbs_teams": len(res["teams"]),
        "solver": {"ppd_iterations": res["ppd"]["iterations"], "ppd_converged": res["ppd"]["converged"],
                   "sr_iterations": res["sr"]["iterations"], "tempo_iterations": res["tempo"]["iterations"]},
        "holdout": {k: holdout[k] for k in ("n", "methods", "sigma", "same_games_vs_market",
                                             "calibration") if k in holdout},
        "excluded_games": [{"game": g["id"], "teams": f"{g['away_name']} at {g['home_name']}",
                            "reason": g["pbp_note"]}
                           for g in res["games"] if g["pbp_note"] and not g["drives"]],
        "data_warnings": [{"game": g["id"], "teams": f"{g['away_name']} at {g['home_name']}",
                           "warning": g["pbp_note"]}
                          for g in res["games"] if g["pbp_note"] and g["drives"]],
    }
    published = [r if r["eligible"] else
                 {k: r[k] for k in ("id", "name", "conference", "W", "L", "games", "eligible")}
                 for r in rows]
    with open(os.path.join(OUT, "ratings.json"), "w") as f:
        json.dump({"meta": meta, "teams": published, "conferences": conferences,
                   "predictions": preds, "names": {k: v.get("name", k) for k, v in teams.items()}},
                  f, indent=1, default=float)
    print(f"{meta['fbs_teams']} FBS teams, {meta['eligible']} eligible, through week {last_week}; "
          f"HFA {meta['hfa_points']:.2f} pts; sigma {sigma:.1f}; NS refs win {meta['net_refs']['win']:.4f} "
          f"loss {meta['net_refs']['loss']:.4f} all {meta['net_refs']['all']:.4f}; "
          f"{len(preds)} predictions for week {nxt}")
    if bad:
        raise SystemExit(f"trace self-check FAILED for: {', '.join(bad)}")
    print(f"trace self-check: every AdjO, AdjD, AdjSR and AdjT reconstructs its stored value "
          f"({len(res['ppd']['O'])} D-I teams); internal derivations: {len(index)}")


if __name__ == "__main__":
    main()
