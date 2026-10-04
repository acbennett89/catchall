"""Odds math: implied probability, vig removal, market consensus, expected value and Kelly sizing.

The value read is "is Caesars' price better than the market's fair price?"  Fair price comes from
removing the vig from every other book's two-way line and taking the median, so one stale or
off-market book can't drag it.  EV is then fair_prob * caesars_decimal - 1 (profit per $1 staked).
"""
import statistics

TARGET_BOOK = "Caesars"
OUTLIER = 0.15  # max distance (in win probability) from the median before a book is ignored


def to_decimal(american):
    a = float(american)
    return 1 + a / 100 if a > 0 else 1 + 100 / -a


def to_american(decimal):
    if decimal is None or decimal <= 1:
        return None
    return round((decimal - 1) * 100) if decimal >= 2 else round(-100 / (decimal - 1))


def implied(american):
    return 1 / to_decimal(american)


def prob_to_american(p):
    if not p or p <= 0 or p >= 1:
        return None
    return to_american(1 / p)


def no_vig(a, b):
    """Two-way line -> (fair_a, fair_b, hold).  Multiplicative normalization."""
    ia, ib = implied(a), implied(b)
    tot = ia + ib
    return ia / tot, ib / tot, tot - 1


def ev(prob, american):
    """Expected profit per $1 at the given price if prob is the true win probability."""
    return prob * to_decimal(american) - 1


def kelly(prob, american):
    """Full-Kelly stake as a fraction of bankroll (0 when the bet is -EV)."""
    b = to_decimal(american) - 1
    f = (b * prob - (1 - prob)) / b
    return max(0.0, f)


def consensus(lines, exclude=(TARGET_BOOK,)):
    """lines: {book: (odds_a, odds_b)} with either side possibly None.

    Returns fair probability of side A as the median of each book's no-vig probability, using only
    books with both sides priced and not in `exclude`.  Falls back to including excluded books when
    nothing else is available.  Returns (prob_a, n_books, books_used) or (None, 0, []).
    """
    def collect(skip):
        out = []
        for book, (oa, ob) in lines.items():
            if book in skip or oa is None or ob is None:
                continue
            pa, _, hold = no_vig(oa, ob)
            if -0.02 <= hold <= 0.25:  # ignore broken or crossed markets
                out.append((book, pa))
        return out

    used = collect(set(exclude))
    if not used:
        used = collect(set())
    if not used:
        return None, 0, []
    med = statistics.median(p for _, p in used)
    # Drop books far off the pack (a settled prediction market, a stale line), then re-take the median.
    kept = [(b, p) for b, p in used if abs(p - med) <= OUTLIER] or used
    return statistics.median(p for _, p in kept), len(kept), [b for b, _ in kept]


def outliers(lines, fair_a):
    """Books whose two-way line is far from the fair price (e.g. a prediction market after the result)."""
    out = []
    for book, (oa, ob) in lines.items():
        if oa is None or ob is None or fair_a is None:
            continue
        pa, _, hold = no_vig(oa, ob)
        if abs(pa - fair_a) > OUTLIER or not -0.02 <= hold <= 0.25:
            out.append(book)
    return out


def market_price(lines, side, exclude=(TARGET_BOOK,)):
    """Median price other books offer on one side (vig included) -> American odds, for one-sided props."""
    probs = [implied(pair[side]) for book, pair in lines.items() if book not in exclude and pair[side] is not None]
    if not probs:
        return None, 0
    return prob_to_american(statistics.median(probs)), len(probs)


def best_price(lines, side):
    """Highest-paying American price for side 0/1 across books -> (book, odds)."""
    best = None
    for book, pair in lines.items():
        o = pair[side]
        if o is None:
            continue
        if best is None or to_decimal(o) > to_decimal(best[1]):
            best = (book, o)
    return best


def assess_prop(labels, lines, target=TARGET_BOOK):
    """Value read for each side of a prop that the target book prices.  One entry per priced side."""
    tl = lines.get(target)
    if not tl:
        return []
    fair_a, n, used = consensus(lines, exclude=(target,))
    if target in used:
        fair_a, n = None, 0  # only the target itself prices both sides; no independent fair line
    out = []
    for side in (0, 1):
        o = tl[side]
        if o is None:
            continue
        fair = None if fair_a is None else (fair_a if side == 0 else 1 - fair_a)
        mkt, mkt_n = market_price(lines, side, exclude=(target,))
        bp = best_price(lines, side)
        out.append({
            "label": labels[side] or ("Yes" if side == 0 else "No"),
            "other": labels[1 - side],
            "odds": o,
            "implied": round(implied(o), 4),
            "fairOdds": prob_to_american(fair) if fair else None,
            "ev": round(ev(fair, o), 4) if fair else None,
            "kelly": round(kelly(fair, o), 4) if fair else None,
            "fairBooks": n,
            "market": mkt,
            "marketBooks": mkt_n,
            # how much more Caesars pays than the typical other book, as a return ratio (one-sided signal)
            "vsMarket": round(to_decimal(o) / to_decimal(mkt) - 1, 4) if mkt else None,
            "best": {"book": bp[0], "odds": bp[1]} if bp else None,
        })
    return out


def assess(lines, target=TARGET_BOOK):
    """Full value read for a two-way market.  lines: {book: (odds_a, odds_b)}."""
    fair_a, n, used = consensus(lines, exclude=(target,))
    out = {"fair": None, "books": n, "booksUsed": used, "sides": [{}, {}], "fairFromTarget": target in used}
    if fair_a is None:
        return out
    fair = (fair_a, 1 - fair_a)
    out["fair"] = [round(fair[0], 4), round(fair[1], 4)]
    out["outliers"] = [b for b in outliers(lines, fair_a) if b != target]
    sane = {b: v for b, v in lines.items() if b not in out["outliers"]}
    tl = lines.get(target)
    if tl and tl[0] is not None and tl[1] is not None:
        out["targetHold"] = round(no_vig(tl[0], tl[1])[2], 4)
    for side in (0, 1):
        s = out["sides"][side]
        s["fairOdds"] = prob_to_american(fair[side])
        bp = best_price(sane, side)
        if bp:
            s["best"] = {"book": bp[0], "odds": bp[1], "ev": round(ev(fair[side], bp[1]), 4)}
        if tl and tl[side] is not None:
            s["target"] = {
                "odds": tl[side],
                "implied": round(implied(tl[side]), 4),
                "ev": round(ev(fair[side], tl[side]), 4),
                "kelly": round(kelly(fair[side], tl[side]), 4),
            }
    return out
