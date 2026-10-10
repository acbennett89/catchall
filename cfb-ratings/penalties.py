"""Penalty event parser for ESPN college-football game summaries.

    from penalties import parse_game_penalties
    events = parse_game_penalties(summary)          # summary = ESPN summary JSON (dict)

Every penalty clause in the play-by-play becomes one event dict:

    game, drive_index, play_id, period, clock, offense_team_id, penalized_team_id,
    penalized_unit ('offense'|'defense'|'kicking'|'return'|'unknown'),
    category, presnap, yards, status ('accepted'|'declined'|'offsetting'|'unknown'),
    no_play, first_down_awarded, on_play_type, source_text
    + seq (play order in the game), player, raw_name, inferred (foul inferred from a kick
      listed twice with no penalty text), status_inferred (narrative clause whose ball spot did
      not move -> declined), enf_from / enf_to (absolute yard line from the home goal)
    + diagnostics: team_token, team_method ('code'|'name'|'prefix'|'direction'|'unresolved'),
      yards_method ('explicit'|'split-std'|'spots'|'spots=std'|'standard'|'half-distance'|
      'replayed-kick'|'none'|'n/a'), dialect ('statcrew'|'narrative'|'inferred'), joined, enf

Pass diag={} to collect counters (methods, de-duplications, orientation_swapped games).
Status 'unknown' is never produced by the text parser: on ESPN's stat-crew text a foul with no
'declined'/'offsetting' word is accepted (validated against the box score).

Penalties come from two places: plays typed 'Penalty' and penalty clauses embedded in
other plays (Rush, Pass Reception, Punt, Kickoff, ...). Three text dialects are handled:

  stat-crew   "PENALTY UNA False Start (#50 W.French III) 5 yards from UNA21 to UNA16. NO PLAY"
  stat-crew2  "PENALTY CLEMSON pass interference (Woodaz, Wade) 15 yards to the LSU34, NO PLAY, 1ST DOWN LSU."
  narrative   "Alabama Penalty, Delay of Game (-5 Yards) to the ECU 35"

Team identification: the penalized-team token is matched against (1) each game's
stat-crew yard-line codes, learned by comparing the spots in play text ("to the UNA16")
with ESPN's absolute start/end yardLine (measured from the home goal line), and
(2) ESPN names (abbreviation, location, displayName, shortDisplayName, nickname).
Only if both fail is the token resolved by prefix match, and only after that by the
direction the ball moved (diagnostic key team_method says which was used).

Accuracy against ESPN box-score penalty totals (accepted fouls): 2026 count exact in 90.4% of
team-games (99.1% within one), yards exact 88.6%; 2025 about 3% of fouls are absent from ESPN's
play text (mostly the mixed-dialect games of weeks 1-8). The box score stays the authority for
team totals; this table supplies the splits (unit, pre-snap, first downs, game situation).

Standard library only.
"""
import re
from collections import Counter, defaultdict

# --------------------------------------------------------------------------------------
# Category normalisation
# --------------------------------------------------------------------------------------
# (regex on lower-cased, de-spaced raw name, category, presnap)
_CAT_RULES = [
    (r"falsestart", "False Start", True),
    (r"delayofgame|delayofthegame", "Delay of Game", True),
    (r"encroach", "Encroachment", True),
    (r"neutralzone", "Neutral Zone Infraction", True),
    (r"offside|off-side|offsides", "Offside", True),
    (r"illegalformation", "Illegal Formation", True),
    (r"illegalshift", "Illegal Shift", True),
    (r"illegalmotion", "Illegal Motion", True),
    (r"illegalprocedure", "Illegal Procedure", True),
    (r"illegalparticipation", "Illegal Participation", False),
    (r"illegalsubstitution|substitutioninfraction|12menonthefield|toomany", "Illegal Substitution", True),
    (r"illegalsnap", "Illegal Snap", True),
    (r"disconcerting", "Disconcerting Signals", True),
    (r"kickcatch|fair ?catchinterference|faircatchinterference", "Kick Catch Interference", False),
    (r"interference.*sideline|sideline", "Sideline Interference", False),
    (r"passinterference|^pi$", "Pass Interference", False),
    (r"roughing(the)?passer", "Roughing the Passer", False),
    (r"roughing(the)?kicker", "Roughing the Kicker", False),
    (r"roughing(the)?holder", "Roughing the Holder", False),
    (r"runninginto(the)?kicker|runninginto(the)?holder", "Running Into the Kicker", False),
    (r"targeting", "Targeting", False),
    (r"facemask", "Face Mask", False),
    (r"horsecollar", "Horse Collar Tackle", False),
    (r"unsportsmanlike|^uns", "Unsportsmanlike Conduct", False),
    (r"unnecessaryroughness|^unr", "Unnecessary Roughness", False),
    (r"fighting", "Personal Foul", False),
    (r"personalfoul", "Personal Foul", False),
    (r"intentionalgrounding", "Intentional Grounding", False),
    (r"ineligible|inelgible", "Ineligible Downfield", False),
    (r"illegalforwardpass", "Illegal Forward Pass", False),
    (r"illegaltouch.*pass", "Illegal Touching", False),
    (r"illegaltouch", "Illegal Touching", False),
    (r"illegalblock.*(back|ibb)|illegalblockinback|^ibb", "Illegal Block in the Back", False),
    (r"blockbelow|chopblock|clipping|illegalwedge|blockingoutofbounds|illegalblockafter",
     "Illegal Block (Other)", False),
    (r"illegalblock", "Illegal Block in the Back", False),
    (r"illegaluseofhands|illegalhands", "Illegal Use of Hands", False),
    (r"tripping", "Tripping", False),
    (r"illegalbat|illegalkick", "Illegal Bat/Kick", False),
    (r"holding", "Holding", False),  # split into Offensive/Defensive by unit below
    (r"equipment", "Equipment Violation", False),
    (r"leaping|leverage", "Leaping/Leverage", False),
    (r"helpingtherunner|returnfromoutofbounds|illegalcontact", "Other", False),
]
_CAT_RULES = [(re.compile(rx), cat, pre) for rx, cat, pre in _CAT_RULES]


