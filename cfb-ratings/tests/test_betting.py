"""The model's line against the book: spreads, sides, results, line parsing and Odds API matching.
Run: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from betting import BREAK_EVEN, bet, book_line, bucket_of, cover_prob, half_point, record  # noqa: E402
from odds import caesars_from_event, espn_lines, match_odds_api  # noqa: E402

LINE = {"book": "Caesars Sportsbook", "caesars": True, "home_spread": -7.0, "total": 50.5,
        "source": "ESPN closing", "read_at": None}


class Lines(unittest.TestCase):
    def test_half_point(self):
        self.assertEqual([half_point(x) for x in (-13.26, 13.74, 2.75, -2.75, 0.24, 6.99)],
                         [-13.5, 13.5, 3.0, -3.0, 0.0, 7.0])

    def test_sides_and_results(self):
        b = bet(10.2, LINE, 3, actual=8)  # model: home by 10.2, a line of -10; book: home by 7
        self.assertEqual((b["model_home_spread"], b["side"], b["likes"], b["ats"], b["edge"]), (-10.0, "home", True, "W", 3.0))
        b = bet(9.7, LINE, 3, actual=8)  # a line of -9.5: 2.5 points from the book's, so no star
        self.assertEqual((b["model_home_spread"], b["edge"], b["likes"]), (-9.5, 2.5, False))
        b = bet(4.0, LINE, 3, actual=7)  # model likes the away team +7; home won by exactly 7
        self.assertEqual((b["side"], b["likes"], b["ats"]), ("away", True, "P"))
        b = bet(5.5, LINE, 3, actual=10)  # 1.5 points of disagreement: a side, but no play
        self.assertEqual((b["side"], b["likes"], b["ats"]), ("away", False, "L"))
        b = bet(7.0, LINE, 3, actual=3)  # the model agrees with the book: no side, no result
        self.assertEqual((b["side"], b["likes"]), (None, False))
        self.assertNotIn("ats", b)
        self.assertEqual(bet(-3.0, None, 3), {"model_home_spread": 3.0})
        late = bet(20.0, {**LINE, "after_kickoff": True}, 3, {"b": 0.07, "s": 15.0})  # read after kickoff
        self.assertEqual((late["side"], late["likes"], late.get("after_kickoff")), ("home", False, True))
        self.assertNotIn("cover_prob", late)
        self.assertIn("cover_prob", bet(20.0, LINE, 3, {"b": 0.07, "s": 15.0}))

    def test_book_preference(self):
        books = {"DraftKings": {"home_spread": -6.5, "total": 49.0},
                 "Caesars Sportsbook (New Jersey)": {"home_spread": None, "total": None},
                 "Caesars Sportsbook (Colorado)": {"home_spread": -7.0, "total": 50.0},
                 "Caesars Sportsbook": {"home_spread": 7.0, "total": None}}
        self.assertEqual(book_line(books)["book"], "Caesars Sportsbook (Colorado)")  # a state desk before the generic entry
        self.assertEqual(book_line({"DraftKings": books["DraftKings"]})["book"], "DraftKings")
        self.assertIsNone(book_line({}))

    def test_stale_caesars_entry_passed_over(self):
        # Notre Dame at Navy 2022: ESPN's generic Caesars entry had the favorite reversed.
        books = {"Caesars Sportsbook": {"home_spread": -17.0}, "DraftKings": {"home_spread": 16.5},
                 "MGM": {"home_spread": 17.0}, "consensus": {"home_spread": 17.0}, "accuscore": {"home_spread": -30.0}}
        self.assertEqual(book_line(books)["book"], "DraftKings")
        books["Caesars Sportsbook (New Jersey)"] = {"home_spread": 16.5}
        self.assertEqual((book_line(books)["book"], book_line(books)["home_spread"]), ("Caesars Sportsbook (New Jersey)", 16.5))
        # With a single other book there is no median to check against.
        self.assertEqual(book_line({"Caesars Sportsbook": {"home_spread": -17.0}, "DraftKings": {"home_spread": 16.5}})["book"],
                         "Caesars Sportsbook")

    def test_record_and_buckets(self):
        bets = [{"edge": e, "ats": r, "book": "Caesars Sportsbook", "tentative": e > 10} for e, r in
                ((1, "W"), (-2, "L"), (3, "W"), (-6.9, "P"), (7, "L"), (12, "W"), (0.5, None))]
        r = record(bets, 3)
        self.assertEqual((r["by_status"]["tentative"]["W"], r["by_status"]["rated"]["W"], r["by_status"]["rated"]["L"]), (1, 2, 2))
        self.assertEqual((r["all"]["W"], r["all"]["L"], r["all"]["P"]), (3, 2, 1))
        self.assertEqual((r["likes"]["W"], r["likes"]["L"], r["likes"]["P"]), (2, 1, 1))
        self.assertEqual({k: (v["W"], v["L"], v["P"]) for k, v in r["by_edge"].items()},
                         {"0-3": (1, 1, 0), "3-7": (1, 0, 1), "7-10": (0, 1, 0), "10+": (1, 0, 0)})
        self.assertEqual([bucket_of(x) for x in (2.99, 3, -9.99, 10)], ["0-3", "3-7", "7-10", "10+"])

    def test_cover_prob(self):
        cal = {"b": 0.07, "s": 15.0}
        self.assertEqual(cover_prob(10, cal), cover_prob(-10, cal))  # the same for a home or an away side
        self.assertGreater(cover_prob(10, cal), cover_prob(3, cal))
        self.assertLess(cover_prob(14, cal), BREAK_EVEN + 0.01)
        self.assertAlmostEqual(cover_prob(5, {"b": 0.0, "s": 15.0}), 0.5)


class EspnLines(unittest.TestCase):
    def test_parse(self):
        item = lambda name, spread, home, total=50.0: {
            "provider": {"name": name}, "spread": spread, "overUnder": total,
            "homeTeamOdds": {"current": {"pointSpread": {"american": home}}}}
        got = espn_lines({"items": [item("Caesars Sportsbook", -40.5, "-40.5", 57.0),
                                    item("DraftKings - Live Odds", -3.5, "-3.5"),
                                    item("Bad Book", -3.5, "+3.5"),  # spread and home price disagree
                                    item("DraftKings", 9.5, "+9.5", 0)]})
        self.assertEqual(got, {"Caesars Sportsbook": {"home_spread": -40.5, "total": 57.0},
                               "DraftKings": {"home_spread": 9.5, "total": None}})


TEAMS = {"1": {"display": "UCF Knights", "name": "UCF"}, "2": {"display": "Hawai'i Rainbow Warriors", "name": "Hawai'i"},
         "3": {"display": "Miami Hurricanes", "name": "Miami"}, "4": {"display": "Miami (OH) RedHawks", "name": "Miami (OH)"},
         "5": {"display": "San José State Spartans", "name": "San José State"}, "6": {"display": "Texas Longhorns", "name": "Texas"},
         "7": {"display": "Texas A&M Aggies", "name": "Texas A&M"}, "8": {"display": "Ohio Bobcats", "name": "Ohio"}}
GAMES = [{"id": "g1", "date": "2026-10-10T16:00Z", "home": "1", "away": "2"},
         {"id": "g2", "date": "2026-10-10T19:30Z", "home": "3", "away": "5"},
         {"id": "g3", "date": "2026-10-10T23:00Z", "home": "4", "away": "8"},
         {"id": "g4", "date": "2026-10-10T19:30Z", "home": "6", "away": "7"}]  # neutral site, listed the other way


def event(home, away, start, home_pt, total=55.5):
    return {"home_team": home, "away_team": away, "commence_time": start,
            "bookmakers": [{"key": "williamhill_us", "last_update": start, "markets": [
                {"key": "spreads", "outcomes": [{"name": home, "price": -110, "point": home_pt},
                                                {"name": away, "price": -110, "point": -home_pt}]},
                {"key": "totals", "outcomes": [{"name": "Over", "price": -110, "point": total},
                                               {"name": "Under", "price": -110, "point": total}]}]}]}


class OddsApiKey(unittest.TestCase):
    def test_key_file_encodings(self):
        import tempfile
        import odds
        old_here, old_env = odds.HERE, os.environ.pop("ODDS_API_KEY", None)
        try:
            with tempfile.TemporaryDirectory() as d:
                odds.HERE = d
                for raw in (b"abc123DEF\r\n", b"\xef\xbb\xbfabc123DEF\r\n", "abc123DEF\r\n".encode("utf-16")):
                    open(os.path.join(d, "odds_api_key.txt"), "wb").write(raw)
                    self.assertEqual(odds.odds_api_key(), "abc123DEF", raw)
                os.remove(os.path.join(d, "odds_api_key.txt"))
                self.assertIsNone(odds.odds_api_key())
        finally:
            odds.HERE = old_here
            if old_env is not None:
                os.environ["ODDS_API_KEY"] = old_env


class OddsApi(unittest.TestCase):
    def test_match_and_read(self):
        events = [event("Central Florida Knights", "Hawaii Rainbow Warriors", "2026-10-10T16:00:00Z", -14.5),
                  event("Miami Hurricanes", "San Jose State Spartans", "2026-10-10T19:30:00Z", -21.0),
                  event("Miami (OH) RedHawks", "Ohio Bobcats", "2026-10-10T23:00:00Z", 2.5),
                  event("Texas A&M Aggies", "Texas Longhorns", "2026-10-10T19:30:00Z", 3.5),
                  event("Alabama Crimson Tide", "Georgia Bulldogs", "2026-10-10T19:30:00Z", -1.5)]
        pairs, unmatched = match_odds_api(events, GAMES, TEAMS)
        self.assertEqual({g: (e["home_team"], sw) for g, (e, sw) in pairs.items()},
                         {"g1": ("Central Florida Knights", False), "g2": ("Miami Hurricanes", False),
                          "g3": ("Miami (OH) RedHawks", False), "g4": ("Texas A&M Aggies", True)})
        self.assertEqual(len(unmatched), 1)
        ev, sw = pairs["g4"]
        # ESPN's home team (Texas) is the Odds API's away team: Texas A&M +3.5 = Texas -3.5.
        c = caesars_from_event(ev, ev["away_team"] if sw else ev["home_team"], "2026-10-10T12:00Z")
        self.assertEqual((c["home_spread"], c["total"]), (-3.5, 55.5))
        ev, sw = pairs["g1"]
        self.assertEqual(caesars_from_event(ev, ev["home_team"], "x")["home_spread"], -14.5)

    def test_kickoff_window(self):
        far = [event("Central Florida Knights", "Hawaii Rainbow Warriors", "2026-10-17T16:00:00Z", -14.5)]
        self.assertEqual(match_odds_api(far, GAMES, TEAMS)[0], {})


if __name__ == "__main__":
    unittest.main()
