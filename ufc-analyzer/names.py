"""Fighter-name normalization and matching across ESPN, UFCStats and BestFightOdds.

The three sources disagree on accents (Godínez/Godinez), suffixes (Jr., III), hyphens, and name order
for Chinese and Korean fighters (Wang Cong / Cong Wang), so names are compared as token sets.
"""
import difflib, re, unicodedata

SUFFIXES = {"jr", "sr", "ii", "iii", "iv", "junior"}


def ascii_name(name):
    """'Roberto Soldić' -> 'Roberto Soldic' (site search boxes don't match accented queries)."""
    return unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().strip()


def norm(name):
    s = unicodedata.normalize("NFKD", name or "").encode("ascii", "ignore").decode().lower()
    s = re.sub(r"[\.'`’]", "", s)
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s


def tokens(name):
    return [t for t in norm(name).split() if t not in SUFFIXES]


def similarity(a, b):
    """0..1 score; 1.0 for identical token sets regardless of order."""
    ta, tb = tokens(a), tokens(b)
    if not ta or not tb:
        return 0.0
    sa, sb = set(ta), set(tb)
    if sa == sb:
        return 1.0
    ratio = difflib.SequenceMatcher(None, " ".join(sorted(ta)), " ".join(sorted(tb))).ratio()
    # every token of the shorter name appears in the longer one ("Loopy Godinez" vs "Loopy Godinez Gonzalez")
    small, big = (sa, sb) if len(sa) <= len(sb) else (sb, sa)
    if small <= big and len(small) >= 2:
        ratio = max(ratio, 0.93)
    # same last name, first names fuzzy-close ("Alexandr" / "Alexander")
    if ta[-1] == tb[-1] and difflib.SequenceMatcher(None, ta[0], tb[0]).ratio() >= 0.75:
        ratio = max(ratio, 0.9)
    return ratio


def shares_token(a, b, min_len=4):
    """True when the names share a meaningful token ("Patricio Pitbull" / "Patricio Freire")."""
    return any(len(t) >= min_len for t in set(tokens(a)) & set(tokens(b)))


def pair_score(a, b, x, y):
    """How well ESPN pair (a, b) matches another source's pair (x, y) in that order.

    Normally both names must match; if one matches outright, the other may just share a name token,
    which covers fighters listed under a ring name on one site ("Patricio Pitbull" on ESPN is
    "Patricio Freire" elsewhere).
    """
    sa, sb = similarity(a, x), similarity(b, y)
    lo, hi = min(sa, sb), max(sa, sb)
    if lo >= 0.84:
        return lo
    if hi >= 0.92 and (shares_token(a, x) if sa < sb else shares_token(b, y)):
        return 0.85
    return lo
