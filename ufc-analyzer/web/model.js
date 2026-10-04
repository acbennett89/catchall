"use strict";
/* Model predictions: loading, the matchup's model panel, and model prices for Caesars props.
   Loaded before app.js; uses its helpers (esc, pct, fmtOdds, ...) only at call time. */

async function loadPred() {
  const id = S.eventId;
  try {
    const p = await api(`/api/predict/${id}`);
    if (id !== S.eventId) return;
    S.pred = p; S.predAt = Date.now(); S.predErr = null;
    renderList();
    updateMatchup(true);
  } catch (e) {
    S.predErr = e.message;
  }
}

function modelFor(f) {
  const p = S.pred && S.pred.available && S.pred.fights ? S.pred.fights[f.id] : null;
  return p && !p.error && !p.suppressed ? p : null;
}

const BASIS_LABEL = { market: "the no-vig market price", model: "the model", blend: "the market + model blend" };

/* Caesars EV for side i measured against the chosen basis (falls back to the market). */
function basisEv(f, fo, i) {
  const pr = modelFor(f);
  if (settings.basis === "model" && pr && pr.sides && pr.sides[i] && pr.sides[i].evModel !== undefined) return pr.sides[i].evModel;
  if (settings.basis === "blend" && pr && pr.sides && pr.sides[i] && pr.sides[i].evBlend !== undefined) return pr.sides[i].evBlend;
  return sideEv(fo, i);
}

/* Win probability for side A under the chosen basis (null when unavailable). */
function basisProb(f) {
  const pr = modelFor(f);
  const fo = fightOdds(f);
  if (settings.basis === "model" && pr) return pr.p[0];
  if (settings.basis === "blend" && pr && pr.blend) return pr.blend[0];
  return fo && fo.value && fo.value.fair ? fo.value.fair[0] : (pr ? pr.p[0] : null);
}

