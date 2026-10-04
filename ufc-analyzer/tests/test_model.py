"""Offline tests for the prediction model's building blocks (synthetic fights, no network)."""
import os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import dataset, engine, espn_hist, features, learn, market_hist  # noqa: E402


def fight(fid, f1, f2, result="f1", method="KO/TKO", rnd=1, time="2:30", rounds=3, wc="Lightweight", stats=True):
    s = {"kd": 1, "sig": 30, "sig_a": 60, "tot": 40, "tot_a": 70, "td": 1, "td_a": 2, "sub": 0, "rev": 0, "ctrl": 60,
         "head": 20, "head_a": 45, "body": 5, "body_a": 8, "leg": 5, "leg_a": 7, "dist": 25, "dist_a": 50,
         "clinch": 3, "clinch_a": 5, "ground": 2, "ground_a": 5}
    s2 = dict(s, kd=0, sig=10, sig_a=40, td=0, td_a=3, ctrl=10)
    return {"id": fid, "f1": f1, "f2": f2, "n1": f1.upper(), "n2": f2.upper(), "result": result, "method": method,
            "round": rnd, "time": time, "rounds": rounds, "wc": wc, "title": False, "order": 0,
            "s1": s if stats else {}, "s2": s2 if stats else {}}


def history():
    events = {
        "e1": {"id": "e1", "date": "2020-01-01", "fights": ["x1", "x2"]},
        "e2": {"id": "e2", "date": "2020-06-01", "fights": ["x3"]},
        "e3": {"id": "e3", "date": "2021-01-01", "fights": ["x4"]},
    }
    fights = {
        "x1": fight("x1", "ann", "bea"),
        "x2": fight("x2", "cat", "dee", method="U-DEC", rnd=3, time="5:00"),
        "x3": fight("x3", "ann", "cat", method="SUB", rnd=2, time="1:00"),
        "x4": fight("x4", "bea", "dee", result="draw", method="M-DEC", rnd=3, time="5:00"),
    }
    for f in fights.values():
        f["date"] = next(e["date"] for e in events.values() if f["id"] in e["fights"])
    fighters = {"ann": {"dob": "1990-01-01", "height": 70, "reach": 72, "stance": "Orthodox", "record": "12-1-0"},
                "bea": {"dob": "1985-01-01", "height": 68, "reach": 70, "stance": "Southpaw", "record": "8-4-1"},
                "cat": {"dob": "1992-05-05", "height": 69, "reach": None, "stance": "Orthodox", "record": "10-2-0"},
                "dee": {"dob": None, "height": None, "reach": None, "stance": None, "record": "5-5-0"}}
    return events, fights, fighters


ESPN = {"ann": {"espn": "1", "hist": [
    ["2022-03-01", "W", 0, "ko"],     # regional win after leaving the UFC: must not count before 2022
    ["2020-06-01", "W", 1, "sub"],    # UFC fight (excluded: not "outside")
    ["2019-05-01", "W", 0, "dec"],
    ["2018-05-01", "L", 0, "dec"],
    ["2017-05-01", "W", 0, "ko"],
]}}


