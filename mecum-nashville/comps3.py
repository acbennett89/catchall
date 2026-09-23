"""Mecum comps, third pass.

Changes from comps2:
  * a grade-filtered tier must have a real pool (>= MIN_GRADE_N) or we fall through to any grade —
    three 'Feature' Z06s were pricing a 354-mile car at $19K while 25 Z06s overall said $28K+.
  * for modern cars (MODERN_YEAR+) with a known odometer, comps are matched on MILEAGE: we fetch
    the odometer from each comp's lot page (cached in odo_cache.json) and price against comps in
    the same mileage band, falling back to a log-log fit of price on miles when the band is thin.
Writes comps.json in the shape the page expects.
"""
import json, re, subprocess, statistics, math, time, os
from concurrent.futures import ThreadPoolExecutor

APP = "U6CFCQ7V52"; KEY = "0291c46cde807bcb428a021a96138fcb"; INDEX = "wp_posts_lot"
# comps come from the three years before the auction being priced, and never from after it —
# so a finished sale's expected prices are what you could have known walking in
_AUC = json.load(open("auction.json")) if os.path.exists("auction.json") else {"start": 1790035200, "end": 1790380800}
SINCE = _AUC["start"] - 3 * 365 * 86400
BASE = f"sold=1 AND hammer_price_meta > 0 AND auction_end_date_meta > {SINCE} AND auction_end_date_meta < {_AUC['start']}"
MIN_N, MIN_GRADE_N, MODERN_YEAR = 4, 6, 1985
CUSTOM_WORDS = {"custom", "resto", "restomod", "mod", "replica", "tribute", "pro", "touring", "street", "rod", "hot"}
ATTRS = ["post_title", "hammer_price_meta", "auction_end_date_meta", "web_id_meta", "permalink", "taxonomies_hierarchical"]
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128"
import urllib.request


def q(s): return '"' + str(s).replace('"', '\\"') + '"'
def years(y, span): return "(" + " OR ".join(f"taxonomies.lot_year.name:{y + d}" for d in range(-span, span + 1)) + ")"
def grade(l):
    s = l["status"]
    return "Main attraction" if "Main attraction" in s else "Feature" if "Feature" in s else "star" if "star" in s else "General"
def grade_filter(g):
    return f' AND taxonomies.lot_status.name:{q(g)}' if g != "General" else ' AND NOT taxonomies.lot_status.name:"Feature" AND NOT taxonomies.lot_status.name:"Main attraction" AND NOT taxonomies.lot_status.name:"star"'


def tiers(l):
    y, mk, md, tr = l["year"], l["make"], l["model"], l["trim"]
    if not (y and mk): return []
    g = grade_filter(grade(l)); out = []
    mm = f"taxonomies.make.name:{q(mk)}" + (f" AND taxonomies.model.name:{q(md)}" if md else "")
    if md:
        if tr:
            out += [("exact trim, same year", f"{mm} AND taxonomies.trim_sub_model.name:{q(tr)} AND taxonomies.lot_year.name:{y}{g}", "", True),
                    ("exact trim, +/-2 yrs", f"{mm} AND taxonomies.trim_sub_model.name:{q(tr)} AND {years(y, 2)}{g}", "", True),
                    ("exact trim, same year", f"{mm} AND taxonomies.trim_sub_model.name:{q(tr)} AND taxonomies.lot_year.name:{y}", "", False),
                    ("exact trim, +/-2 yrs", f"{mm} AND taxonomies.trim_sub_model.name:{q(tr)} AND {years(y, 2)}", "", False)]
        out += [("same year, model", f"{mm} AND taxonomies.lot_year.name:{y}{g}", "", True),
                ("+/-2 yrs, model", f"{mm} AND {years(y, 2)}{g}", "", True),
                ("same year, model", f"{mm} AND taxonomies.lot_year.name:{y}", "", False),
                ("+/-2 yrs, model", f"{mm} AND {years(y, 2)}", "", False),
                ("+/-5 yrs, model", f"{mm} AND {years(y, 5)}", "", False),
                ("any year, model", mm, "", False)]
    else:
        title = " ".join(w for w in (l["title"] or "").split() if not w.isdigit())
        out += [("title match, +/-2 yrs", f"{mm} AND {years(y, 2)}{g}", title, True),
                ("title match, +/-2 yrs", f"{mm} AND {years(y, 2)}", title, False),
                ("title match, +/-5 yrs", f"{mm} AND {years(y, 5)}", title, False),
                ("same make, +/-2 yrs", f"{mm} AND {years(y, 2)}", "", False)]
    return out


