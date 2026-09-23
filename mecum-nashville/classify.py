"""Classify every lot in corpus.jsonl into structured fields and write the car database.

    python classify.py            -> classified.jsonl (one lot per line) + cars.db (SQLite)

Fields added per lot:
  family      make + base model, merging Mecum's split models ("Camaro Z28" -> Camaro, trim z28)
  gen         generation label from taxonomy.json, else the model year
  trim        sorted trim tokens that recur in the family (nicknames and one-off words dropped)
  body        convertible / coupe / fastback / ...   body_group: open / closed / wagon / truck
  mod         stock / custom / replica / race / continuation / project (title words + engine-swap evidence)
  ci, hp, forced, config, trans, speeds, swap   parsed from Mecum's powertrain line
  grade       Main attraction / Feature / star / General / none
"""
import json, re, sqlite3, statistics, collections, time, os

TAX = json.load(open("taxonomy.json", encoding="utf-8"))
PHRASES = sorted(((k, v) for k, v in TAX["phrases"].items()), key=lambda kv: -len(kv[0]))
PHRASES += [("custom deluxe", "customdeluxe"), ("custom cab", "customcab"), ("custom sports special", "cst"), ("custom 500", "custom500"),
            ("custom 10", "custom10"), ("super custom", "supercustom"), ("custom royal", "customroyal"), ("country squire", "countrysquire")]
PHRASES.sort(key=lambda kv: -len(kv[0]))
BODY, MOD, GENERIC = TAX["body"], {k: v for k, v in TAX["modifier"].items() if v}, set(TAX["generic"])
SWAP = TAX["engine_swap_markers"]
MOD_RANK = ["replica", "race", "custom", "continuation", "project"]


def tokens(title):
    s = (title or "").lower().replace("’", "").replace("'", "").replace('"', "")
    s = re.sub(r"\b\d+\s+of\s+[\d,]+\b", " ", s)            # "1 of 650 produced"
    for k, v in PHRASES:
        s = re.sub(r"(?<![a-z0-9])" + re.escape(k) + r"(?![a-z0-9])", f" {v} ", s)
    s = re.sub(r"[^a-z0-9 ]", " ", s)
    return s.split()


def parse_series(s, year):
    out = {}
    if not s: return out
    t = s.lower()
    m = re.search(r"(\d{2,3})\s*ci\b", t)
    if m: out["ci"] = int(m.group(1))
    else:
        m = re.search(r"(\d{1,2}\.\d)\s*l\b", t)
        if m: out["ci"] = round(float(m.group(1)) * 61.0237)
        else:
            m = re.search(r"(\d{3,4})\s*cc\b", t)
            if m: out["ci"] = round(int(m.group(1)) / 16.387)
    m = re.search(r"(\d{2,4})\s*hp\b", t)
    if m: out["hp"] = int(m.group(1))
    out["forced"] = ("twin-turbo" if re.search(r"twin[- ]turbo", t) else "supercharged" if re.search(r"supercharg|blown|blower", t)
                     else "turbo" if "turbo" in t else None)
    for pat, cfg in [(r"v-?12", "V12"), (r"v-?10", "V10"), (r"v-?8", "V8"), (r"v-?6", "V6"), (r"flat[- ]?6|flat 6", "F6"), (r"flat[- ]?4", "F4"),
                     (r"inline[- ]?6|inline 6|straight 6|6-cylinder", "I6"), (r"inline[- ]?8|straight 8|8-cylinder", "I8"), (r"inline[- ]?4|4-cylinder", "I4"),
                     (r"rotary", "R"), (r"electric|\bev\b", "EV")]:
        if re.search(pat, t): out["config"] = cfg; break
    if "automatic" in t or "powerglide" in t or "turbo-hydramatic" in t or "hydra-matic" in t: out["trans"] = "auto"
    elif re.search(r"\d-speed|manual|stick", t): out["trans"] = "manual"
    m = re.search(r"(\d)-speed", t)
    if m: out["speeds"] = int(m.group(1))
    if "hemi" in t: out["hemi"] = 1
    # engine-swap evidence: an LS/Coyote/Hellcat/crate/stroker in a car built before that engine existed
    if any(k in t for k in SWAP) and (year or 9999) < 1997: out["swap"] = 1
    return out


def generation(fam_key, year):
    for label, a, b in TAX["generations"].get(fam_key, []):
        if year and a <= year <= b: return label
    return str(year) if year else None


