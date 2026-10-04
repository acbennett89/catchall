"""Offline tests: parsers against trimmed real pages, odds math, name matching, fighter summaries.

    python -m unittest discover -s tests      (from the ufc-analyzer folder)
"""
import json, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bfo, espn, fighters, names, ufcstats, value  # noqa: E402


def fixture(name):
    with open(os.path.join(HERE, "fixtures", name), encoding="utf-8") as f:
        return json.load(f) if name.endswith(".json") else f.read()


class OddsMath(unittest.TestCase):
    def test_conversions(self):
        self.assertAlmostEqual(value.to_decimal(-200), 1.5)
        self.assertAlmostEqual(value.to_decimal(150), 2.5)
        self.assertAlmostEqual(value.implied(-150), 0.6)
        self.assertEqual(value.to_american(2.5), 150)
        self.assertEqual(value.to_american(1.5), -200)
        self.assertEqual(value.prob_to_american(0.5), 100)

    def test_no_vig(self):
        a, b, hold = value.no_vig(-110, -110)
        self.assertAlmostEqual(a, 0.5)
        self.assertAlmostEqual(hold, 0.0476, places=3)

    def test_ev_and_kelly(self):
        self.assertAlmostEqual(value.ev(0.5, 110), 0.05)
        self.assertAlmostEqual(value.kelly(0.5, 110), 0.05 / 1.1)
        self.assertEqual(value.kelly(0.4, -110), 0.0)

    def test_consensus_excludes_target_and_outliers(self):
        lines = {"Caesars": (-300, 240), "A": (-200, 170), "B": (-205, 175), "C": (-195, 165), "Settled": (-5000, 2000)}
        p, n, used = value.consensus(lines)
        self.assertNotIn("Caesars", used)
        self.assertNotIn("Settled", used)
        self.assertEqual(n, 3)
        self.assertAlmostEqual(p, value.no_vig(-200, 170)[0], places=4)

    def test_assess_flags_caesars_value(self):
        lines = {"Caesars": (-150, 140), "A": (-200, 170), "B": (-210, 175)}
        r = value.assess(lines)
        self.assertGreater(r["sides"][0]["target"]["ev"], 0)  # Caesars -150 on a ~-185 fair favourite
        self.assertLess(r["sides"][1]["target"]["ev"], 0)
        self.assertEqual(r["sides"][1]["best"]["book"], "B")

    def test_settled_market_not_best_price(self):
        lines = {"Caesars": (-145, 122), "A": (-157, 125), "B": (-164, 138), "Kalshi": (-3487, 2236)}
        r = value.assess(lines)
        self.assertEqual(r["outliers"], ["Kalshi"])
        self.assertEqual(r["sides"][1]["best"]["book"], "B")

    def test_prop_without_independent_market(self):
        out = value.assess_prop(["Silva by KO", "Any other result"], {"Caesars": (300, -400), "A": (250, None)})
        self.assertEqual(len(out), 2)
        self.assertIsNone(out[0]["fairOdds"])          # no other book prices both sides
        self.assertGreater(out[0]["vsMarket"], 0)      # but Caesars pays more than the other book


class Names(unittest.TestCase):
    def test_order_and_accents(self):
        self.assertEqual(names.similarity("Wang Cong", "Cong Wang"), 1.0)
        self.assertEqual(names.similarity("Loopy Godínez", "Loopy Godinez"), 1.0)
        self.assertGreaterEqual(names.similarity("Kai Kamaka III", "Kai Kamaka"), 0.99)
        self.assertGreaterEqual(names.similarity("Dooho Choi", "Doo Ho Choi"), 0.9)
        self.assertLess(names.similarity("Jon Jones", "Jon Anik"), 0.84)

    def test_ring_names(self):
        self.assertGreaterEqual(names.pair_score("Patricio Pitbull", "Dooho Choi", "Patricio Freire", "Doo Ho Choi"), 0.84)
        self.assertLess(names.pair_score("Jon Jones", "Tom Aspinall", "Jon Jones", "Tom Smith"), 0.84)


