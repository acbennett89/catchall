"""Render the ratings site: out/site/index.html plus one folder of data files per season.

    python report.py        (after python build.py [--season YYYY] for each season)

The page has a season picker and a week picker. The default season (config.json) is embedded;
other seasons' tables, earlier weeks' tables, and every team's full trace load from
out/site/<season>/ when needed. Serve the
folder to view it locally: python -m http.server -d out/site
"""
import glob
import hashlib
import html
import json
import math
import os
import re
import shutil

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "out")


def inline(s):
    s = html.escape(s, quote=False)
    s = re.sub(r"`([^`]+)`", r"<code>\1</code>", s)
    s = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", s)
    s = re.sub(r"(?<![*\w])\*([^*\n]+)\*(?![*\w])", r"<em>\1</em>", s)
    s = re.sub(r"\[([^\]]+)\]\((https?://[^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
    return s


def markdown(md):
    """Small Markdown subset: headings, paragraphs, lists, tables, fenced code, rules."""
    out, lines, i = [], md.splitlines(), 0
    while i < len(lines):
        ln = lines[i]
        if ln.startswith("```"):
            j = i + 1
            while j < len(lines) and not lines[j].startswith("```"):
                j += 1
            out.append("<pre><code>" + html.escape("\n".join(lines[i + 1:j])) + "</code></pre>")
            i = j + 1
        elif re.match(r"^#{1,4} ", ln):
            n = len(ln) - len(ln.lstrip("#"))
            text = ln[n:].strip()
            anchor = re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")
            out.append(f'<h{n + 1} id="{anchor}">{inline(text)}</h{n + 1}>')
            i += 1
        elif ln.strip() == "---":
            out.append("<hr>")
            i += 1
        elif ln.startswith("|"):
            rows = []
            while i < len(lines) and lines[i].startswith("|"):
                rows.append([c.strip() for c in lines[i].strip().strip("|").split("|")])
                i += 1
            head, body = rows[0], [r for r in rows[2:]]
            t = '<div class="tablewrap"><table class="doc"><thead><tr>' + \
                "".join(f"<th>{inline(c)}</th>" for c in head) + "</tr></thead><tbody>"
            for r in body:
                t += "<tr>" + "".join(f"<td>{inline(c)}</td>" for c in r) + "</tr>"
            out.append(t + "</tbody></table></div>")
        elif re.match(r"^\s*([-*]|\d+\.) ", ln):
            ordered = bool(re.match(r"^\s*\d+\.", ln))
            items = []
            while i < len(lines) and (re.match(r"^\s*([-*]|\d+\.) ", lines[i])
                                      or (lines[i].startswith("   ") and items)):
                if re.match(r"^\s*([-*]|\d+\.) ", lines[i]):
                    items.append(re.sub(r"^\s*([-*]|\d+\.) ", "", lines[i]))
                else:
                    items[-1] += " " + lines[i].strip()
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{inline(x)}</li>" for x in items) + f"</{tag}>")
        elif ln.strip() == "":
            i += 1
        else:
            para = []
            while i < len(lines) and lines[i].strip() and not re.match(
                    r"^(#{1,4} |```|\||---$|\s*([-*]|\d+\.) )", lines[i]):
                para.append(lines[i].strip())
                i += 1
            out.append("<p>" + inline(" ".join(para)) + "</p>")
    return "\n".join(out)


def season_dirs():
    """Every built season (out/<season>/ratings.json), newest first."""
    found = [int(os.path.basename(os.path.dirname(p)))
             for p in glob.glob(os.path.join(OUT, "*", "ratings.json"))
             if os.path.basename(os.path.dirname(p)).isdigit()]
    return sorted(found, reverse=True)


def dump_named(obj, folder, stem):
    """Write obj as <stem>_<content hash>.json and return the file name. A rebuilt file gets a
    new name, so a browser can never pair a new page with a cached old data file."""
    text = json.dumps(obj, separators=(",", ":"), default=float)
    name = f"{stem}_{hashlib.sha1(text.encode()).hexdigest()[:10]}.json"
    with open(os.path.join(folder, name), "w", encoding="utf-8") as f:
        f.write(text)
    return name


def write_season(season, site):
    """Write one season's table and its traces as files beside the page.

    The table (every ranked number) is small; the traces (every game, drive, foul and +2 tree)
    are large, so they go in chunks of about 1.5 MB that the page fetches when a team opens.
    Returns the table and its file name."""
    src = os.path.join(OUT, str(season))
    table = json.load(open(os.path.join(src, "ratings.json"), encoding="utf-8"))
    ids = {t["id"] for t in table["teams"]}
    traces = {}
    for f in sorted(glob.glob(os.path.join(src, "traces", "*.json"))):
        if os.path.basename(f)[:-5] not in ids:
            continue  # a stray file, not a team in this table
        tr = json.load(open(f, encoding="utf-8"))
        tr.pop("summary", None)  # duplicated in the table
        traces[tr["team"]["id"]] = tr
    size = sum(len(json.dumps(t, separators=(",", ":"), default=float)) for t in traces.values())
    n_chunks = max(1, math.ceil(size / 1.5e6))
    chunks = [{} for _ in range(n_chunks)]
    where = {}
    for k, tid in enumerate(sorted(traces)):
        chunks[k % n_chunks][tid] = traces[tid]
        where[tid] = k % n_chunks
    internal = {}
    idir = os.path.join(src, "traces", "internal")
    for tid in json.load(open(os.path.join(idir, "index.json"), encoding="utf-8")):  # the ones build wrote
        tr = json.load(open(os.path.join(idir, f"{tid}.json"), encoding="utf-8"))
        internal[tr["team"]["id"]] = tr
    dst = os.path.join(site, str(season))
    shutil.rmtree(dst, ignore_errors=True)
    os.makedirs(dst, exist_ok=True)  # on Windows a file the server is sending can't be deleted; names are content-hashed, so a leftover is harmless
    table["trace_files"] = [dump_named(c, dst, f"traces_{k}") for k, c in enumerate(chunks)]
    table["trace_chunk"] = where
    table["internal_file"] = dump_named(internal, dst, "internal")
    # Weekly views: one small file per earlier week (the latest week is this table itself), the
    # polls each week used, and every team's week-by-week line for its drawer.
    table["weeks"], table["history"] = [], None
    wpath = os.path.join(src, "weekly.json")
    if os.path.exists(wpath):
        weekly = json.load(open(wpath, encoding="utf-8"))
        last = table["meta"]["through_week"]
        for s in weekly["weeks"]:
            entry = {"week": s["week"], "polls": s["meta"]["polls"]}
            if s["week"] != last:
                entry["file"] = dump_named(s, dst, f"week_{s['week']:02d}")
            table["weeks"].append(entry)
        table["history"] = weekly["history"]
    return table, dump_named(table, dst, "table")


def main():
    seasons = season_dirs()
    if not seasons:
        raise SystemExit("no built seasons: run python build.py [--season YYYY] first")
    site = os.path.join(OUT, "site")
    os.makedirs(site, exist_ok=True)
    default = json.load(open(os.path.join(HERE, "config.json"), encoding="utf-8"))["season"]
    if default not in seasons:
        default = seasons[0]
    tables, index = {}, []
    for season in seasons:
        t, table_file = write_season(season, site)
        m = t["meta"]
        index.append({"season": season, "table": table_file, "complete": m.get("regular_season_complete", False),
                      "through_week": m["through_week"], "rated": m["eligible"], "fbs": m["fbs_teams"],
                      # the model's record against the book, for the Betting tab's track record
                      "betting": m.get("betting") and {"record": m["betting"]["record"]}})
        if season == default:
            tables[str(season)] = t  # the default season is inline so the page renders without a fetch
    docs = {}
    for key, fn in (("metrics", "METRICS.md"), ("review", "ADVERSARIAL_REVIEW.md"),
                    ("trace", "TRACE.md")):
        p = os.path.join(HERE, fn)
        docs[key] = markdown(open(p, encoding="utf-8").read()) if os.path.exists(p) else "<p>Not written yet.</p>"
    boot = {"default": default, "seasons": index, "tables": tables}
    blob = json.dumps(boot, separators=(",", ":"), default=float).replace("</", "<\\/")
    page = open(os.path.join(HERE, "report_template.html"), encoding="utf-8").read()
    page = page.replace("__DATA__", blob)
    for k, v in docs.items():
        page = page.replace(f"<!--DOC:{k}-->", v)
    with open(os.path.join(site, "index.html"), "w", encoding="utf-8") as f:
        f.write(page)
    total = sum(os.path.getsize(os.path.join(dp, fn)) for dp, _, fns in os.walk(site) for fn in fns)
    print(f"out/site/: page {len(page) / 1e6:.2f} MB, seasons {', '.join(map(str, seasons))} "
          f"(default {default}), {total / 1e6:.1f} MB in all")


if __name__ == "__main__":
    main()
