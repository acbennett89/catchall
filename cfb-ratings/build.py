"""Build the published ratings and a full derivation trace for every FBS team.

    python build.py [--season 2025]      (default: config.json "season")
      out/<season>/ratings.csv               one row per FBS team (5+ games ranked; fewer = tentative, unranked)
      out/<season>/ratings.json              same rows + model constants, conferences, predictions
      out/<season>/traces/<id>.json          every number for one team, back to drives and plays
      out/<season>/traces/internal/<id>.json derivations of internal inputs (FCS teams)
      out/<season>/anchors.json              every input to the global constants
      out/<season>/weekly.json               the table as it stood after each week, the next week's
                                             picks with results, and each team's week-by-week line

AP and CFP ranks (data/<season>/polls.json, from python polls.py) ride along on every table for
reference; they never enter a rating.
"""
import argparse
import copy
import csv
import json
import math
import os
import sys
from collections import defaultdict

from datetime import datetime
from zoneinfo import ZoneInfo

from audit_penalties import audit
from efficiency import trace, trace_tempo
from polls import latest as latest_poll, load_polls
from ratings import (DISCIPLINE_KEYS, HERE, comparison_pool, drive_weight, good_clock,
                     is_situational_foul, load, load_config, phi, predict, rate, venue)
from validate import evaluate


COLUMNS = [
    ("rk_AdjEM", "Rk"), ("name", "Team"), ("conference", "Conf"), ("W", "W"), ("L", "L"),
    ("games", "G"), ("eligible", "Eligible"), ("status", "Status"), ("AP", "AP_rank"), ("CFP", "CFP_rank"),
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
    ("PenCoverage", "PenCoverage_parsed_vs_box"),
    ("SOS", "SOS_AdjEM"), ("rk_SOS", "SOS_Rk"), ("NCSOS", "NCSOS_AdjEM"),
    ("OppO", "Opp_AdjO"), ("OppD", "Opp_AdjD"),
    ("WVT", "WinValueTotal"), ("AvgWV", "AvgWinValue"), ("LCT", "LossCostTotal"),
    ("NetResume", "NetResume"), ("NetPerGame", "NetResumePerGame"), ("rk_NetPerGame", "Resume_Rk"),
    ("SchedNS", "SchedStrengthRatio"),
    ("BestWin", "BestWinValue"), ("BestWinOpp", "BestWinOpp"),
    ("WorstLoss", "WorstLossCost"), ("WorstLossOpp", "WorstLossOpp"),
]


# What the page's tables need from each row of a weekly snapshot (the full row lives in ratings.json).
WEEK_FIELDS = (
    "id", "name", "conference", "W", "L", "games", "eligible", "tentative", "status", "AP", "CFP",
    "slot_AdjEM", "slot_NetPerGame", "AdjEM", "AdjEM_se", "rk_AdjEM", "AdjO", "rk_AdjO", "AdjD",
    "rk_AdjD", "AdjT", "SOS", "rk_SOS", "NCSOS", "luck", "WVT", "AvgWV", "LCT", "NetResume",
    "NetPerGame", "rk_NetPerGame", "SchedNS", "BestWin", "BestWinOpp", "WorstLoss", "WorstLossOpp",
    "PenPG", "PenPG_conf", "PenYdsPG", "PenYdsPG_conf", "NetPenYdsPG", "OffPen100", "OffPen100_conf",
    "OffPreSnap100", "OffPreSnap100_conf", "DefPen100", "DefPen100_conf", "PenFDAllowedPG",
    "PenCoverage", "NeutralPace", "NeutralRunRate", "LP_drives", "Q4_lead_drives")
# One line per team per week in the history: these columns, in this order.
HISTORY_COLUMNS = ["week", "W", "L", "AdjEM", "rk_AdjEM", "slot_AdjEM", "NetPerGame", "rk_NetPerGame",
                   "slot_NetPerGame", "AP", "CFP"]


