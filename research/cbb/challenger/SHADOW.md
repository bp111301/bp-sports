# Paired CBB shadow testing

The combined challenger is isolated on `cbb-v2-challenger`. The public CBB V1
board, original pregame snapshots, V1 coefficients and historical evaluation stay
unchanged. There is no automatic model promotion.

## Frozen model and fair control

The shadow coefficient fit uses ending-year 2020–2024, with ending-year 2025 for
calibration. It does not fit, calibrate, score or select on ending-year 2026. The
portable coefficients are in `results/shadow_bundle.json`; fitting refuses to
overwrite that file. Its SHA-256 identifies every shadow forecast.

The control uses the exact frozen V1 coefficients on the same base features,
matchup, schedule source and capture timestamp as the challenger. It is a new
paired control, stored separately from the earlier public V1 snapshots. Original
public predictions are never replaced or represented as contemporaneous controls.

Ending-year 2026 can supply **past team state for forward forecasts**, like the
last season's team statistics. It is not reopened as an evaluation or tuning set.
Pregame state has a full intervening UTC-day embargo; forecast-only schedule rows
never update team strength or rotations.

## Capture and roster fallback

The first eligible prediction in the final **24 hours before verified tipoff** is
preserved for both models. The existing six-hour CBB workflow checks the window;
GitHub queues and source delays can postpone a check. A missed window is never
backfilled after tipoff. Each pair archives model identities, probabilities, all
feature values, source hashes, matchup IDs, tipoff and capture times.

Roster continuity comes only from earlier eligible player-minute records. Until
a current-season appearance clears the embargo, the rotation is explicitly
unknown and the locked fallback is used. No preseason roster declaration,
transfer confirmation, injury report or predicted starting lineup is inferred.

The 30-day readiness preview can check inference and schedule coverage before
the capture window opens. It is labeled `non_record_readiness_preview`, written
to `data/cbb/shadow/readiness_preview.json`, and never loaded by capture or grading.

## Paired grading

Only a source-confirmed regular-season final with matching home/away identities,
verified tipoff after both captures and valid final scores can settle a pair.
Both models receive the same outcome. Settled records are immutable. One-sided
settlements, mismatched contexts, duplicates and changed model identities fail
validation. Pending games never enter accuracy, Brier or log loss.

`data/cbb/shadow/summary.json` compares accuracy, Brier and log loss on **only the
same settled pairs**, with challenger-minus-control differences. Empty samples
report null metrics rather than implied success. Pick disagreements and unknown
roster contexts are counted separately. `dashboard.json` includes source coverage
and grading concerns; it does not feed the public board.

## Operations

The existing default-branch `.github/workflows/cbb_prospective.yml` retains the
public V1 refresh and then runs the independent shadow job. The shadow job checks
out this branch, tests the rules, loads frozen coefficients and writes only
`data/cbb/shadow`. It never invokes `freeze_shadow.py`. Caches are hash-validated
and disposable; historical input hashes and parser identities must match before
cached state can be reused. Current-season finals and player boxes refresh when
needed for a forecast.

From the repository root:

```sh
python -m pip install -r research/cbb/challenger/requirements.txt
python -m pytest research/cbb/test_develop.py research/cbb/test_holdout.py research/cbb/test_prospective.py research/cbb/challenger/test_challenger.py research/cbb/challenger/test_shadow.py -q
python research/cbb/challenger/shadow.py --preflight
python research/cbb/challenger/shadow.py
```

The preview command does not allow captures outside the locked window. Source
coverage is partial: unconfirmed tipoffs and unknown eligibility remain excluded,
and a source's unconfirmed date placeholder is not presented as a verified CT
game date. Inspect `coverage_by_day` and `excluded` before claiming opening-week
coverage is complete. No real preseason games are tested.

Review prospective evidence before any promotion decision. Development results
in `REPORT.md` are separate from this shadow record and from the original 71.75%
historical holdout result.