function renderModel(f) {
  const el = $("#m-model");
  if (!el) return;
  if (!S.pred) { el.innerHTML = S.predErr ? `<div class="err">${esc(S.predErr)}</div>` : `<div class="skeleton" style="height:90px"></div>`; return; }
  if (!S.pred.available) { el.innerHTML = `<div class="muted">The prediction model isn't installed (model/model.json is missing).</div>`; return; }
  const pr = S.pred.fights && S.pred.fights[f.id];
  if (!pr) { el.innerHTML = `<div class="muted">No prediction for this fight.</div>`; return; }
  if (pr.error) { el.innerHTML = `<div class="err">Couldn't score this fight: ${esc(pr.error)}</div>`; return; }
  if (pr.suppressed) { el.innerHTML = `<div class="muted">${esc(pr.suppressed)}</div>`; return; }
  const names = f.fighters.map(x => x.name);
  const ln = names.map(lastName);
  const actionable = f.status.state === "pre";   // the moneylines are pre-fight prices
  const fo = fightOdds(f);
  const mkt = fo && fo.value && fo.value.fair;
  const d = pr.decision || {};
  const sides = [0, 1].map(i => {
    const s = (pr.sides || [])[i] || {};
    // VALUE and a stake only where the BET rule says BET; on the Model basis (your explicit choice) the raw
    // model's EV drives them instead.  Both EVs are shown either way.
    const useModel = settings.basis === "model";
    const ev = useModel ? s.evModel : s.evBlend;
    const kel = useModel ? s.kellyModel : d.kelly;
    const isValue = actionable && (useModel ? ev !== undefined && ev >= settings.threshold : d.action === "BET" && d.side === i);
    return `<div class="odds-side ${i ? "blue" : "red"}${isValue ? " value" : ""}">
      <div class="os-top"><span class="os-name">${esc(names[i])}</span><span class="os-book">Model</span></div>
      <div class="os-price">${pct(pr.p[i], 0)}${isValue ? ` <span class="badge good" style="vertical-align:middle">VALUE</span>` : ""}</div>
      <dl class="kv tight">
        <dt>Model fair price</dt><dd>${esc(fmtOdds(pr.fair[i]))}</dd>
        <dt>Market fair</dt><dd>${mkt ? pct(mkt[i], 1) : "—"}</dd>
        ${pr.blend ? `<dt>Blend</dt><dd>${pct(pr.blend[i], 1)}</dd>` : ""}
        ${s.evModel !== undefined ? `<dt>EV at ${TARGET} (model)</dt><dd class="${s.evModel >= 0 ? "pos" : "neg"}">${signedPct(s.evModel)}</dd>` : ""}
        ${s.evBlend !== undefined ? `<dt>EV at ${TARGET} (blend)</dt><dd class="${s.evBlend >= 0 ? "pos" : "neg"}">${signedPct(s.evBlend)}</dd>` : ""}
        ${isValue && kel > 0 ? `<dt>Stake (${Math.round(settings.kelly * 100)}% Kelly)</dt><dd>${money(stakeFor(kel))}</dd>` : ""}
        <dt>Elo rating</dt><dd>${esc(pr.elo ? pr.elo[i] : "—")}</dd>
      </dl></div>`;
  }).join("");
  let gap = "";
  if (mkt) {
    const d = pr.p[0] - mkt[0];
    const who = d > 0 ? ln[0] : ln[1];
    gap = Math.abs(d) < 0.02 ? `<div class="note-line">The model agrees with the market (within 2 points).</div>`
      : `<div class="note-line">The model is <b>${(Math.abs(d) * 100).toFixed(0)} points</b> higher on ${esc(who)} than the market.</div>`;
  }
  // method of victory
  let method = "";
  const m = pr.method;
  if (m) {
    const row = (lab, k) => `<tr><td>${lab}</td><td>${pct(m.a[k], 0)}</td><td>${pct(m.b[k], 0)}</td></tr>`;
    const wins = t => t.ko + t.sub + t.dec;   // the rows above, so the column adds up (a draw is the rest)
    method = `<table class="books-table"><thead><tr><th>Outcome</th><th>${esc(ln[0])}</th><th>${esc(ln[1])}</th></tr></thead><tbody>
      ${row("KO/TKO", "ko")}${row("Submission", "sub")}${m.a.dec_u !== undefined ? row("Unanimous decision", "dec_u") + row("Split/majority decision", "dec_s") : row("Decision", "dec")}
      <tr class="target"><td>Wins</td><td>${pct(wins(m.a), 0)}</td><td>${pct(wins(m.b), 0)}</td></tr></tbody></table>
      <div class="note-line">Goes the distance: <b>${pct(m.distance, 0)}</b>${m.draw ? ` (draw ${pct(m.draw, 1)})` : ""}${m.over_under ? " · " + m.over_under.filter(o => o.line < f.rounds).map(o => `O/U ${o.line}: ${pct(o.over, 0)} / ${pct(o.under, 0)}`).join(" · ") : ""}</div>`;
    if (m.rounds) {
      method += `<details><summary>Finish by round</summary><table class="books-table"><thead><tr><th>Round</th><th>${esc(ln[0])}</th><th>${esc(ln[1])}</th></tr></thead><tbody>
        ${m.rounds.map(r => `<tr><td>Round ${r.round}</td><td>${pct(r.a, 1)}</td><td>${pct(r.b, 1)}</td></tr>`).join("")}</tbody></table></details>`;
    }
  }
  // drivers
  let drivers = "";
  if (pr.drivers && pr.drivers.length) {
    const max = Math.max(...pr.drivers.map(d => Math.abs(d.logit)), 0.01);
    drivers = `<div class="section-title" style="padding:12px 0 6px">What's driving it</div>` + pr.drivers.map(d => {
      const w = Math.abs(d.logit) / max * 100;
      return `<div class="stat-row"><span class="v a">${d.favors === 0 ? "◀" : ""}</span>
        <div class="bar a"><span style="width:${d.favors === 0 ? w : 0}%"></span></div>
        <span class="lab">${esc(d.label)}</span>
        <div class="bar b"><span style="width:${d.favors === 1 ? w : 0}%"></span></div><span class="v b">${d.favors === 1 ? "▶" : ""}</span></div>`;
    }).join("");
  }
  const flags = (pr.flags || []).map(x => `<div class="note-line">⚠ ${esc(x.text)}</div>`).join("");
  const g = pr.blendState || {};
  const away = g.hours >= 48 ? `${Math.floor(g.hours / 24)} days` : `${Math.round(g.hours || 0)} hours`;   // floor: "4 days" means 96+ hours
  // which blend applies: the early-line blend a week or more out, the closing-line blend inside 12 hours, a mix between
  const moved = mkt && pr.blend ? ` Here it moves ${esc(ln[0])} ${(pr.blend[0] - mkt[0] >= 0 ? "+" : "−")}${Math.abs((pr.blend[0] - mkt[0]) * 100).toFixed(1)} points.` : "";
  const early = (g.hours || 0) >= 96;
  const canBet = early && g.openGate && !g.lowExperience;   // what decide() allows for a blend-only edge
  const betNote = canBet ? "a blend edge can be a BET until 4 days out"
    : g.lowExperience ? "a fighter has under 2 UFC fights, so only market value can be a BET here"
    : early ? "the early-line blend isn't live, so only market value can be a BET" : "inside 4 days only market value is a BET";
  const which = g.wOpen >= 0.999 ? `on early lines the blend (market plus model) beat the market in testing; ${betNote}`
    : g.wOpen <= 0.001 ? `on closing lines the blend edged the market only slightly in testing, mostly by firming up favorites; ${betNote}`
    : `mixing the early-line blend (${Math.round(g.wOpen * 100)}%) with the weaker closing-line blend as fight night nears; ${betNote}`;
  const gateNote = pr.blend ? `<div class="note-line">${g.active
      ? `Blend is live (${away} out): ${which}.${g.lowExperience ? " The model also counts for less in the blend when a fighter has under 2 UFC fights." : ""}${moved}`
      : `Blend = market (${away} out): the model hasn't beaten the market this close to the fight in testing, so it doesn't move the price.`}</div>` : "";
  el.innerHTML = `${decisionBox(pr, f)}<div class="odds-grid">${sides}</div>${gap}${gateNote}${flags}
    <div class="section-title" style="padding:12px 0 6px">How it ends${pr.methodAnchor && pr.methodAnchor !== "model" ? ` <span class="faint" style="text-transform:none;letter-spacing:0">(scaled to the ${pr.methodAnchor === "blend" ? "blended" : "market"} win chance)</span>` : ""}</div>${method}${drivers}
    ${trackRecord()}`;
  const logBtn = $("#log-bet");
  if (logBtn) logBtn.onclick = () => logBet(f, pr);
  const meta = $("#m-model-meta");
  if (meta) meta.textContent = S.pred.model && S.pred.model.trained_through ? `history through ${S.pred.model.trained_through}` : "";
}

