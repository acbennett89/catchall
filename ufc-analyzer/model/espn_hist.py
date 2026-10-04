"""Dated pro histories from ESPN, so a fighter's record outside the UFC is known as of any date.

UFCStats only has UFC fights, and "total record minus UFC results" counts fights a fighter had after
being cut, which wasn't known at the time.  ESPN lists every pro fight with its date, and the app
reads the same ESPN histories at serve time, so training and serving agree.

    python -m model.espn_hist         # writes model/data/espn_hist.json.gz (resumable)

Steps: every UFC event on ESPN's calendar (2001 on) -> each bout's ESPN athlete ids -> matched to
UFCStats bouts by date and names -> each matched athlete's full history.
"""
import datetime, gzip, json, os, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import espn  # noqa: E402
from names import pair_score  # noqa: E402
from model.engine import method_class  # noqa: E402

OUT = os.path.join(HERE, "data", "espn_hist.json.gz")
CARDS = os.path.join(HERE, "data", "espn_cards.json.gz")


def _load(p, default):
    if os.path.exists(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return default


def _save(p, obj):
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, p)


def compact_history(a):
    """espn.parse_athlete() output -> [[iso date, result, is_ufc, method class], ...] newest first."""
    out = []
    for h in a.get("history") or []:
        if not h.get("date") or not h.get("result"):
            continue
        d = datetime.datetime.fromtimestamp(h["date"], datetime.timezone.utc).date().isoformat()
        out.append([d, h["result"], 1 if h.get("ufc") else 0, method_class(h.get("method"))])
    return out


def collect_cards(first=2001, last=None, workers=6, log=print):
    """{espn event id: {"date": iso, "bouts": [[id_a, name_a, id_b, name_b], ...]}} for every UFC event."""
    cards = _load(CARDS, {})
    last = last or datetime.date.today().year
    todo = []
    for y in range(first, last + 1):
        try:
            evs = espn.events(y)
        except Exception as e:
            log(f"  season {y}: {e}")
            continue
        for e in evs:
            if e["id"] not in cards and e.get("start") and e["start"] < time.time() and "contender" not in (e["name"] or "").lower():
                todo.append(e)
    log(f"{len(todo)} ESPN cards to fetch ({len(cards)} stored)")
    lock = threading.Lock()

    def one(e):
        try:
            c = espn.card(e["id"])
        except Exception:
            return
        bouts = [[f["fighters"][0]["id"], f["fighters"][0]["name"], f["fighters"][1]["id"], f["fighters"][1]["name"]]
                 for f in c["fights"]]
        day = datetime.datetime.fromtimestamp(c["date"] or e["start"], datetime.timezone.utc).date().isoformat()
        with lock:
            cards[e["id"]] = {"date": day, "bouts": bouts}
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(one, todo), 1):
            if i % 50 == 0:
                log(f"  cards {i}/{len(todo)}")
                with lock:
                    snap = dict(cards)
                _save(CARDS, snap)
    _save(CARDS, cards)
    return cards


def match_ids(cards, fights):
    """UFCStats fighter id -> ESPN athlete id, by majority over bouts matched on date (+-1 day) and names."""
    by_day = {}
    for c in cards.values():
        by_day.setdefault(c["date"], []).extend(c["bouts"])
    votes = {}
    for r in fights.values():
        if not r.get("date"):
            continue
        day = datetime.date.fromisoformat(r["date"])
        for off in (0, -1, 1):
            hit = None
            for ia, na, ib, nb in by_day.get((day + datetime.timedelta(days=off)).isoformat(), []):
                if pair_score(r["n1"], r["n2"], na, nb) >= 0.84:
                    hit = ((r["f1"], ia), (r["f2"], ib))
                elif pair_score(r["n1"], r["n2"], nb, na) >= 0.84:
                    hit = ((r["f1"], ib), (r["f2"], ia))
                if hit:
                    break
            if hit:
                for uid, eid in hit:
                    votes.setdefault(uid, {}).setdefault(eid, 0)
                    votes[uid][eid] += 1
                break
    return {uid: max(v, key=v.get) for uid, v in votes.items()}


def fetch_histories(mapping, workers=6, log=print):
    store = _load(OUT, {})
    todo = [(u, e) for u, e in mapping.items() if u not in store or store[u].get("espn") != e]
    log(f"{len(todo)} ESPN histories to fetch ({len(store)} stored)")
    lock = threading.Lock()

    def one(item):
        uid, eid = item
        try:
            a = espn.athlete(eid)
        except Exception:
            return
        with lock:
            store[uid] = {"espn": eid, "hist": compact_history(a)}
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(one, todo), 1):
            if i % 200 == 0:
                log(f"  histories {i}/{len(todo)}")
                with lock:
                    snap = dict(store)
                _save(OUT, snap)
    _save(OUT, store)
    return store


def load():
    return _load(OUT, {})


def outside_before(hist, day_iso):
    """(wins, losses, finish wins) outside the UFC strictly before day_iso, from a compact history."""
    w = l = fw = 0
    for d, res, ufc, kind in hist or []:
        if d >= day_iso or ufc:
            continue
        if res == "W":
            w += 1
            if kind in ("ko", "sub"):
                fw += 1
        elif res == "L":
            l += 1
    return w, l, fw


if __name__ == "__main__":
    from model.scrape import load_dataset
    t = time.time()
    cards = collect_cards()
    if "--cards-only" in sys.argv:
        sys.exit(0)
    _, fights, _ = load_dataset()
    mapping = match_ids(cards, fights)
    print(f"matched {len(mapping)} UFCStats fighters to ESPN athletes")
    store = fetch_histories(mapping)
    print(len(store), f"{time.time() - t:.0f}s")
