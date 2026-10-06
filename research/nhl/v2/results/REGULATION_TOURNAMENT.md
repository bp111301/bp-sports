# NHL Regulation-Strength Tournament

All model fitting/selection uses 2021–22 through 2024–25 walk-forward only.

| Candidate | Accuracy | Brier | Log loss | Seasons improved | Research eligible |
|---|---:|---:|---:|---:|---|
| linear_regulation_blend | 61.32% | 0.231470 | 0.654772 | 3 | False |
| v1_reference | 61.34% | 0.231620 | 0.655148 | 0 | False |
| regulation_form_logistic | 61.22% | 0.231818 | 0.655573 | 1 | False |
| regulation_threeway | 61.36% | 0.231824 | 0.655521 | 1 | False |
| regulation_poisson | 60.63% | 0.233398 | 0.659023 | 0 | False |

Selected research candidate: v1_reference.
Regulation score reconstructed by removing one winning overtime/shootout goal. Poisson assumes independent goal counts; extra-time win chance fixed at .5, not known outcome.
No independent confirmation or live release is claimed.
