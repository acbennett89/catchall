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
from ratings import HERE, load, load_config, phi, predict, rate, venue
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
    ("sec_per_play", "SecPerPlay"), ("pythag", "PythagW%"), ("luck", "Luck"),
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
        schedule.append({"game": g["id"], "week": g["week"], "date": g["date"][:10],
                         "opp": opp, "opp_name": nm(opp),
                         "opp_division": teams.get(opp, {}).get("division"),
                         "site": "N" if g["neutral"] else ("H" if home else "A"),
                         "us": us, "them": them, "result": "W" if us > them else "L",
                         "conf_game": bool(g["conf_game"]),
                         "used_in_efficiency": bool(g["drives"]),
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
        tr["success_rate_adjusted"] = {"mu": sr["mu"], "h": sr["h"], "offense": s["offense"],
                                       "defense": s["defense"]}
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

    tr["luck"] = {"PF": row["PF"], "PA": row["PA"], "exponent": cfg["pythag_exp"],
                  "pythag": row["pythag"], "actual": row["W"] / row["games"] if row["games"] else None,
                  "luck": row["luck"]}

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
                           d["result"], d["pts"], d["margin"], d["kept"], d["why"], len(d["plays"])])
    tr["drives"] = {"columns": ["game", "drive#", "side", "qtr", "clock", "start_yardline",
                                "result", "points", "margin_at_start", "kept", "excluded_reason",
                                "scrimmage_plays"], "rows": drives}
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
    rows = sorted(res["teams"].values(),
                  key=lambda r: (not r["eligible"], r.get("rk_AdjEM") or 999, -(r.get("AdjEM") or -99)))
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
            tr = {"team": tr["team"], "schedule": tr["schedule"], "eligibility": tr["eligibility"],
                  "summary": {k: r[k] for k in ("id", "name", "conference", "W", "L", "games", "eligible")},
                  "note": f"{r['name']} has played {r['games']} of the {cfg['min_games']} games "
                          "required for a rating. Its internal estimate is used only to adjust its "
                          "opponents' numbers and is not published."}
        with open(os.path.join(OUT, "traces", f"{r['id']}.json"), "w") as f:
            json.dump(tr, f, separators=(",", ":"), default=float)

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
    print("trace self-check: every AdjO, AdjD, AdjSR and AdjT reconstructs its stored value")


if __name__ == "__main__":
    main()