def finish_rows(res, polls, week):
    """Status, tentative slots and poll ranks for one table. Returns the rows sorted for display
    and {"polls": the polls used, "slot_base": what each slot is counted against}.

    Teams with 5+ games are rated and ranked. Teams below the minimum get a TENTATIVE rating: the
    same numbers, published and traced, but provisional and never ranked. slot_<metric> says where
    a tentative team would sit: among the ranked teams once they are at least half of the teams
    with a value ("ranked"), otherwise among every team with a value ("all"; the first weeks of a
    season). See ratings.comparison_pool. A team with no value of the metric gets no slot."""
    rows = list(res["teams"].values())
    for r in rows:
        r["tentative"] = not r["eligible"]
        r["status"] = "rated" if r["eligible"] else "tentative"
    slot_base = {}
    for metric in ("AdjEM", "NetPerGame"):
        pool = comparison_pool(rows, metric)
        slot_base[metric] = "ranked" if all(r["eligible"] for r in pool) else "all"
        for r in rows:
            if r["eligible"] or r.get(metric) is None:
                r.pop(f"slot_{metric}", None)
                continue
            r[f"slot_{metric}"] = 1 + sum(1 for x in pool if x is not r and x[metric] > r[metric])
    used = {}
    for kind in ("AP", "CFP"):
        p = latest_poll(polls, kind, week)
        ranks = {x["team"]: x["rank"] for x in p["ranks"]} if p else {}
        for r in rows:
            r[kind] = ranks.get(r["id"])
        used[kind] = p and {"after_week": p["after_week"], "released": p["released"],
                            "espn_week": p["espn"]["week"], "headline": p["espn"]["headline"]}
    rows.sort(key=lambda r: (not r["eligible"], r.get("rk_AdjEM") or 999,
                             -(r.get("AdjEM") if r.get("AdjEM") is not None else -999), r["name"]))
    return rows, {"polls": used, "slot_base": slot_base}


def snapshot(res, week, data, cfg, sigma, polls):
    """The table as it stood after `week`, plus the next week's games as the model saw them then
    (prediction from these ratings, and the actual score)."""
    teams = data["teams"]
    rows, info = finish_rows(res, polls, week)
    eligible = {r["id"] for r in rows if r["eligible"]}
    picks, skipped = [], []
    for g in sorted((g for g in data["games"] if g["week"] == week + 1 and g["d1"]), key=lambda g: g["date"]):
        fbs_sides = [x for x in (g["home"], g["away"]) if teams[x]["division"] == "FBS"]
        if not fbs_sides:
            continue
        p = predict(res, g["home"], g["away"], g["neutral"])
        if p is None:  # a team with no rating yet (no game with usable play-by-play)
            skipped.append({"game": g["id"], "home": name_of(teams, g["home"]), "away": name_of(teams, g["away"])})
            continue
        picks.append({"game": g["id"], "date": eastern_date(g["date"]), "home": name_of(teams, g["home"]),
                      "away": name_of(teams, g["away"]), "neutral": bool(g["neutral"]),
                      "tentative": any(x not in eligible for x in fbs_sides),
                      "home_margin": p["margin"], "home_win_prob": phi(p["margin"] / sigma),
                      "possessions": p["poss"], "home_pts": g["home_pts"], "away_pts": g["away_pts"]})
    meta = {"week": week, "last_game_date": eastern_date(max(g["date"] for g in res["games"])),
            "games_used": len(res["games"]), "games_with_drives": sum(1 for g in res["games"] if g["drives"]),
            "eligible": len(eligible), **rating_counts(rows),
            "fbs_teams": len(rows), "min_games": cfg["min_games"], "mu_ppd": res["ppd"]["mu"],
            "muT": res["muT"], "hfa_points": res["hfa_points"], "net_refs": res["net"].references(),
            "net_weights": cfg["net_weights"], **info}
    return {"week": week, "meta": meta, "teams": [{k: r.get(k) for k in WEEK_FIELDS} for r in rows],
            "picks": picks, "picks_skipped": skipped}


def rating_counts(rows):
    """Tentative = rated but under the game minimum; unrated = no rating at all yet (no game with
    usable play-by-play), which happens only in a season's first weeks."""
    return {"tentative": sum(1 for r in rows if not r["eligible"] and r.get("AdjEM") is not None),
            "unrated": sum(1 for r in rows if r.get("AdjEM") is None)}


