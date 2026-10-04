"""BestFightOdds: moneylines and props from every major US book (Caesars included) for each matchup.

BFO's event grouping is loose (many fights on a card can sit in a generic "UFC" bucket or in a
differently named event), so matchups are pooled from every table we can see and matched to ESPN's
card by fighter names.  Upcoming cards come from the front page; past cards are found through the
fighter pages, which also give each fighter's opening and closing line for every past fight.
"""
import datetime, html, re, time, urllib.parse
from concurrent.futures import ThreadPoolExecutor

from net import cache, fetch, DiskStore
from names import ascii_name, pair_score, shares_token, similarity, tokens

BASE = "https://www.bestfightodds.com"
MONTHS = {m: i for i, m in enumerate(["jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec"], 1)}
pages_disk = DiskStore("bfo_pages")


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def _odds(s):
    s = (s or "").strip().replace("−", "-")
    if re.fullmatch(r"[+-]?\d{3,5}", s):
        v = int(s)
        if abs(v) >= 100:
            return v
    return None


def parse_date(text, ref_ts=None):
    """'October 4th' / 'Oct 3rd 2026' -> epoch at noon UTC.  Without a year, pick the year nearest ref_ts."""
    m = re.search(r"([A-Za-z]{3})[a-z]*\.?\s+(\d{1,2})(?:st|nd|rd|th)?(?:,?\s+(\d{4}))?", text or "")
    if not m or m.group(1).lower() not in MONTHS:
        return None
    mon, day = MONTHS[m.group(1).lower()], int(m.group(2))
    ref = ref_ts or time.time()
    years = [int(m.group(3))] if m.group(3) else [datetime.datetime.fromtimestamp(ref, datetime.timezone.utc).year + d for d in (-1, 0, 1)]
    best = None
    for y in years:
        try:
            ts = datetime.datetime(y, mon, day, 12, tzinfo=datetime.timezone.utc).timestamp()
        except ValueError:
            continue
        if best is None or abs(ts - ref) < abs(best - ref):
            best = ts
    return best


