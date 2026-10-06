# CFB V2 Combined Challenger

For each target season, the margin configuration, nonlinear configuration, and their blend weight are chosen using only earlier out-of-fold seasons. The target season is untouched until scoring. No market or 2026 data enters selection.

| Model | 2021-25 accuracy | Brier | Log loss |
|---|---:|---:|---:|
| v1 | 71.53% | 0.183011 | 0.542658 |
| margin | 71.69% | 0.182362 | 0.539834 |
| nonlinear | 71.48% | 0.182127 | 0.539408 |
| combo | 71.53% | 0.182144 | 0.539372 |

## Locked season-by-season choices

| Season | Margin | Nonlinear | Nonlinear weight | Combo Brier | V1 Brier |
|---|---|---|---:|---:|---:|
| 2021 | blend_prior_a100_w35 | hgb_l7_lr03_w35 | 100% | 0.181815 | 0.183720 |
| 2022 | blend_prior_a100_w50 | hgb_l7_lr03_w35 | 100% | 0.191159 | 0.191346 |
| 2023 | blend_prior_a100_w50 | hgb_l7_lr03_w35 | 75% | 0.171321 | 0.171438 |
| 2024 | blend_prior_a100_w50 | hgb_l7_lr03_w35 | 75% | 0.186423 | 0.187191 |
| 2025 | blend_context_a100_w50 | hgb_l7_lr03_w35 | 75% | 0.180175 | 0.181530 |
