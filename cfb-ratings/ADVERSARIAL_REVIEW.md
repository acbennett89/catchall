# Adversarial review

The system was attacked in four rounds:

1. **My own review** (§A–D). Every reading of your brief and every modelling choice was challenged with
   backtests: a full walk-forward on 2025, where ratings use only earlier weeks, and the 2026 data through week 5.
2. **An independent reviewer** (§E). It recomputed eligibility, drive points, win values and AdjO from
   the raw ESPN files without using this code. It confirmed the core math (all 661 published values matched: 271 win
   values, 271 loss costs, 113 FCS wins and 6 FCS losses) and found three major and six minor defects. All three are fixed, and the review text was corrected where it was wrong.
3. **Your follow-up request** (§F–H): penalties, garbage time and situational football. Each topic
   had a research agent and two adversarial verifiers. One reproduced the numbers; the other attacked
   the method. Their corrections are folded in below.
4. **A final independent review** (§I) of the finished system: parser, metrics, documents, and
   leaks of unpublished numbers. It raised 40 findings, 14 of them major. A second agent tried to refute each
   major one: all 14 were upheld, 12 at reduced severity. All 40 are fixed. Every number in this
   document was refreshed on the final code unless it is marked as research (see the note in §F).

Differences are reported as `difference ± standard error`. |z| under about 2 is within noise, and
where many variants were tried, the bar is higher (§G).

---

## Summary

| # | Challenge | Verdict | What the system does |
|---|-----------|---------|----------------------|
| A1 | "1.00 = expected win" has two readings | Ambiguous brief | Opponent-quality reading. **The average FBS win is worth exactly 1.00** (corrected in round 2; inputs in `out/2026/anchors.json`) |
| A2 | Raw win counts reward playing more games | Real fairness problem, no predictive gain | Records are rates, (W+1)/(G+2) |
| A3 | Do FCS losses count? | The brief excludes only FCS wins | They count (6 teams affected) |
| A4 | Should losses count? | Prediction can't decide it; fairness can | Both published; the resume is ranked by **net per counted game** (FCS wins excluded from the count in round 4) |
| A5 | What counts toward "5 played games"? | Literal reading | 107 of 138 rated. Below 5 games, nothing is published (fixed in round 2) |
| B2 | Network weights | Backtested | 0.60/0.30/0.10, within noise of the optimum (tertiary = 0). The network beats win% alone only nominally |
| B3 | Does tertiary matter? | Barely | Effective influence is about 6% of primary |
| C1 | Does opponent adjustment help? | Yes | Walk-forward MAE 12.47 vs 14.02 raw (same games) |
| C2 | Against the betting market | The market is better early in the season | 1.65 ± 0.54 points worse on 2026 weeks 3–5 |
| C3 | Home field inflated by shrinkage | Confirmed (3.6 → 4.6 pts) | Two-stage estimate |
| E | Bad ESPN running scores corrupted drive points | **Confirmed defect, fixed** | Points rebuilt from play types |
| E | Teams under 5 games leaked through traces and predictions | **Confirmed defect, fixed** | Masked; internal inputs labeled |
| F | Penalties | Parsed and validated; no predictive value | Published as descriptive "Discipline"; not in the rating |
| G | Clock-burning (lead protection) | Real in pace and play-calling; no adjustment improves accuracy | Tagged and shown; tagged drives count **half (weight 0.5) by default**, which is accuracy-neutral. The outcome-dependent final-drive rule was removed |
| H | Garbage time | The test can't tell the rules apart | Connelly rule kept for traceability; Luck uses garbage-adjusted scores |
| I | Final review: 40 findings | 14 major findings upheld (12 at reduced severity) | All fixed: snap-time clocks, parser fixes, per-counted-game resume, full traceability of internal inputs and constants |
| J | Season picker and 2024 (round 5): 25 findings | 22 confirmed, 2 partly, 1 refuted | All fixed; 2024 published with a data note (7% of FBS games lack drives, no snap stamps, penalties 54% exact) |

---

## A. Reading your brief

### A1. "1.00 = a perfectly expected win"

The phrase has two readings: opponent quality (a typical win is 1.00, a harder win counts more) or
performance against expectation (1.00 = won by exactly the predicted amount). Your brief builds the
value from the opponent's *wins*, which carry no margin, so this system uses the opponent-quality reading.

