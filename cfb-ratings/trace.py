"""Print the full derivation of a team's numbers.

    python trace.py "Notre Dame"                    # everything
    python trace.py "Notre Dame" --section network  # just the win values
    python trace.py Alabama --section efficiency
    python trace.py Alabama --drives                # every drive and why it was kept/excluded

Sections: schedule, efficiency, tempo, factors, luck, sos, network
"""
import argparse
import json
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))


def find_team(query):
    data = json.load(open(os.path.join(HERE, "out", "ratings.json")))
    q = query.lower()
    hits = [t for t in data["teams"] if t["name"].lower() == q] or \
           [t for t in data["teams"] if q in t["name"].lower()]
    if not hits:
        sys.exit(f"no FBS team matches {query!r}")
    if len(hits) > 1 and hits[0]["name"].lower() != q:
        sys.exit("ambiguous: " + ", ".join(t["name"] for t in hits))
    return json.load(open(os.path.join(HERE, "out", "traces", f"{hits[0]['id']}.json")))


def f(x, nd=3):
    return "—" if x is None else f"{x:.{nd}f}"


def schedule(tr):
    e = tr["eligibility"]
    print(f"\nELIGIBILITY: {e['games']} games played (rule: {e['min_games']} {e['rule']}) -> "
          f"{'ELIGIBLE' if e['eligible'] else 'NOT ELIGIBLE (not ranked)'}")
    for g in tr["schedule"]:
        flag = "" if g["used_in_efficiency"] else "  [not in efficiency model: " + g["note"] + "]"
        print(f"  wk{g['week']:>2} {g['date']} {g['site']} {g['result']} {g['us']:>2}-{g['them']:<2} "
              f"{g['opp_name']} ({g['opp_division']}{', conf' if g['conf_game'] else ''}){flag}")


def efficiency(tr):
    e = tr.get("efficiency")
    if not e:
        print("\nEFFICIENCY: no drive data")
        return
    print(f"\nEFFICIENCY  mu (FBS avg PPD) = {f(e['mu'])}, home edge h = {f(e['h'], 4)} pts/drive, "
          f"muT = {f(e['muT'], 2)} drives/game")
    for side, opp_key, label in (("offense", "opp_AdjD", "AdjO"), ("defense", "opp_AdjO", "AdjD")):
        s = e[side]
        print(f"  {label}: adjusted = raw - (opp rating - mu) - h*venue")
        print(f"    {'opponent':22s} {'drives':>6} {'raw PPD':>8} {opp_key:>9} {'opp adj':>8} "
              f"{'venue':>6} {'adjusted':>9}")
        for ln in s["lines"]:
            print(f"    {ln['opp_name'][:22]:22s} {ln['w']:>6} {ln['raw']:>8.3f} {ln[opp_key]:>9.3f} "
                  f"{ln['opp_adjustment']:>+8.3f} {ln['hfa_adjustment']:>+6.3f} {ln['adjusted']:>9.3f}")
        p = s["prior"]
        tot_w = sum(ln["w"] for ln in s["lines"])
        print(f"    {'phantom game (' + p['division'] + ' avg)':22s} {p['weight']:>6} "
              f"{'':>8} {'':>9} {'':>8} {'':>6} {p['value']:>9.3f}")
        print(f"    {label} = (sum(drives*adjusted) + {p['weight']}*{p['value']:.3f}) / "
              f"({tot_w} + {p['weight']}) = {s['recomputed']:.4f}   [stored {s['stored']:.4f}, "
              f"check {'OK' if s['check_ok'] else 'FAIL'}]")
    print(f"  AdjEM = ({f(e['AdjO'], 4)} - {f(e['AdjD'], 4)}) * {f(e['muT'], 3)} = {f(e['AdjEM'], 2)} "
          f"pts/game vs an average FBS team, neutral field  (+/- {f(e['AdjEM_se'], 1)} SE)")
    print("  game-level adjusted margins (basis of the SE):",
          ", ".join(f"{g['opp_name']} {g['adj_margin_per_game']:+.1f}" for g in e["game_margins"]))


def tempo(tr):
    t = tr.get("tempo")
    if not t:
        return
    print(f"\nTEMPO  AdjT = mean(poss - (opp AdjT - muT)) incl. one phantom game; muT = {f(t['muT'], 2)}")
    for ln in t["lines"]:
        print(f"    {ln['opp_name'][:22]:22s} poss {ln['poss']:5.1f}  opp AdjT {ln['opp_AdjT']:5.2f}  "
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
    print(f"\nLUCK  Pythag = PF^{l['exponent']} / (PF^{l['exponent']} + PA^{l['exponent']}) with "
          f"PF {l['PF']}, PA {l['PA']} = {f(l['pythag'])};  actual {f(l['actual'])};  "
          f"luck = {f(l['luck'])}")


def sos(tr):
    s = tr["sos_efficiency"]
    print(f"\nSOS (efficiency) = mean opponent AdjEM = {f(s['SOS'], 2)};  NCSOS = {f(s['NCSOS'], 2)}")
    for o in s["opponents"]:
        print(f"    {o['opp_name'][:22]:22s} AdjEM {o['opp_AdjEM']:+6.2f}{'  (conf)' if o['conf_game'] else ''}")


def network(tr):
    n = tr["network"]
    w = n["weights"]
    print(f"\nNETWORK WIN VALUES  NS = {w['primary']}*P + {w['secondary']}*S + {w['tertiary']}*T; "
          f"NS_ref = {n['ns_ref']:.4f} (average FBS opponent)")
    print(f"  record rate = (W + {n['record_prior']['wins']}) / (W + L + "
          f"{n['record_prior']['wins'] + n['record_prior']['losses']}); exclusion rule: {n['exclusion']}")
    for kind, rows in (("WIN", n["wins"]), ("LOSS", n["losses"])):
        for r in rows:
            if r.get("fcs"):
                print(f"\n  {kind} vs {r['opp_name']} (FCS): {r['note']} -> "
                      + (f"value {r['value']:.3f}" if kind == "WIN" else f"cost {r['cost']:.3f}"))
                continue
            t = r["tree"]
            val = (f"value = NS / NS_ref = {r['ns']:.4f} / {n['ns_ref']:.4f} = {r['value']:.3f}"
                   if kind == "WIN" else
                   f"cost = (1 - NS) / (1 - NS_ref) = {1 - r['ns']:.4f} / {1 - n['ns_ref']:.4f} = {r['cost']:.3f}")
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
          f"Net Resume {n['net_resume']:+.3f}  Schedule strength ratio {f(n['schedule_ns_ratio'])}")


def drives(tr):
    d = tr["drives"]
    print("\nDRIVES  " + " | ".join(d["columns"]))
    for r in d["rows"]:
        print("  ", *["" if x is None else x for x in r])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("team")
    ap.add_argument("--section", choices=["schedule", "efficiency", "tempo", "factors", "luck",
                                          "sos", "network"])
    ap.add_argument("--drives", action="store_true")
    a = ap.parse_args()
    tr = find_team(a.team)
    s = tr["summary"]
    print(f"{s['name']} ({s['conference']})  {s['W']}-{s['L']}  rank "
          f"{s.get('rk_AdjEM', 'unranked')}  AdjEM {f(s.get('AdjEM'), 2)}")
    if a.drives:
        drives(tr)
        return
    sections = {"schedule": schedule, "efficiency": efficiency, "tempo": tempo, "factors": factors,
                "luck": luck, "sos": sos, "network": network}
    for name, fn in sections.items():
        if a.section in (None, name):
            fn(tr)


if __name__ == "__main__":
    main()
