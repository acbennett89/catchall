"""Turn wiki_raw.json into taxonomy additions -> taxonomy.json (hand-written entries are never overwritten).

Generations: start years from each generation infobox (model_years preferred over production), summary boxes
spanning 20+ years dropped, boundaries kept only inside the years Mecum actually sells for that family.
Trims: multi-word trim names from article headings/bold text become single tokens ("super bee" -> "superbee"),
but only when that phrase appears in 3+ Mecum titles of the family — Wikipedia proposes, Mecum confirms."""
import json, re, collections

tax = json.load(open("taxonomy.json", encoding="utf-8"))
raw = json.load(open("wiki_raw.json", encoding="utf-8"))
rows = [json.loads(l) for l in open("classified.jsonl", encoding="utf-8")]
by_fam = collections.defaultdict(list)
for r in rows:
    if r["type"] == "Auto": by_fam[r["family"]].append(r)
key = lambda s: re.sub(r"[^a-z0-9]", "", s.lower())
have = {(key(k.split("|")[0]), key(k.split("|")[1])) for k in tax["generations"]}
report = {"added_generations": {}, "skipped": {}, "phrases": {}}

for fam, rec in raw.items():
    mk, md = fam.split("|", 1)
    lots = by_fam.get(fam, [])
    yrs = sorted(r["year"] for r in lots if r["year"])
    if not yrs: continue
    lo, hi = yrs[int(len(yrs) * .01)], yrs[int(len(yrs) * .99) - 1] if len(yrs) > 1 else yrs[0]
    boxes = list(rec["infoboxes"]) + [b for s in rec["subarticles"].values() for b in s["infoboxes"]]
    spans = []
    for b in boxes:
        r_ = b.get("model_years") or b.get("production")
        if r_ and r_[1] - r_[0] <= 20: spans.append((r_[0], r_[1], b.get("name") or ""))
    starts = sorted({a for a, _, _ in spans if lo - 1 <= a <= hi})
    # a "generation" shorter than 2 years is an overlapping variant box (HD trucks, facelifts): fold it into its neighbor
    merged = []
    for a in starts:
        if merged and a - merged[-1] < 2: continue
        merged.append(a)
    starts = merged
    if (key(mk), key(md)) not in have:
        if len(starts) >= 2:
            gens = []
            for i, a in enumerate(starts):
                b = starts[i + 1] - 1 if i + 1 < len(starts) else max(hi, max(e for _, e, _ in spans))
                name = next((n for s, _, n in spans if s == a and n), f"{a}")
                gens.append([f"{a}-{b if b < 2030 else ''} ({name[:28]})".replace("-) ", ") "), a, b])
            gens[0][1] = min(gens[0][1], yrs[0])  # early cars before the first documented generation join it
            # a "generation" longer than 15 years is a nameplate history, not a generation: drop it (those years use the ±3-year window)
            gens = [g for g in gens if g[2] - g[1] <= 15]
            if len(gens) >= 1:
                tax["generations"][fam] = gens; report["added_generations"][fam] = [(g[1], g[2]) for g in gens]
        else:
            report["skipped"][fam] = f"{len(starts)} usable generation starts ({rec.get('title')})"
    # phrases
    cand = set()
    for t in rec["heads"] + rec["bold"] + [x for s in rec["subarticles"].values() for x in s["heads"] + s["bold"]]:
        t = re.sub(r"[^A-Za-z0-9/ ]", " ", t).strip().lower()
        w = t.split()
        # a phrase built from make/model words is a name, not a trim ("mercedes benz", "cj 7", "austin healey")
        name_words = set(re.split(r"[^a-z0-9]+", (mk + " " + md).lower())) | {"mercedes", "benz", "austin", "healey", "dmc", "cj", "land", "rover", "rolls", "royce", "alfa", "romeo", "aston", "martin"}
        if any(x in name_words for x in w): continue
        if 2 <= len(w) <= 3 and not any(x in {"the", "and", "of", "in", "for", "model", "year", "generation", "history", "production", "engine", "design"} or x in tax["body"] for x in w) \
                and not all(len(x) <= 1 or x.isdigit() for x in w):
            cand.add(" ".join(w))
    titles = [" " + re.sub(r"[^a-z0-9/ ]", " ", (r["title"] or "").lower()) + " " for r in lots]
    for p in cand:
        n = sum(1 for t in titles if f" {p} " in t)
        if n >= 3 and p not in tax["phrases"]:
            tax["phrases"][p] = p.replace(" ", "").replace("/", ""); report["phrases"][p] = n

json.dump(tax, open("taxonomy.json", "w", encoding="utf-8"), indent=1, ensure_ascii=False)
json.dump(report, open("wiki_report.json", "w"), indent=1)
print("generation tables added:", len(report["added_generations"]), "| skipped:", len(report["skipped"]), "| trim phrases added:", len(report["phrases"]))
for f, g in list(report["added_generations"].items())[:40]: print("  +", f, g)
print("phrases:", sorted(report["phrases"].items(), key=lambda x: -x[1])[:40])
print("skipped (first 25):", list(report["skipped"].items())[:25])