/* How the model and the app's BET rule have done on fights they never saw, from model.json (test years;
   the rule itself was chosen on the validation years). */
function trackRecord() {
  const M = S.pred && S.pred.model;
  const T = M && M.evaluation && M.evaluation.test;
  if (!T || !T.with_market) return "";
  const wm = T.with_market, st = M.stack || {}, bt = (M.backtest || {}).test || {}, bv = (M.backtest || {}).val || {};
  const sr = bt.served_rule || {}, sv = bv.served_rule || {};
  const acc = x => x ? pct(x.accuracy, 1) : "—";
  const ll = x => x ? x.log_loss.toFixed(3) : "—";
  const ci = x => x && x.ci ? ` (95% range ${x.ci[0] >= 0 ? "+" : ""}${x.ci[0].toFixed(3)} to ${x.ci[1] >= 0 ? "+" : ""}${x.ci[1].toFixed(3)})` : "";
  const roi = r => `${r.bets.toLocaleString()} bets, ROI ${signedPct(r.roi, 1)} (95% range ${signedPct(r.roi_ci[0], 0)} to ${signedPct(r.roi_ci[1], 0)})`;
  const gateLine = (anchor, label) => {
    const g = st[anchor];
    if (!g) return "";
    return `<li>${label}: blend minus market log loss ${g.test_minus_market ? g.test_minus_market.est.toFixed(4) : "—"}${ci(g.test_minus_market)}; ${g.gate ? "<b>live</b> (it beat the market on 2016–20 and held up since)" : "not live (it didn't beat the market on 2016–20)"}.</li>`;
  };
  const e = sr.early_open, ev = sv.early_open, fw = sr.fight_week_best, syn = sr.fight_week_blend_synthetic;
  const raw = bt.open && bt.open.raw_model;
  return `<details class="track"><summary>Track record: ${esc(T.years)}, ${T.model ? T.model.n.toLocaleString() : "?"} fights it never saw</summary>
    <div class="note-line">On ${wm.model ? wm.model.n.toLocaleString() : "?"} of them with betting history: model alone ${acc(wm.model)} right (log loss ${ll(wm.model)}),
      opening line ${acc(wm.market_open)} (${ll(wm.market_open)}), closing line ${acc(wm.market_close)} (${ll(wm.market_close)}). Lower log loss is better: the model alone loses to both, so it only ever moves the market price a little.</div>
    <ul class="small muted" style="margin:6px 0 0 18px;padding:0">
      ${gateLine("open", "Blend on early lines")}${gateLine("close", "Blend on closing lines")}
      ${e && e.bets ? `<li><b>This app's BET rule 4+ days out</b> (blend edge, both fighters with 2+ UFC fights), at historical opening prices: ${roi(e)}${e.clv ? `; the closing line moved toward the pick on ${pct(e.clv.beat_close, 0)} of them (CLV ${signedPct(e.clv.mean, 1)})` : ""}.${ev && ev.bets ? ` The rule was picked on 2016–20 (${roi(ev)}).` : ""}</li>` : ""}
      ${fw && fw.bets ? `<li>Inside 4 days only market value is a BET. There's no ${TARGET} price history, so the best price across books stands in (a ceiling): ${roi(fw)}.</li>` : ""}
      ${syn && syn.bets ? `<li>Blend bets at closing prices with a ${TARGET}-like 4.4% margin: ${roi(syn)}. Not a reliable edge, which is why fight-week blend edges stay WATCH.</li>` : ""}
      ${raw && raw.bets ? `<li>Model alone at opening prices: ${roi(raw)}. Don't bet the raw model.</li>` : ""}
    </ul>
    <div class="note-line">Opening prices are an upper bound: they're often one small book's first number, and ${TARGET}'s early lines may already have moved. The forward ledger (top right) is the real test.</div></details>`;
}