def main():
    t0 = time.time()
    rows = [json.loads(l) for l in open("corpus.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["type"] in ("Auto", "Motorcycle", "Tractor", "Trailer")]
    print("vehicles:", len(rows), flush=True)

    # 1. families: merge "Camaro Z28" into "Camaro" when "Camaro" is itself a model with some volume
    mcount = collections.Counter((r["make"], r["model"]) for r in rows if r["model"])
    by_make = collections.defaultdict(list)
    for (mk, md), n in mcount.items(): by_make[mk].append((md, n))
    family_of = {}
    for mk, models in by_make.items():
        cnt = dict(models)
        for md, n in models:
            words = md.split(); base = md
            # shortest prefix that is itself a real model: "Corvette Z06 Carbon Edition" -> Corvette, not "Corvette Z06"
            for i in range(1, len(words)):
                cand = " ".join(words[:i])
                if cnt.get(cand, 0) >= max(5, 0.5 * n): base = cand; break
            family_of[(mk, md)] = base

    # 1b. spelling variants ("F-150" / "F150", "Landrover" / "Land Rover") collapse to the most common spelling
    key = lambda s: re.sub(r"[^a-z0-9]", "", (s or "").lower())
    fam_votes = collections.defaultdict(collections.Counter); make_votes = collections.defaultdict(collections.Counter)
    for r in rows:
        mk = r["make"] or ""; fam = family_of.get((mk, r["model"] or ""), r["model"] or "") or ""
        make_votes[key(mk)][mk] += 1; fam_votes[(key(mk), key(fam))][fam] += 1
    canon_make = {k: c.most_common(1)[0][0] for k, c in make_votes.items()}
    canon_fam = {k: c.most_common(1)[0][0] for k, c in fam_votes.items()}
    gen_keys = {(key(k.split("|")[0]), key(k.split("|")[1])): k for k in TAX["generations"]}

    # 2. per-lot parse
    for r in rows:
        mk0, md, yr = r["make"] or "", r["model"] or "", r["year"]
        fam0 = family_of.get((mk0, md), md) or md
        mk, fam = canon_make[key(mk0)], canon_fam[(key(mk0), key(fam0))]
        r["family"] = f"{mk}|{fam}"
        r["_genkey"] = gen_keys.get((key(mk), key(fam)), r["family"])
        drop = set(tokens(mk)) | set(tokens(fam)) | {str(yr)}
        tk = [w for w in tokens(r["title"]) if w not in drop]
        # the part of Mecum's model name beyond the family is trim evidence ("Chevelle SS" -> ss)
        extra = [w for w in tokens(md) if w not in set(tokens(fam))]
        tk = extra + tk
        if r.get("trim"): tk += [w for w in tokens(r["trim"]) if w not in drop]
        bodies = [w for w in tk if w in BODY]
        mods = {MOD[w] for w in tk if w in MOD}
        s = parse_series(r.get("series"), yr)
        if s.get("swap") and not mods: mods.add("custom")
        r["body"] = bodies[0] if bodies else None
        r["body_group"] = BODY[bodies[0]] if bodies else None
        r["mod"] = next((m for m in MOD_RANK if m in mods), "stock")
        r["_raw"] = [w for w in dict.fromkeys(tk) if w not in BODY and w not in MOD and w not in GENERIC and not re.fullmatch(r"(19|20)\d\d|\d|door|dr|\d+dr", w)]
        # odometer, when Mecum wrote it into the powertrain line ("9,395 Miles", "58 Actual Miles")
        m = re.search(r"([\d,]+)\s+(actual\s+)?miles", r.get("series") or "", re.I)
        r["miles"] = int(m.group(1).replace(",", "")) if m and m.group(1).replace(",", "").isdigit() else None
        r["actual"] = 1 if m and m.group(2) else 0
        r.update({k: s.get(k) for k in ("ci", "hp", "forced", "config", "trans", "speeds", "hemi", "swap")})
        r["gen"] = generation(r.pop("_genkey"), yr)
        st = r.get("status") or []
        r["grade"] = "Main attraction" if "Main attraction" in st else "Feature" if "Feature" in st else "star" if "star" in st else "General" if "General" in st else "none"
        r["no_reserve"] = 1 if "No reserve" in st else 0

    # 2b. NHTSA VIN decode (1981+): fills body when the title has none, and adds drive type
    vin = json.load(open("vin_cache.json")) if os.path.exists("vin_cache.json") else {}
    VBODY = [("convertible", "convertible", "open"), ("roadster", "roadster", "open"), ("coupe", "coupe", "closed"), ("sedan", "sedan", "closed"),
             ("hatchback", "hatchback", "closed"), ("wagon", "wagon", "wagon"), ("pickup", "pickup", "truck"), ("sport utility", "suv", "truck"),
             ("van", "van", "truck"), ("cab chassis", "pickup", "truck")]
    for r in rows:
        v = vin.get(r["id"])
        tk = set(tokens(r["title"]))
        r["drive"] = "4wd" if tk & {"4x4", "4wd", "awd"} else None
        if not v: continue
        b = (v.get("body") or "").lower()
        if not r["body_group"]:
            for pat, lab, grp in VBODY:
                if pat in b: r["body"], r["body_group"] = lab, grp; break
        d = (v.get("drive") or "").lower()
        if not r["drive"] and d: r["drive"] = "4wd" if re.search(r"4wd|4x4|awd|all-wheel|4-wheel", d) else "2wd"

    # 3. learned trim vocabulary: a word counts as trim if it recurs within the family
    vocab = collections.defaultdict(collections.Counter)
    for r in rows: vocab[r["family"]].update(set(r["_raw"]))
    for r in rows:
        v = vocab[r["family"]]
        r["trim_tokens"] = sorted(w for w in r["_raw"] if v[w] >= 3)
        r["trim"] = " ".join(r["trim_tokens"])
        del r["_raw"]
    print("classified in", round(time.time() - t0), "s", flush=True)

    with open("classified.jsonl", "w", encoding="utf-8") as f:
        for r in rows: f.write(json.dumps(r, ensure_ascii=False) + "\n")

    # 4. SQLite database
    if os.path.exists("cars.db"): os.remove("cars.db")
    db = sqlite3.connect("cars.db")
    cols = ["id", "auction", "end", "lot", "title", "year", "make", "model", "family", "gen", "trim", "body", "body_group", "mod",
            "ci", "hp", "forced", "config", "trans", "speeds", "hemi", "swap", "drive", "miles", "actual", "grade", "no_reserve", "sold", "bgo", "price", "series", "color", "url", "type"]
    db.execute(f"CREATE TABLE lots ({', '.join(cols)})")
    db.executemany(f"INSERT INTO lots VALUES ({','.join('?' * len(cols))})", [[r.get(c) for c in cols] for r in rows])
    db.execute("CREATE INDEX lots_family ON lots(family, gen)")
    # summaries over sold cars from the last five years (prices include buyer's premium, as Mecum publishes them)
    recent = [r for r in rows if r["sold"] and r["price"] and (r["end"] or 0) > time.time() - 5 * 365 * 86400]
    def summ(ps):
        ps = sorted(ps); q = statistics.quantiles(ps, n=4) if len(ps) >= 4 else [ps[0], statistics.median(ps), ps[-1]]
        return len(ps), round(statistics.median(ps)), round(q[0]), round(q[2])
    groups = collections.defaultdict(list)
    for r in recent: groups[(r["family"], r["gen"], r["trim"], r["body_group"], r["mod"])].append(r["price"])
    db.execute("CREATE TABLE trims (family, gen, trim, body_group, mod, sold, median, p25, p75)")
    db.executemany("INSERT INTO trims VALUES (?,?,?,?,?,?,?,?,?)", [(*k, *summ(v)) for k, v in groups.items()])
    fams = collections.defaultdict(list); fam_recent = collections.defaultdict(list)
    for r in rows: fams[r["family"]].append(r)
    for r in recent: fam_recent[r["family"]].append(r["price"])
    db.execute("CREATE TABLE families (family, lots, sold, first_year, last_year, median_recent, trims)")
    db.executemany("INSERT INTO families VALUES (?,?,?,?,?,?,?)", [
        (f, len(v), sum(1 for r in v if r["sold"]), min((r["year"] for r in v if r["year"]), default=None), max((r["year"] for r in v if r["year"]), default=None),
         round(statistics.median(fam_recent[f])) if fam_recent[f] else None,
         json.dumps([w for w, n in vocab[f].most_common(40) if n >= 3])) for f, v in fams.items()])
    db.commit(); db.close()
    print("wrote classified.jsonl and cars.db in", round(time.time() - t0), "s", flush=True)


if __name__ == "__main__":
    main()