def normalize_category(raw):
    key = re.sub(r"[\s_]+", "", (raw or "").lower())
    if not key:
        return "Unknown", False
    for rx, cat, pre in _CAT_RULES:
        if rx.search(key):
            return cat, pre
    return "Other", False


# --------------------------------------------------------------------------------------
# Spots ("to the UNA16", "from Jax St35", "to the ECU 35", "to the 50 yard line")
# --------------------------------------------------------------------------------------
_CODE = r"[A-Za-z][A-Za-z&\.\-']*(?: [A-Za-z][A-Za-z&\.\-']*)?"
SPOT_RE = re.compile(r"(?:\bto the |\bat the |\bto |\bfrom |\bat )(?P<code>" + _CODE + r") ?(?P<n>\d{1,2})(?!\d)")
FIFTY_RE = re.compile(r"(?:\bto the |\bat the |\bto |\bat )50(?: yard line)?\b")


def _norm(s):
    return re.sub(r"\s+", " ", (s or "").strip()).upper()


def _spots(text):
    """All (start_index, code, n) spots in text, plus midfield spots with code None."""
    out = [(m.start(), m.group("code"), int(m.group("n"))) for m in SPOT_RE.finditer(text)
           if m.group("code").lower() not in ("the", "a", "for", "of")]
    out += [(m.start(), None, 50) for m in FIFTY_RE.finditer(text)]
    return sorted(out, key=lambda s: s[0])


