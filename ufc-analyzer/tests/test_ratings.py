"""Offline tests for the ratings (KenPom-style) model's building blocks: synthetic fights, no network."""
import datetime, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from ratings import dataset, efficiency, engine, features, fightdata, flatbet, profile, rounds  # noqa: E402
from ratings.efficiency import DIMS, DIM_INDEX, Efficiency, BradleyTerry, side_vectors  # noqa: E402


def stats(sig=30, sig_a=60, td=1, td_a=2, kd=0, ctrl=60, sub=0, ground=2):
    return {"kd": kd, "sig": sig, "sig_a": sig_a, "tot": sig + 10, "tot_a": sig_a + 10, "td": td, "td_a": td_a, "sub": sub, "rev": 0, "ctrl": ctrl,
            "head": int(sig * 0.6), "head_a": int(sig_a * 0.7), "body": int(sig * 0.2), "body_a": int(sig_a * 0.15), "leg": sig - int(sig * 0.6) - int(sig * 0.2),
            "leg_a": sig_a - int(sig_a * 0.7) - int(sig_a * 0.15), "dist": sig - ground - 2, "dist_a": sig_a - ground - 4, "clinch": 2, "clinch_a": 4,
            "ground": ground, "ground_a": ground + 2}


def fight(fid, date, f1, f2, s1, s2, result="f1", method="U-DEC", rnd=3, time="5:00", rounds=3, wc="Lightweight", rd=None):
    r = {"id": fid, "date": date, "event": "e" + date, "f1": f1, "f2": f2, "n1": f1.upper(), "n2": f2.upper(), "result": result,
         "method": method, "round": rnd, "time": time, "rounds": rounds, "wc": wc, "title": False, "order": 1, "s1": s1, "s2": s2}
    r.update(kind=fightdata.method_class(method), div=fightdata.division(wc), secs=fightdata.fight_seconds(r), rounds_data=rd)
    return r


def history():
    """ann beats everyone; bea beats cat; cat loses a lot; dee is a wrestler with two fights."""
    return sorted([
        fight("x1", "2020-01-01", "ann", "bea", stats(50, 90), stats(30, 80)),
        fight("x2", "2020-01-01", "cat", "dee", stats(20, 60), stats(25, 50, td=4, td_a=6, ctrl=300), result="f2", method="SUB", rnd=2, time="3:00"),
        fight("x3", "2020-06-01", "ann", "cat", stats(60, 100, kd=1), stats(15, 70), method="KO/TKO", rnd=2, time="1:00"),
        fight("x4", "2021-01-01", "bea", "cat", stats(40, 80), stats(35, 90)),
        fight("x5", "2021-06-01", "ann", "dee", stats(45, 80), stats(20, 60, td=2, td_a=5, ctrl=200)),
    ], key=lambda r: (r["date"], r["event"]))


WEIGHTS = {"sig": 0.03, "head": 0.01, "ground": 0.02, "kd": 0.4, "td": 0.1, "ctrl": 0.08, "sub": 0.3, "tot": 0.01}


def replay(fights, until="2100-01-01"):
    R = dataset.Replay(infight={"sig": 0.03, "kd": 0.4, "td": 0.1, "ctrl": 0.08}, weights=WEIGHTS)
    for r in fights:
        if r["date"] >= until:
            break
        R.apply(r, datetime.date.fromisoformat(r["date"]).toordinal())
    return R


