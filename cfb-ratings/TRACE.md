# How to trace any number

Every published number is a short, explicit computation over listed inputs. There
are three ways to follow one:

1. **The web page** (`out/site/index.html`; pick the season at the top). Click a team to see each game's adjustment, every
   win's +2 network tree, the five-factor counts, and every drive with its keep or exclude reason. The page loads each
   season's data files from beside it, so serve the folder rather than opening the file:
   `python -m http.server -d out/site`, then http://localhost:8000. The published page needs nothing.
2. **The command line.** `python trace.py "Team"` prints the same derivation as text.
   Add `--section network` (or `efficiency`, `success_rate`, `tempo`, `factors`, `luck`, `sos`,
   `situational`, `discipline`) for one part, or `--drives` for every drive.
   `python trace.py "Team" --internal` prints the derivation of an FCS opponent's internal rating
   wherever it feeds an FBS team's numbers. A tentative FBS team (under 5 games) has a full trace:
   run it without --internal.
3. **The raw files.** `out/<season>/traces/<team_id>.json` holds every input and intermediate value.
   Game ids match ESPN event ids, so any drive can be checked against the original payload at
   `cache/<season>/summaries/<game_id>.json.gz` or on ESPN's site.
   `out/<season>/traces/internal/<team_id>.json` holds the internal derivations, and `out/<season>/anchors.json`
   holds every input to the global constants (μ, the phantom game, μT, NS_win, NS_loss).

## Chain of custody

```
ESPN payload ── fetch.py ──> cache/2026/summaries/<game>.json.gz         (raw, untouched)
             ── parse.py ──> data/2026/games.json.gz                     (drives, points, flags)
                 drive points = rebuilt from each scoring play's type + extra point, reconciled
                 to the final score
                 kept = 0 with a reason: no scrimmage plays | overtime | garbage time |
                        end of half/game (in that order)
                 clean_intervals = snap-to-snap seconds from the "(MM:SS)" stamps;
                 lead-protection drives are tagged and weighted (config)
                 penalties = one row per foul (penalties.py), with how each value was read
             ── ratings.py ─> every metric in METRICS.md
             ── build.py ──> out/<season>/ratings.csv, ratings.json, traces/<id>.json,
                             traces/internal/<id>.json, anchors.json
             ── report.py ─> out/site/index.html + out/site/<season>/ (table, trace files)
```

## Worked example 1: Notre Dame's AdjO

From `python trace.py "Notre Dame" --section efficiency`:

```
opponent               weight  raw PPD  opp_AdjD  opp adj  venue  adjusted
Wisconsin                   9    3.778     1.691   +0.652 -0.000     4.430
Rice                        6    5.833     2.981   -0.637 -0.154     5.042
Michigan State            8.5    3.176     2.064   +0.279 -0.154     3.301
Purdue                      5    5.600     2.749   -0.406 +0.154     5.349
North Carolina *            9    4.111     2.238   +0.106 +0.154     4.371
phantom game (FBS avg)     12                                        2.344
```

- **Weight** is kept drives, with lead-protection drives counted at the configured weight (0.5).
  Against Michigan State, Notre Dame had 9 kept drives. One was a Q4 clock-killing drive: up 17, eight
  straight runs, snaps 50, 46, 46 and 47 s apart. It counts as half a drive, so the weight is 8.5.
- **Raw PPD** is points on kept drives divided by the weight. Against Wisconsin, 34 points on 9 drives = 3.778;
  against Michigan State, 27 points on 8.5 = 3.176.
- **Opp adj** is −(opponent AdjD − μ), with μ = 2.344, the points per drive an average FBS offense scores
  against an average FBS defense. Wisconsin allows 1.691 per drive, 0.652 better than average, so Notre
  Dame is credited +0.652.
- **Venue** is −h × venue, with h = 0.1544: a home game gives it back, a road game adds it.
- **Adjusted** is raw plus both adjustments.
- **The asterisk:** North Carolina has played only 4 games, so its rating is tentative (no official
  rank). Its own trace (`python trace.py "North Carolina"`, or its row on the page, marked T) shows
  how its 2.238 was derived, so this line can still be checked to the end.
- **AdjO** = (9×4.430 + 6×5.042 + 8.5×3.301 + 5×5.349 + 9×4.371 + 12×2.344) / (37.5 + 12) = **3.8867**. The trace
  recomputes this sum and checks it against the stored rating; `build.py` fails if any team's doesn't match.

## Worked example 2: Notre Dame's AdjEM (2026, through week 5)

`AdjEM = (AdjO − AdjD) × possessions per game = (3.8867 − 1.2603) × 11.558 = +30.36`.
That is points per game better than an average FBS team on a neutral field. The average over all 138 FBS
teams is exactly 0; the 107 ranked teams average −0.18.
The ±8.7 standard error is the spread of the five game-level adjusted margins divided by √5.

## Worked example 3: the value of Notre Dame's win over Wisconsin

From `python trace.py "Notre Dame" --section network`:

