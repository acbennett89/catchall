# Power ratings: a KenPom-style model for UFC fighters

Independent of `model/` (the market-blend model). Shares only the raw data: UFCStats fights and
fighters, round-by-round stats (`ratings/data/rounds.json.gz`), ESPN dated histories, BestFightOdds
lines for the benchmark.

## The analogy

KenPom rates a team by how efficiently it scores and prevents scoring **adjusted for who it played**,
plus tempo, strength of schedule and luck, then predicts games from the ratings. Here:

| KenPom | This model |
| --- | --- |
| Possession | A minute of shared cage time (both fighters always have the same minutes). Rates are per minute or per 15 minutes; power and chin use head strikes as the exposure |
| Points | **Cage points**: a weight per thing a fighter does, fitted once on 2008–2015 from what wins fights (`ratings/cagepoints.py`): a knockdown is worth 0.35, a submission attempt 0.38, a takedown 0.12, a minute of control 0.07, a significant strike 0.025 (+0.011 if to the head, +0.021 on the ground), in log-odds per 15 minutes |
| Offensive efficiency (AdjO) | Cage points per 15 minutes the fighter would produce against an average opponent of the division |
| Defensive efficiency (AdjD) | Cage points per 15 minutes an average opponent would produce against the fighter (lower is better) |
| Opponent adjustment | For each of 14 dimensions (sig. strikes, attempts, total strikes, head, distance, clinch and ground strikes, knockdowns, takedowns, takedown attempts, control, submission attempts, finishes, power) a fighter's offensive ratio O and defensive ratio D: expected count = exposure × division-era baseline × O × D(opponent). Observed / expected is shrunk toward 1.0 with K minutes of prior per dimension and iterated until every rating is consistent with everyone else's (`ratings/efficiency.py`) |
| League averages per season | Division-era baselines: decayed per-division rates, frozen into each fight at fight time, so a 2012 fight is judged against 2012 output (output has risen ~50% since 2009) |
| Tempo | Pace: both fighters' significant-strike attempts per minute |
| AdjEM | AdjO − AdjD. Rust-, momentum- and results-neutral; what division rankings sort by |
| Pythagorean win% | Pyth = sigmoid(AdjEM): the chance of beating an average fighter in the division (cage points are in log-odds units) |
| SOS | Decayed mean of opponents' AdjEM |
| Luck | Wins beyond what each fight's own stat line implied (the same fitted in-fight model) |
| Resume | A results-only Bradley-Terry strength, decayed and ridge-shrunk, shown beside AdjEM and used by the predictor |
| Log5 / game predictor | Ratings only: log5 of both fighters' Pyth. The full predictor: a logistic regression on antisymmetric matchup features, led by the expected output each way per dimension (A's offense × B's defense), plus physical, experience, durability, schedule and ring-rust terms |

Every number is point in time: computed from fights strictly before the fight date (same-day cards
never see each other), with exponential decay and shrinkage toward the division while the sample is
small. Two decay conventions are in use, both tuned on 2010–2015: the adjusted efficiencies,
Bradley-Terry and strength of schedule decay with e-folding time 1,500 days (a fight four years ago
counts 38%); the raw per-fighter rates and division priors use a 1,500-day half-life (four years ago
counts 51%). Ratings carry a data tier
(provisional < 15 effective minutes, developing 15–45, established 45+); only established fighters
or those with 3+ fights and 30+ minutes are ranked.

## Per-fighter stats, metrics and considerations

Rates are per minute (pm) or per 15 minutes (/15). "Adj" = opponent-adjusted. "R" = needs the
round-by-round data.

### Physical
| Metric | Definition |
| --- | --- |
| Age | On fight night, from UFCStats DOB (ESPN for debutants); win rate falls from 60% at 21–23 to 38% at 39+ |
| Age past 32 / youth under 25 | Hinge terms so the age curve can bend |
| Height, reach | Inches; reach-to-height ratio |
| Stance | Orthodox / southpaw / switch; southpaw vs orthodox measured 52.6% for the southpaw |
| Division on the night | Weight class of this bout; priors and ranks are per division |