**Correction from round 2.** I originally anchored on the average opponent over *all* game sides and
claimed the average win was worth 1.00. The reviewer showed the average *actual* win was worth 0.934.
Winners usually beat weaker teams, so the true claim was weaker than stated. The anchor now makes the
claim exact:

- **NS_win** = mean network strength of every team beaten in an FBS game (0.468). The average FBS win = 1.00.
- **NS_loss** = mean network strength of every team that won (0.535). The average FBS loss costs 1.00.
- On the 2026 results both averages come out at exactly 1.000. Every input is listed in `out/2026/anchors.json`, and a unit test checks the property on a small hand-built schedule.

Reading 2 is covered separately: each game's opponent-adjusted margin is in the efficiency trace, and Luck (§4) compares wins with scoring.

### A2. Raw win counts or rates?

Taken literally, the brief sums wins at each layer. Through week 5, FBS teams have played 3–6 FBS
games, so raw counts give a 6-game opponent twice the secondary mass of a 3-game one. In the 2025
backtest the freely weighted raw-count version was statistically tied with rates (−0.0026 ± 0.0066 and
−0.0069 ± 0.0055 log loss). **Decision:** rates, which remove the games-played artifact at no cost.

### A3. FCS losses

Your rule removes FCS *wins*. If FCS losses were ignored too, losing to The Citadel would look better than
beating them. Ignoring them made no measurable predictive difference (+0.0008 ± 0.0008). **Decision:** FCS
losses count, and an FCS opponent has network strength 0, so the loss costs the maximum (≈ 2.15). Teams
affected in 2026: Bowling Green (Tarleton State), Charlotte (The Citadel), Utah State (Idaho State),
Northern Illinois (Illinois State), Nevada (Montana State), UL Monroe (SE Louisiana).

### A4. Should losses count?

- **Prediction can't settle it.** In 2025, net and win-only resumes carry identical information
  (+0.0002 ± 0.0047). At equal games played, W and W−L say the same thing.
- **Fairness settles it.** Win-only can't tell 5-0 from 5-2. It gives an FCS loss no penalty, and it
  rewards games played: 5-1 USC, with 6 games, ranks 2nd on win value total, ahead of unbeaten Notre Dame
  and Miami. In 2026 there are 22 pairs where a team with a loss outranks an unbeaten team on win value total.
- **Correction from round 2.** Net Resume *total* has the same games-played bias: USC is 4th, and 9 of
  the 22 inversions remain. The resume ranking is therefore **Net Resume per game**: USC is 12th and
  none of the 22 remain. Totals are still published.
- **Correction from round 4.** "Per game" first meant all games. An FCS win adds 0 to Net Resume but 1
  to that count, so it pulled every resume toward 0. That broke your rule that FCS wins don't count:
  Buffalo's two FCS wins moved it up 12 places. The divisor is now **counted games** (FBS games plus FCS
  losses). Buffalo is −3.641 / 3 = −1.214, 105th.

### A5. What counts toward "5 played games"?

The literal reading is any completed D-I game: 107 of 138 teams after week 5. Counting FBS games only
would rate 17.

**Correction from round 2.** The reviewer found that teams under the minimum still had full ratings in
their trace files, on the web page and in 24 predictions. Now:
- an ineligible team's trace shows only its schedule;
- predictions involving it are dropped (58 → 34);
- inside an eligible team's trace, an ineligible opponent's rating is an unavoidable input, so it is
  marked "internal input, not a published rating".

**Change at your request (after round 5).** Teams under 5 games now get a **tentative** rating: the
same numbers and full trace, marked T, never ranked, with tentative predictions marked too. The
5-game rule still decides who is ranked. Nothing in the model changed, so accuracy is unaffected.

---

## B. The +2 network

### B1. Self-influence

Two rules stop a win from affecting its own value. First, A is removed from the graph. Second, path
exclusion: each record drops games against every team above it in the tree. Path, parent-only (RPI)
and no deep exclusions all predict equally well (+0.0002 ± 0.0003 and −0.0041 ± 0.0029), so the
strictest fairness rule is used. The reviewer confirmed it is implemented exactly as specified.

### B2. Weights (2025 backtest, 567 FBS games; a home-field-only model scores 0.6832)

