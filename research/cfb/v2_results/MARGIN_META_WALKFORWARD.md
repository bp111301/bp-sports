# CFB V2 Margin Meta Walk-Forward

Each target season locks the margin blend using only earlier out-of-fold seasons. No target-season result participates in that season's candidate choice; 2026 remains excluded.

| Target | Prior selection window | Locked candidate | V1 Brier | Challenger Brier | Δ Brier |
|---|---|---|---:|---:|---:|
| 2021 | 2018-2020 | blend_prior_a100_w35 | 0.183720 | 0.182688 | -0.001032 |
| 2022 | 2018-2021 | blend_prior_a100_w50 | 0.191346 | 0.189967 | -0.001379 |
| 2023 | 2018-2022 | blend_prior_a100_w50 | 0.171438 | 0.171633 | +0.000195 |
| 2024 | 2018-2023 | blend_prior_a100_w50 | 0.187191 | 0.186710 | -0.000481 |
| 2025 | 2018-2024 | blend_context_a100_w50 | 0.181530 | 0.180955 | -0.000575 |

## Aggregate 2021-2025

- V1: 71.53% accuracy, 0.183011 Brier, 0.542658 log loss.
- Sequential margin challenger: 71.69% accuracy, 0.182362 Brier, 0.539834 log loss.
- Delta: +0.16% accuracy, -0.000649 Brier.

## Audited weak spots

- conference: V1 70.07%/0.1923; challenger 70.22%/0.1916.
- weeks_7_9: V1 70.81%/0.1863; challenger 70.43%/0.1864.
