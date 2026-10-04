"""Check the parsed penalty table against ESPN box-score totals, team-game by team-game.

    python audit_penalties.py            -> out/penalty_audit.json (+ summary printed), every parsed season

A box row is skipped when it fails the sanity check in parse.box_penalties (one 2025
row reads '743-37'). Only accepted fouls count, as in the box score.
"""
import glob
import json
import os

from ratings import HERE, load


def audit(season):
    d = load(season)
    f = {k: i for i, k in enumerate(d["penalty_fields"])}
    rows = []
    for g in d["games"]:
        if not g["d1"] or "penalties" not in g:
            continue
        for tid, b in g["box"].items():
            if b.get("pen") is None:
                continue
            acc = [r for r in g["penalties"] if r[f["status"]] == "accepted" and r[f["penalized_team_id"]] == tid]
            rows.append({"game": g["id"], "team": tid, "box_count": b["pen"][0], "box_yards": b["pen"][1],
                         "parsed_count": len(acc), "parsed_yards": sum(r[f["yards"]] for r in acc)})
    n = len(rows)
    box_n = sum(r["box_count"] for r in rows)
    parsed_n = sum(r["parsed_count"] for r in rows)
    summary = {
        "team_games": n,
        "count_exact": sum(r["box_count"] == r["parsed_count"] for r in rows) / n,
        "count_within_1": sum(abs(r["box_count"] - r["parsed_count"]) <= 1 for r in rows) / n,
        "yards_exact": sum(r["box_yards"] == r["parsed_yards"] for r in rows) / n,
        "total_count_vs_box": parsed_n / box_n - 1,
        "total_yards_vs_box": sum(r["parsed_yards"] for r in rows) / sum(r["box_yards"] for r in rows) - 1,
    }
    return summary, rows


def main():
    out = {}
    seasons = sorted((int(os.path.basename(os.path.dirname(p)))
                      for p in glob.glob(os.path.join(HERE, "data", "*", "games.json.gz"))), reverse=True)
    for season in seasons:
        summary, rows = audit(season)
        out[season] = {"summary": summary, "team_games": rows}
        print(season, {k: (round(v, 4) if isinstance(v, float) else v) for k, v in summary.items()})
    with open(os.path.join(HERE, "out", "penalty_audit.json"), "w") as f:
        json.dump(out, f, separators=(",", ":"))


if __name__ == "__main__":
    main()