| P / S / T | Log loss (≥3 games) | Log loss (≥5) | Accuracy |
|---|---|---|---|
| 1.00 / 0 / 0 (win% alone) | 0.5804 | 0.5681 | 68.1% |
| 0.50 / 0.30 / 0.20 (provisional) | 0.5743 | 0.5657 | 69.3% |
| 0.571 / 0.286 / 0.143 (4:2:1) | 0.5735 | 0.5647 | 69.0% |
| **0.60 / 0.30 / 0.10 (chosen)** | **0.5729** | **0.5643** | 69.3% |
| 0.667 / 0.333 / 0 (RPI-like) | 0.5718 | 0.5637 | 69.5% |
| best with wP ≥ wS ≥ wT | 0.5709 (0.60/0.40/0) | 0.5637 (0.65/0.35/0) | 69.0% |

The network is only nominally better than win% alone. The reviewer's paired test gives +0.0075 ± 0.0040
log loss at ≥3 games (z 1.9) and +0.0037 ± 0.0043 at ≥5 (z 0.9), which is within noise on one season. The
optimum puts tertiary at 0. The chosen weights trail it by +0.0019 ± 0.0016 and +0.0006 ± 0.0008, which
keeps your +2 structure at no measurable cost.

### B3. Nominal weight isn't effective weight

Across 542 FBS game sides the layers have SDs of P 0.199, S 0.115 and T 0.069. Tertiary is a mean
of about 3 branch means, each over about 3 teams (about 9 records in all), so it regresses toward .500. Effective influence (weight × SD) is P 0.119,
S 0.035, T 0.007, so tertiary moves a win value about 6% as much as primary does.

### B4. The negative tertiary coefficient

With free weights, tertiary gets a negative coefficient in every variant. Two mechanisms were tested
and ruled out: leakage of B's own results into T (path exclusion didn't change it) and collinearity
with S (r = −0.03). The cause is unexplained, so the weight is held small and non-negative.

### B5. Small samples

The one-win, one-loss prior is the only change that significantly improved prediction
(+0.0049 ± 0.0024 and +0.0040 ± 0.0015 without it).

### B6. The network is blind to margin and venue

The two schedule measures agree only loosely (Spearman 0.83). Miami is #24 by network schedule
strength but #89 by efficiency SOS; Texas Tech is the reverse (#70 vs #23). The **ranking uses
AdjEM**, as KenPom does. The network is the resume, and the two correlate at 0.87.

### B7–B8

A win's value changes as the beaten team's later games come in, as with RPI or strength of record.
Conference games are zero-sum, so conference strength enters only through non-conference games.

---

## C. The efficiency model

### C1. Opponent adjustment works

Walk-forward results, using earlier weeks only. Baselines exist only for FBS-vs-FBS games, so all
methods are compared on the same games:

| MAE, points | 2025 wk 4–16 (617) | 2026 wk 3–5 (171) | 2024 wk 4–16 (611) | 2023 wk 4–15 (597) | 2022 wk 4–15 (584) |
|---|---|---|---|---|---|
| **AdjEM model (Power)** | **12.47** | **12.77** | **13.11** | **12.80** | **13.06** |
| Average scoring margin + home field | 13.19 | 14.27 | 13.10 | 13.34 | 12.84 |
| Raw points per drive + home field | 14.02 | 17.71 | 15.12 | 14.06 | 15.05 |

Over every predictable game, MAE is 12.43 with 72.3% of winners picked in 2025 (639 games), and 12.87
with 80.0% in 2026 (205 games). **2024 is weaker:** 13.09 with 71.5% (631 games), and the model only
ties average scoring margin there, though it still beats raw points per drive by 2 points. ESPN's 2024
play-by-play leaves 7% of FBS games without usable drives and has no snap-time stamps (§J), so treat
2024 ratings as less precise. A stricter parser that recovered some of those games did not change this
(13.12 vs 13.14). **2023** behaves like 2025 (12.80 vs 13.34; 73.0% of 614 games picked). **2022** is
the one season where average scoring margin beats the model (12.84 vs 13.06; 69.1% picked): ESPN's
2022 play-by-play leaves 11% of FBS games without usable drives (the scores-only baseline still sees
them), and none has snap-time stamps. Opponent adjustment still beats raw points per drive in every
season, by 1.3 to 4.9 points. Calibration (2025, 639 games):

| Predicted (bin mean) | 0.55 | 0.65 | 0.75 | 0.85 | 0.96 |
|---|---|---|---|---|---|
| Won | 0.60 | 0.60 | 0.72 | 0.86 | 0.94 |

### C2. Against the betting market

On 2026 weeks 3–5 (205 games) the model's MAE is 12.87 against the market's 11.22, worse by
**1.65 ± 0.54** points. ESPN keeps lines for only 55 of the 2025 games; on those the two were tied.
The market uses preseason priors, injuries and recruiting; this model uses only this season's games.

