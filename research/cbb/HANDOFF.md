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
