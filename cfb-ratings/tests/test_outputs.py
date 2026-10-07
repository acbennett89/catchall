"""Invariants of the built outputs (out/<season>/). Run after build.py:
python -m unittest discover -s tests"""
import glob
import json
import os
import sys
import unittest

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def built_seasons():
    return sorted(int(os.path.basename(os.path.dirname(p)))
                  for p in glob.glob(os.path.join(HERE, "out", "*", "ratings.json"))
                  if os.path.basename(os.path.dirname(p)).isdigit())


class TentativeRatings(unittest.TestCase):
    """Teams under the game minimum are published as tentative: full numbers, never ranked."""

    def test_every_season(self):
        seasons = built_seasons()
        self.assertTrue(seasons, "no built seasons")
        for season in seasons:
            with self.subTest(season=season):
                out = os.path.join(HERE, "out", str(season))
                r = json.load(open(os.path.join(out, "ratings.json"), encoding="utf-8"))
                teams, meta = r["teams"], r["meta"]
                ranked = [t for t in teams if t["eligible"]]
                tentative = [t for t in teams if not t["eligible"]]
                self.assertEqual(len(ranked), meta["eligible"])
                self.assertEqual(sum(t["AdjEM"] is not None for t in tentative), meta.get("tentative", 0))
                self.assertEqual(sum(t["AdjEM"] is None for t in teams), meta.get("unrated", 0))
                self.assertEqual(sorted(t["rk_AdjEM"] for t in ranked), list(range(1, len(ranked) + 1)))
                for t in tentative:
                    self.assertTrue(t["tentative"])
                    self.assertEqual(t["status"], "tentative")
                    self.assertIsNotNone(t["AdjEM"])
                    self.assertFalse([k for k, v in t.items() if k.startswith("rk_") and v is not None], t["name"])
                    tr = json.load(open(os.path.join(out, "traces", f"{t['id']}.json"), encoding="utf-8"))
                    self.assertTrue(tr.get("tentative"))
                    self.assertIn("efficiency", tr)
                ids = {t["id"] for t in teams}
                internal = json.load(open(os.path.join(out, "traces", "internal", "index.json"), encoding="utf-8"))
                self.assertFalse(ids & set(internal), "internal derivations must be FCS-only")
                # Opponent labels: tentative FBS opponents vs FCS internal inputs.
                status_of = {t["id"]: "published" if t["eligible"] else "tentative" for t in teams}
                tr = json.load(open(os.path.join(out, "traces", f"{ranked[0]['id']}.json"), encoding="utf-8"))
                for ln in tr["efficiency"]["offense"]["lines"]:
                    want = status_of.get(ln["opp"], "internal")
                    self.assertTrue(ln["opp_status"].startswith(want), (ln["opp"], ln["opp_status"]))
                tent_preds = [p for p in r["predictions"] if p["tentative"]]
                names = {t["name"] for t in tentative}
                for p in r["predictions"]:
                    self.assertEqual(p["tentative"], p["home"] in names or p["away"] in names, p)
                self.assertLessEqual(len(tent_preds), len(r["predictions"]))


