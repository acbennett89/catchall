"""Hand-checked toy network. Run: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from network import Network  # noqa: E402

CFG = {"net_weights": {"primary": 0.5, "secondary": 0.3, "tertiary": 0.2},
       "record_prior": {"wins": 1, "losses": 1}, "fcs_losses_count": True}
TEAMS = {t: {"division": "FBS", "name": t} for t in "ABCDE"}
TEAMS["F"] = {"division": "FCS", "name": "F"}


def game(gid, winner, loser):
    return {"id": gid, "home": winner, "away": loser, "home_pts": 21, "away_pts": 14}


GAMES = [game("g1", "A", "B"), game("g2", "B", "C"), game("g3", "C", "D"),
         game("g4", "E", "C"), game("g5", "B", "F"), game("g6", "F", "D"),
         game("g7", "D", "E"), game("g8", "A", "E")]


class ToyNetwork(unittest.TestCase):
    def setUp(self):
        self.net = Network(GAMES, TEAMS, CFG)

    def test_records_ignore_fcs_wins_but_count_fcs_losses(self):
        self.assertEqual(self.net.record("B")[:2], (1, 1))   # beat C, lost to A; FCS win ignored
        self.assertEqual(self.net.record("D")[:2], (1, 2))   # beat E; lost to C and to FCS F

    def test_a_beats_b_by_hand(self):
        st = self.net.strength("B", "A")
        # P: B without A = 1-0 -> (1+1)/(1+2)
        self.assertAlmostEqual(st["P"], 2 / 3)
        # S: only C (A skipped); C without {A,B} = 1-1 -> 2/4
        self.assertAlmostEqual(st["S"], 0.5)
        # T: C's opponents minus B -> D (1-1 incl. FCS loss, w/o C) = .5, E (0-1 w/o A,C) = 1/3
        self.assertAlmostEqual(st["T"], (0.5 + 1 / 3) / 2)
        self.assertAlmostEqual(st["ns"], 0.5 * 2 / 3 + 0.3 * 0.5 + 0.2 * 5 / 12)

    def test_a_beats_e_by_hand(self):
        st = self.net.strength("E", "A")
        self.assertAlmostEqual(st["P"], 0.5)
        self.assertAlmostEqual(st["S"], (0.5 + 0.25) / 2)
        self.assertAlmostEqual(st["T"], (0.5 + 0.25) / 2)
        self.assertAlmostEqual(st["ns"], 0.4375)

    def test_path_exclusion_keeps_loser_results_out_of_deeper_layers(self):
        # A beats E. Tertiary node C reached via E -> D -> C: C's record must drop
        # games vs A, E and D, leaving only the loss to B (0-1 -> 1/3).
        tree = self.net.strength("E", "A", tree=True)
        d_branch = [c for c in tree["secondary"] if c["team"] == "D"][0]
        c_leaf = [x for x in d_branch["tertiary"] if x["team"] == "C"][0]
        self.assertEqual((c_leaf["W"], c_leaf["L"]), (0, 1))
        self.assertAlmostEqual(c_leaf["wp"], 1 / 3)
        # D reached via E -> C -> D: drops games vs A, E, C -> only the FCS loss remains
        c_branch = [c for c in tree["secondary"] if c["team"] == "C"][0]
        d_leaf = [x for x in c_branch["tertiary"] if x["team"] == "D"][0]
        self.assertEqual((d_leaf["W"], d_leaf["L"]), (0, 1))

    def test_winner_never_appears_in_its_own_tree(self):
        tree = self.net.strength("B", "A", tree=True)
        seen = {c["team"] for c in tree["secondary"]}
        seen |= {d["team"] for c in tree["secondary"] for d in c["tertiary"]}
        self.assertNotIn("A", seen)
        self.assertNotIn("B", {d["team"] for c in tree["secondary"] for d in c["tertiary"]})
        self.assertNotIn("F", seen)  # FCS never a node

    def test_win_values_and_fcs_rules(self):
        ref = self.net.reference()
        res = self.net.resume("A")
        vals = {r["opp"]: r["value"] for r in res["wins"]}
        self.assertAlmostEqual(vals["B"], self.net.strength("B", "A")["ns"] / ref)
        self.assertAlmostEqual(vals["E"], 0.4375 / ref)
        b = self.net.resume("B")
        self.assertEqual([r["value"] for r in b["wins"] if r.get("fcs")], [0.0])
        d = self.net.resume("D")
        fcs_loss = [r for r in d["losses"] if r.get("fcs")][0]
        self.assertAlmostEqual(fcs_loss["cost"], 1 / (1 - ref))
        self.assertAlmostEqual(d["net_resume"], d["win_value_total"] - d["loss_cost_total"])

    def test_average_opponent_win_is_one(self):
        """By construction the mean opponent NS over all FBS game sides equals NS_ref."""
        ref = self.net.reference()
        sides = [self.net.strength(b, a)["ns"] / ref
                 for a in self.net.fbs for b in self.net.opponents(a)]
        self.assertAlmostEqual(sum(sides) / len(sides), 1.0)


if __name__ == "__main__":
    unittest.main()
