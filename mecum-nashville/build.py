"""Build out/<slug>.html (+ out/thumbs/<slug>.json) from data/<slug>/, embedding the list of every built auction
so the page's selector can switch between them.  python build.py <slug>"""
import json, os, re, sys, datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DATA, OUT = os.path.join(HERE, "data"), os.path.join(HERE, "out")
CURRENT = "nashville-2026"
slug = sys.argv[1] if len(sys.argv) > 1 else CURRENT
d = os.path.join(DATA, slug)


def load(name, default):
    p = os.path.join(d, name)
    return json.load(open(p)) if os.path.exists(p) else default


auction = load("auction.json", {"slug": slug, "name": slug, "start": 0, "end": 0})
lots = load("lots.json", [])
comps = load("comps.json", {})
thumbs = load("thumbs.json", {})
details = load("details.json", {})

for l in lots:
    l.pop("img", None)
    dd = details.get(l["id"]) or {}
    if dd.get("error"): continue
    odo = dd.get("odometer")
    l["miles"] = int(re.sub(r"[^\d]", "", odo)) if odo and re.sub(r"[^\d]", "", odo) else None
    l["miles_units"] = dd.get("odometerUnits") or None
    l["miles_since"] = dd.get("odometerMileageSince") or None
    l["actual_miles"] = bool(dd.get("isActualMiles"))
    if dd.get("transmission"): l["trans_detail"] = dd["transmission"]
    if dd.get("highlights"): l["highlights"] = dd["highlights"]
    if dd.get("vinSerial"): l["vin"] = dd["vinSerial"]
for c in comps.values():
    if c: c.pop("error", None)
# same-VIN history: earlier Mecum appearances of this exact car
pp = os.path.join(HERE, "prior_sales.json")
prior = json.load(open(pp)) if os.path.exists(pp) else {}
for l in lots:
    ps = [p for p in prior.get(l["id"], []) if (p["end"] or 0) < auction.get("start", 0)]
    if ps: l["prior"] = [{k: p[k] for k in ("auction", "price", "sold", "url")} for p in ps[:4]]

# every auction with data, for the selector
manifest = []
for s in sorted(os.listdir(DATA)):
    ap = os.path.join(DATA, s, "auction.json"); lp = os.path.join(DATA, s, "lots.json")
    if os.path.exists(ap) and os.path.exists(lp):
        a = json.load(open(ap)); n = len(json.load(open(lp)))
        manifest.append({"slug": s, "name": a["name"], "start": a["start"], "end": a["end"], "lots": n})
manifest.sort(key=lambda a: a["start"])

days = sorted({l["run_date"] for l in lots if l.get("run_date")})
data = {
    "auction": {"slug": slug, "name": auction["name"], "facet": auction.get("facet"), "start": auction["start"], "end": auction["end"]},
    "auctions": manifest,
    "days": days,
    "cond": json.load(open(os.path.join(HERE, "condition_params.json"))) if os.path.exists(os.path.join(HERE, "condition_params.json")) else {},
    "built": datetime.datetime.now().strftime("%a %b %d, %I:%M %p"),
    "builtTs": int(datetime.datetime.now().timestamp() * 1000),
    "lots": lots,
    "comps": {k: v for k, v in comps.items() if v},
}
payload = json.dumps(data, separators=(",", ":")).replace("</", "<\\/")
tpl = open(os.path.join(HERE, "template.html"), encoding="utf-8").read()
html = tpl.replace("/*__DATA__*/{}", payload)
os.makedirs(os.path.join(OUT, "thumbs"), exist_ok=True)
open(os.path.join(OUT, f"{slug}.html"), "w", encoding="utf-8").write(html)
json.dump({k: v for k, v in thumbs.items() if v}, open(os.path.join(OUT, "thumbs", f"{slug}.json"), "w"), separators=(",", ":"))
if slug == CURRENT:
    open(os.path.join(OUT, "index.html"), "w", encoding="utf-8").write(html)
print(f"{slug}: {len(lots)} lots, page {round(len(html.encode()) / 1e6, 2)} MB, thumbs {sum(1 for v in thumbs.values() if v)}")