def history(snaps, polls):
    """team id -> one line per week (HISTORY_COLUMNS), and the preseason AP poll."""
    out = defaultdict(list)
    for s in snaps:
        for r in s["teams"]:
            out[r["id"]].append([s["week"]] + [r.get(k) for k in HISTORY_COLUMNS[1:]])
    pre = latest_poll(polls, "AP", 0)
    return {"columns": HISTORY_COLUMNS, "teams": dict(out),
            "preseason_AP": {x["team"]: x["rank"] for x in pre["ranks"]} if pre else {},
            "preseason_AP_released": pre and pre["released"]}


def name_of(teams, t):
    return teams.get(t, {}).get("name", t)


def opp_status(opp, teams, eligible):
    """How an opponent's rating may be shown inside another team's trace."""
    if teams.get(opp, {}).get("division") != "FBS":
        return "internal: FCS team (FCS teams are rated only to adjust FBS numbers)"
    if opp not in eligible:
        return "tentative: FBS team below the game minimum (provisional rating, no official rank)"
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
                            PenCoverage=row.get("PenCoverage"), counts=row.get("pen_counts"), fouls=fouls,
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


def internal_trace(t, res, teams, cfg, eligible):
    """An internal input's own lines (an FCS team is rated only to adjust FBS numbers)."""
    e, s_ = trace(res["ppd"], t), trace(res["sr"], t)
    tt = trace_tempo(res["tempo"], t) if t in res["tempo"]["T"] else None
    checks = [e["offense"]["check_ok"], e["defense"]["check_ok"], s_["offense"]["check_ok"],
              s_["defense"]["check_ok"]] + ([tt["check_ok"]] if tt else [])
    for ln in e["offense"]["lines"] + e["defense"]["lines"] + s_["offense"]["lines"] + \
            s_["defense"]["lines"] + (tt["lines"] if tt else []):
        ln["opp_name"] = name_of(teams, ln["opp"])
        ln["opp_status"] = opp_status(ln["opp"], teams, eligible)
    div = teams.get(t, {}).get("division")
    return {"team": {"id": t, "name": name_of(teams, t), "division": div,
                     "conference": teams.get(t, {}).get("conference")},
            "internal": True,
            "note": ("Internal input, not a published rating: " +
                     ("FCS teams are rated only to adjust FBS numbers." if div == "FCS" else
                      f"fewer than {cfg['min_games']} games played.") +
                     " These lines exist so every rated team's numbers can be traced to the end."),
            "checks_ok": all(checks),
            "efficiency": {"mu": res["ppd"]["mu"], "h": res["ppd"]["h"],
                           "offense": e["offense"], "defense": e["defense"]},
            "success_rate_adjusted": {"offense": s_["offense"], "defense": s_["defense"]},
            "tempo": tt}


def tentative_note(r, cfg):
    return (f"Tentative: {r['name']} has played {r['games']} of the {cfg['min_games']} games "
            "a full rating needs. These numbers use the same model and are fully traced, "
            "but rest on few games, so they are provisional and carry no official rank.")


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


def data_coverage(games, teams):
    """How complete ESPN's play-by-play is this season, for the page's coverage line."""
    fbs = [g for g in games if "FBS" in (teams[g["home"]]["division"], teams[g["away"]]["division"])]
    drives = [d for g in fbs for d in g["drives"] if d["kept"]]
    return {"d1_games": len(games), "d1_with_drives": sum(1 for g in games if g["drives"]),
            "fbs_games": len(fbs), "fbs_with_drives": sum(1 for g in fbs if g["drives"]),
            # Snap time read from the "(MM:SS)" stamp; otherwise ESPN's end-of-play clock (METRICS 1.5, 7.1).
            "stamp_share": sum(d["clock_src"] == "stamp" for d in drives) / len(drives) if drives else None}


