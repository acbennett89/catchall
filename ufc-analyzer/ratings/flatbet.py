"""Flat-stake backtest of the power ratings' picks against the betting lines.

    python3 -m ratings.flatbet [--since 2021-10-04] [--stake 10] [--max-fav -350] [--hold 0.044]

Every out-of-sample pick of the ratings predictor (ratings/data/oos_preds.pkl, written by
`python3 -m ratings.train`) from --since on is a flat --stake bet on the side the ratings give more
than 50%.  Picks that side with an opening favourite priced --max-fav or heavier are skipped (a -350
favourite the ratings also like is not a bet).  Prices come from BestFightOdds:

  listed open       the opening line as BestFightOdds recorded it (one book's price, its vig included)
  Caesars-like open the opening no-vig price re-vigged to a Caesars-like two-way hold (power method,
                    which loads more of the margin on the underdog, as books do)
  Caesars-like close the same from the closing no-vig price (what the line looked like in fight week)

Caesars' own history is not published, so "Caesars-like" is the best stand-in.  Draws and no
contests are not in the data (the rows carry a winner).  The bucket table groups every fight with an
opening line by the opening favourite's price and shows how often the ratings, the opening line and
the closing line named the winner.
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


def load(since=None):
    """Fights from `since` on, in UFCStats f1/f2 orientation, with the ratings' P(f1) and the lines."""
    d = pickle.load(open(PREDS, "rb"))
    mkt = {r["id"]: r.get("mkt") for r in pickle.load(open(ROWS, "rb"))}
    out = []
    for m in d["rows"]:
        if m["id"] not in d["preds"] or m["y"] is None or (since and m["date"] < since):
            continue
        p = d["preds"][m["id"]]
        k = mkt.get(m["id"]) or {}
        if k.get("open1") is None or k.get("open2") is None:
            continue
        swap = m["swap"]
        out.append({
            "id": m["id"], "date": m["date"], "year": m["year"],
            "p1": 1 - p if swap else p,                 # ratings' chance for f1
            "y1": (1 - m["y"]) if swap else m["y"],     # 1 if f1 won
            "open": (k["open1"], k["open2"]),
            "open_fair": k.get("open_fair"), "close_fair": k.get("close_fair"),
        })
    return out


def side_price(r, side, which, hold):
    if which == "listed":
        return r["open"][side]
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
        for which in ("listed", "open", "close"):
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


def bucket_of(fav_price, pickem, top=550):
    """50-point buckets by the opening favourite's price; pick'em opens get their own row."""
    if pickem:
        return "pickem"
    if fav_price <= -top:
        return top
    return (-fav_price - 100) // 50 * 50 + 100   # -100..-149 -> 100, -150..-199 -> 150, ...


def bucket_label(key, top=550):
    if key == "pickem":
        return "Pick'em open"
    if key == top:
        return f"-{top} and heavier"
    return f"-{key} to -{key + 49}"


def pct(n, d):
    return f"{100.0 * n / d:.1f}%" if d else "-"


def money(x):
    return f"{'-' if x < 0 else '+'}${abs(x):,.0f}"


