# Adversarial review

Every design choice in this system was attacked here: your brief, my reading of it,
the math, and the data. Each finding gives the challenge, the evidence, and what
the system does as a result. Evidence comes from three sources:

- **2025 backtests**: a full season, walk-forward. Ratings are built only from games
  before each week and scored on that week. Files: `out/backtest_network.json`,
  `out/backtest_resume.json`, `out/validation.json`.
- **The 2026 data** through week 5.
- **An independent recomputation** (§E). A separate reviewer recomputed numbers from the raw ESPN
  payloads without using this code.

Paired differences are reported as `difference ± standard error`. A |z| under about 2 is
within noise.

---

## Summary

| # | Challenge | Verdict | Result |
|---|-----------|---------|--------|
| A1 | "1.00 = expected win" has two readings | Ambiguous brief | Opponent-quality reading. 1.00 equals the average FBS opponent, exactly, by construction |
| A2 | Raw win counts reward playing more games | Real fairness problem, no predictive gain | Records are rates: (W+1)/(G+2) |
| A3 | FCS losses: count them or not? | Brief only excludes FCS wins | FCS losses count (no measurable predictive cost) |
| A4 | Should losses count? | Prediction can't decide it; fairness can | Both published; **Net Resume recommended** |
| A5 | "5 played games": all games or FBS only? | Literal reading used | 107 of 138 rated now; FBS-only would rate 17 |
| B1 | Can a win lower its own value? | Yes, without exclusions | Winner removed from graph; path exclusion |
| B2 | Are the primary/secondary/tertiary weights justified? | Backtested | 0.60/0.30/0.10, within noise of the optimum |
| B3 | Does tertiary actually matter? | Barely | Effective influence is about 6% of primary |
| B4 | Why is the free-fit tertiary coefficient negative? | Two mechanisms tested and ruled out | Constrained to ≥ 0 |
| B5 | Small samples (3–6 games) | Real | Laplace prior, the only significant improvement (z ≈ 2–2.7) |
| B6 | Win/loss networks ignore margin and venue | Real | Ranking uses efficiency; both schedule measures shown |
| C1 | Does opponent adjustment help? | Yes | Walk-forward MAE 12.52 vs 14.05 raw (same games) |
| C2 | How does it compare with the betting market? | Market is better early in the season | 1.8 ± 0.5 pts worse in 2026 wk 3–5 |
| C3 | Home field estimate inflated by shrinkage | Confirmed (3.6 → 4.7 pts) | Two-stage estimate |
| C4 | Regression-to-mean strength | Tuned | 12 phantom drives (12 vs 24 within noise) |
| C5 | Garbage-time filter | No measurable effect | Kept for principle |
| C6 | Ratings are noisy at week 5 | Real | ±SE shown on every team (median ±6.7 pts) |
| C7 | ESPN data defects | Found and handled | 6 games dropped from efficiency, 2 kept with 1-pt PAT gaps |

---

## A. Reading your brief

### A1. What does "1.00 = a perfectly expected win" mean?

**Challenge.** The phrase supports two readings:
1. *Opponent quality.* A win over a typical opponent is 1.00. A harder win counts for more, an easier one for less.
2. *Performance against expectation.* 1.00 means you won exactly as much as predicted. A bigger
   margin over-performs and a smaller margin under-performs.

**Decision.** Reading 1, because your brief builds the value from the opponent's +2 network of
*wins*, which carries no margin information. Under that reading, B "didn't over-perform or
under-perform" when its network is exactly average. The scale is anchored so this holds
**exactly**. NS_ref is the mean opponent network strength across every FBS-vs-FBS game
played. Averaged over every one of those games, win values come to 1.000. A unit test
asserts this (`tests/test_network.py::test_average_opponent_win_is_one`).

Reading 2 is covered elsewhere and kept separate. The efficiency trace shows each game's
opponent-adjusted margin, and **Luck** compares actual wins with scoring-margin expectation.

### A2. "Wins" as counts or as rates?