class WeeklyViews(unittest.TestCase):
    """out/<season>/weekly.json: the table after each week, from that week's games only."""

    def test_every_season(self):
        sys.path.insert(0, HERE)
        from build import HISTORY_COLUMNS, SLOT_METRICS, WEEK_FIELDS
        from polls import latest, load_polls
        from ratings import load
        for season in built_seasons():
            with self.subTest(season=season):
                out = os.path.join(HERE, "out", str(season))
                r = json.load(open(os.path.join(out, "ratings.json"), encoding="utf-8"))
                wk = json.load(open(os.path.join(out, "weekly.json"), encoding="utf-8"))
                meta, polls = r["meta"], load_polls(season)
                data = load(season)
                week_of = {g["id"]: g["week"] for g in data["games"]}
                fbs_games = {g["id"] for g in data["games"] if g["d1"] and "FBS" in
                             (data["teams"][g["home"]]["division"], data["teams"][g["away"]]["division"])}
                weeks = [s["week"] for s in wk["weeks"]]
                self.assertEqual(weeks, list(range(1, meta["through_week"] + 1)))
                self.assertEqual(meta["weeks"], weeks)
                # The latest week is the published table itself.
                final = {t["id"]: t for t in r["teams"]}
                for t in wk["weeks"][-1]["teams"]:
                    self.assertEqual(t, {k: final[t["id"]].get(k) for k in WEEK_FIELDS}, t["name"])
                games_before = {}
                for s in wk["weeks"]:
                    w, rows = s["week"], s["teams"]
                    ranked = [t for t in rows if t["eligible"] and t["AdjEM"] is not None]
                    self.assertEqual(sorted(t["rk_AdjEM"] for t in ranked), list(range(1, len(ranked) + 1)))
                    self.assertEqual(s["meta"]["eligible"], sum(t["eligible"] for t in rows))
                    self.assertEqual(s["meta"]["tentative"], sum(not t["eligible"] and t["AdjEM"] is not None for t in rows))
                    self.assertEqual(s["meta"]["unrated"], sum(t["AdjEM"] is None for t in rows))
                    # ≈n: placed among the ranked teams once they are half of those with a value,
                    # otherwise among all of them -- never against a handful of early starters.
                    self.assertEqual([m for m, _ in SLOT_METRICS], ["AdjEM", "NetPerGame", "AdjO", "AdjD"])
                    for metric, sign in SLOT_METRICS:  # AdjD: lower is better, as in rk_AdjD
                        have = [t for t in rows if t[metric] is not None]
                        elig = [t for t in have if t["eligible"]]
                        pool = elig if 2 * len(elig) >= len(have) else have
                        self.assertEqual(s["meta"]["slot_base"][metric], "ranked" if pool is elig else "all")
                        for t in rows:
                            want = None if t["eligible"] or t[metric] is None else \
                                1 + sum(1 for x in pool if x is not t and sign * (x[metric] - t[metric]) > 1e-9)
                            self.assertEqual(t.get("slot_" + metric), want, (w, t["name"], metric))
                    for t in rows:
                        self.assertEqual(t["eligible"], t["games"] >= meta["min_games"], (w, t["name"]))
                        self.assertEqual(t["W"] + t["L"], t["games"])
                        self.assertGreaterEqual(t["games"], games_before.get(t["id"], 0))
                        games_before[t["id"]] = t["games"]
                        if t["tentative"]:
                            self.assertIsNone(t["rk_AdjEM"])
                            if t["AdjEM"] is not None:
                                self.assertGreaterEqual(t["slot_AdjEM"], 1)
                    for kind in ("AP", "CFP"):
                        p = latest(polls, kind, w)
                        used = s["meta"]["polls"][kind]
                        self.assertEqual(used and used["after_week"], p and p["after_week"])
                        ranks = {x["team"]: x["rank"] for x in p["ranks"]} if p else {}
                        self.assertEqual({t["id"]: t[kind] for t in rows if t[kind] is not None}, ranks)
                    # Picks: next week's games, predicted from this week's ratings, with results;
                    # every game with an FBS side is either picked or listed as unpickable.
                    self.assertEqual(bool(s["picks"]), w < weeks[-1], w)
                    for g in s["picks"]:
                        self.assertEqual(week_of[g["game"]], w + 1)
                        self.assertIsNotNone(g["home_pts"])
                    listed = {g["game"] for g in s["picks"]} | {g["game"] for g in s["picks_skipped"]}
                    self.assertEqual(listed, {g for g, wk_ in week_of.items() if wk_ == w + 1 and g in fbs_games})
                # The drawer's week-by-week lines are the weekly tables, re-cut by team.
                h = wk["history"]
                self.assertEqual(h["columns"], HISTORY_COLUMNS)
                for s in wk["weeks"]:
                    for t in s["teams"]:
                        line = h["teams"][t["id"]][s["week"] - 1]
                        self.assertEqual(line, [s["week"]] + [t.get(k) for k in HISTORY_COLUMNS[1:]])

    def test_a_week_recomputes(self):
        """A weekly table is ratings.rate() over that week's games: rerun two and compare every field
        the page shows, ranks, tentative slots and poll columns included."""
        import copy
        sys.path.insert(0, HERE)
        from build import WEEK_FIELDS, finish_rows
        from polls import load_polls
        from ratings import load, load_config, rate
        seasons = built_seasons()
        picks = [(seasons[-1], 3)] + ([(2025, 8)] if 2025 in seasons else [])
        for season, week in picks:
            with self.subTest(season=season, week=week):
                wk = json.load(open(os.path.join(HERE, "out", str(season), "weekly.json"), encoding="utf-8"))
                snap = next(s for s in wk["weeks"] if s["week"] == week)
                res = rate(copy.deepcopy(load(season)), load_config(), through_week=week)
                rows, info = finish_rows(res, load_polls(season), week)
                self.assertEqual(info["polls"], snap["meta"]["polls"])
                self.assertEqual(info["slot_base"], snap["meta"]["slot_base"])
                got = {r["id"]: r for r in rows}
                for t in snap["teams"]:
                    for k in WEEK_FIELDS:
                        a, b = got[t["id"]].get(k), t[k]
                        if isinstance(b, float):
                            self.assertAlmostEqual(a, b, places=9, msg=(t["name"], k))
                        else:
                            self.assertEqual(a, b, (t["name"], k))