### Style (archetype from the stat mix)
| Metric | Definition |
| --- | --- |
| Distance / clinch / ground share | Of significant strikes landed |
| Head / body / leg share | Target mix |
| Attempt rate | Significant strikes attempted pm |
| Grapple share | Takedown and submission attempts relative to strike attempts |
| Control share | Control minutes / fight minutes |
| Archetype scores | Wrestler, submission grappler, volume striker, power striker, kicker, clinch, counter striker (soft scores; primary and secondary shown) |

### Striking (raw and adjusted)
| Metric | Definition |
| --- | --- |
| SLpM, SApM, strike differential | Landed, absorbed, and the margin pm |
| Accuracy, defense | Landed / attempted; 1 − opponents' accuracy against the fighter |
| Head, body, leg landed /15; head strikes absorbed pm | Damage proxies |
| Knockdowns /15 for and against | |
| Distance net rate | Landed − absorbed at distance pm |
| **Adjusted ratios, offense and defense** | For sig. strikes, attempts, total strikes, head, distance, clinch and ground strikes, knockdowns: an index (100 = division-era average) and the rate against an average opponent |
| **Power / chin** | Knockdowns per 100 head strikes landed (offense) and per 100 absorbed (defense), opponent-adjusted |

### Grappling (raw and adjusted)
| Metric | Definition |
| --- | --- |
| Takedowns /15, attempts /15, accuracy | |
| Takedown defense, takedowns conceded /15 | |
| Control minutes /15 for and against, control margin | |
| Submission attempts /15 for and against, reversals /15 | |
| Ground strikes landed / absorbed pm | |
| **Adjusted ratios, offense and defense** | Takedowns, takedown attempts, control minutes, submission attempts, ground strikes: index and rate against an average opponent |
| **Finishes** | Finish wins per 15 minutes at risk (offense) and being finished (defense), opponent-adjusted |

### Damage and durability
| Metric | Definition |
| --- | --- |
| Chin | Share of losses by KO/TKO; KO losses in the last 3 years; career KO losses |
| Gets finished | Share of fights lost inside the distance |
| Knockdowns absorbed /15 (adj) | |
| Head strikes absorbed pm | |
| Submission losses share | |

### Pace and cardio (R)
| Metric | Definition |
| --- | --- |
| Pace | Both fighters' significant-strike attempts pm in the fighter's fights |
| Own attempt rate | |
| Fade | Rounds 2+ output pm vs round 1 (smoothed ratio); 1.0 = no fade |
| Drains opponents | The same ratio for opponents in this fighter's fights |
| Late-round margin | Strike differential pm from round 3 on |
| Championship-round minutes | Minutes logged past the 15-minute mark |
| Average fight length; share going the distance | |

### Finishing and judging
| Metric | Definition |
| --- | --- |
| Finish rate | KO share + submission share of wins; KO wins /15; submission wins /15 |
| Decision win rate | Of decisions fought |
| Split/majority share | Of decisions fought (judging exposure) |
| Luck | Actual minus expected win rate, where expected comes from each fight's own strike, control, knockdown and takedown margins |