class EngineTests(unittest.TestCase):
    def test_helpers(self):
        self.assertEqual(engine.finish_seconds({"round": 2, "time": "1:30"}), 390)
        self.assertEqual(engine.method_class("KO/TKO"), "ko")
        self.assertEqual(engine.method_class("TKO - Doctor's Stoppage"), "ko")
        self.assertEqual(engine.method_class("SUB"), "sub")
        self.assertEqual(engine.method_class("S-DEC"), "dec")
        self.assertEqual(engine.method_class("Overturned"), "other")
        self.assertEqual(engine.method_class("CNC"), "ko")              # "could not continue" with a winner
        self.assertEqual(engine.weight_class("UFC Women's Flyweight Title Bout"), "w flyweight")
        self.assertEqual(engine.weight_class("Light Heavyweight Bout"), "light heavyweight")
        self.assertEqual(engine.weight_class("Heavyweight"), "heavyweight")

    def test_elo_moves_toward_winner_and_is_point_in_time(self):
        ev, fi, _ = history()
        eng = engine.Engine()
        seen = {}

        def on_event(e, bouts, day):
            for r in bouts:
                seen[r["id"]] = (eng.get(r["f1"]).elo, eng.get(r["f2"]).elo, eng.get(r["f1"]).fights)
        eng.replay(ev, fi, on_event=on_event)
        self.assertEqual(seen["x1"], (1500.0, 1500.0, 0))          # nothing known before the first fight
        self.assertGreater(seen["x3"][0], 1500.0)                  # ann won x1, so she's rated up before x3
        self.assertEqual(seen["x3"][2], 1)                         # and has exactly one prior fight
        self.assertGreater(eng.get("ann").elo, eng.get("cat").elo)
        self.assertEqual(eng.get("bea").draws, 1)
        self.assertEqual(eng.get("ann").wins_by["sub"], 1)

    def test_until_stops_before_date(self):
        ev, fi, _ = history()
        eng = engine.Engine().replay(ev, fi, until="2020-06-01")
        self.assertEqual(eng.get("ann").fights, 1)                 # x3 on 2020-06-01 is not applied

    def test_same_day_cards_see_state_from_before_that_day(self):
        ev, fi, _ = history()
        ev["e2b"] = {"id": "e2b", "date": "2020-06-01", "fights": ["x5"]}   # a second card on x3's date
        fi["x5"] = dict(fight("x5", "bea", "dee"), date="2020-06-01")
        eng = engine.Engine()
        seen = {}

        def on_event(e, bouts, day):
            seen[e["id"]] = (eng.n_div.copy() if hasattr(eng, "n_div") else None, eng.get("ann").fights, eng.as_of)
        eng.replay(ev, fi, on_event=on_event)
        self.assertEqual(seen["e2"][2], seen["e2b"][2])            # neither card is applied before the other
        self.assertEqual(seen["e2b"][1], 1)                         # ann's x3 (same day) isn't in e2b's state

    def test_layoff_never_negative(self):
        ev, fi, _ = history()
        eng = engine.Engine().replay(ev, fi)
        import datetime
        p = features.fighter_profile(eng, eng.get("ann"), {}, datetime.date(2020, 3, 1), "lightweight", (0, 0))
        self.assertEqual(p["layoff"], 0)                            # a date before her last fight can't crash log1p
        features.win_features(p, p)


class FeatureTests(unittest.TestCase):
    def test_antisymmetric(self):
        ev, fi, fr = history()
        rows, eng, _ = dataset.build_rows(ev, fi, fr, since="2000-01-01", espn_histories=ESPN)
        r = next(r for r in rows if r["id"] == "x3")
        flipped = features.win_features(r["B"], r["A"])
        for k, v in r["x"].items():
            self.assertAlmostEqual(v, -flipped[k], places=9, msg=k)
        self.assertEqual(set(r["x"]), set(features.WIN_FEATURES))

    def test_labels_follow_orientation(self):
        ev, fi, fr = history()
        rows, _, _ = dataset.build_rows(ev, fi, fr, since="2000-01-01", espn_histories=ESPN)
        for r in rows:
            if r["result"] in ("f1", "f2"):
                winner = fi[r["id"]]["f1"] if r["result"] == "f1" else fi[r["id"]]["f2"]
                self.assertEqual(r["y"], 1 if r["a"] == winner else 0)
            else:
                self.assertIsNone(r["y"])

    def test_outside_record_is_point_in_time(self):
        hist = ESPN["ann"]["hist"]
        self.assertEqual(espn_hist.outside_before(hist, "2020-01-01"), (2, 1, 1))   # UFC fights and later fights excluded
        self.assertEqual(espn_hist.outside_before(hist, "2023-01-01"), (3, 1, 2))   # the post-UFC regional win counts only after it happened
        ev, fi, fr = history()
        rows, _, _ = dataset.build_rows(ev, fi, fr, since="2000-01-01", espn_histories=ESPN)
        r = next(r for r in rows if r["id"] == "x1")
        ann = r["A"] if r["a"] == "ann" else r["B"]
        bea = r["B"] if r["a"] == "ann" else r["A"]
        self.assertEqual(ann["outside_known"], 1.0)
        self.assertAlmostEqual(ann["outside_win_pct"], (2 + 3) / (2 + 1 + 4) - 0.75)   # 2-1 outside, debut fight: no fade yet
        self.assertEqual(bea["outside_known"], 0.0)            # no ESPN history: neutral
        self.assertEqual(bea["outside_win_pct"], 0.0)

    def test_debutant_profile_uses_division_priors(self):
        ev, fi, fr = history()
        eng = engine.Engine().replay(ev, fi)
        new = engine.Fighter("zed", 1500.0)
        import datetime
        p = features.fighter_profile(eng, new, {}, datetime.date(2022, 1, 1), "lightweight", (0, 0))
        self.assertEqual(p["debut"], 1.0)
        self.assertAlmostEqual(p["slpm"], eng.div_rate("lightweight", "sig"), places=6)


