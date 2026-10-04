# How to trace any number

Every published number is a short, explicit computation over listed inputs. There
are three ways to follow one:

1. **The web page** (`out/index.html`). Click a team to see each game's adjustment, every
   win's +2 network tree, the five-factor counts, and every drive with its keep or exclude reason.
2. **The command line.** `python trace.py "Team"` prints the same derivation as text.
   Add `--section network` (or `efficiency`, `tempo`, `factors`, `luck`, `sos`)
   for one part, or `--drives` for every drive.
3. **The raw files.** `out/traces/<team_id>.json` holds every input and intermediate value.
   Game ids match ESPN event ids, so any drive can be checked against the original payload at
   `cache/<season>/summaries/<game_id>.json.gz` or on ESPN's site.

## Chain of custody

```
ESPN payload ── fetch.py ──> cache/2026/summaries/<game>.json.gz         (raw, untouched)
             ── parse.py ──> data/2026/games.json.gz                     (drives, points, flags)
                 drive points = rebuilt from each scoring play's type + extra point, reconciled
                 to the final score
                 kept = 0 with a reason: no scrimmage plays | overtime | end of half/game |
                        leader's final drive | garbage time
                 penalties = one row per foul (penalties.py), with how each value was read
             ── ratings.py ─> every metric in METRICS.md
             ── build.py ──> out/ratings.csv, out/ratings.json, out/traces/<id>.json
```

## Worked example 1: Notre Dame's AdjO

From `python trace.py "Notre Dame" --section efficiency`:

```
opponent               drives  raw PPD  opp_AdjD  opp adj  venue  adjusted
Wisconsin                   9    3.778     1.709   +0.668 -0.000     4.446
Rice                        6    5.833     3.053   -0.676 -0.159     4.998
Michigan State              8    3.375     2.161   +0.216 -0.159     3.432
Purdue                      5    5.600     2.792   -0.415 +0.159     5.343
North Carolina *            9    4.111     2.251   +0.126 +0.159     4.396
phantom game (FBS avg)     12                                        2.377
```

- **Raw PPD** is points on kept drives divided by kept drives. Against Wisconsin, 34 points on 9 drives = 3.778.
- **Opp adj** is −(opponent AdjD − μ), with μ = 2.377, the points per drive an average FBS offense scores
  against an average FBS defense. Wisconsin allows 1.709 per drive, 0.668 better than average, so Notre
  Dame is credited +0.668.
- **Venue** is −h × venue, with h = 0.1588: a home game gives it back, a road game adds it.
- **Adjusted** is raw plus both adjustments.
- **The asterisk:** North Carolina has played only 4 games, so its rating is not published. It
  appears here as an internal input so this line can still be checked.
- **AdjO** = (9×4.446 + 6×4.998 + 8×3.432 + 5×5.343 + 9×4.396 + 12×2.377) / (37 + 12) = **3.924**. The trace
  recomputes this sum and checks it against the stored rating; `build.py` fails if any team's doesn't match.

## Worked example 2: Notre Dame's AdjEM

`AdjEM = (AdjO − AdjD) × possessions per game = (3.9237 − 1.2749) × 11.549 = +30.59`.
That is points per game better than an average FBS team on a neutral field (the FBS average is exactly 0).
The ±8.3 standard error is the spread of the five game-level adjusted margins divided by √5.

## Worked example 3: the value of Notre Dame's win over Wisconsin

From `python trace.py "Notre Dame" --section network`:

```
anchors: NS_win 0.4682 (mean NS of all 271 beaten FBS teams -> average win = 1.00)
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
- **NS_win** = 0.4682 is the average network strength of every team beaten in an FBS game, so the
  average FBS win is worth exactly 1.00.
- **Value** = 0.7111 / 0.4682 = **1.519**: about 52% more valuable than a typical win.

## Worked example 4: a game result adjusted for garbage time

From `python trace.py Rutgers --section luck`. Rutgers scored 150 and allowed 161. After removing the
offensive points scored on garbage-time drives (each game's removals are listed in the schedule
section), that becomes 104 and 144. Pythag = 104^2.37 / (104^2.37 + 144^2.37) = 0.316. The actual W% is
0.200, so luck is −0.116; on raw scores it would be −0.258.

## Worked example 5: a lead-protection drive and a foul

`python trace.py Alabama --section situational` shows the one tagged drive, vs Florida State at
7:07 of Q4: up 7, 41.8 s/snap over 4 clean intervals, 8 of 9 runs. Every input to that rule is in
the drive's own snaps.

`--section discipline` lists every foul charged to Alabama, with:
- quarter, clock, foul and unit;
- yards and status;
- whether it counted (kept drive, garbage time, or situational);
- how the value was read, e.g. `narrative/explicit` or `statcrew/none`.

## What guarantees the traces are right

- **Self-checks.** Every AdjO, AdjD, AdjSR and AdjT trace recomputes its stored value, for all 266 D-I
  teams. `build.py` fails loudly if any differs by more than 1e-6.
- **Unit tests** (`tests/`, 26 tests):
  - A hand-computed network on a toy graph covers FCS wins and losses, path exclusions, and the
    average FBS win and loss being exactly 1.00.
  - Solver tests recover known ratings from synthetic games.
  - Parser tests cover rebuilt scoring, relabeled drives, the end-of-half and final-drive rules,
    kneels, nullified snaps, clock intervals and the box-score sanity check.
  - Penalty-parser tests cover both ESPN text dialects.
- **Independent recomputation.** A separate reviewer re-derived eligibility, drive points, win values
  and AdjO from the raw ESPN payloads without using this code. It found one data defect, now fixed;
  see `ADVERSARIAL_REVIEW.md` §E.
- **Penalty audit.** Parsed penalty counts are checked against every box score: 90% of 2026 team-games
  are exact, 99% within one.
