"""Pull every lot of one auction from Mecum's public Algolia index into ./lots.json.
The auction comes from ./auction.json (written by pipeline.py); run days are discovered from the index."""
import json, os, urllib.request

APP = "U6CFCQ7V52"
KEY = "0291c46cde807bcb428a021a96138fcb"
INDEX = "wp_posts_lot_sort_order_asc"
AUCTION = json.load(open("auction.json"))["facet"] if os.path.exists("auction.json") else "Nashville 2026|1790035200|1790380800"


def query(body):
    req = urllib.request.Request(
        f"https://{APP}-dsn.algolia.net/1/indexes/{INDEX}/query",
        data=json.dumps(body).encode(),
        headers={"x-algolia-application-id": APP, "x-algolia-api-key": KEY, "Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def first(tax, key, field="name"):
    v = tax.get(key) or []
    return v[0].get(field) if v else None


def slim(h):
    tax = h.get("taxonomies") or {}
    imgs = h.get("images_meta") or []
    return {
        "id": h.get("web_id_meta"),
        "lot": h.get("lot_number_meta"),
        "title": h.get("post_title"),
        "year": first(tax, "lot_year"),
        "make": first(tax, "make"),
        "model": first(tax, "model"),
        "trim": first(tax, "trim_sub_model"),
        "type": first(tax, "lot_type"),
        "status": [t["name"] for t in tax.get("lot_status") or []],
        "collection": (first(tax, "collection_tax") or "").split("|")[0] or None,
        "run_date": first(tax, "run_date"),
        "run_ts": first(tax, "run_date", "timestamp"),
        "sort": h.get("sort_order_meta"),
        "hammer": h.get("hammer_price_meta"),
        "sold": h.get("sold"),
        "bid_goes_on": h.get("bid_goes_on"),
        "current_bid": h.get("current_bid_meta"),
        "color": h.get("color_meta"),
        "engine": h.get("engine_configuration_meta") or h.get("engine_meta"),
        "trans": h.get("transmission_type_meta"),
        "img": imgs[0]["url"] if imgs else None,
        "url": "https://www.mecum.com" + (h.get("permalink") or ""),
    }


# run days come from the run_date facet; each day is well under Algolia's 1000-hit page
facets = query({"query": "", "hitsPerPage": 0, "filters": f'taxonomies.auction_tax.name:"{AUCTION}"',
                "facets": ["taxonomies.run_date.timestamp"], "maxValuesPerFacet": 50})
days = sorted(int(k) for k in (facets.get("facets", {}).get("taxonomies.run_date.timestamp") or {}))
lots = []
for ts in days:
    d = query({"query": "", "hitsPerPage": 1000, "attributesToHighlight": [], "attributesToSnippet": [],
               "filters": f'taxonomies.auction_tax.name:"{AUCTION}" AND taxonomies.run_date.timestamp:{ts}'})
    print(ts, d["nbHits"], len(d["hits"]))
    lots.extend(slim(h) for h in d["hits"])
# lots with no run day yet (early consignments) are still worth listing
d = query({"query": "", "hitsPerPage": 1000, "attributesToHighlight": [], "attributesToSnippet": [],
           "filters": f'taxonomies.auction_tax.name:"{AUCTION}"' + "".join(f" AND NOT taxonomies.run_date.timestamp:{ts}" for ts in days)})
if d["hits"]:
    print("undated", d["nbHits"]); lots.extend(slim(h) for h in d["hits"])

ids = [l["id"] for l in lots]
print("total", len(lots), "unique", len(set(ids)))
json.dump(lots, open("lots.json", "w"), indent=0)
