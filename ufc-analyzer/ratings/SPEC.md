# Power ratings: a KenPom-style model for UFC fighters

Independent of `model/` (the market-blend model). Shares only the raw data: UFCStats fights and
fighters, round-by-round stats (`ratings/data/rounds.json.gz`), ESPN dated histories, BestFightOdds
lines for the benchmark.

## The analogy

KenPom rates a team by how efficiently it scores and prevents scoring **adjusted for who it played**,
plus tempo, strength of schedule and luck, then predicts games from the ratings. Here:

| KenPom | This model |
| --- | --- |
| Possession | A minute of cage time (rates are per minute or per 15 minutes) |
| Offensive efficiency | Significant strikes landed per minute, takedowns per 15, control minutes per 15, knockdowns per 15, submission attempts per 15, head strikes per minute, ground strikes per minute |
| Defensive efficiency | The same things allowed to opponents |
| Opponent adjustment | Each fight's rate is scaled by how much better or worse than average the opponent is at preventing it, iterated to consistency (`engine.adjust`) |
| Tempo | Pace: both fighters' significant-strike attempts per minute |
| AdjEM | Composite rating from the adjusted margins, and the model's **power rating** (log-odds of beating a division-average fighter) |
| SOS | Recency-weighted mean rating of opponents faced |
| Luck | Win rate beyond what the per-fight stat margins say |
| Log5 / Pythagorean | Logistic predictor on fighter differences |

Every number is point in time: computed from fights strictly before the fight date, with recency
weighting (half-life 18 months), exposure weighting (minutes) and shrinkage toward the division
average while the sample is small (30 minutes of pseudo-exposure).

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
| **Adj striking offense / defense** | SLpM against an average defense; SApM from an average offense |
| **Adj head strikes landed / absorbed** | |
| **Adj knockdown rate / knockdowns taken** | |

### Grappling (raw and adjusted)
| Metric | Definition |
| --- | --- |
| Takedowns /15, attempts /15, accuracy | |
| Takedown defense, takedowns conceded /15 | |
| Control minutes /15 for and against, control margin | |
| Submission attempts /15 for and against, reversals /15 | |
| Ground strikes landed / absorbed pm | |
| **Adj takedown offense / defense** | |
| **Adj control / control conceded** | |
| **Adj submission threat / exposure** | |
| **Adj ground striking for / against** | |

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
| **Strength of schedule** | Recency-weighted mean rating of opponents; SOS of the last 3 |
| Division rank and percentile | By power rating among active fighters (a UFC fight in the last 4 years) |

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
| Wrestling vs takedown defense | A's adjusted takedown offense × (1 − B's takedown defense), minus the reverse |
| Volume vs striking defense | |
| Power vs chin | Knockdown rate × opponent's KO-loss share |
| Submissions vs ground game | |
| Reach at distance | Reach edge weighted by how much both fight at distance |
| Five rounds × cardio, five rounds × rating | Championship-round context |

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