def pools(l):
    """Return (label, graded?, hits) for the first tier with an adequate pool."""
    ts = tiers(l)
    if not ts: return None
    body = {"requests": [{"indexName": INDEX, "query": text, "hitsPerPage": 80, "filters": f"{BASE} AND {f}",
                          "attributesToRetrieve": ATTRS, "attributesToHighlight": [], "attributesToSnippet": []} for (_, f, text, _) in ts]}
    for attempt in range(4):
        try:
            req = urllib.request.Request(f"https://{APP}-dsn.algolia.net/1/indexes/*/queries", data=json.dumps(body).encode(),
                                         headers={"x-algolia-application-id": APP, "x-algolia-api-key": KEY, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r: res = json.load(r)["results"]
            break
        except Exception:
            time.sleep(2 * (attempt + 1))
            if attempt == 3: return None
    for (label, _, _, graded), r in zip(ts, res):
        hits = [h for h in r["hits"] if h.get("web_id_meta") != l["id"]]
        need = MIN_GRADE_N if graded else MIN_N
        if len(hits) >= need or (r is res[-1] and hits):
            return label, graded, hits
    return "no comps", False, []


# ---- odometer cache for comp lots --------------------------------------------------------
ODO_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "odo_cache.json")  # shared across auctions
odo = json.load(open(ODO_FILE)) if os.path.exists(ODO_FILE) else {}


def fetch_odo(item):
    wid, url = item
    for attempt in range(3):
        r = subprocess.run(["curl", "-sL", "--max-time", "40", "-A", UA, url], capture_output=True)
        page = r.stdout.decode("utf-8", "ignore")
        if r.returncode == 0 and len(page) > 20000: break
        time.sleep(2 * (attempt + 1))
    else:
        return wid, None
    m = re.search(r'\\"odometer\\":\\"([^"\\]*)\\"', page)
    u = re.search(r'\\"odometerUnits\\":\\"([^"\\]*)\\"', page)
    digits = re.sub(r"[^\d]", "", m.group(1)) if m else ""
    return wid, {"mi": int(digits) if digits else None, "u": u.group(1) if u else None}


def band(mi):
    if mi is None: return None
    return 0 if mi < 5000 else 1 if mi < 20000 else 2 if mi < 60000 else 3 if mi < 120000 else 4
BAND_NAMES = ["under 5K mi", "5K–20K mi", "20K–60K mi", "60K–120K mi", "120K+ mi"]


def summarize(prices, weights=None):
    """median, p25, p75, lo, hi — weighted when weights are given (like-kind comps count more)."""
    if not weights:
        p = sorted(prices); n = len(p)
        qs = statistics.quantiles(p, n=4) if n >= 4 else [p[0], statistics.median(p), p[-1]]
        return round(statistics.median(p)), round(qs[0]), round(qs[2]), p[0], p[-1]
    pairs = sorted(zip(prices, weights)); total = sum(w for _, w in pairs)
    def wq(q):
        acc = 0
        for p, w in pairs:
            acc += w
            if acc >= q * total: return p
        return pairs[-1][0]
    return round(wq(0.5)), round(wq(0.25)), round(wq(0.75)), pairs[0][0], pairs[-1][0]


# words that describe what kind of car it is, once year/make/model are stripped from the title
STOP = {"the", "and", "of", "a", "an", "with"}
def descriptors(title, l):
    skip = {str(l.get("year") or ""), *(l.get("make") or "").lower().split(), *(l.get("model") or "").lower().split()}
    # numbers stay: "Chevelle 300", "Z06", "442" are trims — only the model year is stripped (it is in skip)
    return {w for w in re.sub(r"[^a-z0-9 ]", " ", (title or "").lower()).split() if w not in skip and w not in STOP}


def kind_score(lot_desc, comp_title, l):
    """1 = same descriptors (convertible vs convertible), 0 = nothing in common. Both plain = 1."""
    cd = descriptors(comp_title, l)
    if not lot_desc and not cd: return 1.0
    if not lot_desc or not cd: return 0.35
    return len(lot_desc & cd) / len(lot_desc | cd)


def build(l, label, graded, hits, lot_miles):
    g = grade(l)
    tier = label + (f" · {g.lower()} grade" if graded else "")
    note = None
    # like-kind: a Convertible prices against convertibles, a Custom against customs, a Coupe against coupes.
    # Enough close matches -> they become the pool; otherwise every comp stays but the close ones weigh more.
    ld = descriptors(l.get("title"), l)
    scored = [(h, kind_score(ld, h.get("post_title"), l)) for h in hits]
    pool_n = len(hits)
    # a comp with nothing in common (a ZR1 against a 2LT coupe) is a different car: drop it when we can afford to
    nonzero = [(h, s) for h, s in scored if s > 0]
    if ld and len(nonzero) >= 4 and len(nonzero) < len(scored):
        scored = nonzero
    like = [h for h, s in scored if s >= 0.5]
    if ld and 4 <= len(like) < len(scored):
        tier += f" · like-kind ({' '.join(sorted(ld))}: {len(like)} of {pool_n})"
        scored = [(h, s) for h, s in scored if s >= 0.5]
    elif ld and len(scored) < pool_n:
        tier += (f" · like-kind ({' '.join(sorted(ld))}: {len(scored)} of {pool_n})" if all(s >= 0.5 for _, s in scored)
                 else f" · like-kind weighted ({len(scored)} of {pool_n})")
    elif ld and any(s < 1 for _, s in scored):
        tier += " · weighted toward like-kind"
    hits = [h for h, _ in scored]
    w_of = {id(h): 0.15 + 0.85 * s for h, s in scored}
    prices = [h["hammer_price_meta"] for h in hits]
    weights = [w_of[id(h)] for h in hits] if ld and any(s < 1 for _, s in scored) else None
    med, p25, p75, lo, hi = summarize(prices, weights)
    expected = p25 if (g == "General" and graded and len(prices) >= 4) else med
    # honesty flags: a thin pool is a guess, and a custom build's value is in the build, which comps can't see
    if len(prices) < 4:
        note = f"only {len(prices)} comp{'s' if len(prices) != 1 else ''} — treat as a rough guess"
    if ld & CUSTOM_WORDS:
        note = (note + "; " if note else "") + "custom build — comps range widely and sales often land well below build cost"
    # mileage-aware pricing for modern cars with a known odometer
    if lot_miles is not None and (l["year"] or 0) >= MODERN_YEAR:
        withmi = [(h, odo.get(h["web_id_meta"], {}).get("mi")) for h in hits]
        withmi = [(h, m) for h, m in withmi if m]
        b = band(lot_miles)
        same = [h for h, m in withmi if band(m) == b]
        if len(same) >= 4:
            # like-kind weights carry into the mileage band, so a same-mileage different-trim car still counts less
            med, p25, p75, lo, hi = summarize([h["hammer_price_meta"] for h in same], [w_of[id(h)] for h in same] if weights else None); expected = med
            tier += f" · mileage-matched ({BAND_NAMES[b]}, {len(same)} of {len(hits)})"; hits = same + [h for h in hits if h not in same]
        elif len(withmi) >= 8 and lot_miles > 0:
            # log-log fit of price on miles across the pool, evaluated at this car's mileage
            xs = [math.log(max(m, 100)) for _, m in withmi]; ys = [math.log(h["hammer_price_meta"]) for h, _ in withmi]
            mx, my = statistics.mean(xs), statistics.mean(ys)
            sxx = sum((x - mx) ** 2 for x in xs); slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys)) / sxx if sxx else 0
            if slope < 0:  # only trust a fit that says what it should: more miles, less money
                pred = math.exp(my + slope * (math.log(max(lot_miles, 100)) - mx))
                resid = [y - (my + slope * (x - mx)) for x, y in zip(xs, ys)]; sd = statistics.pstdev(resid)
                expected = round(pred); p25, p75 = round(pred * math.exp(-0.67 * sd)), round(pred * math.exp(0.67 * sd))
                tier += f" · mileage-adjusted (fit on {len(withmi)} comps with odometers)"
                note = (note + "; " if note else "") + f"{len(same)} comps in the {BAND_NAMES[b]} band; adjusted from the whole pool instead"
        else:
            note = (note + "; " if note else "") + f"comps don't account for mileage ({len(withmi)} of {len(hits)} had odometers)"
    hits.sort(key=lambda h: -h.get("auction_end_date_meta", 0))
    return {"tier": tier, "n": len(prices), "grade": g, "median": expected, "all_median": med, "p25": p25, "p75": p75, "lo": lo, "hi": hi, "note": note,
            "recent": [{"title": h["post_title"], "price": h["hammer_price_meta"], "miles": odo.get(h["web_id_meta"], {}).get("mi"),
                        "auction": (h.get("taxonomies_hierarchical") or {}).get("auction_tax", {}).get("lvl0", [""])[0],
                        "url": "https://www.mecum.com" + h.get("permalink", "")} for h in hits[:6]]}


