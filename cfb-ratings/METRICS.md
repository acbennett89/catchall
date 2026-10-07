# CFB Efficiency Ratings: full metric list

This is the complete list of metrics the system computes, with each metric's definition, its inputs,
and the rule that decides what counts. It was written before the build and updated as the
adversarial review changed rules; `ADVERSARIAL_REVIEW.md` records each change and the evidence for it.
Every published number can be traced back to individual games, drives, plays and fouls (`TRACE.md`).

Data source: ESPN's public college football API (scoreboards plus per-game play-by-play).
Universe: all Division I games (FBS and FCS). Only FBS teams are published.

---

## 0. Eligibility and counting rules

| # | Rule | Definition |
|---|------|------------|
| 0.1 | **Published teams** | FBS teams only (138 in 2026, from ESPN's 11 FBS conference rosters; 136 in 2025, 134 in 2024, 133 in 2023, 131 in 2022). |
| 0.1b | **Season scope** | The **regular season**, conference championship games and Army–Navy included. Bowls and the CFP are never downloaded. The FCS playoff rounds ESPN lists among regular-season weeks ("FCS Championship - First Round" and so on) are flagged by `parse.py` and left out by `ratings.load()`; the page lists how many. A finished season is labeled "regular season final". |
| 0.2 | **Eligibility** | A team gets an official rating and rank after **5 completed games** against D-I opponents (FBS or FCS). **Below that it gets a tentative rating** (added at your request after the first build): the same model and the same full trace, marked **T** on the page and `tentative` in the files, but never ranked. The page shows "≈n", where it would slot among ranked teams, and a checkbox hides tentative teams. While fewer than half the rated teams are ranked (the first four or five weeks of a season, in the weekly views), ≈n is instead the team's place among all rated teams; placing it against two to ten early starters would put nearly everyone at ≈1–≈3 (`ratings.comparison_pool`). Predictions involving one are marked tentative. Inside other teams' traces, a tentative FBS opponent links to its own trace. FCS teams stay internal inputs: their derivations are in `out/<season>/traces/internal/` (`trace.py --internal`, or the page's "internal*" links). The threshold is `min_games`. |
| 0.3 | **Efficiency model universe** | Every D-I vs D-I game. FCS teams are rated from their own FCS schedules, so a win over a strong FCS team and a win over a weak one are adjusted differently. Games against D-II/NAIA teams are dropped, as KenPom drops non-D-I games. |
| 0.4 | **Network universe** | FBS vs FBS games only. A win over an FCS team is worth **0**, and its secondary and tertiary branches are never traversed (your rule). |

---

## 1. Drive and play cleaning (inputs to the efficiency model)

A "possession" is an offensive **drive**.

| # | Rule | Definition | Why |
|---|------|------------|-----|
| 1.1 | Drive points | Each scoring play's points are **rebuilt from what the play was**: touchdown 6 plus the extra-point result, field goal 3, safety 2. When ESPN shows an extra point as "Not Available", the team's unreported extra points share whatever it still needs to reach its final score. If nothing reconciles, ESPN's running score is used only when every change is a legal score; otherwise the game is dropped from efficiency. A drive's points are the touchdowns and field goals its offense **itself snapped**. | ESPN's running score was wrong on 21 scoring plays in 8 FBS-involved 2026 games (e.g. a TD credited as 1, 13 or −8 points). 5 more FBS games use the running-score fallback because ESPN mislabels an extra point. |
| 1.2 | Drive offense | The team that snapped most of the drive's plays. | ESPN mislabels some drives. |
| 1.3 | Zero-play drives | Dropped. | Kickoff and punt-return "drives" aren't possessions. |
| 1.4 | Overtime | Dropped. | OT drives start at the 25. |
| 1.5 | End of half / game | Dropped if the drive's **first snap comes with 60 s or less left in Q2 or Q4**, whatever the result. The snap time is the "(MM:SS)" stamp that opens stat-crew play text. Without a stamp, ESPN's clock field is used (roughly end of play); a stale 0:00 reading falls back to ESPN's drive start clock. Stamp coverage depends on the season's feed: about 88% of drives in 2026, 37% in 2025 and almost none in 2022–2024, so in 2022–2024 and much of 2025 this rule, the clean intervals (7.1), neutral pace and lead-protection tags run on the end-of-play clock and are not comparable with 2026. Each season's page states its share. | Based on the situation, never the outcome. Dropping only drives that failed would inflate offense. |
| 1.6 | Garbage time | Dropped (both teams) when the margin at the first snap is more than **43 (Q1), 37 (Q2), 27 (Q3) or 21 (Q4)**. Checked before 1.5, so garbage points always come out of the garbage-adjusted scores (§4). | Bill Connelly's rule. It is kept because it can be checked by hand; the alternatives tested were no better (review §H). |
| 1.7 | Scrimmage plays | Rushes, passes, sacks and scrimmage fumbles on kept drives. Excluded: kneel-downs and spikes (whole-word match, so "McKneely" isn't a kneel), snaps the text says were nullified ("NO PLAY"), muffed punts and other special-teams fumbles, and snaps ESPN lists twice. These tests read only the snap's own text: the extra-point narrative ESPN appends to touchdowns is cut off first. A fumble is a turnover when the defense ends up with the ball, whatever ESPN's fumble label says. | Standard play filter. |

Every drive in the trace carries `kept`, `excluded_reason` and, where it applies, a lead-protection tag (§7).

---

## 2. Core efficiency ratings (KenPom analogs)

A single additive, drive-weighted opponent-adjustment model, solved by iterative averaging:

```
PPD(X on offense vs Y) = AdjO_X + AdjD_Y − μ + h·v_X + error
   v_X = +1 home, −1 away, 0 neutral;  h = home-field bonus per drive
```

O and D are only identified up to a shared constant. The solver pins the average FBS team's
O − D to 0, then shifts O, D and μ together so that the average FBS defense equals μ exactly.

| # | Metric | Definition | Units |
|---|--------|------------|-------|
| 2.1 | **μ** | Points per drive an average FBS offense scores against an average FBS defense on a neutral field (2.344 in 2026 through week 5; each season's value is in its page header and `anchors.json`). It equals the mean AdjO, and the mean AdjD, over all 138 FBS teams; every input is listed in `out/2026/anchors.json`. | pts/drive |
| 2.2 | **AdjO** | Points per drive against an **average FBS defense**, neutral field. It equals the drive-weighted mean of game values `raw PPD − (opp AdjD − μ) − h·v`, plus one phantom game at the division mean (§2.7). | pts/drive (higher is better) |
| 2.3 | **AdjD** | Points per drive allowed to an **average FBS offense**, built the same way. | pts/drive (lower is better) |
| 2.4 | **AdjEM** | `(AdjO − AdjD) × μT`. Points per game better than an average FBS team on a neutral field. **This is the power rating and the ranking metric** (the page's "Power" column). It averages exactly 0 over all FBS teams, including tentative teams (in 2026 through week 5: 138 teams, of which the 107 ranked average −0.18). | pts/game |
| 2.5 | **AdjT** | Opponent-adjusted possessions per game: `Poss_g = AdjT_X + AdjT_Y − μT`. A game's possessions are both teams' regulation drives with a real snap, divided by 2. That includes garbage-time and end-of-half drives, because tempo measures how many possessions a game has, not how good they were. Tested against neutral-pace and Q1–Q3-only versions; neither helped, so it is kept. | drives/game |
| 2.6 | **Home field** | `h` is estimated from the **unshrunk** fit and then held fixed. Estimating it jointly with the shrinkage prior inflated it from 3.6 to 4.6 points. It is shown per drive and as `2·h·μT` points per game. | pts |
| 2.7 | **Regression to the mean** | One phantom game of 12 drives at the team's division average, shown as its own line in the trace. | — |
| 2.8 | **±SE** | The SD of the game-level adjusted margins ÷ √games. | pts/game |
| 2.9 | **AdjSR O / D** | The same model applied to success rate, play-weighted. | % |

---

## 3. Five factors (raw, on kept drives, offense and defense)

| # | Factor | Definition |
|---|--------|------------|
| 3.1 | **Success rate** | Share of plays gaining ≥ 50% of the yards needed on 1st down, ≥ 70% on 2nd, and 100% on 3rd/4th. A touchdown is a success; a turnover is not. |
| 3.2 | **Explosiveness** | Share of plays gaining ≥ 12 yards (rush) or ≥ 16 yards (pass). Yards per play is shown alongside. |
| 3.3 | **Field position** | Average drive start, in yards from the team's own goal line. |
| 3.4 | **Finishing drives** | Points per scoring opportunity, i.e. per drive with a 1st down at or inside the opponent's 40. |
| 3.5 | **Turnovers** | Giveaways, takeaways and margin per game, from the box score. |
| 3.6 | **Seconds per play** | ESPN's elapsed time on kept drives ÷ their scrimmage plays (relabeled drives left out, since ESPN's time belongs to another possession). |

---

## 4. Luck (with garbage-adjusted game results)

| # | Metric | Definition |
|---|--------|------------|
| 4.1 | **Garbage-adjusted score** | Each game's final score minus the offensive points scored on garbage-time drives (§1.6). The schedule in every trace lists what was removed. |
| 4.2 | **Pythagorean W%** | `PF^2.37 / (PF^2.37 + PA^2.37)` on garbage-adjusted points. |
| 4.3 | **Luck** | Actual W% minus Pythagorean W%. |
| 4.4 | **Luck (raw scores)** | The same calculation on unadjusted final scores, shown for comparison. |

---

## 5. Strength of schedule: efficiency version (the KenPom definition)

| # | Metric | Definition |
|---|--------|------------|
| 5.1 | **SOS** | Average AdjEM of all D-I opponents. |
| 5.2 | **Opp AdjO / Opp AdjD** | Average AdjO and AdjD of opponents. |
| 5.3 | **NCSOS** | SOS over non-conference games only. |

---

## 6. Strength of schedule: network win values (your +2 design)

When team A beats team B, the win is valued by the strength of B's network, three layers deep.

### 6.1 Records

- An FBS win counts. **A win over an FCS team is ignored completely.**
- **Losses count, including losses to FCS teams.** Your rule removes only FCS *wins*.
- Records are a **rate**, `wp = (W + 1) / (W + L + 2)`, not a raw count. Raw counts reward teams that have played more games. The +1/+2 is a one-win, one-loss prior, and it is the only variant that significantly improved prediction.

### 6.2 Exclusions (a team can't affect the value of its own win)

1. **Team A is removed from the graph.** Games against A are dropped from every record used to value A's win.
2. **Path exclusion.** Each record also drops games against every team above it in the tree: C drops games vs {A, B}; D drops games vs {A, B, C}; and D is never B.
3. FCS teams are never nodes.

### 6.3 Layers

```
P(B;A) = wp(B)                                    games vs A removed
S(B;A) = mean over C in Opp(B)\{A}   of wp(C)      games vs {A, B} removed
T(B;A) = mean over C of [ mean over D in Opp(C)\{A,B} of wp(D) ]   games vs {A, B, C} removed
NS(B;A) = 0.60·P + 0.30·S + 0.10·T
```

The weights were backtested on the 2025 season. The data's optimum puts tertiary at 0, and
0.60/0.30/0.10 is statistically indistinguishable from it (`ADVERSARIAL_REVIEW.md` §B2).

### 6.4 Win value (1.00 = a perfectly expected win)

```
WinValue(A beats B) = NS(B;A) / NS_win
NS_win = mean NS of the beaten team over every FBS-vs-FBS win this season (0.468 through week 5)
```

**The average FBS win is worth exactly 1.00.** 1.30 means the win was 30% more valuable than a
typical win. A win over an FCS team is worth 0.

### 6.5 Loss cost (you were undecided, so both totals are published)

```
LossCost(A loses to B) = (1 − NS(B;A)) / (1 − NS_loss)
NS_loss = mean NS of the winning team over every FBS-vs-FBS loss (0.535)
```

**The average FBS loss costs exactly 1.00.** Losing to a strong team costs less, and losing to a weak
team costs more. A loss to an FCS team costs the maximum, `1 / (1 − NS_loss)` ≈ 2.15.

### 6.6 Team-level outputs

| # | Metric | Definition |
|---|--------|------------|
| 6.6a | **Win Value Total** | Σ win values. This is the win-only version from your brief. |
| 6.6b | **Avg Win Value** | Win Value Total ÷ FBS wins |
| 6.6c | **Loss Cost Total** | Σ loss costs |
| 6.6d | **Net Resume** | Win Value Total − Loss Cost Total |
| 6.6e | **Net Resume per game** | Net Resume ÷ counted games (FBS games plus FCS losses; a win over an FCS team doesn't count, per your rule). **This is the resume ranking**, so a sixth game played isn't an advantage over five. |
| 6.6f | **Schedule strength** | Mean opponent NS, with FCS opponents counted as 0, ÷ NS_all (the mean over every FBS game side). 1.00 = an average FBS schedule. |
| 6.6g | **Best win / worst loss** | Highest win value and highest loss cost, with their trees. |

---

## 7. Situational football (your clock-burning question)

| # | Metric | Definition |
|---|--------|------------|
| 7.1 | **Clean interval** | Game-clock seconds from one snap to the very next snap by the same offense in the same quarter. The snap time is read from the "(MM:SS)" stamp in stat-crew text (88% of scrimmage snaps in 2026 FBS games; ESPN's narrative feed has no stamp); both ends must come from the same source. Not counted when something stopped the clock: kneel or spike, incompletion, score, turnover, penalty, out of bounds, a timeout or any other row in between, a first down in the final 2:00 of a half, the two-minute warning, or a reading of 2 s or less, or over 60 s. |
| 7.2 | **Usable clock** | A game whose snap-to-snap readings are 0 s less than 25% of the time. In 2026: 95% of P4-vs-P4 games, 86–91% of other FBS games, 15% of FCS-only games (384 of 640 overall). Each game's status is shown in its schedule row. |
| 7.3 | **Neutral pace** | Mean clean seconds per snap in Q1–Q3 with the score within 14 at the drive's start, leaving out any interval snapped in the final 2:00 of Q2, in usable-clock games. Published once a team has at least 30 intervals. In the round-3 research its split-half reliability was 0.87, against 0.39 for possessions per game. **Display only.** |
| 7.4 | **Neutral run rate** | Share of runs among scrimmage plays on the same drives. |
| 7.5 | **Lead-protection drive** | A kept drive in **Q4** with the offense **ahead by 1–21** at the first snap, in a usable-clock game, with **≥ 60% runs over ≥ 3 plays**. Its clean intervals (**≥ 2**) must average at least the team's **own neutral pace + 6 s/snap, capped at 38.0 s**. A fast team that slows down counts, and teams without a neutral pace use 38.0 s. Every input (the intervals, run count and threshold) is in the drive row. |
| 7.6 | **Lead-protection weight** | Tagged drives count at **0.5** in AdjO, AdjD and AdjSR. **This is the situational adjustment you asked for, and it is on by default.** Walk-forward it is accuracy-neutral (−0.013 ± 0.017 MAE vs no adjustment), so it changes how a clock-burning drive counts without costing prediction. Set `situational.lead_protection.weight` to 1.0 to turn it off, or 0 to drop those drives. |
| 7.7 | **Leader's final drive (removed)** | An earlier version dropped the leader's last drive of the game. It fired almost only on scoreless drives, so it was outcome-dependent, and it didn't improve accuracy. It was replaced by 7.5–7.6 (review §I). |

## 8. Discipline (penalties; descriptive, not in the rating)

The parser (`penalties.py`) turns every penalty in the play-by-play into a row in the game's penalty
table. It reads both ESPN text dialects and fouls embedded in other plays. The fields are period,
clock, offense, penalized team and unit, foul category, pre-snap flag, yards, status
(accepted/declined/offsetting), first down awarded, and the drive's keep status. Provenance fields
record how each value was read (dialect, team method, yards method, status inferred).
It matches the box-score count exactly for 90.3% of 2026 team-games (98.9% within one); 2025 is 74.7% (94.9%), 2024 is 53.8% (82.8%), 2023 52.3% (81.8%) and 2022 55.5% (77.7%), with 10.9%, 14.2% and 19.7% of those seasons' box-score fouls missing from ESPN's play-by-play. Each season's figures are shown on that season's Discipline tab, since the per-100-snap rates run low by the share of missing fouls. `python audit_penalties.py` reproduces these and writes every team-game to `out/penalty_audit.json`.

| # | Metric | Definition |
|---|--------|------------|
| 8.1 | **Pen/G, Pen Yds/G** | Accepted penalties and yards per game, from the box score. A box row is rejected if it shows more than 30 fouls or more than 25 yards per foul. |
| 8.2 | **Net Pen Yds/G** | Opponents' penalty yards minus the team's own, per game. |
| 8.3 | **Off Pen /100** | Accepted offensive fouls per 100 offensive snaps (scrimmage plays plus penalty-only snaps) on kept drives. A game whose play-by-play lists no penalties at all while the box score shows fouls is left out of every per-snap rate, snaps included (15 games in 2022, 6 in 2023, 4 in 2024, 1 in 2025); the trace names it. |
| 8.4 | **Off Pre-snap /100** | The pre-snap subset: false start, delay of game, illegal formation, shift, motion, procedure, substitution and snap, encroachment, and offside. |
| 8.5 | **Def Pen /100** | Accepted defensive fouls per 100 defensive snaps, on kept drives. |
| 8.5b | **Coverage** | The team's accepted fouls found in ESPN's play-by-play ÷ its box-score fouls, over the games the rates use. Below 100% the per-snap rates (8.3–8.6) read low by about the shortfall; the page marks teams under 90%. In 2024 41 of 134 FBS teams are under 90% (range about 75% to 110%); 2023, 49 of 133 (range 35% to 106%); 2022, 21 of 131 (33% to 109%); 2025, 4; 2026, none. |
| 8.6 | **Pen 1st downs allowed / G** | Accepted defensive fouls that gave a first down, on kept drives, per game with play-by-play. |
| 8.7 | **Situational fouls** | A Q4 leader's offensive delay of game is clock management. It is shown in the trace but left out of the rates. |
| 8.8 | **Conference average** | Shown beside each rate: the mean over the conference's ranked (5+ game) teams; tentative teams are left out, except in a season's first weeks, while fewer than half the rated teams are ranked: then every rated member counts (same rule as ≈n, §0.2). FBS Independents show the FBS average. Officiating differs by conference: the research found conference explains about 27% of team differences. ESPN's feed carries no crew data, so conference stands in for crew. Kicking- and return-unit fouls are listed but aren't in any rate. |

No penalty metric enters the rating. In the round-3 research, none of the 22 variants tested improved predictions, because
penalty yards and first downs already show up in points per drive.

---

## 9. Validation (published so you can judge the system)

| # | Metric | Definition |
|---|--------|------------|
| 9.1 | **Walk-forward test** | For each week of 2025 (4–16) and 2026 (3–5), and with the default model only 2024 (4–16), 2023 and 2022 (4–15), fit only on earlier weeks and predict that week. Reported as MAE and straight-up accuracy against raw-PPD and scoring-margin baselines, and against the sportsbook line where ESPN has one. |
| 9.2 | **Network backtest** | 2025, rolling weekly: log loss and accuracy for each weight set and rule variant, with paired standard errors. |
| 9.3 | **σ** | Out-of-sample margin error from this season's walk-forward test. Used to turn margins into win probabilities. |

## 10. Derived output

| # | Output | Definition |
|---|--------|------------|
| 10.1 | **Next-week predictions** | `Margin = (AdjEM_A − AdjEM_B)·Poss/μT + 2h·Poss·home`, with `P(win) = Φ(margin / σ)`. Every next-week game with an FBS team. Games involving a team with a tentative rating (under 5 games) are included and marked T. |
| 10.3 | **Anchors** | `out/<season>/anchors.json` lists every input to μ, the phantom-game values, μT and NS_win/NS_loss/NS_all, so the global constants can be recomputed. |
| 10.2 | **Conference ratings** | Average AdjEM of ranked members; tentative teams are left out. |
| 10.4 | **Weekly views** | Week *w* = the whole table rerun on the games of weeks 1..*w* only (`ratings.rate(…, through_week=w)`): every metric, rank, eligibility and tentative status as it stood then. Nothing is carried over from later weeks, with one exception: the win probabilities on an earlier week's picks use the season's walk-forward σ (10.1), which includes later weeks' errors. The margins and hit/miss do not depend on it. The latest week is the published table. `out/<season>/weekly.json` holds every week, each team's week-by-week line, and the week *w*+1 games predicted from week *w*'s ratings (10.1) with the actual scores. A game whose team has no rating yet (no game with usable play-by-play) can't be predicted; it is listed under `picks_skipped`, and the page counts it. |
| 10.5 | **AP and CFP ranks** | Reference only; never an input. Each week shows the newest AP Top 25 and CFP committee ranking that reflects games through that week. ESPN's "Week N" poll follows week N−1, and the preseason poll is week 0. `polls.py` checks each label against the release date: it must fall after the middle kickoff of its week and before the middle kickoff of the next. If no poll came out after a week (Army–Navy week), the newest earlier one is shown and labelled. |
| 10.6 | **Opponent ranks in the efficiency derivation** | Display only. Beside each game in a team's Offense (AdjO) table is the opponent's **AdjD** rank, and in the Defense (AdjD) table its **AdjO** rank: the rating that game is adjusted for. Two ranks are shown. **At game** is the rank entering the game, from the weekly view after the week before (10.4). **Now** is the rank in the table the trace covers. 1 = best (highest AdjO, lowest AdjD). Every number in a column is on one scale, the ≈n rule of §0.2: once ranked (5+ game) teams are at least half of the rated teams, a ranked opponent shows its official rank and a tentative one shows ≈ where it would slot among them; before that (a season's first weeks) every opponent shows ≈ its place among all rated teams, because an official rank among a handful of early 5-game teams would read "3" for a team that was 113th. There is no rank for an FCS opponent, a week-1 game (no table before it) or an opponent with no rating yet. `build.rank_in` writes them into each trace as `opp_rank`; `trace.py` prints them, with ~n for ≈n and - for none. |

---

## 11. Parameters (`config.json`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `min_games` | 5 | Games required for an official rating and rank; below it the rating is tentative (§0.2) |
| `garbage_margin` | 43 / 37 / 27 / 21 | Garbage-time margins by quarter |
| `end_of_half_seconds` | 60 | Drives whose first snap comes this late in Q2/Q4 are dropped |
| `prior_drives` / `prior_plays` | 12 / 65 | Phantom game size (§2.7) |
| `pythag_exp` | 2.37 | Pythagorean exponent |
| `net_weights` | 0.60 / 0.30 / 0.10 | P / S / T weights |
| `record_prior` | 1 W, 1 L | Laplace prior on records |
| `exclusion` | path | `path`, `parent` (RPI), or `none` |
| `fcs_losses_count` | true | FCS losses count as losses |
| `situational.lead_protection` | own pace + 6 s (cap 38.0 s), 2 intervals, 60% runs of 3 plays, lead ≤ 21, **weight 0.5** | §7.5–7.6 |
| `situational.neutral_margin`, `min_pace_intervals`, `max_zero_clock_share` | 14, 30, 0.25 | §7.2–7.3 |
| `explosive` | rush 12 / pass 16 | Explosive-play thresholds |
