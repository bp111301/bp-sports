# CBB V2 challenger development — October 16, 2026

This is an isolated development experiment, not a production model or a replacement
for CBB V1. The protocol was committed before evaluation in `EXPERIMENT_LOCK.json`.
See `REPORT.md` and `results/comparison.json` for the comparison and decision.

The subsequent paired shadow-testing setup is documented in `SHADOW.md`, with
its separate `SHADOW_LOCK.json`, frozen `results/shadow_bundle.json` and
`data/cbb/shadow` ledger. Read that document for current prospective operations;
the development comparison below is preserved as a separate historical experiment.

## Scope

Only ending-year seasons 2020–2025 are loaded. Evaluate 2023, 2024 and 2025
chronologically: fit through Y−2, calibrate on Y−1, evaluate Y. Those development
seasons have been examined before, so this is exploratory evidence, not a fresh
untouched holdout. The previously inspected 2026 holdout is explicitly excluded.
The historical 71.75% result is not revised or reused to choose a challenger.

All variants use the original regular-season eligibility filter and exact V1
training/calibration recipe. The V1 replay is asserted equal to the original
`develop()` predictions in each fold. No hyperparameter search is performed.

## Added features

**Opponent adjustment:** online offensive and defensive efficiency residuals.
For an observed game, adjusted offense = own offense − opponent's pregame
defensive estimate + 103; adjusted defense = own defense − opponent's pregame
offensive estimate + 103. Estimates shrink toward the previous season using eight
prior games. Before any day's results are applied, that day's opponent estimates
are fixed. This is a scoped online adjustment, not a claim to reproduce another
published rating system. Existing V1 features remain present.

**Observed continuity:** use only earlier eligible games' player-minute records.
Compute the current observed rotation's returning-player minute share, incoming
transfer minute share, weighted log prior-season playing minutes and whether a
rotation is known. Returning means the athlete played for the same team in the
previous season; transfer means a different previous-season team. A player is
recognized only after an earlier appearance clears the embargo. Unknown rotations
use explicit fallback values and a missing-rotation indicator. These are not
preseason roster declarations, current injury reports or forecasts of starters.

No current-game player appearances or future roster memberships enter features.
Only games from UTC dates strictly earlier than forecast date minus one day update
either feature family. The first eligible game cannot benefit from a later roster.
Player records must match accepted game/team/opponent/score identities. Incomplete
minute totals are excluded from continuity, not treated as zero returning talent.
Player coverage and source hashes are recorded by season.

## Decision rule

A challenger can be shortlisted for further development if pooled Brier and log
loss improve, Brier improves in at least two of three folds, and pooled accuracy
is no more than 0.2 percentage points below V1. This does not authorize promotion,
live publication, retraining or changes to saved forecasts.

Limitations include incomplete observed-rotation coverage; no reliable historical
pregame roster/injury source; inherited historical Division I membership and
overtime-pace limitations; and previously inspected development seasons.

## Reproduction

From the repository root, with Python 3.12:

```sh
python -m pip install -r research/cbb/challenger/requirements.txt
python -m pytest research/cbb/test_develop.py research/cbb/test_holdout.py research/cbb/test_prospective.py research/cbb/challenger/test_challenger.py -q
python research/cbb/challenger/run.py --cache runtime/cbb
```

The script downloads missing 2020–2025 SportsDataverse schedule, team-box and
player-box Parquet files. Compare their recorded SHA-256 hashes: publisher
corrections may change a later replay. Outputs are written only below
`research/cbb/challenger/results/`. No preseason or live forecasts are generated.
Per-game predictions are archived with the result, together with their checksum.
All V1 coefficients, historical evaluations, live ledgers, grading and UI remain
unchanged.