### C3. Home field

Estimated jointly with the shrinkage prior, home field comes out at 4.61 points; without the prior it is
3.57. Strong teams host most games, so the shrinkage residual was being credited to home field. It is
now estimated without shrinkage and held fixed. The reviewer confirmed this introduces no bias.

### C4. How much regression to the mean?

On the final code, 2025 walk-forward MAE is 13.76 with no prior, 12.71 at 6 drives, **12.43 at 12**
and 12.37 at 24. An earlier sweep found 36 drives level with 12 on 2025 (12.44 vs 12.46) and worse on
the 2026 holdout. 12 and 24 are within noise of each other, and 12 (one phantom game) is easier to read.

### C5. Garbage time

See §H.

### C6. Noise at week 5

The median AdjEM standard error is **±7.0 points** (IQR 4.4–8.5). Treat ranks 5–25 as a band, not an order.

### C7. ESPN data defects

- Drive points come from rebuilt scoring plays (§E, M1). In 2026, ESPN's running score is wrong on 21
  scoring plays in 8 FBS-involved games. 5 more FBS games use the running-score fallback because ESPN mislabels an extra point.
- 4 games are dropped from efficiency in 2026; all four are FCS-only.
- 55 games are kept with a data note, such as a corrected running score or a relabeled drive. Each note is in the trace.
- The scoreboard API silently returns 25 games when asked for more than 500, so the fetcher fails loudly instead.

### C8. Other choices

- **FCS games are in the efficiency model, opponent-adjusted.** Your FCS rule applies in full to the
  network.
- **Overtime drives are dropped.** They start at the opponent's 25.
- **Late-half drives are dropped by situation, not by result.** Before round 2, a late drive that
  failed was dropped while one that scored was kept. Since round 4 the time used is the snap stamp,
  not ESPN's end-of-play clock.
- **There is no recency weighting yet.** Five games are too few to estimate one.

---

## D. What would change these conclusions

- **More seasons.** Every backtest uses one season, and the weight optimum is flat.
- **A preseason prior** would close most of the gap to the market, at the cost of putting
  non-2026 information into a 2026 rating.

---

## E. Independent recomputation (round 2)

A separate reviewer wrote its own code against the raw ESPN files. It recomputed:

| Item | Result |
|---|---|
| Games, W-L, eligibility for all 138 FBS teams | 138/138 match |
| Every drive of Georgia State at Kennesaw State, with exclusions | Match |
| Full re-solve of every FBS team's AdjO / AdjD / AdjEM | Match; largest gap 3e-5 (solver tolerance) |
| NS_ref over all 542 FBS game sides | Match |
| All 661 published values (271 win values, 271 loss costs, 113 FCS wins, 6 FCS losses), plus Net Resume | Largest gap 4e-16 |
| AdjO / AdjD rebuilt from trace lines | Match |
| UTEP at New Mexico drive points | **Mismatch**: New Mexico 21 points on 5 drives vs our 13 (M1) |

Findings and fixes:

| # | Finding | Fix |
|---|---|---|
| M1 | ESPN's running score on scoring plays is sometimes wrong even when the final reconciles. TD drives were credited 1, 6, 13 or −8 points, changing 19 ranks. My review wrongly called one case "a missed PAT". | Points are rebuilt from play type plus extra-point result and reconciled to the final (§1.1); parser tests added. UTEP–New Mexico now gives New Mexico 21 points on 5 drives, matching the reviewer. |
| M2 | Teams under 5 games were published through traces, the page and predictions. | Masked (A5). |
| M3 | "Average win = 1.00" was false (0.934). | Re-anchored (A1). |
| m1 | 17 drives had the wrong team label (ESPN). | Offense taken from who snapped the plays. |
| m2 | A punt-return safety counted as offensive points; 22 muffed punts counted as rushes; 13 snaps were listed twice. | All three excluded. |
| m3 | The end-of-half rule kept late drives that scored and dropped the ones that failed. | Decided by time at the first snap. |
| m4 | Net Resume total rewards games played. | Ranked per game (A4). |
| m5 | Doc/code mismatches: the μ definition, the schedule-strength definition, a validation description, a stale docstring, and the FCS-loss count. | Fixed. AdjO is now *exactly* "vs an average FBS defense" (§2). |
| m6 | Ties were treated inconsistently. | Both modules skip ties (none exist in modern CFB). |

