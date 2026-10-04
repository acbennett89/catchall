"use strict";
/* Power ratings (the KenPom-style model): loading, the matchup's ratings panel, and the division
   rankings dialog.  Loaded before app.js; uses its helpers only at call time. */

async function loadRatings() {
  const id = S.eventId;
  try {
    const r = await api(`/api/ratings/${id}`);
    if (id !== S.eventId) return;
    S.ratings = r; S.ratingsErr = null;
    renderList();
    updateMatchup(true);
  } catch (e) {
    S.ratingsErr = e.message;
  }
}

function ratingFor(f) {
  const r = S.ratings && S.ratings.available && S.ratings.fights ? S.ratings.fights[f.id] : null;
  return r && !r.error ? r : null;
}

// adjusted dimensions shown on the ratings page: [dimension key, label, unit]
const ADJ_DIMS = [
  ["sig", "Sig. strikes", "/15"], ["head", "Head strikes", "/15"], ["dist", "Distance strikes", "/15"], ["clinch", "Clinch strikes", "/15"],
  ["ground", "Ground strikes", "/15"], ["kd", "Knockdowns", "/15"], ["pow", "Power (KD per 100 head strikes)", ""], ["td", "Takedowns", "/15"],
  ["td_a", "Takedown attempts", "/15"], ["ctrl", "Control", "min/15"], ["sub", "Sub attempts", "/15"], ["fin", "Finishes", "/15"],
];

const RAW_ROWS = [
  ["Strike differential", p => p.str_diff, true, v => (v >= 0 ? "+" : "") + v.toFixed(2) + "/min"],
  ["Striking accuracy", p => p.sig_acc, true, v => pct(v, 0)],
  ["Striking defense", p => p.sig_def, true, v => pct(v, 0)],
  ["Takedown defense", p => p.td_def, true, v => pct(v, 0)],
  ["Pace (both fighters' attempts)", p => p.pace, null, v => v.toFixed(1) + "/min"],
  ["Cardio (late rounds vs round 1)", p => p.fade, true, v => "×" + v.toFixed(2)],
  ["Drains opponents", p => p.opp_fade, false, v => "×" + v.toFixed(2)],
  ["Chin (losses by KO)", p => p.ko_loss_share, false, v => pct(v, 0)],
  ["Gets finished", p => p.finished_share, false, v => pct(v, 0)],
  ["Finish rate", p => p.finish_rate, true, v => pct(v, 0)],
  ["Wins decisions", p => p.dec_win_pct, true, v => pct(v, 0)],
  ["Age", p => p.age, false, v => v.toFixed(1)],
  ["Reach", p => p.reach, true, v => v + '"'],
  ["Layoff", p => p.layoff_days, false, v => v + " days"],
  ["Activity (fights, 2 yrs)", p => p.fights_24m, true, v => String(v)],
  ["Last 5", p => p.last5_n ? p.last5_wins + "-" + (p.last5_n - p.last5_wins) : null, null, v => v],
  ["Streak", p => p.streak, true, v => (v > 0 ? "W" : v < 0 ? "L" : "") + Math.abs(v)],
  ["UFC fights", p => p.ufc_fights, true, v => String(v)],
  ["Record outside the UFC", p => p.outside_known ? p.outside_wins + "-" + p.outside_losses : null, null, v => v],
];

