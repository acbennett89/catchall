# Adversarial review

The system was attacked in three rounds:

1. **My own review** (§A–D). Every reading of your brief and every modelling choice was challenged with
   backtests: a full walk-forward on 2025, where ratings use only earlier weeks, and the 2026 data through week 5.
2. **An independent reviewer** (§E). It recomputed eligibility, drive points, win values and AdjO from
   the raw ESPN files without using this code. It confirmed the core math (661 of 661 win values matched) and found
   three real defects. All three are fixed, and the review text was corrected where it was wrong.
3. **Your follow-up request** (§F–H): penalties, garbage time and situational football. Each topic
   had a research agent and two adversarial verifiers. One reproduced the numbers; the other attacked
   the method. Their corrections are folded in below.

Differences are reported as `difference ± standard error`. |z| under about 2 is within noise, and
where many variants were tried, the bar is higher (§G).

---

## Summary

| # | Challenge | Verdict | What the system does |
|---|-----------|---------|----------------------|
| A1 | "1.00 = expected win" has two readings | Ambiguous brief | Opponent-quality reading. **The average FBS win is worth exactly 1.00** (corrected in round 2) |
| A2 | Raw win counts reward playing more games | Real fairness problem, no predictive gain | Records are rates, (W+1)/(G+2) |
| A3 | Do FCS losses count? | The brief excludes only FCS wins | They count (6 teams affected) |
| A4 | Should losses count? | Prediction can't decide it; fairness can | Both published; the resume is ranked by **net per game** |
| A5 | What counts toward "5 played games"? | Literal reading | 107 of 138 rated. Below 5 games, nothing is published (fixed in round 2) |
| B2 | Network weights | Backtested | 0.60/0.30/0.10, within noise of the optimum (tertiary = 0) |
| B3 | Does tertiary matter? | Barely | Effective influence is about 6% of primary |
| C1 | Does opponent adjustment help? | Yes | Walk-forward MAE 12.53 vs 14.19 raw (same games) |
| C2 | Against the betting market | The market is better early in the season | 1.6 ± 0.5 points worse on 2026 weeks 3–5 |
| C3 | Home field inflated by shrinkage | Confirmed (3.7 → 4.7 pts) | Two-stage estimate |
| E | Bad ESPN running scores corrupted drive points | **Confirmed defect, fixed** | Points rebuilt from play types |
| E | Teams under 5 games leaked through traces and predictions | **Confirmed defect, fixed** | Masked; internal inputs labeled |
| F | Penalties | Parsed and validated; no predictive value | Published as descriptive "Discipline"; not in the rating |
| G | Clock-burning (lead protection) | Real in pace and play-calling; no adjustment improves accuracy | Tagged and shown; opt-in weight, **off by default** |
| H | Garbage time | The test can't tell the rules apart | Connelly rule kept for traceability; Luck uses garbage-adjusted scores |

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
- A unit test checks both averages on real results.

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
  and Miami. There are 18 such inversions against unbeaten teams in 2026.
- **Correction from round 2.** Net Resume *total* has the same games-played bias; USC was 4th. The
  resume ranking is therefore **Net Resume per game**, and USC is 10th. Totals are still published.

### A5. What counts toward "5 played games"?

The literal reading is any completed D-I game: 107 of 138 teams after week 5. Counting FBS games only
would rate 17.

**Correction from round 2.** The reviewer found that teams under the minimum still had full ratings in
their trace files, on the web page and in 24 predictions. Now:
- an ineligible team's trace shows only its schedule;
- predictions involving it are dropped (58 → 34);
- inside an eligible team's trace, an ineligible opponent's rating is an unavoidable input, so it is
  marked "internal input, not a published rating".

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

The network beats win% alone. The optimum puts tertiary at 0. The chosen weights trail it by
+0.0019 ± 0.0016 and +0.0006 ± 0.0008, which keeps your +2 structure at no measurable cost.

