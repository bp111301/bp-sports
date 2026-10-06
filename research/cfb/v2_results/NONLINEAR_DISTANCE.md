# CFB V2 Nonlinear + Distance

Tests the already-selected shallow nonlinear architecture with one leakage-safe travel-distance feature. Hyperparameters remain fixed; 2026 and market data are excluded.

| Candidate | Overall accuracy | Overall Brier | 2021-25 accuracy | 2021-25 Brier | Delta vs HGB |
|---|---:|---:|---:|---:|---:|
| v1 | 72.74% | 0.177338 | 71.53% | 0.183011 | +0.000883 |
| v1_distance | 72.74% | 0.177248 | 71.50% | 0.182896 | +0.000769 |
| hgb | 72.81% | 0.176387 | 71.48% | 0.182127 | +0.000000 |
| hgb_distance_signal | 72.79% | 0.176395 | 71.45% | 0.182116 | -0.000011 |
| hgb_distance_full | 72.84% | 0.176337 | 71.50% | 0.182043 | -0.000085 |