**Challenge.** Read literally, the brief sums B's wins, B's opponents' wins, and their opponents' wins.
Raw counts grow with games played. Through week 5 of 2026, FBS teams have played between 3
and 6 FBS games. With raw counts, a 6-game opponent's network carries up to twice the
secondary and tertiary mass of a 3-game opponent, no matter how anyone played.

**Evidence (2025 backtest).** As predictors of later games, a freely weighted raw-count version
and the rate version are statistically tied. Counts minus rates: −0.0026 ± 0.0066 log loss
(≥3 prior games) and −0.0069 ± 0.0055 (≥5).

**Decision.** Rates. The predictive evidence is a wash, and rates remove the games-played
artifact. Each record is `(W+1)/(G+2)`, still "wins," counted per game.

### A3. FCS losses

**Challenge.** Your rule excludes *wins* over FCS teams and their branches. It says nothing about a
loss to an FCS team. If FCS losses were ignored too, a team's record would improve when it
loses to The Citadel instead of beating them.

**Evidence.** Ignoring FCS losses makes no measurable predictive difference (+0.0008 ± 0.0008).

**Decision.** An FCS loss counts as a loss in every record. Within the win-value system, an FCS
opponent has network strength 0. That one rule gives your exclusion (a win is worth 0) and
the maximum loss cost, 1/(1 − NS_ref) ≈ 2.01. In 2026 this hits Charlotte (The Citadel),
Bowling Green (Tarleton State), Utah State (Idaho State), and UL Monroe (SE Louisiana).

### A4. Should losses count? (You were undecided.)

**Evidence it can't be settled by prediction.** In 2025, win-only and net resume carry identical
predictive information: net minus win-only is +0.0002 ± 0.0047 (z = 0.04). When two teams
have played the same number of games, W and W−L carry the same information.

**Evidence it matters for fairness (2026).**
- Win-only can't tell 5-0 from 5-2. It also rewards playing more games: **5-1 USC (6 games)
  ranks above unbeaten Notre Dame and Miami** on win value total (5.37 vs 5.13 and 4.59).
- There are 13 pairs where win-only puts a team with losses above an unbeaten team and net resume
  disagrees.
- Win-only gives an FCS loss no penalty at all.

**Decision.** Both are published (Win Value Total and Net Resume). The resume ranking uses
**Net Resume**. Losses cost `(1 − NS)/(1 − NS_ref)`, the mirror image of win value. Losing
to an average team costs 1.00, and losing to a weak team costs more.

### A5. What counts toward "5 played games"?

**Challenge.** Should FCS games count? The efficiency model uses FCS games (opponent-adjusted),
but the network ignores FCS wins.

**Decision.** The literal reading: any completed D-I game. 107 of 138 FBS teams qualify after week 5. The
31 at four games (bye weeks, including Oregon, Texas, Oklahoma, and Ole Miss) get no published
numbers. They still count as **opponents**, because dropping them would corrupt everyone
else's adjustments. Counting only FBS games would rate just 17 teams today. Change `min_games`
in `config.json` to adjust the threshold.

---

## B. The +2 network

### B1. Self-influence

**Challenge.** When A beats B, B's record gets worse, so the value of beating B goes down.
A could also be one of B's opponents' opponents and feed its own record into the tertiary layer.

**Decision.** Two rules, both unit-tested:
1. **A is removed from the graph.** Every record used to value A's win ignores games against A.
2. **Path exclusion.** A node's record ignores games against every team above it in the
   tree. C ignores games vs {A, B}, D ignores games vs {A, B, C}, and D is never B. B's own
   results never leak into its secondary or tertiary layers.

The backtest compared path exclusion with the RPI convention (parent only) and with no deep
exclusions. All three predict equally well (+0.0002 ± 0.0003 and −0.0041 ± 0.0029). The
strictest fairness rule is kept at no measurable cost.

### B2. The weights

The 2025 backtest covered weeks 5–16 (567 FBS-vs-FBS games, both teams with ≥ 3 prior games). At each
week the network was built only from earlier games. A team's network strength had to predict
who won. The table shows log loss (lower is better); a home-field-only model scores 0.6832.

