"""One fighter, as of a given event: bio, career stats, record breakdown, and the last five fights.

ESPN supplies the bio and the complete pro history (regional fights included, so debutants still have
a last five).  UFCStats adds the official career rates and, for UFC fights, both fighters' knockdowns,
significant strikes, takedowns and submission attempts.  BestFightOdds adds the opening and closing
line for each past fight, so you can see whether a win came as a favourite or an underdog.
"""
import datetime

import bfo, espn, ufcstats
from names import similarity

DAY = 86400


def method_kind(method):
    m = (method or "").lower()
    if "no contest" in m or m.strip() in ("nc", "overturned"):
        return "nc"
    if "dq" in m or "disqual" in m:
        return "dq"
    if "sub" in m:
        return "sub"
    if "ko" in m or "doctor" in m or "stoppage" in m:
        return "ko"
    if "dec" in m or "decision" in m:
        return "dec"
    return "other"


def _ufcs_date(s):
    try:
        return datetime.datetime.strptime(s.replace(".", ""), "%b %d, %Y").replace(tzinfo=datetime.timezone.utc).timestamp() + 12 * 3600
    except Exception:
        return None


def _num(s):
    try:
        return int(s)
    except (TypeError, ValueError):
        return None


def _match_ufcs(h, rows):
    for r in rows:
        d = _ufcs_date(r["date"])
        if d and h["date"] and abs(d - h["date"]) <= 2 * DAY and similarity(h["opponent"]["name"] or "", r["opponent"]) >= 0.7:
            return r
    return None


def _match_odds(h, odds_hist):
    for o in odds_hist:
        if o["date"] and h["date"] and abs(o["date"] - h["date"]) <= 3 * DAY and similarity(h["opponent"]["name"] or "", o["opponent"]) >= 0.8:
            return o
    return None


def _closing(o):
    """A single representative closing price from BFO's closing range (the less extreme end)."""
    lo, hi = o.get("closeLow"), o.get("closeHigh")
    vals = [v for v in (lo, hi) if v is not None]
    if not vals:
        return o.get("open")
    return max(vals) if all(v < 0 for v in vals) else min(vals) if all(v > 0 for v in vals) else vals[0]


def summarize(prior):
    """Record breakdown, streak and finish rates over a list of past fights (most recent first)."""
    wins = {"ko": 0, "sub": 0, "dec": 0, "other": 0}
    losses = {"ko": 0, "sub": 0, "dec": 0, "other": 0}
    w = l = d = nc = 0
    ufc = [0, 0, 0]
    for h in prior:
        r, kind = (h.get("result") or "").upper(), method_kind(h.get("method"))
        if kind == "nc" or r == "NC":
            nc += 1
            continue
        k = kind if kind in wins else "other"
        if r == "W":
            w += 1
            wins[k] += 1
        elif r == "L":
            l += 1
            losses[k] += 1
        elif r == "D":
            d += 1
        if h.get("ufc"):
            ufc[0 if r == "W" else 1 if r == "L" else 2] += r in ("W", "L", "D")
    streak = None
    for h in prior:
        r = (h.get("result") or "").upper()
        if r not in ("W", "L"):
            if r == "D" or method_kind(h.get("method")) == "nc":
                break
            continue
        if streak is None:
            streak = [r, 1]
        elif r == streak[0]:
            streak[1] += 1
        else:
            break
    finishes = wins["ko"] + wins["sub"]
    return {
        "record": f"{w}-{l}-{d}" + (f" ({nc} NC)" if nc else ""),
        "wins": wins, "losses": losses,
        "ufcRecord": f"{ufc[0]}-{ufc[1]}-{ufc[2]}",
        "ufcFights": sum(ufc),
        "streak": f"{streak[0]}{streak[1]}" if streak else None,
        "finishRate": round(finishes / w, 3) if w else None,
        "finishedRate": round((losses["ko"] + losses["sub"]) / l, 3) if l else None,
        "fights": w + l + d,
    }


