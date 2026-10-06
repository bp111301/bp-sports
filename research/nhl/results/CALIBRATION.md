# NHL Leader Calibration

Each season uses only earlier season OOF labels. 2021–22 is warm-up; fair calibration comparison is 2022–23 through 2024–25 (3,936 games). No 2025–26 input.

| Method | Accuracy | Brier | Log loss | Seasons improved | Eligible |
|---|---:|---:|---:|---:|---|
| raw | 60.24% | 0.233072 | 0.657892 | 0 | False |
| temperature | 60.24% | 0.233089 | 0.657957 | 1 | False |
| sigmoid | 60.32% | 0.233077 | 0.657928 | 2 | False |

Selected method: **raw**.

## Selected confidence buckets (all development, 5,248 games)

| Predicted winner confidence | Games | Mean confidence | Actual win rate | 95% Wilson interval |
|---|---:|---:|---:|---|
| 50%–55% | 1329 | 52.53% | 52.97% | 50.28%–55.64% |
| 55%–60% | 1278 | 57.40% | 58.37% | 55.65%–61.05% |
| 60%–65% | 1025 | 62.45% | 60.78% | 57.76%–63.72% |
| 65%–70% | 743 | 67.44% | 67.16% | 63.70%–70.44% |
| 70%–75% | 508 | 72.21% | 71.65% | 67.58%–75.40% |
| 75%–80% | 258 | 77.19% | 74.81% | 69.17%–79.71% |
| 80%–90% | 107 | 82.55% | 84.11% | 76.02%–89.84% |
| 90%–100% | 0 | — | — | — |

Reused development seasons; binomial intervals are descriptive, not a guarantee of future performance or independence.