| P / S / T weights | Log loss (≥3 games) | Log loss (≥5 games) | Accuracy |
|---|---|---|---|
| 1.00 / 0 / 0 (win% alone) | 0.5804 | 0.5681 | 68.1% |
| 0.50 / 0.30 / 0.20 (provisional) | 0.5743 | 0.5657 | 69.3% |
| 0.571 / 0.286 / 0.143 (4:2:1 halving) | 0.5735 | 0.5647 | 69.0% |
| **0.60 / 0.30 / 0.10 (chosen)** | **0.5729** | **0.5643** | 69.3% |
| 0.667 / 0.333 / 0 (RPI-like) | 0.5718 | 0.5637 | 69.5% |
| best with wP ≥ wS ≥ wT | 0.5709 (0.60/0.40/0) | 0.5637 (0.65/0.35/0) | 69.0% |
| equal thirds | 0.5834 | 0.5743 | 67.5% |

- **The network beats win% alone.** Secondary adds real information.
- **The optimum puts tertiary at 0.** The chosen 0.60/0.30/0.10 trails it by +0.0019 ± 0.0016 and
  +0.0006 ± 0.0008, which is within noise. Your +2 structure is kept. Set tertiary to 0 in
  `config.json` for a strict data-driven version.

### B3. Nominal weight is not effective weight

Across the 542 FBS-vs-FBS game sides in 2026, the layers have very different spreads. P has an
SD of 0.199, S 0.115, and T 0.069, because tertiary averages ~25 teams and regresses toward .500.
Effective influence (weight × SD) is **P 0.119, S 0.035, T 0.007**. Tertiary moves a win value
about 6% as much as primary does. Under the provisional 0.50/0.30/0.20 it would still be only
0.014. Even a large tertiary weight would barely move the numbers.

### B4. The negative tertiary coefficient

With free weights, tertiary gets a **negative** coefficient in every variant (−1.89 in the
default). Two explanations were tested and ruled out:
- *Leakage of B's own wins into T.* Ruled out: path exclusion, which removes the leak, leaves the
  coefficient unchanged (−1.75 → −1.89).
- *Collinearity with S.* Ruled out: the S and T differences are uncorrelated (r = −0.03).

The cause is unexplained. The safe reading is that at 3–6 games per team, tertiary records carry no
usable signal, so the weight is held non-negative and small.

### B5. Small samples

Records of 3–6 games are coarse. A 2-0 team reads as 1.000 and a 0-2 team as .000. The
one-win, one-loss prior is the **only change that significantly improved prediction**
(+0.0049 ± 0.0024 and +0.0040 ± 0.0015 without it).

### B6. The network is blind to margin and venue

A 1-point home win and a 40-point road win look identical to the network. The two schedule
measures agree only loosely (Spearman 0.78). Examples:
- **Miami** is #13 by network schedule strength but #88 by efficiency SOS. Its opponents have good
  records but weak efficiency.