class LedgerTests(unittest.TestCase):
    def test_point_in_time_and_sides(self):
        L = engine.Ledger().replay(history(), until="2021-01-01")
        self.assertEqual(len(L.log["ann"]), 2)                       # x5 (2021-06) and x4 (2021-01) are after the cutoff
        self.assertEqual(L.before("ann", datetime.date(2020, 6, 1)), L.log["ann"][:1])   # the same-day fight is not "before"
        b = L.log["cat"][0]                                           # cat's view of x2: she lost by sub in round 2
        self.assertEqual((b.result, b.kind, b.opp, b.secs), ("loss", "sub", "dee", 480))
        self.assertEqual(b.them["td"], 4)
        self.assertEqual(fightdata.division("UFC Women's Strawweight Title Bout"), "w strawweight")
        self.assertEqual(fightdata.division("Light Heavyweight Bout"), "light heavyweight")

    def test_no_contests_are_ignored(self):
        h = history()
        h.append(fight("x6", "2021-07-01", "ann", "bea", stats(), stats(), result="nc", method="Overturned"))
        L = engine.Ledger().replay(h)
        self.assertEqual(len(L.log["ann"]), 3)


class EfficiencyTests(unittest.TestCase):
    def test_side_vectors(self):
        y, e = side_vectors(stats(30, 60, kd=1, ctrl=120), stats(), 10.0, True)
        self.assertEqual(y[DIM_INDEX["sig"]], 30)
        self.assertEqual(y[DIM_INDEX["ctrl"]], 2.0)                   # minutes
        self.assertEqual((y[DIM_INDEX["fin"]], e[DIM_INDEX["fin"]]), (1.0, 10.0))
        self.assertEqual((y[DIM_INDEX["pow"]], e[DIM_INDEX["pow"]]), (1.0, 18))   # knockdowns per head strike landed

    def test_offense_rises_against_good_defense_and_debutant_is_average(self):
        R = replay(history())
        t = datetime.date(2022, 1, 1).toordinal()
        R.converge(t)
        E = R.eff
        k = DIM_INDEX["sig"]
        Oann, Dann = E.ratios("ann")
        Ocat, Dcat = E.ratios("cat")
        self.assertGreater(Oann[k], Ocat[k])              # ann lands more
        self.assertLess(Dann[k], Dcat[k])                 # and allows less (lower is better)
        self.assertEqual(E.ratios("zed"), ([1.0] * len(DIMS), [1.0] * len(DIMS)))   # unknown fighter = average
        ao, ad, em = E.composite("ann", "lightweight")
        self.assertGreater(em, E.composite("cat", "lightweight")[2])
        # cat's opponents (ann, bea, dee) are better than average defenders, so her adjusted offense sits
        # above her raw observed/expected against average defense
        raw = [s for s in E.sides if E.ids[s[0]] == "cat"]
        obs = sum(s[2][k] / s[4][k] for s in raw); exp_avg = sum(s[3][k] for s in raw)
        self.assertGreater(Ocat[k], (obs + E.K[k]) / (exp_avg + E.K[k]) * 0.99)

    def test_numpy_and_python_sweeps_agree(self):
        try:
            import numpy  # noqa: F401
        except Exception:
            self.skipTest("numpy not installed")
        import copy
        R = replay(history())
        t = datetime.date(2022, 1, 1).toordinal()
        E1, E2 = R.eff, copy.deepcopy(R.eff)
        E1._sweep_np(t, 30, 1e-9)
        E2._sweep_py(t, 30, 1e-9)
        for a, b in zip(E1.O, E2.O):
            for x, y in zip(a, b):
                self.assertAlmostEqual(x, y, places=9)

    def test_baselines_are_point_in_time(self):
        """A fight added later never changes the baseline frozen into an earlier side."""
        R = replay(history(), until="2021-01-01")
        rb_before = R.eff.sides[0][4][:]
        R.apply(fight("x9", "2021-02-01", "ann", "bea", stats(90, 120), stats(80, 120)), datetime.date(2021, 2, 1).toordinal())
        self.assertEqual(R.eff.sides[0][4], rb_before)
        self.assertGreater(R.eff.rbar("lightweight")[DIM_INDEX["sig"]], rb_before[DIM_INDEX["sig"]])   # the new high-output fight lifts today's baseline

    def test_bradley_terry(self):
        bt = BradleyTerry()
        t = datetime.date(2021, 1, 1).toordinal()
        for i in range(3):
            bt.add("ann", "cat", 1.0, t)
            bt.add("cat", "bea", 1.0, t)
        bt.sweep(t, n=30)
        self.assertGreater(bt.get("ann"), bt.get("cat"))
        self.assertGreater(bt.get("cat"), bt.get("bea"))
        self.assertAlmostEqual(bt.get("ann") + bt.get("cat") + bt.get("bea"), 0.0, places=6)   # ridge keeps the mean at zero

    def test_training_and_serving_use_the_same_weights(self):
        """The composites in training rows must come from the same cage-point weights serving uses."""
        from ratings import cagepoints
        R = dataset.Replay()
        self.assertEqual(R.eff.weights, cagepoints.load() or efficiency.DEFAULT_WEIGHTS)
        rows, R = dataset.build_rows({"fights": history(), "fighters": {}, "espn": {}}, since="2021-06-01", log=lambda *a: None, replay=replay([]))
        r = rows[0]
        for P in (r["A"], r["B"]):
            rb, O = P["eff"]["rb"], P["eff"]["O"]
            self.assertAlmostEqual(P["eff"]["adjo"], sum(WEIGHTS[k] * rb[k] * O[k] * 15 for k in WEIGHTS), places=9)

    def test_catchweight_is_rated_in_the_usual_division(self):
        h = history() + [fight("x9", "2021-09-01", "ann", "bea", stats(), stats(), wc="Catch Weight")]
        rows, R = dataset.build_rows({"fights": h, "fighters": {}, "espn": {}}, since="2021-09-01", log=lambda *a: None, replay=replay([]))
        self.assertEqual((rows[0]["bout_div"], rows[0]["div"]), ("catch", "lightweight"))
        self.assertEqual(dataset.rating_division(R.ledger, "catch", "zed", "yan"), "catch")   # two unknowns stay catch
        self.assertEqual(dataset.rating_division(R.ledger, "catch", "bea", "ann"), dataset.rating_division(R.ledger, "catch", "ann", "bea"))

    def test_luck_and_sos(self):
        R = replay(history())
        t = datetime.date(2022, 1, 1).toordinal()
        R.converge(t)
        p = R.eff_profile("cat", "lightweight", t)
        self.assertLess(p["luck"], 0.1)                                   # cat has not outperformed her stat lines
        self.assertGreater(p["sos"], R.eff_profile("ann", "lightweight", t)["sos"] - 10)   # finite, computed
        self.assertEqual(set(p["O"]), {d[0] for d in DIMS})