class GameContext:
    """Per-game team names and stat-crew yard-line codes."""

    def __init__(self, summary):
        comps = summary["header"]["competitions"][0]["competitors"]
        self.side = {}       # team id -> 'home'/'away'
        self.ids = {}        # 'home'/'away' -> team id
        self.names = defaultdict(set)   # team id -> aliases (upper)
        for c in comps:
            t = c["team"]
            self.side[t["id"]] = c["homeAway"]
            self.ids[c["homeAway"]] = t["id"]
            for k in ("abbreviation", "location", "displayName", "shortDisplayName", "nickname", "name"):
                if t.get(k) and k != "name":
                    self.names[t["id"]].add(_norm(t[k]))
        for bt in summary.get("boxscore", {}).get("teams", []):
            t = bt.get("team", {})
            if t.get("id") in self.side:
                for k in ("abbreviation", "location", "displayName", "shortDisplayName"):
                    if t.get(k):
                        self.names[t["id"]].add(_norm(t[k]))
        self.home, self.away = self.ids.get("home"), self.ids.get("away")
        self._learn_codes(summary)

    def other(self, tid):
        return self.away if tid == self.home else self.home if tid == self.away else None

    def _learn_codes(self, summary):
        votes = defaultdict(Counter)   # code -> Counter(team_id), from play-text spots
        pvotes = defaultdict(Counter)  # code -> Counter(team_id), from ESPN possessionText
        for d in summary.get("drives", {}).get("previous", []):
            for p in d.get("plays", []):
                st, en = p.get("start", {}), p.get("end", {})
                lines = {x.get("yardLine") for x in (st, en) if isinstance(x.get("yardLine"), int)}
                # possessionText "UK 25" -> the abbreviation sits on that side of the field
                for x in (st, en):
                    m = re.match(r"^(.*?)\s*(\d{1,2})$", x.get("possessionText") or "")
                    yl = x.get("yardLine")
                    if m and isinstance(yl, int) and int(m.group(2)) != 50:
                        n = int(m.group(2))
                        if yl == n:
                            pvotes[_norm(m.group(1))][self.home] += 1
                        elif yl == 100 - n:
                            pvotes[_norm(m.group(1))][self.away] += 1
                if not lines:
                    continue
                for _, code, n in _spots((p.get("text", "") or "").replace("`", "")):
                    if code is None or n == 50:
                        continue
                    h, a = n in lines, (100 - n) in lines
                    if h and not a:
                        votes[_norm(code)][self.home] += 1
                    elif a and not h:
                        votes[_norm(code)][self.away] += 1
        def decide(c):
            (t1, n1), *rest = c.most_common(2) + [(None, 0)]
            return t1 if n1 >= 2 and n1 >= 3 * rest[0][1] else None
        # Text tokens are stat-crew codes, so votes from text spots win; ESPN's possessionText
        # labels only fill in codes never seen in the text (they can disagree when a stat-crew
        # feed has the two teams' labels swapped).
        self.code_side = {}
        for code in set(votes) | set(pvotes):
            t = decide(votes[code]) if code in votes else None
            if t is None and not votes.get(code):
                t = decide(pvotes[code])
            if t is not None:
                self.code_side[code] = t
        # Orientation check: codes that are plainly one team's name ('ALST', 'SOUT' ~ 'SOUTHERN')
        # should land on that team. If most such codes land on the other team, ESPN's play
        # orientation (yardLine / start.team) is swapped for this game: trust the names.
        agree = disagree = 0
        for code, tid in self.code_side.items():
            nt = self._name_team(code)
            if nt is None:
                continue
            agree += nt == tid
            disagree += nt != tid
        self.orientation_swapped = disagree > agree and disagree >= 2
        if self.orientation_swapped:
            self.code_side = {c: self.other(t) for c, t in self.code_side.items()}
        # header aliases are a weaker prior: only used if the learned map has no opinion
        self.alias_side = {}
        for tid, al in self.names.items():
            for a in al:
                if a in self.alias_side and self.alias_side[a] != tid:
                    self.alias_side[a] = None   # ambiguous
                else:
                    self.alias_side[a] = tid
        cands = set(self.code_side) | {a for a, t in self.alias_side.items() if t}
        self.candidates = sorted(cands, key=len, reverse=True)

    def _name_team(self, code):
        """Team whose ESPN names contain this code exactly or as a unique prefix (len >= 3)."""
        k2 = re.sub(r"[^A-Z0-9&]", "", code)
        exact = {t for t, al in self.names.items() if code in al}
        if len(exact) == 1:
            return exact.pop()
        if len(k2) < 3:
            return None
        hits = {t for t, al in self.names.items()
                for a in al if re.sub(r"[^A-Z0-9&]", "", a).startswith(k2)}
        return hits.pop() if len(hits) == 1 else None

    # ---- resolution -------------------------------------------------------------------
    def resolve(self, token):
        """token -> (team_id, method) or (None, None)."""
        k = _norm(token)
        if not k:
            return None, None
        if k in self.code_side:
            return self.code_side[k], "code"
        if self.alias_side.get(k):
            return self.alias_side[k], "name"
        k2 = re.sub(r"[^A-Z0-9&]", "", k)
        hits = set()
        for a, tid in list(self.alias_side.items()) + list(self.code_side.items()):
            if not tid:
                continue
            a2 = re.sub(r"[^A-Z0-9&]", "", a)
            if len(k2) >= 3 and len(a2) >= 3 and (a2.startswith(k2) or k2.startswith(a2)):
                hits.add(tid)
        if len(hits) == 1:
            return hits.pop(), "prefix"
        return None, None

    def spot_abs(self, code, n):
        """Absolute yard line from the home goal line, or None."""
        if code is None:
            return 50
        if n == 50:
            return 50
        tid, _ = self.resolve(code)
        if tid is None:
            return None
        return n if tid == self.home else 100 - n

    def lead_token(self, body):
        """Longest known team code/alias at the start of body -> (token, rest)."""
        b = body.lstrip()
        bu = b.upper()
        for c in self.candidates:
            if bu.startswith(c) and (len(b) == len(c) or not (b[len(c)].isalnum() or b[len(c)] == "&")):
                return b[:len(c)], b[len(c):]
        m = re.match(r"(\S+)(.*)$", b, re.S)
        return (m.group(1), m.group(2)) if m else ("", b)


# --------------------------------------------------------------------------------------
# Clause parsing
# --------------------------------------------------------------------------------------
_NAME_STOP = re.compile(
    r"\s*\(|\s+declined|\s+offsetting|\s+off-setting|\s+-?\d+\s+yards?\b|\s+enforced\b|,|\.(?:\s|$)|"
    r"\s+on\s+(?!pass\b)|\s+#|\s+PENALTY\b|\s{2,}|\s+to the\b|\s+for a 1ST|$", re.I)
_YDS_FROM = re.compile(r"(-?\d+)\s+yards?\s+from\s+(?P<a>" + _CODE + r") ?(?P<an>\d{1,2})(?!\d)\s+to\s+(?:the\s+)?"
                       r"(?:(?P<b>" + _CODE + r") ?(?P<bn>\d{1,2})(?!\d)|(?P<b50>50))", re.I)
_YDS_TO = re.compile(r"(-?\d+)\s+yards?\s+to\s+(?:the\s+)?(?:(?P<b>" + _CODE + r") ?(?P<bn>\d{1,2})(?!\d)|(?P<b50>50))", re.I)
_YDS_ENF = re.compile(r"enforced for (\d+) yards?", re.I)
_YDS_PAREN = re.compile(r"\((-?\d+) Yards\)")
_TO_SPOT = re.compile(r"\bto the (?:(?P<b>" + _CODE + r") ?(?P<bn>\d{1,2})(?!\d)|(?P<b50>50)(?: yard line)?)")
_ORIG = re.compile(r"\(Original Play:.*?\)\s*$|\(Original Play:.*", re.S)


