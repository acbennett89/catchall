// Prop label -> model probability mapping (web/model.js).  Run: node tests/props_map.test.js
"use strict";
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const ko_a = [0.10, 0.06, 0.04], sub_a = [0.05, 0.03, 0.02];
const ko_b = [0.06, 0.04, 0.02], sub_b = [0.02, 0.02, 0.01];
const table = {
  rounds_scheduled: 3, draw: 0.006,
  a: { ko: 0.20, sub: 0.10, dec: 0.25, dec_u: 0.19, dec_s: 0.06, ko_r: ko_a, sub_r: sub_a },
  b: { ko: 0.12, sub: 0.05, dec: 0.274, dec_u: 0.21, dec_s: 0.064, ko_r: ko_b, sub_r: sub_b },
  distance: 0.53,
  rounds: [{ round: 1, a: 0.15, b: 0.08 }, { round: 2, a: 0.09, b: 0.06 }, { round: 3, a: 0.06, b: 0.03 }],
  over_under: [{ line: 0.5, under: 0.1, over: 0.9 }, { line: 1.5, under: 0.3, over: 0.7 }, { line: 2.5, under: 0.45, over: 0.55 }],
};
const ctx = vm.createContext({ S: { pred: { available: true, fights: { f1: { p: [0.6, 0.4], method: table } } } }, settings: { basis: "market" }, console });
vm.runInContext(fs.readFileSync(path.join(__dirname, "..", "web", "model.js"), "utf8"), ctx);
const f = { id: "f1", rounds: 3, fighters: [{ name: "Natalia Silva" }, { name: "Wang Cong" }] };
const ends = r => ko_a[r - 1] + sub_a[r - 1] + ko_b[r - 1] + sub_b[r - 1];
const cases = [
  ["Silva wins by TKO/KO", 0.20], ["Cong wins by submission", 0.05], ["Silva wins by decision", 0.25],
  ["Silva wins by unanimous decision", 0.19], ["Cong wins by split/majority decision", 0.064],
  ["Cong wins inside distance", 0.17], ["Not Silva inside distance", 0.70], ["Not Cong by decision", 0.726],
  ["Silva wins in round 2", 0.09], ["Silva wins in round 1 or 2", 0.24], ["Silva wins by TKO/KO in round 1", 0.10],
  ["Cong wins by submission in round 3", 0.01], ["Silva wins in final round or by decision", 0.31],
  ["Either fighter wins by TKO/KO", 0.32], ["Either fighter wins by submission", 0.15],
  ["Fight goes to decision", 0.53], ["Fight doesn't go to decision", 0.47],
  ["Fight is a draw", 0.006], ["Fight is not a draw", 0.994],
  ["Over 1½ rounds", 0.7], ["Under 2½ rounds", 0.45],
  ["Fight ends in round 1", ends(1)], ["Fight ends in round 1 or 2", ends(1) + ends(2)], ["Fight doesn't end in round 1", 1 - ends(1)],
  ["Fight starts round 2", 1 - ends(1)], ["Fight won't start round 3", ends(1) + ends(2)],
  ["Fight ends in final round or goes to decision", ends(3) + 0.53],
  ["Silva (scorecards = no action)", null],
];
let bad = 0;
for (const [label, want] of cases) {
  const got = ctx.propModelProb({ label, other: "" }, f);
  const ok = want === null ? got === null : got !== null && Math.abs(got - want) < 1e-9;
  if (!ok) { bad++; console.log("FAIL", label, "got", got, "want", want); }
}
const other = ctx.propModelProb({ label: "Any other result", other: "Silva wins by TKO/KO" }, f);
if (Math.abs(other - 0.8) > 1e-9) { bad++; console.log("FAIL any other result", other); }
const g = { id: "f1", rounds: 3, fighters: [{ name: "Joshua Van" }, { name: "Alexandre Pantoja" }] };
if (Math.abs(ctx.propModelProb({ label: "van wins in round 1" }, g) - 0.15) > 1e-9) { bad++; console.log("FAIL lowercase surname"); }
console.log(bad ? `${bad} failures` : `all ${cases.length + 2} prop mappings ok`);
process.exit(bad ? 1 : 0);
