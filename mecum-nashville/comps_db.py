"""Price one auction's lots with the class-aware model over the local corpus -> ./comps.json.
Run inside data/<slug>/ (reads auction.json, lots.json, details.json there)."""
import json, os, re, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import price_model as PM

P = {**PM.DEFAULTS, **json.load(open(os.path.join(HERE, "model_params.json")))} if os.path.exists(os.path.join(HERE, "model_params.json")) else PM.DEFAULTS
auction = json.load(open("auction.json")); lots = json.load(open("lots.json"))
details = json.load(open("details.json")) if os.path.exists("details.json") else {}
fam = PM.load(os.path.join(HERE, "classified.jsonl"))
# the classified record for each lot of this auction (the corpus holds every lot, sold or not)
want = {l["id"] for l in lots}; cls = {}
for line in open(os.path.join(HERE, "classified.jsonl"), encoding="utf-8"):
    r = json.loads(line)
    if r["id"] in want: cls[r["id"]] = r

out = {}
for l in lots:
    t = cls.get(l["id"])
    if not t or l["type"] not in ("Auto", "Motorcycle", "Tractor", "Trailer"): continue
    o = re.sub(r"[^\d]", "", (details.get(l["id"]) or {}).get("odometer") or "")
    if o: t = {**t, "miles": int(o)}
    e = PM.estimate(t, auction["start"], P, fam)
    if not e: out[l["id"]] = {"tier": "no comps", "n": 0}; continue
    notes = []
    if e["eff"] < 4: notes.append(f"only {e['eff']:.0f} effective comps — treat as a rough guess")
    if t["mod"] == "custom": notes.append("custom build — comps range widely and sales often land well below build cost")
    if t["mod"] == "replica": notes.append("replica/tribute — priced against other replicas")
    cls_desc = " · ".join(x for x in [t["gen"] if t["gen"] and not str(t["gen"]).isdigit() else None, t["trim"] or "base", t["body"], t["mod"] if t["mod"] != "stock" else None] if x)
    out[l["id"]] = {"tier": f"{cls_desc} · {e['tier']}", "n": e["n"], "grade": t["grade"], "median": e["median"], "p25": e["p25"], "p75": e["p75"],
                    "lo": e["lo"], "hi": e["hi"], "note": "; ".join(notes) or None,
                    "recent": [{"title": c["title"], "price": c["price"], "miles": c.get("miles"), "auction": c["auction"],
                                "url": "https://www.mecum.com" + (c.get("url") or ""), "w": round(w / e["top"][0][1], 2)} for c, w in e["top"]]}
json.dump(out, open("comps.json", "w"))
print(auction["name"], ":", sum(1 for v in out.values() if v.get("n")), "priced of", len(out))
