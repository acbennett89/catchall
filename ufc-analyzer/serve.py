"""UFC fight analyzer: local server.

Serves the app from web/ and a small JSON API that pulls live data from ESPN (cards, live status,
fighter history), UFCStats (career stats) and BestFightOdds (Caesars and every other book's lines):

    /api/events?season=2026        UFC events on ESPN's calendar
    /api/event/<id>                the card with live status (refresh every ~15s while live)
    /api/odds/<id>                 per fight: all books, no-vig fair price, Caesars edge, props, movement
    /api/fighter/<id>?before=<ts>  bio, career stats, record breakdown and last five fights before <ts>
    /api/predict/<id>              model win/method/round probabilities per fight, with model edge at Caesars
    /api/ledger[/add|/remove]      forward record of flagged and placed bets, settled with CLV and results
    /api/ratings/<event id>        KenPom-style power ratings model: per-fight prediction and rating cards
    /api/leaderboard?div=          ranked active fighters by division

    python serve.py            # http://localhost:8766  and  http://<this-pc-ip>:8766 from your phone
    python serve.py --open     # same, and open it in the browser
"""
import json, os, socket, sys, threading, time, traceback, urllib.parse, webbrowser
from concurrent.futures import ThreadPoolExecutor
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import espn, fighters, ledger, market, modelapi, ratingsapi  # noqa: E402

ARGS = [a for a in sys.argv[1:] if not a.startswith("--")]
PORT = int(ARGS[0]) if ARGS else 8766
WEB = os.path.join(HERE, "web")
warm_pool = ThreadPoolExecutor(6)
warmed = {}  # event id -> last warm-up time
warm_lock = threading.Lock()


def warm(event_id, card):
    """Prefetch every fighter on the card (and the odds) so clicking through fights is instant."""
    with warm_lock:
        if time.time() - warmed.get(event_id, 0) < 900:
            return
        warmed[event_id] = time.time()
    warm_pool.submit(_quiet, market.card_odds, event_id)
    if modelapi.available():
        warm_pool.submit(_quiet, predictions, event_id)
    if ratingsapi.available():
        warm_pool.submit(_quiet, ratingsapi.predictions, event_id)
    for f in card["fights"]:
        for x in f["fighters"]:
            warm_pool.submit(_quiet, fighters.build, x["id"], card["date"], x["name"])


def _quiet(fn, *a):
    try:
        fn(*a)
    except Exception as e:
        print(time.strftime("%H:%M:%S"), f"warm-up {fn.__module__}.{fn.__name__}{a[:1]} failed: {e}", flush=True)


def predictions(event_id):
    try:
        odds = market.card_odds(event_id)
    except Exception:
        odds = None
    return modelapi.predictions(event_id, odds)


def keep_model_current():
    """Top up the fight history with newly completed events (UFCStats), then rebuild fighter states."""
    from model import predict as model_predict, scrape as model_scrape
    while True:
        try:
            added = model_scrape.update()
            if added and added[1]:
                model_predict.reload()
                try:
                    from ratings import predict as ratings_predict, rounds as ratings_rounds
                    ratings_rounds.update()
                    ratings_predict.reload()
                except Exception as e:
                    print(time.strftime("%H:%M:%S"), f"ratings: round top-up failed ({e})", flush=True)
                print(time.strftime("%H:%M:%S"), f"model: added {added[1]} fights from {added[0]} new events", flush=True)
        except Exception as e:
            print(time.strftime("%H:%M:%S"), f"model: history update failed ({e}); using what's on disk", flush=True)
        time.sleep(6 * 3600)


def watch_prices():
    """Keep prices (and model flags) current for upcoming cards and cards with open ledger entries, even
    with no page open, so the ledger sees closing prices: every 2 minutes within two days of a card,
    every 15 minutes before that."""
    last = {}
    while True:
        try:
            now = time.time()
            watch = {}
            for e in espn.events():
                if e.get("start") and now - 12 * 3600 < e["start"] < now + 8 * 86400 and "contender" not in (e.get("name") or "").lower():
                    watch[str(e["id"])] = e["start"]
            for e in ledger.open_events():
                watch.setdefault(str(e["event"]), e.get("eventDate") or now)
            for eid, date in watch.items():
                gap = 120 if date - now < 2 * 86400 else 900
                if now - last.get(eid, 0) >= gap:
                    last[eid] = now
                    _quiet(predictions if modelapi.available() else market.card_odds, eid)
        except Exception as e:
            print(time.strftime("%H:%M:%S"), f"price watch failed: {e}", flush=True)
        time.sleep(60)


