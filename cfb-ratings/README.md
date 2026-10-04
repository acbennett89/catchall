# FBS Efficiency Ratings

KenPom-style college football ratings for every FBS team, built on opponent-adjusted
points per drive. They come with a custom "+2 head-to-head" strength-of-schedule that
values every win by the beaten team's network of records. Every published number can be
traced back to individual games, drives, and plays.

| Doc | What it holds |
|-----|---------------|
| [METRICS.md](METRICS.md) | The full metric list and every counting rule (written before the build) |
| [ADVERSARIAL_REVIEW.md](ADVERSARIAL_REVIEW.md) | Every design choice attacked, with backtests and evidence |
| [TRACE.md](TRACE.md) | How to trace any number, with worked examples |

## Run it

Python 3.10+, standard library plus `requests` (for downloading only).

```
python fetch.py --season 2026 --weeks 1-6     # ESPN scoreboards + play-by-play -> cache/
python parse.py --season 2026                 # -> data/2026/games.json.gz (drives, points, flags)
python build.py                               # -> out/ratings.csv, out/ratings.json, out/traces/*.json
python report.py                              # -> out/index.html (table + drill-down derivations)
python trace.py "Notre Dame"                  # print any team's full derivation
python -m unittest discover -s tests          # hand-checked network + solver tests
```

Validation (optional, slower):

```
python fetch.py --season 2025 --weeks 1-16 && python parse.py --season 2025
python backtest.py                            # network weights, exclusions, losses (2025)
python validate.py                            # walk-forward efficiency vs baselines and market
```

All parameters live in `config.json`.

## Files

| File | Role |
|------|------|
| `fetch.py` | Downloads ESPN payloads (cached, gzipped) |
| `parse.py` | Drives, drive points from ESPN's scoring plays, garbage/OT/end-of-half flags, scrimmage plays |
| `efficiency.py` | Additive opponent-adjustment solver (AdjO, AdjD, home field, tempo) with traces |
| `network.py` | +2 network: primary/secondary/tertiary records, win values, loss costs, trees |
| `ratings.py` | Assembles every metric in METRICS.md |
| `build.py` / `report.py` / `trace.py` | Outputs, web page, command-line trace |
| `backtest.py` / `validate.py` | Evidence for the adversarial review |
