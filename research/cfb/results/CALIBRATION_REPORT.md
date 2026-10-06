# CFB V1 Calibration Experiment

All calibration mappings are trained only on out-of-sample probabilities from seasons before the season being predicted.

| Candidate | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| context_platt_1 | 72.63% | 0.1779 | 0.5293 |
| context_raw | 72.67% | 0.1780 | 0.5294 |
| full_c005_raw | 72.84% | 0.1781 | 0.5294 |
| context_platt_3 | 72.84% | 0.1781 | 0.5304 |
| full_c005_platt_3 | 72.74% | 0.1783 | 0.5304 |

Leader by Brier: **context_platt_1**.

2026 remains untouched.
