# UFC Fight Analyzer

A live fight-card analyzer for finding value on Caesars Sportsbook. Pick any UFC event (live,
upcoming, or past) and every fight on the card shows fighter v fighter: Caesars' moneyline next to
the market's fair price, each fighter's stats, and each fighter's last five fights underneath.

## Run it

**Windows:** double-click `start-server.bat`. It opens http://localhost:8766 in your browser. Leave
the black window open while you use it.

**Mac / Linux:** `python3 serve.py --open`

You need Python 3.8 or newer (python.org) and nothing else: no packages to install.

**On your phone:** the server prints a second address like `http://192.168.1.20:8766`. Open that on
your phone while it's on the same Wi-Fi. If Windows asks whether to allow Python on private
networks, say yes.

## What's on screen

**Card (left):** every fight by segment (main card, prelims, early prelims), with live round and
clock, results as they come in, the Caesars moneyline for each fighter, and Caesars' expected value
against the market. Fights with a Caesars price above your value threshold get a green edge. The
coloured bar under each fight is the market's fair win probability. The dots next to each name are
the last five results (green win, red loss).

**Matchup (right), top to bottom:**

1. **Fighter v fighter header:** photo, record, current streak, weight class, rounds, title fight,
   and live status or result.
2. **Caesars moneyline vs. market:** for each fighter: Caesars' price and implied probability, the
   market's fair (no-vig) probability and price, EV at Caesars, the best price at any book, a Kelly
   stake for your bankroll when the bet is +EV, and the market's opening line. Under that: Caesars'
   hold, how Caesars' line has moved since the app first saw it, and every book's line.
3. **Your number:** drag to your own win probability, or type in the price Caesars is showing you
   right now (live betting). You get EV, break-even, your fair price, and a stake.
4. **Matchup notes:** what stands out: Caesars mispricing, a better price at another book, reach and
   height edges, age, layoffs, striking differential, takedown threat vs. takedown defense,
   submission threat, KO losses, finishing rates, streaks, experience gaps, stance matchup.
5. **Tale of the tape:** pro and UFC record, last-five record, streak, age, height, reach, stance,
   wins and losses by KO/sub/decision, finish rate, days since last fight, gym, style.
6. **Career stats** (UFCStats): sig. strikes landed and absorbed per minute, accuracy, defense,
   strike differential, takedowns per 15 minutes, takedown accuracy and defense, sub attempts. Under
   that: recent form over the last five UFC fights. The better number on each row is highlighted.
7. **Last 5 fights:** under each fighter: result, opponent, method, round and time, the closing
   line (favorite or underdog), sig. strikes / takedowns / knockdowns for vs. against, event and date.
   Regional fights are included, so debuting fighters still have a history.
8. **Caesars props:** every prop Caesars has posted for the fight (method, round, distance), sorted
   by EV against the rest of the market.

The gear icon sets your bankroll, Kelly fraction (quarter Kelly by default), the EV threshold for
flagging value, and American or decimal odds.

## How "value" is worked out

- Each book's two-way line is de-vigged to a fair probability. The **market fair price** is the
  median across every book except Caesars; books far off the pack (for example a prediction market
  that has already settled) are dropped.
- **EV at Caesars** = fair probability × Caesars decimal odds − 1. For example, +4% means $4 expected
  profit per $100 if the market is right.
- **Stake** = Kelly fraction × full Kelly × bankroll, shown only when EV is positive.
- One-sided props (Caesars prices "wins in round 1" but no book prices the other side) have no fair
  price, so they show how much more or less Caesars pays than the median other book.

The market is usually right. Caesars' moneylines rarely beat it, so a flagged edge is worth a closer
look, not an automatic bet. Lines here come through BestFightOdds and refresh about every minute,
so **check the price in the Caesars app before you bet.**

## Prediction model

Each fight also gets a **Model prediction** panel: the model's win chance for each fighter, how the
fight ends (KO/TKO, submission, unanimous or split decision, draw), the chance it finishes in each
round, what's driving the pick, and a **BET / WATCH / PASS** call on the Caesars moneyline. The card
list shows the call next to each fight, and the props table gets **Model** and **Model EV** columns.

