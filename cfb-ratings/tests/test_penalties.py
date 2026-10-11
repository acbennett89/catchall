"""Penalty parser on both ESPN text dialects. Run: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from penalties import parse_game_penalties, team_totals  # noqa: E402

H, A = "1", "2"


def summary(plays):
    return {"header": {"id": "g", "competitions": [{"competitors": [
                {"homeAway": "home", "team": {"id": H, "abbreviation": "HOM", "location": "Home State",
                                              "displayName": "Home State Hogs", "shortDisplayName": "Home St"}},
                {"homeAway": "away", "team": {"id": A, "abbreviation": "AWY", "location": "Away Tech",
                                              "displayName": "Away Tech Ants", "shortDisplayName": "Away Tech"}}]}]},
            "drives": {"previous": [{"team": {"id": H}, "plays": plays}]}}


def play(pid, text, typ="Penalty", down=1, yl=25, team=H):
    return {"id": pid, "type": {"text": typ}, "text": text, "period": {"number": 1},
            "clock": {"displayValue": "10:00"},
            "start": {"down": down, "distance": 10, "yardLine": yl, "yardsToEndzone": 100 - yl, "team": {"id": team}},
            "end": {"down": down, "yardLine": yl, "team": {"id": team}}}


class Dialects(unittest.TestCase):
    def test_statcrew_accepted_declined_and_offsetting(self):
        plays = [play("1", "rush for 4 yards to the HOM29", typ="Rush", yl=25),
                 play("2", "PENALTY HOM False Start (#50 J.Doe) 5 yards from HOM29 to HOM24. NO PLAY", yl=29),
                 play("3", "pass incomplete PENALTY AWY Pass Interference declined", typ="Pass Incompletion", yl=24),
                 play("4", "rush for 2 yards PENALTY HOM Holding offsetting AWY Holding offsetting", typ="Rush", yl=24)]
        ev = parse_game_penalties(summary(plays))
        by = {(e["penalized_team_id"], e["category"], e["status"]) for e in ev}
        self.assertIn((H, "False Start", "accepted"), by)
        self.assertIn((A, "Pass Interference", "declined"), by)
        self.assertEqual(sum(1 for e in ev if e["status"] == "offsetting"), 2)
        fs = [e for e in ev if e["category"] == "False Start"][0]
        self.assertEqual((fs["yards"], fs["presnap"], fs["no_play"], fs["penalized_unit"]), (5, True, True, "offense"))
        self.assertEqual(team_totals(ev), {H: (1, 5)})   # only accepted fouls count, like the box score

    def test_narrative_dialect(self):
        plays = [play("1", "Home State Penalty, False Start (-5 Yards) to the HOM 20", yl=25),
                 play("2", "Away Tech Penalty, Roughing Passer (Jim Smith) to the HOM 35 for a 1ST down", yl=20)]
        ev = parse_game_penalties(summary(plays))
        cats = {e["category"]: e for e in ev}
        self.assertEqual(cats["False Start"]["penalized_team_id"], H)
        self.assertEqual(cats["False Start"]["yards"], 5)
        self.assertEqual(cats["Roughing the Passer"]["penalized_team_id"], A)
        self.assertTrue(cats["Roughing the Passer"]["first_down_awarded"])
        self.assertEqual(cats["Roughing the Passer"]["dialect"], "narrative")


if __name__ == "__main__":
    unittest.main()
