"""Training rows for the ratings predictor: for every fight from SINCE on, both fighters' raw profiles
and opponent-adjusted ratings as they stood the day before the fight.

The adjusted ratings are recomputed per event date over the pool of active fighters (about a second
each), so no fight ever sees itself or anything later.  Rows are oriented by a hash of the fight id
(UFCStats lists the winner first) so side A wins about half the time.
"""
import datetime, hashlib, os, pickle, sys, time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

from model import espn_hist  # noqa: E402  (ESPN dated histories: the shared raw data, not the other model)
from ratings import engine, fightdata, profile, ratings  # noqa: E402

SINCE = "2009-01-01"


def swap_for(fid):
    return int(hashlib.md5(fid.encode()).hexdigest()[:8], 16) % 2 == 1


def outside_for(espn, fid, day_iso):
    h = espn.get(fid)
    if not h:
        return None
    w, l, fin = espn_hist.outside_before(h["hist"], day_iso)
    return (w, l, fin, True)


def build_rows(data=None, since=SINCE, log=print, market=None):
    data = data or fightdata.load()
    fights = data["fights"]
    ledger = engine.Ledger()
    rows = []
    by_date = {}
    for r in fights:
        by_date.setdefault(r["date"], []).append(r)
    dates = sorted(by_date)
    t0 = time.time()
    applied = 0
    for i, date in enumerate(dates):
        day = fightdata.parse_day(date)
        todays = by_date[date]
        if date >= since:
            # ratings and priors from everything before today (same-day cards share the same state)
            pool = ratings.pool_as_of(ledger, day)
            table = ratings.compute(ledger, day, pool=pool) if pool else {"_prior": {}}
            priors = profile.Priors(ledger, day)
            last_div = {f: bs[-1].div for f, bs in ledger.log.items()}
            rank = ratings.ranks(table, ledger, day, lambda f: last_div[f]) if pool else {}
            for r in todays:
                if r["result"] not in ("f1", "f2", "draw"):
                    continue
                sides = []
                for fid in (r["f1"], r["f2"]):
                    P = profile.raw_profile(ledger, fid, data["fighters"].get(fid), day, r["div"], priors=priors,
                                            outside=outside_for(data["espn"], fid, date))
                    R = dict(table.get(fid) or {})
                    P["adj"] = R
                    P["rank"] = rank.get(fid)
                    sides.append(P)
                swap = swap_for(r["id"])
                A, B = (sides[1], sides[0]) if swap else (sides[0], sides[1])
                a, b = (r["f2"], r["f1"]) if swap else (r["f1"], r["f2"])
                y = None if r["result"] == "draw" else (1 if (r["result"] == "f1") != swap else 0)
                rows.append({"id": r["id"], "date": date, "year": int(date[:4]), "a": a, "b": b, "swap": swap, "y": y,
                             "A": A, "B": B, "div": r["div"], "rounds": r.get("rounds") or 3, "title": bool(r.get("title")),
                             "kind": r["kind"], "round": r.get("round"), "secs": r["secs"], "result": r["result"],
                             "mkt": (market or {}).get(r["id"])})
        for r in todays:
            ledger._add(r)
            applied += 1
        ledger.as_of = date
        if i % 100 == 0 and date >= since:
            log(f"  {date}: {len(rows)} rows, {time.time() - t0:.0f}s")
    return rows, ledger


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else os.path.join(HERE, "data", "rows.pkl")
    data = fightdata.load()
    rows, _ = build_rows(data, market=fightdata.market())
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "wb") as f:
        pickle.dump(rows, f)
    print(f"wrote {len(rows)} rows to {out}")
