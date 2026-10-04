"""UFCStats.com: the UFC's official career stats (SLpM, Str. Acc., SApM, Str. Def, TD Avg/Acc/Def, Sub. Avg)
and the round-by-round fight history behind them.

The site sits behind a light proof-of-work browser check (find n so sha256(nonce:n) starts with k zeros,
POST it to /__c, get a cookie).  The session solves it once and reuses the cookie.
"""
import hashlib, html, http.cookiejar, re, threading, urllib.parse, urllib.request

from net import cache, fetch, DiskStore
from names import ascii_name, similarity, tokens

BASE = "http://ufcstats.com"
_jar = http.cookiejar.CookieJar()
_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(_jar))
_sem = threading.Semaphore(4)  # be polite: at most 4 concurrent requests
_challenge_lock = threading.Lock()
pages_disk = DiskStore("ufcstats_fighters")
ids_disk = DiskStore("ufcstats_ids")
CHALLENGE = re.compile(r'var nonce="([0-9a-f]+)",\s*target=new Array\((\d+)\+1\)')


def solve(nonce, zeros):
    target = "0" * zeros
    n = 0
    while not hashlib.sha256(f"{nonce}:{n}".encode()).hexdigest().startswith(target):
        n += 1
    return n


def get(path):
    url = path if path.startswith("http") else BASE + path
    with _sem:
        body = fetch(url, opener=_opener)
        m = CHALLENGE.search(body)
        if not m:
            return body
        with _challenge_lock:
            body = fetch(url, opener=_opener)  # another thread may have solved it meanwhile
            m = CHALLENGE.search(body)
            if m:
                n = solve(m.group(1), int(m.group(2)))
                data = urllib.parse.urlencode({"nonce": m.group(1), "n": n}).encode()
                fetch(BASE + "/__c", data=data, opener=_opener,
                      headers={"Content-Type": "application/x-www-form-urlencoded"})
                body = fetch(url, opener=_opener)
        if CHALLENGE.search(body):
            raise RuntimeError("UFCStats browser check not passed")
        return body


def _text(s):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", s or ""))).strip()


def parse_search(body):
    out = []
    for row in re.findall(r'<tr class="b-statistics__table-row">(.*?)</tr>', body, re.S):
        link = re.search(r'href="https?://(?:www\.)?ufcstats\.com/fighter-details/([0-9a-f]+)"', row)
        if not link:
            continue
        cells = [_text(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
        if len(cells) < 10:
            continue
        out.append({"id": link.group(1), "name": f"{cells[0]} {cells[1]}".strip(), "nickname": cells[2],
                    "height": cells[3], "weight": cells[4], "reach": cells[5], "stance": cells[6],
                    "record": f"{cells[7]}-{cells[8]}-{cells[9]}"})
    return out


def _pct(v):
    m = re.match(r"(-?[\d.]+)", v or "")
    return float(m.group(1)) if m else None


def parse_fighter(body):
    name = _text((re.search(r'b-content__title-highlight">(.*?)</span>', body, re.S) or [None, ""])[1])
    record = _text((re.search(r'b-content__title-record">(.*?)</span>', body, re.S) or [None, ""])[1]).replace("Record:", "").strip()
    info = {}
    for label, val in re.findall(r'<i class="b-list__box-item-title[^"]*">\s*([^<:]+):\s*</i>([^<]*)', body):
        info[label.strip().lower()] = _text(val)
    career = {
        "slpm": _pct(info.get("slpm")),
        "strAcc": _pct(info.get("str. acc.")),
        "sapm": _pct(info.get("sapm")),
        "strDef": _pct(info.get("str. def")),
        "tdAvg": _pct(info.get("td avg.")),
        "tdAcc": _pct(info.get("td acc.")),
        "tdDef": _pct(info.get("td def.")),
        "subAvg": _pct(info.get("sub. avg.")),
    }
    fights = []
    for row in re.findall(r'<tr class="b-fight-details__table-row b-fight-details__table-row__hover[^"]*"(.*?)</tr>', body, re.S):
        flag = re.search(r'b-flag__text">([a-z]+)', row)
        tds = re.findall(r'<td class="b-fight-details__table-col[^"]*">(.*?)</td>', row, re.S)
        cols = [[_text(p) for p in re.findall(r'<p class="b-fight-details__table-text">(.*?)</p>', td, re.S)] for td in tds]
        if len(cols) < 10:
            continue

        def pair(i):
            c = cols[i] + ["", ""]
            return [c[0], c[1]]
        fights.append({
            "result": (flag.group(1) if flag else "").lower(),   # win / loss / draw / nc / next
            "opponent": pair(1)[1],
            "kd": pair(2), "str": pair(3), "td": pair(4), "sub": pair(5),
            "event": pair(6)[0], "date": pair(6)[1],
            "method": pair(7)[0], "methodDetail": pair(7)[1],
            "round": (cols[8] + [""])[0], "time": (cols[9] + [""])[0],
        })
    return {"name": name, "record": record, "height": info.get("height"), "reach": info.get("reach"),
            "stance": info.get("stance"), "dob": info.get("dob"), "career": career, "fights": fights}


def search(term):
    q = urllib.parse.quote_plus(ascii_name(term))
    return cache.get(("ufcs-search", term.lower()), lambda: parse_search(get(f"/statistics/fighters/search?query={q}")), ttl=86400)


def find_id(name, first=None, last=None, espn_id=None):
    """UFCStats fighter id for a name, or None.  Results (including misses) are remembered on disk."""
    key = str(espn_id or name)
    hit = ids_disk.get(key, max_age=30 * 86400)
    if hit is not None:
        return hit or None
    terms = []
    for t in [last, first] + list(reversed(tokens(name))):
        if t and t.lower() not in [x.lower() for x in terms] and len(t) > 1:
            terms.append(t)
    best, best_s = None, 0.0
    for t in terms[:4]:
        cands = search(t)
        for c in cands:
            # also try first name + nickname: ESPN lists some fighters by ring name ("Patricio Pitbull")
            s = max(similarity(name, c["name"]), similarity(name, f'{c["name"].split(" ")[0]} {c["nickname"]}') if c["nickname"] else 0)
            if s > best_s:
                best, best_s = c, s
        if best_s >= 0.97:
            break
    fid = best["id"] if best and best_s >= 0.86 else ""
    ids_disk.put(key, fid)
    return fid or None


def fighter(fid):
    def load():
        try:
            out = parse_fighter(get(f"/fighter-details/{fid}"))
            out["id"] = fid
            pages_disk.put(fid, out)
            return out
        except Exception:
            v = pages_disk.get(fid)
            if v:
                return v
            raise
    return cache.get(("ufcs-fighter", fid), load, ttl=6 * 3600)
