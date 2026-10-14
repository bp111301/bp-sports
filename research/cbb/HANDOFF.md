# CBB V1 initial development — October 13, 2026

Status: research baseline implemented and tested. Not frozen, not released,
and no prospective CBB forecasts have been issued.

Audited 31,368 eligible regular-season games across ending-year 2020–2025.
Sources are SportsDataverse team box scores and schedules; exact source URLs,
SHA-256 hashes, exclusion counts and neutral-site counts are in
`results/development.json`. Unknown conference eligibility and unpaired boxes
are excluded. Historical Division I membership still needs a fuller audit.

## Chronological development accuracy

| Ending-year evaluation season | Elo | Elo + statistical features |
|---|---:|---:|
| 2023 (2022–23) | 70.45% | 70.72% |
| 2024 (2023–24) | 70.50% | 71.25% |
| 2025 (2024–25) | 71.34% | 71.82% |

Each fold fits through two seasons before evaluation and calibrates on the
intervening season. Development evaluations are used to compare candidates;
they are not untouched final tests or prospective records.

On the 5,636-game 2025 development slate, the statistical candidate got 4,048
winners correct. Brier score was 0.18318 versus 0.19355 for Elo; log loss was
0.54058 versus 0.57112. Designated-home picks were correct 64.28% of the time.
The candidate's neutral-site accuracy was 65.01% over 643 games, compared with
72.70% over 4,993 non-neutral games. Difficulty varies by venue context.

## Safety and limitations

Four tests pass: current/future outcomes do not enter earlier features;
same-day games do not leak; neutral venues remove home advantage; future
seasons cannot change earlier features; and a midnight-overlap scenario is
covered by the conservative full intervening UTC-day embargo.

No current-game box scores, full-season ratings, markets, injuries, transfers
or roster continuity are model inputs. Overtime-adjusted pace and historical
membership verification remain tasks before release. Cached source files can
be corrected by their publisher; hashes preserve this run's input identity.

Ending-year 2026 (2025–26) has not been evaluated. The development script does
not load it. Lock model and evaluation choices before opening that holdout,
then evaluate once without tuning on it. After that, validate schedule coverage,
immutable pregame captures and grading for the 2026–27 season.

Existing B.P. Sports frozen models, historical evaluations and prospective
ledgers have not been modified by this research work.

## Locked holdout result — October 13, 2026

The earlier development-stage note above describes the state before the final
evaluation. Ending-year 2026 has now been evaluated once using the previously
committed `EVALUATION_LOCK.json`. Do not reuse this season as an untouched test.

All eight precommitted historical gate checks passed. On 5,647 eligible games:

| Model | Correct | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| Fixed Elo | 3,991 | 70.67% | 0.19495 | 0.57400 |
| Calibrated Elo logistic | 3,997 | 70.78% | 0.19133 | 0.56253 |
| Locked statistical candidate | 4,052 | 71.75% | 0.18545 | 0.54597 |

The candidate got 61 more winners correct than fixed Elo. November accuracy was
77.19% over 1,245 games, with Brier 0.15675 versus calibrated Elo's 0.16445.
Neutral-site accuracy was 63.72% over 623 games, with Brier 0.22030 versus
calibrated Elo's 0.22541. Non-neutral accuracy was 72.75% over 5,024 games.

Exact metrics, source hashes, eligibility exclusions, confidence bands and a
descriptive paired bootstrap are in `results/holdout_2026.json`. All 5,647
historical forecasts are archived in `results/holdout_2026_predictions.csv`.
Portable coefficients are in `results/candidate_bundle.json`; inference was
checked against the fitted model. Six tests pass. Neither training nor
calibration used 2026 outcomes.

Status: passed historical gate, pending live pipeline validation. This is not
prospective evidence and does not authorize automatic publication. Next validate
2026–27 schedule eligibility and coverage, pregame timestamps, same-source team
identity, the result embargo, immutable forecast capture and final grading.
No roster/transfer/injury adjustment is supported yet. Unknown-conference games
remain excluded; historical membership and overtime-adjusted pace are documented
limitations of this scoped first candidate.
