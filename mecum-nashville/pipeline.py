"""Build the block sheet for one or more Mecum auctions.

    python pipeline.py nashville-2026 dallas-fort-worth-2026 ...   # fetch + comp + scrape + thumbs, then build every page
    python pipeline.py --build-only                                 # just regenerate the pages from data/

Each auction gets data/<slug>/ (lots, details, comps, thumbs) and out/<slug>.html; out/index.html is the
auction named in CURRENT. The steps are the existing scripts, run inside the auction's data directory.

Before adding a new auction, refresh the corpus so its lots are classified:  python corpus.py && python classify.py"""
import json, os, re, subprocess, sys, time, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
DATA, OUT = os.path.join(HERE, "data"), os.path.join(HERE, "out")
CURRENT = "nashville-2026"
APP, KEY = "U6CFCQ7V52", "0291c46cde807bcb428a021a96138fcb"


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def auctions():
    """Every auction in Mecum's index: {slug: {name, facet, start, end, count}}."""
    req = urllib.request.Request(f"https://{APP}-dsn.algolia.net/1/indexes/wp_posts_lot_sort_order_asc/query",
                                 data=json.dumps({"query": "", "hitsPerPage": 0, "facets": ["taxonomies.auction_tax.name"], "maxValuesPerFacet": 1000}).encode(),
                                 headers={"x-algolia-application-id": APP, "x-algolia-api-key": KEY, "Content-Type": "application/json"})
    f = json.load(urllib.request.urlopen(req, timeout=60))["facets"]["taxonomies.auction_tax.name"]
    out = {}
    for k, n in f.items():
        p = k.split("|")
        if len(p) != 3: continue
        out[slugify(p[0])] = {"name": p[0], "facet": k, "start": int(p[1]), "end": int(p[2]), "count": n}
    return out


def run(step, cwd):
    print(f"  [{os.path.basename(cwd)}] {step}", flush=True); t0 = time.time()
    r = subprocess.run([sys.executable, os.path.join(HERE, step)], cwd=cwd)
    print(f"  [{os.path.basename(cwd)}] {step} -> exit {r.returncode} in {round(time.time() - t0)} s", flush=True)
    if r.returncode: raise SystemExit(f"{step} failed for {cwd}")


def prepare(slug):
    a = auctions().get(slug)
    if not a: raise SystemExit(f"unknown auction slug {slug!r}; known: {', '.join(sorted(auctions()))}")
    d = os.path.join(DATA, slug); os.makedirs(d, exist_ok=True)
    json.dump({"slug": slug, **a}, open(os.path.join(d, "auction.json"), "w"))
    return d


if __name__ == "__main__":
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    for slug in args:
        d = prepare(slug)
        run("fetch_lots.py", d)
        run("scrape_lots.py", d)
        run("comps_db.py", d)   # class-aware comps; refresh corpus.py + classify.py first so new lots are in the corpus
        run("thumbs.py", d)
    # rebuild every auction that has data, so each page's selector knows about all the others
    built = [s for s in sorted(os.listdir(DATA)) if os.path.exists(os.path.join(DATA, s, "lots.json"))]
    os.makedirs(OUT, exist_ok=True)
    for s in built:
        r = subprocess.run([sys.executable, os.path.join(HERE, "build.py"), s], cwd=HERE)
        if r.returncode: raise SystemExit(f"build failed for {s}")
    print("built:", ", ".join(built))