def _name_split(body):
    m = _NAME_STOP.search(body)
    return body[:m.start()].strip(), body[m.start():]


_SPLIT = re.compile(r"\b(?:declined|offsetting|off-setting)\b[,.]?\s*|\s{2,}|(?<=\))\s+", re.I)


def _stat_crew_clauses(text, ctx):
    """Yield raw clause dicts from 'PENALTY ...' text.

    One 'PENALTY' segment can hold several fouls: 'Ark Holding offsetting UTA Holding offsetting',
    'GSU Holding declined GSU Holding (#89 K.Robinson) 9 yards from ...', or two fouls joined by a
    double space ('WSU Offside  WSU UNS: Unsportsmanlike Conduct ...'). A new foul starts after a
    status word or a double space only when it is followed by a known team code and a penalty name.
    """
    idx = [m.start() for m in re.finditer(r"\bPENALTY\b", text)]
    for j, s in enumerate(idx):
        e = idx[j + 1] if j + 1 < len(idx) else len(text)
        seg = text[s + len("PENALTY"):e]
        if re.match(r"\s*#\d", seg):        # "PENALTY #99 H.Zureikat kick attempt good" (junk echo)
            continue
        body, first, pos = seg, True, s
        while body.strip():
            token, rest = ctx.lead_token(body)
            name, tail = _name_split(rest.lstrip())
            if not first and not (ctx.resolve(token)[0] and name):
                break
            nxt, tail_here = None, tail
            for m in _SPLIT.finditer(tail):
                after = tail[m.end():]
                t2, r2 = ctx.lead_token(after)
                n2 = _name_split(r2.lstrip())[0] if t2 else ""
                if ctx.resolve(t2)[0] and n2 and normalize_category(n2)[0] not in ("Unknown", "Other"):
                    nxt, tail_here = after, tail[:m.end()]
                    break
            clause_txt = body[:len(body) - len(nxt)] if nxt is not None else body
            yield {"dialect": "statcrew", "token": token, "name": name, "tail": tail_here,
                   "clause": ("PENALTY " + clause_txt.strip()), "pos": pos, "seg": s,
                   "joined": (not first) or nxt is not None}
            first = False
            if nxt is None:
                break
            body = nxt


def _narr_clauses(text, ctx):
    """Yield raw clause dicts from '<Team> Penalty, ...' text."""
    marks = [m for m in re.finditer(r"\bPenalty,\s*", text)]
    if not marks:
        # rare lower-case form, only when it is the sole mention: "...for a TD,Sam Houston penalty, illegal forward pass"
        marks = [m for m in re.finditer(r"(?<!\bby )\bpenalty,\s*(?!clock)", text)]
    names = sorted({a for a, t in ctx.alias_side.items() if t} | set(ctx.code_side), key=len, reverse=True)
    for j, m in enumerate(marks):
        before = text[:m.start()].rstrip()
        token = None
        bu = before.upper()
        for a in names:
            if bu.endswith(a) and (len(bu) == len(a) or not bu[-len(a) - 1].isalnum()):
                token = before[-len(a):]
                break
        if token is None:
            w = re.findall(r"[A-Za-z&\.\-'\(\)]+", before[-40:])
            token = " ".join(w[-2:]) if w else ""
        e = len(text)
        if j + 1 < len(marks):
            e = marks[j + 1].start()
            # back up over the next clause's team name
            nb = text[:e].rstrip()
            nbu = nb.upper()
            for a in names:
                if nbu.endswith(a):
                    e = len(nb) - len(a)
                    break
        body = text[m.end():e]
        name, tail = _name_split(body)
        yield {"dialect": "narrative", "token": token, "name": name, "tail": tail,
               "clause": (token + " Penalty, " + body).strip(), "pos": m.start() - len(token), "joined": False}


def _play_kind(ptype, text):
    tl = text.lower()
    if ptype.startswith("Kickoff") or " kickoff " in f" {tl} ":
        return "kickoff"
    if ptype.startswith("Punt") or ptype == "Blocked Punt" or re.search(r"\bpunt\b", tl):
        return "punt"
    if "Field Goal" in ptype or "field goal" in tl:
        return "fg"
    return "scrimmage"