def eastern_date(iso):
    """ESPN stamps kickoffs in UTC; a late kickoff is the previous day on the US calendar."""
    return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ZoneInfo("America/New_York")).date().isoformat()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--season", type=int, help="season to build (default: config.json)")
    args = ap.parse_args()
    cfg = load_config()
    if args.season:
        cfg["season"] = args.season
    out_dir = os.path.join(HERE, "out", str(cfg["season"]))
    data = load(cfg["season"])
    res = rate(copy.deepcopy(data), cfg)
    teams = data["teams"]

    # out-of-sample sigma for win probabilities: this season's walk-forward weeks
    last_week = max(g["week"] for g in data["games"] if g["d1"])
    holdout = evaluate(cfg["season"], range(3, last_week + 1), cfg, "walk-forward")
    sigma = holdout["sigma"]

    os.makedirs(os.path.join(out_dir, "traces"), exist_ok=True)
    polls = load_polls(cfg["season"])
    rows, table_info = finish_rows(res, polls, last_week)
    with open(os.path.join(out_dir, "ratings.csv"), "w", newline="") as f:
        w = csv.writer(f)
        w.writerow([c for _, c in COLUMNS])
        for r in rows:
            out = []
            for k, _ in COLUMNS:
                v = r.get(k)
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
            tr["tentative"], tr["note"] = True, tentative_note(r, cfg)
        with open(os.path.join(out_dir, "traces", f"{r['id']}.json"), "w") as f:
            json.dump(tr, f, separators=(",", ":"), default=float)

    # Internal-input derivations. Every FCS team appears as an opponent in some FBS team's
    # trace; its own lines are written here, labeled, with no AdjEM, rank or resume, so each
    # FBS number traces to the end. (Tentative FBS teams have full traces of their own.)
    idir = os.path.join(out_dir, "traces", "internal")
    os.makedirs(idir, exist_ok=True)
    index = {}
    for t in res["ppd"]["O"]:
        tr = internal_trace(t, res, teams, cfg, eligible)
        if not tr["checks_ok"]:
            bad.append(name_of(teams, t))
        if teams.get(t, {}).get("division") == "FBS":
            continue
        index[t] = name_of(teams, t)
        with open(os.path.join(idir, f"{t}.json"), "w") as f:
            json.dump(tr, f, separators=(",", ":"), default=float)
    with open(os.path.join(idir, "index.json"), "w") as f:
        json.dump(index, f)

    # Anchors: every input to the global constants, so they can be recomputed.
    ppd_ = res["ppd"]
    net_rows = []
    for a in res["net"].fbs:
        for b, won, gid in res["net"].fbs_games[a]:
            net_rows.append([gid, a, b, int(won), res["net"].strength(b, a)["ns"]])
    with open(os.path.join(out_dir, "anchors.json"), "w") as f:
        json.dump({
            "mu": {"value": ppd_["mu"], "rule": "mean AdjO over all FBS teams (= mean FBS AdjD); "
                                               "includes tentative teams below the game minimum"},
            "teams": [{"id": t, "name": name_of(teams, t), "division": ppd_["division"][t],
                       "AdjO": ppd_["O"][t], "AdjD": ppd_["D"][t],
                       "status": "published" if t in eligible else
                                 "tentative" if teams[t]["division"] == "FBS" else "internal"}
                      for t in sorted(ppd_["O"])],
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
        if not fbs_sides:
            continue
        p = predict(res, u["home"], u["away"], u["neutral"])
        if p is None:
            continue
        preds.append({"game": u["id"], "date": eastern_date(u["date"]), "home": name_of(teams, u["home"]),
                      "away": name_of(teams, u["away"]), "neutral": bool(u["neutral"]),
                      "tentative": any(x not in eligible for x in fbs_sides),
                      "home_margin": p["margin"], "home_win_prob": phi(p["margin"] / sigma),
                      "possessions": p["poss"], "em_diff_per_drive": p["em_diff_drive"],
                      "hfa_per_drive": p["hfa_drive"]})
    preds.sort(key=lambda x: x["date"])

    # Weekly views: the table as it stood after each week, each from its own rate() run over the
    # games through that week only (the last week is the table above).
    snaps = []
    for w in range(1, last_week + 1):
        rw = res if w == last_week else rate(copy.deepcopy(data), cfg, through_week=w)
        snaps.append(snapshot(rw, w, data, cfg, sigma, polls))
    with open(os.path.join(out_dir, "weekly.json"), "w") as f:
        json.dump({"season": cfg["season"],
                   "rule": "week w = ratings.rate(data, cfg, through_week=w): every number from the games of "
                           "weeks 1..w only. AP/CFP = the newest poll reflecting games through week w "
                           "(data/<season>/polls.json); reference only. picks = week w+1 games predicted "
                           "from week w's ratings, with the actual score.",
                   "weeks": snaps, "history": history(snaps, polls)}, f, separators=(",", ":"), default=float)

    cal = data.get("calendar", {})
    meta = {
        "season": cfg["season"], "through_week": last_week,
        # Final only when every week on ESPN's regular-season calendar was downloaded and no game
        # is left to play; otherwise the page says "through week N".
        "regular_season_complete": bool(not upcoming and cal.get("regular_season_weeks")
                                        and max(cal.get("weeks_fetched") or [0]) >= cal["regular_season_weeks"]),
        "calendar": cal,
        "last_game_date": eastern_date(max(g["date"] for g in res["games"])),
        # Parsed play-by-play fouls vs ESPN box scores, this season (python audit_penalties.py).
        "penalty_audit": audit(cfg["season"])[0],
        "data_coverage": data_coverage(res["games"], teams),
        "excluded_postseason": data.get("excluded_postseason", []),
        "games_used": len(res["games"]),
        "games_with_drives": sum(1 for g in res["games"] if g["drives"]),
        "mu_ppd": res["ppd"]["mu"], "h_per_drive": res["ppd"]["h"],
        "hfa_points": res["hfa_points"], "muT": res["muT"],
        "prior_drives": cfg["prior_drives"], "sigma_points": sigma,
        "net_refs": res["net"].references(), "net_weights": cfg["net_weights"],
        "min_games": cfg["min_games"],
        **table_info, "weeks": [s["week"] for s in snaps],
        "eligible": sum(r["eligible"] for r in res["teams"].values()),
        **rating_counts(rows),
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
    newest_ap = latest_poll(polls, "AP", last_week)
    if polls and not meta["regular_season_complete"] and (not newest_ap or newest_ap["after_week"] < last_week):
        print(f"note: the newest AP poll in data/{cfg['season']}/polls.json follows week "
              f"{newest_ap and newest_ap['after_week']}; once ESPN releases the poll that follows week "
              f"{last_week}, run python polls.py --season {cfg['season']} and rebuild")
    published = rows
    with open(os.path.join(out_dir, "ratings.json"), "w") as f:
        json.dump({"meta": meta, "teams": published, "conferences": conferences,
                   "predictions": preds, "names": {k: v.get("name", k) for k, v in teams.items()}},
                  f, indent=1, default=float)
    print(f"{meta['fbs_teams']} FBS teams, {meta['eligible']} eligible, through week {last_week}; "
          f"HFA {meta['hfa_points']:.2f} pts; sigma {sigma:.1f}; NS refs win {meta['net_refs']['win']:.4f} "
          f"loss {meta['net_refs']['loss']:.4f} all {meta['net_refs']['all']:.4f}; "
          f"{len(preds)} predictions for week {nxt}; weekly views for weeks 1-{last_week}"
          + ("" if polls else "; no polls (run python polls.py)"))
    if bad:
        raise SystemExit(f"trace self-check FAILED for: {', '.join(bad)}")
    print(f"trace self-check: every AdjO, AdjD, AdjSR and AdjT reconstructs its stored value "
          f"({len(res['ppd']['O'])} D-I teams); internal derivations: {len(index)}")


if __name__ == "__main__":
    # Python salts string hashes per run, which reorders set iteration and moves float sums in the
    # last bits (about 1e-14). A fixed seed makes every rebuild byte-identical, so the files (and
    # the page's content-hashed data files) change only when a number really does.
    if os.environ.get("PYTHONHASHSEED") != "0":
        os.environ["PYTHONHASHSEED"] = "0"
        os.execv(sys.executable, [sys.executable] + sys.argv)
    main()
