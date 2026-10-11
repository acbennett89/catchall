"""The model's point spread beside a sportsbook's, and how the model's side has done against it.

    python betting.py      every built season's record against the book, and the fit behind
                           the cover chance (prints only)

Reference only: nothing here enters a rating, and nothing here is betting advice.

Model line: the predicted home margin (ratings.predict) as a home point spread, -margin, rounded
to the half point: the line the model sets. Book line: Caesars Sportsbook when there is one
(odds.CAESARS; a Caesars entry 3+ points from the median of the game's other books is stale and
passed over), otherwise the book ESPN listed that season (odds.STAND_INS); every line names its
book. Spreads are the home team's: -7 = home favored by 7.

    edge = book home spread - model home spread   (points between the two lines shown)

Positive: the model likes the home team at the book's number; negative: the away team. The model
"likes" a game when |edge| >= betting.min_edge points (config.json), unless the book's line was
read after kickoff. Against the spread, home covers when actual margin + home spread > 0, and it
is a push at 0.

Cover chance (games not yet played): the chance the model's side covers, read from earlier
complete seasons' walk-forward picks (each week's games predicted from the week before) against
their book lines, with no home/away term (the model's side is either):

    actual margin - book margin = b * edge + e,   e ~ Normal(0, s)
    P(model's side covers) = Phi(b * |edge| / s)

b is the share of the model's disagreement that has shown up in results. A b near 0 means the
disagreements carried little information beyond the book's line, and every cover chance is near
50%. At standard -110 odds a side has to cover 52.4% of the time to break even.
"""
import json
import math
import os

from odds import CAESARS, ODDS_API_BOOK, PROJECTIONS, STAND_INS, load_lines

HERE = os.path.dirname(os.path.abspath(__file__))
BUCKETS = ((0, 3), (3, 7), (7, 10), (10, None))  # |edge| in points; fixed before any results were seen
BREAK_EVEN = 110 / 210  # a -110 bet: risk 110 to win 100


def phi(x):
    return 0.5 * (1 + math.erf(x / math.sqrt(2)))


def half_point(x):
    """Round to the nearest half point (halves away from zero), as books quote spreads."""
    return math.copysign(math.floor(abs(x) * 2 + 0.5) / 2, x) if x else 0.0


STALE = 3  # points from the other books' median at which a Caesars entry is passed over


