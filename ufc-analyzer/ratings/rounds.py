"""Round-by-round stats for every UFC fight, from the UFCStats fight pages.

    python -m ratings.rounds            # build or top up ratings/data/rounds.json.gz (resumable)

Each fight: [{"r": 1, "s": [{kd, sig, sig_a, tot, tot_a, td, td_a, sub, rev, ctrl, head, head_a, body,
body_a, leg, leg_a, dist, dist_a, clinch, clinch_a, ground, ground_a}, {...same for f2}]}, ...], in the
fight's f1/f2 order.  Totals per fight are in model/data (scrape.py); this adds how each round went,
for cardio, fade, pace by round and round-of-finish work.  At runtime update() tops up cache/ with any
fights the shipped file lacks.
"""
import gzip, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import ufcstats  # noqa: E402
from model import scrape  # noqa: E402

DATA = os.path.join(HERE, "data")
CACHE = os.path.join(ROOT, "cache")
NAME = "rounds"

_SECTION = re.compile(r'<thead class="b-fight-details__table-row b-fight-details__table-row_type_head">\s*<th[^>]*>\s*Round (\d)\s*</th>\s*</thead>')


def _sections(table):
    parts = _SECTION.split(table)
    return [(int(parts[i]), parts[i + 1]) for i in range(1, len(parts), 2)]


def parse_rounds(body):
    """Fight page -> per-round stats for both fighters (page order = event row order, checked by name
    by the caller the same way scrape.parse_fight is)."""
    tables = re.findall(r"<table[^>]*>(.*?)</table>", body, re.S)
    out = {}
    tot_t = next((t for t in tables if "Ctrl" in t and "Round 1" in t), None)
    sig_t = next((t for t in tables if "Distance" in t and "Head" in t and "Round 1" in t), None)
    if tot_t:
        for rnd, chunk in _sections(tot_t):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.S)[:10]
            if len(tds) < 10:
                continue
            cols = [scrape._pairs(td) + ["", ""] for td in tds]
            out.setdefault(rnd, [{}, {}])
            for i in (0, 1):
                s = out[rnd][i]
                s["kd"] = scrape._int(cols[1][i])
                s["sig"], s["sig_a"] = scrape._of(cols[2][i])
                s["tot"], s["tot_a"] = scrape._of(cols[4][i])
                s["td"], s["td_a"] = scrape._of(cols[5][i])
                s["sub"] = scrape._int(cols[7][i])
                s["rev"] = scrape._int(cols[8][i])
                s["ctrl"] = scrape._secs(cols[9][i])
    if sig_t:
        for rnd, chunk in _sections(sig_t):
            tds = re.findall(r"<td[^>]*>(.*?)</td>", chunk, re.S)[:9]
            if len(tds) < 9:
                continue
            cols = [scrape._pairs(td) + ["", ""] for td in tds]
            out.setdefault(rnd, [{}, {}])
            for i in (0, 1):
                for k, col in zip(("head", "body", "leg", "dist", "clinch", "ground"), cols[3:9]):
                    out[rnd][i][k], out[rnd][i][k + "_a"] = scrape._of(col[i])
    return [{"r": r, "s": out[r]} for r in sorted(out)]


def _names(body):
    t = re.findall(r"<table[^>]*>(.*?)</table>", body, re.S)
    if not t:
        return []
    tds = re.findall(r"<td[^>]*>(.*?)</td>", t[0].split("<tbody", 1)[-1], re.S)
    return scrape._pairs(tds[0])[:2] if tds else []


def load():
    """{fight id: rounds} merged from the shipped file and the runtime top-up."""
    out = {}
    for base in (DATA, CACHE):
        p = os.path.join(base, NAME + ".json.gz")
        if os.path.exists(p):
            with gzip.open(p, "rt", encoding="utf-8") as f:
                out.update(json.load(f))
    return out


def _save(obj, base):
    os.makedirs(base, exist_ok=True)
    p = os.path.join(base, NAME + ".json.gz")
    tmp = p + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(tmp, p)


def build(base=DATA, workers=4, log=print, limit=None):
    """Fetch rounds for every stored fight that has none yet."""
    _, fights, _ = scrape.load_dataset()
    known = load()
    mine = {}
    p = os.path.join(base, NAME + ".json.gz")
    if os.path.exists(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            mine = json.load(f)
    todo = sorted((r for r in fights.values() if r["id"] not in known and r.get("s1")), key=lambda r: r["date"], reverse=True)
    if limit:
        todo = todo[:limit]
    log(f"{len(todo)} fights to fetch rounds for ({len(known)} stored)")
    lock = threading.Lock()
    done = [0]

    def one(r):
        try:
            body = ufcstats.get(f"/fight-details/{r['id']}")
            rounds = parse_rounds(body)
            names = _names(body)
            if names and names[0] and names[0] != r["n1"] and names[0] == r["n2"]:
                for x in rounds:
                    x["s"] = x["s"][::-1]
            rec = rounds if rounds else {"empty": True}
        except Exception as ex:
            rec = {"error": str(ex)[:120]}
        with lock:
            mine[r["id"]] = rec
            done[0] += 1
            if done[0] % 200 == 0:
                log(f"  {done[0]}/{len(todo)}")
                _save(mine, base)
    with ThreadPoolExecutor(workers) as ex:
        list(ex.map(one, todo))
    _save(mine, base)
    return len(todo)


def update(log=lambda *_: None):
    """Runtime top-up into cache/ for fights added since the shipped file."""
    return build(base=CACHE, workers=2, log=log, limit=200)


if __name__ == "__main__":
    ufcstats._sem = threading.Semaphore(8)
    t = time.time()
    print(build(workers=8), f"fights in {time.time() - t:.0f}s")
