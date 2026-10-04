"""Flat-stake backtest of the power ratings' picks against the betting lines.

    python3 -m ratings.flatbet [--since 2021-10-03] [--stake 10] [--max-fav -350] [--hold 0.044] [--by fav|dog|both]

Every out-of-sample pick of the ratings predictor (ratings/data/oos_preds.pkl, written by
`python3 -m ratings.train`) from --since (default: five years before the latest fight) on is a flat
--stake bet on the side the ratings give more than 50%.  Picks that side with a listed opening
favourite priced --max-fav or heavier are skipped (a -350 favourite the ratings also like is not a
bet).  Prices come from BestFightOdds:

  listed open        the opening line as BestFightOdds recorded it: one early book's first price, its
                     vig included, with no book name or posting time
  Caesars-like open  the opening no-vig price re-vigged to a Caesars-like two-way hold (power method,
                     which loads more of the margin on the underdog, as books do)
  Caesars-like close the same from the closing no-vig price (what the line looked like in fight week)
  worst close        the least generous closing price of any book: a conservative single-book stand-in

Caesars' own history is not published, so "Caesars-like" is the best stand-in; it usually lists after
the opener, so a fight-week bet lands nearer the closing rows.  Draws and no
contests are not in the data (the rows carry a winner).  The bucket tables group every fight with an
opening line by the opening favourite's price, then by the opening underdog's, and show how often the
ratings, the opening line and the closing line named the winner; the underdog table adds the fights
where the ratings took the dog and what those bets made.
"""
import argparse, collections, datetime as dt, os, pickle, random, sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

PREDS = os.path.join(HERE, "data", "oos_preds.pkl")
ROWS = os.path.join(HERE, "data", "rows.pkl")
SYNTH_HOLD = 0.044   # same Caesars-like margin the model/ backtests use


def dec_odds(american):
    return 1 + american / 100.0 if american > 0 else 1 + 100.0 / -american


def synth_price(p_fair, hold=SYNTH_HOLD):
    """Book price for a side with fair probability p_fair, re-vigged with the power method
    (q_i = p_i^(1/k), sum q_i = 1 + hold).  Same construction as model/train.py."""
    pa = min(max(p_fair, 1e-4), 1 - 1e-4)
    pb = 1 - pa
    lo, hi = 1.0, 3.0
    for _ in range(60):
        k = (lo + hi) / 2
        if pa ** (1 / k) + pb ** (1 / k) > 1 + hold:
            hi = k
        else:
            lo = k
    q = min(0.995, pa ** (1 / ((lo + hi) / 2)))
    d = 1 / q
    return round((d - 1) * 100) if d >= 2 else round(-100 / (d - 1))


PRICES = ("listed", "open", "close", "worst")


def load(since=None, stats=None):
    """Fights from `since` on, in UFCStats f1/f2 orientation, with the ratings' P(f1) and the lines.
    `stats`, if given, receives how many decided fights in the window had no BestFightOdds line."""
    d = pickle.load(open(PREDS, "rb"))
    mkt = {r["id"]: r.get("mkt") for r in pickle.load(open(ROWS, "rb"))}
    out, no_line = [], 0
    for m in d["rows"]:
        if m["id"] not in d["preds"] or m["y"] is None or (since and m["date"] < since):
            continue
        p = d["preds"][m["id"]]
        k = mkt.get(m["id"]) or {}
        if k.get("open1") is None or k.get("open2") is None:
            no_line += 1
            continue
        swap = m["swap"]
        out.append({
            "id": m["id"], "date": m["date"], "year": m["year"],
            "p1": 1 - p if swap else p,                 # ratings' chance for f1
            "y1": (1 - m["y"]) if swap else m["y"],     # 1 if f1 won
            "open": (k["open1"], k["open2"]),
            "worst": (k.get("worst1"), k.get("worst2")),   # least generous closing price across books
            "open_fair": k.get("open_fair"), "close_fair": k.get("close_fair"),
        })
    if stats is not None:
        stats["no_line"] = no_line
    return out


def side_price(r, side, which, hold):
    if which == "listed":
        return r["open"][side]
    if which == "worst":
        return (r.get("worst") or (None, None))[side]
    fair = r["open_fair"] if which == "open" else r["close_fair"]
    if fair is None:
        return None
    return synth_price(fair if side == 0 else 1 - fair, hold)


def picks(fights, stake, max_fav, hold):
    """One record per fight: the ratings' pick, whether it is a bet, and its profit at each price."""
    out = []
    for r in fights:
        o1, o2 = r["open"]
        pick = 0 if r["p1"] > 0.5 else 1
        open_fav = 0 if o1 < o2 else 1 if o2 < o1 else None
        fav_price = min(o1, o2)
        skipped = open_fav is not None and pick == open_fav and fav_price <= max_fav
        won = int((r["y1"] == 1) == (pick == 0))
        pnl = {}
        for which in PRICES:
            price = side_price(r, pick, which, hold)
            pnl[which] = None if price is None else (stake * (dec_odds(price) - 1) if won else -stake)
        cf = r["close_fair"]
        out.append(dict(r, pick=pick, open_fav=open_fav, fav_price=fav_price, bet=not skipped, won=won, pnl=pnl,
                        pick_is_fav=(open_fav is not None and pick == open_fav),
                        open_right=None if open_fav is None else int((r["y1"] == 1) == (open_fav == 0)),
                        close_right=None if cf is None or cf == 0.5 else int((r["y1"] == 1) == (cf > 0.5))))
    return out


