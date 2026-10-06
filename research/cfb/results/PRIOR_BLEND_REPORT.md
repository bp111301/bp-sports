# CFB V1 Dynamic Prior Experiment

Current-season efficiency is blended with prior-season efficiency using only pregame information. 2026 is excluded.

| Candidate | Accuracy | Brier | Log loss |
|---|---:|---:|---:|
| blend_replace_k7 | 72.82% | 0.1775 | 0.5286 |
| blend_replace_k5 | 72.60% | 0.1775 | 0.5286 |
| blend_replace_k3 | 72.75% | 0.1776 | 0.5289 |
| context_raw | 72.67% | 0.1780 | 0.5294 |
| blend_add_k3 | 72.51% | 0.1781 | 0.5302 |
| blend_add_k7 | 72.54% | 0.1781 | 0.5303 |
| blend_add_k5 | 72.53% | 0.1782 | 0.5303 |

Leader by Brier: **blend_replace_k7**.