function renderRatings(f) {
  const el = $("#m-ratings");
  if (!el) return;
  if (!S.ratings) { el.innerHTML = S.ratingsErr ? `<div class="err">${esc(S.ratingsErr)}</div>` : `<div class="skeleton" style="height:90px"></div>`; return; }
  if (!S.ratings.available) { el.innerHTML = `<div class="muted">The ratings model isn't installed (ratings/model.json is missing).</div>`; return; }
  const r = S.ratings.fights && S.ratings.fights[f.id];
  if (!r) { el.innerHTML = `<div class="muted">No rating for this fight.</div>`; return; }
  if (r.error) { el.innerHTML = `<div class="err">Couldn't rate this fight: ${esc(r.error)}</div>`; return; }
  const names = f.fighters.map(x => x.name), ln = names.map(lastName);
  const fo = fightOdds(f);
  const mkt = fo && fo.value && fo.value.fair;
  const P = r.profiles;
  const rankTxt = i => r.rank[i] && r.rank[i].rank ? `#${r.rank[i].rank} of ${r.rank[i].of}` : "unranked";
  const tierTxt = i => r.tier[i] ? `${r.tier[i].tier}, ${Math.round(r.tier[i].effective_minutes)} min` : "";
  const sides = [0, 1].map(i => `<div class="odds-side ${i ? "blue" : "red"}">
      <div class="os-top"><span class="os-name">${esc(names[i])}</span><span class="os-book">Rating</span></div>
      <div class="os-price">${pct(r.p[i], 0)}<span class="small muted" style="font-weight:500"> to win</span></div>
      <dl class="kv tight">
        <dt title="Adjusted efficiency margin: cage points per 15 minutes vs an average opponent (log-odds)">AdjEM</dt><dd>${(r.adjem[i] >= 0 ? "+" : "") + r.adjem[i].toFixed(2)}</dd>
        <dt title="Chance of beating an average fighter of the division this fight is rated in">Beats avg ${esc(divShort(r.div || ""))}</dt><dd>${pct(P[i].adj.pyth, 0)}</dd>
        <dt>Rank</dt><dd>${rankTxt(i)}${r.rank[i] ? ` <span class="faint">· ${ordinal(r.rank[i].pct)}</span>` : ""}</dd>
        <dt title="Provisional under 15 effective minutes, developing to 45, established beyond">Data</dt><dd>${esc(tierTxt(i))}</dd>
        ${mkt ? `<dt>Market</dt><dd>${pct(mkt[i], 1)}</dd>` : ""}
      </dl>
      <div class="small muted" style="margin-top:6px">${esc(styleName(P[i].style.primary))} <span class="faint">/ ${esc(styleName(P[i].style.secondary))}</span></div></div>`).join("");
  let gap = "";
  if (mkt) {
    const d = r.p[0] - mkt[0];
    gap = Math.abs(d) < 0.02 ? `<div class="note-line">The ratings agree with the market (within 2 points).</div>`
      : `<div class="note-line">The ratings are <b>${(Math.abs(d) * 100).toFixed(0)} points</b> higher on ${esc(d > 0 ? ln[0] : ln[1])} than the market.</div>`;
  }
  // the ratings page: adjusted numbers side by side, better one highlighted
  const row = (label, va, vb, better, fmt, help) => {
    const miss = v => v === null || v === undefined || (typeof v === "number" && isNaN(v));
    const a = miss(va), b = miss(vb);
    const winA = !a && !b && better !== null && (better ? va > vb : va < vb), winB = !a && !b && better !== null && (better ? vb > va : vb < va);
    return `<tr><td title="${esc(help || "")}">${esc(label)}</td><td class="${winA ? "best" : ""}">${a ? "—" : esc(fmt(va))}</td><td class="${winB ? "best" : ""}">${b ? "—" : esc(fmt(vb))}</td></tr>`;
  };
  // adjusted page: offense and defense per dimension as an index (100 = division average) with the natural rate
  const idx = (v, better) => `<span title="100 = division-era average">${v}</span>`;
  const adjCell = (P, k, side) => { const o = P.adj[side === "o" ? "index_o" : "index_d"][k], n = P.adj[side === "o" ? "o15" : "d15"][k]; return o === undefined ? "—" : `${o} <span class="faint">(${n})</span>`; };
  const adjRows = ADJ_DIMS.map(([k, label, unit]) => {
    const oa = P[0].adj.index_o[k], ob = P[1].adj.index_o[k], da = P[0].adj.index_d[k], db = P[1].adj.index_d[k];
    return `<tr><td>${esc(label)} <span class="faint">offense${unit ? " " + esc(unit) : ""}</span></td><td class="${oa > ob ? "best" : ""}">${adjCell(P[0], k, "o")}</td><td class="${ob > oa ? "best" : ""}">${adjCell(P[1], k, "o")}</td></tr>
      <tr><td>${esc(label)} <span class="faint">defense (lower is better)</span></td><td class="${da < db ? "best" : ""}">${adjCell(P[0], k, "d")}</td><td class="${db < da ? "best" : ""}">${adjCell(P[1], k, "d")}</td></tr>`;
  }).join("");
  const comp = [["AdjO (cage points /15 vs avg)", p => p.adj.adjo, true, v => v.toFixed(2)], ["AdjD (allowed, lower is better)", p => p.adj.adjd, false, v => v.toFixed(2)],
    ["AdjEM", p => p.adj.adjem, true, v => (v >= 0 ? "+" : "") + v.toFixed(2)], ["Results strength (Bradley-Terry)", p => p.adj.bt, true, v => (v >= 0 ? "+" : "") + v.toFixed(2)],
    ["Strength of schedule", p => p.adj.sos, true, v => (v >= 0 ? "+" : "") + v.toFixed(2)], ["Luck (wins beyond the stat lines)", p => p.adj.luck, null, v => (v >= 0 ? "+" : "") + v.toFixed(2)],
    ["Performance-implied win share", p => p.adj.pyth_share, true, v => pct(v, 0)]];
  const compRows = comp.map(([label, get, better, fmt]) => row(label, get(P[0]), get(P[1]), better, fmt)).join("");
  const rawRows = RAW_ROWS.map(([label, get, better, fmt]) => row(label, get(P[0]), get(P[1]), better, fmt)).join("");
  const ex = r.expected || {};
  const exRows = ADJ_DIMS.filter(([k]) => k !== "pow" && k !== "fin").map(([k, label, unit]) => `<tr><td>${esc(label)}${unit ? ` <span class="faint">${esc(unit)}</span>` : ""}</td><td>${ex.a_on_b ? ex.a_on_b[k] : "—"}</td><td>${ex.b_on_a ? ex.b_on_a[k] : "—"}</td><td class="muted">${ex.baseline ? ex.baseline[k] : ""}</td></tr>`).join("");
  const table = `<table class="books-table ratings-table"><thead><tr><th>Composite</th><th>${esc(ln[0])}</th><th>${esc(ln[1])}</th></tr></thead><tbody>${compRows}</tbody>
    <thead><tr><th>Opponent-adjusted (index, rate)</th><th></th><th></th></tr></thead><tbody>${adjRows}</tbody>
    <thead><tr><th>Raw</th><th></th><th></th></tr></thead><tbody>${rawRows}</tbody></table>
    <div class="section-title" style="padding:12px 0 6px">How the fight looks <span class="faint" style="text-transform:none;letter-spacing:0">(expected per 15 minutes)</span></div>
    <table class="books-table"><thead><tr><th></th><th>${esc(ln[0])} on ${esc(ln[1])}</th><th>${esc(ln[1])} on ${esc(ln[0])}</th><th>avg</th></tr></thead><tbody>${exRows}</tbody></table>
    ${r.log5 ? `<div class="note-line">Ratings only (log5 of each fighter's chance against an average opponent): ${esc(ln[0])} ${pct(r.log5[0], 0)}, ${esc(ln[1])} ${pct(r.log5[1], 0)}. The full model above adds physical, experience, durability and ring-rust terms.</div>` : ""}`;
  // drivers by group and the biggest single terms
  const groups = Object.entries(r.groups || {});
  const gmax = Math.max(...groups.map(([, v]) => Math.abs(v)), 0.01);
  const gbars = groups.map(([g, v]) => `<div class="stat-row"><span class="v a">${v > 0 ? "◀" : ""}</span>
      <div class="bar a"><span style="width:${v > 0 ? Math.abs(v) / gmax * 100 : 0}%"></span></div>
      <span class="lab">${esc(groupName(g))}</span>
      <div class="bar b"><span style="width:${v < 0 ? Math.abs(v) / gmax * 100 : 0}%"></span></div><span class="v b">${v < 0 ? "▶" : ""}</span></div>`).join("");
  const dmax = Math.max(...(r.drivers || []).map(d => Math.abs(d.logit)), 0.01);
  const dbars = (r.drivers || []).map(d => `<div class="stat-row"><span class="v a">${d.favors === 0 ? "◀" : ""}</span>
      <div class="bar a"><span style="width:${d.favors === 0 ? Math.abs(d.logit) / dmax * 100 : 0}%"></span></div>
      <span class="lab">${esc(d.label)}</span>
      <div class="bar b"><span style="width:${d.favors === 1 ? Math.abs(d.logit) / dmax * 100 : 0}%"></span></div><span class="v b">${d.favors === 1 ? "▶" : ""}</span></div>`).join("");
  const flags = (r.flags || []).map(x => `<div class="note-line">⚠ ${esc(x.text)}</div>`).join("");
  el.innerHTML = `<div class="odds-grid">${sides}</div>${gap}${flags}
    <div class="section-title" style="padding:12px 0 6px"><span>Ratings page</span><button class="link-btn" id="rank-btn">Division rankings</button></div>${table}
    <div class="section-title" style="padding:12px 0 6px">What's driving it, by area</div>${gbars}
    <details><summary>Biggest single factors</summary>${dbars}</details>
    ${ratingsRecord()}`;
  const rb = $("#rank-btn");
  if (rb) rb.onclick = () => openRankings(r.div || (r.rank[0] && r.rank[0].div));
  const meta = $("#m-ratings-meta");
  if (meta) meta.textContent = r.asof ? `history through ${r.asof}` : (S.ratings.model && S.ratings.model.trained_through ? `fitted through ${S.ratings.model.trained_through}` : "");
}

function ratingsRecord() {
  const M = S.ratings && S.ratings.model;
  const T = M && M.evaluation && M.evaluation.test;
  if (!T || !T.with_market) return "";
  const wm = T.with_market, abl = M.ablation || {}, other = M.blend_model_for_comparison && M.blend_model_for_comparison.test;
  const acc = x => x ? pct(x.accuracy, 1) : "—", ll = x => x ? x.log_loss.toFixed(3) : "—";
  const ci = x => x && x.ci ? ` (95% range ${x.ci[0] >= 0 ? "+" : ""}${x.ci[0].toFixed(3)} to ${x.ci[1] >= 0 ? "+" : ""}${x.ci[1].toFixed(3)})` : "";
  const kept = Object.entries(abl).filter(([, a]) => a.kept).map(([g]) => groupName(g)), dropped = Object.entries(abl).filter(([, a]) => !a.kept).map(([g]) => groupName(g));
  return `<details class="track"><summary>Track record: ${esc(T.years)}, ${T.model ? T.model.n.toLocaleString() : "?"} fights it never saw</summary>
    <div class="note-line">On ${wm.model ? wm.model.n.toLocaleString() : "?"} of them with betting history: ratings model ${acc(wm.model)} right (log loss ${ll(wm.model)}),
      opening line ${acc(wm.market_open)} (${ll(wm.market_open)}), closing line ${acc(wm.market_close)} (${ll(wm.market_close)}). Lower log loss is better.
      Ratings minus opening line ${wm.model_minus_open ? wm.model_minus_open.est.toFixed(4) : "—"}${ci(wm.model_minus_open)}; minus closing line ${wm.model_minus_close ? wm.model_minus_close.est.toFixed(4) : "—"}${ci(wm.model_minus_close)}.</div>
    ${T.rating_only ? `<div class="note-line">AdjEM alone (the KenPom number): ${acc(T.rating_only)} right (${ll(T.rating_only)}); without the opponent-adjusted efficiencies: ${acc(T.without_adjusted)} (${ll(T.without_adjusted)}).</div>` : ""}
    ${other ? `<div class="note-line">The app's other model (the market blend's fight model, same years): ${acc(other.model)} right (${ll(other.model)}).</div>` : ""}
    ${kept.length || dropped.length ? `<div class="note-line">Tested on 2010–2020 and kept: ${esc(kept.join(", ") || "none")}. Dropped because they didn't help: ${esc(dropped.join(", ") || "none")}.</div>` : ""}
    <div class="note-line">This is a second opinion on who wins, not a bet signal: the BET rule above uses the market blend, which has a tested edge. Where the two models and the market disagree, that's the fight to look at.</div></details>`;
}