def total(bets, which):
    return sum(b["pnl"][which] for b in bets if b["pnl"][which] is not None)


def bootstrap_ci(bets, which, n=2000, seed=7):
    """95% range of the total from resampling whole fight nights (same-card bets move together)."""
    by_day = collections.defaultdict(float)
    for b in bets:
        if b["pnl"][which] is not None:
            by_day[b["date"]] += b["pnl"][which]
    days = list(by_day.values())
    if not days:
        return (0.0, 0.0)
    rng = random.Random(seed)
    tots = sorted(sum(rng.choice(days) for _ in days) for _ in range(n))
    return tots[int(0.025 * n)], tots[int(0.975 * n) - 1]


TOP = 550   # last bucket: this price and beyond


def bucket_of(fav_price, pickem, top=TOP):
    """50-point buckets by the opening favourite's price; pick'em opens get their own row."""
    if pickem:
        return "pickem"
    if fav_price <= -top:
        return top
    return (-fav_price - 100) // 50 * 50 + 100   # -100..-149 -> 100, -150..-199 -> 150, ...


def dog_bucket_of(dog_price, pickem, top=TOP):
    """50-point buckets by the opening underdog's price.  A dog at minus money (-105 against a -115
    favourite) gets a "short" row, pick'em opens their own."""
    if pickem:
        return "pickem"
    if dog_price < 100:
        return "short"
    if dog_price >= top:
        return top
    return (dog_price - 100) // 50 * 50 + 100     # +100..+149 -> 100, +150..+199 -> 150, ...


def bucket_label(key, by="fav", top=TOP):
    if key == "pickem":
        return "Pick'em open"
    if key == "short":
        return "Under +100"
    sign = "-" if by == "fav" else "+"
    if key == top:
        return f"{sign}{top} and {'heavier' if by == 'fav' else 'longer'}"
    return f"{sign}{key} to {sign}{key + 49}"


def bucket_key(r, by):
    pickem = r["open_fav"] is None
    if by == "fav":
        return bucket_of(r["fav_price"], pickem)
    return dog_bucket_of(max(r["open"]), pickem)


def bucket_sort(key):
    return (key in ("short", "pickem"), key == "pickem", key if isinstance(key, int) else 0)


def pct(n, d):
    return f"{100.0 * n / d:.1f}%" if d else "-"


def money(x):
    if abs(x) < 0.5:
        return "$0"
    return f"{'-' if x < 0 else '+'}${abs(x):,.0f}"


def roi(t, stake, n):
    return f"{100 * t / (stake * n):+.1f}%" if stake and n else "-"


PRICE_LABELS = (("listed", "listed opening line"), ("open", "Caesars-like opening price"),
                ("close", "Caesars-like closing price"), ("worst", "least generous closing price of any book"))


def report(recs, stake, max_fav, since, hold, by="both", stats=None):
    bets = [r for r in recs if r["bet"]]
    skipped = [r for r in recs if not r["bet"]]
    print(f"Fights with an opening line since {since}: {len(recs)}"
          + (f" ({stats['no_line']} decided fights had no BestFightOdds line and are left out)" if stats and stats.get("no_line") else ""))
    print("Draws and no contests are not in the data (a moneyline pushes on a draw at Caesars).")
    print(f"Ratings picked the winner in {sum(r['won'] for r in recs)} ({pct(sum(r['won'] for r in recs), len(recs))})")
    print(f"Skipped (ratings side with a listed opening favourite of {max_fav} or heavier): {len(skipped)}, "
          f"{sum(r['won'] for r in skipped)} of which won")
    print(f"\nFlat ${stake:g} on each of the {len(bets)} remaining picks ({sum(r['won'] for r in bets)} won, "
          f"{pct(sum(r['won'] for r in bets), len(bets))}), ${stake * len(bets):,.0f} staked:")
    for which, label in PRICE_LABELS:
        n = sum(1 for b in bets if b["pnl"][which] is not None)
        t = total(bets, which)
        lo, hi = bootstrap_ci(bets, which)
        print(f"  {label:44s} {money(t):>9s}  ROI {roi(t, stake, n):>7s}  95% range {money(lo)} to {money(hi)}  ({n} bets)")
    sk = total(skipped, "open")
    print(f"  (the {len(skipped)} skipped heavy favourites would have made {money(sk)} at the Caesars-like open)")
    print(f"  The opener is one early book's first price; Caesars usually lists later, so a fight-week bet lands nearer the\n"
          f"  closing rows.  Caesars-like = the no-vig price re-vigged to a {hold:.1%} two-way hold; Caesars' own history isn't published.")

    fav = [b for b in bets if b["pick_is_fav"]]
    dog = [b for b in bets if b["open_fav"] is not None and not b["pick_is_fav"]]
    pk = [b for b in bets if b["open_fav"] is None]
    print(f"\nBy side picked:{'':29s} bets   won            P&L at open  at close")
    for label, grp in (("with the opening favourite", fav), ("against the opening favourite", dog), ("pick'em opens", pk)):
        if grp:
            print(f"  {label:42s} {len(grp):4d}  {sum(g['won'] for g in grp):4d} ({pct(sum(g['won'] for g in grp), len(grp)):>6s})  "
                  f"{money(total(grp, 'open')):>9s} {money(total(grp, 'close')):>9s}")

    print(f"\nBy year:{'':36s} bets   won            P&L at open  at close")
    for y in sorted({b["year"] for b in bets}):
        grp = [b for b in bets if b["year"] == y]
        print(f"  {y:<42d} {len(grp):4d}  {sum(g['won'] for g in grp):4d} ({pct(sum(g['won'] for g in grp), len(grp)):>6s})  "
              f"{money(total(grp, 'open')):>9s} {money(total(grp, 'close')):>9s}")

    if by in ("fav", "both"):
        bucket_table(recs, "fav")
    if by in ("dog", "both"):
        bucket_table(recs, "dog")
    return bets


