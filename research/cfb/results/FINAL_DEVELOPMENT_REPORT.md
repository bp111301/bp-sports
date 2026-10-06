# CFB V1 Final Development Tournament

No 2026 games were used. Ranking is by walk-forward Brier score, then log loss, with 2023-2025 shown as a stability check.

| Candidate | Accuracy | Brier | Log loss | 2023-25 acc | 2023-25 Brier |
|---|---:|---:|---:|---:|---:|
| blend_context_prior_25 | 72.74% | 0.1773 | 0.5280 | 72.10% | 0.1801 |
| blend_context_prior_50 | 72.77% | 0.1774 | 0.5280 | 72.15% | 0.1800 |
| prior_k7_platt1 | 72.74% | 0.1774 | 0.5283 | 72.02% | 0.1809 |
| prior_k7_raw | 72.82% | 0.1775 | 0.5286 | 72.19% | 0.1803 |
| context_raw | 72.67% | 0.1780 | 0.5294 | 72.02% | 0.1801 |

Prefreeze leader: **blend_context_prior_25**.

The next step after this report is to lock the CFB V1 specification before opening the 2026 diagnostic holdout.
