"""HTTP fetching and caching shared by the data sources.

fetch() is a small urllib wrapper (browser UA, gzip, retries).  cached() memoizes a function result
for a TTL, with one fetch in flight per key so a page of parallel requests doesn't stampede a source.
Long-lived results (fighter pages, name matches) can also be persisted to cache/ on disk so a server
restart on fight night doesn't refetch every fighter.
"""
import gzip, json, os, threading, time, urllib.error, urllib.request, zlib

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE_DIR = os.path.join(HERE, "cache")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def fetch(url, data=None, headers=None, opener=None, timeout=25, retries=2):
    """GET (or POST when data is given) and return the decoded body as str."""
    h = {"User-Agent": UA, "Accept-Encoding": "gzip, deflate", "Accept-Language": "en-US,en;q=0.9"}
    h.update(headers or {})
    last = None
    for attempt in range(retries + 1):
        try:
            req = urllib.request.Request(url, data=data, headers=h)
            with (opener.open(req, timeout=timeout) if opener else urllib.request.urlopen(req, timeout=timeout)) as r:
                raw = r.read()
                enc = (r.headers.get("Content-Encoding") or "").lower()
                charset = r.headers.get_content_charset() or "utf-8"
            if enc == "gzip":
                raw = gzip.decompress(raw)
            elif enc == "deflate":
                raw = zlib.decompress(raw)
            return raw.decode(charset, "replace")
        except urllib.error.HTTPError as e:
            if e.code in (400, 401, 403, 404, 410):
                raise
            last = e
        except Exception as e:  # network blips, timeouts
            last = e
        time.sleep(0.6 * (attempt + 1))
    raise last


def fetch_json(url, **kw):
    return json.loads(fetch(url, headers={"Accept": "application/json"}, **kw))


class TTLCache:
    def __init__(self):
        self._lock = threading.Lock()
        self._data = {}      # key -> (expires_at, value)
        self._inflight = {}  # key -> Event

    def get(self, key, loader, ttl, stale_ok=True):
        """Return a cached value or call loader().  If the loader fails and a stale value exists, return it."""
        while True:
            with self._lock:
                hit = self._data.get(key)
                if hit and hit[0] > time.time():
                    return hit[1]
                ev = self._inflight.get(key)
                if ev is None:
                    ev = self._inflight[key] = threading.Event()
                    owner = True
                else:
                    owner = False
            if not owner:
                ev.wait(60)
                with self._lock:
                    hit = self._data.get(key)
                if hit:
                    return hit[1]
                continue  # owner failed with nothing cached; try ourselves
            try:
                value = loader()
                t = ttl(value) if callable(ttl) else ttl
                with self._lock:
                    self._data[key] = (time.time() + t, value)
                return value
            except Exception:
                if stale_ok and hit:
                    return hit[1]
                raise
            finally:
                with self._lock:
                    self._inflight.pop(key, None)
                ev.set()

    def drop(self, key):
        with self._lock:
            self._data.pop(key, None)


cache = TTLCache()


class DiskStore:
    """A JSON dict persisted under cache/<name>.json, written atomically and throttled."""

    def __init__(self, name):
        self.path = os.path.join(CACHE_DIR, name + ".json")
        self._lock = threading.Lock()
        self._dirty_since = None
        try:
            with open(self.path, encoding="utf-8") as f:
                self.data = json.load(f)
        except Exception:
            self.data = {}

    def get(self, key, max_age=None):
        with self._lock:
            v = self.data.get(key)
        if v is None:
            return None
        if max_age is not None and time.time() - v.get("_at", 0) > max_age:
            return None
        return v.get("v")

    def put(self, key, value):
        with self._lock:
            self.data[key] = {"v": value, "_at": time.time()}
            if self._dirty_since is None:
                self._dirty_since = time.time()
        self.flush(force=False)

    def flush(self, force=True):
        with self._lock:
            if self._dirty_since is None or (not force and time.time() - self._dirty_since < 5):
                return
            snapshot = json.dumps(self.data, separators=(",", ":"))
            self._dirty_since = None
        os.makedirs(CACHE_DIR, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as f:
            f.write(snapshot)
        os.replace(tmp, self.path)