- **Texas Tech** is the reverse (#66 vs #20).

For this reason the **ranking uses AdjEM**, as KenPom does, and the network is the resume
measure. The two rankings correlate at 0.88.

### B7. Win values change after the game

A win's value is recomputed every week from current records. Beating a team that later goes
10-2 gains value. This is intended (RPI and strength of record work the same way), but a team's
resume can move in a week it doesn't play.

### B8. Conference insularity

Conference games are zero-sum. A conference's collective record differs from .500 only through
non-conference games, which are mostly played in weeks 1–4. Both schedule measures share this
limit. The efficiency model softens it, because margins carry more information than wins.

---

## C. The efficiency model

### C1. Opponent adjustment works

Walk-forward: each week was predicted only from earlier weeks. Baselines exist only for
FBS-vs-FBS games, so all three methods are compared on the same games.

| Predictor (mean absolute error, points) | 2025 wk 4–16 (617 games) | 2026 wk 3–5 (171 games) |
|---|---|---|
| **AdjEM model** | **12.52** | **12.89** |
| Average scoring margin + home field | 13.19 | 14.27 |
| Raw points-per-drive margin + home field | 14.05 | 18.16 |

Over every game it could predict (639 in 2025, including FBS-vs-FCS), the model had MAE
12.46 and picked the winner 72.6% of the time. Early-season raw numbers are badly distorted
by schedule, so opponent adjustment matters most in September.

Calibration is good. In 2025, games the model gave 80–90% won 89% of the time. Games given
90%+ won 93%. Games in the 70–80% band ran low (69%).

### C2. Against the betting market

- **2026 weeks 3–5 (n = 205):** model MAE 12.98, market 11.22. The model is worse by
  **1.76 ± 0.54 points**. That's significant.
- **2025:** ESPN still holds lines for only 55 of these games. On those, the model and market tie
  (11.22 vs 11.31, ±0.46).

The market uses preseason priors, recruiting, injuries, and quarterback news. This
model uses only this season's games. Adding a preseason prior is the clearest upgrade.

### C3. Home field was inflated by the shrinkage prior

With the regression-to-mean prior on, the estimated home edge rose from 3.6 points (no prior) to
4.7 (12 drives) and 5.1 (24 drives). Strong teams host most games, so the shrinkage
residual was being credited to home field. Fix: home field is estimated from the unshrunk fit
(**3.63 points**) and held fixed for the shrunk ratings. Both stages appear in the trace.

### C4. How much regression to the mean?

| Phantom drives | 0 | 6 | **12** | 24 | 36 | 48 | 72 |
|---|---|---|---|---|---|---|---|
| 2025 MAE (639 games) | 14.02 | 12.77 | **12.46** | 12.38 | 12.44 | 12.56 | 12.86 |
| 2026 wk 3–5 MAE (205 games) | — | — | **12.98** | 13.09 | 13.48 | 13.76 | 14.21 |

12 and 24 are within noise of each other. 12 (one phantom game) is kept for readability.

### C5. Garbage time

With the filter the model scores MAE 12.46; with garbage-time drives counted, 12.48. The filter
doesn't measurably help prediction. It's kept because it stops 50-point blowouts from
inflating a team's per-drive rating, and every dropped drive is listed with its reason.

### C6. Noise at week 5

The median AdjEM standard error is **±6.7 points** (IQR 4.4–8.4). Sixteen teams sit within 5
points of #10. Treat ranks 5–25 as a band, not an order. Every team shows its ±SE.

### C7. Data defects found in ESPN's feed

- Per-play running scores are unreliable: touchdown drives showed 0 or negative score changes.
  Drive points instead come from ESPN's `scoringPlays`, which reconcile to the final score in
  639 of 644 games.
- Six games are dropped from the efficiency model (all FCS-only; reasons are listed in
  `out/ratings.json`). They still count for records and eligibility.
- Two games are kept with a 1-point gap, a missed PAT in the feed: UTEP–New Mexico and Idaho State–Southern Utah.
- ESPN's scoreboard silently returns 25 games when asked for more than 500. The fetcher
  now fails loudly if a page looks truncated.

### C8. Other choices a skeptic should know about

- **FCS games are in the efficiency model.** FCS teams are rated from their own FCS
  schedules, so a 60-point win over a bad FCS team is adjusted down. Your FCS rule applies to
  the win-value network, where it is fully enforced.
- **Overtime drives are dropped.** They start at the 25 and would inflate points per drive. End-of-half
  drives and zero-play "drives" (return touchdowns) are dropped too.
- **AdjEM's zero is the average FBS team.** O and D are only identified up to a shared constant, so
  the FBS average is pinned to 0.
- **There's no recency weighting yet.** With 5 games there isn't enough data to estimate one.

---

## D. What would change these conclusions

- More seasons. Every backtest here is one season (2025). The weight optimum is flat, and a
  second season could move it.
- A preseason prior (last season's rating, returning production). It would close most of
  the gap to the market, at the cost of putting non-2026 information into a 2026 rating.

---

## E. Independent recomputation

<!-- filled from the independent reviewer's report -->
Pending.
