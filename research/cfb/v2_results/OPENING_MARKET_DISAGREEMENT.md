# CFB Opening-Market Disagreement Audit

The opening spread is benchmark-only. It never enters B.P.'s winner model. Market probabilities are calibrated using prior seasons only; 2026 is excluded.

| B.P. vs opening-market probability gap | Games | B.P.-lean side win rate | Market expected | Excess | V1 Brier | Market Brier |
|---|---:|---:|---:|---:|---:|---:|
| 0.0%-2.5% | 779 | 51.60% | 52.13% | -0.52% | 0.1323 | 0.1319 |
| 2.5%-5.0% | 618 | 56.31% | 54.16% | +2.15% | 0.1649 | 0.1645 |
| 5.0%-7.5% | 463 | 55.51% | 51.30% | +4.21% | 0.1800 | 0.1814 |
| 7.5%-10.0% | 361 | 50.42% | 52.41% | -1.99% | 0.2071 | 0.1961 |
| 10.0%-15.0% | 453 | 56.95% | 50.04% | +6.91% | 0.2146 | 0.2153 |
| 15.0%-100.0% | 341 | 44.57% | 43.84% | +0.73% | 0.2672 | 0.2280 |

## Cumulative disagreement thresholds

| Minimum gap | Games | B.P.-lean win rate | Market expected | Excess |
|---|---:|---:|---:|---:|
| 2.5%+ | 2,236 | 53.53% | 50.88% | +2.66% |
| 5.0%+ | 1,618 | 52.47% | 49.62% | +2.85% |
| 7.5%+ | 1,155 | 51.26% | 48.95% | +2.30% |
| 10.0%+ | 794 | 51.64% | 47.38% | +4.26% |
| 15.0%+ | 341 | 44.57% | 43.84% | +0.73% |
