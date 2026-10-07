"""Pinning polls to game weeks. Run: python -m unittest discover -s tests"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from polls import latest, middle_kickoffs, pin, when  # noqa: E402


def games(spec):
    """spec: {week: [kickoff iso, ...]}"""
    return [{"week": w, "date": d} for w, ds in spec.items() for d in ds]


# A season shaped like 2022: Saturday slates, one game moved to the following Sunday afternoon.
SEASON = middle_kickoffs(games({
    1: ["2022-08-27T16:00Z", "2022-09-03T19:00Z", "2022-09-03T23:30Z", "2022-09-05T00:00Z"],
    2: ["2022-09-10T16:00Z", "2022-09-10T19:00Z", "2022-09-10T23:00Z"],
    3: ["2022-09-17T16:00Z", "2022-09-17T19:00Z", "2022-09-18T16:00Z"],  # a Sunday game
}))


class Pin(unittest.TestCase):
    def test_preseason_is_week_0(self):
        self.assertEqual(pin(1, 1, "2022-08-15T07:00Z", SEASON), 0)
        self.assertEqual(pin(2, 1, "2022-08-15T07:00Z", SEASON), 0)  # 2022-2024 file it as type 2, week 1

    def test_week_n_poll_follows_week_n_minus_1(self):
        self.assertEqual(pin(2, 2, "2022-09-06T07:00Z", SEASON), 1)  # after the Labor Day Monday game
        self.assertEqual(pin(2, 4, "2022-09-18T07:00Z", SEASON), 3)  # before week 3's Sunday game: still week 3

    def test_label_and_date_must_agree(self):
        with self.assertRaises(SystemExit):
            pin(2, 4, "2022-09-12T07:00Z", SEASON)  # labelled after week 3, released before it

    def test_week_not_in_data_yet(self):
        self.assertIsNone(pin(2, 5, "2022-09-25T07:00Z", SEASON))

    def test_middle_not_last_kickoff(self):
        self.assertEqual(SEASON[3], when("2022-09-17T19:00Z"))


class Latest(unittest.TestCase):
    POLLS = {"polls": [{"poll": "AP", "after_week": w} for w in (0, 1, 2, 4)] +
                      [{"poll": "CFP", "after_week": 3}]}

    def test_newest_through_week(self):
        self.assertEqual(latest(self.POLLS, "AP", 3)["after_week"], 2)
        self.assertEqual(latest(self.POLLS, "AP", 4)["after_week"], 4)
        self.assertEqual(latest(self.POLLS, "CFP", 5)["after_week"], 3)

    def test_none_yet(self):
        self.assertIsNone(latest(self.POLLS, "CFP", 2))
        self.assertIsNone(latest(None, "AP", 9))


if __name__ == "__main__":
    unittest.main()
