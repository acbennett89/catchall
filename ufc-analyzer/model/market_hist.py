"""Join BestFightOdds history to UFCStats fights and derive market probabilities.

For each matched fight (date within 3 days, both names matching) we get, from fighter f1's side:
  open_fair   no-vig probability from both fighters' opening lines
  close_fair  no-vig probability from the midpoints of both closing ranges
  close_worst f1's least generous closing price across books (a conservative stand-in for a single
              book such as Caesars, whose own history isn't published), and the same for f2

A closing range wider than CLOSE_MAX_WIDTH in implied probability usually means one book's "closing"
price was taken during the fight (e.g. -3500 / +135 on the same side), which leaks the result; those
fights get no closing data at all.
"""
import datetime

from names import pair_score
from model.learn import dec_odds

CLOSE_MAX_WIDTH = 0.12


def _imp(o):
    return 1.0 / dec_odds(o) if o is not None else None


def _mid_prob(lo, hi):
    ps = [_imp(o) for o in (lo, hi) if o is not None]
    return sum(ps) / len(ps) if ps else None


def _worst(lo, hi):
    """The lower-paying of two prices."""
    vals = [o for o in (lo, hi) if o is not None]
    if not vals:
        return None
    return min(vals, key=dec_odds)


def close_width(lo1, hi1, lo2, hi2):
    """Widest closing range of the two sides, in implied probability (0 when a range has one end)."""
    w = 0.0
    for lo, hi in ((lo1, hi1), (lo2, hi2)):
        if lo is not None and hi is not None:
            w = max(w, abs(_imp(lo) - _imp(hi)))
    return w


def join(fights, matchups):
    """{ufcstats fight id: market dict oriented to f1}."""
    by_day = {}
    for m in matchups.values():
        if not m.get("date") or not m.get("a") or not m.get("b"):
            continue
        d = datetime.datetime.fromtimestamp(m["date"], datetime.timezone.utc).date() if isinstance(m["date"], (int, float)) else None
        if d:
            by_day.setdefault(d, []).append(m)
    out = {}
    for fid, r in fights.items():
        if not r.get("date"):
            continue
        day = datetime.date.fromisoformat(r["date"])
        best = None
        for off in (0, -1, 1, -2, 2, -3, 3):
            for m in by_day.get(day + datetime.timedelta(days=off), []):
                s1 = pair_score(r["n1"], r["n2"], m["a"], m["b"])
                s2 = pair_score(r["n1"], r["n2"], m["b"], m["a"])
                s, swap = (s1, False) if s1 >= s2 else (s2, True)
                if s >= 0.84 and (best is None or s > best[0] or (s == best[0] and abs(off) < best[3])):
                    best = (s, m, swap, abs(off))
        if not best:
            continue
        _, m, swap = best[:3]
        f1 = ("b" if swap else "a")
        f2 = ("a" if swap else "b")
        o1, o2 = m.get(f1 + "Open"), m.get(f2 + "Open")
        lo1, hi1, lo2, hi2 = m.get(f1 + "Lo"), m.get(f1 + "Hi"), m.get(f2 + "Lo"), m.get(f2 + "Hi")
        rec = {"matchup": m.get("matchup"), "open1": o1, "open2": o2,
               "close1": [lo1, hi1], "close2": [lo2, hi2],
               "worst1": _worst(lo1, hi1), "worst2": _worst(lo2, hi2)}
        if o1 is not None and o2 is not None:
            a, b = _imp(o1), _imp(o2)
            rec["open_fair"] = a / (a + b)
        if close_width(lo1, hi1, lo2, hi2) > CLOSE_MAX_WIDTH:
            rec.update(close1=[None, None], close2=[None, None], worst1=None, worst2=None, close_inplay=True)
            out[fid] = rec
            continue
        a, b = _mid_prob(lo1, hi1), _mid_prob(lo2, hi2)
        if a and b:
            fair = a / (a + b)
            hold = a + b - 1
            if -0.03 <= hold <= 0.3:
                rec["close_fair"] = fair
                rec["close_hold"] = hold
        out[fid] = rec
    return out
