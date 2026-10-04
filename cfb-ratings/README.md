# FBS Efficiency Ratings

KenPom-style college football ratings for every FBS team, built on opponent-adjusted
points per drive. They come with a custom "+2 head-to-head" strength-of-schedule that
values every win by the beaten team's network of records. Every published number can be
traced back to individual games, drives, and plays.

Game results are cleaned before they are rated:
- **Garbage time** drives are left out (Bill Connelly's margin-by-quarter rule).
- **Clock-burning drives** are tagged and count as half a drive. This covers a team protecting a Q4
  lead by running the ball and snapping it well slower than its own normal pace.
- **Penalties** are parsed from the play-by-play into a "Discipline" profile. It is descriptive only,
  because penalties showed no predictive value beyond points per drive.

| Doc | What it holds |
|-----|---------------|
| [METRICS.md](METRICS.md) | The full metric list and every counting rule (written before the build) |
| [ADVERSARIAL_REVIEW.md](ADVERSARIAL_REVIEW.md) | Every design choice attacked, with backtests and evidence |
| [TRACE.md](TRACE.md) | How to trace any number, with worked examples |

## Run it

Python 3.10+ and the standard library. `requests` is needed only by `fetch.py`, to download.

```
python fetch.py --season 2026 --weeks 1-6     # ESPN scoreboards + play-by-play -> cache/
python parse.py --season 2026                 # -> data/2026/games.json.gz (drives, points, flags)
python build.py                               # -> out/2026/ (ratings.csv, ratings.json, traces/, anchors.json)
python build.py --season 2025                 # any other parsed season -> out/2025/
python report.py                              # -> out/site/ (one page, a season picker, data files per season)
python -m http.server -d out/site             # view it at http://localhost:8000
python trace.py "Notre Dame"                  # print any team's full derivation
python trace.py Indiana --season 2025         # ...for another season
python trace.py "Idaho State" --internal      # derivation of an FCS opponent's internal input
python audit_penalties.py                     # parsed penalties vs box scores -> out/penalty_audit.json
python -m unittest discover -s tests          # network, solver, parser and penalty tests
```

**Seasons.** Parsed data is committed for 2024, 2025 and 2026, and `config.json` `"season"` picks the
default season. To add a year, run `fetch.py --season YYYY --weeks 1-16`, `parse.py --season YYYY`
and `build.py --season YYYY`, then `report.py`; the page's season picker lists every season in `out/`.
The ratings cover the **regular season**, conference championship games and Army–Navy included.
Postseason games are left out: bowls and the CFP are never downloaded, and the FCS playoff rounds that
ESPN files among regular-season weeks are flagged by `parse.py` and set aside by `ratings.load()`.

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
| `parse.py` | Drives, drive points from ESPN's scoring plays, garbage/OT/end-of-half flags, scrimmage plays, snap-to-snap clock intervals |
| `penalties.py` | One row per foul from both ESPN text dialects, with how each value was read |
| `efficiency.py` | Additive opponent-adjustment solver (AdjO, AdjD, home field, tempo) with traces |
| `network.py` | +2 network: primary/secondary/tertiary records, win values, loss costs, trees |
| `ratings.py` | Assembles every metric in METRICS.md |
| `build.py` / `report.py` / `trace.py` | Per-season outputs in `out/<season>/` (including internal-input derivations and `anchors.json`), the multi-season page in `out/site/`, command-line trace |
| `backtest.py` / `validate.py` / `audit_penalties.py` | Evidence for the adversarial review |
