# CFB Incremental Information vs Market

Diagnostic only. Market prices remain excluded from the B.P. production winner model. Each target season uses only earlier seasons for meta-model fitting and margin-candidate selection.

| Line | Games | Market Brier | Market + V1 | Market + V1 + margin | Best Δ vs market |
|---|---:|---:|---:|---:|---:|
| spread_open | 3,015 | 0.177259 | 0.177131 | 0.177161 | -0.000129 |
| spread | 4,264 | 0.175729 | 0.175849 | 0.175870 | +0.000120 |

A negative delta means the independent B.P. signal improved the spread-only benchmark out of sample. A positive delta means the market already subsumed the tested model information.