class LearnTests(unittest.TestCase):
    def test_backtest(self):
        bets = [{"p": 0.6, "odds": 100, "won": 1}, {"p": 0.6, "odds": 100, "won": 0}, {"p": 0.4, "odds": 100, "won": 1}]
        r = learn.backtest(bets, threshold=0.05)
        self.assertEqual(r["bets"], 2)          # the 0.4 @ +100 bet is -EV and skipped
        self.assertEqual(r["profit"], 0.0)
        self.assertEqual(r["roi"], 0.0)

    def test_calibration_and_metrics(self):
        ps, ys = [0.9, 0.8, 0.3, 0.2], [1, 1, 0, 0]
        self.assertEqual(learn.accuracy(ps, ys), 1.0)
        self.assertLess(learn.log_loss(ps, ys), 0.3)
        rows = learn.calibration(ps, ys, bins=5)
        self.assertEqual(sum(r[2] for r in rows), 4)


class MarketJoinTests(unittest.TestCase):
    def test_join_orients_to_f1(self):
        import calendar
        ts = calendar.timegm((2021, 1, 2, 12, 0, 0))
        fights = {"x4": dict(fight("x4", "bea", "dee"), date="2021-01-01", n1="Bea Smith", n2="Dee Jones")}
        matchups = {"9": {"matchup": 9, "date": ts, "a": "Dee Jones", "b": "Bea Smith",
                          "aOpen": -200, "aLo": -250, "aHi": -220, "bOpen": 170, "bLo": 180, "bHi": 200}}
        j = market_hist.join(fights, matchups)["x4"]
        self.assertEqual(j["open1"], 170)        # Bea's own line, although BFO listed Dee first
        self.assertLess(j["close_fair"], 0.5)    # Bea is the underdog
        self.assertEqual(j["worst1"], 180)       # Bea's least generous closing price

    def test_inplay_closing_range_is_dropped(self):
        import calendar
        ts = calendar.timegm((2021, 4, 10, 12, 0, 0))
        fights = {"y1": dict(fight("y1", "al", "so"), date="2021-04-10", n1="Arnold Allen", n2="Sodiq Yusuff")}
        matchups = {"7": {"matchup": 7, "date": ts, "a": "Arnold Allen", "b": "Sodiq Yusuff",
                          "aOpen": 100, "aLo": -3500, "aHi": 135, "bOpen": -120, "bLo": -161, "bHi": 1480}}
        j = market_hist.join(fights, matchups)["y1"]
        self.assertTrue(j.get("close_inplay"))
        self.assertNotIn("close_fair", j)        # a price taken mid-fight would leak the result
        self.assertIsNone(j["worst1"])
        self.assertIn("open_fair", j)            # the opening line is still fine




