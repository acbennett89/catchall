"""Invariants of the built outputs (out/<season>/). Run after build.py:
python -m unittest discover -s tests"""
import glob
import json
import os
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


if __name__ == "__main__":
    unittest.main()