if __name__ == "__main__":
    lots = json.load(open("lots.json")); details = json.load(open("details.json"))
    work = [l for l in lots if l["type"] in ("Auto", "Motorcycle", "Tractor", "Trailer")]
    def lot_miles(l):
        o = (details.get(l["id"]) or {}).get("odometer"); d = re.sub(r"[^\d]", "", o or ""); return int(d) if d else None
    t0 = time.time(); print("lots:", len(work), flush=True)
    with ThreadPoolExecutor(8) as ex: P = dict(zip([l["id"] for l in work], ex.map(pools, work)))
    print("pools in", round(time.time() - t0), "s", flush=True)
    # which comp lots need an odometer? only those backing modern cars with a known odometer
    need = {}
    for l in work:
        if lot_miles(l) is None or (l["year"] or 0) < MODERN_YEAR or not P.get(l["id"]): continue
        for h in P[l["id"]][2]:
            if h["web_id_meta"] not in odo: need[h["web_id_meta"]] = "https://www.mecum.com" + h.get("permalink", "")
    print("comp odometers to fetch:", len(need), flush=True)
    with ThreadPoolExecutor(12) as ex:
        for i, (wid, d) in enumerate(ex.map(fetch_odo, need.items())):
            if d: odo[wid] = d
            if i % 500 == 0:
                print(" odo", i, round(time.time() - t0), "s", flush=True); json.dump(odo, open(ODO_FILE, "w"))
    json.dump(odo, open(ODO_FILE, "w"))
    comps = {}
    for l in work:
        p = P.get(l["id"])
        comps[l["id"]] = build(l, *p, lot_miles(l)) if p and p[2] else {"tier": "no comps", "n": 0, "grade": grade(l)}
    json.dump(comps, open("comps.json", "w"))
    from collections import Counter
    print(Counter(c["tier"].split(" · mileage")[0] for c in comps.values()).most_common(8))
    print("mileage-matched:", sum(1 for c in comps.values() if "mileage-matched" in c["tier"]), "mileage-adjusted:", sum(1 for c in comps.values() if "mileage-adjusted" in c["tier"]), "done in", round(time.time() - t0), "s")
