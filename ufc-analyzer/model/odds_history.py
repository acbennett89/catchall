"""Historical betting lines from BestFightOdds, for benchmarking the model against the market.

Crawls fighter pages outward from today's UFC fighters, following opponents met at UFC events, and
records every matchup's opening line and closing range for both fighters.  Fighters in the UFCStats
dataset that the crawl never reached are looked up by name afterwards.

    python -m model.odds_history      # writes model/data/bfo_odds.json.gz (resumable)
"""
import gzip, json, os, re, sys, threading, time
from collections import deque
from concurrent.futures import ThreadPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))

import bfo  # noqa: E402
from net import fetch  # noqa: E402
from model.scrape import load_dataset  # noqa: E402

OUT = os.path.join(HERE, "data", "bfo_odds.json.gz")
UFC_EVENT = re.compile(r"\bUFC\b|Ultimate Fighter|\bTUF\b", re.I)


def parse_page(body):
    """Fighter page -> (fighter name, [matchup entries], {opponent link: name})."""
    name = re.search(r'<h1 id="team-name">([^<]*?)(?: Odds)?</h1>', body)
    entries, links = [], {}
    i = body.find('<table class="team-stats-table"')
    if i < 0:
        return (name.group(1) if name else None), entries, links
    tbody = body[i:body.find("</table>", i)]
    for seg in re.split(r'<tr class="event-header[^"]*">', tbody)[1:]:
        ev = re.search(r'<a href="(/events/[^"]+)">([^<]*)</a>\s*([^<]*)</td>', seg)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", seg.split("</tr>", 1)[1] if "</tr>" in seg else "", re.S)
        if not ev or len(rows) < 2:
            continue

        def side(row):
            m = re.search(r'<a href="(/fighters/[^"]+)">([^<]+)</a>', row)
            nums = [bfo._odds(x) for x in re.findall(r'<span id="oID\d+">([^<]*)</span>', row)]
            return (m.group(1) if m else None), (bfo._text(m.group(2)) if m else ""), (nums + [None, None, None])[:3]
        a, b = side(rows[0]), side(rows[1])
        li = re.search(r'data-li="\[(\d+),(\d)\]"', seg)
        if not li:
            continue
        if b[0] and UFC_EVENT.search(ev.group(2)):
            links[b[0]] = b[1]
        entries.append({"matchup": int(li.group(1)), "event": ev.group(2).strip(), "eventUrl": ev.group(1),
                        "date": bfo.parse_date(ev.group(3)), "a": a[1], "aLink": a[0], "b": b[1], "bLink": b[0],
                        "aOpen": a[2][0], "aLo": a[2][1], "aHi": a[2][2], "bOpen": b[2][0], "bLo": b[2][1], "bHi": b[2][2]})
    return (name.group(1).strip() if name else None), entries, links


def crawl(max_pages=6000, workers=3, log=print):
    state = {"matchups": {}, "visited": []}
    if os.path.exists(OUT):
        with gzip.open(OUT, "rt", encoding="utf-8") as f:
            state = json.load(f)
    matchups = state["matchups"]
    visited = set(state["visited"])
    lock = threading.Lock()
    queue = deque()

    front = fetch(bfo.BASE + "/")
    for link in re.findall(r'<a href="(/fighters/[^"]+)"><span class="t-b-fcc">', front):
        if link not in visited:
            queue.append(link)
    # re-expand from stored matchups so a resumed crawl continues where it stopped
    for m in matchups.values():
        for l in (m.get("aLink"), m.get("bLink")):
            if l and l not in visited and UFC_EVENT.search(m.get("event", "")):
                queue.append(l)
    seen_q = set(queue)

    def visit(link):
        try:
            body = fetch(bfo.BASE + link)
        except Exception as e:
            log(f"  {link}: {e}")
            return []
        _, entries, links = parse_page(body)
        with lock:
            visited.add(link)
            for e in entries:
                e = dict(e, aLink=e["aLink"] or link)
                key = str(e["matchup"])
                # keep one orientation per matchup; the first page to see it wins
                matchups.setdefault(key, e)
        return list(links)

    pages = 0
    with ThreadPoolExecutor(workers) as ex:
        while queue and pages < max_pages:
            batch = []
            while queue and len(batch) < workers * 4:
                l = queue.popleft()
                if l not in visited:
                    batch.append(l)
            for new_links in ex.map(visit, batch):
                for l in new_links:
                    if l not in visited and l not in seen_q:
                        seen_q.add(l)
                        queue.append(l)
            pages += len(batch)
            if pages % 200 < len(batch):
                log(f"  pages {pages}, queue {len(queue)}, matchups {len(matchups)}")
                _save(matchups, visited)
            time.sleep(0.2)
    _save(matchups, visited)
    return len(visited), len(matchups)


def fill_missing(workers=3, log=print, since="2008-01-01"):
    """Look up, by name, UFCStats fighters (UFC fights since `since`) that the crawl never reached."""
    with gzip.open(OUT, "rt", encoding="utf-8") as f:
        state = json.load(f)
    matchups, visited = state["matchups"], set(state["visited"])
    known = {bfo_name_key(m[k]) for m in matchups.values() for k in ("a", "b")}
    _, fights, fighters = load_dataset()
    names = {}
    for r in fights.values():
        if r.get("date", "") >= since:
            for fid, n in ((r["f1"], r["n1"]), (r["f2"], r["n2"])):
                names[fid] = n
    missing = sorted({n for n in names.values() if bfo_name_key(n) not in known})
    log(f"{len(missing)} fighters not reached by the crawl; searching by name")
    lock = threading.Lock()

    def look(n):
        hist = bfo.fighter_history(n)  # search + page fetch (merges duplicate pages)
        with lock:
            for h in hist:
                if h.get("matchup"):
                    matchups.setdefault(str(h["matchup"]), {
                        "matchup": h["matchup"], "event": h["event"], "eventUrl": h["url"].replace(bfo.BASE, ""),
                        "date": h["date"], "a": h["fighter"], "aLink": None, "b": h["opponent"], "bLink": None,
                        "aOpen": h["open"], "aLo": h["closeLow"], "aHi": h["closeHigh"],
                        "bOpen": h["oppOpen"], "bLo": h["oppCloseLow"], "bHi": h["oppCloseHigh"]})
    with ThreadPoolExecutor(workers) as ex:
        for i, _ in enumerate(ex.map(look, missing), 1):
            if i % 100 == 0:
                log(f"  searched {i}/{len(missing)}, matchups {len(matchups)}")
                _save(matchups, visited)
    _save(matchups, visited)
    return len(missing), len(matchups)


def bfo_name_key(n):
    from names import tokens
    return " ".join(sorted(tokens(n or "")))


def _save(matchups, visited):
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    tmp = OUT + ".tmp"
    with gzip.open(tmp, "wt", encoding="utf-8") as f:
        json.dump({"matchups": matchups, "visited": sorted(visited)}, f, separators=(",", ":"))
    os.replace(tmp, OUT)


def load():
    if not os.path.exists(OUT):
        return {}
    with gzip.open(OUT, "rt", encoding="utf-8") as f:
        return json.load(f)["matchups"]


if __name__ == "__main__":
    t = time.time()
    if "--fill" in sys.argv:
        print(fill_missing(), f"{time.time() - t:.0f}s")
    else:
        print(crawl(), f"{time.time() - t:.0f}s")
