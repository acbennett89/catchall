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
                 drive points = offense's score change from ESPN scoringPlays
                 kept = 0 with a reason: no scrimmage plays | overtime | end of half/game | garbage time
             ── ratings.py ─> every metric in METRICS.md
             ── build.py ──> out/ratings.csv, out/ratings.json, out/traces/<id>.json
```

## Worked example 1: Notre Dame's AdjO

From `python trace.py "Notre Dame" --section efficiency`:

```
opponent        drives  raw PPD  opp_AdjD  opp adj   venue  adjusted
Wisconsin            9    3.778     1.805   +0.518  -0.000     4.296
Rice                 6    5.833     3.028   -0.705  -0.157     4.971
Michigan State       8    3.375     2.131   +0.192  -0.157     3.410
Purdue               5    5.600     2.764   -0.441  +0.157     5.316
North Carolina       9    4.111     2.248   +0.075  +0.157     4.344
phantom game (FBS avg) 12                                     2.345
```

- **Raw PPD** is points on kept drives divided by kept drives. Against Wisconsin that's 34 points
  on 9 drives = 3.778.
- **Opp adj** is −(opponent AdjD − μ), with μ = 2.323. Wisconsin's defense allows 1.805 per drive,
  better than average by 0.518, so Notre Dame is credited +0.518.
- **Venue** is −h × venue, with h = 0.1574. A home game gives back 0.157; a road game adds it; a neutral site is 0.
- **Adjusted** is raw + opp adj + venue.
- **AdjO** = (9×4.296 + 6×4.971 + 8×3.410 + 5×5.316 + 9×4.344 + 12×2.345) / (37 + 12) = **3.869**.

The trace recomputes this sum and compares it to the stored rating. It matches for every team,
and `build.py` reports any failure. AdjD is the same calculation on points allowed.

## Worked example 2: Notre Dame's AdjEM

`AdjEM = (AdjO − AdjD) × possessions per game = (3.8692 − 1.2573) × 11.542 = +30.15`.
That's points per game better than an average FBS team on a neutral field. The ±8.3 standard
error is the spread of the five game-level adjusted margins divided by √5.

## Worked example 3: the value of Notre Dame's win over Wisconsin

From `python trace.py "Notre Dame" --section network`:

```
NS = 0.6*0.8000 + 0.3*0.5889 + 0.1*0.5444 = 0.7111;  value = 0.7111 / 0.5015 = 1.418
PRIMARY   Wisconsin: 3-0 -> 0.8000   (W Eastern Michigan, W Penn State, W Michigan State;
                                      excluded: Notre Dame, Western Illinois)
SECONDARY Eastern Michigan 2-2 -> 0.5000   tertiary: Sacramento State 0-3, San José State 1-2, ...
SECONDARY Penn State       3-1 -> 0.6667   tertiary: Marshall 2-1, Temple 1-2, ...
SECONDARY Michigan State   2-1 -> 0.6000   tertiary: Toledo 3-0, Eastern Michigan 2-1, Nebraska 3-0
```

- **Primary.** Wisconsin's record without the Notre Dame game is 3-0, and its win over FCS Western Illinois
  is ignored. That gives (3+1)/(3+0+2) = 0.800.
- **Secondary.** Each of Wisconsin's other FBS opponents, with games vs Notre Dame and Wisconsin removed.
  Mean of 0.500, 0.667, 0.600 = 0.589.
- **Tertiary.** For each secondary team, the mean record of *its* opponents, with games vs Notre Dame,
  Wisconsin, and that team removed. The mean of those three branch means is 0.544.
- **NS_ref** = 0.5015 is the average opponent network strength over every FBS-vs-FBS game this
  season. A win worth 1.00 is a win over a perfectly average opponent.
- **Value** = 0.7111 / 0.5015 = **1.418**. The win was 42% more valuable than an average win.

## What guarantees the traces are right

- **Self-checks.** Every AdjO, AdjD, and AdjT trace recomputes its stored value. `build.py` fails
  loudly if any differ by more than 1e-6.
- **Unit tests** (`tests/`). A hand-computed network on a toy graph covers FCS wins, FCS losses,
  exclusions, and the property that the average win is exactly 1.00. Solver tests recover known ratings from
  synthetic games.
- **Independent recomputation.** A separate reviewer re-derived eligibility, drive points, win values,
  and AdjO from the raw ESPN payloads without using this code. See `ADVERSARIAL_REVIEW.md` §E.