### Experience and schedule
| Metric | Definition |
| --- | --- |
| UFC fights, rounds, minutes; pro fights; years in the UFC; debut flag | |
| Record outside the UFC | Wins, losses and finish share before this fight, from ESPN's dated history (faded out by 4 UFC fights) |
| Title fights, main events, five-round fights | |
| **AdjO, AdjD, AdjEM, Pyth** | The composites above |
| **Results strength** | Bradley-Terry on results only; performance-implied win share (mean of P(win | stat line) over the fighter's fights) |
| **Strength of schedule** | Decayed mean of opponents' AdjEM; SOS of the last 3 |
| Division rank, percentile, tier | By AdjEM among qualified active fighters (a UFC fight in the last 4 years); data tier and effective minutes |

### Ring rust
| Metric | Definition |
| --- | --- |
| Days since last fight; log layoff; bucket (<90, 90–180, 180–365, 365–730, >730) | Measured win rates 49 / 52 / 51 / 43 / 48% |
| Out over a year; out over two years | |
| Layoff vs the fighter's usual gap | |
| Fights in the last 12 and 24 months | Activity |
| Coming off a KO loss / submission loss / any loss | Next-fight win rates 45 / 46 / 50% |
| Age × long layoff | Older fighters off long layoffs |

### Momentum (last 5)
| Metric | Definition |
| --- | --- |
| Last-5 record; streak | |
| Recent finishes | In the last 3 |
| Striking trend | Strike differential in the last 3 vs career |
| Recent opposition | Mean rating of the last 3 opponents |

Momentum and ring rust are **tested, not assumed**: each group stays in the predictor only if
removing it makes the walk-forward log loss worse on 2010–2015 and on 2016–2020.

### Matchup and context
| Term | Definition |
| --- | --- |
| (see Matchup above) | Style-versus-style effects are native to the expected-output terms |

### Matchup
| Term | Definition |
| --- | --- |
| Expected output each way | For each dimension: baseline × O_A × D_B minus baseline × O_B × D_A (A's offense against B's defense, and the reverse): the native style interaction, in natural units |
| Offense-and-defense margin | The additive alternative, baseline × ((O_A − O_B) − (D_A − D_B)); the ablation keeps whichever form helps |
| Five rounds × cardio, five rounds × AdjEM | Championship-round context |

## Predictor

Logistic regression, no intercept, on antisymmetric differences (A − B), mirrored rows, ridge
regularization chosen on 2010–2015; a single calibration slope fitted per year on earlier years'
out-of-sample predictions. Walk-forward: year Y is predicted from fits on years before Y.

Windows match the other model so the two can be compared: TUNE 2010–2015, VAL 2016–2020, TEST
2021–now. The benchmark is the opening and closing line on the same fights.

## App

A **Power ratings** panel in the matchup view: win chance, power rating and division rank for both
fighters, style, the ratings page (adjusted and raw metrics side by side, better number highlighted),
what's driving the pick by area, flags (debut, rust, chin, age), the track record, and a division
rankings dialog. A chip in the fight list shows the ratings pick. It is a second opinion; the BET rule
stays with the market blend.

## Results (walk-forward, from `ratings/model.json` and `model/model.json`)

- Rating settings: τ = 1,500 days (chosen on 2010–2015 and confirmed on 2016–2020 over 365–1,500),
  15 pseudo-minutes of shrinkage for raw rates; per-dimension K from the reliability analysis.
- Groups kept by the ablation: additive offense-and-defense margins, results, schedule, ring rust.
  Dropped: momentum, multiplicative margins, cardio, pace, judging, record.
- 2021–2026 (2,957 fights): log loss 0.631, 63.7% right; AdjEM alone 0.657 / 60.4%; without the
  adjusted efficiencies 0.643. On the 2,872 fights with lines: 0.628 vs opening line 0.618
  (difference +0.010, 95% range −0.000 to +0.019) and closing line 0.595. The fight model in
  `model/` scores 0.638 on the same fights.
- Calibration: by decile, predicted and actual agree within 2 points from 0.2 to 0.8.
- In the market blend (`model/train.py`, two-model stacker, gated on 2016–2020): adding the ratings
  beat the single-model blend by −0.0045 (opening) and −0.0024 (closing) log loss; blend minus
  market −0.0113 and −0.0041 on 2021–2026. Served BET rule at historical opening prices: 1,003
  bets, ROI +16.3% [+10.7, +22.2], CLV +7.2%; fight-week blend bets at Caesars-like prices: 674
  bets, +9.8% [+4.0, +15.9] (2016–2020: +14.8%).

## Not built yet (from the design panel's longer list)

Debut prior by ridge regression on pre-UFC records; age-dependent decay and Glicko-style uncertainty
inflation; division-specific temperature; per-round judging model and round-level luck; archetype
pair matrix; market-informed debut variant; event location and short-notice data; a full dynamic-state
(Kalman) rating as an alternative to decay.
