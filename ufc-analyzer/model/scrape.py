"""Historical UFC fight data from UFCStats, for training the prediction model and keeping it current.

Every completed UFC event, every fight on it (result, method, round, time, scheduled rounds, title,
both fighters' strike / takedown / control totals), and every fighter's physical attributes.

    python -m model.scrape            # build or top up model/data/*.json.gz (resumable)

At runtime the server calls update() in the background so fights from new events are picked up
without retraining; new rows go to cache/ufcstats_*.json so the shipped dataset is never rewritten.
"""
import datetime, gzip, json, os, re, sys, threading, time
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
sys.path.insert(0, ROOT)

import ufcstats  # noqa: E402  (PoW-solving session shared with the app)
from ufcstats import _text  # noqa: E402

DATA = os.path.join(HERE, "data")
CACHE = os.path.join(ROOT, "cache")


def _pairs(td):
    return [_text(p) for p in re.findall(r'<p class="b-fight-details__table-text">(.*?)</p>', td, re.S)]


def _date(s):
    try:
        return datetime.datetime.strptime(s.strip().replace(".", ""), "%B %d, %Y").strftime("%Y-%m-%d")
    except ValueError:
        try:
            return datetime.datetime.strptime(s.strip().replace(".", ""), "%b %d, %Y").strftime("%Y-%m-%d")
        except ValueError:
            return None


def parse_events(body):
    """Completed-events list -> [{id, name, date, location}] (newest first)."""
    out = []
    for row in re.findall(r'<tr class="b-statistics__table-row">(.*?)</tr>', body, re.S):
        m = re.search(r'href="https?://(?:www\.)?ufcstats\.com/event-details/([0-9a-f]+)"[^>]*>\s*([^<]+?)\s*</a>', row)
        d = re.search(r'b-statistics__date">\s*([^<]+?)\s*</span>', row)
        if not m or not d:
            continue
        loc = re.findall(r'<td class="b-statistics__table-col b-statistics__table-col_style_big-top-padding">(.*?)</td>', row, re.S)
        out.append({"id": m.group(1), "name": _text(m.group(2)), "date": _date(d.group(1)),
                    "location": _text(loc[0]) if loc else None})
    return out


def parse_event(body):
    """Event page -> fights in bout order (index 0 = main event), with the per-fighter totals shown there."""
    fights = []
    rows = re.findall(r'<tr class="b-fight-details__table-row[^"]*"[^>]*data-link="https?://(?:www\.)?ufcstats\.com/fight-details/([0-9a-f]+)"[^>]*>(.*?)</tr>', body, re.S)
    for order, (fid, row) in enumerate(rows):
        tds = re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)
        if len(tds) < 10:
            continue
        ids = re.findall(r"fighter-details/([0-9a-f]+)", tds[1])
        names = _pairs(tds[1])
        flags = [f.lower() for f in re.findall(r'b-flag__text">([a-zA-Z]+)', tds[0])]
        if len(ids) < 2 or not flags:
            continue  # upcoming bout (no result yet)
        if flags[0] == "win":
            result = "f1"
        elif len(flags) > 1 and flags[1] == "win":
            result = "f2"
        elif "draw" in flags:
            result = "draw"
        elif "nc" in flags:
            result = "nc"
        else:
            continue
        imgs = re.findall(r'/([a-z_]+)\.png', tds[6])
        method = _pairs(tds[7]) + ["", ""]
        fights.append({
            "id": fid, "order": order, "f1": ids[0], "f2": ids[1], "n1": names[0], "n2": names[1],
            "result": result, "wc": (_pairs(tds[6]) or [""])[0], "title": "belt" in imgs,
            "bonus": [i for i in imgs if i in ("fight", "perf", "sub", "ko")],
            "method": method[0], "detail": method[1],
            "round": int((_pairs(tds[8]) or ["0"])[0] or 0), "time": (_pairs(tds[9]) or [""])[0],
        })
    return fights


def _of(s):
    m = re.match(r"(\d+)\s+of\s+(\d+)", s or "")
    return (int(m.group(1)), int(m.group(2))) if m else (None, None)


def _secs(s):
    m = re.match(r"(\d+):(\d+)", s or "")
    return int(m.group(1)) * 60 + int(m.group(2)) if m else None