def book_line(books):
    """The line the model is compared with: the first Caesars book with a spread that is within
    STALE points of the median of the game's other ESPN books (when two or more list one), else
    ESPN's book that season."""
    books = books or {}
    others = sorted(v["home_spread"] for b, v in books.items() if v.get("home_spread") is not None
                    and b not in CAESARS and b not in PROJECTIONS)
    median = (others[len(others) // 2] + others[(len(others) - 1) // 2]) / 2 if len(others) >= 2 else None
    for b in CAESARS + STAND_INS:
        v = books.get(b)
        if not v or v.get("home_spread") is None:
            continue
        if b in CAESARS and median is not None and b != ODDS_API_BOOK and abs(v["home_spread"] - median) >= STALE:
            continue
        return {"book": b, "caesars": b in CAESARS, "home_spread": v["home_spread"], "total": v.get("total"),
                "source": v.get("source"), "read_at": v.get("read_at"), "after_kickoff": bool(v.get("after_kickoff"))}
    return None


def cover_prob(edge, cal):
    return phi(cal["b"] * abs(edge) / cal["s"])


def bet(home_margin, line, min_edge, cal=None, actual=None):
    """The model's line against the book for one game. actual = final home margin, if played."""
    model = half_point(-home_margin) + 0.0
    out = {"model_home_spread": model}
    if not line:
        return out
    edge = line["home_spread"] - model
    side = "home" if edge > 0 else "away" if edge < 0 else None
    started = line.get("after_kickoff", False)
    out.update(book=line["book"], caesars=line["caesars"], book_home_spread=line["home_spread"],
               book_total=line["total"], line_source=line["source"], line_read_at=line["read_at"],
               edge=edge, side=side, likes=side is not None and abs(edge) >= min_edge and not started)
    if started:
        out["after_kickoff"] = True  # read once the game was under way: shown, not starred
    elif cal and side:
        out["cover_prob"] = cover_prob(edge, cal)
    if actual is not None and side:
        m = actual + line["home_spread"]  # the home team's margin against the spread
        r = m if side == "home" else -m
        out["ats"] = "W" if r > 0 else "L" if r < 0 else "P"
    return out


def label(lo, hi):
    return f"{lo}+" if hi is None else f"{lo}-{hi}"


def bucket_of(edge):
    e = abs(edge)
    return next(label(lo, hi) for lo, hi in BUCKETS if e >= lo and (hi is None or e < hi))


def record(bets, min_edge):
    """W-L-P of the model's side: overall, at |edge| >= min_edge, by |edge|, and split into games
    with a tentative team (fewer than min_games games: a season's first weeks) and the rest."""
    def tally(xs):
        w, l, p = (sum(1 for x in xs if x["ats"] == k) for k in "WLP")
        return {"W": w, "L": l, "P": p, "pct": w / (w + l) if w + l else None}
    done = [b for b in bets if b.get("ats")]
    return {"all": tally(done), "likes": tally([b for b in done if abs(b["edge"]) >= min_edge]),
            "by_edge": {label(lo, hi): tally([b for b in done if bucket_of(b["edge"]) == label(lo, hi)])
                        for lo, hi in BUCKETS},
            "by_status": {"tentative": tally([b for b in done if b.get("tentative")]),
                          "rated": tally([b for b in done if not b.get("tentative")])},
            "books": {k: sum(1 for b in done if b["book"] == k) for k in sorted({b["book"] for b in done})}}


def season_rows(season):
    """Walk-forward picks of a built season that have a book line: (edge, actual - book margin)."""
    p = os.path.join(HERE, "out", str(season), "weekly.json")
    if not os.path.exists(p):
        return []
    lines, rows = load_lines(season), []
    for s in json.load(open(p, encoding="utf-8"))["weeks"]:
        for g in s["picks"]:
            line = book_line(lines.get(g["game"]))
            if line:
                actual = g["home_pts"] - g["away_pts"]
                rows.append((line["home_spread"] - half_point(-g["home_margin"]), actual + line["home_spread"]))
    return rows


def calibrate(seasons):
    """Fit actual - book margin = b * edge (through the origin) over these seasons' walk-forward picks."""
    rows = [r for s in seasons for r in season_rows(s)]
    if len(rows) < 100:
        return None
    n = len(rows)
    sxx = sum(x * x for x, _ in rows)
    b = sum(x * y for x, y in rows) / sxx
    s = math.sqrt(sum((y - b * x) ** 2 for x, y in rows) / (n - 1))
    return {"seasons": list(seasons), "n": n, "b": b, "b_se": s / math.sqrt(sxx), "s": s,
            "rule": "actual margin - book margin = b * edge + Normal(0, s), least squares through the "
                    "origin over the seasons' walk-forward picks with a book line; P(model's side covers) "
                    "= Phi(b * |edge| / s)"}


def prior_complete_seasons(season):
    """Built seasons before `season` whose regular season is complete (their results are final)."""
    out = []
    for p in sorted(os.listdir(os.path.join(HERE, "out"))):
        if p.isdigit() and int(p) < season:
            f = os.path.join(HERE, "out", p, "ratings.json")
            if os.path.exists(f) and json.load(open(f, encoding="utf-8"))["meta"].get("regular_season_complete"):
                out.append(int(p))
    return out


def main():
    seasons = sorted(int(p) for p in os.listdir(os.path.join(HERE, "out")) if p.isdigit())
    total = {"W": 0, "L": 0, "P": 0}
    for season in seasons:
        b = json.load(open(os.path.join(HERE, "out", str(season), "ratings.json"), encoding="utf-8"))["meta"].get("betting")
        if not b:
            print(f"{season}: no betting record (rebuild with python build.py --season {season})")
            continue
        r = b["record"]
        fmt = lambda t: f"{t['W']}-{t['L']}-{t['P']}" + (f" ({100 * t['pct']:.1f}%)" if t["pct"] is not None else "")
        print(f"{season} vs {', '.join(f'{k} {v}' for k, v in r['books'].items()) or 'no lines'}")
        print(f"   all picks {fmt(r['all'])};  edge >= {b['min_edge']:g}: {fmt(r['likes'])};  by |edge|: " +
              ", ".join(f"{k} {fmt(v)}" for k, v in r["by_edge"].items()))
        for k in total:
            total[k] += r["all"][k]
    if total["W"] + total["L"]:
        print(f"all seasons: {total['W']}-{total['L']}-{total['P']} "
              f"({100 * total['W'] / (total['W'] + total['L']):.1f}%; break-even at -110 is {100 * BREAK_EVEN:.1f}%)")
    cal = calibrate([s for s in seasons if s in prior_complete_seasons(max(seasons) + 1)])
    if cal:
        print(f"fit over {cal['seasons']} ({cal['n']} games): b = {cal['b']:.3f} +/- {cal['b_se']:.3f}, "
              f"s = {cal['s']:.2f}")
        for e in (3, 7, 10, 14):
            print(f"   cover chance at an edge of {e} points: {100 * cover_prob(e, cal):.1f}%")


if __name__ == "__main__":
    main()
