"""Local server for the block sheets.

Serves out/ (one page per auction plus thumbnail sidecars) and keeps sale results fresh:
auctions that are running now are re-pulled from Mecum's index every REFRESH_SECONDS; any other
auction is pulled on first request and cached for a while. Pages poll /results/<slug>.json.

    python serve.py            # http://localhost:8765  and  http://<this-pc-ip>:8765
"""
import json, os, socket, sys, threading, time, urllib.request
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

PORT = int(sys.argv[1]) if len(sys.argv) > 1 else 8765
REFRESH_SECONDS, STALE_SECONDS = 30, 600
HERE = os.path.dirname(os.path.abspath(__file__))
DATA, OUT = os.path.join(HERE, "data"), os.path.join(HERE, "out")
APP, KEY, INDEX = "U6CFCQ7V52", "0291c46cde807bcb428a021a96138fcb", "wp_posts_lot_sort_order_asc"

lock = threading.Lock()
results = {}   # slug -> {"doc": {...}, "at": epoch}


def auctions():
    out = {}
    for s in os.listdir(DATA) if os.path.isdir(DATA) else []:
        p = os.path.join(DATA, s, "auction.json")
        if os.path.exists(p): out[s] = json.load(open(p))
    return out


def live(a, now=None):
    now = now or time.time()
    return a["start"] - 86400 <= now <= a["end"] + 2 * 86400


def pull(a):
    def q(body):
        req = urllib.request.Request(f"https://{APP}-dsn.algolia.net/1/indexes/{INDEX}/query", data=json.dumps(body).encode(),
                                     headers={"x-algolia-application-id": APP, "x-algolia-api-key": KEY, "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r: return json.load(r)
    f = q({"query": "", "hitsPerPage": 0, "filters": f'taxonomies.auction_tax.name:"{a["facet"]}"', "facets": ["taxonomies.run_date.timestamp"], "maxValuesPerFacet": 50})
    days = sorted(int(k) for k in (f.get("facets", {}).get("taxonomies.run_date.timestamp") or {}))
    m = {}
    for ts in days:
        d = q({"query": "", "hitsPerPage": 1000, "filters": f'taxonomies.auction_tax.name:"{a["facet"]}" AND taxonomies.run_date.timestamp:{ts}',
               "attributesToRetrieve": ["web_id_meta", "hammer_price_meta", "sold", "bid_goes_on", "current_bid_meta"], "attributesToHighlight": [], "attributesToSnippet": []})
        for h in d["hits"]:
            cb = h.get("current_bid_meta")
            m[h["web_id_meta"]] = {"h": h.get("hammer_price_meta"), "s": 1 if h.get("sold") else 0, "b": 1 if h.get("bid_goes_on") else 0, "c": cb if cb and cb > 0 else None}
    return {"map": m, "at": int(time.time() * 1000)}


def refresh(slug, a):
    try:
        doc = pull(a)
        with lock: results[slug] = {"doc": doc, "at": time.time()}
        sold = sum(1 for v in doc["map"].values() if v["s"]); bgo = sum(1 for v in doc["map"].values() if v["b"])
        print(time.strftime("%H:%M:%S"), f"{slug}: {sold} sold, {bgo} bid-goes-on", flush=True)
    except Exception as e:
        print(time.strftime("%H:%M:%S"), f"{slug}: pull failed: {e}", flush=True)


def refresher():
    while True:
        for slug, a in auctions().items():
            if live(a): refresh(slug, a)
        time.sleep(REFRESH_SECONDS)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=OUT, **k)

    def do_GET(self):
        path = self.path.split("?")[0]
        if path.startswith("/results/") and path.endswith(".json"):
            slug = path[len("/results/"):-5]; a = auctions().get(slug)
            if not a: return self.send_error(404)
            with lock: r = results.get(slug)
            if not r or (not live(a) and time.time() - r["at"] > STALE_SECONDS):
                refresh(slug, a)
                with lock: r = results.get(slug)
            body = json.dumps(r["doc"] if r else {"error": "no data"}).encode()
            self.send_response(200 if r else 503)
            self.send_header("Content-Type", "application/json"); self.send_header("Cache-Control", "no-store"); self.send_header("Content-Length", str(len(body)))
            self.end_headers(); self.wfile.write(body); return
        if path == "/": self.path = "/index.html"
        return super().do_GET()

    def guess_type(self, path):
        t = super().guess_type(path)
        return t + "; charset=utf-8" if t.startswith("text/") else t

    def log_message(self, fmt, *args):
        if args and ("results/" in args[0] or "thumbs/" in args[0]): return
        super().log_message(fmt, *args)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM); s.connect(("8.8.8.8", 80)); ip = s.getsockname()[0]; s.close(); return ip
    except Exception:
        return "?"


if __name__ == "__main__":
    threading.Thread(target=refresher, daemon=True).start()
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Block sheets: http://localhost:{PORT}/   phone on same Wi-Fi: http://{lan_ip()}:{PORT}/   auctions: {', '.join(sorted(auctions()))}", flush=True)
    srv.serve_forever()
