# CBB V1 research

Men's college basketball pregame winner probabilities. This is an isolated
development project, not a released or frozen model and not a live board.

Run from the repository root in a separate Python environment:

```bash
python -m pip install -r research/cbb/requirements.txt
python -m pytest -q research/cbb/test_develop.py
python research/cbb/develop.py
```

The script downloads ending-year seasons 2020–2025 into `runtime/cbb`, audits
paired box scores against schedules, and writes development results and predictions.
Source URLs, content hashes, exclusions and eligible counts are recorded per season.
Ending-year 2026 (2025–26) is never downloaded by this development script.

Models: fixed Elo with home/neutral context; calibrated Elo logistic regression;
calibrated Elo plus prior-game efficiency, shooting, turnovers, rebounding,
free throws, pace, rest and experience. The two logistic models use seasons
2020–2023 for fitting, 2024 for probability calibration, and 2025 for development
evaluation. No result here is prospective evidence.

All games on a UTC date use only state through dates at least two calendar days
earlier. A full intervening UTC day is an embargo because final timestamps are
unavailable; this prevents midnight-overlapping games from leaking results. End-of-season
team ratings and current-game box scores never enter the pregame features.
Results update state only after the embargo. Same-day updates are batched.

Eligibility requires regular-season final status, both teams' conference IDs,
no explicit non-Division-I flag, known venue context, reciprocal paired boxes,
matching schedule scores, and complete core statistics. Independent/unknown
conference games are excluded pending a verified historical membership map.
Source conference IDs are an eligibility proxy, not a full historical NCAA audit.

Limitations: no dated injury/roster/transfer inputs yet; pace is an estimated
possession count and is not overtime-adjusted; conference tournaments may be
classified as regular season by the source. Archived historical files can be
corrected after publication, so retrospective accuracy is not a substitute
for collecting immutable live pregame snapshots.

Next: assess chronological development stability, audit membership and overtime
context, lock choices, evaluate 2026 once, then validate the prospective pipeline.
Existing B.P. Sports models, weights, ledgers and UI remain unchanged.

## Locked holdout evaluation

`EVALUATION_LOCK.json` was committed before opening the ending-year 2026
evaluation season. It fixes the candidate, fit/calibration seasons, features,
hyperparameters and historical pass/fail criteria. The runner refuses to
overwrite an existing holdout report:

```bash
python -m pytest -q research/cbb/test_develop.py research/cbb/test_holdout.py
python research/cbb/evaluate_holdout.py
```

Evaluation fits through ending-year 2024, calibrates on 2025, then evaluates
2026. It writes the report, a portable JSON candidate bundle, and per-game
historical predictions. Bundle inference is checked against the fitted model.
Passing this historical gate only permits prospective pipeline validation;
it does not automatically publish CBB forecasts or promote the model.
