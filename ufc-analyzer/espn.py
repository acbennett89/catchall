"""ESPN's public JSON: the UFC schedule, full fight cards with live status, and fighter profiles.

    events(season)   every UFC event on ESPN's calendar for a season
    card(event_id)   the card for one event, segment by segment, with live status and results
    athlete(id)      bio plus complete pro fight history (regional fights included) with per-fight stats
"""
import datetime, re, time

from net import cache, fetch_json, DiskStore

SITE = "https://site.api.espn.com/apis/site/v2/sports/mma/ufc"
WEB = "https://site.web.api.espn.com/apis/common/v3/sports/mma"
SEGMENTS = [("main", "Main Card"), ("prelims1", "Prelims"), ("prelims2", "Early Prelims")]
athletes_disk = DiskStore("espn_athletes")


def _ts(iso):
    if not iso:
        return None
    iso = iso.replace("Z", "+00:00")
    if re.search(r"T\d\d:\d\d\+", iso):  # "2026-10-03T20:00+00:00" has no seconds
        iso = iso.replace("+", ":00+", 1)
    return datetime.datetime.fromisoformat(iso).timestamp()


def events(season=None):
    def load():
        url = SITE + "/scoreboard" + (f"?dates={season}" if season else "")
        d = fetch_json(url)
        cal = (d.get("leagues") or [{}])[0].get("calendar") or []
        live = {e["id"]: e.get("status", {}).get("type", {}).get("state") for e in d.get("events", [])}
        out = []
        for c in cal:
            m = re.search(r"events/(\d+)", (c.get("event") or {}).get("$ref", ""))
            if not m:
                continue
            eid = m.group(1)
            start, end = _ts(c.get("startDate")), _ts(c.get("endDate"))
            now = time.time()
            state = live.get(eid) or ("post" if end and end < now else "pre" if start and start > now else "in")
            out.append({"id": eid, "name": c.get("label"), "start": start, "end": end, "state": state})
        return out
    return cache.get(("events", season), load, ttl=600)


