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
        self.assertEqual(out[0]["iv"], [40, 35])
        self.assertEqual(clock, {"cand": 2, "zero": 0})

    def test_leaders_final_drive_is_excluded(self):
        drives = [{"team": {"id": H}, "result": "TD", "plays": [td("t", H, period=4, clock="9:00")]},
                  {"team": {"id": A}, "result": "PUNT", "plays": [play("a", A, period=4, clock="8:00")]},
                  {"team": {"id": H}, "result": "", "plays": [
                      play("b", H, period=4, clock="4:00"), play("c", H, down=2, period=4, clock="3:20")]}]
        scoring = [sp("t", H, "touchdown", 0, 7)]
        out, _, _ = parse_drives(summary(drives, scoring), H, A, {"home": 7, "away": 0})
        self.assertEqual(out[2]["why"], "leader's final drive")
        self.assertEqual(out[1]["why"], "")


class BoxPenalties(unittest.TestCase):
    def test_sanity_check(self):
        from parse import box_penalties
        self.assertEqual(box_penalties("7-61"), [7, 61])
        self.assertIsNone(box_penalties("743-37"))   # the corrupt 2025 row
        self.assertIsNone(box_penalties(""))


if __name__ == "__main__":
    unittest.main()
