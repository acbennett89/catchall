"""Print the full derivation of a team's numbers.

    python trace.py "Notre Dame"                    # everything
    python trace.py "Notre Dame" --section network  # just the win values
    python trace.py Alabama --section efficiency
    python trace.py Alabama --drives                # every drive and why it was kept/excluded
    python trace.py Indiana --season 2025           # another season (default: config.json)
    python trace.py Indiana --season 2025 --week 8  # as it stood after week 8 (recomputed)

Sections: schedule, efficiency, success_rate, tempo, factors, luck, situational, discipline, sos,
network. Opponents marked T have a tentative rating (fewer than 5 games; run trace.py on them
normally). Opponents marked * are FCS internal inputs; show one with:
    python trace.py "Idaho State" --internal

--week N reruns the ratings on the games of weeks 1..N only, exactly as build.py does for the
page's weekly views, and prints that week's derivation (a few seconds; nothing is written).
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out", "2026")  # set from --season in main()


def _match(query, items):
    q = query.lower()
    hits = [(i, n) for i, n in items if n.lower() == q] or [(i, n) for i, n in items if q in n.lower()]
    if len(hits) > 1 and hits[0][1].lower() != q:
        sys.exit("ambiguous: " + ", ".join(n for _, n in hits))
    return hits[0][0] if hits else None


def find_team(query, internal=False):
    if internal:
        rated = json.load(open(os.path.join(OUT, "ratings.json"), encoding="utf-8"))["teams"]
        hit = next((t for t in rated if t["name"].lower() == query.lower()), None)
        if hit:
            kind = "rated" if hit.get("eligible") else "tentatively rated"
            sys.exit(f"{hit['name']} is {kind} in {os.path.basename(OUT)}; run without --internal")
        index = json.load(open(os.path.join(OUT, "traces", "internal", "index.json"), encoding="utf-8"))
        tid = _match(query, list(index.items()))
        if tid is None:
            sys.exit(f"no internal derivation for {query!r} (FBS teams have full traces; run without --internal)")
        return json.load(open(os.path.join(OUT, "traces", "internal", f"{tid}.json"), encoding="utf-8"))
    data = json.load(open(os.path.join(OUT, "ratings.json"), encoding="utf-8"))
    tid = _match(query, [(t["id"], t["name"]) for t in data["teams"]])
    if tid is None:
        sys.exit(f"no FBS team matches {query!r}; for an FCS opponent use --internal")
    return json.load(open(os.path.join(OUT, "traces", f"{tid}.json"), encoding="utf-8"))


def recompute(season, week, query, internal):
    """A team's trace as it stood after `week`, rebuilt in memory the way build.py builds the
    weekly views: ratings.rate() over the games of weeks 1..week only."""
    import copy
    from build import finish_rows, internal_trace, team_trace, tentative_note
    from polls import load_polls
    from ratings import load, load_config, rate
    cfg = load_config()
    cfg["season"] = season
    data = load(season)
    last = max(g["week"] for g in data["games"] if g["d1"])
    if not 1 <= week <= last:
        sys.exit(f"{season} has weeks 1-{last}")
    res = rate(copy.deepcopy(data), cfg, through_week=week)
    rows, _ = finish_rows(res, load_polls(season), week)
    eligible = {r["id"] for r in rows if r["eligible"]}
    if internal:
        hit = next((r for r in rows if r["name"].lower() == query.lower()), None)
        if hit:
            kind = "rated" if hit["eligible"] else "tentatively rated"
            sys.exit(f"{hit['name']} is {kind} after week {week}; run without --internal")
        fcs = [(t, data["teams"][t].get("name", t)) for t in res["ppd"]["O"]
               if data["teams"].get(t, {}).get("division") != "FBS"]
        tid = _match(query, fcs)
        if tid is None:
            sys.exit(f"no internal derivation for {query!r} after week {week}")
        return {**internal_trace(tid, res, data["teams"], cfg, eligible), "as_of_week": week, "as_of_last": week == last}
    tid = _match(query, [(r["id"], r["name"]) for r in rows])
    if tid is None:
        sys.exit(f"no FBS team matches {query!r}; for an FCS opponent use --internal")
    tr = team_trace(tid, res, data, cfg, None, eligible)
    if not res["teams"][tid]["eligible"]:
        tr["tentative"], tr["note"] = True, tentative_note(res["teams"][tid], cfg)
    tr["as_of_week"], tr["as_of_last"] = week, week == last
    return tr


def f(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def schedule(tr):
    e = tr["eligibility"]
    print(f"\nELIGIBILITY: {e['games']} games played (rule: {e['min_games']} {e['rule']}) -> "
          f"{'ELIGIBLE' if e['eligible'] else 'NOT ELIGIBLE (not ranked)'}")
    for g in tr["schedule"]:
        flag = "" if g["used_in_efficiency"] else "  [not in efficiency model: " + g["note"] + "]"
        adj = ""
        if g.get("garbage_pts_us") or g.get("garbage_pts_them"):
            adj = (f"  [garbage-adjusted {g['adj_us']:g}-{g['adj_them']:g}: removed {g['garbage_pts_us']:g} "
                   f"of ours, {g['garbage_pts_them']:g} of theirs]")
        ck = g.get("clock") or {}
        clock = (f"clock {'usable' if ck.get('usable') else 'not usable'} ({ck.get('zero', 0)}/{ck.get('cand', 0)} "
                 f"zero readings)" if ck.get("cand") is not None else "")
        bp = g.get("box_penalties") or {}
        pen = f"box penalties {bp.get('us')} vs {bp.get('them')}" if bp else ""
        print(f"  wk{g['week']:>2} {g['date']} {g['site']} {g['result']} {g['us']:>2}-{g['them']:<2} "
              f"{g['opp_name']} ({g['opp_division']}{', conf' if g['conf_game'] else ''}){adj}{flag}")
        if clock or pen:
            print(f"        {clock}; {pen}" + (f"; box rows rejected: {bp['rejected']}" if bp.get("rejected") else ""))


def mark_of(status):
    """T = tentative FBS opponent (its own trace is published); * = FCS internal input."""
    status = status or "published"
    return " T" if status.startswith("tentative") else " *" if status.startswith("internal") else ""


def lines_table(s, label, opp_key, fmt=".3f"):
    print(f"  {label}: adjusted = raw - (opp rating - mu) - h*venue")
    print(f"    {'opponent':22s} {'weight':>6} {'raw':>8} {opp_key:>12} {'opp adj':>8} {'venue':>6} {'adjusted':>9}")
    for ln in s["lines"]:
        mark = mark_of(ln.get("opp_status"))
        print(f"    {(ln['opp_name'][:20] + mark):22s} {ln['w']:>6g} {ln['raw']:>8{fmt}} {ln[opp_key]:>12{fmt}} "
              f"{ln['opp_adjustment']:>+8{fmt}} {ln['hfa_adjustment']:>+6{fmt}} {ln['adjusted']:>9{fmt}}")
    p = s["prior"]
    tot_w = sum(ln["w"] for ln in s["lines"])
    print(f"    {'phantom game (' + p['division'] + ' avg)':22s} {p['weight']:>6} {'':>8} {'':>12} {'':>8} {'':>6} "
          f"{p['value']:>9{fmt}}")
    print(f"    {label} = (sum(weight*adjusted) + {p['weight']}*{p['value']:{fmt}}) / ({tot_w:g} + {p['weight']}) "
          f"= {s['recomputed']:.4f}   [stored {s['stored']:.4f}, check {'OK' if s['check_ok'] else 'FAIL'}]")


def success_rate(tr):
    s = tr.get("success_rate_adjusted")
    if not s:
        return
    print("\nADJUSTED SUCCESS RATE  same model as AdjO/AdjD, play-weighted")
    lines_table(s["offense"], "AdjSR_O", "opp_AdjSR_D" if "opp_AdjSR_D" in (s["offense"]["lines"] or [{}])[0] else "opp_AdjD")
    lines_table(s["defense"], "AdjSR_D", "opp_AdjSR_O" if "opp_AdjSR_O" in (s["defense"]["lines"] or [{}])[0] else "opp_AdjO")


def efficiency(tr):
    e = tr.get("efficiency")
    if not e:
        print("\nEFFICIENCY: no drive data")
        return
    if tr.get("internal"):
        print(f"\nEFFICIENCY (internal input)  mu = {f(e['mu'])}, h = {f(e['h'], 4)}")
        lines_table(e["offense"], "AdjO", "opp_AdjD")
        lines_table(e["defense"], "AdjD", "opp_AdjO")
        print("  * opponent is itself an internal input (FCS); T = tentative FBS opponent")
        return
    print(f"\nEFFICIENCY  mu (FBS avg PPD) = {f(e['mu'])}, home edge h = {f(e['h'], 4)} pts/drive, "
          f"muT = {f(e['muT'], 2)} drives/game")
    for side, opp_key, label in (("offense", "opp_AdjD", "AdjO"), ("defense", "opp_AdjO", "AdjD")):
        s = e[side]
        print(f"  {label}: adjusted = raw - (opp rating - mu) - h*venue")
        print(f"    {'opponent':22s} {'weight':>6} {'raw PPD':>8} {opp_key:>9} {'opp adj':>8} "
              f"{'venue':>6} {'adjusted':>9}")
        for ln in s["lines"]:
            mark = mark_of(ln.get("opp_status"))
            print(f"    {(ln['opp_name'][:20] + mark):22s} {ln['w']:>6g} {ln['raw']:>8.3f} {ln[opp_key]:>9.3f} "
                  f"{ln['opp_adjustment']:>+8.3f} {ln['hfa_adjustment']:>+6.3f} {ln['adjusted']:>9.3f}")
        p = s["prior"]
        tot_w = sum(ln["w"] for ln in s["lines"])
        print(f"    {'phantom game (' + p['division'] + ' avg)':22s} {p['weight']:>6} "
              f"{'':>8} {'':>9} {'':>8} {'':>6} {p['value']:>9.3f}")
        print(f"    {label} = (sum(weight*adjusted) + {p['weight']}*{p['value']:.3f}) / "
              f"({tot_w:g} + {p['weight']}) = {s['recomputed']:.4f}   [stored {s['stored']:.4f}, "
              f"check {'OK' if s['check_ok'] else 'FAIL'}]")
    print("  weight = kept drives, with lead-protection drives at the configured weight")
    print(f"  AdjEM = ({f(e['AdjO'], 4)} - {f(e['AdjD'], 4)}) * {f(e['muT'], 3)} = {f(e['AdjEM'], 2)} "
          f"pts/game vs an average FBS team, neutral field  (+/- {f(e['AdjEM_se'], 1)} SE)")
    print('  T = tentative FBS opponent (fewer than 5 games): python trace.py "<opponent>"')
    print('  * = FCS internal input: python trace.py "<opponent>" --internal')
    print("  game-level adjusted margins (basis of the SE):",
          ", ".join(f"{g['opp_name']} {g['adj_margin_per_game']:+.1f}" for g in e["game_margins"]))


def tempo(tr):
    t = tr.get("tempo")
    if not t:
        return
    print(f"\nTEMPO  AdjT = mean(poss - (opp AdjT - muT)) incl. one phantom game; muT = "
          f"{f(t.get('muT'), 2)}; poss = (both teams' regulation drives with a real snap) / 2")
    for ln in t["lines"]:
        mark = mark_of(ln.get("opp_status"))
        print(f"    {(ln['opp_name'][:20] + mark):22s} poss {ln['poss']:5.1f}  opp AdjT {ln['opp_AdjT']:5.2f}  "
              f"adjusted {ln['adjusted']:5.2f}")
    print(f"    phantom game {t['prior']:.2f} -> AdjT {t['recomputed']:.3f} [check "
          f"{'OK' if t['check_ok'] else 'FAIL'}]")


def factors(tr):
    fa = tr["factors"]
    print("\nFIVE FACTORS (kept drives only)")
    for k, v in fa["definitions"].items():
        print(f"  {k}: {v}")
    tot = {s: {} for s in ("O", "D")}
    for g in fa["games"]:
        for s in ("O", "D"):
            for k, v in g[s].items():
                tot[s][k] = tot[s].get(k, 0) + v
        print(f"  {g['opp_name'][:22]:22s} O: {g['O']['drives']} dr {g['O']['points']} pts "
              f"{g['O']['successes']}/{g['O']['plays']} succ {g['O']['explosive']} expl "
              f"{g['O']['opp_points']}/{g['O']['scoring_opps']} opp-pts | "
              f"D: {g['D']['drives']} dr {g['D']['points']} pts {g['D']['successes']}/{g['D']['plays']} succ "
              f"| TO {g['turnovers_given']}/{g['turnovers_taken']}")
    for s in ("O", "D"):
        t = tot[s]
        if t.get("plays"):
            print(f"  TOTAL {s}: PPD {t['points'] / t['drives']:.3f}  SR {t['successes'] / t['plays']:.3f}  "
                  f"Explosive {t['explosive'] / t['plays']:.3f}  YPP {t['yards'] / t['plays']:.2f}  "
                  f"FieldPos {t['start_yardline_sum'] / t['drives']:.1f}  "
                  f"PtsPerOpp {f(t['opp_points'] / t['scoring_opps'] if t['scoring_opps'] else None, 2)}")


def luck(tr):
    l = tr["luck"]
    e = l["exponent"]
    print(f"\nLUCK  ({l['rule']})")
    print(f"  Pythag = PF^{e} / (PF^{e} + PA^{e}) with garbage-adjusted PF {l['adjPF']:g}, PA {l['adjPA']:g} "
          f"= {f(l['pythag'])};  actual {f(l['actual'])};  luck = {f(l['luck'])}")
    print(f"  raw scores (PF {l['PF']}, PA {l['PA']}): Pythag {f(l['pythag_raw'])}, luck {f(l['luck_raw'])}")


def situational(tr):
    s = tr["situational"]
    print(f"\nSITUATIONAL  neutral pace {f(s['neutral_pace'], 1)} s/snap, neutral run rate "
          f"{f(s['neutral_run_rate'])} over {s['pace_intervals']} clean intervals "
          f"(published at >= {s['min_pace_intervals']}); rule: {s['pace_rule']}")
    lp = s["lead_protection_rule"]
    print(f"  lead protection (Q4, ahead 1-{lp['max_lead']}, usable clock, clean intervals averaging >= own neutral "
          f"pace + {lp['relative_slowdown']} s, capped at {lp['min_mean_secs']} s, over >= {lp['min_intervals']} "
          f"intervals, >= {lp['min_run_share']:.0%} runs of >= {lp['min_plays']} plays): "
          f"{len(s['lead_protection_drives'])} of {s['q4_lead_drives']} Q4 leading drives in "
          f"{s.get('usable_clock_games')} usable-clock games; {s['weight_note']}")
    for d in s["lead_protection_drives"]:
        print(f"    vs {d['opp_name']} drive {d['drive']} ({d['clock']}): {d['reason']}, {d['points']:g} pts; "
              f"intervals {d.get('intervals')}")
    print("  every drive's clean intervals, runs and clock source are in --drives")


def discipline(tr):
    d = tr["discipline"]
    c = d["counts"] or {}
    print(f"\nDISCIPLINE  ({d['rules']['rating']})")
    print(f"  {d['rules']['per_game']}: {f(d['PenPG'], 2)} penalties, {f(d['PenYdsPG'], 1)} yards per game "
          f"(conference {f(d['PenPG_conf'], 2)}); net penalty yards per game {f(d['NetPenYdsPG'], 1)}")
    print(f"  {d['rules']['rates']}:")
    print(f"    offense {c.get('off_fouls')} fouls / {c.get('off_snaps')} snaps = {f(d['OffPen100'], 2)} per 100 "
          f"(conference {f(d['OffPen100_conf'], 2)}); pre-snap {c.get('off_presnap')} = {f(d['OffPreSnap100'], 2)}")
    print(f"    defense {c.get('def_fouls')} fouls / {c.get('def_snaps')} snaps = {f(d['DefPen100'], 2)} per 100 "
          f"(conference {f(d['DefPen100_conf'], 2)}); first downs given {c.get('def_first_downs')} = "
          f"{f(d['PenFDAllowedPG'], 2)} per game")
    for x in d["fouls"]:
        print(f"    vs {x['opp_name'][:16]:16s} Q{x['period']} {x['clock'] or '':>5} {x['category'][:24]:24s} "
              f"{x['penalized_unit']:8s} {x['yards']:>3} yds {x['status']:10s}{' 1st down' if x['first_down_awarded'] else ''} "
              f"[{counted(x)}; {x['dialect']}/{x['yards_method']}]")


def counted(x):
    if x["status"] != "accepted":
        return "not counted: not accepted"
    if x["penalized_unit"] not in ("offense", "defense"):
        return f"not counted: {x['penalized_unit']} unit (special teams)"
    if x["situational"]:
        return "not counted: situational"
    if x["drive_why"] != "":
        return f"not counted: {x['drive_why'] or 'no drive'}"
    return "counted"


def sos(tr):
    s = tr["sos_efficiency"]
    print(f"\nSOS (efficiency) = mean opponent AdjEM = {f(s['SOS'], 2)};  NCSOS = {f(s['NCSOS'], 2)}")
    for o in s["opponents"]:
        mark = {" T": "  T tentative", " *": "  * internal input"}.get(mark_of(o.get("opp_status")), "")
        print(f"    {o['opp_name'][:22]:22s} AdjEM {o['opp_AdjEM']:+6.2f}{'  (conf)' if o['conf_game'] else ''}{mark}")


def network(tr):
    n = tr["network"]
    w = n["weights"]
    rf = n["refs"]
    print(f"\nNETWORK WIN VALUES  NS = {w['primary']}*P + {w['secondary']}*S + {w['tertiary']}*T")
    print(f"  anchors: NS_win {rf['win']:.4f} (mean NS of the beaten team over all {rf['n_wins']} FBS wins -> "
          f"average win = 1.00); NS_loss {rf['loss']:.4f} (mean NS of the winner over all {rf['n_losses']} FBS "
          f"losses -> average loss costs 1.00); NS_all {rf['all']:.4f} (schedule). Inputs: " +
          (f"recomputed for week {tr['as_of_week']} (anchors.json covers the latest week)"
           if tr.get("as_of_week") and not tr.get("as_of_last") else f"{os.path.relpath(OUT, HERE)}/anchors.json"))
    print(f"  record rate = (W + {n['record_prior']['wins']}) / (W + L + "
          f"{n['record_prior']['wins'] + n['record_prior']['losses']}); exclusion rule: {n['exclusion']}")
    for kind, rows in (("WIN", n["wins"]), ("LOSS", n["losses"])):
        for r in rows:
            if r.get("fcs"):
                print(f"\n  {kind} vs {r['opp_name']} (FCS): {r['note']} -> "
                      + (f"value {r['value']:.3f}" if kind == "WIN" else f"cost {r['cost']:.3f}"))
                continue
            t = r["tree"]
            val = (f"value = NS / NS_win = {r['ns']:.4f} / {rf['win']:.4f} = {r['value']:.3f}"
                   if kind == "WIN" else
                   f"cost = (1 - NS) / (1 - NS_loss) = {1 - r['ns']:.4f} / {1 - rf['loss']:.4f} = {r['cost']:.3f}")
            print(f"\n  {kind} vs {r['opp_name']}:  NS = {w['primary']}*{t['P']:.4f} + "
                  f"{w['secondary']}*{t['S']:.4f} + {w['tertiary']}*{t['T']:.4f} = {t['ns']:.4f};  {val}")
            p = t["primary"]
            counted = [g for g in p["games"] if g["counted"]]
            print(f"    PRIMARY   {p['name']}: {p['W']}-{p['L']} -> {p['wp']:.4f}   (games: "
                  + ", ".join(f"{'W' if g['won'] else 'L'} {g['opp_name']}" for g in counted)
                  + "; excluded: " + (", ".join(g["opp_name"] for g in p["games"] if not g["counted"]) or "none")
                  + ")")
            for c in t["secondary"]:
                tm = "—" if c["tertiary_mean"] is None else f"{c['tertiary_mean']:.4f}"
                print(f"    SECONDARY {c['name'][:20]:20s} {c['W']}-{c['L']} -> {c['wp']:.4f}   "
                      f"tertiary mean {tm}: "
                      + ", ".join(f"{d['name']} {d['W']}-{d['L']}" for d in c["tertiary"]))
            if t.get("fallbacks"):
                print(f"    (empty layers set to .500: {t['fallbacks']})")
    print(f"\n  Win Value Total {n['win_value_total']:.3f}  Loss Cost Total {n['loss_cost_total']:.3f}  "
          f"Net Resume {n['net_resume']:+.3f} ({f(n['net_per_game'])} per game)  "
          f"Schedule strength ratio {f(n['schedule_ns_ratio'])} (FCS opponents count as 0)")


def drives(tr):
    d = tr["drives"]
    print("\nDRIVES  " + " | ".join(d["columns"]))
    for r in d["rows"]:
        print("  ", *["" if x is None else x for x in r])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--internal", action="store_true",
                    help="show the internal-input derivation of an FCS opponent")
    ap.add_argument("--section", choices=["schedule", "efficiency", "success_rate", "tempo", "factors", "luck",
                                          "situational", "discipline", "sos", "network"])
    ap.add_argument("--drives", action="store_true")
    ap.add_argument("--season", type=int, help="season (default: config.json); build it first")
    ap.add_argument("--week", type=int, help="the derivation as it stood after this week (recomputed)")
    a = ap.parse_args()
    global OUT
    season = a.season or json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))["season"]
    OUT = os.path.join(HERE, "out", str(season))
    if not os.path.exists(os.path.join(OUT, "ratings.json")):
        sys.exit(f"no ratings for {season}: run python build.py --season {season}")
    if a.week is not None:
        tr = recompute(season, a.week, a.team, a.internal)
        latest = json.load(open(os.path.join(OUT, "ratings.json"), encoding="utf-8"))["meta"]["through_week"]
        print(f"AFTER WEEK {a.week} of {season}: recomputed from the games of weeks 1-{a.week} only "
              "(the page's weekly view). " + (f"This is the latest week: the same as {os.path.relpath(OUT, HERE)}/."
                                              if a.week == latest else
                                              f"Global constants differ from {os.path.relpath(OUT, HERE)}/anchors.json, "
                                              "which covers the latest week."))
    else:
        tr = find_team(a.team, a.internal)
    if tr.get("internal"):
        t = tr["team"]
        print(f"{t['name']} ({t['division']}, {t['conference']})  INTERNAL INPUT\n{tr['note']}")
        efficiency(tr)
        print("\nADJUSTED SUCCESS RATE (internal input)")
        lines_table(tr["success_rate_adjusted"]["offense"], "AdjSR_O", "opp_AdjD")
        lines_table(tr["success_rate_adjusted"]["defense"], "AdjSR_D", "opp_AdjO")
        if tr.get("tempo"):
            tempo(tr)
        return
    s = tr["summary"]
    if tr.get("tentative"):
        print(f"{s['name']} ({s['conference']})  {s['W']}-{s['L']}  TENTATIVE (no official rank)  "
              f"Power (AdjEM) {f(s.get('AdjEM'), 2)}")
        print(tr["note"])
    else:
        print(f"{s['name']} ({s['conference']})  {s['W']}-{s['L']}  rank "
              f"{s.get('rk_AdjEM', 'unranked')}  Power (AdjEM) {f(s.get('AdjEM'), 2)}")
    if a.drives:
        drives(tr)
        return
    sections = {"schedule": schedule, "efficiency": efficiency, "success_rate": success_rate,
                "tempo": tempo, "factors": factors,
                "luck": luck, "situational": situational, "discipline": discipline, "sos": sos,
                "network": network}
    for name, fn in sections.items():
        if a.section in (None, name):
            fn(tr)


if __name__ == "__main__":
    # Python salts string hashes per run, which reorders set iteration and moves float sums in the
    # last bits (about 1e-14). A fixed seed makes every rebuild byte-identical, so the files (and
    # the page's content-hashed data files) change only when a number really does.
    # (A child process rather than os.execv: on Windows execv returns to the caller at once.)
    if os.environ.get("PYTHONHASHSEED") != "0":
        import subprocess
        sys.exit(subprocess.call([sys.executable] + sys.argv, env={**os.environ, "PYTHONHASHSEED": "0"}))
    main()