Effect on prediction, paired on the same games. All parser changes from the first commit through
round 3: 2025 +0.019 ± 0.070, 2026 −0.174 ± 0.079, pooled −0.028 ± 0.057. The round-2 fixes alone:
pooled −0.047 ± 0.065. The round-3 parser changes alone: +0.019 ± 0.027. They are correctness fixes,
neutral for accuracy. (Round 2 of this document mislabeled the first figure as "round-2 fixes"; the
final reviewer caught it.)

---

## F. Penalties

> **Measurement note for §F–H.** Two kinds of numbers appear here.
> - **Research numbers** (variant tests, reliabilities, the 27% conference share, pace-by-score
>   curves) were measured by research agents in round 3, on the parse as it stood before the round-2
>   and round-3 parser changes. Their scripts are not in the repo, so they can't be reproduced from
>   it; treat them as research findings. The parser changes since then were prediction-neutral
>   (pooled −0.028 ± 0.057, §E), so the comparisons should stand, but counts can differ.
> - **Repo numbers** were refreshed on the final code and can be regenerated: penalty-parser accuracy
>   (`python audit_penalties.py`), the garbage-time test and share (`validate.py`, §H), usable-clock
>   coverage, and the lead-protection weight tests (§G, §I).

**Parser.** `penalties.py` reads both ESPN text dialects plus fouls embedded in other plays. Against the box score:

| Season | Count exact (team-games) | Within 1 | Total fouls vs box |
|---|---|---|---|
| 2026 | 90.3% | 98.9% | −1.05% |
| 2025 | 74.7% | 94.9% | −3.45% |
| 2024 | 53.8% | 82.8% | −10.9% |

All D-I team-games with play-by-play, regular season. `python audit_penalties.py` reproduces every
row and writes each team-game to `out/penalty_audit.json`. 2024 was added with the season picker. Its
shortfall comes from ESPN, not the parser: in a sample of 400 games the box scores show 5,149 fouls but
only 4,802 plays mention a penalty, and four games list none at all. Those four are left out of the
per-snap rates (METRICS 8.3), and each season's audit is printed on its Discipline tab.

The 2025 gap is concentrated in weeks 1–8, when ESPN mixed two text dialects and dropped some fouls from the
text. The verifier caught one corrupt box-score row ("743-37") that had inflated the reported 2025
shortfall to 7%. Box rows are now sanity-checked. About half of 2026's missing fouls have no trace in the text at all.

**Is penalty-proneness a team trait?** Only modestly. Full-season reliability is 0.27–0.62, and at
week 5 it is 0.16–0.40, mostly noise. The steadiest metric is offensive pre-snap fouls (0.62).

**Does it predict?** No. None of 22 penalty variants beat the model in walk-forward (net penalty yards
+0.0016 ± 0.030). Penalty yards and first downs are already inside points per drive.

**Verifier corrections adopted:**
- Rates are per 100 snaps, so fast teams aren't penalized for running more plays (r = +0.32 between penalties and snaps per game).
- Rates use only kept drives.
- A Q4 leader's delay of game is situational, not indiscipline.
- The conference average is shown beside each rate, since conference explains about 27% of team differences (research). ESPN's feed has no crew data, so conference stands in for crew.

**Rejected:** a penalty-inclusive success rate. It scored touchdowns that counted as failures, and its
"nullified snap" rule was a guess that ESPN's own yardage contradicted 96% of the time. Only snaps the
text confirms were wiped out ("NO PLAY") are removed.

---

## G. Situational football: a high-tempo team burning clock to protect a lead

**It is real.** Measured on clean snap-to-snap clock intervals over two seasons:
- Up to the end of Q3, pace moves less than ±1 s/snap with the score.
- In Q4, a team ahead by 9–16 slows by up to 6 s/snap relative to its own neutral pace, and the fastest third of teams by up to 10 s.
- Run rate rises from about 52% to 73–85%.
- A leader's late-Q4 drives score 0.5–1 points per drive below expectation.

**No adjustment improves accuracy.** About 27 efficiency variants were tested walk-forward:
- The best (half-weighting state-and-behaviour drives) was −0.029 ± 0.017. A permutation test across all variants puts its family-wise p at 0.38, which is noise.
- Dropping a leader's late-Q4 drives by game state alone was nominally *worse* (+0.137 ± 0.057).
- Random exclusions of the same size cost about as much (+0.10 to +0.14), so the harm is mostly lost data, not a football effect.