class ProfileTests(unittest.TestCase):
    def test_raw_profile_values(self):
        L = engine.Ledger().replay(history())
        day = datetime.date(2022, 1, 1)
        P = profile.Priors(L, day)
        ann = profile.raw_profile(L, "ann", {"dob": "1992-01-01", "height": 70, "reach": 72, "stance": "Southpaw"}, day, "lightweight", priors=P, outside=(5, 1, 3, True))
        self.assertEqual(ann["fights"], 3)
        self.assertEqual(ann["stance"], "southpaw")
        self.assertAlmostEqual(ann["age"], 30.0, places=1)
        self.assertEqual(ann["last5_wins"], 3)
        self.assertEqual(ann["streak"], 3)
        self.assertEqual(ann["layoff_days"], (day - datetime.date(2021, 6, 1)).days)
        self.assertEqual(ann["layoff_bucket"], "180-365")
        self.assertEqual(ann["outside_wins"], 5)
        self.assertGreater(ann["str_diff"], 0)
        cat = profile.raw_profile(L, "cat", {}, day, "lightweight", priors=P)
        self.assertEqual(cat["off_loss"], 1.0)
        self.assertEqual(cat["ko_losses"], 1)
        self.assertLess(cat["win_pct"], 0.5)
        zed = profile.raw_profile(L, "zed", {}, day, "lightweight", priors=P)
        self.assertEqual(zed["debut"], 1.0)
        self.assertAlmostEqual(zed["slpm"], P.get("lightweight")["sig_15"] / 15)   # a debutant sits at the prior

    def test_rows_and_features_are_antisymmetric(self):
        data = {"fights": history(), "fighters": {"ann": {"dob": "1992-01-01", "height": 70, "reach": 72, "stance": "Orthodox"},
                                                  "cat": {"dob": "1995-01-01", "height": 68, "reach": 70, "stance": "Southpaw"}}, "espn": {}}
        rows, R = dataset.build_rows(data, since="2020-06-01", log=lambda *a: None, replay=replay([]))
        self.assertEqual([r["id"] for r in rows], ["x3", "x4", "x5"])
        r = rows[0]                                                     # ann vs cat on 2020-06-01: only x1 and x2 are known
        self.assertEqual({r["A"]["fights"], r["B"]["fights"]}, {1})
        x, y = features.matchup(r["A"], r["B"], 5), features.matchup(r["B"], r["A"], 5)
        for k in x:
            self.assertAlmostEqual(x[k], -y[k], places=9, msg=k)
        self.assertEqual(set(x), set(features.ALL_FEATURES))
        a_is_ann = r["a"] == "ann"
        self.assertGreater(x["adjem"] if a_is_ann else -x["adjem"], 0)   # ann (won x1 big) rates above cat (lost x2)
        self.assertGreater(x["mult_sig"] if a_is_ann else -x["mult_sig"], 0)

    def test_ranks_and_tiers(self):
        from ratings import predict
        R = replay(history())
        day = datetime.date(2022, 1, 1)
        R.converge(day.toordinal())
        tiers = {f: predict.tier_of(R, f, day) for f in ("ann", "bea", "cat", "dee")}
        self.assertEqual(tiers["ann"]["tier"], "developing")                # 3 fights, ~37 minutes
        adjem = {f: R.eff.composite(f, "lightweight")[2] for f in tiers}
        rk = predict.ranks(adjem, {f: "lightweight" for f in tiers}, tiers)
        self.assertEqual(rk["ann"]["rank"], 1)
        self.assertIsNone(rk["dee"]["rank"])                                # 2 fights: unranked
        self.assertEqual(rk["ann"]["active"], 4)


