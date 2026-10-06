# CFB External Market Benchmark

The point spread remains outside the B.P. winner model. This is a benchmark only: each season's spread-to-win-probability mapping is fit using prior seasons, then evaluated on that season.

| Benchmark | Games | Market accuracy | V1 accuracy | Market Brier | V1 Brier | Market − V1 Brier |
|---|---:|---:|---:|---:|---:|---:|
| spread_open | 3,015 | 73.43% | 71.58% | 0.1773 | 0.1829 | -0.0056 |
| spread | 5,733 | 73.63% | 72.74% | 0.1723 | 0.1773 | -0.0050 |

This benchmark is deliberately difficult. Historical betting spreads aggregate information from many participants and are widely documented as strong predictors of college-football outcomes. Beating V1 is not enough for V2; the long-term goal is to identify independent information the market does not already contain.