**How it works.** Every UFC fight since 1994 (UFCStats) is replayed in date order. Before each fight
the model only knows what was known that day: an Elo rating (finishes count more than decisions), a
rating for how dominant each fighter is in the cage, recent striking and grappling rates (weighted
toward recent fights and pulled toward the division average when there's little data), age, reach,
height, layoffs, weight-class moves, five-round experience, and the regional record before the UFC
(from ESPN's dated fight histories). A logistic regression turns the 39 differences between the two
fighters into a win chance. A second model splits each fighter's win into KO/TKO, submission and
decision, with round-by-round finish chances.

**Three probabilities, one decision.**

- *Model*: the fight model on its own. It's shown for reference but never used on its own to bet:
  on its own it is worse than the betting market.
- *Market*: the no-vig consensus of the other books (Caesars left out).
- *Bet probability*: the market, nudged toward the model only where that blend beat the market in
  testing. Two blends were fitted, one on opening lines and one on closing lines; a week or more out
  the opening-line blend applies, inside 12 hours the closing one, and in between a mix. Fighters
  with under 2 UFC fights get less of the model.

A **BET** needs all of: EV of 3% or more at Caesars using the bet probability; no negative EV at the
plain market price (the model can't create a bet the market prices as a loser); a side above 20%;
a fair price from 3+ books; and Caesars within 8 points of the market. A bet that only exists
because of the model also needs the blend to be live, both fighters to have 2+ UFC fights, the model
and market within 15 points of each other (bigger gaps are usually news the model can't see), and
both fighters' latest fights in the model's history. Stakes are quarter Kelly, capped at 1.5% of
your bankroll. **WATCH** means positive EV that doesn't clear the bar.

The settings menu has a **Value basis** option (market, model, or blend) that changes which
probability drives the card list's EV column and the "Your number" calculator.

**Track record (from `model/model.json`; open "Track record" in the panel for the live numbers).**
Settings were tuned on 2010–2015, the go/no-go decision for each blend was made on 2016–2020, and
the headline numbers are 2021–2026: 2,954 fights the model never saw, each predicted with
coefficients fitted only on earlier years.

| 2021–2026, fights with odds (2,915) | Picks the winner | Log loss (lower is better) |
| --- | --- | --- |
| Model alone | 63.5% | 0.640 |
| Opening line | 65.8% | 0.619 |
| Closing line | 68.4% | 0.595 |
| Opening line + model blend | 66.9% | 0.612 |
| Closing line + model blend | 68.7% | 0.593 |

- Against **opening lines** the blend clearly beats the market (log loss −0.0073, 95% range −0.011
  to −0.004). Betting it at opening prices with EV ≥ 3%: 1,031 bets, ROI +14.6% (95% range +9% to
  +20%), positive every year, and the closing line moved toward the pick on 62% of bets.
- Against **closing lines** the gain is small (−0.0022, range −0.004 to −0.000) and mostly comes from
  firming up the market's favorite, not from the model. At closing prices with a Caesars-sized 4.4%
  margin: 421 bets, ROI +1.4% (range −5% to +8%): not distinguishable from zero.
- **The model alone loses**: at closing prices with Caesars' margin it returned −12.7%. Don't bet
  the raw model number.

Read the opening-line result as an upper bound: historical opening lines are often one small book's
first number days before Caesars posts, and you can't usually bet big at them. Realistically, the
edge is in getting down early when Caesars hangs a line close to the opener; by fight night the
market has absorbed most of what the model knows. Props get a Model price from the method and round
model, which beat base rates on unseen fights (log loss 0.97 vs 1.03) but has never been tested
against prop prices, so Model EV on props is a lean, not a signal.

**Ledger.** The ledger button (top right) tracks every BET/WATCH the app flags (logged the first time
it's flagged) and every bet you log with "I bet this". Each is graded against the last consensus
price the app saw before the fight (closing-line value, CLV) and the result. Positive average CLV
over a few hundred bets is the quickest honest test of whether the edge is real; leave the server
running into fight night so it sees the close. The ledger lives in `cache/ledger.json`.

**Keeping it current.** While the server runs it pulls new UFC results from UFCStats every 6 hours
and folds them into every fighter's ratings and stats, so predictions stay current without
retraining. To refit the win model's coefficients on the latest results (pure Python, a minute or
two): `python -m model.retrain`. Rebuilding everything from scratch needs numpy and scikit-learn
(LightGBM optional, for a challenger comparison): `python -m model.scrape`, `python -m
model.odds_history`, `python -m model.espn_hist` refresh the data in `model/data/`, then `python -m
model.train` tunes, evaluates walk-forward, fits the blends, runs the backtests, and rewrites
`model/model.json`.

## Data sources and refresh

| What | Source | Refresh |
| --- | --- | --- |
| Schedule, cards, live round/clock, results, bios, full pro history | ESPN | card every 15s while live |
| Career stats (current career totals, even when viewing a past event), per-fight strikes/takedowns for both fighters | UFCStats | cached 6h |
| Caesars + FanDuel, DraftKings, BetMGM, BetRivers, BetWay, Unibet, Kalshi, Polymarket lines and props; opening and closing lines | BestFightOdds | every 60s |

Everything is pulled live, so any event on ESPN's calendar works (use the year picker for older
seasons). Fighter data is cached in `cache/`; delete that folder to force a full refresh.

## Files

- `serve.py`: local server and JSON API (`/api/events`, `/api/event/<id>`, `/api/odds/<id>`, `/api/fighter/<id>`)
- `espn.py`, `ufcstats.py`, `bfo.py`: data sources
- `fighters.py`: builds one fighter's profile and last five as of a given event
- `market.py`, `value.py`: odds matching, no-vig fair prices, EV, Kelly, line movement
- `names.py`: matches fighter names across sources (accents, name order, ring names)
- `modelapi.py`: model predictions for a card, the blend, and the BET/WATCH/PASS rule (`/api/predict/<id>`)
- `ledger.py`: forward CLV ledger (`/api/ledger`, `/api/ledger/add`, `/api/ledger/remove`)
- `model/`: the prediction model: `engine.py` (point-in-time replay, Elo, dominance, decayed stats),
  `features.py`, `dataset.py`, `learn.py` (pure-Python logistic regression and metrics), `predict.py`
  (serving and the outcome table), `train.py` (walk-forward training and backtests), `retrain.py`,
  data collectors `scrape.py`, `odds_history.py`, `espn_hist.py`, `market_hist.py`; trained model in
  `model.json`, historical data in `data/`
- `web/`: the app (plain HTML/CSS/JS)
- `tests/`: offline tests against trimmed copies of real pages: `python -m unittest discover -s tests`
  (and `node tests/props_map.test.js` for the prop label mapping)

21+. If gambling stops being fun, call 1-800-GAMBLER.
