"use strict";
/* Fight Analyzer front end: event picker, live card, fighter-v-fighter matchup with Caesars value. */

const TARGET = "Caesars";
const $ = (s, el = document) => el.querySelector(s);
const esc = s => String(s ?? "").replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
const store = {
  get(k) { try { return JSON.parse(localStorage.getItem(k)) || {}; } catch (e) { return {}; } },
  set(k, v) { try { localStorage.setItem(k, JSON.stringify(v)); } catch (e) { /* private mode */ } },
};
const settings = Object.assign({ bankroll: 1000, kelly: 0.25, threshold: 0.02, format: "american", basis: "market" }, store.get("fa-settings"));

const S = {
  season: null, events: [], eventId: null, card: null, odds: null, fightId: null,
  fighters: {}, cardAt: 0, oddsAt: 0, timers: {}, calc: {}, showAllProps: false, oddsErr: null,
  pred: null, predAt: 0, predErr: null,
};

/* ---------- odds math (mirrors value.py) ---------- */
const dec = a => (a > 0 ? 1 + a / 100 : 1 + 100 / -a);
const imp = a => 1 / dec(a);
const evAt = (p, a) => p * dec(a) - 1;
const kellyAt = (p, a) => { const b = dec(a) - 1; return Math.max(0, (b * p - (1 - p)) / b); };
const probToAm = p => (!p || p <= 0 || p >= 1) ? null : (p <= 0.5 ? Math.round((1 / p - 1) * 100) : Math.round(-100 / (1 / p - 1)));
function fmtOdds(a) {
  if (a === null || a === undefined || isNaN(a)) return "—";
  if (settings.format === "decimal") return dec(a).toFixed(2);
  return (a > 0 ? "+" : "") + Math.round(a);
}
const pct = (p, d = 0) => (p === null || p === undefined || isNaN(p)) ? "—" : (p * 100).toFixed(d) + "%";
const signedPct = (p, d = 1) => (p === null || p === undefined || isNaN(p)) ? "—" : (p >= 0 ? "+" : "") + (p * 100).toFixed(d) + "%";
const money = v => "$" + (v >= 100 ? Math.round(v).toLocaleString() : v.toFixed(2));
const fmtDate = ts => ts ? new Date(ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" }) : "";
const fmtTime = ts => ts ? new Date(ts * 1000).toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" }) : "";
const lastName = n => (n || "").split(" ").slice(-1)[0];

async function api(path) {
  const r = await fetch(path, { cache: "no-store" });
  const j = await r.json().catch(() => ({ error: `HTTP ${r.status}` }));
  if (!r.ok || j.error && !j.fights && !j.events && !j.name) throw new Error(j.error || `HTTP ${r.status}`);
  return j;
}

/* ---------- routing ---------- */
function readHash() {
  const h = new URLSearchParams(location.hash.slice(1));
  return { event: h.get("event"), fight: h.get("fight") };
}
function writeHash(push) {
  const h = new URLSearchParams();
  if (S.eventId) h.set("event", S.eventId);
  if (S.fightId && document.body.classList.contains("show-matchup")) h.set("fight", S.fightId);
  else if (S.fightId && !isMobile()) h.set("fight", S.fightId);
  const url = "#" + h.toString();
  if (url === location.hash) return;
  if (push) history.pushState(null, "", url); else history.replaceState(null, "", url);
}
const isMobile = () => window.matchMedia("(max-width: 980px)").matches;

/* ---------- events ---------- */
async function loadEvents(season, wantId) {
  const d = await api("/api/events" + (season ? `?season=${season}` : ""));
  S.events = d.events || [];
  const now = Date.now() / 1000;
  const sel = $("#event-select");
  const groups = { Live: [], Upcoming: [], Past: [] };
  for (const e of S.events) (e.state === "in" ? groups.Live : e.state === "pre" ? groups.Upcoming : groups.Past).push(e);
  groups.Upcoming.sort((a, b) => a.start - b.start);
  groups.Past.sort((a, b) => b.start - a.start);
  sel.innerHTML = Object.entries(groups).filter(([, l]) => l.length).map(([g, l]) =>
    `<optgroup label="${g}">${l.map(e => `<option value="${esc(e.id)}">${esc(e.name)} · ${esc(fmtDate(e.start))}</option>`).join("")}</optgroup>`).join("");
  let pick = wantId && S.events.find(e => e.id === wantId) ? wantId : null;
  if (!pick && groups.Live.length) pick = groups.Live[0].id;
  if (!pick) {
    const ufcFirst = l => l.find(e => !/contender/i.test(e.name)) || l[0];
    const soon = groups.Upcoming.filter(e => e.start > now - 12 * 3600);
    pick = soon.length ? ufcFirst(soon).id : groups.Past.length ? ufcFirst(groups.Past).id : null;
  }
  if (wantId && !S.events.find(e => e.id === wantId)) {
    // deep link to an event from another season: add it so the picker shows it
    sel.insertAdjacentHTML("afterbegin", `<option value="${esc(wantId)}">Event ${esc(wantId)}</option>`);
    pick = wantId;
  }
  sel.value = pick || "";
  return pick;
}

function setupSeasons() {
  const sel = $("#season-select");
  const y = new Date().getFullYear();
  const years = [];
  for (let k = y + 1; k >= 2015; k--) years.push(k);
  sel.innerHTML = years.map(v => `<option value="${v}">${v}</option>`).join("");
  sel.value = String(y);
  S.season = y;
  sel.onchange = async () => {
    S.season = +sel.value;
    const id = await loadEvents(S.season === y ? null : S.season);
    if (id) selectEvent(id);
  };
}

/* ---------- card + odds polling ---------- */
function selectEvent(id, fightId) {
  if (S.eventId !== id) {
    S.card = null; S.odds = null; S.fightId = fightId || null; S.oddsErr = null; S.pred = null; S.predErr = null;
    clearTimeout(S.timers.card); clearTimeout(S.timers.odds);
  }
  S.eventId = id;
  $("#card-list").innerHTML = `<div class="loading">Loading card…</div>`;
  $("#matchup").innerHTML = "";
  loadCard(true);
}

function cardDelay() {
  const c = S.card;
  if (!c) return 30000;
  if (c.state === "in") return 15000;
  if (c.state === "pre") return (c.date - Date.now() / 1000 < 12 * 3600) ? 60000 : 300000;
  return 0;
}

async function loadCard(first) {
  const id = S.eventId;
  try {
    const c = await api(`/api/event/${id}`);
    if (id !== S.eventId) return;
    S.card = c; S.cardAt = Date.now();
    if (first) {
      if (!S.fightId || !c.fights.find(f => f.id === S.fightId)) S.fightId = defaultFight(c);
      renderList();
      renderMatchup();
      writeHash(false);
      loadOdds();
      prefetchFighters();
    } else {
      renderList();
      updateMatchup();
    }
  } catch (e) {
    if (first) $("#card-list").innerHTML = `<div class="empty">Couldn't load this card.<br><span class="err">${esc(e.message)}</span></div>`;
  }
  clearTimeout(S.timers.card);
  const d = cardDelay();
  if (d) S.timers.card = setTimeout(() => loadCard(false), d);
  renderStatus();
}

async function loadOdds() {
  const id = S.eventId;
  try {
    const o = await api(`/api/odds/${id}`);
    if (id !== S.eventId) return;
    S.odds = o; S.oddsAt = Date.now(); S.oddsErr = o.error || null;
    renderList();
    updateMatchup(true);
    loadPred();
  } catch (e) {
    S.oddsErr = e.message;
  }
  clearTimeout(S.timers.odds);
  if (S.card && S.card.state !== "post") S.timers.odds = setTimeout(loadOdds, 60000);
  renderStatus();
}

function defaultFight(c) {
  const live = c.fights.find(f => f.status.state === "in");
  if (live) return live.id;
  // the next fight up: last scheduled fight in card order (cards run bottom to top)
  const pre = c.fights.filter(f => f.status.state === "pre");
  if (pre.length && c.state === "in") return pre[pre.length - 1].id;
  return c.fights.length ? c.fights[0].id : null;
}

function renderStatus() {
  const el = $("#status");
  const c = S.card;
  if (!c) { el.innerHTML = ""; return; }
  const ago = t => { if (!t) return "—"; const s = Math.round((Date.now() - t) / 1000); return s < 60 ? `${s}s ago` : `${Math.round(s / 60)}m ago`; };
  const state = c.state === "in" ? `<span class="dot live"></span><b style="color:var(--live)">LIVE</b>` :
    c.state === "pre" ? `<span class="dot"></span>${esc(fmtDate(c.date))} ${esc(fmtTime(c.date))}` : `<span class="dot"></span>Final`;
  el.innerHTML = `${state} · card ${ago(S.cardAt)} · odds ${S.odds ? ago(S.oddsAt) : (S.oddsErr ? "unavailable" : "loading…")}`;
}

/* ---------- fighters ---------- */
function fighterKey(f) { return `${f.id}@${Math.round(S.card.date)}`; }
function getFighter(f) {
  const k = fighterKey(f);
  if (!S.fighters[k]) {
    S.fighters[k] = { loading: true };
    api(`/api/fighter/${f.id}?before=${Math.round(S.card.date)}&name=${encodeURIComponent(f.name)}`)
      .then(d => { S.fighters[k] = d; })
      .catch(e => { S.fighters[k] = { error: e.message }; })
      .finally(() => {
        renderList();
        const cur = currentFight();
        if (cur && cur.fighters.some(x => x.id === f.id)) updateMatchup(false, true);
      });
  }
  return S.fighters[k];
}
function prefetchFighters() {
  if (!S.card) return;
  const sel = S.card.fights.find(f => f.id === S.fightId);
  const order = [...(sel ? sel.fighters : []), ...S.card.fights.flatMap(f => f.fighters)];
  let i = 0;
  const next = () => {
    while (i < order.length) {
      const f = order[i++];
      const k = fighterKey(f);
      if (S.fighters[k]) continue;
      getFighter(f);
      const t = setInterval(() => { if (!S.fighters[k] || !S.fighters[k].loading) { clearInterval(t); next(); } }, 150);
      return;
    }
  };
  for (let n = 0; n < 4; n++) next();
}

/* ---------- card list ---------- */
function fightOdds(f) { return S.odds && S.odds.fights ? S.odds.fights[f.id] : null; }
function sideEv(fo, i) { return fo && fo.value && fo.value.sides[i] && fo.value.sides[i].target ? fo.value.sides[i].target.ev : null; }
function statusLine(f) {
  const st = f.status;
  if (st.state === "in") return `<span class="live-tag">● ${st.period ? `R${st.period} ${esc(st.clock || "")}` : esc(st.short || "Live")}</span>`;
  if (st.state === "post") {
    const w = f.fighters.find(x => x.winner);
    const how = [st.method, st.period ? `R${st.period}` : "", st.clock && st.clock !== "-" ? st.clock : ""].filter(Boolean).join(" ");
    return w ? `${esc(lastName(w.name))} · ${esc(how)}` : esc(st.method || st.short || "Final");
  }
  return esc(f.date ? fmtTime(f.date) : st.short || "");
}
function formDots(f) {
  const p = S.card && S.fighters[fighterKey(f)];
  if (!p || !p.lastFive) return "";
  return `<span class="form-dots" title="Last 5 (newest first)">${p.lastFive.map(x => `<i class="${esc(x.result)}"></i>`).join("")}</span>`;
}

function renderList() {
  const c = S.card;
  const el = $("#card-list");
  if (!c) return;
  if (!c.fights.length) { el.innerHTML = `<div class="empty">No fights posted for this event yet.</div>`; return; }
  let html = `<div class="seg-title" style="margin-top:0"><span>${esc(c.name)}</span></div><div class="small muted" style="margin:-6px 2px 2px">${esc(c.venue || "")}</div>`;
  let seg = null;
  for (const f of c.fights) {
    if (f.segment !== seg) {
      seg = f.segment;
      html += `<div class="seg-title"><span>${esc(f.segmentName)}</span><span>${f.date ? esc(fmtTime(f.date)) : ""}</span></div>`;
    }
    const fo = fightOdds(f);
    const cz = fo && fo.lines[TARGET];
    const fair = fo && fo.value && fo.value.fair;
    const actionable = f.status.state !== "post";
    const evs = [0, 1].map(i => basisEv(f, fo, i));
    const isValue = actionable && evs.some(v => v !== null && v >= settings.threshold);
    html += `<button class="fight-row${f.id === S.fightId ? " selected" : ""}${isValue ? " value" : ""}" data-fid="${esc(f.id)}">
      <div class="fr-head"><span>${esc(f.weightClass || "")}${f.title ? " · <b style='color:var(--warn)'>Title</b>" : ""} · ${f.rounds} rds</span><span>${statusLine(f)}</span></div>
      ${f.fighters.map((x, i) => {
        const cls = f.status.state === "post" ? (x.winner ? "won" : (f.fighters.some(y => y.winner) ? "lost" : "")) : "";
        const ev = evs[i];
        const evCls = actionable && ev !== null && ev >= settings.threshold ? "pos" : "";
        return `<div class="fr-line"><span class="fr-name ${cls}">${esc(x.name)}<span class="rec">${esc(x.record || "")}</span>${formDots(x)}</span>
          <span class="fr-odds">${cz && cz[i] !== null ? esc(fmtOdds(cz[i])) : "<span class='faint'>—</span>"}</span>
          <span class="fr-ev ${evCls}">${actionable && ev !== null ? esc(signedPct(ev)) : ""}</span></div>`;
      }).join("")}
      ${fair ? `<div class="fr-bar" title="Market fair: ${esc(pct(fair[0]))} / ${esc(pct(fair[1]))}"><span style="width:${(fair[0] * 100).toFixed(1)}%"></span></div>` : ""}
    </button>`;
  }
  html += `<div class="small faint" style="padding:4px 2px">Odds column = ${TARGET} moneyline. % = ${TARGET} EV vs. ${BASIS_LABEL[settings.basis] || BASIS_LABEL.market}${S.oddsErr ? `<br><span class="err">Odds: ${esc(S.oddsErr)}</span>` : ""}</div>`;
  const scroll = el.scrollTop;
  el.innerHTML = html;
  el.scrollTop = scroll;
  el.querySelectorAll(".fight-row").forEach(b => b.onclick = () => openFight(b.dataset.fid));
}

function openFight(fid) {
  S.fightId = fid;
  S.showAllProps = false;
  document.body.classList.add("show-matchup");
  writeHash(isMobile());
  renderList();
  renderMatchup();
  if (isMobile()) window.scrollTo(0, 0);
}

/* ---------- matchup ---------- */
function currentFight() { return S.card ? S.card.fights.find(f => f.id === S.fightId) : null; }

function renderMatchup() {
  const el = $("#matchup");
  const f = currentFight();
  if (!f) { el.innerHTML = `<div class="panel empty">Pick a fight from the card.</div>`; return; }
  el.innerHTML = `
    <button class="back-btn" id="back-btn">← Card</button>
    <section class="panel" id="m-head"></section>
    <section class="panel"><h3><span>${TARGET} moneyline vs. market</span><span class="small" id="m-odds-meta"></span></h3><div class="panel-body" id="m-odds"></div></section>
    <section class="panel"><h3><span>Model prediction</span><span class="small" id="m-model-meta"></span></h3><div class="panel-body" id="m-model"></div></section>
    <section class="panel"><h3><span>Your number</span><button class="link-btn" id="calc-reset">Reset</button></h3><div class="panel-body" id="m-calc"></div></section>
    <section class="panel"><h3>Matchup notes</h3><div class="panel-body" id="m-notes"></div></section>
    <section class="panel"><h3>Tale of the tape</h3><div class="panel-body" id="m-tape"></div></section>
    <section class="panel"><h3><span>Career stats</span><span class="small">UFCStats</span></h3><div class="panel-body" id="m-stats"></div></section>
    <section class="panel"><h3>Last 5 fights</h3><div class="panel-body" id="m-l5"></div></section>
    <section class="panel"><h3><span>${TARGET} props</span><span class="small" id="m-props-meta"></span></h3><div class="panel-body" id="m-props"></div></section>
    <div class="small faint" id="m-sources" style="padding:0 4px 20px"></div>`;
  $("#back-btn").onclick = () => { document.body.classList.remove("show-matchup"); writeHash(false); window.scrollTo(0, 0); };
  $("#calc-reset").onclick = () => { delete S.calc[f.id]; renderCalc(f, true); };
  updateMatchup(true, true);
}

function updateMatchup(oddsChanged, fightersChanged) {
  const f = currentFight();
  if (!f || !$("#m-head")) return;
  const [A, B] = f.fighters.map(getFighter);
  renderHead(f, A, B);
  renderOdds(f, A, B);
  if (oddsChanged || !$("#m-model").innerHTML) renderModel(f);
  const calcFocused = document.activeElement && $("#m-calc") && $("#m-calc").contains(document.activeElement);
  if (!calcFocused && (oddsChanged || !$("#m-calc").innerHTML)) renderCalc(f);
  if (fightersChanged || oddsChanged) {
    renderNotes(f, A, B);
    renderTape(f, A, B);
    renderStats(f, A, B);
    renderLastFive(f, A, B);
  }
  renderProps(f);
  renderSources(f);
}

function renderHead(f, A, B) {
  const st = f.status;
  const card = (x, p, side) => {
    const nick = p && p.nickname ? `“${esc(p.nickname)}”` : "";
    const initials = esc((x.name || "?").split(" ").map(s => s[0]).slice(0, 2).join(""));
    const img = x.headshot ? `<img class="headshot" src="${esc(x.headshot)}" alt="" onerror="this.replaceWith(Object.assign(document.createElement('div'),{className:'headshot',textContent:'${initials}',style:'display:grid;place-items:center;font-weight:800;color:var(--muted)'}))">`
      : `<div class="headshot" style="display:grid;place-items:center;font-weight:800;color:var(--muted)">${initials}</div>`;
    return `<div class="fighter-card ${side === 0 ? "red" : "blue right"}">${img}<div style="min-width:0">
      <div class="fc-name">${esc(x.name)}${x.winner ? ` <span class="badge W">W</span>` : ""}</div>
      ${nick ? `<div class="fc-nick">${nick}</div>` : ""}
      <div class="fc-meta">${x.flag ? `<img class="flag" src="${esc(x.flag)}" alt="">` : ""}<span>${esc(x.record || "")}</span>${p && p.summary && p.summary.streak ? `<span class="badge ${p.summary.streak[0]}">${esc(p.summary.streak)}</span>` : ""}</div>
    </div></div>`;
  };
  let mid = `<div class="vs">VS</div><div>${esc(f.weightClass || "")}</div><div>${f.rounds} rounds</div>`;
  if (f.title) mid += `<div style="margin-top:4px"><span class="badge title">Title fight</span></div>`;
  if (st.state === "in") mid += `<div style="margin-top:6px"><span class="badge live">● LIVE ${st.period ? `R${st.period} ${esc(st.clock || "")}` : esc(st.short || "")}</span></div>`;
  else if (st.state === "post") {
    const w = f.fighters.find(x => x.winner);
    mid += `<div class="result">${w ? esc(lastName(w.name)) + " wins" : "Final"}</div><div>${esc(st.method || "")}${st.methodDetail ? ` (${esc(st.methodDetail)})` : ""}${st.period ? ` · R${st.period} ${esc(st.clock || "")}` : ""}</div>`;
  } else mid += `<div style="margin-top:4px">${esc(f.segmentName)} · ${esc(fmtTime(f.date))}</div>`;
  $("#m-head").innerHTML = `<div class="vs-head">${card(f.fighters[0], A, 0)}<div class="vs-mid">${mid}</div>${card(f.fighters[1], B, 1)}</div>`;
}

function sparkline(series, idx) {
  const pts = series.map(s => s[idx]).filter(v => v !== null && v !== undefined).map(v => imp(v));
  if (pts.length < 2) return "";
  const min = Math.min(...pts), max = Math.max(...pts), span = max - min || 0.01;
  const d = pts.map((v, i) => `${(i / (pts.length - 1) * 100).toFixed(1)},${(30 - (v - min) / span * 26 - 2).toFixed(1)}`).join(" ");
  return `<svg class="spark" viewBox="0 0 100 30" preserveAspectRatio="none"><polyline points="${d}" fill="none" stroke="currentColor" stroke-width="1.5" vector-effect="non-scaling-stroke"/></svg>`;
}

function renderOdds(f, A, B) {
  const el = $("#m-odds");
  const fo = fightOdds(f);
  if (!S.odds) { el.innerHTML = `<div class="skeleton" style="height:90px"></div>`; return; }
  if (!fo || !Object.keys(fo.lines).length) {
    el.innerHTML = `<div class="muted">No lines posted for this fight yet.</div>`;
    $("#m-odds-meta").textContent = "";
    return;
  }
  const v = fo.value || { sides: [{}, {}] };
  const cz = fo.lines[TARGET];
  const actionable = f.status.state !== "post";
  const profiles = [A, B];
  const sides = [0, 1].map(i => {
    const x = f.fighters[i], s = v.sides[i] || {}, t = s.target, fair = v.fair ? v.fair[i] : null;
    const isValue = actionable && t && t.ev >= settings.threshold;
    const stake = t && t.ev > 0 ? settings.bankroll * t.kelly * settings.kelly : 0;
    const cur = profiles[i] && profiles[i].currentOdds;
    return `<div class="odds-side ${i ? "blue" : "red"}${isValue ? " value" : ""}">
      <div class="os-top"><span class="os-name">${esc(x.name)}</span><span class="os-book">${TARGET}</span></div>
      <div class="os-price">${cz && cz[i] !== null ? esc(fmtOdds(cz[i])) : `<span class="faint" style="font-size:16px">not posted</span>`}${isValue ? ` <span class="badge good" style="vertical-align:middle">VALUE</span>` : ""}</div>
      <dl class="kv">
        ${t ? `<dt>${TARGET} implied</dt><dd>${pct(t.implied, 1)}</dd>` : ""}
        <dt>Market fair</dt><dd>${fair !== null ? `${pct(fair, 1)} <span class="muted">(${esc(fmtOdds(s.fairOdds))})</span>` : "—"}</dd>
        ${t ? `<dt>EV at ${TARGET}</dt><dd class="${t.ev >= 0 ? "pos" : "neg"}">${signedPct(t.ev)}</dd>` : ""}
        ${s.best ? `<dt>Best price</dt><dd>${esc(fmtOdds(s.best.odds))} <span class="muted">${esc(s.best.book)}</span></dd>` : ""}
        ${t && t.ev > 0 ? `<dt>Stake (${Math.round(settings.kelly * 100)}% Kelly)</dt><dd>${money(stake)}</dd>` : ""}
        ${cur && cur.open !== null && cur.open !== undefined ? `<dt>Market open</dt><dd>${esc(fmtOdds(cur.open))}</dd>` : ""}
      </dl>
    </div>`;
  }).join("");
  const books = Object.entries(fo.lines).sort((a, b) => (a[0] === TARGET ? -1 : b[0] === TARGET ? 1 : a[0].localeCompare(b[0])));
  const off = new Set(v.outliers || []);
  const bestOf = i => Math.max(...books.filter(([bk]) => !off.has(bk)).map(([, p]) => p[i] === null ? -Infinity : dec(p[i])));
  const best = [bestOf(0), bestOf(1)];
  const table = `<table class="books-table"><thead><tr><th>Book</th><th>${esc(lastName(f.fighters[0].name))}</th><th>${esc(lastName(f.fighters[1].name))}</th><th>Hold</th></tr></thead><tbody>
    ${books.map(([bk, p]) => {
      const hold = p[0] !== null && p[1] !== null ? imp(p[0]) + imp(p[1]) - 1 : null;
      const isOff = off.has(bk);
      return `<tr class="${bk === TARGET ? "target" : ""}${isOff ? " off" : ""}"><td>${esc(bk)}${isOff ? ` <span class="faint small" title="Far from every other book (often a prediction market that has settled), so it's left out of the fair price and best price.">off-market</span>` : ""}</td>${[0, 1].map(i => `<td class="${!isOff && p[i] !== null && dec(p[i]) === best[i] ? "best" : ""}">${p[i] !== null ? esc(fmtOdds(p[i])) : "—"}</td>`).join("")}<td class="muted">${hold !== null ? pct(hold, 1) : "—"}</td></tr>`;
    }).join("")}</tbody></table>`;
  let move = "";
  const mv = fo.movement;
  if (mv && mv.length > 1 && cz) {
    const first = mv.find(s => s[1] !== null);
    if (first && (first[1] !== cz[0] || first[2] !== cz[1])) {
      move = `<div class="note-line">${TARGET} since ${esc(fmtDate(first[0]))} ${esc(fmtTime(first[0]))}: ${esc(lastName(f.fighters[0].name))} ${esc(fmtOdds(first[1]))} → <b>${esc(fmtOdds(cz[0]))}</b>, ${esc(lastName(f.fighters[1].name))} ${esc(fmtOdds(first[2]))} → <b>${esc(fmtOdds(cz[1]))}</b></div>
        <div style="color:var(--red)">${sparkline(mv, 1)}</div>`;
    }
  }
  const notes = [];
  if (!actionable) notes.push("Fight is over; these were the last lines posted.");
  if (v.fairFromTarget) notes.push(`Only ${TARGET} prices both sides, so there's no independent fair line.`);
  if (!cz) notes.push(`${TARGET} hasn't posted this fight; showing the rest of the market.`);
  el.innerHTML = `<div class="odds-grid">${sides}</div>
    ${notes.map(n => `<div class="note-line">${esc(n)}</div>`).join("")}
    ${move}
    <details${isMobile() ? "" : " open"}><summary>All books (${books.length})</summary>${table}</details>`;
  $("#m-odds-meta").textContent = [v.books ? `fair from ${v.books} book${v.books > 1 ? "s" : ""}` : "", v.targetHold !== undefined ? `${TARGET} hold ${pct(v.targetHold, 1)}` : ""].filter(Boolean).join(" · ");
}

function renderCalc(f, reset) {
  const el = $("#m-calc");
  const fo = fightOdds(f);
  const cz = fo && fo.lines[TARGET];
  const start = basisProb(f);
  let c = S.calc[f.id];
  if (!c || reset || !c.touched) {
    c = S.calc[f.id] = {
      p: start !== null ? Math.round(start * 1000) / 10 : 50,
      oa: cz && cz[0] !== null ? cz[0] : "",
      ob: cz && cz[1] !== null ? cz[1] : "",
    };
  }
  const [na, nb] = f.fighters.map(x => lastName(x.name));
  el.innerHTML = `<div class="calc">
    <label style="grid-column:1/-1">Your win probability: <b id="calc-p-label" style="color:var(--text)"></b>
      <input type="range" id="calc-p" min="1" max="99" step="0.5" value="${c.p}"></label>
    <label>${esc(na)} price at ${TARGET}<input id="calc-oa" inputmode="numeric" value="${esc(c.oa)}" placeholder="e.g. -150"></label>
    <label>${esc(nb)} price at ${TARGET}<input id="calc-ob" inputmode="numeric" value="${esc(c.ob)}" placeholder="e.g. +130"></label>
    <div class="calc-out" id="calc-out"></div>
  </div>
  <div class="note-line">Starts at ${esc(BASIS_LABEL[settings.basis] || BASIS_LABEL.market)}; drag to your own read, or type a live ${TARGET} price to check it mid-event. Prices are American odds.</div>`;
  const upd = () => {
    c.p = +$("#calc-p").value;
    c.oa = $("#calc-oa").value.trim();
    c.ob = $("#calc-ob").value.trim();
    const p = c.p / 100;
    $("#calc-p-label").textContent = `${na} ${c.p.toFixed(1)}% · ${nb} ${(100 - c.p).toFixed(1)}%`;
    const box = (name, prob, oddsStr) => {
      const o = parseFloat(String(oddsStr).replace("+", ""));
      if (!o || Math.abs(o) < 100) return `<div class="box"><b>${esc(name)}</b><div class="muted small">Enter a price</div></div>`;
      const e = evAt(prob, o), k = kellyAt(prob, o);
      return `<div class="box"><b>${esc(name)}</b> <span class="muted">at ${esc(fmtOdds(o))}</span>
        <dl class="kv"><dt>EV</dt><dd class="${e >= 0 ? "pos" : "neg"}">${signedPct(e)}</dd>
        <dt>Break-even</dt><dd>${pct(imp(o), 1)}</dd>
        <dt>Your fair price</dt><dd>${esc(fmtOdds(probToAm(prob)))}</dd>
        <dt>Stake</dt><dd>${e > 0 ? money(settings.bankroll * k * settings.kelly) : "—"}</dd></dl></div>`;
    };
    $("#calc-out").innerHTML = box(na, p, c.oa) + box(nb, 1 - p, c.ob);
  };
  el.querySelectorAll("input").forEach(i => i.oninput = () => { c.touched = true; upd(); });
  upd();
}

/* ---------- notes ---------- */
const inches = s => { if (!s) return null; const m = String(s).match(/(\d+)'\s*(\d+(?:\.\d+)?)?/); if (m) return +m[1] * 12 + (+m[2] || 0); const n = parseFloat(s); return isNaN(n) ? null : n; };
const ok = p => p && !p.loading && !p.error;

function renderNotes(f, A, B) {
  const el = $("#m-notes");
  if (!ok(A) || !ok(B)) { el.innerHTML = (A && A.error) || (B && B.error) ? `<div class="err">${esc((A.error || B.error))}</div>` : `<div class="skeleton"></div><div class="skeleton" style="margin-top:8px;width:70%"></div>`; return; }
  const P = [A, B], X = f.fighters, names = X.map(x => lastName(x.name)), side = ["red", "blue"];
  const notes = [];
  const add = (i, text) => notes.push({ cls: i === null ? "" : side[i], text });
  const fo = fightOdds(f);
  if (fo && fo.value && fo.value.sides && f.status.state !== "post") {
    [0, 1].forEach(i => {
      const t = fo.value.sides[i].target;
      if (t && t.ev >= settings.threshold) notes.push({ cls: "money", text: `${TARGET} has ${names[i]} at ${fmtOdds(t.odds)}; the market makes it ${fmtOdds(fo.value.sides[i].fairOdds)}. That's ${signedPct(t.ev)} expected value.` });
    });
    const bestA = fo.value.sides[0].best, bestB = fo.value.sides[1].best;
    [[0, bestA], [1, bestB]].forEach(([i, b]) => {
      const t = fo.value.sides[i].target;
      if (b && t && b.book !== TARGET && dec(b.odds) - dec(t.odds) >= 0.08) add(null, `${b.book} pays ${fmtOdds(b.odds)} on ${names[i]} vs ${fmtOdds(t.odds)} at ${TARGET}.`);
    });
  }
  const r = P.map(p => inches(p.reach)), h = P.map(p => inches(p.height));
  if (r[0] && r[1] && Math.abs(r[0] - r[1]) >= 2) { const i = r[0] > r[1] ? 0 : 1; add(i, `${names[i]} has a ${Math.abs(r[0] - r[1]).toFixed(1).replace(".0", "")}" reach advantage.`); }
  if (h[0] && h[1] && Math.abs(h[0] - h[1]) >= 3) { const i = h[0] > h[1] ? 0 : 1; add(i, `${names[i]} is ${Math.abs(h[0] - h[1]).toFixed(0)}" taller.`); }
  const ages = P.map(p => p.age);
  if (ages[0] && ages[1] && Math.abs(ages[0] - ages[1]) >= 5) { const i = ages[0] < ages[1] ? 0 : 1; add(i, `${names[i]} is ${Math.abs(ages[0] - ages[1])} years younger (${ages[i]} vs ${ages[1 - i]}).`); }
  P.forEach((p, i) => { if (p.age >= 36) add(1 - i, `${names[i]} is ${p.age}.`); });
  P.forEach((p, i) => {
    if (p.daysSinceLast >= 400) add(1 - i, `${names[i]} hasn't fought in ${Math.round(p.daysSinceLast / 30.4)} months.`);
    else if (p.daysSinceLast !== null && p.daysSinceLast <= 49) add(null, `${names[i]} is back after only ${p.daysSinceLast} days.`);
  });
  const C = P.map(p => p.career || {});
  const diff = C.map(c => c.slpm !== null && c.sapm !== null && c.slpm !== undefined ? c.slpm - c.sapm : null);
  if (diff[0] !== null && diff[1] !== null && Math.abs(diff[0] - diff[1]) >= 1) { const i = diff[0] > diff[1] ? 0 : 1; add(i, `${names[i]} out-lands opponents by ${diff[i] >= 0 ? "+" : ""}${diff[i].toFixed(2)}/min, vs ${diff[1 - i] >= 0 ? "+" : ""}${diff[1 - i].toFixed(2)} for ${names[1 - i]}.`); }
  [0, 1].forEach(i => {
    const o = 1 - i;
    if (C[i].tdAvg >= 1.5 && C[o].tdDef !== null && C[o].tdDef !== undefined && C[o].tdDef <= 70) add(i, `${names[i]} lands ${C[i].tdAvg} takedowns per 15 min; ${names[o]} stops only ${C[o].tdDef}% of attempts.`);
    if (C[i].subAvg >= 1 && P[o].summary.losses.sub >= 2) add(i, `${names[i]} attempts ${C[i].subAvg} subs per 15 min; ${names[o]} has ${P[o].summary.losses.sub} submission losses.`);
    if (P[i].summary.losses.ko >= 3) add(o, `${names[i]} has been stopped by strikes ${P[i].summary.losses.ko} times.`);
    const w = P[i].summary.wins, wt = w.ko + w.sub + w.dec + w.other;
    if (wt >= 5 && P[i].summary.finishRate >= 0.7) add(i, `${names[i]} finishes ${pct(P[i].summary.finishRate)} of wins (${w.ko} KO/TKO, ${w.sub} sub).`);
    if (wt >= 5 && P[i].summary.finishRate !== null && P[i].summary.finishRate <= 0.25) add(null, `${names[i]} goes the distance a lot: only ${pct(P[i].summary.finishRate)} of wins are finishes.`);
    if (P[i].summary.ufcFights === 0) add(null, `${names[i]} is making a UFC debut.`);
    const s = P[i].summary.streak;
    if (s && s[0] === "W" && +s.slice(1) >= 3) add(i, `${names[i]} has won ${s.slice(1)} straight.`);
    if (s && s[0] === "L" && +s.slice(1) >= 2) add(o, `${names[i]} has lost ${s.slice(1)} straight.`);
  });
  const uf = P.map(p => p.summary.ufcFights);
  if (Math.abs(uf[0] - uf[1]) >= 8) { const i = uf[0] > uf[1] ? 0 : 1; add(i, `Experience gap: ${uf[i]} UFC fights for ${names[i]} vs ${uf[1 - i]} for ${names[1 - i]}.`); }
  const st = P.map(p => p.stance);
  if (st[0] && st[1] && st[0] !== st[1]) add(null, `Stance matchup: ${names[0]} ${st[0].toLowerCase()}, ${names[1]} ${st[1].toLowerCase()}.`);
  el.innerHTML = notes.length ? `<ul class="notes">${notes.map(n => `<li class="${n.cls}">${esc(n.text)}</li>`).join("")}</ul>` : `<div class="muted">Nothing stands out on paper. This one is close.</div>`;
}

/* ---------- tale of the tape ---------- */
function renderTape(f, A, B) {
  const el = $("#m-tape");
  const X = f.fighters;
  const P = [A, B].map(p => ok(p) ? p : null);
  const val = (i, fn) => { try { const v = fn(P[i], X[i]); return v === undefined || v === null || v === "" ? "—" : v; } catch (e) { return "—"; } };
  const rows = [
    ["Pro record", p => p.summary.record, null],
    ["UFC record", p => p.summary.ufcRecord, null],
    ["Last 5", p => { const w = p.lastFive.filter(x => x.result === "W").length; return `${w}-${p.lastFive.length - w}`; }, p => p.lastFive.filter(x => x.result === "W").length],
    ["Streak", p => p.summary.streak, null],
    ["Age", (p, x) => p ? p.age : x.age, (p, x) => -(p ? p.age : x.age)],
    ["Height", (p, x) => (p && p.height) || x.height, (p, x) => inches((p && p.height) || x.height)],
    ["Reach", (p, x) => (p && p.reach) || x.reach, (p, x) => inches((p && p.reach) || x.reach)],
    ["Stance", (p, x) => (p && p.stance) || x.stance, null],
    ["Wins KO / Sub / Dec", p => `${p.summary.wins.ko} / ${p.summary.wins.sub} / ${p.summary.wins.dec}`, null],
    ["Losses KO / Sub / Dec", p => `${p.summary.losses.ko} / ${p.summary.losses.sub} / ${p.summary.losses.dec}`, null],
    ["Finish rate", p => pct(p.summary.finishRate), p => p.summary.finishRate],
    ["Last fight", p => p.daysSinceLast !== null ? `${p.daysSinceLast} days ago` : null, null],
    ["Gym", p => p.gym, null],
    ["Style", p => p.style, null],
  ];
  el.innerHTML = `<table class="tape">${rows.map(([lab, fn, adv]) => {
    let advIdx = -1;
    if (adv) {
      try {
        const a = adv(P[0], X[0]), b = adv(P[1], X[1]);
        if (a !== null && b !== null && !isNaN(a) && !isNaN(b) && a !== b) advIdx = a > b ? 0 : 1;
      } catch (e) { /* missing data */ }
    }
    return `<tr><td class="a${advIdx === 0 ? " adv" : ""}">${esc(val(0, fn))}</td><td class="lab">${esc(lab)}</td><td class="b${advIdx === 1 ? " adv" : ""}">${esc(val(1, fn))}</td></tr>`;
  }).join("")}</table>`;
}

/* ---------- stats ---------- */
function renderStats(f, A, B) {
  const el = $("#m-stats");
  const X = f.fighters;
  const P = [A, B];
  const car = i => (ok(P[i]) && P[i].career && P[i].career.slpm !== null && P[i].career.slpm !== undefined) ? P[i].career : null;
  const esp = i => X[i].espnStats || {};
  const get = (i, k) => { const c = car(i); if (c && c[k] !== null && c[k] !== undefined) return c[k]; const e = esp(i)[k]; return e === null || e === undefined ? null : e; };
  const rows = [
    ["Sig. strikes landed / min", "slpm", 1, 2, null],
    ["Sig. strike accuracy", "strAcc", 1, 0, 100],
    ["Sig. strikes absorbed / min", "sapm", -1, 2, null],
    ["Sig. strike defense", "strDef", 1, 0, 100],
    ["Strike differential / min", "diff", 1, 2, null],
    ["Takedowns / 15 min", "tdAvg", 1, 2, null],
    ["Takedown accuracy", "tdAcc", 1, 0, 100],
    ["Takedown defense", "tdDef", 1, 0, 100],
    ["Sub attempts / 15 min", "subAvg", 1, 1, null],
  ];
  const v = (i, k) => k === "diff" ? (get(i, "slpm") !== null && get(i, "sapm") !== null ? get(i, "slpm") - get(i, "sapm") : null) : get(i, k);
  const loading = [A, B].some(p => p && p.loading);
  let html = rows.map(([lab, k, better, d, max]) => {
    const a = v(0, k), b = v(1, k);
    if (a === null && b === null) return "";
    const m = max || Math.max(Math.abs(a || 0), Math.abs(b || 0), 0.01);
    const w = x => x === null ? 0 : Math.max(2, Math.min(100, Math.abs(x) / m * 100));
    const adv = a !== null && b !== null && a !== b ? ((a - b) * better > 0 ? 0 : 1) : -1;
    const fmt = x => x === null ? "—" : (max ? x.toFixed(d) + "%" : (k === "diff" && x > 0 ? "+" : "") + x.toFixed(d));
    return `<div class="stat-row"><span class="v a${adv === 0 ? " adv" : ""}">${fmt(a)}</span><div class="bar a"><span style="width:${w(a)}%"></span></div><span class="lab">${lab}</span><div class="bar b"><span style="width:${w(b)}%"></span></div><span class="v b${adv === 1 ? " adv" : ""}">${fmt(b)}</span></div>`;
  }).join("");
  // recent form: last five UFC fights from UFCStats
  const rec = P.map(p => ok(p) && p.recent ? p.recent : null);
  if (rec[0] || rec[1]) {
    const per = (r, k) => r && r.seconds ? r[k] / (r.seconds / 60) : null;
    const rrows = [
      ["Landed / min (last 5)", r => per(r, "sigFor"), 1, 2],
      ["Absorbed / min (last 5)", r => per(r, "sigAgainst"), -1, 2],
      ["Knockdowns for–against", r => r ? `${r.kdFor}–${r.kdAgainst}` : null, 0, 0],
      ["Takedowns for–against", r => r ? `${r.tdFor}–${r.tdAgainst}` : null, 0, 0],
    ];
    html += `<div class="section-title" style="padding:12px 0 4px">Recent form · last 5 UFC fights</div>` + rrows.map(([lab, fn, better, d]) => {
      const a = fn(rec[0]), b = fn(rec[1]);
      if (better === 0) return `<div class="stat-row"><span class="v a">${esc(a ?? "—")}</span><span></span><span class="lab">${lab}</span><span></span><span class="v b">${esc(b ?? "—")}</span></div>`;
      const m = Math.max(a || 0, b || 0, 0.01);
      const adv = a !== null && b !== null && a !== b ? ((a - b) * better > 0 ? 0 : 1) : -1;
      return `<div class="stat-row"><span class="v a${adv === 0 ? " adv" : ""}">${a === null ? "—" : a.toFixed(d)}</span><div class="bar a"><span style="width:${a === null ? 0 : a / m * 100}%"></span></div><span class="lab">${lab}</span><div class="bar b"><span style="width:${b === null ? 0 : b / m * 100}%"></span></div><span class="v b${adv === 1 ? " adv" : ""}">${b === null ? "—" : b.toFixed(d)}</span></div>`;
    }).join("");
  }
  const src = [0, 1].map(i => car(i) ? "UFCStats" : "ESPN");
  el.innerHTML = (html || (loading ? `<div class="skeleton"></div>` : `<div class="muted">No UFC stats yet for either fighter.</div>`)) +
    `<div class="stat-help">Per-minute rates over each fighter's UFC career${src[0] !== src[1] || src[0] === "ESPN" ? ` (source: ${esc(lastName(X[0].name))} ${src[0]}, ${esc(lastName(X[1].name))} ${src[1]})` : ""}. Highlighted = better.</div>`;
}

/* ---------- last five ---------- */
function fightItem(e) {
  const res = e.result || "?";
  let odds = "";
  if (e.odds && e.odds.close !== null && e.odds.close !== undefined) {
    const c = e.odds.close;
    odds = `<span class="fi-odds">closed <b>${esc(fmtOdds(c))}</b> ${c < 0 ? "fav" : "dog"}</span>`;
  }
  const st = e.stats;
  let stats = "";
  if (st && st.source === "ufcstats") {
    const pair = (lab, p) => p && p[0] !== null ? `<span>${lab} <b>${p[0]}</b>–${p[1] ?? "?"}</span>` : "";
    stats = pair("Sig", st.sig) + pair("TD", st.td) + pair("KD", st.kd) + (st.subAtt && (st.subAtt[0] || st.subAtt[1]) ? pair("Sub att", st.subAtt) : "");
  } else if (st) {
    stats = (st.sig && st.sig[0] !== null ? `<span>Sig <b>${st.sig[0]}</b>/${st.sigAtt ?? "?"}</span>` : "") + (st.td && st.td[0] !== null ? `<span>TD <b>${st.td[0]}</b>/${st.tdAtt ?? "?"}</span>` : "") + (st.kd ? `<span>KD <b>${st.kd[0]}</b></span>` : "");
  }
  const method = [e.method || "", e.methodDetail ? `(${e.methodDetail})` : ""].join(" ").trim();
  const when = e.round ? `R${e.round} ${e.time || ""}` : "";
  return `<div class="fight-item">
    <div class="fi-top"><span class="badge ${esc(res)}">${esc(res)}</span><span class="fi-opp" title="${esc(e.opponent.name)}">${esc(e.opponent.name || "Unknown")}</span>${odds}</div>
    <div class="fi-method">${esc(method)}${when ? ` · ${esc(when)}` : ""}${e.title ? ` <span class="badge title">Title</span>` : ""}</div>
    ${stats ? `<div class="fi-stats">${stats}</div>` : ""}
    <div class="fi-meta" title="${esc(e.event)}">${esc(fmtDate(e.date))} · ${esc(e.event || "")}${e.ufc ? "" : " (non-UFC)"}</div>
  </div>`;
}

function renderLastFive(f, A, B) {
  const el = $("#m-l5");
  const col = (p, x, i) => {
    let body;
    if (!p || p.loading) body = `<div class="skeleton" style="height:70px"></div><div class="skeleton" style="height:70px;margin-top:8px"></div>`;
    else if (p.error) body = `<div class="err">${esc(p.error)}</div>`;
    else if (!p.lastFive.length) body = `<div class="muted small">No previous pro fights on record.</div>`;
    else body = p.lastFive.map(fightItem).join("") + (p.lastFive.length < 5 ? `<div class="muted small">Only ${p.lastFive.length} prior pro fight${p.lastFive.length > 1 ? "s" : ""} on record.</div>` : "");
    const rec = ok(p) ? `${p.lastFive.filter(e => e.result === "W").length}-${p.lastFive.filter(e => e.result === "L").length}` : "";
    return `<div class="l5-col ${i ? "blue" : "red"}"><h4><span>${esc(x.name)}</span><span class="muted">${esc(rec)}</span></h4>${body}</div>`;
  };
  el.innerHTML = `<div class="l5-grid">${col(A, f.fighters[0], 0)}${col(B, f.fighters[1], 1)}</div>
    <div class="stat-help">Sig/TD/KD shown as fighter–opponent. Closing line from BestFightOdds (fav = favorite, dog = underdog).</div>`;
}

/* ---------- props ---------- */
function renderProps(f) {
  const el = $("#m-props");
  const fo = fightOdds(f);
  if (!S.odds) { el.innerHTML = `<div class="skeleton"></div>`; return; }
  const props = (fo && fo.props) || [];
  if (!props.length) {
    el.innerHTML = `<div class="muted">${TARGET} hasn't posted props for this fight yet (method, rounds and distance props usually go up fight week).</div>`;
    $("#m-props-meta").textContent = "";
    return;
  }
  const show = S.showAllProps ? props : props.slice(0, 10);
  const actionable = f.status.state !== "post";
  const hasModel = !!modelFor(f);
  el.innerHTML = `<div style="overflow-x:auto"><table class="props-table"><thead><tr><th>Bet</th><th>${TARGET}</th><th>Fair</th><th>EV</th>${hasModel ? "<th>Model</th><th>Model EV</th>" : ""}<th>Other books</th></tr></thead><tbody>
    ${show.map(p => {
      const mp = hasModel ? propModelProb(p, f) : null;
      const mev = mp !== null ? evAt(mp, p.odds) : null;
      const useEv = settings.basis === "market" ? p.ev : (mev !== null ? mev : p.ev);
      const val = actionable && useEv !== null && useEv >= settings.threshold;
      const modelCells = hasModel ? `<td>${mp !== null ? esc(fmtOdds(probToAm(mp))) : "—"}</td><td>${mev !== null ? `<span class="${mev >= 0 ? "pos" : "neg"}">${signedPct(mev)}</span>` : "—"}</td>` : "";
      const evCell = p.ev !== null ? `<span class="${p.ev >= 0 ? "pos" : "neg"}">${signedPct(p.ev)}</span>` :
        (p.vsMarket !== null ? `<span class="muted" title="No two-way market to strip the vig from; this compares ${TARGET}'s payout with the median of other books.">${p.vsMarket >= 0 ? "pays +" : "pays "}${(p.vsMarket * 100).toFixed(0)}%</span>` : "—");
      return `<tr class="${val ? "value" : ""}"><td>${esc(p.label)}</td><td><b>${esc(fmtOdds(p.odds))}</b></td><td>${p.fairOdds !== null ? esc(fmtOdds(p.fairOdds)) : "—"}</td><td>${evCell}</td>${modelCells}<td class="muted">${p.market !== null ? `${esc(fmtOdds(p.market))} med · ` : ""}${p.best ? `${esc(fmtOdds(p.best.odds))} ${esc(p.best.book)}` : ""}</td></tr>`;
    }).join("")}</tbody></table></div>
    ${props.length > 10 ? `<button class="link-btn" id="props-more" style="margin-top:8px">${S.showAllProps ? "Show top 10" : `Show all ${props.length}`}</button>` : ""}
    <div class="stat-help">Sorted by market EV. "Fair" strips the vig from other books' two-way prices; one-sided props compare ${TARGET} with the median other book instead.${hasModel ? ` "Model" prices the prop from the model's method and round breakdown.` : ""}</div>`;
  const more = $("#props-more");
  if (more) more.onclick = () => { S.showAllProps = !S.showAllProps; renderProps(f); };
  $("#m-props-meta").textContent = `${props.length} priced`;
}

function renderSources(f) {
  const fo = fightOdds(f);
  const bits = ["Card & live status: ESPN", "Career stats: UFCStats", "History: ESPN + UFCStats"];
  if (fo && fo.bfoUrl) bits.push(`Lines: <a href="${esc(fo.bfoUrl)}" target="_blank" rel="noopener">BestFightOdds</a>`);
  else if (fo && fo.source === "espn") bits.push("Lines: ESPN (DraftKings)");
  $("#m-sources").innerHTML = bits.join(" · ");
}

/* ---------- settings ---------- */
function setupSettings() {
  const dlg = $("#settings");
  $("#settings-btn").onclick = () => {
    $("#set-bankroll").value = settings.bankroll;
    $("#set-kelly").value = String(settings.kelly);
    $("#set-threshold").value = String(settings.threshold);
    $("#set-format").value = settings.format;
    $("#set-basis").value = settings.basis;
    dlg.showModal();
  };
  dlg.addEventListener("close", () => {
    settings.bankroll = Math.max(0, +$("#set-bankroll").value || 0);
    settings.kelly = +$("#set-kelly").value;
    settings.threshold = +$("#set-threshold").value;
    settings.format = $("#set-format").value;
    settings.basis = $("#set-basis").value;
    store.set("fa-settings", settings);
    renderList();
    if (currentFight()) { renderMatchup(); }
  });
}

/* ---------- boot ---------- */
async function boot() {
  setupSettings();
  setupSeasons();
  const h = readHash();
  if (h.fight && isMobile()) document.body.classList.add("show-matchup");
  try {
    const id = await loadEvents(null, h.event);
    if (!id) { $("#card-list").innerHTML = `<div class="empty">No events found.</div>`; return; }
    selectEvent(id, h.fight);
  } catch (e) {
    $("#card-list").innerHTML = `<div class="empty">Couldn't reach the server.<br><span class="err">${esc(e.message)}</span></div>`;
  }
  $("#event-select").onchange = e => { S.fightId = null; document.body.classList.remove("show-matchup"); selectEvent(e.target.value); writeHash(false); };
  window.addEventListener("popstate", () => {
    const hh = readHash();
    if (hh.event && hh.event !== S.eventId) { $("#event-select").value = hh.event; selectEvent(hh.event, hh.fight); return; }
    if (hh.fight) { S.fightId = hh.fight; document.body.classList.add("show-matchup"); renderList(); renderMatchup(); }
    else document.body.classList.remove("show-matchup");
  });
  document.addEventListener("visibilitychange", () => {
    if (document.hidden || !S.card) return;
    if (Date.now() - S.cardAt > 20000 && cardDelay()) loadCard(false);
    if (S.card.state !== "post" && Date.now() - S.oddsAt > 60000) loadOdds();
  });
  setInterval(renderStatus, 1000);
}
boot();