class BestFightOdds(unittest.TestCase):
    def test_event_tables(self):
        evs = bfo.parse_tables(fixture("bfo_event.html"))
        self.assertEqual(len(evs), 1)
        ev = evs[0]
        self.assertEqual(ev["name"], "UFC 332")
        m = ev["matchups"][0]
        self.assertEqual(m["fighters"], ["Natalia Silva", "Wang Cong"])
        self.assertEqual(m["ml"]["Caesars"], [-200, 170])
        self.assertIn("FanDuel", m["ml"])
        draw = next(p for p in m["props"] if p["labels"][0] == "Fight is a draw")
        self.assertEqual(draw["labels"][1], "Fight is not a draw")
        self.assertEqual(draw["odds"]["Caesars"][0], 6000)
        self.assertEqual(ev["matchups"][1]["fighters"], ["Deiveson Figueiredo", "Payton Talbott"])

    def test_fighter_page(self):
        h = bfo.parse_fighter_page(fixture("bfo_fighter.html"))
        self.assertEqual(len(h), 2)
        self.assertEqual(h[0]["opponent"], "Mick Parkin")
        self.assertEqual((h[0]["open"], h[0]["closeLow"], h[0]["closeHigh"]), (157, -117, -104))
        self.assertTrue(h[0]["url"].endswith("/events/ufc-4380"))

    def test_dates(self):
        ref = bfo.parse_date("Oct 3rd 2026")
        self.assertEqual(bfo.parse_date("October 4th", ref) - ref, 86400)
        self.assertIsNone(bfo.parse_date("Future Events"))

    def test_match_orients_to_espn(self):
        card = espn.parse_card(fixture("espn_fightcenter.json"))
        pool = [(e, m) for e in bfo.parse_tables(fixture("bfo_event.html")) for m in e["matchups"]]
        f = card["fights"][0]  # ESPN lists Natalia Silva first after sorting by corner order
        r = bfo._match_fight(f, pool, card["date"])
        self.assertIsNotNone(r)
        i = [x["name"] for x in f["fighters"]].index("Natalia Silva")
        self.assertEqual(r["ml"]["Caesars"][i], -200)


class Espn(unittest.TestCase):
    def test_card(self):
        c = espn.parse_card(fixture("espn_fightcenter.json"))
        self.assertEqual(c["name"], "UFC 332: Silva vs. Wang")
        self.assertEqual([f["segment"] for f in c["fights"]], ["main", "main", "prelims2"])
        main = c["fights"][0]
        self.assertTrue(main["title"])
        self.assertEqual(main["rounds"], 5)
        done = c["fights"][2]
        self.assertEqual(done["status"]["state"], "post")
        self.assertEqual(done["status"]["method"], "KO/TKO")
        self.assertEqual(sum(x["winner"] for x in done["fighters"]), 1)

    def test_athlete(self):
        a = espn.parse_athlete(fixture("espn_athlete.json"), espn.parse_stats(fixture("espn_athlete_stats.json")))
        self.assertEqual(a["name"], "Court McGee")
        self.assertEqual(a["gym"], "The Pit Elevated Fight Team")
        h = a["history"][0]
        self.assertEqual(h["opponent"]["name"], "Eric Nolan")
        self.assertEqual((h["round"], h["time"], h["seconds"]), (3, "3:26", 806))
        self.assertEqual(h["stats"]["ssl"], 98)


class UfcStats(unittest.TestCase):
    def test_fighter(self):
        f = ufcstats.parse_fighter(fixture("ufcstats_fighter.html"))
        self.assertEqual(f["name"], "Jose Aldo")
        self.assertEqual(f["career"]["slpm"], 3.65)
        self.assertEqual(f["career"]["tdDef"], 92.0)
        self.assertEqual(f["fights"][0]["opponent"], "Aiemann Zahabi")
        self.assertEqual(f["fights"][0]["str"], ["68", "99"])

    def test_search(self):
        rows = ufcstats.parse_search(fixture("ufcstats_search.html"))
        self.assertTrue(rows and all(len(r["id"]) == 16 for r in rows))

    def test_pow(self):
        import hashlib
        n = ufcstats.solve("a9a44c6850736e3b", 2)
        self.assertTrue(hashlib.sha256(f"a9a44c6850736e3b:{n}".encode()).hexdigest().startswith("00"))


class Summaries(unittest.TestCase):
    def test_summarize(self):
        hist = [
            {"result": "W", "method": "KO/TKO", "ufc": True},
            {"result": "W", "method": "Submission", "ufc": True},
            {"result": "L", "method": "Decision - Split", "ufc": True},
            {"result": "W", "method": "Decision - Unanimous", "ufc": False},
            {"result": "L", "method": "No Contest", "ufc": True},
        ]
        s = fighters.summarize(hist)
        self.assertEqual(s["record"], "3-1-0 (1 NC)")
        self.assertEqual(s["ufcRecord"], "2-1-0")
        self.assertEqual(s["streak"], "W2")
        self.assertEqual(s["wins"], {"ko": 1, "sub": 1, "dec": 1, "other": 0})
        self.assertAlmostEqual(s["finishRate"], 2 / 3, places=3)


if __name__ == "__main__":
    unittest.main()
