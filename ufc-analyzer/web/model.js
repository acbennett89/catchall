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
  return p && !p.error ? p : null;
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
  const names = f.fighters.map(x => x.name);
  const ln = names.map(lastName);
  const actionable = f.status.state !== "post";
  const fo = fightOdds(f);
  const mkt = fo && fo.value && fo.value.fair;
  const sides = [0, 1].map(i => {
    const s = (pr.sides || [])[i] || {};
    const ev = settings.basis === "blend" && s.evBlend !== undefined ? s.evBlend : s.evModel;
    const kel = settings.basis === "blend" && s.kellyBlend !== undefined ? s.kellyBlend : s.kellyModel;
    const isValue = actionable && ev !== undefined && ev >= settings.threshold;
    return `<div class="odds-side ${i ? "blue" : "red"}${isValue ? " value" : ""}">
      <div class="os-top"><span class="os-name">${esc(names[i])}</span><span class="os-book">Model</span></div>
      <div class="os-price">${pct(pr.p[i], 0)}${isValue ? ` <span class="badge good" style="vertical-align:middle">VALUE</span>` : ""}</div>
      <dl class="kv">
        <dt>Model fair price</dt><dd>${esc(fmtOdds(pr.fair[i]))}</dd>
        <dt>Market fair</dt><dd>${mkt ? pct(mkt[i], 1) : "—"}</dd>
        ${pr.blend ? `<dt>Blend</dt><dd>${pct(pr.blend[i], 1)}</dd>` : ""}
        ${s.evModel !== undefined ? `<dt>EV at ${TARGET} (model)</dt><dd class="${s.evModel >= 0 ? "pos" : "neg"}">${signedPct(s.evModel)}</dd>` : ""}
        ${s.evBlend !== undefined ? `<dt>EV at ${TARGET} (blend)</dt><dd class="${s.evBlend >= 0 ? "pos" : "neg"}">${signedPct(s.evBlend)}</dd>` : ""}
        ${ev !== undefined && ev > 0 ? `<dt>Stake (${Math.round(settings.kelly * 100)}% Kelly)</dt><dd>${money(settings.bankroll * kel * settings.kelly)}</dd>` : ""}
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
    method = `<table class="books-table"><thead><tr><th>Outcome</th><th>${esc(ln[0])}</th><th>${esc(ln[1])}</th></tr></thead><tbody>
      ${row("KO/TKO", "ko")}${row("Submission", "sub")}${row("Decision", "dec")}
      <tr class="target"><td>Wins</td><td>${pct(pr.p[0], 0)}</td><td>${pct(pr.p[1], 0)}</td></tr></tbody></table>
      <div class="note-line">Goes the distance: <b>${pct(m.distance, 0)}</b>${m.over_under ? " · " + m.over_under.filter(o => o.line < f.rounds).map(o => `O/U ${o.line}: ${pct(o.over, 0)} / ${pct(o.under, 0)}`).join(" · ") : ""}</div>`;
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
  el.innerHTML = `<div class="odds-grid">${sides}</div>${gap}${flags}
    <div class="section-title" style="padding:12px 0 6px">How the model sees it ending</div>${method}${drivers}
    ${trackRecord()}`;
  const meta = $("#m-model-meta");
  if (meta) meta.textContent = S.pred.model && S.pred.model.trained_through ? `history through ${S.pred.model.trained_through}` : "";
}

/* One honest paragraph on how the model has done out of sample, from model.json's evaluation. */
function trackRecord() {
  const ev = S.pred && S.pred.model && S.pred.model.evaluation;
  if (!ev || !ev.vs_market) return "";
  const vm = ev.vs_market, b = ev.blend || {};
  const acc = x => x ? pct(x.accuracy, 1) : "—";
  const ll = x => x ? x.log_loss.toFixed(3) : "—";
  let s = `<details class="track"><summary>Track record (${esc(ev.period)}, fights it never saw)</summary><div class="note-line">
    On ${vm.model ? vm.model.n.toLocaleString() : "?"} fights with betting history: model accuracy ${acc(vm.model)} (log loss ${ll(vm.model)}),
    closing market ${acc(vm.market_close)} (${ll(vm.market_close)}), opening market ${acc(vm.market_open)} (${ll(vm.market_open)}).
    ${b.blend ? `Market + model blend: ${acc(b.blend)} (${ll(b.blend)}). ` : ""}Lower log loss is better.</div>`;
  const bt = ev.backtest || {};
  const pick = (k, lab) => {
    const r = bt[k];
    if (!r || !r.bets) return "";
    const ci = r.roi_ci ? ` (95% range ${signedPct(r.roi_ci[0], 0)} to ${signedPct(r.roi_ci[1], 0)})` : "";
    return `<li>${lab}: ${r.bets.toLocaleString()} bets, ROI ${signedPct(r.roi, 1)}${ci}</li>`;
  };
  const items = [pick("model|open|0.05", "Model, bet at opening lines when EV ≥ 5%"), pick("model|worst|0.05", "Model, worst closing price, EV ≥ 5%"),
    pick("blend|open|0.03", "Blend, opening lines, EV ≥ 3%"), pick("blend|worst|0.03", "Blend, worst closing price, EV ≥ 3%")].join("");
  if (items) s += `<ul class="small muted" style="margin:6px 0 0 18px;padding:0">${items}</ul>`;
  s += `<div class="note-line">The closing market is very hard to beat. Treat a model edge as a second opinion, and check it against the matchup.</div></details>`;
  return s;
}

/* Model probability for a Caesars prop label ("Silva wins by TKO/KO", "Over 2½ rounds", ...). */
function propModelProb(p, f) {
  const pr = modelFor(f);
  if (!pr || !pr.method) return null;
  const m = pr.method;
  const tokensOf = n => (n || "").toLowerCase().normalize("NFKD").replace(/[̀-ͯ]/g, "").split(/[^a-z0-9]+/).filter(t => t.length >= 2);
  const toks = f.fighters.map(x => tokensOf(x.name));
  const sideOf = who => {
    const w = tokensOf(who);
    const hit = [0, 1].filter(i => w.length && w.every(t => toks[i].includes(t)));
    return hit.length === 1 ? hit[0] : null;
  };
  const S_ = i => (i === 0 ? m.a : m.b);
  const roundFinish = r => (m.rounds && m.rounds[r - 1]) ? m.rounds[r - 1].a + m.rounds[r - 1].b : null;
  const one = (label) => {
    const L = label.replace(/½/g, ".5").trim();
    let x;
    if ((x = L.match(/^either fighter wins by (?:tko\/ko|ko\/tko|ko)$/i))) return m.a.ko + m.b.ko;
    if ((x = L.match(/^either fighter wins by submission$/i))) return m.a.sub + m.b.sub;
    if ((x = L.match(/^(.+?) wins by (?:tko\/ko|ko\/tko|ko|tko)$/i))) { const i = sideOf(x[1]); return i === null ? null : S_(i).ko; }
    if ((x = L.match(/^(.+?) wins by submission$/i))) { const i = sideOf(x[1]); return i === null ? null : S_(i).sub; }
    if ((x = L.match(/^(.+?) wins by decision$/i))) { const i = sideOf(x[1]); return i === null ? null : S_(i).dec; }
    if ((x = L.match(/^(.+?) wins inside (?:the )?distance$/i))) { const i = sideOf(x[1]); return i === null ? null : S_(i).ko + S_(i).sub; }
    if ((x = L.match(/^not (.+?) inside (?:the )?distance$/i))) { const i = sideOf(x[1]); return i === null ? null : 1 - S_(i).ko - S_(i).sub; }
    if ((x = L.match(/^not (.+?) by decision$/i))) { const i = sideOf(x[1]); return i === null ? null : 1 - S_(i).dec; }
    if ((x = L.match(/^(.+?) wins in round (\d)$/i))) { const i = sideOf(x[1]); const r = m.rounds && m.rounds[+x[2] - 1]; return i === null || !r ? null : (i === 0 ? r.a : r.b); }
    if (/^fight goes to decision$/i.test(L)) return m.distance;
    if (/^fight doesn'?t go to decision$/i.test(L)) return 1 - m.distance;
    if ((x = L.match(/^(over|under) (\d(?:\.5)?) rounds$/i)) && m.over_under) {
      const o = m.over_under.find(o => Math.abs(o.line - +x[2]) < 1e-6);
      return o ? (x[1].toLowerCase() === "over" ? o.over : o.under) : null;
    }
    if ((x = L.match(/^fight ends in round (\d)$/i))) return roundFinish(+x[1]);
    if ((x = L.match(/^fight (won'?t )?starts? round (\d)$/i))) {
      let before = 0;
      for (let r = 1; r < +x[2]; r++) { const v = roundFinish(r); if (v === null) return null; before += v; }
      return x[1] ? before : 1 - before;
    }
    return null;
  };
  let v = one(p.label);
  if (v === null && /^any other result$/i.test(p.label) && p.other) {
    const o = one(p.other);
    v = o === null ? null : 1 - o;
  }
  return v === null || isNaN(v) ? null : Math.min(0.995, Math.max(0.005, v));
}