async function openRankings(div) {
  const dlg = $("#rankings"), body = $("#rankings-body");
  body.innerHTML = `<div class="loading">Loading…</div>`;
  dlg.showModal();
  try {
    const d = await api(`/api/leaderboard?div=${encodeURIComponent(div || "")}&top=40`);
    const sel = `<select id="rank-div">${(d.divisions || []).map(x => `<option value="${esc(x)}"${x === div ? " selected" : ""}>${esc(divName(x))}</option>`).join("")}</select>`;
    const sg = v => (v >= 0 ? "+" : "") + v.toFixed(2);
    const rows = (d.rows || []).map(r => `<tr class="${r.rank ? "" : "off"}"><td>${r.rank || "—"}</td><td>${esc(r.name || r.id)}${r.rank ? "" : ` <span class="faint">(${esc(r.tier)})</span>`}</td><td><b>${sg(r.adjem)}</b></td><td>${pct(r.pyth, 0)}</td><td>${r.adjo.toFixed(1)}</td><td>${r.adjd.toFixed(1)}</td><td>${sg(r.bt)}</td><td>${sg(r.sos)}</td><td>${sg(r.luck)}</td><td>${r.fights}</td><td>${esc(r.last || "")}</td></tr>`).join("");
    body.innerHTML = `<p class="fine">Active fighters (a UFC fight in the last 4 years) ranked by <b>AdjEM</b>, the adjusted efficiency margin: cage points per 15 minutes a fighter produces against an average opponent of the division minus what they allow, with every number adjusted for the quality of opposition faced (as of ${esc(d.asof || "")}). "Pyth" is the chance of beating an average fighter in the division. Fighters with too little data are listed unranked. Ratings are rust- and momentum-neutral: they say how good a fighter is, not how they'll do this week.</p>
      <div style="margin:6px 0">${sel}</div>
      <div style="overflow-x:auto"><table class="books-table"><thead><tr><th>#</th><th>Fighter</th><th>AdjEM</th><th>Pyth</th><th>AdjO</th><th>AdjD</th><th>Results</th><th>SOS</th><th>Luck</th><th>Fights</th><th>Last</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    $("#rank-div").onchange = e => openRankings(e.target.value);
  } catch (e) { body.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}

function styleName(s) {
  return { wrestler: "wrestler", grappler: "submission grappler", volume_striker: "volume striker", power_striker: "power striker", kicker: "kicker", clinch: "clinch fighter", counter: "counter striker" }[s] || s;
}
function groupName(g) {
  return { margins_mult: "Matchup (expected output each way)", margins_add: "Adjusted offense & defense", composite: "Efficiency margin (AdjEM)", results: "Results & performance", adjusted: "Adjusted ratings", schedule: "Schedule & luck", striking: "Striking", grappling: "Grappling", durability: "Durability", finishing: "Finishing", judging: "Judging", record: "Record",
    pace: "Pace", cardio: "Cardio", physical: "Physical", experience: "Experience", rust: "Ring rust", momentum: "Momentum", matchup: "Style matchup", other: "Other" }[g] || g;
}
function divName(d) { return (d || "").replace(/^w /, "women's ").replace(/(^|\s)\w/g, c => c.toUpperCase()); }
function divShort(d) { return ({ "strawweight": "SW", "flyweight": "FLW", "bantamweight": "BW", "featherweight": "FW", "lightweight": "LW", "welterweight": "WW", "middleweight": "MW", "light heavyweight": "LHW", "heavyweight": "HW" })[(d || "").replace(/^w /, "")] ? ((d || "").startsWith("w ") ? "W" : "") + ({ "strawweight": "SW", "flyweight": "FLW", "bantamweight": "BW", "featherweight": "FW", "lightweight": "LW", "welterweight": "WW", "middleweight": "MW", "light heavyweight": "LHW", "heavyweight": "HW" })[(d || "").replace(/^w /, "")] : d; }
function ordinal(n) { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }

function ratingChip(f) {
  const r = ratingFor(f);
  if (!r || f.status.state === "post") return "";
  const i = r.p[0] >= 0.5 ? 0 : 1;
  return ` <span class="badge faint-badge" title="Power ratings model: ${esc(f.fighters[i].name)} ${pct(r.p[i], 0)}">R ${pct(r.p[i], 0)} ${esc(lastName(f.fighters[i].name))}</span>`;
}
