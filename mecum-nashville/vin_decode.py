"""Decode every 17-character VIN we hold (comp lot pages in odo_cache.json + each auction's details.json)
through NHTSA's free vPIC batch API -> vin_cache.json {lot id: {body, drive, trim, series, disp, hp, doors}}.
50 VINs per request, one request per second. Resumable."""
import json, glob, os, re, time, urllib.request, urllib.parse

OUT = "vin_cache.json"
cache = json.load(open(OUT)) if os.path.exists(OUT) else {}
vins = {}
for lid, o in (json.load(open("odo_cache.json")) if os.path.exists("odo_cache.json") else {}).items():
    if o and o.get("vin"): vins[lid] = o["vin"]
for d in glob.glob("data/*/details.json"):
    for lid, dd in json.load(open(d)).items():
        if dd.get("vinSerial"): vins[lid] = dd["vinSerial"]
todo = [(lid, v.strip().upper()) for lid, v in vins.items() if lid not in cache and re.fullmatch(r"[A-HJ-NPR-Z0-9]{17}", (v or "").strip().upper())]
print("VINs to decode:", len(todo), flush=True)
t0 = time.time()
for i in range(0, len(todo), 50):
    chunk = todo[i:i + 50]
    body = urllib.parse.urlencode({"format": "json", "data": ";".join(v for _, v in chunk)}).encode()
    for a in range(4):
        try:
            res = json.load(urllib.request.urlopen(urllib.request.Request("https://vpic.nhtsa.dot.gov/api/vehicles/DecodeVINValuesBatch/", data=body), timeout=90))["Results"]; break
        except Exception:
            time.sleep(5 * (a + 1)); res = []
    for (lid, _), r in zip(chunk, res):
        if not r.get("ErrorCode", "").startswith("0"): cache[lid] = None; continue
        cache[lid] = {"body": r.get("BodyClass") or None, "drive": r.get("DriveType") or None, "trim": r.get("Trim") or None, "series": r.get("Series") or None,
                      "disp": r.get("DisplacementL") or None, "hp": r.get("EngineHP") or None, "doors": r.get("Doors") or None}
    if (i // 50) % 20 == 0:
        json.dump(cache, open(OUT, "w")); print(i, "decoded", round(time.time() - t0), "s", flush=True)
    time.sleep(1)
json.dump(cache, open(OUT, "w"))
print("done:", sum(1 for v in cache.values() if v), "clean decodes of", len(cache), "in", round(time.time() - t0), "s")