def _int(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def parse_fight(body):
    """Fight details page -> scheduled rounds, referee and both fighters' totals."""
    head = _text(body[body.find("b-fight-details__fight"):body.find("b-fight-details__fight") + 1500])
    fmt = re.search(r"Time format:\s*(.*?)\s*(?:Referee:|Details:|$)", head)
    ref = re.search(r"Referee:\s*(.*?)\s*(?:Details:|$)", head)
    rounds = re.match(r"(\d+)\s*Rnd", fmt.group(1)) if fmt else None
    out = {"fmt": fmt.group(1).strip() if fmt else None, "rounds": int(rounds.group(1)) if rounds else None,
           "ref": ref.group(1).split("<")[0].strip()[:60] if ref else None, "s": [{}, {}], "names": []}
    tables = re.findall(r"<table[^>]*>(.*?)</table>", body, re.S)
    # tables[0] = totals, tables[1] = totals per round, tables[2] = sig. strikes, tables[3] = per round
    if tables:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", tables[0].split("<tbody", 1)[-1], re.S)[:10]
        if len(tds) >= 10:
            cols = [_pairs(td) + ["", ""] for td in tds]
            out["names"] = cols[0][:2]
            for i in (0, 1):
                s = out["s"][i]
                s["kd"] = _int(cols[1][i])
                s["sig"], s["sig_a"] = _of(cols[2][i])
                s["tot"], s["tot_a"] = _of(cols[4][i])
                s["td"], s["td_a"] = _of(cols[5][i])
                s["sub"] = _int(cols[7][i])
                s["rev"] = _int(cols[8][i])
                s["ctrl"] = _secs(cols[9][i])
    sig_t = next((t for t in tables[1:] if "Distance" in t and "Head" in t), None)
    if sig_t:
        tds = re.findall(r"<td[^>]*>(.*?)</td>", sig_t.split("<tbody", 1)[-1], re.S)[:9]
        if len(tds) >= 9:
            cols = [_pairs(td) + ["", ""] for td in tds]
            for i in (0, 1):
                s = out["s"][i]
                for k, col in zip(("head", "body", "leg", "dist", "clinch", "ground"), cols[3:9]):
                    s[k], s[k + "_a"] = _of(col[i])
    return out


def parse_fighter_attrs(body):
    f = ufcstats.parse_fighter(body)
    nick = re.search(r'b-content__Nickname">(.*?)</p>', body, re.S)

    def inches(s):
        m = re.match(r"(\d+)'\s*(\d+)", s or "")
        if m:
            return int(m.group(1)) * 12 + int(m.group(2))
        m = re.match(r"([\d.]+)", s or "")
        return float(m.group(1)) if m else None
    w = re.match(r"(\d+)", (re.search(r"Weight:\s*</i>\s*([^<]*)", body) or [None, ""])[1].strip() or "")
    return {"name": f["name"], "nick": _text(nick.group(1)) if nick else "", "record": f["record"],
            "height": inches(f["height"]), "reach": inches(f["reach"]), "weight": int(w.group(1)) if w else None,
            "stance": (f["stance"] or "").strip() or None, "dob": _date(f["dob"] or "")}


def _load(name):
    for base in (CACHE, DATA):
        for p in (os.path.join(base, name + ".json.gz"), os.path.join(base, name + ".json")):
            if os.path.exists(p):
                op = gzip.open if p.endswith(".gz") else open
                with op(p, "rt", encoding="utf-8") as f:
                    return json.load(f)
    return None


def _save(name, obj, base=DATA):
    os.makedirs(base, exist_ok=True)
    p = os.path.join(base, name + ".json.gz")
    tmp = p + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump(obj, f, separators=(",", ":"), sort_keys=True)
    os.replace(tmp, p)


def load_dataset():
    """(events, fights, fighters) merged from the shipped data and any runtime top-ups in cache/."""
    def merged(name):
        base, extra = {}, {}
        for src, dst in ((DATA, base), (CACHE, extra)):
            p = os.path.join(src, f"ufcstats_{name}.json.gz")
            if os.path.exists(p):
                with gzip.open(p, "rt", encoding="utf-8") as f:
                    dst.update(json.load(f))
        base.update(extra)
        return base
    fighters = merged("fighters")
    for k, v in merged("fighters_extra").items():
        fighters.setdefault(k, v)
    return merged("events"), merged("fights"), fighters


def build(base=DATA, workers=4, log=print, max_new_events=None):
    """Fetch every completed event not yet stored, then its fights and any fighters not yet stored."""
    # What's already known (shipped data + cache) decides what to skip; only `base`'s own files are rewritten.
    known_events, _, known_fighters = load_dataset()
    events, fights, fighters = (_load_exact(base, "events"), _load_exact(base, "fights"), _load_exact(base, "fighters"))
    listing = parse_events(ufcstats.get("/statistics/events/completed?page=all"))
    today = datetime.date.today().isoformat()
    todo = [e for e in listing if e["date"] and e["date"] < today and e["id"] not in known_events]
    todo.sort(key=lambda e: e["date"])
    if max_new_events:
        todo = todo[-max_new_events:]
    log(f"{len(todo)} events to fetch ({len(known_events)} stored)")
    new_events, new_fights, new_fighters = {}, {}, {}
    lock = threading.Lock()

    def do_event(e):
        rows = parse_event(ufcstats.get(f"/event-details/{e['id']}"))
        if not rows:
            return  # results not posted yet; try again next time
        def do_fight(r):
            try:
                d = parse_fight(ufcstats.get(f"/fight-details/{r['id']}"))
            except Exception as ex:
                d = {"error": str(ex)[:120]}
            rec = dict(r, event=e["id"], date=e["date"])
            if "s" in d:
                # fight page lists fighters in the same order as the event row; verify by name
                if d.get("names") and d["names"][0] and d["names"][0] != r["n1"] and d["names"][0] == r["n2"]:
                    d["s"] = d["s"][::-1]
                rec.update(fmt=d["fmt"], rounds=d["rounds"], ref=d["ref"], s1=d["s"][0], s2=d["s"][1])
            return rec
        with ThreadPoolExecutor(3) as ex:
            recs = list(ex.map(do_fight, rows))
        with lock:
            for rec in recs:
                new_fights[rec["id"]] = rec
            new_events[e["id"]] = dict(e, fights=[r["id"] for r in rows])

    done = 0
    with ThreadPoolExecutor(max(1, workers // 2)) as ex:
        for _ in ex.map(lambda e: _safe(do_event, e, log), todo):
            done += 1
            if done % 20 == 0:
                log(f"  events {done}/{len(todo)}, fights {len(new_fights)}")
                if base == DATA:
                    _checkpoint(base, events, fights, fighters, new_events, new_fights, new_fighters)
    known_fighters = load_dataset()[2]  # a parallel fetch_fighters() may have filled some in meanwhile
    need = {fid for r in new_fights.values() for fid in (r["f1"], r["f2"])} - set(known_fighters) - set(new_fighters)
    log(f"{len(need)} fighters to fetch")

    def do_fighter(fid):
        try:
            a = parse_fighter_attrs(ufcstats.get(f"/fighter-details/{fid}"))
        except Exception as ex:
            a = {"error": str(ex)[:120]}
        with lock:
            new_fighters[fid] = a
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(do_fighter, sorted(need)), 1):
            if i % 200 == 0:
                log(f"  fighters {i}/{len(need)}")
    _checkpoint(base, events, fights, fighters, new_events, new_fights, new_fighters)
    return len(new_events), len(new_fights), len(new_fighters)


def _load_exact(base, name):
    p = os.path.join(base, f"ufcstats_{name}.json.gz")
    if os.path.exists(p):
        with gzip.open(p, "rt", encoding="utf-8") as f:
            return json.load(f)
    return {}


def _checkpoint(base, events, fights, fighters, ne, nf, nr):
    events.update(ne)
    fights.update(nf)
    fighters.update(nr)
    _save("ufcstats_events", events, base)
    _save("ufcstats_fights", fights, base)
    _save("ufcstats_fighters", fighters, base)


def _safe(fn, arg, log):
    try:
        return fn(arg)
    except Exception as ex:
        log(f"  failed {arg.get('name', arg) if isinstance(arg, dict) else arg}: {ex}")


def fetch_fighters(workers=4, log=print, until_idle=600):
    """Fetch attributes for fighters in stored fights who have none yet, into ufcstats_fighters_extra.
    Keeps polling while a build is still adding fights; stops after `until_idle` seconds with nothing new."""
    extra = _load_exact(DATA, "fighters_extra")
    idle_since = time.time()
    while time.time() - idle_since < until_idle:
        _, fights, fighters = load_dataset()
        need = sorted({fid for r in fights.values() for fid in (r["f1"], r["f2"])} - set(fighters) - set(extra))
        if not need:
            time.sleep(30)
            continue
        idle_since = time.time()
        lock = threading.Lock()

        def one(fid):
            try:
                a = parse_fighter_attrs(ufcstats.get(f"/fighter-details/{fid}"))
            except Exception as ex:
                a = {"error": str(ex)[:120]}
            with lock:
                extra[fid] = a
        with ThreadPoolExecutor(workers) as ex:
            for i, _ in enumerate(ex.map(one, need), 1):
                if i % 200 == 0:
                    log(f"  fighters {i}/{len(need)}")
                    _save("ufcstats_fighters_extra", extra)
        _save("ufcstats_fighters_extra", extra)
        log(f"fighters stored: {len(extra)}")
    return len(extra)


def update(log=lambda *_: None):
    """Runtime top-up: fetch events completed since the shipped dataset, into cache/."""
    return build(base=CACHE, workers=2, log=log, max_new_events=40)


if __name__ == "__main__":
    # a one-off historical build can afford a little more parallelism than the app's default of 4
    ufcstats._sem = threading.Semaphore(8)
    t = time.time()
    if "--fighters" in sys.argv:
        print(fetch_fighters(), f"{time.time() - t:.0f}s")
    else:
        print(build(workers=8), f"{time.time() - t:.0f}s")
