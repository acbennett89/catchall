"""The solver must recover known ratings from noiseless synthetic games."""
import os
import random
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from efficiency import solve, solve_tempo, trace, trace_tempo  # noqa: E402


class SyntheticRecovery(unittest.TestCase):
    def setUp(self):
        rng = random.Random(7)
        self.teams = [f"T{i}" for i in range(20)]
        self.div = {t: ("FBS" if i < 14 else "FCS") for i, t in enumerate(self.teams)}
        self.mu, self.h = 2.3, 0.15
        self.trueO = {t: self.mu + rng.uniform(-1, 1) for t in self.teams}
        self.trueD = {t: self.mu + rng.uniform(-1, 1) for t in self.teams}
        self.obs, self.tempo_games = [], []
        self.trueT = {t: 11.5 + rng.uniform(-1.5, 1.5) for t in self.teams}
        gid = 0
        for _ in range(6):
            order = self.teams[:]
            rng.shuffle(order)
            for a, b in zip(order[::2], order[1::2]):
                gid += 1
                v = rng.choice([1, -1, 0])
                for off, dfn, vv in ((a, b, v), (b, a, -v)):
                    self.obs.append({"game": f"g{gid}", "off": off, "def": dfn, "v": vv,
                                     "w": rng.randint(8, 14),
                                     "y": self.trueO[off] + self.trueD[dfn] - self.mu + self.h * vv})
                self.tempo_games.append({"game": f"g{gid}", "a": a, "b": b,
                                         "poss": self.trueT[a] + self.trueT[b] - 11.5})

    def test_recovers_truth_without_prior(self):
        m = solve(self.obs, self.div, prior_weight=0, max_iter=5000, tol=1e-12)
        self.assertTrue(m["converged"])
        self.assertAlmostEqual(m["h"], self.h, places=6)
        # O and D are identified up to a shared constant (O+c, D-c predict the
        # same games), so compare every team against a reference team.
        ref = self.teams[0]
        for t in self.teams:
            self.assertAlmostEqual(m["O"][t] - m["O"][ref], self.trueO[t] - self.trueO[ref], places=5)
            self.assertAlmostEqual(m["D"][t] - m["D"][ref], self.trueD[t] - self.trueD[ref], places=5)
        # ...and every game is reproduced exactly.
        for o in self.obs:
            pred = m["O"][o["off"]] + m["D"][o["def"]] - m["mu"] + m["h"] * o["v"]
            self.assertAlmostEqual(pred, o["y"], places=6)

    def test_trace_reconstructs_every_rating_with_prior(self):
        m = solve(self.obs, self.div, prior_weight=12, max_iter=5000, tol=1e-12)
        for t in self.teams:
            tr = trace(m, t)
            self.assertTrue(tr["offense"]["check_ok"], t)
            self.assertTrue(tr["defense"]["check_ok"], t)

    def test_tempo(self):
        m = solve_tempo(self.tempo_games, self.div, prior_games=0, max_iter=5000, tol=1e-12)
        ref = self.teams[0]
        for t in self.teams:
            self.assertAlmostEqual(m["T"][t] - m["T"][ref], self.trueT[t] - self.trueT[ref], places=5)
        for g in self.tempo_games:
            self.assertAlmostEqual(m["T"][g["a"]] + m["T"][g["b"]] - m["muT"], g["poss"], places=6)
        m1 = solve_tempo(self.tempo_games, self.div, prior_games=1, max_iter=5000, tol=1e-12)
        for t in self.teams:
            self.assertTrue(trace_tempo(m1, t)["check_ok"])


if __name__ == "__main__":
    unittest.main()
