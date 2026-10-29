# Corrected QB count experiment — rebuilt results

Historical development only. Repeatedly reused history; no live accuracy claim. All three fixed recipes failed the original joint gate.

| Recipe | Wins / 4,999 | Accuracy | Brier | Log loss | Qualified |
|---|---:|---:|---:|---:|---|
| control | 3614 | 72.294% | 0.179442 | 0.533684 | Reference |
| qb_counts_augmented | 3617 | 72.354% | 0.180385 | 0.536019 | False |
| qb_counts_halfblend | 3618 | 72.374% | 0.179661 | 0.534194 | False |
| qb_offset_correction | 3612 | 72.254% | 0.181227 | 0.538860 | False |

Numeric-ID identity retention: 99.552%. Both-team prior QB coverage: 92.158%.

Only same-season observations at least two calendar days earlier enter the twenty features. These describe the last observed incumbent, not a confirmed upcoming starter. Counts are aggregated before rates. No live 2026 labels enter development.

Safeguards: duplicate identities fail; <99% source retention or <70% paired coverage fails; train-only imputation; temporal exclusion; fixed feature allowlist; exact original control parity check. Six focused tests passed.

See results/results.json for every gate, season, confidence bucket, support/Wilson interval and paired season/week bootstrap accuracy interval. Bootstrap intervals are descriptive, not adjusted for repeated model selection.

This is a rebuilt implementation, not an exact reproduction of the lost preliminary QB run. The source validation and resulting candidate counts differ. No gate or hyperparameter was relaxed. No weights, historical evaluations or immutable forecasts were changed.
