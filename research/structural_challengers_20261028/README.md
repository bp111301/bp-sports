# Rebuilt structural challenger tournament

All fixed recipes have completed. Historical development only; repeatedly reused history and multiple candidates do not establish prospective improvement.

## CFB: ten candidate recipes

| Recipe | Wins | Games | Accuracy | Brier | Log loss | Qualified |
|---|---:|---:|---:|---:|---:|---|
| cat_d3_l2_20 | 4203 | 5733 | 73.312% | 0.177866 | 0.530952 | False |
| cat_d3_l2_20_halfblend | 4184 | 5733 | 72.981% | 0.175997 | 0.524998 | False |
| cat_d3_l2_5 | 4208 | 5733 | 73.400% | 0.178893 | 0.533351 | False |
| cat_d3_l2_5_halfblend | 4176 | 5733 | 72.841% | 0.176401 | 0.525872 | False |
| cat_d5_l2_20 | 4205 | 5733 | 73.347% | 0.178765 | 0.533560 | False |
| cat_d5_l2_20_halfblend | 4183 | 5733 | 72.964% | 0.176178 | 0.525394 | False |
| cat_d5_l2_5 | 4192 | 5733 | 73.121% | 0.179340 | 0.534178 | False |
| cat_d5_l2_5_halfblend | 4200 | 5733 | 73.260% | 0.176443 | 0.525776 | False |
| control | 4170 | 5733 | 72.737% | 0.177341 | 0.528055 | Reference |
| margin_normal | 4193 | 5733 | 73.138% | 0.177719 | 0.529734 | False |
| margin_normal_halfblend | 4195 | 5733 | 73.173% | 0.176262 | 0.525238 | False |

Selected research candidate: **none**.

## NHL: twelve candidate recipes

| Recipe | Wins | Games | Accuracy | Brier | Log loss | Qualified |
|---|---:|---:|---:|---:|---:|---|
| cat_d3_l2_20 | 3149 | 5248 | 60.004% | 0.236153 | 0.665069 | False |
| cat_d3_l2_20_halfblend | 3172 | 5248 | 60.442% | 0.232703 | 0.657503 | False |
| cat_d3_l2_5 | 3167 | 5248 | 60.347% | 0.235102 | 0.662898 | False |
| cat_d3_l2_5_halfblend | 3199 | 5248 | 60.957% | 0.232157 | 0.656301 | False |
| cat_d5_l2_20 | 3103 | 5248 | 59.127% | 0.237483 | 0.667875 | False |
| cat_d5_l2_20_halfblend | 3175 | 5248 | 60.499% | 0.232956 | 0.657949 | False |
| cat_d5_l2_5 | 3139 | 5248 | 59.813% | 0.237123 | 0.667343 | False |
| cat_d5_l2_5_halfblend | 3178 | 5248 | 60.556% | 0.232830 | 0.657717 | False |
| control | 3219 | 5248 | 61.338% | 0.231620 | 0.655148 | Reference |
| poisson_alpha_0.01 | 3187 | 5248 | 60.728% | 0.232528 | 0.657104 | False |
| poisson_alpha_0.01_halfblend | 3205 | 5248 | 61.071% | 0.231726 | 0.655325 | False |
| poisson_alpha_0.1 | 3171 | 5248 | 60.423% | 0.232460 | 0.656891 | False |
| poisson_alpha_0.1_halfblend | 3210 | 5248 | 61.166% | 0.231703 | 0.655279 | False |

Selected research candidate: **none**.

## Validation and limits

Eight structural safety tests pass: train-only imputation, chronological season/date boundaries, prior-only residual sigma, scoring-probability validity, fixed CatBoost configuration, duplicate NHL team/date rejection, all-empty training column retention, and outcome exclusion/calendar/postseason inputs. The separate QB repair has six safety tests; confidence projection and bundle interface have eight more, for22 focused tests total.

Every candidate has the identical reference game IDs, labels and evaluation cohort. Original control probabilities reproduce at game level within1e-12 across the whole CFB and NHL cohorts. NHL was rerun completely with byte-identical prediction CSV, temporal-boundary JSON and result JSON. CFB has one complete rebuilt tournament; no second complete CFB tournament rerun is claimed.

The earlier unsaved runs remain preliminary. These outputs are rebuilt from the existing registered protocol and saved separately. The CFB calendar feature was corrected to whole days before this complete evaluation; no gate or recipe was changed after viewing its results.

See each results.json for all gates, every season, recent performance, confidence bucket support/Wilson intervals and paired block-bootstrap accuracy intervals. Intervals are descriptive, not adjusted for repeated model selection. Source hashes, exact code hashes and environment versions are in source_manifest.json.

No existing model weight, historical evaluation, forecast or grade was changed. No production model was promoted. The separately qualified confidence-only recipes now have frozen research bundles in ../confidence_projection_20261028/final_bundles/; they still require same-time prospective shadow collection and independent results. They preserve reference winners and do not constitute winner-selection improvements.

## Reproduction

Use Python3.12 and requirements.txt in an isolated environment. From repository root:

```sh
python research/structural_challengers_20261028/download_sources.py
python -W ignore -m pytest --import-mode=importlib -q research/structural_challengers_20261028/test_safety.py
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/structural_challengers_20261028/experiment.py --sport cfb
OPENBLAS_NUM_THREADS=1 OMP_NUM_THREADS=1 python research/structural_challengers_20261028/experiment.py --sport nhl
```

Compare downloaded file hashes with source_manifest.json before interpreting a rerun. Remote historical sources can change; a mismatched source is not an exact reproduction. No live2026 CFB or2026–27 NHL outcome enters this tournament; NHL2025–26 is also excluded here.