### B3. Nominal weight isn't effective weight

Across 542 FBS game sides the layers have SDs of P 0.199, S 0.115 and T 0.069. Tertiary averages
about 25 teams, so it regresses hard toward .500. Effective influence (weight × SD) is P 0.119,
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
strength but #89 by efficiency SOS; Texas Tech is the reverse (#70 vs #22). The **ranking uses
AdjEM**, as KenPom does. The network is the resume, and the two correlate at 0.87.

### B7–B8

A win's value changes as the beaten team's later games come in, as with RPI or strength of record.
Conference games are zero-sum, so conference strength enters only through non-conference games.

---

## C. The efficiency model

### C1. Opponent adjustment works

Walk-forward results, using earlier weeks only. Baselines exist only for FBS-vs-FBS games, so all
methods are compared on the same games:

| MAE, points | 2025 wk 4–16 (617) | 2026 wk 3–5 (171) |
|---|---|---|
| **AdjEM model** | **12.53** | **12.69** |
| Average scoring margin + home field | 13.19 | 14.23 |
| Raw points per drive + home field | 14.19 | 17.76 |

Over every predictable game, MAE is 12.48 with 72.9% of winners picked in 2025 (639 games), and 12.80
with 81.0% in 2026 (205 games). Calibration (2025):

| Predicted (bin mean) | 0.55 | 0.65 | 0.75 | 0.85 | 0.95 |
|---|---|---|---|---|---|
| Won | 0.62 | 0.59 | 0.70 | 0.88 | 0.94 |

### C2. Against the betting market

On 2026 weeks 3–5 (205 games) the model's MAE is 12.80 against the market's 11.22, worse by
**1.59 ± 0.54** points. ESPN keeps lines for only 55 of the 2025 games; on those the two were tied.
The market uses preseason priors, injuries and recruiting; this model uses only this season's games.

### C3. Home field

Estimated jointly with the shrinkage prior, home field comes out at 4.73 points; without the prior it is
3.67. Strong teams host most games, so the shrinkage residual was being credited to home field. It is
now estimated without shrinkage and held fixed. The reviewer confirmed this introduces no bias.

### C4. How much regression to the mean?

On the current data, 2025 walk-forward MAE is 13.89 with no prior, 12.80 at 6 drives, **12.48 at 12**
and 12.41 at 24. An earlier sweep found 36 or more drives worse. 12 and 24 are within noise of each
other, and 12 (one phantom game) is easier to read.

### C5. Garbage time

See §H.

### C6. Noise at week 5

The median AdjEM standard error is **±6.8 points** (IQR 4.4–8.5). Treat ranks 5–25 as a band, not an order.

### C7. ESPN data defects

- Drive points come from rebuilt scoring plays (§E, M1).
- 4 games are dropped from efficiency in 2026; all four are FCS-only.
- 55 games are kept with a data note, such as a corrected running score or a relabeled drive. Each note is in the trace.
- The scoreboard API silently returns 25 games when asked for more than 500, so the fetcher fails loudly instead.

### C8. Other choices

- **FCS games are in the efficiency model, opponent-adjusted.** Your FCS rule applies in full to the
  network.
- **Overtime drives are dropped.** They start at the opponent's 25.
- **Late-half drives are dropped by situation, not by result.** Before round 2, a late drive that
  failed was dropped while one that scored was kept.
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
| All 661 published win values and loss costs, plus Net Resume | Largest gap 4e-16 |
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

Effect of all data fixes on prediction, paired on the same games: 2025 +0.019 ± 0.070, 2026
−0.174 ± 0.079, pooled −0.028 ± 0.057. They are correctness fixes, neutral for accuracy.

---

## F. Penalties

> Measurement note for §F–H: the research numbers here were measured on the data as it stood before
> the round-2 parser fixes (§E). Those fixes were prediction-neutral (pooled −0.028 ± 0.057), so the
> comparisons stand, but drive counts can differ slightly from the current files. Penalty-parser
> accuracy and the lead-protection sensitivity were re-measured on the current data.

