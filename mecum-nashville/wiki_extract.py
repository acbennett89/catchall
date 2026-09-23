"""Pull generation infoboxes and trim candidates from Wikipedia for the top N Mecum families -> wiki_raw.json.
Polite: one request at a time, ~1 s apart, identified user agent. Resumable (skips families already fetched)."""
import json, re, time, collections, urllib.request, urllib.parse, os, sys

N = int(sys.argv[1]) if len(sys.argv) > 1 else 250
UA = "mecum-block-sheet/1.0 (personal research; https://github.com/acbennett89/catchall)"
API = "https://en.wikipedia.org/w/api.php?"
OUT = "wiki_raw.json"
raw = json.load(open(OUT)) if os.path.exists(OUT) else {}


def api(**p):
    p.update(format="json", formatversion=2)
    for a in range(4):
        try:
            req = urllib.request.Request(API + urllib.parse.urlencode(p), headers={"User-Agent": UA})
            d = json.load(urllib.request.urlopen(req, timeout=30)); time.sleep(1.0); return d
        except Exception as e:
            time.sleep(5 * (a + 1))
    return {}


def wikitext(title):
    d = api(action="parse", page=title, prop="wikitext", redirects=1)
    return (d.get("parse") or {}).get("title"), (d.get("parse") or {}).get("wikitext") or ""


def find_article(make, model):
    t, w = wikitext(f"{make} {model}")
    if w and not re.search(r"\{\{\s*(disambiguation|dab|set index)", w, re.I): return t, w
    d = api(action="query", list="search", srsearch=f"{make} {model} automobile", srlimit=3)
    for hit in (d.get("query") or {}).get("search", []):
        t, w = wikitext(hit["title"])
        if w and make.split()[0].lower() in w.lower()[:3000]: return t, w
    return None, ""


def years(s):
    ys = [int(y) for y in re.findall(r"\b(18[89]\d|19\d\d|20[0-3]\d)\b", re.sub(r"<ref.*?(</ref>|/>)", "", s or "", flags=re.S))]
    return (min(ys), max(ys)) if ys else None


def infoboxes(w):
    out = []
    for m in re.finditer(r"\{\{\s*Infobox automobile(.*?)\n\}\}", w, re.S | re.I):
        body = m.group(1)
        f = lambda k: (re.search(r"\|\s*" + k + r"\s*=\s*([^\n]*)", body) or [None, ""])[1]
        out.append({"name": re.sub(r"\[\[|\]\]|'''|''", "", f("name")).strip(), "model_years": years(f("model_years")), "production": years(f("production")),
                    "body": re.sub(r"<.*?>|\[\[[^|\]]*\||\[\[|\]\]", " ", f("body_style"))[:200].strip(), "engine": re.sub(r"<.*?>|\[\[[^|\]]*\||\[\[|\]\]", " ", f("engine"))[:300].strip()})
    return out


def trim_candidates(w):
    heads = [h.strip() for h in re.findall(r"\n==+\s*([^=\n]{2,60}?)\s*==+", w)]
    bold = [b.strip() for b in re.findall(r"'''([^'\n]{2,40})'''", w)]
    return heads, list(dict.fromkeys(bold))[:80]


if __name__ == "__main__":
    rows = [json.loads(l) for l in open("classified.jsonl", encoding="utf-8")]
    cnt = collections.Counter(r["family"] for r in rows if r["type"] == "Auto" and r["sold"] and r["price"] and r["family"].split("|")[1])
    fams = [f for f, _ in cnt.most_common(N)]
    t0 = time.time()
    for i, fam in enumerate(fams):
        if fam in raw: continue
        mk, md = fam.split("|", 1)
        title, w = find_article(mk, md)
        rec = {"title": title, "infoboxes": infoboxes(w), "subarticles": {}}
        rec["heads"], rec["bold"] = trim_candidates(w)
        # per-generation articles: {{Main|Chevrolet Corvette (C2)}} or links like [[Ford Mustang (first generation)]]
        subs = set(re.findall(r"\{\{\s*(?:Main|Main article|See also)\s*\|\s*([^}|]+)", w, re.I))
        subs |= set(re.findall(r"\[\[(" + re.escape(title or md) + r" \([^)\]]+\))", w)) if title else set()
        for s in list(subs)[:12]:
            if not re.search(r"generation|\(|C\d|series", s, re.I): continue
            st, sw = wikitext(s.strip())
            if sw: rec["subarticles"][st] = {"infoboxes": infoboxes(sw), "heads": trim_candidates(sw)[0], "bold": trim_candidates(sw)[1]}
        raw[fam] = rec
        if i % 10 == 0:
            json.dump(raw, open(OUT, "w")); print(f"{i}/{len(fams)} {fam} -> {title} ({len(rec['infoboxes'])} boxes, {len(rec['subarticles'])} sub) {round(time.time()-t0)} s", flush=True)
    json.dump(raw, open(OUT, "w")); print("done", len(raw), "families in", round(time.time() - t0), "s", flush=True)
