"""Render out/index.html: ratings table + per-team derivations + the docs.

    python report.py
"""
import glob
import html
import json
import os
import re

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


def main():
    ratings = json.load(open(os.path.join(OUT, "ratings.json")))
    traces = {}
    for f in glob.glob(os.path.join(OUT, "traces", "*.json")):
        tr = json.load(open(f))
        tr.pop("summary", None)  # duplicated in ratings
        traces[tr["team"]["id"]] = tr
    ratings["traces"] = traces
    internal = {}
    for f in glob.glob(os.path.join(OUT, "traces", "internal", "*.json")):
        if not f.endswith("index.json"):
            tr = json.load(open(f))
            internal[tr["team"]["id"]] = tr
    ratings["internal"] = internal
    docs = {}
    for key, fn in (("metrics", "METRICS.md"), ("review", "ADVERSARIAL_REVIEW.md"),
                    ("trace", "TRACE.md")):
        p = os.path.join(HERE, fn)
        docs[key] = markdown(open(p).read()) if os.path.exists(p) else "<p>Not written yet.</p>"
    blob = json.dumps(ratings, separators=(",", ":"), default=float).replace("</", "<\\/")
    page = open(os.path.join(HERE, "report_template.html")).read()
    page = page.replace("__DATA__", blob)
    for k, v in docs.items():
        page = page.replace(f"<!--DOC:{k}-->", v)
    with open(os.path.join(OUT, "index.html"), "w") as f:
        f.write(page)
    print(f"out/index.html: {len(page) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
