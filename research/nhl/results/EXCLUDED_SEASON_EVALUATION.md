# NHL V1 Excluded-Season Evaluation

2025–26; specification committed before evaluation. Model weights fit only on 2018–19 through 2024–25.

| Model | Games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| Frozen NHL V1 | 1312 | 53.43% | 0.249421 | 0.692045 |
| Fixed baseline | 1312 | 53.43% | 0.248543 | 0.690427 |

Eligible for prospective shadow: **False**. This does not activate production predictions.

Excluded from candidate selection; baseline-only results were previously viewed. No tuning, calibration refit or classifier refit on excluded-season labels. Prior completed evaluation games update rolling features only.

## Confidence buckets

| Confidence | Games | Mean predicted | Actual win rate |
|---|---:|---:|---:|
| 50%–55% | 440 | 52.52% | 50.23% |
| 55%–60% | 374 | 57.27% | 50.00% |
| 60%–65% | 253 | 62.30% | 54.94% |
| 65%–70% | 154 | 67.07% | 59.09% |
| 70%–75% | 67 | 72.25% | 65.67% |
| 75%–80% | 18 | 77.19% | 77.78% |
| 80%–90% | 5 | 81.73% | 80.00% |
| 90%–100% | 1 | 94.94% | 100.00% |