def _num(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _fighter(comp):
    a = comp.get("athlete") or {}
    stats = {s.get("name"): s.get("value") for s in comp.get("stats") or []}
    ml = None
    for o in (comp.get("bets") or {}).get("odds") or []:
        if o.get("type") == "moneyline" and o.get("values"):
            ml = _num(str(o["values"][0].get("odds", "")).replace("+", ""))
    return {
        "id": comp.get("id") or a.get("id"),
        "name": a.get("displayName") or a.get("fullName"),
        "firstName": a.get("firstName"),
        "lastName": a.get("lastName"),
        "record": comp.get("displayRecord"),
        "age": a.get("age"),
        "height": a.get("displayHeight"),
        "weight": a.get("displayWeight"),
        "reach": a.get("displayReach"),
        "stance": (a.get("stance") or {}).get("text"),
        "country": a.get("country"),
        "flag": (a.get("flag") or {}).get("href"),
        "headshot": (a.get("headshot") or {}).get("href"),
        "winner": bool(comp.get("winner")),
        "order": comp.get("order"),
        "espnStats": {
            "slpm": stats.get("strikeLPM"),
            "strAcc": stats.get("strikeAccuracy"),
            "tdAvg": stats.get("takedownAvg"),
            "tdAcc": stats.get("takedownAccuracy"),
            "subAvg": stats.get("submissionAvg"),
        },
        "dkMoneyline": ml,
    }


def _fight_bets(comp):
    """DraftKings props ESPN exposes at fight level (total rounds, goes the distance)."""
    out = []
    for o in (comp.get("bets") or {}).get("odds") or []:
        vals = [{"line": v.get("line"), "odds": v.get("odds")} for v in o.get("values") or []]
        out.append({"name": o.get("displayName"), "values": vals})
    return out


def _placeholder(comp):
    name = ((comp.get("athlete") or {}).get("displayName") or "").strip()
    return not name or re.fullmatch(r"(?i)(opponent\s+)?tb[ad]", name) is not None


def parse_card(d):
    ev = d.get("event") or {}
    venue = d.get("venue") or {}
    meta = d.get("meta") or {}
    fights = []
    cards = d.get("cards") or {}
    seg_names = dict(SEGMENTS)
    order = [s for s, _ in SEGMENTS] + [s for s in cards if s not in seg_names]
    for seg in order:
        c = cards.get(seg)
        if not c:
            continue
        for comp in c.get("competitions") or []:
            st = comp.get("status") or {}
            stype = st.get("type") or {}
            res = st.get("result") or {}
            note = comp.get("note") or ""
            title = any("title" in (t.get("text") or "").lower() for t in comp.get("types") or []) or "Title" in note
            main_event = "Main Event" in note
            competitors = sorted(comp.get("competitors") or [], key=lambda x: x.get("order") or 9)
            if len(competitors) != 2 or any(_placeholder(x) for x in competitors):
                continue  # ESPN lists unannounced bouts as "Opponent TBA vs TBA"
            fights.append({
                "id": comp.get("id"),
                "segment": seg,
                "segmentName": c.get("displayName") or seg_names.get(seg, seg),
                "matchNumber": comp.get("matchNumber"),
                "date": _ts(comp.get("date")),
                "weightClass": (comp.get("type") or {}).get("text"),
                "note": note,
                "title": title,
                "mainEvent": main_event,
                "rounds": 5 if (title or main_event) else 3,
                "status": {
                    "state": stype.get("state"),
                    "completed": bool(stype.get("completed")),
                    "detail": stype.get("detail"),
                    "short": stype.get("shortDetail"),
                    "period": st.get("period"),
                    "clock": st.get("displayClock"),
                    "method": res.get("displayName") or res.get("shortDisplayName"),
                    "methodDetail": res.get("displayDescription") or res.get("description"),
                },
                "fighters": [_fighter(x) for x in competitors],
                "dkProps": _fight_bets(comp),
            })
    states = [f["status"]["state"] for f in fights]
    state = meta.get("gameState") or ("in" if "in" in states else "post" if states and all(s == "post" for s in states) else "pre")
    if state == "in" and states and all(s == "post" for s in states):
        state = "post"
    return {
        "id": ev.get("id"),
        "name": ev.get("name"),
        "shortName": ev.get("shortName"),
        "date": _ts(ev.get("date")),
        "venue": venue.get("displayNameLocation") or venue.get("fullName"),
        "state": state,
        "fights": fights,
    }


def card(event_id):
    def load():
        return parse_card(fetch_json(f"{WEB}/ufc/fightcenter/{event_id}"))
    # Live cards refresh fast; finished cards rarely change.
    return cache.get(("card", event_id), load, ttl=lambda c: 15 if c["state"] == "in" else 120 if c["state"] == "pre" else 1800)


def _clock_seconds(period, clock):
    try:
        m, s = str(clock).split(":")
        return (int(period) - 1) * 300 + int(m) * 60 + int(s)
    except Exception:
        return None


STAT_KEYS = {"SSL": "ssl", "SSA": "ssa", "TSL": "tsl", "TSA": "tsa", "KD": "kd", "TDL": "tdl", "TDA": "tda", "SM": "subAtt"}


def parse_stats(d):
    """Per-fight stats keyed by competition uid."""
    out = {}
    for cat in d.get("categories") or []:
        labels = [l.strip() for l in cat.get("labels") or []]
        for row in cat.get("statistics") or []:
            uid = row.get("uid")
            dst = out.setdefault(uid, {})
            for lab, val in zip(labels, row.get("stats") or []):
                k = STAT_KEYS.get(lab)
                if k:
                    v = _num(val)
                    dst[k] = int(v) if v is not None and v == int(v) else v
    return out


def parse_athlete(d, stats=None):
    a = d.get("athlete") or {}
    summ = {s.get("name"): s.get("displayValue") for s in (a.get("statsSummary") or {}).get("statistics") or []}
    em = d.get("eventsMap") or {}
    stats = stats or {}
    hist = []
    for uid in d.get("events") or []:
        e = em.get(uid)
        if not e:
            continue
        st = e.get("status") or {}
        res = st.get("result") or {}
        opp = e.get("opponent") or {}
        league = re.search(r"~l:(\d+)", uid)
        hist.append({
            "uid": uid,
            "eventId": e.get("id"),
            "date": _ts(e.get("gameDate")),
            "event": e.get("name"),
            "shortEvent": e.get("shortName"),
            "ufc": bool(league and league.group(1) == "3321"),
            "result": e.get("gameResult"),
            "opponent": {"id": opp.get("id"), "name": opp.get("displayName")},
            "method": res.get("displayName"),
            "methodShort": res.get("shortDisplayName"),
            "round": st.get("period"),
            "time": st.get("displayClock"),
            "seconds": _clock_seconds(st.get("period"), st.get("displayClock")),
            "title": bool(e.get("titleFight")),
            "stats": stats.get(uid),
        })
    hist.sort(key=lambda h: h["date"] or 0, reverse=True)
    return {
        "id": a.get("id"),
        "name": a.get("displayName"),
        "nickname": a.get("nickname"),
        "headshot": (a.get("headshot") or {}).get("href"),
        "height": a.get("displayHeight"),
        "weight": a.get("displayWeight"),
        "reach": a.get("displayReach"),
        "stance": (a.get("stance") or {}).get("text"),
        "dob": a.get("displayDOB"),
        "age": a.get("age"),
        "gym": (a.get("association") or {}).get("name"),
        "style": a.get("displayFightingStyle"),
        "country": a.get("citizenship"),
        "flag": (a.get("flag") or {}).get("href"),
        "weightClass": (a.get("weightClass") or {}).get("text"),
        "record": summ.get("wins-losses-draws"),
        "koRecord": summ.get("tkos-tkoLosses"),
        "subRecord": summ.get("submissions-submissionLosses"),
        "history": hist,
    }


def athlete(aid):
    def load():
        d = fetch_json(f"{WEB}/athletes/{aid}")
        try:
            s = parse_stats(fetch_json(f"{WEB}/athletes/{aid}/stats"))
        except Exception:
            s = {}
        out = parse_athlete(d, s)
        athletes_disk.put(str(aid), out)
        return out

    def load_with_disk():
        try:
            return load()
        except Exception:
            v = athletes_disk.get(str(aid))
            if v:
                return v
            raise
    return cache.get(("athlete", aid), load_with_disk, ttl=1800)