class ServingHelpersTests(unittest.TestCase):
    def test_usual_division_ignores_catchweights(self):
        from ratings import predict
        L = engine.Ledger().replay(history() + [fight("x9", "2021-09-01", "ann", "bea", stats(), stats(), wc="Catch Weight")])
        self.assertEqual(predict.usual_division(L.log["ann"]), "lightweight")
        self.assertEqual(predict.usual_division([]), "catch")

    def test_style_is_relative_to_division(self):
        from ratings import predict
        L = engine.Ledger().replay(history())
        day = datetime.date(2022, 1, 1)
        P = profile.Priors(L, day)
        dee = profile.raw_profile(L, "dee", {}, day, "lightweight", priors=P)   # takedowns and control well above the others
        self.assertEqual(predict.style_of(dee, P.get("lightweight"))["primary"], "wrestler")
        avg = profile.raw_profile(L, "nobody", {}, day, "lightweight", priors=P)
        s = predict.style_of(avg, P.get("lightweight"))["scores"]
        for k in ("wrestler", "power_striker", "kicker", "counter", "volume_striker", "clinch"):
            self.assertAlmostEqual(s[k], 1.0, places=5, msg=k)   # a division-average fighter scores 1.0 on each

    def test_fade_ratio(self):
        self.assertIsNone(engine.fade_ratio([10], 300))
        self.assertIsNone(engine.fade_ratio([10, 3], 330))             # 30 seconds into round 2: too little
        self.assertAlmostEqual(engine.fade_ratio([10, 10, 10], 900), 1.0)
        self.assertLess(engine.fade_ratio([20, 5, 5], 900), 1.0)       # fading
        self.assertGreater(engine.fade_ratio([0, 10, 10], 900), 1.0)   # slow start, no blow-up