class FakeStore(dict):
    """market.history stand-in: get(key) and stamp(key) (when the key was last written)."""
    def __init__(self, data, stamps=None):
        super().__init__(data)
        self.stamps = stamps or {}

    def stamp(self, key):
        return self.stamps.get(key, 1e10 if key in self else None)


class LedgerTests(unittest.TestCase):
    def test_record_dedupe_and_settle(self):
        import tempfile
        import espn, ledger
        tmp = tempfile.mkdtemp()
        old_path, old_card = ledger.PATH, espn.card
        ledger.PATH = os.path.join(tmp, "ledger.json")
        fighters = [{"name": "Ann A", "winner": False}, {"name": "Bea B", "winner": False}]
        fight = {"id": "f1", "status": {"state": "pre"}, "fighters": fighters}
        card = {"id": "e1", "name": "Test Card", "date": 2e9, "fights": [fight]}
        pred = {"market": 0.6, "p": [0.55, 0.45], "blend": [0.58, 0.42], "sides": [{"caesars": -130}, {"caesars": 110}]}
        dec = {"action": "BET", "side": 1, "ev": 0.04, "evMarket": 0.01, "tier": "Market value"}
        try:
            watch = dict(dec, action="WATCH")
            self.assertIsNotNone(ledger.record("e1", card, fight, watch, pred))
            self.assertIsNone(ledger.record("e1", card, fight, watch, pred))         # WATCH logged once per fight/side
            self.assertIsNotNone(ledger.record("e1", card, fight, dec, pred))        # turning into a BET is logged too
            self.assertIsNone(ledger.record("e1", card, fight, dec, pred))
            pre = ledger.report(FakeStore({"e1:f1": [[1, -130, 110, 0.62]]}))
            self.assertTrue(all(e["clv"] is None for e in pre["entries"]))          # no CLV before the fight starts
            self.assertIsNone(pre["summary"]["all"]["clv"])
            self.assertIsNotNone(ledger.record("e1", card, fight, dec, pred, source="user", price=115, stake=10, side=1))
            settled = {"id": "f1", "status": {"state": "post"}, "date": 2e9,
                       "fighters": [{"name": "Ann A", "winner": False}, {"name": "Bea B", "winner": True}]}
            espn.card = lambda eid: dict(card, fights=[settled])
            hist = FakeStore({"e1:f1": [[1, -130, 110, 0.62], [2, -140, 120, 0.56]], "e1:f1:last": [3, -140, 120, 0.55]})
            stale = ledger.report(FakeStore(dict(hist), {"e1:f1:last": 2e9 - 7200}))
            self.assertTrue(all(e["clv"] is None for e in stale["entries"]))        # last price seen 2h before: no close
            rep = ledger.report(hist)                                                 # closing fair for A = 0.55
            user = next(e for e in rep["entries"] if e["source"] == "user")
            self.assertAlmostEqual(user["closeFair"], 0.45)
            self.assertAlmostEqual(user["clv"], round(0.45 * 2.15 - 1, 4))
            self.assertEqual(user["result"], "won")
            self.assertAlmostEqual(user["profit"], 11.5)
            self.assertEqual(rep["summary"]["your_bets"]["settled"], 1)
            self.assertEqual(rep["summary"]["flagged_bets"]["entries"], 1)
        finally:
            ledger.PATH, espn.card = old_path, old_card