def report(recs, stake, max_fav, since, hold):
    bets = [r for r in recs if r["bet"]]
    skipped = [r for r in recs if not r["bet"]]
    print(f"Fights with an opening line since {since}: {len(recs)}")
    print(f"Ratings picked the winner in {sum(r['won'] for r in recs)} ({pct(sum(r['won'] for r in recs), len(recs))})")
    print(f"Skipped (ratings side with an opening favourite of {max_fav} or heavier): {len(skipped)}, "
          f"{sum(r['won'] for r in skipped)} of which won")
    print(f"\nFlat ${stake:g} on each of the {len(bets)} remaining picks ({sum(r['won'] for r in bets)} won, "
          f"{pct(sum(r['won'] for r in bets), len(bets))}), ${stake * len(bets):,.0f} staked:")
    for which, label in (("listed", "listed opening line"), ("open", f"Caesars-like opening price ({hold:.1%} hold)"),
                         ("close", f"Caesars-like closing price ({hold:.1%} hold)")):
        n = sum(1 for b in bets if b["pnl"][which] is not None)
        t = total(bets, which)
        lo, hi = bootstrap_ci(bets, which)
        print(f"  {label:44s} {money(t):>9s}  ROI {100 * t / (stake * n):+.1f}%  95% range {money(lo)} to {money(hi)}  ({n} bets)")
    sk = total(skipped, "open")
    print(f"  (the {len(skipped)} skipped heavy favourites would have made {money(sk)} at the Caesars-like open)")

    fav = [b for b in bets if b["pick_is_fav"]]
    dog = [b for b in bets if b["open_fav"] is not None and not b["pick_is_fav"]]
    pk = [b for b in bets if b["open_fav"] is None]
    print("\nBy side picked (Caesars-like open):")
    for label, grp in (("with the opening favourite", fav), ("against the opening favourite", dog), ("pick'em opens", pk)):
        if grp:
            print(f"  {label:30s} {len(grp):4d} bets  {sum(g['won'] for g in grp):4d} won ({pct(sum(g['won'] for g in grp), len(grp))})  {money(total(grp, 'open')):>8s}")

    print("\nBy year (Caesars-like open):")
    for y in sorted({b["year"] for b in bets}):
        grp = [b for b in bets if b["year"] == y]
        print(f"  {y}  {len(grp):4d} bets  {sum(g['won'] for g in grp):4d} won ({pct(sum(g['won'] for g in grp), len(grp))})  {money(total(grp, 'open')):>8s}")

    print("\nBy the opening favourite's price (all fights with a line; bets and P&L at the Caesars-like open):")
    print(f"  {'Opening favourite':20s} {'Fights':>6s} {'Ratings right':>16s} {'Open right':>16s} {'Close right':>16s} {'Bets':>5s} {'P&L':>8s}")
    groups = collections.defaultdict(list)
    for r in recs:
        groups[bucket_of(r["fav_price"], r["open_fav"] is None)].append(r)
    order = sorted(groups, key=lambda k: (k == "pickem", k if k != "pickem" else 0))
    for key in order:
        grp = groups[key]
        n = len(grp)
        rr = sum(g["won"] for g in grp)
        op = [g["open_right"] for g in grp if g["open_right"] is not None]
        cl = [g["close_right"] for g in grp if g["close_right"] is not None]
        bs = [g for g in grp if g["bet"]]
        print(f"  {bucket_label(key):20s} {n:6d} {rr:5d} ({pct(rr, n):>6s}) "
              f"{(str(sum(op)) + ' (' + pct(sum(op), len(op)) + ')') if op else 'no pick':>16s} "
              f"{(str(sum(cl)) + ' (' + pct(sum(cl), len(cl)) + ')') if cl else '-':>16s} "
              f"{len(bs):5d} {money(total(bs, 'open')):>8s}")
    return bets


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--since", default=None, help="first fight date (default: five years before the latest fight)")
    ap.add_argument("--stake", type=float, default=10.0)
    ap.add_argument("--max-fav", type=int, default=-350, help="skip picks that side with an opening favourite this heavy or heavier")
    ap.add_argument("--hold", type=float, default=SYNTH_HOLD, help="two-way hold for the Caesars-like prices")
    a = ap.parse_args(argv)
    since = a.since
    if since is None:
        last = max(m["date"] for m in pickle.load(open(PREDS, "rb"))["rows"])
        y, mo, d = (int(x) for x in last.split("-"))
        since = (dt.date(y, mo, d) - dt.timedelta(days=365 * 5 + 1)).isoformat()
    recs = picks(load(since), a.stake, a.max_fav, a.hold)
    report(recs, a.stake, a.max_fav, since, a.hold)


if __name__ == "__main__":
    main()
