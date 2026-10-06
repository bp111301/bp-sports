# CFB V2 Margin Challenger

Ridge score-margin models are trained only on prior seasons. Their predicted margins are converted to win probabilities using training residual variance. 2026 is excluded.

| Candidate | Accuracy | Brier | Δ Brier | Recent Brier | Recent Δ | Seasons improved |
|---|---:|---:|---:|---:|---:|---:|
| blend_context_a100_w50 | 72.82% | 0.176808 | -0.000530 | 0.179718 | -0.000386 | 6/8 |
| blend_context_a10_w50 | 72.84% | 0.176837 | -0.000501 | 0.179611 | -0.000493 | 4/8 |
| blend_context_a1_w50 | 72.79% | 0.176849 | -0.000488 | 0.179599 | -0.000506 | 4/8 |
| blend_context_a100_w35 | 72.93% | 0.176851 | -0.000487 | 0.179755 | -0.000349 | 6/8 |
| blend_prior_a100_w50 | 72.84% | 0.176859 | -0.000479 | 0.179920 | -0.000185 | 5/8 |
| blend_context_a10_w35 | 73.02% | 0.176869 | -0.000469 | 0.179678 | -0.000426 | 6/8 |
| blend_context_a1_w35 | 73.02% | 0.176876 | -0.000462 | 0.179669 | -0.000436 | 5/8 |
| blend_prior_a100_w35 | 72.81% | 0.176916 | -0.000422 | 0.179908 | -0.000197 | 6/8 |
| blend_prior_a10_w50 | 72.65% | 0.176928 | -0.000410 | 0.179875 | -0.000230 | 6/8 |
| blend_context_a100_w25 | 72.89% | 0.176934 | -0.000403 | 0.179818 | -0.000287 | 6/8 |
| blend_prior_a1_w50 | 72.65% | 0.176943 | -0.000395 | 0.179869 | -0.000236 | 5/8 |
| blend_context_a10_w25 | 73.02% | 0.176947 | -0.000391 | 0.179762 | -0.000343 | 6/8 |
| blend_context_a1_w25 | 72.98% | 0.176950 | -0.000387 | 0.179755 | -0.000350 | 6/8 |
| blend_prior_a10_w35 | 72.82% | 0.176967 | -0.000371 | 0.179875 | -0.000230 | 6/8 |
| blend_prior_a1_w35 | 72.82% | 0.176978 | -0.000360 | 0.179870 | -0.000234 | 6/8 |