def last_five(prior, ufcs_rows, odds_hist):
    out = []
    for h in prior[:5]:
        row = _match_ufcs(h, ufcs_rows) if h.get("ufc") else None
        odds = _match_odds(h, odds_hist)
        s = h.get("stats") or {}
        entry = {
            "date": h["date"], "event": h["event"], "ufc": h["ufc"], "title": h["title"],
            "result": h["result"], "opponent": h["opponent"],
            "method": h["method"], "methodShort": h["methodShort"], "methodDetail": row["methodDetail"] if row else None,
            "round": h["round"], "time": h["time"], "seconds": h["seconds"],
            "stats": None,
            "odds": None,
        }
        if row:
            entry["stats"] = {"kd": [_num(x) for x in row["kd"]], "sig": [_num(x) for x in row["str"]],
                              "td": [_num(x) for x in row["td"]], "subAtt": [_num(x) for x in row["sub"]], "source": "ufcstats"}
        elif s:
            entry["stats"] = {"kd": [s.get("kd"), None], "sig": [s.get("ssl"), None], "sigAtt": s.get("ssa"),
                              "td": [s.get("tdl"), None], "tdAtt": s.get("tda"), "subAtt": [s.get("subAtt"), None], "source": "espn"}
        if odds:
            entry["odds"] = {"open": odds["open"], "close": _closing(odds), "closeLow": odds["closeLow"], "closeHigh": odds["closeHigh"]}
        out.append(entry)
    return out


def _safe(fn, *a, default=None):
    try:
        return fn(*a)
    except Exception:
        return default


def build(espn_id, before=None, name=None):
    a = espn.athlete(espn_id)
    name = a.get("name") or name
    before = before or 9e12
    hist = [h for h in a["history"] if h["date"] and h["date"] < before - 6 * 3600 and h.get("result")]

    first, last = (name.split(" ", 1) + [""])[:2] if name else ("", "")
    fid = _safe(ufcstats.find_id, name, first, last.split(" ")[-1] if last else None, espn_id, a.get("record"))
    uf = _safe(ufcstats.fighter, fid) if fid else None
    ufcs_rows = (uf or {}).get("fights") or []
    opponents = tuple(h["opponent"]["name"] for h in hist[:6] if h["opponent"]["name"])
    odds_hist = _safe(bfo.fighter_history, name, opponents, default=[]) or []

    current_odds = None
    for o in odds_hist:
        if o["date"] and abs(o["date"] - before) <= 3 * DAY:
            current_odds = {"open": o["open"], "closeLow": o["closeLow"], "closeHigh": o["closeHigh"],
                            "opponent": o["opponent"], "spark": o["spark"]}
            break

    l5 = last_five(hist, ufcs_rows, odds_hist)
    recent = {"sigFor": 0, "sigAgainst": 0, "tdFor": 0, "tdAgainst": 0, "kdFor": 0, "kdAgainst": 0, "fights": 0, "seconds": 0}
    for e in l5:
        st = e["stats"]
        if not st or st.get("source") != "ufcstats" or None in st["sig"]:
            continue
        recent["fights"] += 1
        recent["seconds"] += e["seconds"] or 0
        recent["sigFor"] += st["sig"][0]
        recent["sigAgainst"] += st["sig"][1]
        recent["tdFor"] += st["td"][0] or 0
        recent["tdAgainst"] += st["td"][1] or 0
        recent["kdFor"] += st["kd"][0] or 0
        recent["kdAgainst"] += st["kd"][1] or 0

    return {
        "id": a["id"], "name": a["name"], "nickname": a.get("nickname"), "headshot": a.get("headshot"),
        "height": a.get("height"), "weight": a.get("weight"), "reach": a.get("reach"), "stance": a.get("stance"),
        "dob": a.get("dob"), "age": a.get("age"), "gym": a.get("gym"), "style": a.get("style"),
        "country": a.get("country"), "flag": a.get("flag"), "weightClass": a.get("weightClass"),
        "espnRecord": a.get("record"),
        "career": (uf or {}).get("career"),
        "ufcstatsId": fid,
        "summary": summarize(hist),
        "daysSinceLast": round((min(before, 9e12) - hist[0]["date"]) / DAY) if hist and before < 9e12 else None,
        "lastFive": l5,
        "recent": recent if recent["fights"] else None,
        "currentOdds": current_odds,
    }
