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

const RATING_ROWS = [
  // [label, key, how to read, higher is better?, format]
  ["Adj. striking offense", "adj_sig_o", "sig. strikes landed per minute against an average defense", true, v => v.toFixed(2)],
  ["Adj. striking defense", "adj_sig_d", "sig. strikes absorbed per minute from an average offense", false, v => v.toFixed(2)],
  ["Adj. head strikes landed", "adj_head_o", "per minute", true, v => v.toFixed(2)],
  ["Adj. head strikes absorbed", "adj_head_d", "per minute", false, v => v.toFixed(2)],
  ["Adj. knockdowns", "adj_kd_o", "per 15 minutes", true, v => v.toFixed(2)],
  ["Adj. knockdowns taken", "adj_kd_d", "per 15 minutes", false, v => v.toFixed(2)],
  ["Adj. takedowns", "adj_td_o", "per 15 minutes against an average defense", true, v => v.toFixed(2)],
  ["Adj. takedowns conceded", "adj_td_d", "per 15 minutes", false, v => v.toFixed(2)],
  ["Adj. control time", "adj_ctrl_o", "minutes per 15", true, v => v.toFixed(1)],
  ["Adj. control conceded", "adj_ctrl_d", "minutes per 15", false, v => v.toFixed(1)],
  ["Adj. submission threat", "adj_sub_o", "attempts per 15", true, v => v.toFixed(2)],
  ["Adj. submission exposure", "adj_sub_d", "attempts faced per 15", false, v => v.toFixed(2)],
  ["Strength of schedule", "sos", "average rating of opponents faced", true, v => (v >= 0 ? "+" : "") + v.toFixed(2)],
  ["Luck", "luck", "wins beyond what the fight stats say", null, v => (v >= 0 ? "+" : "") + v.toFixed(2)],
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
  const rankTxt = i => r.rank[i] ? `#${r.rank[i].rank} of ${r.rank[i].of} ${esc(divShort(r.rank[i].div))} · ${ordinal(r.rank[i].pct)} pct` : "unranked";
  const sides = [0, 1].map(i => `<div class="odds-side ${i ? "blue" : "red"}">
      <div class="os-top"><span class="os-name">${esc(names[i])}</span><span class="os-book">Rating</span></div>
      <div class="os-price">${pct(r.p[i], 0)}<span class="small muted" style="font-weight:500"> to win</span></div>
      <dl class="kv tight">
        <dt>Power rating</dt><dd>${(r.power[i] >= 0 ? "+" : "") + r.power[i].toFixed(2)}</dd>
        <dt>Division rank</dt><dd>${rankTxt(i)}</dd>
        <dt>Style</dt><dd>${esc(styleName(P[i].style.primary))}<span class="muted"> / ${esc(styleName(P[i].style.secondary))}</span></dd>
        ${mkt ? `<dt>Market</dt><dd>${pct(mkt[i], 1)}</dd>` : ""}
      </dl></div>`).join("");
  let gap = "";
  if (mkt) {
    const d = r.p[0] - mkt[0];
    gap = Math.abs(d) < 0.02 ? `<div class="note-line">The ratings agree with the market (within 2 points).</div>`
      : `<div class="note-line">The ratings are <b>${(Math.abs(d) * 100).toFixed(0)} points</b> higher on ${esc(d > 0 ? ln[0] : ln[1])} than the market.</div>`;
  }
  // the ratings page: adjusted numbers side by side, better one highlighted
  const row = (label, va, vb, better, fmt, help) => {
    const a = va === null || va === undefined || isNaN(va), b = vb === null || vb === undefined || isNaN(vb);
    const winA = !a && !b && better !== null && (better ? va > vb : va < vb), winB = !a && !b && better !== null && (better ? vb > va : vb < va);
    return `<tr><td title="${esc(help || "")}">${esc(label)}</td><td class="${winA ? "best" : ""}">${a ? "—" : esc(fmt(va))}</td><td class="${winB ? "best" : ""}">${b ? "—" : esc(fmt(vb))}</td></tr>`;
  };
  const adjRows = RATING_ROWS.map(([label, key, help, better, fmt]) => row(label, P[0].adj[key], P[1].adj[key], better, fmt, help)).join("");
  const rawRows = RAW_ROWS.map(([label, get, better, fmt]) => row(label, get(P[0]), get(P[1]), better, fmt)).join("");
  const table = `<table class="books-table ratings-table"><thead><tr><th>Opponent-adjusted</th><th>${esc(ln[0])}</th><th>${esc(ln[1])}</th></tr></thead><tbody>${adjRows}</tbody>
    <thead><tr><th>Raw</th><th></th><th></th></tr></thead><tbody>${rawRows}</tbody></table>`;
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
  if (meta) meta.textContent = S.ratings.model && S.ratings.model.trained_through ? `history through ${S.ratings.model.trained_through}` : "";
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
    ${T.rating_only ? `<div class="note-line">The single opponent-adjusted rating alone: ${acc(T.rating_only)} right (${ll(T.rating_only)}); without any opponent adjustment: ${acc(T.without_adjusted)} (${ll(T.without_adjusted)}).</div>` : ""}
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
    const rows = (d.rows || []).map(r => `<tr><td>${r.rank}</td><td>${esc(r.name || r.id)}</td><td>${(r.power >= 0 ? "+" : "") + r.power.toFixed(2)}</td><td>${r.fights}</td><td>${esc(r.last || "")}</td>
      <td>${r.adj.net_strike !== undefined ? (r.adj.net_strike >= 0 ? "+" : "") + r.adj.net_strike.toFixed(2) : "—"}</td><td>${r.adj.net_td !== undefined ? (r.adj.net_td >= 0 ? "+" : "") + r.adj.net_td.toFixed(2) : "—"}</td><td>${r.adj.sos !== undefined ? (r.adj.sos >= 0 ? "+" : "") + r.adj.sos.toFixed(2) : "—"}</td></tr>`).join("");
    body.innerHTML = `<p class="fine">Active fighters (a UFC fight in the last 4 years), ranked by power rating: the model's log-odds of beating an average fighter in the division, as of ${esc(d.asof || "")}. Striking and takedown margins are per minute / per 15 against average opposition; SOS is the average rating of opponents faced.</p>
      <div style="margin:6px 0">${sel}</div>
      <div style="overflow-x:auto"><table class="books-table"><thead><tr><th>#</th><th>Fighter</th><th>Power</th><th>Fights</th><th>Last</th><th>Strike mgn</th><th>TD mgn</th><th>SOS</th></tr></thead><tbody>${rows}</tbody></table></div>`;
    $("#rank-div").onchange = e => openRankings(e.target.value);
  } catch (e) { body.innerHTML = `<div class="err">${esc(e.message)}</div>`; }
}

