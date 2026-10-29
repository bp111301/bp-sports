# CFB near-qualifier failure audit

Descriptive analysis of reused historical development predictions. No2026 outcome was used; no original model, forecast or evaluation was changed.

The parent challenger fixed144 original errors and broke114 originally correct picks, for30 net additional wins. It changed258 picks;5,475 picks stayed the same. In2018,2020 and2024, changed-pick Brier improved but confidence changes on unchanged picks outweighed that gain.2023 worsened in both groups.

| Stage | Games | Net extra wins | Brier change | Logloss change |
|---|---:|---:|---:|---:|
| postseason | 28 | -1 | +0.002134 | +0.007230 |
| regular_1_4 | 1467 | 6 | -0.001983 | -0.005186 |
| regular_5_8 | 1632 | 16 | -0.001183 | -0.004041 |
| regular_9_plus | 2606 | 9 | -0.000141 | +0.000359 |

Missing weighted talent was not the historical cause of overall failure: both missing and present groups improved aggregate Brier. This does not imply missingness is harmless in every season. Team groups overlap and are descriptive; the20 adverse games are retained for diagnosis, not excluded from evaluation.

## Current live inputs

Among59 saved CFB shadow captures, weighted-talent difference is missing in23 games (38.98%), versus19.13% in the historical source-week-matched sample. One observed difference is outside the historical matched-week range. These are distribution/coverage flags, not proof of corrupt data or the cause of the older live losses. No captured numeric feature is infinite. No2026 outcome was used.

The original shadow snapshots retain source week but not season_type; the type-matched comparison cannot be verified from those receipts. The report explicitly records this limitation. These are later research captures, not the unavailable first-input vectors of the older175 graded V1 forecasts.

## Resulting experiment

Separately registered cfb_anchor_20261029 tests exactly one response: retain the reference probability when the parent challenger leaves the winner unchanged; otherwise retain the parent probability. It preserves every parent winner without fitting another parameter. All original gates stay fixed. This is an adaptively motivated development test and still needs prospective validation.

Complete group metrics, source checksums and flags are in results/results.json; every paired row is retained in paired_diagnostics.csv.gz.