def parse_game_penalties(summary, game_id=None, diag=None):
    """Return a list of penalty event dicts for one ESPN game summary.

    diag (optional dict) receives counters: team_method, yards_method, unresolved, etc.
    """
    if diag is None:
        diag = {}
    for k in ("team_method", "yards_method", "status", "dialect"):
        diag.setdefault(k, Counter())
    ctx = GameContext(summary)
    diag["orientation_swapped"] = diag.get("orientation_swapped", 0) + int(ctx.orientation_swapped)
    gid = game_id or summary.get("header", {}).get("id")
    events, recent, pseq_counter = [], [], 0
    for di, d in enumerate(summary.get("drives", {}).get("previous", [])):
        drive_team = d.get("team", {}).get("id")
        for p in d.get("plays", []):
            pseq_counter += 1
            raw = (p.get("text", "") or "").replace("`", "")
            text = _ORIG.sub("", raw)            # ignore the pre-review "(Original Play: ...)" echo
            ptype = p.get("type", {}).get("text", "") or ""
            clauses = list(_stat_crew_clauses(text, ctx)) + list(_narr_clauses(text, ctx))
            if not clauses and ptype == "Penalty" and not re.search(r"penalty", raw, re.I):
                diag.setdefault("penalty_type_without_text", 0)
                diag["penalty_type_without_text"] += 1
            if not clauses:
                continue
            st, en = p.get("start", {}), p.get("end", {})
            off = st.get("team", {}).get("id") or drive_team
            if off not in ctx.side:
                off = drive_team if drive_team in ctx.side else None
            kind = _play_kind(ptype, text)
            spots = _spots(text)
            evs = []
            for c in clauses:
                ev = _build_event(c, ctx, p, ptype, kind, off, spots, text, st, en, diag)
                ev.update(game=gid, drive_index=di, play_id=p.get("id"), seq=pseq_counter,
                          period=p.get("period", {}).get("number"),
                          clock=p.get("clock", {}).get("displayValue"))
                evs.append(ev)
            _split_joined_yards(evs, clauses, diag)
            evs = _dedupe_play(evs, diag)
            # the same foul echoed on a neighbouring play (same team, foul, player, enforcement text)
            keep = []
            for e in evs:
                k = (e["penalized_team_id"], e["category"], e["player"], e["yards"], e["enf"], e["status"])
                echo = e["enf"] and any(k == key and pseq_counter - pseq <= 3 for key, pseq, _ in recent)
                # a yardless copy of a foul listed (with yardage) on the play just before/after
                echo = echo or any(pseq_counter - pseq <= 1 and _same_foul(e, o) and
                                   (e["yards_method"] == "none" or o["yards_method"] == "none"
                                    or (OPTIONS.get("echo_same_text") and e["source_text"] == o["source_text"]))
                                   for _, pseq, o in recent)
                if echo:
                    diag.setdefault("deduped_cross_play", 0)
                    diag["deduped_cross_play"] += 1
                    continue
                keep.append(e)
            for e in keep:
                recent.append(((e["penalized_team_id"], e["category"], e["player"], e["yards"], e["enf"],
                                e["status"]), pseq_counter, e))
            events.extend(keep)
    events = _drop_corrections(events, diag)
    if OPTIONS.get("infer_replayed_kicks", True):
        events += _infer_replayed_kicks(summary, ctx, events, gid, diag)
    for ev in events:
        diag["team_method"][ev["team_method"]] += 1
        diag["yards_method"][ev["yards_method"]] += 1
        diag["status"][ev["status"]] += 1
        diag["dialect"][ev["dialect"]] += 1
    return events


# Standard enforcement distance by category (NCAA), used only when the text gives no yardage
# (narrative dialect spot fouls). None = variable (spot fouls such as DPI / grounding).
STD_YARDS = {
    "False Start": 5, "Delay of Game": 5, "Encroachment": 5, "Neutral Zone Infraction": 5, "Offside": 5,
    "Illegal Formation": 5, "Illegal Shift": 5, "Illegal Motion": 5, "Illegal Procedure": 5,
    "Illegal Substitution": 5, "Illegal Participation": 15, "Illegal Snap": 5, "Running Into the Kicker": 5,
    "Ineligible Downfield": 5, "Illegal Forward Pass": 5, "Illegal Touching": 5,
    "Offensive Holding": 10, "Defensive Holding": 10, "Holding": 10, "Illegal Block in the Back": 10,
    "Illegal Use of Hands": 10, "Illegal Bat/Kick": 10,
    "Kick Catch Interference": 15, "Roughing the Passer": 15, "Roughing the Kicker": 15,
    "Roughing the Holder": 15, "Targeting": 15, "Face Mask": 15, "Horse Collar Tackle": 15,
    "Unsportsmanlike Conduct": 15, "Unnecessary Roughness": 15, "Personal Foul": 15,
    "Illegal Block (Other)": 15, "Tripping": 15, "Leaping/Leverage": 15,
}
_OFF_LIVE = {"Offensive Holding", "Illegal Block in the Back", "Ineligible Downfield", "Illegal Forward Pass",
             "Illegal Block (Other)", "Illegal Use of Hands", "Illegal Touching", "Holding"}
_OFF_ONLY = re.compile(r"false ?start|offensive|ineligible|inelgible|illegal ?formation|illegal ?shift|illegal ?motion|"
                       r"intentional ?grounding|illegal ?forward|illegal ?snap", re.I)
_DEF_ONLY = re.compile(r"defensive|roughing ?(the )?passer|neutral ?zone|disconcerting", re.I)


def _implied_unit(raw):
    if _OFF_ONLY.search(raw or ""):
        return "offense"
    if _DEF_ONLY.search(raw or ""):
        return "defense"
    return None