**The tagged drives aren't the underperforming ones.** The behaviour test needs clean clock readings
over a sustained drive, so it selects drives that went well (residual −0.19 / +0.16). The underperforming
late drives are the ones it can't measure (−0.77). Down-weighting tagged drives is close to cosmetic:
at weight 0.5 no team moves more than 3 ranks, and fast and slow teams move alike (+0.09 vs +0.06).

**What the system does (final, round 4):**
- Each lead-protection drive is **tagged and shown** in the trace and on the page (METRICS §7.5). The rule:
  Q4, ahead by 1–21, a usable-clock game, ≥ 60% runs over ≥ 3 plays, and ≥ 2 clean snap-to-snap
  intervals averaging at least **the team's own neutral pace + 6 s, capped at 38 s**. The relative
  threshold follows the research above, where a leader slows by up to 6 s/snap against its own pace.
  It catches your example, a fast team slowing down: a 26 s/snap team is tagged at 32 s. Every
  interval, the run count and the threshold are in the drive row, so a tag or non-tag can be checked by hand.
- Intervals are read from the snap-time stamp in the play text ("(07:10) …"), not ESPN's clock
  field, which is roughly end of play. The two-minute warning breaks an interval.
- **Tagged drives count at weight 0.5 by default.** This is the adjustment you asked for. On the
  final code it is accuracy-neutral in paired walk-forward: weight 0.5 vs 1.0 is −0.013 ± 0.017 MAE,
  and weight 0 is −0.012 ± 0.035. It moves no team more than 5 ranks (Memphis, 37th → 42nd) or
  1.08 AdjEM (Boise State). Set `situational.lead_protection.weight` to 1.0 to switch it off.
- **The leader's final-drive rule was removed.** An earlier version dropped the leader's last drive
  of the game. It almost only fired on scoreless drives: in 2025 it dropped 1 scoring drive of 308,
  where comparable kept drives score 33% of the time. It was therefore outcome-dependent, and it
  never improved accuracy (the reviewer measured +0.021 ± 0.027).
- **Neutral pace** (s/snap, Q1–Q3, score within 14) is published. It is a far steadier team trait than possessions per game (split-half 0.87 vs 0.39), but as a predictor it hurt margins (+0.10 ± 0.05), so it is display only.
- **Tempo (AdjT) is unchanged.** Q1–Q3-only possessions (+0.031 ± 0.024) and neutral-pace tempo (+0.015 ± 0.040) didn't help.

**Caveat: clock coverage.** A game's clock is usable when its snap-to-snap readings are 0 s less than
25% of the time. In 2026 that holds for 95% of P4-vs-P4 games, 91% of P4-vs-G5, 86% of G5-vs-G5, 85% of
FBS-vs-FCS and 15% of FCS-only games: 384 of 640 overall. Each game's status is shown in the team's
schedule (trace and page). Q4 leading drives are counted only in usable-clock games, so "N of M" on the
page compares like with like.

## H. Garbage time, revisited

| Rule | 2025 drives flagged | MAE vs current rule | Verdict |
|---|---|---|---|
| **Current (Connelly margins)** | 3,556 (10.1%) on the final parse, regular season; 3,253 in the research | — | **Kept** |
| No garbage filter | 0 | +0.027 on the final code (12.456 vs 12.429; round-3 paired SE ±0.12) | Same |
| Time-aware sqrt rule (fit on 2025 wk 1–3) | 5,569 | +0.084 ± 0.082 | Same; flags 70% more |
| State-only win-probability model, leader WP ≥ 0.99 (fit on wk 1–3) | — | +0.071 ± 0.072 | Same; agrees with the current rule on 96% of drives |
| ESPN win probability ≥ 0.975 | 650 in Q1 alone | pooled +0.48 ± 0.17 | **Rejected** |
| Leader-only drop | — | −0.07 ± 0.07 | Rejected (unfair, below) |

- **ESPN's win probability contains the betting line.** It is never 0.5 at kickoff and correlates 0.84
  with the spread. Using it would put market information into the rating.
- **The test can't tell the rules apart.** The verifier showed that even a perfect rule could gain at most
  0.22 MAE, below the team-clustered standard error. So the current rule is kept because you can check it
  by hand (quarter, score before the drive, four numbers), not because the data proved it best. It
  behaves like a conservative "leader wins 99%+" rule: in the research, the leader went on to lose only 2 of 3,253 flagged drives.
