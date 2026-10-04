"""Offline tests for the ratings (KenPom-style) model's building blocks: synthetic fights, no network."""
import datetime, os, sys, unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from ratings import engine, features, fightdata, profile, ratings, rounds  # noqa: E402


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
    """ann beats everyone; bea beats cat; cat loses a lot; dee is a wrestler with one fight."""
    return sorted([
        fight("x1", "2020-01-01", "ann", "bea", stats(50, 90), stats(30, 80)),
        fight("x2", "2020-01-01", "cat", "dee", stats(20, 60), stats(25, 50, td=4, td_a=6, ctrl=300), result="f2", method="SUB", rnd=2, time="3:00"),
        fight("x3", "2020-06-01", "ann", "cat", stats(60, 100, kd=1), stats(15, 70), method="KO/TKO", rnd=2, time="1:00"),
        fight("x4", "2021-01-01", "bea", "cat", stats(40, 80), stats(35, 90)),
        fight("x5", "2021-06-01", "ann", "dee", stats(45, 80), stats(20, 60, td=2, td_a=5, ctrl=200)),
    ], key=lambda r: (r["date"], r["event"]))


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


class AdjustTests(unittest.TestCase):
    def test_offense_rises_against_good_defense(self):
        """Same raw output against a stingier opponent must rate higher after adjustment."""
        L = engine.Ledger().replay(history())
        day = datetime.date(2022, 1, 1)
        pool = ["ann", "bea", "cat", "dee"]
        prior = 3.0
        adj = engine.adjust(lambda f: L.before(f, day), pool, lambda b: engine.per_min("sig", b), lambda b: engine.per_min("sig", b, "them"), prior, day)
        self.assertGreater(adj["ann"][0], adj["cat"][0])              # ann lands more than cat
        self.assertLess(adj["ann"][1], adj["cat"][1])                 # and allows less
        # cat's opponents (ann, bea, dee) are good defenders, so her adjusted offense beats her raw rate
        raw_cat = sum((b.me["sig"] or 0) for b in L.log["cat"]) / sum(b.minutes for b in L.log["cat"])
        self.assertGreater(adj["cat"][0], min(raw_cat, prior) * 0.9)
        # debutant = prior
        adj2 = engine.adjust(lambda f: L.before(f, day), pool + ["zed"], lambda b: engine.per_min("sig", b), lambda b: engine.per_min("sig", b, "them"), prior, day)
        self.assertAlmostEqual(adj2["zed"][0], prior)

    def test_fade_ratio(self):
        self.assertIsNone(engine.fade_ratio([10], 300))
        self.assertIsNone(engine.fade_ratio([10, 3], 330))             # 30 seconds into round 2: too little
        self.assertAlmostEqual(engine.fade_ratio([10, 10, 10], 900), 1.0)
        self.assertLess(engine.fade_ratio([20, 5, 5], 900), 1.0)       # fading
        self.assertGreater(engine.fade_ratio([0, 10, 10], 900), 1.0)   # slow start, no blow-up


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

    def test_features_are_antisymmetric(self):
        L = engine.Ledger().replay(history())
        day = datetime.date(2022, 1, 1)
        P = profile.Priors(L, day)
        T = ratings.compute(L, day, pool=["ann", "bea", "cat", "dee"])
        A = profile.raw_profile(L, "ann", {"dob": "1992-01-01", "height": 70, "reach": 72, "stance": "Orthodox"}, day, "lightweight", priors=P)
        B = profile.raw_profile(L, "cat", {"dob": "1995-01-01", "height": 68, "reach": 70, "stance": "Southpaw"}, day, "lightweight", priors=P)
        A["adj"], B["adj"] = T["ann"], T["cat"]
        x, y = features.matchup(A, B, 5), features.matchup(B, A, 5)
        for k in x:
            self.assertAlmostEqual(x[k], -y[k], places=9, msg=k)
        self.assertEqual(set(x), set(features.ALL_FEATURES))
        self.assertGreater(x["rating"], 0)   # ann rates above cat, whom she knocked out

    def test_ranks_and_sos(self):
        L = engine.Ledger().replay(history())
        day = datetime.date(2022, 1, 1)
        T = ratings.compute(L, day, pool=["ann", "bea", "cat", "dee"])
        self.assertGreater(T["ann"]["rating"], T["cat"]["rating"])
        # strength of schedule is the recency-weighted mean of the opponents' ratings
        opp = [(b.opp, engine.recency_weight((day - b.day).days, ratings.HALF_LIFE)) for b in L.log["cat"]]
        self.assertAlmostEqual(T["cat"]["sos"], sum(w * T[o]["rating"] for o, w in opp) / sum(w for _, w in opp))
        self.assertGreater(T["ann"]["luck"], -0.5)
        R = ratings.ranks(T, L, day, lambda f: "lightweight")
        self.assertEqual(R["ann"]["rank"], 1)
        self.assertEqual(R["ann"]["of"], 4)


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
        for k in ("wrestler", "power_striker", "kicker", "counter"):
            self.assertAlmostEqual(s[k], 1.0, places=5, msg=k)   # a division-average fighter scores 1.0 on each


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
