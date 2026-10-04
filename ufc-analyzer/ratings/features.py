"""Matchup features for the ratings predictor: differences (A minus B) of the per-fighter metrics, so
the model is antisymmetric (swapping the fighters flips every sign), plus a few interaction terms
(style vs style) that are also built to flip sign.

Groups are named so ablations can switch whole groups off (ring rust, momentum, cardio, physical...).
"""
import math

# (feature name, group, function of one fighter's profile P -> number or None)
_log = lambda v: math.log(max(v, 1e-6))

PER_FIGHTER = [
    # --- opponent-adjusted ratings (the KenPom core)
    ("rating", "adjusted", lambda P: P["adj"].get("rating")),
    ("adj_sig_o", "adjusted", lambda P: P["adj"].get("adj_sig_o")),
    ("adj_sig_d", "adjusted", lambda P: -(P["adj"].get("adj_sig_d") or 0) if P["adj"] else None),
    ("adj_head_o", "adjusted", lambda P: P["adj"].get("adj_head_o")),
    ("adj_head_d", "adjusted", lambda P: -(P["adj"].get("adj_head_d") or 0) if P["adj"] else None),
    ("adj_kd_o", "adjusted", lambda P: P["adj"].get("adj_kd_o")),
    ("adj_kd_d", "adjusted", lambda P: -(P["adj"].get("adj_kd_d") or 0) if P["adj"] else None),
    ("adj_td_o", "adjusted", lambda P: P["adj"].get("adj_td_o")),
    ("adj_td_d", "adjusted", lambda P: -(P["adj"].get("adj_td_d") or 0) if P["adj"] else None),
    ("adj_ctrl_o", "adjusted", lambda P: P["adj"].get("adj_ctrl_o")),
    ("adj_ctrl_d", "adjusted", lambda P: -(P["adj"].get("adj_ctrl_d") or 0) if P["adj"] else None),
    ("adj_sub_o", "adjusted", lambda P: P["adj"].get("adj_sub_o")),
    ("adj_sub_d", "adjusted", lambda P: -(P["adj"].get("adj_sub_d") or 0) if P["adj"] else None),
    ("sos", "schedule", lambda P: P["adj"].get("sos")),
    ("luck", "schedule", lambda P: P["adj"].get("luck")),
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
    ("sos_last3", "momentum", lambda P: P["adj"].get("sos_last3")),
]

# interaction terms: f(A, B) - f(B, A), so they flip sign with the orientation
def _wrestler_vs_td_def(A, B):
    return A["adj"].get("adj_td_o", 0) * (1 - B["td_def"])

def _volume_vs_defense(A, B):
    return A["attempts_pm"] * (1 - B["sig_def"])

def _power_vs_chin(A, B):
    return A["kd_15"] * B["ko_loss_share"]

def _sub_vs_ground(A, B):
    return A["sub_15"] * B["share_ground"]

def _reach_vs_dist(A, B):
    return ((A["reach"] or 0) - (B["reach"] or 0)) * (A["share_dist"] + B["share_dist"]) / 2 if A["reach"] and B["reach"] else 0.0

INTERACTIONS = [
    ("wrestler_vs_td_def", "matchup", _wrestler_vs_td_def),
    ("volume_vs_defense", "matchup", _volume_vs_defense),
    ("power_vs_chin", "matchup", _power_vs_chin),
    ("sub_vs_ground", "matchup", _sub_vs_ground),
    ("reach_vs_distance", "matchup", _reach_vs_dist),
]

FEATURES = [n for n, _, _ in PER_FIGHTER] + [n for n, _, _ in INTERACTIONS]
GROUP = {n: g for n, g, _ in PER_FIGHTER}
GROUP.update({n: g for n, g, _ in INTERACTIONS})


def matchup(A, B, rounds=3, title=False):
    """Antisymmetric feature vector for A vs B."""
    x = {}
    for name, _, fn in PER_FIGHTER:
        va, vb = fn(A), fn(B)
        if va is None or vb is None:
            x[name] = 0.0   # unknown on either side: no information about the difference
        else:
            x[name] = float(va) - float(vb)
    for name, _, fn in INTERACTIONS:
        x[name] = float(fn(A, B)) - float(fn(B, A))
    # context terms stay antisymmetric by multiplying a symmetric context with an antisymmetric difference
    five = 1.0 if rounds >= 5 else 0.0
    x["five_x_cardio"] = five * (x["fade"] + x["champ_round_min"])
    x["five_x_rating"] = five * x["rating"]
    return x


ALL_FEATURES = FEATURES + ["five_x_cardio", "five_x_rating"]
GROUP["five_x_cardio"] = "cardio"
GROUP["five_x_rating"] = "adjusted"