- **Leader-only exclusion was rejected as unfair.** It charges a team's defense for garbage-time points while
  dropping its own garbage-time offense, which pulls dominant and fast teams down. Its small gain disappears on cleaner targets.
- **Garbage-adjusted results are new.** Garbage-time points were flowing straight into Pythagorean
  W% and Luck: 8.9% of FBS teams' points in 2025 and 13.3% in 2026 (7.2% and 8.8% in FBS-vs-FBS games;
  early-season FCS blowouts drive the 2026 figure). Luck now uses each game's score with the
  offensive points from garbage-time drives removed. Each removal is listed per game, and the raw
  version is shown beside it. Example: Rutgers' luck goes from −0.258 (raw) to −0.116 (adjusted).
- **Fairness.** The research found the rule raised the fastest-pace quartile by +0.80 AdjEM in 2025. On the
  final 2026 data it doesn't favor fast teams: against no filter, the fastest AdjT quartile moves +0.10
  and the slowest +0.35 (all rated teams +0.21). By neutral pace it is +0.37 for the fastest quartile and +0.54 for the slowest.
- **Order of checks.** Since round 4, garbage time is checked before the end-of-half rule, so a late
  garbage-time touchdown is always taken out of the garbage-adjusted score.

---

## I. Final independent review (round 4)

Four reviewers worked on the finished system, one each on the parser, the metrics, the documents, and
leaks of unpublished numbers. They raised 40 findings, 14 of them major. A separate verifier tried to
refute each major finding; all 14 were upheld, 12 at reduced severity. Every finding is fixed, and
the regression tests in `tests/test_parse.py` are built from the plays they cited.

