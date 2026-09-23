"""Pull EVERY lot in Mecum's public index — all auctions, all years, all makes and models — into corpus.jsonl.

Algolia returns at most 1,000 hits per query, so we page by auction, then by run day, and split any
day that still exceeds 1,000 by lot type and then by make. One line of JSON per lot."""
import json, os, time, urllib.request
from concurrent.futures import ThreadPoolExecutor

APP, KEY, INDEX = "U6CFCQ7V52", "0291c46cde807bcb428a021a96138fcb", "wp_posts_lot_sort_order_asc"
ATTRS = ["web_id_meta", "post_title", "taxonomies", "auction_end_date_meta", "hammer_price_meta", "sold", "bid_goes_on",
         "current_bid_meta", "engine_configuration_meta", "transmission_type_meta", "lot_series_meta", "color_meta",
         "interior_meta", "lot_number_meta", "permalink", "highest_bid_or_price"]
OUT = "corpus.jsonl"


def query(body, tries=4):
    for a in range(tries):
        try:
            req = urllib.request.Request(f"https://{APP}-dsn.algolia.net/1/indexes/{INDEX}/query", data=json.dumps(body).encode(),
                                         headers={"x-algolia-application-id": APP, "x-algolia-api-key": KEY, "Content-Type": "application/json"})
            with urllib.request.urlopen(req, timeout=60) as r: return json.load(r)
        except Exception as e:
            time.sleep(2 * (a + 1))
            if a == tries - 1: raise


def facet(filters, name):
    d = query({"query": "", "hitsPerPage": 0, "filters": filters, "facets": [name], "maxValuesPerFacet": 1000})
    return d.get("facets", {}).get(name) or {}


def q(s): return '"' + str(s).replace('"', '\\"') + '"'


def first(tax, key, field="name"):
    v = tax.get(key) or []
    return v[0].get(field) if v else None


def slim(h):
    tax = h.get("taxonomies") or {}
    return {
        "id": h.get("web_id_meta"), "lot": h.get("lot_number_meta"), "title": h.get("post_title"),
        "year": first(tax, "lot_year"), "make": first(tax, "make"), "model": first(tax, "model"), "trim": first(tax, "trim_sub_model"),
        "type": first(tax, "lot_type"), "status": [t["name"] for t in tax.get("lot_status") or []],
        "auction": (first(tax, "auction_tax") or "").split("|")[0], "end": h.get("auction_end_date_meta"), "run_ts": first(tax, "run_date", "timestamp"),
        "price": h.get("hammer_price_meta"), "sold": 1 if h.get("sold") else 0, "bgo": 1 if h.get("bid_goes_on") else 0,
        "bid": h.get("current_bid_meta"), "engine": h.get("engine_configuration_meta"), "trans": h.get("transmission_type_meta"),
        "series": h.get("lot_series_meta"), "color": h.get("color_meta"), "url": h.get("permalink"),
    }


def page(filters):
    """All hits for a filter that is known to match <= 1000 lots."""
    d = query({"query": "", "hitsPerPage": 1000, "filters": filters, "attributesToRetrieve": ATTRS, "attributesToHighlight": [], "attributesToSnippet": []})
    return [slim(h) for h in d["hits"]]


def chunks_for(filters, count, depth=0):
    """Yield filter strings each matching <= 1000 lots, splitting by run day, lot type, then make."""
    if count <= 1000:
        yield filters; return
    splitter = ["taxonomies.run_date.timestamp", "taxonomies.lot_type.name", "taxonomies.make.name"][depth] if depth < 3 else None
    if not splitter:
        yield filters; return  # give up: take the first 1000 (rare)
    f = facet(filters, splitter)
    covered = 0
    for val, n in f.items():
        sub = f"{filters} AND {splitter}:{val if splitter.endswith('timestamp') else q(val)}"
        covered += n
        yield from chunks_for(sub, n, depth + 1)
    if covered < count:  # lots with no value for this facet
        rest = f"{filters}" + "".join(f" AND NOT {splitter}:{val if splitter.endswith('timestamp') else q(val)}" for val in f)
        yield from chunks_for(rest, count - covered, depth + 1)


if __name__ == "__main__":
    t0 = time.time()
    auctions = facet("", "taxonomies.auction_tax.name")
    print("auctions:", len(auctions), "lots:", sum(auctions.values()), flush=True)
    jobs = []
    for name, n in auctions.items():
        jobs.extend(chunks_for(f"taxonomies.auction_tax.name:{q(name)}", n))
    print("queries:", len(jobs), "in", round(time.time() - t0), "s", flush=True)
    seen = set(); written = 0
    with open(OUT, "w", encoding="utf-8") as out, ThreadPoolExecutor(8) as ex:
        for i, rows in enumerate(ex.map(page, jobs)):
            for r in rows:
                if r["id"] in seen: continue
                seen.add(r["id"]); out.write(json.dumps(r, ensure_ascii=False) + "\n"); written += 1
            if i % 50 == 0: print(f"  {i}/{len(jobs)} queries, {written} lots, {round(time.time() - t0)} s", flush=True)
    print("done:", written, "lots in", round(time.time() - t0), "s;", os.path.getsize(OUT) // 1_000_000, "MB", flush=True)
