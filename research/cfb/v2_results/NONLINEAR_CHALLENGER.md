# CFB V2 Nonlinear Challenger

Shallow histogram gradient boosting uses only the same leakage-safe, market-free feature families as V1. Every season is trained on prior seasons only; 2026 is excluded.

| Candidate | Accuracy | Brier | Delta Brier | Recent Brier | Seasons improved |
|---|---:|---:|---:|---:|---:|
| hgb_l7_lr03_w35 | 72.81% | 0.176387 | -0.000951 | 0.179325 | 8/8 |
| hgb_l15_lr03_w35 | 72.95% | 0.176459 | -0.000879 | 0.179129 | 6/8 |
| hgb_l7_lr03_w25 | 72.68% | 0.176558 | -0.000780 | 0.179470 | 8/8 |
| hgb_l15_lr03_w25 | 72.84% | 0.176576 | -0.000762 | 0.179312 | 7/8 |
| hgb_l7_lr05_w35 | 73.09% | 0.176593 | -0.000745 | 0.179365 | 7/8 |
| hgb_l7_lr05_w25 | 72.95% | 0.176693 | -0.000645 | 0.179493 | 7/8 |
| hgb_l15_lr05_w25 | 72.95% | 0.176742 | -0.000596 | 0.179456 | 7/8 |
| hgb_l15_lr05_w35 | 73.00% | 0.176746 | -0.000591 | 0.179368 | 6/8 |
| hgb_l15_lr03_w15 | 72.70% | 0.176800 | -0.000538 | 0.179572 | 7/8 |
| hgb_l7_lr03_w15 | 72.72% | 0.176810 | -0.000528 | 0.179677 | 8/8 |

## Sequential configuration selection

- V1 2021-2025: 71.53% accuracy / 0.183011 Brier.
- Nonlinear challenger: 71.48% accuracy / 0.182127 Brier.

| Season | Chosen using prior seasons | Challenger Brier | V1 Brier |
|---|---|---:|---:|
| 2021 | hgb_l7_lr03_w35 | 0.181815 | 0.183720 |
| 2022 | hgb_l7_lr03_w35 | 0.191159 | 0.191346 |
| 2023 | hgb_l7_lr03_w35 | 0.171344 | 0.171438 |
| 2024 | hgb_l7_lr03_w35 | 0.186456 | 0.187191 |
| 2025 | hgb_l7_lr03_w35 | 0.180040 | 0.181530 |
