"""Fetch odometer + VIN from Mecum lot pages for every id in odo_todo.json -> merged into odo_cache.json.
Resumable: ids already in the cache are skipped; the cache is saved every 500 pages."""
import json, re, subprocess, time, os
from concurrent.futures import ThreadPoolExecutor

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128"
odo = json.load(open("odo_cache.json")) if os.path.exists("odo_cache.json") else {}
todo = [(i, u) for i, u in json.load(open("odo_todo.json")) if i not in odo]


def get(item):
    wid, url = item
    for a in range(3):
        r = subprocess.run(["curl", "-sL", "--max-time", "40", "-A", UA, url], capture_output=True)
        page = r.stdout.decode("utf-8", "ignore")
        if r.returncode == 0 and len(page) > 20000: break
        time.sleep(2 * (a + 1))
    else:
        return wid, None
    f = lambda k: (re.search(r'\\"' + k + r'\\":\\"([^"\\]*)\\"', page) or [None, None])[1]
    d = re.sub(r"[^\d]", "", f("odometer") or "")
    return wid, {"mi": int(d) if d else None, "u": f("odometerUnits"), "since": f("odometerMileageSince"), "vin": f("vinSerial")}


t0 = time.time(); print("to fetch:", len(todo), flush=True)
with ThreadPoolExecutor(12) as ex:
    for i, (wid, d) in enumerate(ex.map(get, todo)):
        if d: odo[wid] = d
        if i % 500 == 0:
            json.dump(odo, open("odo_cache.json", "w")); print(i, round(time.time() - t0), "s", flush=True)
json.dump(odo, open("odo_cache.json", "w"))
print("done:", len(odo), "cached;", sum(1 for v in odo.values() if v and v.get("mi")), "with miles; in", round(time.time() - t0), "s", flush=True)