def api(path, q):
    parts = path.strip("/").split("/")
    if parts[:2] == ["api", "events"]:
        season = q.get("season", [None])[0]
        evs = espn.events(int(season) if season else None)
        return {"events": evs, "season": season, "now": time.time()}
    if parts[:2] == ["api", "event"] and len(parts) == 3:
        card = espn.card(parts[2])
        warm(parts[2], card)
        return dict(card, now=time.time())
    if parts[:2] == ["api", "odds"] and len(parts) == 3:
        return market.card_odds(parts[2])
    if parts[:2] == ["api", "fighter"] and len(parts) == 3:
        before = q.get("before", [None])[0]
        return fighters.build(parts[2], float(before) if before else None, q.get("name", [None])[0])
    if parts[:2] == ["api", "predict"] and len(parts) == 3:
        return predictions(parts[2])
    if parts[:2] == ["api", "ratings"] and len(parts) == 3:
        return ratingsapi.predictions(parts[2])
    if parts[:2] == ["api", "leaderboard"]:
        return ratingsapi.leaderboard(q.get("div", [None])[0], int(q.get("top", ["25"])[0]))
    if parts[:2] == ["api", "ledger"]:
        if len(parts) == 3 and parts[2] == "add":
            g = lambda k: q.get(k, [None])[0]
            card = espn.card(g("event"))
            f = next((x for x in card["fights"] if x["id"] == g("fight")), None)
            if not f:
                return {"error": "fight not found"}
            pred = (predictions(g("event")).get("fights") or {}).get(f["id"]) or {}
            dec = pred.get("decision") or {}
            e = ledger.record(g("event"), card, f, dec, pred, source="user", price=int(float(g("price"))),
                              stake=float(g("stake")) if g("stake") else None, side=int(g("side")))
            return {"ok": bool(e), "entry": e}
        if len(parts) == 3 and parts[2] == "remove":
            return {"ok": ledger.remove(q.get("id", [""])[0])}
        return ledger.report(market.history)
    if parts[:2] == ["api", "health"]:
        return {"ok": True, "now": time.time()}
    return None


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *a, **k):
        super().__init__(*a, directory=WEB, **k)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        url = urllib.parse.urlparse(self.path)
        if not url.path.startswith("/api/"):
            return super().do_GET()
        try:
            body = api(url.path, urllib.parse.parse_qs(url.query))
            if body is None:
                return self.send_error(404)
            code = 200
        except Exception as e:
            traceback.print_exc()
            body, code = {"error": f"{type(e).__name__}: {e}"}, 502
        data = json.dumps(body, separators=(",", ":")).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def log_message(self, fmt, *args):
        if args and str(args[1])[:1] in "45":
            super().log_message(fmt, *args)


def lan_ip():
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except Exception:
        return None


if __name__ == "__main__":
    for stream in (sys.stdout, sys.stderr):  # fighter names with accents on a Windows console
        try:
            stream.reconfigure(errors="replace")
        except Exception:
            pass
    srv = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    srv.daemon_threads = True
    print(f"UFC fight analyzer running:  http://localhost:{PORT}", flush=True)
    ip = lan_ip()
    if ip:
        print(f"On your phone (same Wi-Fi):  http://{ip}:{PORT}", flush=True)
    if modelapi.available() and "--no-update" not in sys.argv:
        threading.Thread(target=keep_model_current, daemon=True).start()
    if "--no-watch" not in sys.argv:
        threading.Thread(target=watch_prices, daemon=True).start()
    if "--open" in sys.argv:
        threading.Timer(0.8, webbrowser.open, [f"http://localhost:{PORT}"]).start()
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