/* Model probability for a Caesars prop label ("Silva wins by TKO/KO", "Over 2½ rounds", ...),
   computed from the fight's outcome table (method x round per fighter, decisions, draw). */
function propModelProb(p, f) {
  const pr = modelFor(f);
  if (!pr || !pr.method || !pr.method.a) return null;
  if (f.status && f.status.state === "in") return null;   // a pre-fight table says nothing once rounds have gone by
  const m = pr.method;
  const R = m.rounds_scheduled || (m.rounds ? m.rounds.length : f.rounds);
  const norm = n => (n || "").toLowerCase().normalize("NFKD").replace(/[\u0300-\u036f]/g, "");
  const tokensOf = n => norm(n).split(/[^a-z0-9]+/).filter(t => t.length >= 2);
  const toks = f.fighters.map(x => tokensOf(x.name));
  const sideOf = who => {
    const w = tokensOf(who);
    const hit = [0, 1].filter(i => w.length && w.every(t => toks[i].includes(t)));
    return hit.length === 1 ? hit[0] : null;
  };
  const T = i => (i === 0 ? m.a : m.b);
  const sum = a => a.reduce((x, y) => x + y, 0);
  const winRound = (i, r) => (T(i).ko_r ? T(i).ko_r[r - 1] + T(i).sub_r[r - 1] : (m.rounds[r - 1] || {})[i === 0 ? "a" : "b"]);
  const endsIn = r => winRound(0, r) + winRound(1, r);
  const ou = line => (m.over_under || []).find(o => Math.abs(o.line - line) < 1e-6);
  const rounds = str => str.split(/\s*(?:or|,)\s*/).map(Number).filter(n => n >= 1 && n <= R);
  const one = label => {
    const L = norm(label.replace(/½/g, ".5")).replace(/\s+/g, " ").trim();  // before NFKD, which splits "½"
    let x;
    if ((x = L.match(/^either fighter wins by (?:tko\/ko|ko\/tko|ko)$/))) return m.a.ko + m.b.ko;
    if ((x = L.match(/^either fighter wins by submission$/))) return m.a.sub + m.b.sub;
    if (/^fight is a draw$/.test(L)) return m.draw || 0;
    if (/^fight is not a draw$/.test(L)) return 1 - (m.draw || 0);
    if (/^fight goes to (?:a )?decision$/.test(L) || /^fight goes the distance$/.test(L)) return m.distance;
    if (/^fight doesn'?t go to (?:a )?decision$/.test(L) || /^fight doesn'?t go the distance$/.test(L)) return 1 - m.distance;
    if ((x = L.match(/^(over|under) (\d(?:\.5)?) rounds$/))) { const o = ou(+x[2]); return o ? (x[1] === "over" ? o.over : o.under) : null; }
    if ((x = L.match(/^fight ends in round ([\d ,or]+)$/))) { const rs = rounds(x[1]); return rs.length ? sum(rs.map(endsIn)) : null; }
    if ((x = L.match(/^fight doesn'?t end in round (\d)$/))) return 1 - endsIn(+x[1]);
    if ((x = L.match(/^fight (won'?t )?starts? round (\d)$/))) { const before = sum(Array.from({ length: +x[2] - 1 }, (_, k) => endsIn(k + 1))); return x[1] ? before : 1 - before; }
    if (/^fight ends in (?:the )?final round or goes to decision$/.test(L)) return endsIn(R) + m.distance;
    if ((x = L.match(/^(.+?) wins by (?:tko\/ko|ko\/tko|ko|tko) in round (\d)$/))) { const i = sideOf(x[1]); return i === null || !T(i).ko_r ? null : T(i).ko_r[+x[2] - 1]; }
    if ((x = L.match(/^(.+?) wins by submission in round (\d)$/))) { const i = sideOf(x[1]); return i === null || !T(i).sub_r ? null : T(i).sub_r[+x[2] - 1]; }
    if ((x = L.match(/^(.+?) wins by (?:tko\/ko|ko\/tko|ko|tko)$/))) { const i = sideOf(x[1]); return i === null ? null : T(i).ko; }
    if ((x = L.match(/^(.+?) wins by submission$/))) { const i = sideOf(x[1]); return i === null ? null : T(i).sub; }
    if ((x = L.match(/^(.+?) wins by unanimous decision$/))) { const i = sideOf(x[1]); return i === null || T(i).dec_u === undefined ? null : T(i).dec_u; }
    if ((x = L.match(/^(.+?) wins by (?:split|majority|split\/majority) decision$/))) { const i = sideOf(x[1]); return i === null || T(i).dec_s === undefined ? null : T(i).dec_s; }
    if ((x = L.match(/^(.+?) wins by decision$/))) { const i = sideOf(x[1]); return i === null ? null : T(i).dec; }
    if ((x = L.match(/^(.+?) wins inside (?:the )?distance$/))) { const i = sideOf(x[1]); return i === null ? null : T(i).ko + T(i).sub; }
    if ((x = L.match(/^not (.+?) inside (?:the )?distance$/))) { const i = sideOf(x[1]); return i === null ? null : 1 - T(i).ko - T(i).sub; }
    if ((x = L.match(/^not (.+?) by decision$/))) { const i = sideOf(x[1]); return i === null ? null : 1 - T(i).dec; }
    if ((x = L.match(/^(.+?) wins in (?:the )?final round or by decision$/))) { const i = sideOf(x[1]); return i === null ? null : winRound(i, R) + T(i).dec; }
    if ((x = L.match(/^(.+?) wins in round ([\d ,or]+)$/))) { const i = sideOf(x[1]); const rs = rounds(x[2]); return i === null || !rs.length ? null : sum(rs.map(r => winRound(i, r))); }
    return null;
  };
  let v = one(p.label);
  if (v === null && /^any other result$/i.test(p.label) && p.other) {
    const o = one(p.other);
    v = o === null ? null : 1 - o;
  }
  return v === null || isNaN(v) ? null : Math.min(0.995, Math.max(0.005, v));
}

/* Stake suggestion: fractional Kelly, capped at 1.5% of bankroll per bet. */
function stakeFor(kelly) {
  const raw = settings.bankroll * kelly * settings.kelly;
  return Math.min(raw, settings.bankroll * 0.015);
}

function decisionBox(pr, f) {
  const d = pr.decision;
  if (!d || f.status.state !== "pre") return "";
  const cls = d.action === "BET" ? "good" : d.action === "WATCH" ? "title" : "";
  const who = d.side !== undefined ? esc(f.fighters[d.side].name) : "";
  const stake = d.action === "BET" && d.kelly ? ` · stake ${money(stakeFor(d.kelly))}` : "";
  return `<div class="decision ${d.action.toLowerCase()}"><span class="badge ${cls}">${d.action}</span>${d.tier ? ` <span class="small muted">${esc(d.tier)}</span>` : ""}
    ${d.side !== undefined ? `<b>${who}</b>` : ""}${d.ev !== undefined ? ` <span class="${d.ev >= 0 ? "pos" : "neg"}">${signedPct(d.ev)}</span>` : ""}${stake}
    <ul>${(d.reasons || []).map(r => `<li>${esc(r)}</li>`).join("")}</ul>
    ${d.side !== undefined ? `<button class="link-btn" id="log-bet">I bet this</button>` : ""}</div>`;
}

/* ---------- ledger ---------- */
async function logBet(f, pr) {
  const d = pr.decision;
  const side = d.side;
  const cz = pr.sides && pr.sides[side] && pr.sides[side].caesars;
  const price = window.prompt(`Price you got on ${f.fighters[side].name} at ${TARGET} (American odds):`, cz !== undefined ? String(cz) : "");
  if (price === null || isNaN(parseFloat(price)) || Math.abs(parseFloat(price)) < 100) return;
  const suggested = d.action === "BET" && d.kelly ? stakeFor(d.kelly).toFixed(2) : "";
  const stake = window.prompt("Stake ($, optional):", suggested);
  if (stake === null) return;
  const q = new URLSearchParams({ event: S.eventId, fight: f.id, side, price: parseFloat(price) });
  if (stake && !isNaN(parseFloat(stake))) q.set("stake", parseFloat(stake));
  try {
    const r = await api(`/api/ledger/add?${q}`);
    window.alert(r.ok ? "Logged. Open the ledger (top right) to track it against the closing line." : "Couldn't log it (the fight may have started).");
  } catch (e) { window.alert(`Couldn't log it: ${e.message}`); }
}

async function openLedger() {
  const dlg = $("#ledger"), body = $("#ledger-body");
  body.innerHTML = `<div class="loading">Loading…</div>`;
  dlg.showModal();
  try {
    const d = await api("/api/ledger");
    body.innerHTML = renderLedger(d);
    body.querySelectorAll("[data-remove]").forEach(b => b.onclick = async () => {
      if (!window.confirm("Remove this entry?")) return;
      await api(`/api/ledger/remove?id=${encodeURIComponent(b.dataset.remove)}`);
      openLedger();
    });
  } catch (e) { body.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}

function renderLedger(d) {
  const s = d.summary || {};
  const line = (lab, x) => x && x.entries ? `<tr><td>${lab}</td><td>${x.entries}</td><td>${x.clv !== null ? signedPct(x.clv, 1) : "—"}</td><td>${x.beatClose !== null ? pct(x.beatClose, 0) : "—"}</td><td>${x.settled}</td><td>${x.roi !== null ? signedPct(x.roi, 1) : "—"}</td></tr>` : "";
  const rows = (d.entries || []).map(e => `<tr>
      <td class="nowrap">${esc(new Date(e.ts * 1000).toLocaleDateString(undefined, { month: "short", day: "numeric" }))}</td><td title="${esc(e.eventName || "")}">${esc(e.fighters[e.side])} <span class="faint">vs ${esc(lastName(e.fighters[1 - e.side]))}</span></td>
      <td>${esc(fmtOdds(e.price))}</td><td>${esc(e.source === "user" ? "your bet" : e.action)}${e.tier ? `<br><span class="faint">${esc(e.tier)}</span>` : ""}</td>
      <td>${e.closeFair !== null ? esc(fmtOdds(probToAm(e.closeFair)))
        : !e.started && e.fairNow != null ? `<span class="faint" title="Market now; the close is taken when the fight starts">${esc(fmtOdds(probToAm(e.fairNow)))} now</span>`
        : e.started ? `<span class="faint" title="No price seen within an hour of the start">missed</span>` : "—"}</td>
      <td class="${e.clv > 0 ? "pos" : e.clv < 0 ? "neg" : ""}">${e.clv !== null ? signedPct(e.clv, 1) : "—"}</td>
      <td>${esc(e.result || "open")}${e.profit !== null && e.profit !== undefined ? ` <span class="${e.profit >= 0 ? "pos" : "neg"}">${e.profit >= 0 ? "+" : ""}${e.profit}</span>` : ""}</td>
      <td>${e.source === "user" ? `<button class="link-btn" data-remove="${esc(e.id)}">✕</button>` : ""}</td></tr>`).join("");
  return `<p class="fine">Every ${TARGET} price the app flags is logged the first time it's flagged as WATCH and again if it becomes a BET, plus the bets you log. Once the fight starts, each is checked against the last consensus price the app saw (closing-line value), then the result. Positive CLV over a few hundred bets is the clearest sign of a real edge; ROI takes thousands. Keep the server running into fight night so it sees the close.</p>
    <div style="overflow-x:auto"><table class="books-table"><thead><tr><th></th><th>Entries</th><th>Avg CLV</th><th>Beat close</th><th>Settled</th><th>ROI</th></tr></thead><tbody>
      ${line("Flagged BET", s.flagged_bets)}${line("Flagged WATCH", s.flagged_watch)}${line("Your bets", s.your_bets)}</tbody></table></div>
    ${rows ? `<div style="overflow-x:auto;margin-top:10px"><table class="books-table"><thead><tr><th>Logged</th><th>Pick</th><th>Price</th><th>Type</th><th>Close</th><th>CLV</th><th>Result</th><th></th></tr></thead><tbody>${rows}</tbody></table></div>`
      : `<div class="muted" style="margin-top:10px">Nothing logged yet. Flags are recorded automatically as cards are viewed.</div>`}`;
}

function decisionChip(f) {
  const pr = modelFor(f);
  const d = pr && pr.decision;
  if (!d || f.status.state !== "pre" || d.action === "PASS") return "";
  return ` <span class="badge ${d.action === "BET" ? "good" : "title"}" title="${esc((d.reasons || []).join(" "))}">${d.action}</span>`;
}