class ServingTests(unittest.TestCase):
    def test_espn_dob_is_day_first(self):
        import datetime
        from model.predict import parse_espn_dob
        today = datetime.date(2026, 10, 4)
        self.assertEqual(parse_espn_dob("26/5/1992", today=today), "1992-05-26")
        self.assertEqual(parse_espn_dob("5/8/2004", today=today), "2004-08-05")           # day-first by default
        self.assertEqual(parse_espn_dob("5/8/2004", age=22, today=today), "2004-08-05")
        self.assertEqual(parse_espn_dob("9/12/1990", age=36, today=today), "1990-09-12")  # ESPN's age breaks the tie
        self.assertIsNone(parse_espn_dob("", today=today))

    def test_decide_regimes(self):
        import modelapi, value
        lines = {value.TARGET_BOOK: [-165, 140], "A": [-160, 135], "B": [-155, 130], "C": [-150, 128]}
        view = {"lines": lines, "value": {"books": 3, "fair": [0.60, 0.40]}}
        early = {"active": True, "open_gate": True, "hours": 200.0}
        late = {"active": True, "open_gate": True, "hours": 30.0}
        d = modelapi.decide(0.66, 0.60, 0.66, view, early, False, False)
        self.assertEqual((d["action"], d["side"], d["tier"]), ("BET", 0, "Early-line blend"))   # tested at opening prices
        d = modelapi.decide(0.66, 0.60, 0.66, view, late, False, False)
        self.assertEqual(d["action"], "WATCH")      # inside 4 days only market value is a BET with the single-model blend
        late_r = dict(late, uses_ratings=True, close_gate=True)
        d = modelapi.decide(0.66, 0.60, 0.66, view, late_r, False, False)
        self.assertEqual((d["action"], d["tier"]), ("BET", "Blend (fight week)"))   # with the ratings model in the blend, tested at fight-week prices
        d = modelapi.decide(0.66, 0.60, 0.66, view, early, True, False)
        self.assertEqual(d["action"], "WATCH")      # a fighter with under 2 UFC fights
        d = modelapi.decide(0.66, 0.60, 0.85, view, early, False, False)
        self.assertEqual(d["action"], "BET")        # a big model-market gap is a check-the-news note, not a block
        self.assertTrue(any("check for news" in r for r in d["reasons"]))
        d = modelapi.decide(0.66, 0.60, 0.66, view, early, False, True)
        self.assertEqual(d["action"], "WATCH")      # a fighter's latest fight is missing from the history
        good = dict(view, lines=dict(lines, **{value.TARGET_BOOK: [-130, 110]}))
        d = modelapi.decide(0.60, 0.60, 0.62, good, late, False, False)
        self.assertEqual((d["action"], d["tier"]), ("BET", "Market value + model agrees"))
        d = modelapi.decide(0.66, 0.60, 0.58, view, early, False, False)
        self.assertTrue(any("firming up favorites" in r for r in d["reasons"]))   # model below market: say so

    def test_card_day_is_the_us_date(self):
        import calendar, datetime, modelapi
        self.assertEqual(modelapi.card_day(calendar.timegm((2025, 12, 14, 0, 0, 0))), datetime.date(2025, 12, 13))   # US Saturday night
        self.assertEqual(modelapi.card_day(calendar.timegm((2025, 10, 25, 14, 0, 0))), datetime.date(2025, 10, 25))  # Abu Dhabi afternoon

    def test_pending_bouts(self):
        from model import scrape
        row = ('<tr class="b-fight-details__table-row" data-link="http://ufcstats.com/fight-details/{fid}">'
               '<td>{flag}</td><td><a href="http://ufcstats.com/fighter-details/aaa">A</a>'
               '<a href="http://ufcstats.com/fighter-details/bbb">B</a></td>' + "<td></td>" * 8 + "</tr>")
        done = row.format(fid="f1", flag='<i class="b-flag__text">win</i>')
        live = row.format(fid="f2", flag="")
        self.assertEqual(scrape.pending_bouts(done + live), 1)
        self.assertEqual(scrape.pending_bouts(done), 0)


class PropMappingJS(unittest.TestCase):
    def test_prop_labels(self):
        import shutil, subprocess
        node = shutil.which("node")
        if not node:
            self.skipTest("node not installed")
        r = subprocess.run([node, os.path.join(HERE, "props_map.test.js")], capture_output=True, text=True)
        self.assertEqual(r.returncode, 0, r.stdout + r.stderr)


if __name__ == "__main__":
    unittest.main()