**Parser.** `penalties.py` reads both ESPN text dialects plus fouls embedded in other plays. Against the box score:

| Season | Count exact (team-games) | Within 1 | Total fouls vs box |
|---|---|---|---|
| 2026 | 90.4% | 99.1% | −0.8% |
| 2025 | 75.2% | 95.4% | −3.0% |

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
- The conference average is shown beside each rate, since conference and crew explain about 27% of differences.

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

**What the system does:**
- Each lead-protection drive is **tagged and shown** in the trace and on the page (§7.5). The rule can be checked by hand: Q4, ahead 1–21, ≥ 38 s/snap over ≥ 2 clean intervals, ≥ 60% runs.
- A leader's **final clock-killing drive** is no longer counted as a failed possession (§1.5). ESPN often leaves its result blank.
- **Neutral pace** (s/snap, Q1–Q3, score within 14) is published. It is a far steadier team trait than possessions per game (split-half 0.87 vs 0.39), but as a predictor it hurt margins (+0.10 ± 0.05), so it is display only.
- **Tempo (AdjT) is unchanged.** Q1–Q3-only possessions (+0.031 ± 0.024) and neutral-pace tempo (+0.015 ± 0.040) didn't help.
- The **opt-in weight** `situational.lead_protection.weight` stays at 1.0 (no adjustment). Set 0.5 if you want the rating to discount clock-burning on judgment; there is no accuracy claim either way.

**Caveat:** only about 60% of D-I games have a usable clock: P4 65%, G5 55%, FCS 11%. A team in
stale-clock games can't be tagged. This is disclosed on each team's page.

---

## H. Garbage time, revisited

| Rule | 2025 drives flagged | MAE vs current rule | Verdict |
|---|---|---|---|
| **Current (Connelly margins)** | 3,253 (9.8%); 3,473 on the current parse | — | **Kept** |
| No garbage filter | 0 | +0.012 ± 0.110 | Same |
| Time-aware sqrt rule (fit on 2025 wk 1–3) | 5,569 | +0.084 ± 0.082 | Same; flags 70% more |
| State-only win-probability model, leader WP ≥ 0.99 (fit on wk 1–3) | — | +0.071 ± 0.072 | Same; agrees with the current rule on 96% of drives |
| ESPN win probability ≥ 0.975 | 650 in Q1 alone | pooled +0.48 ± 0.17 | **Rejected** |
| Leader-only drop | — | −0.07 ± 0.07 | Rejected (unfair, below) |

- **ESPN's win probability contains the betting line.** It is never 0.5 at kickoff and correlates 0.84
  with the spread. Using it would put market information into the rating.
- **The test can't tell the rules apart.** The verifier showed that even a perfect rule could gain at most
  0.22 MAE, below the team-clustered standard error. So the current rule is kept because you can check it
  by hand (quarter, score before the drive, four numbers), not because the data proved it best. It
  behaves like a conservative "leader wins 99%+" rule: the leader went on to lose only 2 of 3,253 flagged drives.
- **Leader-only exclusion was rejected as unfair.** It charges a team's defense for garbage-time points while
  dropping its own garbage-time offense, which pulls dominant and fast teams down. Its small gain disappears on cleaner targets.
- **Garbage-adjusted results are new.** Garbage-time points were flowing straight into Pythagorean
  W% and Luck: 8.9% of FBS points in 2025 and 12.7% in 2026. Luck now uses each game's score with the
  offensive points from garbage-time drives removed. Each removal is listed per game, and the raw
  version is shown beside it. Example: Rutgers' luck goes from −0.258 (raw) to −0.116 (adjusted).
- **Fairness.** The current rule raises the fastest-pace quartile by +0.80 AdjEM in 2025 (+0.49 in 2026). Fast
  teams have more garbage-time drives. P4 and G5 teams are affected about equally.