OPTIONS = {"narr_std_yards": True, "narr_spot0": "all", "infer_replayed_kicks": True, "drop_corrections": True,
           "echo_same_text": True, "joined_share_from": False}


def _build_event(c, ctx, p, ptype, kind, off, spots, text, st, en, diag):
    tail, name = c["tail"], c["name"]
    tl = tail.lower()
    player = None
    mp = re.match(r"\s*\(([^)]*)\)", tail)
    if mp and not re.match(r"-?\d+ Yards$|Yards$|\d+ yards$", mp.group(1)):
        player = mp.group(1)
    # ---- status
    if re.search(r"\boff-?setting\b", tl):
        status = "offsetting"
    elif re.search(r"\bdeclined\b", tl):
        status = "declined"
    else:
        status = None
    # ---- yards (explicit first)
    yards, ymeth, frm_abs, to_abs, enf = None, None, None, None, ""
    m = _YDS_FROM.search(tail)
    if m:
        enf = m.group(0)
        yards, ymeth = abs(int(m.group(1))), "explicit"
        frm_abs = ctx.spot_abs(m.group("a"), int(m.group("an")))
        to_abs = 50 if m.group("b50") else ctx.spot_abs(m.group("b"), int(m.group("bn")))
    else:
        m = _YDS_TO.search(tail)
        if m:
            enf = m.group(0)
            yards, ymeth = abs(int(m.group(1))), "explicit"
            to_abs = 50 if m.group("b50") else ctx.spot_abs(m.group("b"), int(m.group("bn")))
        else:
            m = _YDS_ENF.search(tail)
            if m:
                yards, ymeth = int(m.group(1)), "explicit"
            else:
                m = _YDS_PAREN.search(tail)
                if m:
                    yards, ymeth = abs(int(m.group(1))), "explicit"
    mt = _TO_SPOT.search(tail)
    if mt and to_abs is None:
        to_abs = 50 if mt.group("b50") else ctx.spot_abs(mt.group("b"), int(mt.group("bn")))
        enf = enf or mt.group(0)
    prev_abs = None
    if frm_abs is None:
        # previous spot: last spot in the text before this clause, else the play's start
        prev = [s for s in spots if s[0] < c["pos"]]
        if prev:
            prev_abs = ctx.spot_abs(prev[-1][1], prev[-1][2])
        elif isinstance(st.get("yardLine"), int):
            prev_abs = st["yardLine"]
    start_abs = st.get("yardLine") if isinstance(st.get("yardLine"), int) else None
    # ---- team
    tid, tmeth = ctx.resolve(c["token"])
    f_abs = frm_abs if frm_abs is not None else prev_abs
    if tid is None and f_abs is not None and to_abs is not None and to_abs != f_abs:
        # ball moves toward the penalised team's own goal line (home goal = 0)
        tid, tmeth = (ctx.home if to_abs < f_abs else ctx.away), "direction"
    if tid is None and ptype == "Penalty" and isinstance(st.get("yardsToEndzone"), int) \
            and isinstance(en.get("yardsToEndzone"), int) and off:
        dy = en["yardsToEndzone"] - st["yardsToEndzone"]
        if dy and st.get("team", {}).get("id") == en.get("team", {}).get("id"):
            tid, tmeth = (off if dy > 0 else ctx.other(off)), "direction"
    if tid is None:
        tmeth = "unresolved"
    # A foul type that only one unit can commit overrides a contradicting team name (the
    # narrative feed occasionally names the wrong team).
    if OPTIONS.get("unit_override") and tid is not None and off in ctx.side and kind == "scrimmage":
        imp = _implied_unit(name)
        if imp and (imp == "offense") != (tid == off):
            tid, tmeth = (off if imp == "offense" else ctx.other(off)), "unit-override"
    # ---- unit and category
    if tid is None or off is None:
        unit = "unknown"
    elif kind in ("kickoff", "punt"):
        unit = "kicking" if tid == off else "return"
    elif kind == "fg":
        unit = "kicking" if tid == off else "defense"
    else:
        unit = "offense" if tid == off else "defense"
    cat, presnap = normalize_category(name)
    if cat == "Holding":
        cat = {"offense": "Offensive Holding", "defense": "Defensive Holding"}.get(unit, "Holding")
    status_inferred = False
    # ---- yards without explicit numbers (mostly the narrative dialect)
    spot_y = abs(to_abs - prev_abs) if (yards is None and to_abs is not None and prev_abs is not None) else None
    spot_y_start = abs(to_abs - start_abs) if (to_abs is not None and start_abs is not None) else None
    if yards is None and status is None and c["dialect"] == "narrative":
        std = STD_YARDS.get(cat)
        dist_to = None
        if to_abs is not None and tid is not None:
            dist_to = to_abs if tid == ctx.home else 100 - to_abs
        if std is None or not OPTIONS["narr_std_yards"]:
            if spot_y is not None:
                yards, ymeth = spot_y, "spots"
        elif spot_y == std or spot_y_start == std:
            yards, ymeth = std, "spots=std"
        elif dist_to is not None and dist_to < std:
            # half-the-distance zone
            cands = [y for y in (spot_y, spot_y_start) if y is not None and y <= std]
            yards, ymeth = (min(cands, key=lambda y: abs(y - dist_to)) if cands else dist_to), "half-distance"
        else:
            yards, ymeth = std, "standard"
        if c["dialect"] == "narrative" and spot_y == 0 and status is None and OPTIONS["narr_spot0"] != "keep":
            if OPTIONS["narr_spot0"] == "all" or (OPTIONS["narr_spot0"] == "live" and not presnap):
                status = "declined"      # ball left where the play ended: narrative omitted 'declined'
                status_inferred = True
                diag.setdefault("narr_spot0_declined", 0)
                diag["narr_spot0_declined"] += 1
    if status is None:
        # stat-crew convention: a foul with no 'declined'/'offsetting' is accepted, even when no
        # yardage is printed (intentional grounding at the spot, illegal bat, ...)
        status = "accepted"
    if status in ("declined", "offsetting"):
        yards, ymeth = 0, "n/a"
    if yards is None:
        ymeth = "none"
    # ---- nullified snap?
    if c["dialect"] == "statcrew":
        no_play = bool(re.search(r"NO PLAY", tail))
    else:
        # The narrative dialect never says whether the snap stood, and ESPN's yardage shows
        # most "spot foul" snaps did stand, so this is unknown (None) unless the foul sits on
        # its own Penalty row with no play action (a pre-snap / dead-ball foul).
        no_play = None
        if status == "accepted" and ptype == "Penalty" and not re.search(
                r"\b(run|rush|pass|sacked|kneel|punt|kickoff|return)\b", text[:c["pos"]], re.I):
            no_play = True
    first = bool(re.search(r"1ST DOWN", tail, re.I))
    return {"offense_team_id": off, "penalized_team_id": tid, "penalized_unit": unit,
            "category": cat, "presnap": bool(presnap), "yards": yards if yards is not None else 0,
            "status": status, "no_play": bool(no_play), "first_down_awarded": first,
            "on_play_type": ptype, "source_text": c["clause"][:300],
            "raw_name": name, "player": player, "team_token": c["token"], "team_method": tmeth,
            "yards_method": ymeth, "dialect": c["dialect"], "joined": c["joined"], "enf": enf,
            "enf_from": frm_abs, "enf_to": to_abs, "status_inferred": status_inferred, "inferred": False}