def parse_tables(body, url=None):
    """Every odds table on a BFO page -> list of events with their matchups."""
    events = []
    parts = re.split(r'<div class="table-div" id="event(\d+)">', body)
    for k in range(1, len(parts), 2):
        eid, sec = parts[k], parts[k + 1]
        name = _text((re.search(r"<h1>(.*?)</h1>", sec, re.S) or [None, ""])[1]).replace(" Odds", "")
        date_text = _text((re.search(r'table-header-date">(.*?)<', sec, re.S) or [None, ""])[1])
        href = (re.search(r'<div class="table-header"><a href="([^"]+)"', sec) or [None, None])[1]
        i = sec.find('<table class="odds-table">')
        if i < 0:
            continue
        table = sec[i:sec.find("</table>", i)]
        books = {}
        for bid, inner in re.findall(r'<th scope="col" data-b="(\d+)">(.*?)</th>', table, re.S):
            books[int(bid)] = _text(inner.split("<br")[0])
        matchups = {}
        prop_pos = {}
        cur_mid, next_side = None, 1
        for attrs, row in re.findall(r"<tr([^>]*)>(.*?)</tr>", table, re.S):
            th = re.search(r'<th scope="row">(.*?)</th>', row, re.S)
            if not th:
                continue
            cells = re.findall(r'data-li="\[([\d,]+)\]"><span[^>]*>([^<]*)</span>', row)
            if 'class="pr"' in attrs:
                # Prop rows come in pairs under their matchup (Over/Under, "X wins by KO"/"Any other result");
                # pair by position so a side nobody prices still gets its label.
                if cur_mid not in matchups:
                    continue
                props = matchups[cur_mid]["props"]
                pos = prop_pos.get(cur_mid, 0)
                prop_pos[cur_mid] = pos + 1
                grp = props.setdefault(pos // 2, {"type": None, "team": None, "labels": ["", ""], "odds": {}})
                grp["labels"][pos % 2] = _text(th.group(1))
                for li, val in cells:
                    v = [int(x) for x in li.split(",")]
                    if len(v) < 5:
                        continue
                    book, side, _, ptype, team = v[:5]
                    grp["type"], grp["team"] = ptype, team
                    o = _odds(val)
                    if o is not None and book in books:
                        grp["odds"].setdefault(books[book], [None, None])[side - 1] = o
                continue
            fname = re.search(r'<a href="(/fighters/[^"]+)"><span class="t-b-fcc">([^<]+)</span>', th.group(1))
            if not fname:
                continue
            # A matchup's first row carries its id (an admin link in the main table, id="mu-N" elsewhere).
            mu = re.search(r'id="mu-(\d+)"', attrs) or re.search(r'/cnadm/matchups/(\d+)"', th.group(1))
            if mu:
                cur_mid, next_side = int(mu.group(1)), 1
            mid_side = None
            for li, _ in cells:
                v = [int(x) for x in li.split(",")]
                mid_side = (v[2], v[1])
                break
            mid, side = mid_side if mid_side else (cur_mid, next_side)
            if mid is None:
                continue
            m = matchups.setdefault(mid, {"id": mid, "fighters": ["", ""], "links": ["", ""], "ml": {}, "props": {}})
            m["fighters"][side - 1] = html.unescape(fname.group(2)).strip()
            m["links"][side - 1] = fname.group(1)
            for li, val in cells:
                v = [int(x) for x in li.split(",")]
                o = _odds(val)
                if o is not None and v[0] in books:
                    m["ml"].setdefault(books[v[0]], [None, None])[v[1] - 1] = o
            cur_mid, next_side = mid, 2
        for m in matchups.values():
            m["props"] = [p for p in m["props"].values() if p["odds"]]
        events.append({"id": int(eid), "name": name, "dateText": date_text, "url": BASE + href if href else url,
                       "matchups": [m for m in matchups.values() if all(m["fighters"])]})
    return events


def parse_fighter_page(body):
    """A fighter's odds history: one entry per fight with event link, date, open and closing range."""
    out = []
    i = body.find('<table class="team-stats-table"')
    if i < 0:
        return out
    tbody = body[i:body.find("</table>", i)]
    for seg in re.split(r'<tr class="event-header[^"]*">', tbody)[1:]:
        ev = re.search(r'<a href="(/events/[^"]+)">([^<]*)</a>\s*([^<]*)</td>', seg)
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", seg.split("</tr>", 1)[1] if "</tr>" in seg else "", re.S)
        if not ev or len(rows) < 2:
            continue

        def side(row):
            name = _text((re.search(r'<a href="/fighters/[^"]+">([^<]+)</a>', row) or [None, ""])[1])
            nums = [_odds(x) for x in re.findall(r'<span id="oID\d+">([^<]*)</span>', row)]
            return name, (nums + [None, None, None])[:3]
        me, them = side(rows[0]), side(rows[1])
        li = re.search(r'data-li="\[(\d+),(\d)\]"', seg)
        spark = re.search(r'data-sparkline="([^"]+)"', seg)
        out.append({
            "event": ev.group(2).strip(), "url": BASE + ev.group(1), "date": parse_date(ev.group(3)),
            "fighter": me[0], "opponent": them[0],
            "open": me[1][0], "closeLow": me[1][1], "closeHigh": me[1][2],
            "oppOpen": them[1][0], "oppCloseLow": them[1][1], "oppCloseHigh": them[1][2],
            "matchup": int(li.group(1)) if li else None,
            "spark": [float(x) for x in spark.group(1).split(",")] if spark else None,
        })
    return out


def front_page_events():
    return cache.get("bfo-front", lambda: parse_tables(fetch(BASE + "/"), BASE + "/"), ttl=60)


def event_page(url, past=False):
    def load():
        key = "evt:" + url
        if past:
            v = pages_disk.get(key)
            if v is not None:
                return v
        evs = parse_tables(fetch(url), url)
        if past:
            pages_disk.put(key, evs)
        return evs
    return cache.get(("bfo-event", url), load, ttl=6 * 3600 if past else 60)


def _search_links(term):
    body = fetch(BASE + "/search?query=" + urllib.parse.quote_plus(ascii_name(term)))
    if 'id="team-name"' in body:  # search jumped straight to the fighter page
        return body, []
    return None, [(l, html.unescape(n).strip()) for l, n in re.findall(r'href="(/fighters/[^"]+)">([^<]+)</a>', body)]


def _merge(pages):
    merged, seen = [], set()
    for hist in pages:
        for h in hist:
            key = h["matchup"] or (h["date"], h["opponent"])
            if key not in seen:
                seen.add(key)
                merged.append(h)
    merged.sort(key=lambda h: h["date"] or 0, reverse=True)
    return merged


def fighter_history(name, opponents=()):
    """Odds history for a fighter by name ([] when BFO doesn't know them).

    BFO sometimes keeps two pages for one fighter ("Cong Wang" and "Wang Cong"); those are merged.
    If no page carries the name at all (ESPN uses a ring name, e.g. "Patricio Pitbull" for BFO's
    "Patricio Freire"), pages sharing a name token are accepted when they list a known opponent.
    """
    def load():
        direct, links = _search_links(name)
        if direct:
            return parse_fighter_page(direct)
        cands = {}
        for link, n in links:
            s = similarity(name, n)
            if s >= 0.86:
                cands[link] = max(s, cands.get(link, 0))
        return _merge(parse_fighter_page(fetch(BASE + l)) for l in sorted(cands, key=cands.get, reverse=True)[:3])

    def load_by_opponents():
        tried = set()
        for term in sorted({t for t in tokens(name) if len(t) >= 4}, key=len, reverse=True)[:2]:
            _, links = _search_links(term)
            for link, n in links:
                if link in tried or not shares_token(name, n) or len(tried) >= 4:
                    continue
                tried.add(link)
                hist = parse_fighter_page(fetch(BASE + link))
                if sum(1 for h in hist if any(similarity(o, h["opponent"]) >= 0.85 for o in opponents)) >= 2:
                    return hist
        return []
    try:
        hist = cache.get(("bfo-fhist", name.lower()), load, ttl=3 * 3600)
        if not hist and opponents:
            hist = cache.get(("bfo-fhist-opp", name.lower()), load_by_opponents, ttl=3 * 3600)
        return hist
    except Exception:
        return []


def _match_fight(fight, pool, event_ts):
    """Best BFO matchup for an ESPN fight, oriented to ESPN's fighter order.  pool: [(event, matchup)].

    Moneylines are flipped to ESPN's order when BFO lists the fighters the other way round.  Props are
    left alone: their two sides are outcomes (over/under, yes/any other result), and the labels name
    the fighter.
    """
    a, b = fight["fighters"][0]["name"], fight["fighters"][1]["name"]
    best = None
    for ev, m in pool:
        s1 = pair_score(a, b, m["fighters"][0], m["fighters"][1])
        s2 = pair_score(a, b, m["fighters"][1], m["fighters"][0])
        s, swap = (s1, False) if s1 >= s2 else (s2, True)
        if s < 0.84:
            continue
        ets = parse_date(ev.get("dateText"), event_ts)
        near = ets is None or event_ts is None or abs(ets - event_ts) < 4 * 86400
        nbooks = sum(1 for v in m["ml"].values() if v[0] is not None and v[1] is not None)
        rank = (near, round(s, 2), nbooks)
        if best is None or rank > best[0]:
            best = (rank, ev, m, swap)
    if not best or not best[0][0]:
        return None
    _, ev, m, swap = best

    def flip(pair):
        return [pair[1], pair[0]] if swap else list(pair)
    return {"matchup": m["id"], "event": ev["name"], "eventUrl": ev.get("url"),
            "names": flip(m["fighters"]), "ml": {bk: flip(v) for bk, v in m["ml"].items()}, "props": m["props"]}


def _find_event_url(fight, ets):
    """The BFO event page holding this fight, found via either fighter's odds history."""
    for fi in (0, 1):
        me, opp = fight["fighters"][fi]["name"], fight["fighters"][1 - fi]["name"]
        for h in fighter_history(me):
            if h["date"] and abs(h["date"] - ets) < 3 * 86400 and pair_score(me, opp, h["fighter"], h["opponent"]) >= 0.84:
                return h["url"]
    return None


def odds_for_card(card, now=None, pool_size=6):
    """{espn_fight_id: matched BFO matchup} for a card from espn.card()."""
    now = now or time.time()
    ets = card.get("date")
    past = bool(ets and ets < now - 2 * 86400)
    pool = []
    if not past:
        for ev in front_page_events():
            pool += [(ev, m) for m in ev["matchups"]]
    out = {}
    for f in card["fights"]:
        r = _match_fight(f, pool, ets)
        if r:
            out[f["id"]] = r
    unmatched = [f for f in card["fights"] if f["id"] not in out]
    if not unmatched or not ets:
        return out
    # Not on the front page (past card, or BFO filed it elsewhere): find it through fighter pages.
    with ThreadPoolExecutor(pool_size) as ex:
        urls = {u for u in ex.map(lambda f: _find_event_url(f, ets), unmatched[:16]) if u}
        pages = list(ex.map(lambda u: _safe(event_page, u, past), sorted(urls)))
    for evs in pages:
        for ev in evs or []:
            pool += [(ev, m) for m in ev["matchups"]]
    for f in unmatched:
        r = _match_fight(f, pool, ets)
        if r:
            out[f["id"]] = r
    return out


def _safe(fn, *a):
    try:
        return fn(*a)
    except Exception:
        return None
