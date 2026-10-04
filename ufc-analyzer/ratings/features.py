"""Matchup features for the ratings predictor: antisymmetric in the two fighters (swapping them flips
every sign), so a model with no intercept gives P(A) = 1 - P(B) exactly.

Groups are named so ablations can switch whole groups off (ring rust, momentum, cardio, ...).

  margins_mult  expected output of A on B minus B on A, per dimension: rbar x (O_A D_B - O_B D_A).
                The native style interaction (a wrestler's takedowns against this opponent's takedown
                defense), in natural units per minute.
  margins_add   rbar x ((O_A - O_B) - (D_A - D_B)): the additive alternative, kept if it tests better.
  composite     AdjEM, AdjO and AdjD differences (cage points per 15).
  results       Bradley-Terry strength (results only) and the performance-implied win share.
"""
import math

from ratings.efficiency import DIMS

DIM_KEYS = [d[0] for d in DIMS]
_log = lambda v: math.log(max(v, 1e-6))

PER_FIGHTER = [
    # --- composites and results
    ("adjem", "composite", lambda P: P["eff"]["adjem"]),
    ("adjo", "composite", lambda P: P["eff"]["adjo"]),
    ("adjd", "composite", lambda P: -P["eff"]["adjd"]),
    ("bt", "results", lambda P: P["eff"]["bt"]),
    ("pyth_share", "results", lambda P: P["eff"]["pyth_share"]),
    ("sos", "schedule", lambda P: P["eff"]["sos"]),
    ("luck", "schedule", lambda P: P["eff"]["luck"]),
    ("log_eff_min", "schedule", lambda P: math.log1p(P["eff"]["eff_min"])),
    # --- raw striking
    ("str_diff", "striking", lambda P: P["str_diff"]),
    ("sig_acc", "striking", lambda P: P["sig_acc"]),
    ("sig_def", "striking", lambda P: P["sig_def"]),
    ("kd_15", "striking", lambda P: P["kd_15"]),
    ("kd_abs_15", "durability", lambda P: -P["kd_abs_15"]),
    ("head_abs_15", "durability", lambda P: -P["head_abs_15"]),
    ("dist_net", "striking", lambda P: P["dist_net"]),
    # --- raw grappling
    ("td_15", "grappling", lambda P: P["td_15"]),
    ("td_acc", "grappling", lambda P: P["td_acc"]),
    ("td_def", "grappling", lambda P: P["td_def"]),
    ("ctrl_diff", "grappling", lambda P: P["ctrl_diff"]),
    ("sub_15", "grappling", lambda P: P["sub_15"]),
    ("ground_15", "grappling", lambda P: P["ground_15"]),
    # --- durability and finishing
    ("ko_loss_share", "durability", lambda P: -P["ko_loss_share"]),
    ("finished_share", "durability", lambda P: -P["finished_share"]),
    ("ko_losses_3y", "durability", lambda P: -P["ko_losses_3y"]),
    ("finish_rate", "finishing", lambda P: P["finish_rate"]),
    ("ko_15", "finishing", lambda P: P["ko_15"]),
    ("dec_win_pct", "judging", lambda P: P["dec_win_pct"]),
    ("win_pct", "record", lambda P: P["win_pct"]),
    # --- pace and cardio (round data)
    ("pace", "pace", lambda P: P["pace"]),
    ("fade", "cardio", lambda P: P["fade"]),
    ("opp_fade", "cardio", lambda P: -P["opp_fade"]),
    ("late_diff", "cardio", lambda P: P["late_diff"]),
    ("champ_round_min", "cardio", lambda P: math.log1p(P["champ_round_min"])),
    # --- physical
    ("age", "physical", lambda P: P["age"]),
    ("age_over_32", "physical", lambda P: max(0.0, P["age"] - 32) if P["age"] else 0.0),
    ("age_under_25", "physical", lambda P: max(0.0, 25 - P["age"]) if P["age"] else 0.0),
    ("reach", "physical", lambda P: P["reach"]),
    ("height", "physical", lambda P: P["height"]),
    ("ape", "physical", lambda P: P["ape"]),
    ("southpaw", "physical", lambda P: 1.0 if P["stance"] == "southpaw" else 0.0),
    ("switch", "physical", lambda P: 1.0 if P["stance"] == "switch" else 0.0),
    # --- experience and schedule
    ("log_ufc_fights", "experience", lambda P: math.log1p(P["ufc_fights"])),
    ("log_pro_fights", "experience", lambda P: math.log1p(P["pro_fights"])),
    ("outside_win_pct", "experience", lambda P: (P["outside_win_pct"] - 0.75) * P["outside_known"] * max(0.0, 1 - P["ufc_fights"] / 4)),
    ("outside_finish", "experience", lambda P: (P["outside_finish_share"] - 0.5) * P["outside_known"] * max(0.0, 1 - P["ufc_fights"] / 4)),
    ("title_fights", "experience", lambda P: math.log1p(P["title_fights"])),
    ("five_round_fights", "experience", lambda P: math.log1p(P["five_round_fights"])),
    ("debut", "experience", lambda P: P["debut"]),
    # --- ring rust
    ("log_layoff", "rust", lambda P: P["log_layoff"]),
    ("layoff_over_1y", "rust", lambda P: 1.0 if (P["layoff_days"] or 0) > 365 else 0.0),
    ("layoff_over_2y", "rust", lambda P: 1.0 if (P["layoff_days"] or 0) > 730 else 0.0),
    ("layoff_vs_usual", "rust", lambda P: math.log(P["layoff_vs_usual"]) if P["layoff_vs_usual"] else 0.0),
    ("fights_24m", "rust", lambda P: P["fights_24m"]),
    ("off_ko_loss", "rust", lambda P: P["off_ko_loss"]),
    ("off_loss", "rust", lambda P: P["off_loss"]),
    ("age_x_layoff", "rust", lambda P: (max(0.0, (P["age"] or 30) - 32)) * (1.0 if (P["layoff_days"] or 0) > 365 else 0.0)),
    # --- momentum
    ("last5_wins", "momentum", lambda P: (P["last5_wins"] - 0.5 * P["last5_n"])),
    ("streak", "momentum", lambda P: max(-5, min(5, P["streak"]))),
    ("last3_finishes", "momentum", lambda P: P["last3_finishes"]),
    ("str_diff_trend", "momentum", lambda P: P["str_diff_trend"]),
    ("sos_last3", "momentum", lambda P: P["eff"]["sos_last3"]),
]