def _same_foul(a, b):
    return (a["penalized_team_id"], a["category"], a["player"], a["status"]) == \
        (b["penalized_team_id"], b["category"], b["player"], b["status"])


def _dedupe_play(evs, diag):
    """Drop echoes of the same foul inside one play's text (PAT re-tries repeat clauses):
    same team, foul, player and status, and either identical yardage/enforcement or one copy
    without any yardage."""
    out = []
    for e in evs:
        dup = None
        for i, o in enumerate(out):
            if _same_foul(o, e) and ((o["yards"] == e["yards"] and o["enf"] == e["enf"])
                                     or o["yards_method"] == "none" or e["yards_method"] == "none"):
                dup = i
                break
        if dup is None:
            out.append(e)
        else:
            diag.setdefault("deduped", 0)
            diag["deduped"] += 1
            if out[dup]["yards_method"] == "none" and e["yards_method"] != "none":
                out[dup] = e
    return out


def _drop_corrections(events, diag):
    """ESPN sometimes posts a foul, then re-posts the corrected call on the next play entry. Two
    accepted fouls on the same team enforced from the same spot on the same or the next play
    entry (or within two entries for the same player) -> keep only the later one."""
    if not OPTIONS.get("drop_corrections", True):
        return events
    drop = set()
    acc = [i for i, e in enumerate(events) if e["status"] == "accepted" and e["enf_from"] is not None]
    for x, i in enumerate(acc):
        a = events[i]
        for j in acc[x + 1:]:
            b = events[j]
            gap = b["seq"] - a["seq"]
            if gap > 2:
                break
            if b["penalized_team_id"] == a["penalized_team_id"] and b["enf_from"] == a["enf_from"] and \
                    (gap <= 1 or (a["player"] and a["player"] == b["player"])):
                drop.add(i)
                break
    if drop:
        diag.setdefault("dropped_corrections", 0)
        diag["dropped_corrections"] += len(drop)
    return [e for i, e in enumerate(events) if i not in drop]


_SKIP_TYPES = {"Timeout", "End Period", "End of Half", "End of Game", "Coin Toss", "Official Timeout",
               "End of Regulation", "Two-minute warning"}
_NARR_TEXT = re.compile(r"#\d|PENALTY|\(\d\d?:\d\d\)|[Pp]enalty")


