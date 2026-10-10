"""Drive parsing on synthetic ESPN summaries. Run: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from parse import parse_drives  # noqa: E402

H, A = "1", "2"


def play(pid, team, typ="Rush", down=1, dist=10, yte=75, yds=4, period=1, clock="10:00", text="run"):
    return {"id": pid, "type": {"text": typ}, "text": text, "period": {"number": period},
            "clock": {"displayValue": clock}, "statYardage": yds,
            "start": {"down": down, "distance": dist, "yardsToEndzone": yte, "team": {"id": team}}}


def td(pid, team, pat_id=61, pat_value=1, **kw):
    p = play(pid, team, typ="Rushing Touchdown", yds=5, yte=5, **kw)
    p["pointAfterAttempt"] = {"id": pat_id, "value": pat_value}
    return p


def summary(drives, scoring):
    return {"drives": {"previous": drives}, "scoringPlays": scoring}


def sp(pid, team, kind, away, home, typ="Rushing Touchdown"):
    return {"id": pid, "team": {"id": team}, "scoringType": {"name": kind},
            "type": {"text": typ}, "awayScore": away, "homeScore": home}


class ScoringReconstruction(unittest.TestCase):
    def test_bad_running_score_is_rebuilt_from_play_type(self):
        # ESPN's running score says the home TD added 1 point; the play type says 7.
        drives = [{"team": {"id": H}, "result": "TD", "plays": [play("a", H), td("b", H)]},
                  {"team": {"id": A}, "result": "FG", "plays": [play("c", A, clock="5:00"),
                   play("d", A, typ="Field Goal Good", down=4, clock="4:00")]}]
        scoring = [sp("b", H, "touchdown", 0, 1), sp("d", A, "field-goal", 3, 7, typ="Field Goal Good")]
        out, note, _ = parse_drives(summary(drives, scoring), H, A, {"home": 7, "away": 3})
        self.assertEqual([d["pts"] for d in out], [7, 3])
        self.assertIn("ESPN running score +1, rebuilt 7", note)

    def test_unknown_extra_points_share_the_gap_to_the_final(self):
        drives = [{"team": {"id": H}, "result": "TD", "plays": [td("b", H, pat_id=0, pat_value=0)]},
                  {"team": {"id": H}, "result": "TD", "plays": [td("c", H, pat_id=0, pat_value=0, clock="5:00")]}]
        scoring = [sp("b", H, "touchdown", 0, 6), sp("c", H, "touchdown", 0, 12)]
        out, _, _ = parse_drives(summary(drives, scoring), H, A, {"home": 14, "away": 0})
        self.assertEqual([d["pts"] for d in out], [7, 7])

    def test_unreconcilable_game_is_dropped(self):
        drives = [{"team": {"id": H}, "result": "TD", "plays": [td("b", H)]}]
        out, note, _ = parse_drives(summary(drives, [sp("b", H, "touchdown", 0, 7)]), H, A,
                                 {"home": 21, "away": 0})
        self.assertEqual(out, [])
        self.assertIn("can't be reconciled", note)

    def test_safety_credited_to_offense_is_not_offensive_points(self):
        # Home punts; the returner is tackled in his end zone: the safety goes to home.
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": [
            play("a", H), play("p", H, typ="Punt", down=4, text="punt returned, tackled for a SAFETY")]}]
        scoring = [sp("p", H, "safety", 0, 2, typ="Safety")]
        out, _, _ = parse_drives(summary(drives, scoring), H, A, {"home": 2, "away": 0})
        self.assertEqual(out[0]["pts"], 0)


class DriveRules(unittest.TestCase):
    def test_offense_comes_from_the_plays_not_the_label(self):
        drives = [{"team": {"id": A}, "result": "PUNT",
                   "plays": [play("a", H), play("b", H, down=2), play("c", H, down=3)]}]
        out, note, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(out[0]["off"], H)
        self.assertIn("relabeled", note)

    def test_duplicate_snap_counted_once(self):
        dup = play("a", H)
        twin = dict(dup, id="a2")
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": [dup, twin, play("b", H, down=2)]}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(len(out[0]["plays"]), 2)

    def test_end_of_half_is_decided_by_start_time_not_result(self):
        late_score = {"team": {"id": H}, "result": "FG", "plays": [
            play("a", H, period=2, clock="0:40"), play("f", H, typ="Field Goal Good", down=4, period=2, clock="0:05")]}
        two_minute_fail = {"team": {"id": A}, "result": "END OF HALF", "plays": [
            play("b", A, period=4, clock="1:50"), play("c", A, down=2, period=4, clock="1:30")]}
        scoring = [sp("f", H, "field-goal", 0, 3, typ="Field Goal Good")]
        out, _, _ = parse_drives(summary([late_score, two_minute_fail], scoring), H, A, {"home": 3, "away": 0})
        self.assertEqual(out[0]["why"], "end of half/game")   # started with 0:40 left: dropped despite scoring
        self.assertEqual(out[1]["why"], "")                   # started with 1:50 left: kept despite failing

    def test_muffed_punt_fumble_is_not_an_offensive_play(self):
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": [
            play("a", H), play("m", H, typ="Fumble Recovery (Own)", down=4, text="punt muffed, recovered")]}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(len(out[0]["plays"]), 1)


class NewRules(unittest.TestCase):
    def test_kneel_matches_whole_words_only(self):
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": [
            play("a", H, text="R.McKneely run for 4 yards"),
            play("b", H, down=2, text="QB kneels at the 30"),
            play("c", H, down=3, text="Jade Kneeland rush for 2 yards")]}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(len(out[0]["plays"]), 2)

    def test_nullified_snap_is_not_a_play(self):
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": [
            play("a", H, yds=30, text="rush for 30 yards PENALTY ABC Holding 10 yards from ABC40 to ABC30. NO PLAY"),
            play("b", H, text="rush for 4 yards")]}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(len(out[0]["plays"]), 1)

    def test_clean_intervals_skip_clock_stoppers(self):
        plays = [play("a", H, clock="10:00", text="rush for 3 yards"),
                 play("b", H, down=2, clock="9:20", text="pass incomplete"),      # 40 s clean
                 play("c", H, down=3, clock="9:15", text="rush for 2 yards"),     # after incompletion: skip
                 play("d", H, down=4, clock="8:40", text="rush for 1 yard out of bounds")]  # 35 s clean
        drives = [{"team": {"id": H}, "result": "DOWNS", "plays": plays}]
        out, _, clock = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(out[0]["iv"], [[1, 600, 40], [1, 555, 35]])
        self.assertEqual(clock, {"cand": 2, "zero": 0})

    def test_snap_time_stamp_beats_end_of_play_clock(self):
        # ESPN's clock field is near the end of the play; the "(MM:SS)" stamp is the snap.
        plays = [play("a", H, clock="7:07", text="(07:10) rush for 3 yards"),
                 play("b", H, down=2, clock="6:24", text="(06:33) rush for 4 yards"),
                 play("c", H, down=3, clock="5:43", text="(05:51) rush for 2 yards")]
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": plays}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual([x[2] for x in out[0]["iv"]], [37, 42])
        self.assertEqual(out[0]["clock"], "7:10")

    def test_two_minute_warning_breaks_an_interval(self):
        plays = [play("a", H, period=4, clock="2:10", text="(02:10) rush for 3 yards"),
                 play("b", H, down=2, period=4, clock="1:55", text="(01:55) rush for 4 yards")]
        drives = [{"team": {"id": H}, "result": "PUNT", "plays": plays}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        self.assertEqual(out[0]["iv"], [])

    def test_try_text_does_not_delete_the_touchdown(self):
        # "NO PLAY" and "kick" belong to the extra point, not the snap.
        t = td("t", H, text="(05:00) J.Doe rush for 67 yards TOUCHDOWN. #91 C.Arreola kick attempt "
                            "good. PENALTY ABC Holding 10 yards. NO PLAY")
        drives = [{"team": {"id": H}, "result": "TD", "plays": [t]}]
        out, _, _ = parse_drives(summary(drives, [sp("t", H, "touchdown", 0, 7)]), H, A, {"home": 7, "away": 0})
        self.assertEqual(len(out[0]["plays"]), 1)
        self.assertEqual(out[0]["why"], "")

    def test_strip_sack_returned_for_td_is_a_turnover_not_special_teams(self):
        p = play("f", H, typ="Fumble Recovery (Own)", down=3,
                 text="Q.Henicle sacked, fumble, recovered by AWY, return 40 yards TOUCHDOWN, kick attempt good")
        drives = [{"team": {"id": H}, "result": "FUMBLE TD", "plays": [play("a", H), p]}]
        out, _, _ = parse_drives(summary(drives, [sp("f", A, "touchdown", 7, 0, typ="Fumble Return Touchdown")]),
                                 H, A, {"home": 0, "away": 7})
        self.assertEqual(len(out[0]["plays"]), 2)
        self.assertEqual(out[0]["plays"][1][7], 1)   # turnover
        self.assertEqual(out[0]["pts"], 0)

    def test_lost_fumble_labeled_own_recovery_is_a_turnover(self):
        p = play("f", H, typ="Fumble Recovery (Own)", down=3, yds=34,
                 text="sacked for loss of 12, fumble, recovered by AWY, return 34 yards")
        p["end"] = {"team": {"id": A}}
        drives = [{"team": {"id": H}, "result": "FUMBLE", "plays": [play("a", H), p]}]
        out, _, _ = parse_drives(summary(drives, []), H, A, {"home": 0, "away": 0})
        row = out[0]["plays"][1]
        self.assertEqual((row[4], row[5], row[6], row[7]), (0, 0, 0, 1))   # no yards, no success, turnover

    def test_points_only_for_scores_the_offense_snapped(self):
        # A defensive return TD inside a mislabeled drive is not offensive points.
        pick = play("i", A, typ="Interception Return Touchdown", down=2, text="pass intercepted, returned for TD")
        drives = [{"team": {"id": H}, "result": "INT TD", "plays": [play("a", H), play("b", H, down=2), pick]}]
        out, _, _ = parse_drives(summary(drives, [sp("i", H, "touchdown", 0, 7)]), H, A, {"home": 7, "away": 0})
        self.assertEqual(out[0]["pts"], 0)

    def test_garbage_time_wins_over_end_of_half(self):
        # A late Q2 drive by a team leading past the garbage margin is garbage time, so its
        # points come out of garbage-adjusted scores (end-of-half would leave them in).
        import parse
        saved = dict(parse.CONFIG["garbage_margin"])
        parse.CONFIG["garbage_margin"]["2"] = 5
        try:
            drives = [{"team": {"id": H}, "result": "TD", "plays": [td("t", H, period=2, clock="5:00")]},
                      {"team": {"id": A}, "result": "PUNT", "plays": [play("a", A, period=2, clock="4:00")]},
                      {"team": {"id": H}, "result": "FG", "plays": [
                          play("b", H, period=2, clock="0:40"),
                          play("f", H, typ="Field Goal Good", down=4, period=2, clock="0:05")]}]
            scoring = [sp("t", H, "touchdown", 0, 7), sp("f", H, "field-goal", 0, 10, typ="Field Goal Good")]
            out, _, _ = parse_drives(summary(drives, scoring), H, A, {"home": 10, "away": 0})
        finally:
            parse.CONFIG["garbage_margin"].update(saved)
        self.assertEqual(out[2]["why"], "garbage time")
        self.assertEqual(out[2]["pts"], 3)


class BoxPenalties(unittest.TestCase):
    def test_sanity_check(self):
        from parse import box_penalties
        self.assertEqual(box_penalties("7-61"), [7, 61])
        self.assertIsNone(box_penalties("743-37"))   # the corrupt 2025 row
        self.assertIsNone(box_penalties(""))



class Postseason(unittest.TestCase):
    """The ratings cover the regular season; ESPN files FCS playoff rounds among its weeks."""

    @staticmethod
    def event(*notes, season_type=2):
        return {"season": {"type": season_type},
                "competitions": [{"notes": [{"headline": n} for n in notes]}]}

    def test_fcs_playoff_rounds_are_postseason(self):
        from parse import postseason_reason
        for n in ("FCS Championship - First Round", "FCS Championship - Second Round",
                  "FCS Championship - Quarterfinals", "FCS Championship - Semifinals",
                  "College Football Playoff Semifinal at the Cotton Bowl"):
            self.assertEqual(postseason_reason(self.event(n)), n)

    def test_conference_title_games_and_named_games_are_regular_season(self):
        from parse import postseason_reason
        for n in ("SEC Championship", "Dr Pepper Big 12 Championship", "SWAC Championship",
                  "Allstate Red River Rivalry", "Aflac Kickoff", "FCS Kickoff", "Turkey Day Classic",
                  "FCS Kickoff - Declared No Contest with 7:46 remaining in 4th Quarter"):
            self.assertEqual(postseason_reason(self.event(n)), "", n)
        self.assertEqual(postseason_reason(self.event()), "")

    def test_espn_postseason_type(self):
        from parse import postseason_reason
        self.assertTrue(postseason_reason(self.event("Rose Bowl Game", season_type=3)))

    def test_load_sets_postseason_games_aside(self):
        from ratings import load
        full, reg = load(2025, regular_season_only=False), load(2025)
        flagged = {g["id"] for g in full["games"] if g["postseason"]}
        self.assertEqual(len(flagged), 17)  # FCS playoff rounds through the quarterfinals
        self.assertFalse(flagged & {g["id"] for g in reg["games"]})
        self.assertEqual({x["game"] for x in reg["excluded_postseason"]}, flagged)
        self.assertEqual(len(reg["games"]) + len(flagged), len(full["games"]))


if __name__ == "__main__":
    unittest.main()