MARGIN_DIMS = [k for k in DIM_KEYS if k not in ("fin", "pow")] + ["fin", "pow"]
FEATURES = [n for n, _, _ in PER_FIGHTER] + ["mult_" + k for k in MARGIN_DIMS] + ["add_" + k for k in MARGIN_DIMS]
GROUP = {n: g for n, g, _ in PER_FIGHTER}
GROUP.update({"mult_" + k: "margins_mult" for k in MARGIN_DIMS})
GROUP.update({"add_" + k: "margins_add" for k in MARGIN_DIMS})


def matchup(A, B, rounds=3, title=False):
    """Antisymmetric feature vector for A vs B."""
    x = {}
    for name, _, fn in PER_FIGHTER:
        va, vb = fn(A), fn(B)
        x[name] = 0.0 if va is None or vb is None else float(va) - float(vb)   # unknown on either side: no information
    ea, eb = A["eff"].get("exp_on_opp") or {}, B["eff"].get("exp_on_opp") or {}
    rb = A["eff"].get("rb") or {}
    for k in MARGIN_DIMS:
        x["mult_" + k] = (ea.get(k, 0.0) - eb.get(k, 0.0)) * (15.0 if k != "pow" else 100.0)
        x["add_" + k] = rb.get(k, 0.0) * ((A["eff"]["O"][k] - B["eff"]["O"][k]) - (A["eff"]["D"][k] - B["eff"]["D"][k])) * (15.0 if k != "pow" else 100.0)
    # context terms: a symmetric context times an antisymmetric difference stays antisymmetric
    five = 1.0 if rounds >= 5 else 0.0
    x["five_x_cardio"] = five * (x["fade"] + x["champ_round_min"])
    x["five_x_adjem"] = five * x["adjem"]
    return x


ALL_FEATURES = FEATURES + ["five_x_cardio", "five_x_adjem"]
GROUP["five_x_cardio"] = "cardio"
GROUP["five_x_adjem"] = "composite"
