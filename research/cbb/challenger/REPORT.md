# CBB challenger development results — October 16, 2026

Status: combined challenger shortlisted for further validation. V1 unchanged.

## Same-cohort development comparison

Evaluate ending-year 2023, 2024 and 2025 chronologically, covering 16,840 regular-season games. Train through Y−2 and calibrate on Y−1. These previously inspected development seasons are exploratory evidence. The 2025–26 historical holdout was not loaded or evaluated. Its original 71.75% result remains unchanged.

| Variant | Correct | Accuracy | Brier ↓ | Log loss ↓ |
|---|---:|---:|---:|---:|
| V1 replay | 12,001 | 71.26% | 0.18658 | 0.54987 |
| Opponent adjustment | 12,060 | 71.62% | 0.18329 | 0.54113 |
| Observed rotation continuity | 12,022 | 71.39% | 0.18558 | 0.54724 |
| Both additions | 12,100 | 71.85% | 0.18260 | 0.53925 |

The combined variant adds 99 correct picks (+0.59 percentage points) on the identical cohort. Probability quality improves in all three seasons. These figures do not revise the separate 71.75% locked holdout result and are not a prospective record.

## Seasonal comparison

| Ending-year season | Games | V1 accuracy | Combined accuracy | V1 Brier | Combined Brier |
|---|---:|---:|---:|---:|---:|
| 2023 | 5,601 | 70.72% | 71.68% | 0.18848 | 0.18550 |
| 2024 | 5,603 | 71.25% | 71.93% | 0.18810 | 0.18339 |
| 2025 | 5,636 | 71.82% | 71.95% | 0.18318 | 0.17893 |

## Decision and limits

All three additions meet the precommitted development-shortlist rule. Combined is the leading development candidate because it has the best pooled accuracy, Brier and log loss, with improvements over V1 in every fold. No model is promoted, published to the live board or retrained here. This is not enough evidence to promise improved future accuracy.

Continuity uses only already-observed current-season player minutes, matched to earlier-season player identities. It does not establish opening-night rosters, prospective transfers, injuries or availability. Before the first eligible appearance clears the embargo, the rotation remains unknown. Missing player boxes are excluded from this input; forecasts remain on the same full evaluation cohort.

A future step is to lock a portable challenger and validate a separate prospective capture pipeline before collecting shadow forecasts alongside V1. Do not tune on the already-reviewed 2026 holdout. No automatic follow-up, schedule or production change is enabled.

## Integrity and reproduction

- 18 original and challenger tests passed.
- V1 probabilities replayed within 1e-12 on every fold.
- All 12 schedule/team-box source hashes match the original V1 development audit.
- Player coverage, source URLs and hashes are in `results/comparison.json`.
- Raw per-game probabilities are in `results/predictions.csv.gz`; decompressed and compressed SHA-256 checksums are recorded.
- Experiment protocol was committed before evaluation; no hyperparameter search.
- Frozen V1 coefficients, historical evaluations, prospective forecasts and grading remain unchanged.
- No preseason games or 2026/2027 inputs were evaluated.

See `README.md` for the reproduction command and feature definitions.