def bucket_table(recs, by):
    """Accuracy of the ratings, the opening line and the closing line per 50-point bucket of the opening
    favourite's (by="fav") or underdog's (by="dog") price, with the bets and P&L at the Caesars-like open.
    The underdog table also shows the fights where the ratings took the dog and what those bets made."""
    who = "favourite" if by == "fav" else "underdog"
    print(f"\nBy the opening {who}'s price (all fights with a line; 'Bets' are every bet in the bucket, P&L at the Caesars-like open):")
    head = f"  {'Opening ' + who:20s} {'Fights':>6s} {'Ratings right':>16s} {'Open right':>16s} {'Close right':>16s} {'Bets':>5s} {'P&L':>8s}"
    if by == "dog":
        head += f" {'Dogs won':>13s} {'Dog picks':>9s} {'Dog won':>13s} {'Dog P&L open':>12s} {'at close':>9s}"
    print(head)
    groups = collections.defaultdict(list)
    for r in recs:
        groups[bucket_key(r, by)].append(r)
    for key in sorted(groups, key=bucket_sort):
        grp = groups[key]
        n = len(grp)
        rr = sum(g["won"] for g in grp)
        op = [g["open_right"] for g in grp if g["open_right"] is not None]
        cl = [g["close_right"] for g in grp if g["close_right"] is not None]
        bs = [g for g in grp if g["bet"]]
        line = (f"  {bucket_label(key, by):20s} {n:6d} {rr:5d} ({pct(rr, n):>6s}) "
                f"{(str(sum(op)) + ' (' + pct(sum(op), len(op)) + ')') if op else 'no pick':>16s} "
                f"{(str(sum(cl)) + ' (' + pct(sum(cl), len(cl)) + ')') if cl else '-':>16s} "
                f"{len(bs):5d} {money(total(bs, 'open')):>8s}")
        if by == "dog":
            dogs_won = len(op) - sum(op)                      # the underdog won (fights with a favourite)
            dogs = [g for g in grp if g["open_fav"] is not None and not g["pick_is_fav"]]
            dw = sum(g["won"] for g in dogs)
            line += (f" {(str(dogs_won) + ' (' + pct(dogs_won, len(op)) + ')') if op else '-':>13s}"
                     f" {len(dogs):9d} {(str(dw) + ' (' + pct(dw, len(dogs)) + ')') if dogs else '-':>13s}"
                     f" {money(total(dogs, 'open')):>12s} {money(total(dogs, 'close')):>9s}")
        print(line)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", default=None, help="first fight date (default: five years before the latest fight)")
    ap.add_argument("--stake", type=float, default=10.0)
    ap.add_argument("--max-fav", type=int, default=-350, help="skip picks that side with an opening favourite this heavy or heavier")
    ap.add_argument("--hold", type=float, default=SYNTH_HOLD, help="two-way hold for the Caesars-like prices")
    ap.add_argument("--by", choices=("fav", "dog", "both"), default="both", help="bucket fights by the opening favourite's or underdog's price")
    a = ap.parse_args(argv)
    since = a.since or five_years_before(max(m["date"] for m in pickle.load(open(PREDS, "rb"))["rows"]))
    stats = {}
    recs = picks(load(since, stats), a.stake, a.max_fav, a.hold)
    report(recs, a.stake, a.max_fav, since, a.hold, a.by, stats)


def five_years_before(day):
    """Calendar arithmetic: '2026-10-03' -> '2021-10-03' (Feb 29 falls back to Feb 28)."""
    y, mo, d = (int(x) for x in day.split("-"))
    try:
        return dt.date(y - 5, mo, d).isoformat()
    except ValueError:
        return dt.date(y - 5, mo, 28).isoformat()


if __name__ == "__main__":
    main()