def _infer_replayed_kicks(summary, ctx, events, gid, diag):
    """Narrative-dialect feeds sometimes list a punt/kickoff twice (original and re-kick or
    re-spotted result) and drop the penalty text. Two consecutive kick entries with the same
    start spot, down and type, different text and different end spots, neither carrying any
    penalty text -> one inferred accepted foul against the team the ball moved against.
    Flagged inferred=True, category 'Unknown'."""
    pen_plays = {e["play_id"] for e in events}
    seq = []
    n = 0
    for di, d in enumerate(summary.get("drives", {}).get("previous", [])):
        for p in d.get("plays", []):
            n += 1
            if (p.get("type", {}).get("text") or "") in _SKIP_TYPES:
                continue
            if isinstance(p.get("start", {}).get("yardLine"), int):
                seq.append((di, n, p))
    out = []
    for (da, na, a), (db, nb, b) in zip(seq, seq[1:]):
        ta, tb = a.get("text", "") or "", b.get("text", "") or ""
        if a.get("id") in pen_plays or b.get("id") in pen_plays or _NARR_TEXT.search(ta) or _NARR_TEXT.search(tb):
            continue
        if not re.search(r"\b(punt|kickoff)\b", ta, re.I):
            continue
        sa, sb = a["start"], b["start"]
        if (sa.get("yardLine"), sa.get("down"), sa.get("distance")) != (sb.get("yardLine"), sb.get("down"), sb.get("distance")):
            continue
        if a.get("type", {}).get("text") != b.get("type", {}).get("text") or ta == tb:
            continue
        ea, eb = a.get("end", {}).get("yardLine"), b.get("end", {}).get("yardLine")
        if not isinstance(ea, int) or not isinstance(eb, int) or ea == eb:
            continue
        tid = ctx.home if eb < ea else ctx.away
        kicker = a.get("start", {}).get("team", {}).get("id")
        unit = "unknown" if kicker not in ctx.side else ("kicking" if tid == kicker else "return")
        out.append({"offense_team_id": kicker, "penalized_team_id": tid, "penalized_unit": unit,
                    "category": "Unknown", "presnap": False, "yards": abs(eb - ea), "status": "accepted",
                    "no_play": True, "first_down_awarded": False,
                    "on_play_type": a.get("type", {}).get("text", ""),
                    "source_text": ("[inferred: kick listed twice without penalty text] " + ta[:100] + " || " + tb[:100]),
                    "raw_name": "", "player": None, "team_token": "", "team_method": "direction",
                    "yards_method": "replayed-kick", "dialect": "inferred", "joined": False, "enf": "",
                    "enf_from": None, "enf_to": None, "inferred": True,
                    "game": gid, "drive_index": da, "play_id": a.get("id"), "seq": na,
                    "period": a.get("period", {}).get("number"), "clock": a.get("clock", {}).get("displayValue")})
    if out:
        diag.setdefault("inferred_replayed_kicks", 0)
        diag["inferred_replayed_kicks"] += len(out)
    return out


def _split_joined_yards(evs, clauses, diag):
    """'PENALTY USA Holding (#57) SLU UNS: Unsportsmanlike Conduct (#25) 25 yards from ...' prints
    one combined distance for two fouls. When the standard distances add up to it, give each foul
    its own standard distance."""
    groups = {}
    for e, c in zip(evs, clauses):
        if c.get("seg") is not None:
            groups.setdefault(c["seg"], []).append(e)
    for g in groups.values():
        acc = [e for e in g if e["status"] == "accepted"]
        if len(acc) < 2:
            continue
        # the fouls of one joined clause share its enforcement spot
        frm = [e["enf_from"] for e in acc if e["enf_from"] is not None]
        for e in acc:
            if e["enf_from"] is None and frm and OPTIONS.get("joined_share_from"):
                e["enf_from"] = frm[0]
        with_y = [e for e in acc if e["yards_method"] == "explicit"]
        if len(with_y) != 1 or any(e["yards_method"] not in ("none", "explicit") for e in acc):
            continue
        stds = [STD_YARDS.get(e["category"]) for e in acc]
        if None in stds or sum(stds) != with_y[0]["yards"]:
            continue
        for e, s in zip(acc, stds):
            e["yards"], e["yards_method"] = s, "split-std"
        diag.setdefault("split_joined_yards", 0)
        diag["split_joined_yards"] += 1


TABLE_FIELDS = ("seq", "drive_index", "play_id", "period", "clock", "offense_team_id",
                "penalized_team_id", "penalized_unit", "category", "presnap", "yards", "status",
                "no_play", "first_down_awarded", "on_play_type", "inferred",
                # provenance: how each value was obtained, so imputed values can be told apart
                "dialect", "team_method", "yards_method", "status_inferred", "player")


def penalty_table(events):
    """Compact rows (lists, TABLE_FIELDS order) for storage in games.json.gz."""
    return [[e.get(k) for k in TABLE_FIELDS] for e in sorted(events, key=lambda e: e["seq"])]


def team_totals(events):
    """{team_id: (accepted count, accepted yards)} -- the box-score 'totalPenaltiesYards' analog."""
    out = {}
    for e in events:
        if e["status"] == "accepted" and e["penalized_team_id"]:
            n, y = out.get(e["penalized_team_id"], (0, 0))
            out[e["penalized_team_id"]] = (n + 1, y + e["yards"])
    return out