class FlatBetTests(unittest.TestCase):
    def _fight(self, p1, y1, open_, close_fair=None, date="2024-01-06"):
        o1, o2 = open_
        a, b = (1 / flatbet.dec_odds(o1), 1 / flatbet.dec_odds(o2))
        return {"id": f"{p1}{y1}{o1}", "date": date, "year": 2024, "p1": p1, "y1": y1, "open": open_,
                "open_fair": a / (a + b), "close_fair": close_fair if close_fair is not None else a / (a + b)}

    def test_prices(self):
        self.assertEqual(flatbet.synth_price(0.5), -109)                     # a 4.4% hold split evenly: 52.2% a side
        fav, dog = flatbet.synth_price(0.7), flatbet.synth_price(0.3)
        self.assertLess(1 / flatbet.dec_odds(fav) + 1 / flatbet.dec_odds(dog) - 1, 0.045)
        self.assertGreater(1 / flatbet.dec_odds(dog) - 0.3, 1 / flatbet.dec_odds(fav) - 0.7)   # more margin on the dog
        self.assertEqual(flatbet.bucket_of(-100, False), 100)
        self.assertEqual(flatbet.bucket_of(-149, False), 100)
        self.assertEqual(flatbet.bucket_of(-150, False), 150)
        self.assertEqual(flatbet.bucket_of(-800, False), 550)
        self.assertEqual(flatbet.bucket_of(-110, True), "pickem")

    def test_picks_settle_and_skip(self):
        recs = flatbet.picks([
            self._fight(0.62, 1, (-180, 155)),        # pick f1 (the favourite), wins
            self._fight(0.40, 0, (-180, 155)),        # pick f2 (the dog), wins
            self._fight(0.55, 0, (-180, 155)),        # pick f1, loses
            self._fight(0.80, 1, (-400, 310)),        # sides with a -400 favourite: skipped
            self._fight(0.30, 0, (-400, 310)),        # against a -400 favourite: still a bet
            self._fight(0.51, 1, (-110, -110)),       # pick'em open: no opening pick
        ], stake=10, max_fav=-350, hold=0.044)
        self.assertEqual([r["bet"] for r in recs], [True, True, True, False, True, True])
        self.assertEqual([r["won"] for r in recs], [1, 1, 0, 1, 1, 1])
        self.assertEqual([r["open_right"] for r in recs], [1, 0, 0, 1, 0, None])
        self.assertAlmostEqual(recs[0]["pnl"]["listed"], 10 * (flatbet.dec_odds(-180) - 1))
        self.assertAlmostEqual(recs[1]["pnl"]["listed"], 15.5)
        self.assertEqual(recs[2]["pnl"]["listed"], -10)
        self.assertEqual(recs[0]["pnl"]["open"], 10 * (flatbet.dec_odds(flatbet.synth_price(recs[0]["open_fair"])) - 1))
        bets = [r for r in recs if r["bet"]]
        self.assertEqual(len(bets), 5)
        self.assertGreater(flatbet.total(bets, "listed"), 0)


class RoundsParserTests(unittest.TestCase):
    def test_parse_rounds_fixture(self):
        with open(os.path.join(HERE, "fixtures", "ufcstats_fight_rounds.html"), encoding="utf-8") as f:
            body = f.read()
        rr = rounds.parse_rounds(body)
        self.assertEqual([x["r"] for x in rr], [1, 2, 3, 4, 5])
        r1 = rr[0]["s"]
        self.assertEqual((r1[0]["sig"], r1[0]["sig_a"], r1[1]["sig"]), (14, 30, 17))
        self.assertEqual(r1[0]["leg"], 9)
        self.assertEqual(sum(x["s"][0]["sig"] for x in rr), 69)       # rounds add up to the fight total


if __name__ == "__main__":
    unittest.main()
