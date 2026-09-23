"""Same-car history: for every lot whose VIN we hold, the earlier Mecum sales of that exact VIN -> prior_sales.json
{lot id: [{auction, end, price, sold, url}]}  (only sales that ended before the lot's own auction)."""
import json, glob, collections, re

corp = {}
for line in open("corpus.jsonl", encoding="utf-8"):
    r = json.loads(line); corp[r["id"]] = r
vin_of = {}
for lid, o in json.load(open("odo_cache.json")).items():
    if o and o.get("vin"): vin_of[lid] = o["vin"]
for d in glob.glob("data/*/details.json"):
    for lid, dd in json.load(open(d)).items():
        if dd.get("vinSerial"): vin_of[lid] = dd["vinSerial"]
norm = lambda v: re.sub(r"[^A-Z0-9]", "", (v or "").upper())
by_vin = collections.defaultdict(list)
for lid, v in vin_of.items():
    v = norm(v)
    # short or placeholder serials ("NONE", "1", "0000") would join unrelated cars
    if len(v) >= 6 and not re.fullmatch(r"0+|NONE|NA|TBD|UNKNOWN", v) and lid in corp: by_vin[v].append(corp[lid])
out = {}
for v, lots in by_vin.items():
    if len(lots) < 2: continue
    for r in lots:
        prev = [x for x in lots if x["id"] != r["id"] and (x["end"] or 0) < (r["end"] or 0) - 20 * 86400]
        if prev:
            out[r["id"]] = [{"auction": x["auction"], "end": x["end"], "price": x["price"], "sold": x["sold"], "lot": x["lot"],
                             "url": "https://www.mecum.com" + (x["url"] or "")} for x in sorted(prev, key=lambda x: -x["end"])]
json.dump(out, open("prior_sales.json", "w"))
print("lots with an earlier Mecum appearance of the same VIN:", len(out), "| of those previously SOLD:", sum(1 for v in out.values() if any(x["sold"] for x in v)))