| Area | Finding | Fix |
|---|---|---|
| Clock | Snap-to-snap intervals and the end-of-half test read ESPN's clock field, which is about end of play. That flipped about 13% of lead-protection tags and dropped 44 drives that started with more than 60 s left. | Snap time from the "(MM:SS)" stamp in the play text, with ESPN's clock only as a fallback; both ends of an interval must come from the same source. The trace shows the clock source. |
| Clock | The two-minute warning wasn't detected; stale 0:00 clocks dropped mid-quarter drives as end of half. | An interval that straddles 2:00 is broken. A 0:00 reading falls back to ESPN's drive start clock. |
| Clock | Usable-clock figures in this review (P4 65%, G5 55%) were wrong, and the claimed per-team disclosure didn't exist. | Recomputed (§G). Each game's clock status is in the schedule. Q4 leading drives are counted in usable-clock games only. |
| Parser | Text tests ran over the extra-point narrative ESPN appends to touchdowns. That deleted 11 real possessions and dozens of snaps. | The try text is cut before testing, and offensive touchdowns are protected. |
| Parser | Lost fumbles typed "Fumble Recovery (Own)" counted as gains, some as explosive plays. | A fumble is a turnover when the defense ends with the ball. |
| Parser | Points were credited by drive membership, not by who snapped the scoring play (FCS-only games). | A score counts for an offense only if it snapped the play. |
| Parser | Relabeled drives kept ESPN's shifted result and elapsed time. | Both blanked on relabeled drives; the note says why. |
| Situational | The final-drive rule was outcome-dependent, default-on and never validated; the docs said otherwise. | Removed (§G). |
| Situational | The lead-protection weight was off by default, and the fixed 38 s rule missed a fast team slowing down. | Relative threshold (own pace + 6 s, cap 38 s); weight 0.5 by default, accuracy-neutral (§G). |
| Situational | The Q2 cut in neutral pace was applied per drive, with a falsy-zero bug. | Applied per interval. |
| Resume | Net Resume per game counted FCS wins in the divisor. | Divided by counted games (§A4). |
| Traceability | Neutral pace, run rate, discipline rates, AdjSR and the lead-protection decision couldn't be rebuilt from the traces. | Each drive row now carries its intervals, run count, penalty-only snaps, clock source and weight. Each game carries clock status and box-score penalties. AdjSR has its own trace section (`trace.py --section success_rate`). |
| Traceability | Internal ratings of unrated and FCS opponents were inputs but never derived, so 101 of 107 teams' chains stopped there. | `out/<season>/traces/internal/` holds each one's derivation, with no AdjEM, rank or resume (`trace.py --internal`, or the page's "internal*" links). |
| Traceability | The global constants (μ, the phantom game, μT, NS_win, NS_loss) couldn't be recomputed. "Average AdjEM is 0" was false for the published table. | `out/<season>/anchors.json` lists every input. The docs say the 0 holds over all 138 FBS teams; the published 107 average −0.18. |
| Traceability | The build self-check covered only the 138 FBS teams. | It now covers all 266 D-I teams. |
| Leaks | Unrated teams were listed in order of their internal AdjEM. | Listed by name. |
| Leaks | Unrated teams' garbage-adjusted scores were published per game. | Removed from their schedules. |
| Display | The foul table said "Counted? yes" for special-teams fouls that the rates leave out. Tempo's internal inputs were unlabeled. | Both labeled correctly. |
| Docs | Stale or wrong figures: running-score errors (8 games, not 4), tertiary breadth (9 records, not 25), "the network beats win%", 18 inversions (22), the 2025 penalty audit, the officiating-crew claim, "271 beaten FBS teams", the A1 test claim, the review's description of the round-2 fixes, and the README's dependencies. | Corrected in this document, METRICS, TRACE and README. Penalty audit and garbage numbers can now be regenerated by scripts. |

**Effect of round 4 on prediction.** On the final code the 2025 walk-forward MAE is 12.43 (72.3% of
winners) and the 2026 holdout MAE 12.87 (80.0%). The ratings changed through correctness fixes, not tuning;
the lead-protection weight was the only modelling choice, and it is accuracy-neutral.

---

## J. Seasons: the season picker and 2024 (round 5)

The page now switches between seasons (2024, 2025, 2026). Each season is rated on its **regular season**,
conference title games and Army–Navy included. ESPN files the FCS playoff rounds among regular-season
weeks; `parse.py` flags them and `ratings.load()` sets them aside (17 games in 2025, 20 in 2024).
Removing them from 2025 moved its validation by at most 0.0006 MAE.

**Data coverage differs by season** and is printed on each season's page:

| Season | FBS games with usable drives | Snap-time stamps (kept drives) | Penalties exact vs box | Teams under 90% penalty coverage |
|---|---|---|---|---|
| 2024 | 810 of 873 (93%) | ~0% | 53.8% | 41 of 134 |
| 2025 | 871 of 888 (98%) | 37% | 74.7% | 4 of 136 |
| 2026 (wk 1–5) | 390 of 390 | 88% | 90.3% | 0 of 107 |
| 2023 | 830 of 868 (96%) | ~0% | 52.3% | 49 of 133 |
| 2022 | 758 of 854 (89%) | ~0% | 55.5% | 21 of 131 |

In 2024 the missing drives come from ESPN: some scoring plays appear in the scoring summary but in no
drive, so the parser drops the game from efficiency rather than guess. Those games still count in
records, win values and the resume. Without snap stamps the clock rules run on the end-of-play clock,
so 2024 neutral pace and lead-protection tags are not comparable with 2026.

Three reviewers (page behavior, data pipeline, docs and 2024 data) and three verifiers checked the
work. Findings and fixes:

| Area | Finding | Fix |
|---|---|---|
| Page | Enter on a row opened the drawer and closed it at once. | The keystroke no longer reaches the Close button. |
| Page | A slow or failed trace load could replace or reopen a drawer the user had left. | Each drawer request carries a token; late results for anything else are dropped. |
| Page | Links didn't name the default season, were read only at load, and an unknown season silently fell back. | Links always carry the season (`#s2026-t87`), follow `hashchange`, and say when a season isn't available. |
| Page | The season select lost keyboard focus; long paths scrolled sideways on phones. | Focus is kept; paths wrap. |
| Page | Opening the file from disk broke every drill-down with a "reload" message that couldn't help. | The page says to serve the folder; TRACE.md too. |
| Pipeline | "Regular season final" depended on how many weeks were downloaded. | It now requires every week of ESPN's regular-season calendar and no game left. |
| Pipeline | Dates were UTC, so late kickoffs showed the next day. | US Eastern. |
| Pipeline | Data files kept their names across rebuilds, so a cached file could pair with a new page. | Files are named by content hash. |
| Pipeline | 2024 penalties weren't audited, and four games with no penalties in the play-by-play deflated rates. | Every season is audited; those games are left out of the rates; a per-team Coverage column marks teams under 90%. |
| Docs | 2026 figures read as general; stale counts; 2024 validation missing. | Labeled, refreshed, and the 2024 row added to §C1. |
| CLI | `trace.py --internal` on a team rated that season gave "ambiguous". | It says the team is rated. |

