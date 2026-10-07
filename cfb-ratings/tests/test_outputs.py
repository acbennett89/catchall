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
                r = json.load(open(os.path.join(out, "ratings.json")))
                teams, meta = r["teams"], r["meta"]
                ranked = [t for t in teams if t["eligible"]]
                tentative = [t for t in teams if not t["eligible"]]
                self.assertEqual(len(ranked), meta["eligible"])
                self.assertEqual(len(tentative), meta.get("tentative", 0))
                self.assertEqual(sorted(t["rk_AdjEM"] for t in ranked), list(range(1, len(ranked) + 1)))
                for t in tentative:
                    self.assertTrue(t["tentative"])
                    self.assertEqual(t["status"], "tentative")
                    self.assertIsNotNone(t["AdjEM"])
                    self.assertFalse([k for k, v in t.items() if k.startswith("rk_") and v is not None], t["name"])
                    tr = json.load(open(os.path.join(out, "traces", f"{t['id']}.json")))
                    self.assertTrue(tr.get("tentative"))
                    self.assertIn("efficiency", tr)
                ids = {t["id"] for t in teams}
                internal = json.load(open(os.path.join(out, "traces", "internal", "index.json")))
                self.assertFalse(ids & set(internal), "internal derivations must be FCS-only")
                # Opponent labels: tentative FBS opponents vs FCS internal inputs.
                status_of = {t["id"]: "published" if t["eligible"] else "tentative" for t in teams}
                tr = json.load(open(os.path.join(out, "traces", f"{ranked[0]['id']}.json")))
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
        from build import HISTORY_COLUMNS, WEEK_FIELDS
        from polls import latest, load_polls
        from ratings import load
        for season in built_seasons():
            with self.subTest(season=season):
                out = os.path.join(HERE, "out", str(season))
                r = json.load(open(os.path.join(out, "ratings.json")))
                wk = json.load(open(os.path.join(out, "weekly.json")))
                meta, polls = r["meta"], load_polls(season)
                week_of = {g["id"]: g["week"] for g in load(season)["games"]}
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
                    # Picks: next week's games, predicted from this week's ratings, with results.
                    self.assertEqual(bool(s["picks"]), w < weeks[-1], w)
                    for g in s["picks"]:
                        self.assertEqual(week_of[g["game"]], w + 1)
                        self.assertIsNotNone(g["home_pts"])
                # The drawer's week-by-week lines are the weekly tables, re-cut by team.
                h = wk["history"]
                self.assertEqual(h["columns"], HISTORY_COLUMNS)
                for s in wk["weeks"]:
                    for t in s["teams"]:
                        line = h["teams"][t["id"]][s["week"] - 1]
                        self.assertEqual(line, [s["week"]] + [t.get(k) for k in HISTORY_COLUMNS[1:]])

    def test_a_week_recomputes(self):
        """A weekly table is ratings.rate() over that week's games: rerun one and compare."""
        import copy
        sys.path.insert(0, HERE)
        from ratings import load, load_config, rate
        season = built_seasons()[-1]
        wk = json.load(open(os.path.join(HERE, "out", str(season), "weekly.json")))
        snap = wk["weeks"][len(wk["weeks"]) // 2]
        cfg = load_config()
        res = rate(copy.deepcopy(load(season)), cfg, through_week=snap["week"])
        for t in snap["teams"]:
            got = res["teams"][t["id"]]
            self.assertEqual((got["W"], got["L"], got.get("rk_AdjEM")), (t["W"], t["L"], t["rk_AdjEM"]))
            for k in ("AdjEM", "NetPerGame"):
                if t[k] is None:
                    self.assertIsNone(got.get(k))
                else:
                    self.assertAlmostEqual(got[k], t[k], places=9)


class Polls(unittest.TestCase):
    def test_polls_files(self):
        for season in built_seasons():
            p = os.path.join(HERE, "data", str(season), "polls.json")
            if not os.path.exists(p):
                continue
            with self.subTest(season=season):
                polls = json.load(open(p))["polls"]
                last = json.load(open(os.path.join(HERE, "out", str(season), "ratings.json")))["meta"]["through_week"]
                keys = [(x["poll"], x["after_week"]) for x in polls]
                self.assertEqual(len(keys), len(set(keys)))
                for x in polls:
                    self.assertTrue(0 <= x["after_week"] <= last)
                    self.assertEqual(x["espn"]["week"] - 1 if x["after_week"] else 0, x["after_week"])
                    self.assertEqual([r["rank"] for r in x["ranks"]], sorted(r["rank"] for r in x["ranks"]))
                    self.assertTrue(24 <= len(x["ranks"]) <= 26, (x["poll"], x["after_week"]))


if __name__ == "__main__":
    unittest.main()