class OpponentRanks(unittest.TestCase):
    """Each efficiency line carries the opponent's rank in the rating it is adjusted for (AdjD on
    offense, AdjO on defense): entering the game (the weekly table after the week before) and now."""

    def test_every_line(self):
        sys.path.insert(0, HERE)
        from ratings import load
        for season in built_seasons():
            with self.subTest(season=season):
                out = os.path.join(HERE, "out", str(season))
                r = json.load(open(os.path.join(out, "ratings.json"), encoding="utf-8"))
                wk = json.load(open(os.path.join(out, "weekly.json"), encoding="utf-8"))
                now = r["meta"]["through_week"]
                tables = {s["week"]: {t["id"]: t for t in s["teams"]} for s in wk["weeks"]}
                self.assertEqual(tables[now], {t["id"]: {k: t.get(k) for k in wk["weeks"][-1]["teams"][0]}
                                               for t in r["teams"]})
                week_of = {g["id"]: g["week"] for g in load(season)["games"]}

                def want(table, opp, metric, after):
                    t = (table or {}).get(opp)
                    if after < 1 or t is None or t[metric] is None:
                        return None, False
                    return (t["rk_" + metric], False) if t["eligible"] else (t["slot_" + metric], True)

                files = [os.path.join(out, "traces", f"{t['id']}.json") for t in r["teams"]]
                idx = json.load(open(os.path.join(out, "traces", "internal", "index.json"), encoding="utf-8"))
                files += [os.path.join(out, "traces", "internal", f"{t}.json") for t in idx]
                n = {"then": 0, "approx": 0, "fcs": 0, "week1": 0}
                for path in files:
                    e = json.load(open(path, encoding="utf-8")).get("efficiency")
                    if not e:
                        continue
                    for side, metric in (("offense", "AdjD"), ("defense", "AdjO")):
                        for ln in e[side]["lines"]:
                            x = ln["opp_rank"]
                            self.assertEqual(x["metric"], metric)
                            after = week_of[ln["game"]] - 1
                            for key, table, wk_ in (("then", tables.get(after), after), ("now", tables[now], now)):
                                got = x[key]
                                self.assertEqual(got["after_week"], wk_)
                                self.assertEqual((got["rank"], got["approx"]), want(table, ln["opp"], metric, wk_),
                                                 (path, ln["game"], key))
                                self.assertEqual(got["rank"] is None, "why" in got)
                            n["then"] += x["then"]["rank"] is not None
                            n["approx"] += x["then"]["approx"]
                            n["fcs"] += ln["opp"] not in tables[now]
                            n["week1"] += after == 0
                            if ln["opp"] not in tables[now]:
                                self.assertTrue(ln["opp_status"].startswith("internal"))
                # Every kind of line occurs: ranked, tentative slot, FCS, week 1.
                self.assertTrue(all(n.values()), n)


class Polls(unittest.TestCase):
    def test_polls_files(self):
        for season in built_seasons():
            with self.subTest(season=season):
                p = os.path.join(HERE, "data", str(season), "polls.json")
                self.assertTrue(os.path.exists(p), "run python polls.py --season %d" % season)
                polls = json.load(open(p, encoding="utf-8"))["polls"]
                last = json.load(open(os.path.join(HERE, "out", str(season), "ratings.json"), encoding="utf-8"))["meta"]["through_week"]
                keys = [(x["poll"], x["after_week"]) for x in polls]
                self.assertEqual(len(keys), len(set(keys)))
                for kind in ("AP", "CFP"):
                    weeks = sorted(w for k, w in keys if k == kind)
                    if weeks:  # weekly from its first release, no holes
                        self.assertEqual(weeks, list(range(weeks[0], weeks[-1] + 1)), kind)
                self.assertEqual(min(w for k, w in keys if k == "AP"), 0)
                for x in polls:
                    self.assertTrue(0 <= x["after_week"] <= last)
                    e = x["espn"]
                    if x["after_week"] == 0:
                        self.assertTrue(e["season_type"] == 1 or e["week"] == 1, e)
                    else:
                        self.assertEqual((e["season_type"], e["week"] - 1), (2, x["after_week"]))
                    self.assertEqual([r["rank"] for r in x["ranks"]], sorted(r["rank"] for r in x["ranks"]))
                    self.assertTrue(24 <= len(x["ranks"]) <= 26, (x["poll"], x["after_week"]))


if __name__ == "__main__":
    unittest.main()
