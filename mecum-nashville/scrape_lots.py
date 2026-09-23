"""Fetch each vehicle lot's detail page and pull the fields the search index lacks:
odometer, transmission (detailed), VIN, estimates, and the highlight bullets -> details.json"""
import json, re, subprocess, time, html
from concurrent.futures import ThreadPoolExecutor

lots = [l for l in json.load(open("lots.json")) if l["type"] in ("Auto", "Motorcycle", "Tractor", "Trailer")]
FIELDS = ["odometer", "odometerUnits", "odometerMileageSince", "isActualMiles", "transmission", "lowEstimate", "highEstimate", "vinSerial", "engine"]


def field(page, name):
    m = re.search(r'\\"' + name + r'\\":\\"((?:[^"\\]|\\\\.)*)\\"', page)
    return html.unescape(m.group(1).replace('\\\\"', '"')) if m and m.group(1) else None


def scrape(l):
    for attempt in range(3):
        r = subprocess.run(["curl", "-sL", "--max-time", "40", "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/128", l["url"]],
                           capture_output=True)
        page = r.stdout.decode("utf-8", "ignore")
        if r.returncode == 0 and len(page) > 20000:
            break
        time.sleep(2 * (attempt + 1))
    else:
        return l["id"], {"error": "fetch failed"}
    d = {k: field(page, k) for k in FIELDS}
    # highlight bullets: plain-text <li> items (nav items contain links, so they are skipped)
    d["highlights"] = [html.unescape(re.sub(r"<[^>]+>", "", x)).strip() for x in re.findall(r"<li>([^<]{4,200})</li>", page)][:10]
    return l["id"], d


t0 = time.time(); out = {}
with ThreadPoolExecutor(12) as ex:
    for i, (lid, d) in enumerate(ex.map(scrape, lots)):
        out[lid] = d
        if i % 100 == 0:
            print(i, round(time.time() - t0), "s", flush=True)
json.dump(out, open("details.json", "w"))
ok = [d for d in out.values() if "error" not in d]
print("done", len(out), "errors", len(out) - len(ok), "with odometer", sum(1 for d in ok if d.get("odometer")),
      "with transmission", sum(1 for d in ok if d.get("transmission")), "with highlights", sum(1 for d in ok if d.get("highlights")),
      "with estimate", sum(1 for d in ok if d.get("lowEstimate")), "in", round(time.time() - t0), "s")
