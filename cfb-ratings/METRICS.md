# CFB Efficiency Ratings: full metric list

This is the complete list of metrics the system computes, written before any
rating code. Each metric has its definition, its inputs, and the rule that
decides what counts. Every published number can be traced back to
individual games, drives, and plays. See `TRACE.md` for how.

Data source: ESPN's public college football API (scoreboards + per-game play-by-play).
Universe: all Division I games (FBS and FCS). Only FBS teams are published.

---

## 0. Eligibility and counting rules

| # | Rule | Definition |
|---|------|------------|
| 0.1 | **Published teams** | FBS teams only (138 in 2026, taken from ESPN's 11 FBS conference rosters). |
| 0.2 | **Eligibility** | A team gets a rating only after **5 completed games** (any D-I opponent, FBS or FCS). Teams with fewer games still count as opponents for everyone else, so their games are used. They just aren't ranked. The threshold is `min_games` in `config.json`. |
| 0.3 | **Efficiency model universe** | Every D-I vs D-I game. FCS teams get ratings from their own FCS schedules, so beating a strong FCS team and beating a weak one are adjusted differently. Games against D-II/NAIA opponents are dropped, as KenPom drops non-D-I games. |
| 0.4 | **Network SOS universe** | FBS vs FBS games only. A win over an FCS team is worth **0**, and its secondary and tertiary branches are never traversed (your rule). |

---

## 1. Drive and play cleaning (the efficiency model's inputs)

A "possession" is an offensive **drive**, the football version of KenPom's possession.

| # | Filter | Rule | Why |
|---|--------|------|-----|
| 1.1 | Drive points | Offense's score after the drive's last play minus its score before the drive's first play. Defensive and return touchdowns scored *against* the offense are not offensive points. | Isolates offensive scoring. |
| 1.2 | Zero-play drives | Dropped (kickoff/punt return "drives"). | Not possessions. |
| 1.3 | Overtime drives | Dropped (period ≥ 5). | OT drives start at the opponent's 25. Keeping them inflates points per drive. |
| 1.4 | End-of-half / end-of-game drives | Dropped. | Mostly kneel-downs and clock-killing. FEI drops these too. |
| 1.5 | Garbage time | A drive is dropped when the score margin at its start is greater than **43 in Q1, 37 in Q2, 27 in Q3, or 21 in Q4**. | Bill Connelly's garbage-time definition. Stops blowouts from inflating margins. |
| 1.6 | Scrimmage plays (for factors) | Rushes, passes, sacks, and scrimmage turnovers in non-garbage regulation drives. Excludes kneels, spikes, penalties with no play, and special teams. | Standard play filter. |

Every drive in the trace carries a `kept` flag and an `excluded_reason`.

---

## 2. Core efficiency ratings (KenPom analogs)

All "adjusted" values come from one additive, drive-weighted opponent-adjustment
model, solved by the same iterative averaging KenPom uses:

```
PPD(X on offense vs Y) = AdjO_X + AdjD_Y − μ + h·v_X + error
   μ   = D-I average points per drive (drive-weighted)
   v_X = +1 if X is home, −1 if away, 0 on a neutral site
   h   = home-field bonus per drive, estimated from the data
```

| # | Metric | Definition | Units |
|---|--------|------------|-------|
| 2.1 | **Raw PPD (O / D)** | Kept-drive points ÷ kept drives, for and against. | pts/drive |
| 2.2 | **AdjO** | Points per drive the offense would score against an average D-I defense on a neutral field. At convergence it equals the drive-weighted average of the game values `PPD_g − (AdjD_opp − μ) − h·v_g`, plus one phantom game (§2.8). | pts/drive (higher is better) |
| 2.3 | **AdjD** | Points per drive the defense would allow to an average D-I offense on a neutral field. Game value: `PPDallowed_g − (AdjO_opp − μ) − h·v_opp,g`. | pts/drive (lower is better) |
| 2.4 | **AdjEM (per drive)** | `AdjO − AdjD`. **This is the ranking metric**, as in KenPom. | pts/drive |
| 2.5 | **AdjEM (per game)** | `(AdjO − AdjD) × μT`, where μT is average possessions per team per game. Read it as "points better than an average D-I team on a neutral field." | pts/game |
| 2.6 | **AdjT (tempo)** | Opponent-adjusted possessions per game: `Poss_g = AdjT_X + AdjT_Y − μT`, solved the same way. Raw seconds per offensive play is shown next to it. | drives/game |
| 2.7 | **HFA** | `h` per drive, and `2·h·μT` in points per game, estimated jointly with the ratings. | pts |
| 2.8 | **Regression to the mean** | Each team's AdjO and AdjD include **one phantom game** of 12 drives at its division average (FBS or FCS). It shows up as its own line in the trace. | — |
| 2.9 | **Rating uncertainty (±)** | Standard error of AdjEM: the SD of the team's game-level adjusted margins ÷ √games. | pts/game |
| 2.10 | **Opponent-adjusted success rate (AdjSR O / D)** | Same model applied to per-game success rate (§3.1), play-weighted. A steadier second opinion than PPD. | % |

---

## 3. Five Factors (raw, KenPom "four factors" equivalent, offense and defense)

All five are computed on kept drives and scrimmage plays only.

| # | Factor | Definition |
|---|--------|------------|
| 3.1 | **Success rate** | Share of plays that gain ≥ 50% of the needed yards on 1st down, ≥ 70% on 2nd, and 100% on 3rd or 4th. A touchdown is a success; a turnover is not. |
| 3.2 | **Explosiveness** | Share of plays that are explosive (rush ≥ 12 yards, pass ≥ 16 yards). Yards per play is shown alongside. |
| 3.3 | **Field position** | Average drive start, in yards from your own goal line. Defense: the opponent's average start. |
| 3.4 | **Finishing drives** | Points per scoring opportunity. An opportunity is a drive with a first down at or inside the opponent's 40 (Connelly). |
| 3.5 | **Turnovers** | Giveaways (interceptions + fumbles lost) per game, takeaways per game, and margin per game, taken from the box score. |

---

## 4. Luck

| # | Metric | Definition |
|---|--------|------------|
| 4.1 | **Pythagorean W%** | `PF^2.37 / (PF^2.37 + PA^2.37)` over all D-I games. 2.37 is the standard college football exponent. |
| 4.2 | **Luck** | Actual W% minus Pythagorean W%. Positive means the team won more than its scoring margin suggests. |

---

## 5. Strength of schedule: efficiency version (the KenPom definition)

| # | Metric | Definition |
|---|--------|------------|
| 5.1 | **SOS (AdjEM)** | Average AdjEM per game of all D-I opponents played. |
| 5.2 | **Opp AdjO / Opp AdjD** | Average AdjO and AdjD of opponents. |
| 5.3 | **NCSOS** | 5.1 restricted to non-conference games. |

---

## 6. Strength of schedule: network win value (your +2 head-to-head design)

This scores **each win** by the strength of the beaten opponent's network,
measured three hops deep. When team A beats team B:

| Layer | Name | What it measures |
|-------|------|------------------|
| 1 | **Primary (P)** | B's own record |
| 2 | **Secondary (S)** | The records of every team B played |
| 3 | **Tertiary (T)** | The records of every team *those* opponents played |

### 6.1 Records (the "wins" the layers are built from)

- **FBS wins** count in the numerator and the denominator. **Wins over FCS teams are ignored completely** (your rule).
- **Losses** count in the denominator, **including losses to FCS teams**. Your rule removes FCS *wins* only, and a loss to an FCS team is real evidence a team is weak.
- Records are stated as a **rate**, not a raw count: `wp = (W + 1) / (G + 2)`. Raw counts would reward teams that have simply played more games (byes and 5-vs-6-game schedules are common in October). The +1/+2 is a one-win, one-loss prior. It keeps a 1-0 or 0-1 record from reading as 1.000 or .000.

### 6.2 Exclusion rules (so team A cannot inflate or deflate its own win)

1. **Team A is removed from the graph.** Every record used to value A's win leaves out games against A. Your win's value is computed in a world where you don't exist. Without this, beating B lowers B's record and therefore lowers the value of beating B.
2. **Path exclusion.** A node's record leaves out games against every team on its path back to the root. C's record drops games vs A and B. D's record drops games vs A, B, and C, and D is never B. This is stricter than the RPI convention (drop the parent only), and B's own results never leak into B's secondary or tertiary layers.
3. FCS teams are never nodes. Their branches are cut at the edge.

### 6.3 Layer formulas

```
P(B;A) = wp(B)                       record without games vs A
S(B;A) = mean over C in Opp(B)\{A} of  wp(C)   without games vs {A, B}
T(B;A) = mean over C in Opp(B)\{A} of
           [ mean over D in Opp(C)\{A,B} of wp(D) without games vs {A, B, C} ]
NS(B;A) = wP·P + wS·S + wT·T          (network strength, 0–1 scale)
```

The weights are **wP = 0.60, wS = 0.30, wT = 0.10**, set by a backtest on the
2025 season. Each week, network strengths built from earlier games were scored
on how well they separated later winners from losers (log loss), with
`wP ≥ wS ≥ wT` enforced. The data's optimum puts tertiary at 0. 0.60/0.30/0.10 is
statistically indistinguishable from that optimum and keeps the +2 layer you asked for.
The provisional 0.50/0.30/0.20 was slightly worse. Full table and paired
standard errors: `ADVERSARIAL_REVIEW.md` §B and `out/backtest_network.json`.

The path exclusion rule below was also tested against the RPI parent-only rule
and against no exclusions. All three predict equally well (differences within
noise), so the strictest fairness rule is used.

### 6.4 Win value

```
WinValue(A beats B) = NS(B;A) / NS_ref
NS_ref = average NS of the opponent across every FBS-vs-FBS game played this season
```

- **1.00 is a perfectly expected win**: B's network is exactly that of an average FBS opponent. B didn't over- or under-perform relative to its schedule's schedule.
- 1.30 means the win was 30% more valuable than an average win. 0.75 means 25% less.
- A win over an FCS team is **0.00** (FCS network strength is treated as 0).

### 6.5 Losses (you were undecided, so both versions are computed)

```
LossCost(A loses to B) = (1 − NS(B;A)) / (1 − NS_ref)
```

This mirrors the win value around 1.00. Losing to an average team costs 1.00, losing to a
strong team costs less, and losing to a weak team costs more. A loss to an FCS team
costs the maximum, `1 / (1 − NS_ref)` (about 2.0).

### 6.6 Team-level network outputs

| # | Metric | Definition |
|---|--------|------------|
| 6.6a | **Win Value Total (WVT)** | Σ WinValue over all wins. This is the win-only SOS from your brief. |
| 6.6b | **Avg Win Value** | WVT ÷ wins |
| 6.6c | **Loss Cost Total** | Σ LossCost over all losses |
| 6.6d | **Net Resume** | WVT − Loss Cost Total, in "net wins over average opponents." Recommended in the adversarial review. |
| 6.6e | **Schedule Network Strength** | Average NS(opp; team) over every FBS opponent, wins and losses. Pure schedule difficulty, independent of results. |
| 6.6f | **Best win / worst loss** | Highest WinValue and highest LossCost, each with its trace. |

---

## 7. Validation metrics (published, so you can judge the system)

| # | Metric | Definition |
|---|--------|------------|
| 7.1 | **Week-5 holdout** | Fit on weeks 1–4, predict week 5 margins and winners. MAE and straight-up accuracy for AdjEM, raw scoring margin, and network NS. |
| 7.2 | **Network weight backtest** | 2025 season, rolling weekly: log loss and accuracy for each candidate (wP, wS, wT). |
| 7.3 | **Prediction σ** | SD of out-of-sample margin errors. Used to turn predicted margins into win probabilities. |

## 8. Derived output

| # | Output | Definition |
|---|--------|------------|
| 8.1 | **Game predictions** (next week) | `Margin = (AdjEM_A − AdjEM_B)·Poss + 2h·Poss·(home)`, where `Poss = AdjT_A + AdjT_B − μT`. `P(win) = Φ(margin / σ)`. |
| 8.2 | **Conference ratings** | Average AdjEM of each conference's FBS members. |

---

## 9. Parameters (all in `config.json`)

| Parameter | Default | Meaning |
|-----------|---------|---------|
| `min_games` | 5 | Completed D-I games required for a published rating |
| `garbage_margin` | Q1 43 / Q2 37 / Q3 27 / Q4 21 | Margins above these drop a drive |
| `prior_drives` | 12 | Phantom drives at the division mean (§2.8) |
| `pythag_exp` | 2.37 | Luck exponent |
| `net_weights` | 0.60 / 0.30 / 0.10 | P / S / T weights (set by backtest) |
| `exclusion` | path | Record exclusions: `path`, `parent` (RPI), or `none` |
| `record_prior` | 1 W, 1 L | Laplace prior on records |
| `fcs_losses_count` | true | FCS losses count as losses in records |
| `explosive` | rush 12 / pass 16 | Explosive play thresholds |