```
anchors: NS_win 0.4682 (mean NS of the beaten team over all 271 FBS wins -> average win = 1.00)
WIN vs Wisconsin:  NS = 0.6*0.8000 + 0.3*0.5889 + 0.1*0.5444 = 0.7111;  value = 0.7111 / 0.4682 = 1.519
  PRIMARY   Wisconsin: 3-0 -> 0.8000  (W Eastern Michigan, W Penn State, W Michigan State;
                                       excluded: Notre Dame, Western Illinois)
  SECONDARY Eastern Michigan 2-2 -> 0.5000   tertiary: Sacramento State 0-3, San José State 1-2, ...
  SECONDARY Penn State       3-1 -> 0.6667   tertiary: Marshall 2-1, Temple 1-2, ...
  SECONDARY Michigan State   2-1 -> 0.6000   tertiary: Toledo 3-0, Eastern Michigan 2-1, Nebraska 3-0
```

- **Primary.** Wisconsin without the Notre Dame game is 3-0; its win over FCS Western Illinois is
  ignored. That gives (3+1)/(3+0+2) = 0.800.
- **Secondary.** Wisconsin's other FBS opponents, each with games vs Notre Dame and Wisconsin removed.
  The mean of 0.500, 0.667 and 0.600 is 0.589.
- **Tertiary.** For each of those teams, the mean record of *its* opponents, with games vs Notre Dame,
  Wisconsin and that team removed. The mean of the three branch means is 0.544.
- **NS_win** = 0.4682 is the average network strength of the beaten team over all 271 FBS wins, so the
  average FBS win is worth exactly 1.00. Every one of those 271 rows is in `out/2026/anchors.json`.
- **Value** = 0.7111 / 0.4682 = **1.519**: about 52% more valuable than a typical win.

## Worked example 4: a game result adjusted for garbage time

From `python trace.py Rutgers --section luck`. Rutgers scored 150 and allowed 161. After removing the
offensive points scored on garbage-time drives (each game's removals are listed in the schedule
section), that becomes 104 and 144. Pythag = 104^2.37 / (104^2.37 + 144^2.37) = 0.316. The actual W% is
0.200, so luck is −0.116; on raw scores it would be −0.258.

## Worked example 5: a lead-protection drive and a foul

`python trace.py Alabama --section situational` shows the two tagged drives out of six Q4 leading
drives in usable-clock games:

```
vs Kentucky drive 21 (7:04): Q4, up 21, 38.0 s/snap over 2 clean intervals (threshold 38.0), 4/5 runs; intervals [39, 37]
vs Florida State drive 21 (7:10): Q4, up 7, 41.8 s/snap over 4 clean intervals (threshold 38.0), 8/9 runs; intervals [37, 42, 41, 47]
```

The threshold is Alabama's own neutral pace (37.4 s/snap) + 6 s, capped at 38 s. Each interval is the
gap between two "(MM:SS)" snap stamps by the same offense, so it can be checked in ESPN's play text.
`--drives` lists every drive's intervals, run count and clock source, including the leading drives
that weren't tagged.

`--section discipline` lists every foul charged to Alabama, with:
- quarter, clock, foul and unit;
- yards and status;
- whether it counted (kept drive; not counted for garbage time, a special-teams unit, or a situational delay of game);
- how the value was read, e.g. `narrative/explicit` or `statcrew/none`.

## What guarantees the traces are right

- **Self-checks.** Every AdjO, AdjD, AdjSR and AdjT trace recomputes its stored value, for every D-I
  team in the season. In 2026 through week 5 that is 266 teams: the 107 ranked and 31 tentative FBS teams, plus
  the internal derivations of the 128 FCS teams (2025: 265, 2024: 263, 2023: 261, 2022: 261). `build.py` fails
  loudly if any differs by more than 1e-6.
- **Unit tests** (`tests/`, 37 tests, one of which checks every built season's tentative rules):
  - A hand-computed network on a toy graph covers FCS wins and losses, path exclusions, and the
    average FBS win and loss being exactly 1.00.
  - Solver tests recover known ratings from synthetic games.
  - Parser tests cover rebuilt scoring, relabeled drives, the end-of-half rule on snap stamps, garbage
    time before end of half, kneels, nullified snaps, extra-point text, strip-sacks and lost fumbles,
    who scored, clock intervals, the two-minute warning and the box-score sanity check. Several are
    built from plays the final reviewer cited.
  - Penalty-parser tests cover both ESPN text dialects.
- **Independent recomputation.** A separate reviewer re-derived eligibility, drive points, win values
  and AdjO from the raw ESPN payloads without using this code. It found three major and six minor
  defects, all fixed; see `ADVERSARIAL_REVIEW.md` §E. A final four-reviewer audit found 40 more, all
  fixed (§I).
- **Penalty audit.** `python audit_penalties.py` checks parsed penalty counts against every box score
  and writes each team-game to `out/penalty_audit.json`: 90.3% of 2026 team-games are exact and 98.9%
  are within one.