function styleName(s) {
  return { wrestler: "wrestler", grappler: "submission grappler", volume_striker: "volume striker", power_striker: "power striker", kicker: "kicker", clinch: "clinch fighter", counter: "counter striker" }[s] || s;
}
function groupName(g) {
  return { adjusted: "Adjusted ratings", schedule: "Schedule & luck", striking: "Striking", grappling: "Grappling", durability: "Durability", finishing: "Finishing", judging: "Judging", record: "Record",
    pace: "Pace", cardio: "Cardio", physical: "Physical", experience: "Experience", rust: "Ring rust", momentum: "Momentum", matchup: "Style matchup", other: "Other" }[g] || g;
}
function divName(d) { return (d || "").replace(/^w /, "women's ").replace(/\b\w/g, c => c.toUpperCase()); }
function divShort(d) { return ({ "strawweight": "SW", "flyweight": "FLW", "bantamweight": "BW", "featherweight": "FW", "lightweight": "LW", "welterweight": "WW", "middleweight": "MW", "light heavyweight": "LHW", "heavyweight": "HW" })[(d || "").replace(/^w /, "")] ? ((d || "").startsWith("w ") ? "W" : "") + ({ "strawweight": "SW", "flyweight": "FLW", "bantamweight": "BW", "featherweight": "FW", "lightweight": "LW", "welterweight": "WW", "middleweight": "MW", "light heavyweight": "LHW", "heavyweight": "HW" })[(d || "").replace(/^w /, "")] : d; }
function ordinal(n) { const s = ["th", "st", "nd", "rd"], v = n % 100; return n + (s[(v - 20) % 10] || s[v] || s[0]); }

function ratingChip(f) {
  const r = ratingFor(f);
  if (!r || f.status.state === "post") return "";
  const i = r.p[0] >= 0.5 ? 0 : 1;
  return ` <span class="badge faint-badge" title="Power ratings model: ${esc(f.fighters[i].name)} ${pct(r.p[i], 0)}">R ${pct(r.p[i], 0)} ${esc(lastName(f.fighters[i].name))}</span>`;
}
