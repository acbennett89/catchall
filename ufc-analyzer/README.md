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
- `web/`: the app (plain HTML/CSS/JS)
- `tests/`: offline tests against trimmed copies of real pages: `python -m unittest discover -s tests`

21+. If gambling stops being fun, call 1-800-GAMBLER.
