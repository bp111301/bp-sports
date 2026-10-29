# Additional CFB information and NHL rate aggregation — October 28, 2026

Four registered feature-based recipes and one separately registered postseason correction were evaluated. **None passed the joint accuracy-and-confidence gate. No live model, pick or percentage changed.** CFB picked more historical winners in one variant but worsened aggregate probability quality. NHL probability quality improved consistently without improved overall winner accuracy. These are separate research leads, not production upgrades.

`PROTOCOL.md` was committed before these results. The same historical development seasons have already been reused; these results are not independent confirmation. No post-result tuning, live-label selection or threshold relaxation was performed.

| Sport | Recipe | Accuracy | Net correct vs control | Brier ↓ | Log loss ↓ | Fixed-bin confidence error ↓ |
|---|---|---:|---:|---:|---:|---:|
| CFB | control | 72.737% | +0 | 0.177341 | 0.528055 | 1.794 pp |
| CFB | expanded_halfblend | 72.754% | +1 | 0.177186 | 0.527855 | 1.854 pp |
| CFB | expanded_linear | 72.946% | +12 | 0.177622 | 0.529331 | 1.841 pp |
| NHL | control | 61.338% | +0 | 0.231620 | 0.655148 | 0.919 pp |
| NHL | pooled_rates | 61.319% | -1 | 0.231394 | 0.654658 | 0.415 pp |
| NHL | pooled_rates_halfblend | 61.261% | -4 | 0.231436 | 0.654751 | 0.668 pp |

CFB cohort: 5,733 games, target seasons 2018–2025. NHL: 5,248 games, 2021–22 through 2024–25. These percentages are historical development results, not the live 2026 records.

## Findings

CFB expanded linear picked 12 additional winners (72.946% versus 72.737%) and four additional recent winners in 2023–2025. However, aggregate Brier rose from .177341 to .177622, log loss worsened, and fixed-bin confidence error rose slightly. Its paired season/week bootstrap accuracy-difference interval is **−0.217 to +0.642 percentage points**. It fails the registered +.5-point accuracy threshold and probability/calibration requirements. The 50/50 blend selected just one additional winner overall and four fewer recent winners; despite better probability scores, it also fails.

NHL pooled rates picked one fewer winner overall (61.319% versus 61.338%), seven more recent winners, and improved Brier and log loss in all four development seasons. Fixed-bin confidence error fell from .919 to .415 percentage points. That is a useful probability-reliability lead, but it does not satisfy a joint winner-accuracy improvement goal. Its paired day-block accuracy-difference interval is **−0.462 to +0.414 percentage points**. The half-blend picked four fewer winners while also improving probability scores. Neither becomes an eligible shadow or live replacement under this protocol.

Expected calibration error depends on the chosen bins and sample composition. A lower development ECE does not establish trustworthy individual-game percentages or prospective improvement. The full result JSON includes counts, actual win rates, mean confidence and Wilson intervals for all fixed buckets, per-season and recent results, uncertainty intervals, and each exact gate decision.

## Information added

CFB adds 12 current/prior k7 blended differences: offensive/defensive weighted EPA, third-down percentage, scoring-opportunity rate over expected, starting field position, rush rate over expected, and plays per game. Three pass/rush/success-rate interaction differences encode attack-versus-opponent-defence products. Both original ensemble components retain their original recipe and C=.5. New values are missing on approximately .17–.19% of evaluation games; missingness is reported before imputation, never treated as observed zero. Market data, realized QB identity, scores and retrospective game-day weather are excluded from learner inputs.

NHL replaces equal-game-average percentages with pooled goals/opportunities, shrunk toward strictly earlier league counts. Shooting/save estimates receive 100 prior shots, PP/PK estimates 20 prior opportunities. Each team's window is its latest 20 current-season source games, with at least three valid games per metric. Source games from the target day and previous calendar day are excluded. Missing numerator/denominator is excluded, while a valid zero-opportunity game contributes zero opportunities. The original possession/faceoff and 10 base features stay; new logistic imputation has no indicators because of the previously documented missingness sensitivity. The four new differences are missing on 4.25% of evaluation games, primarily early season under the conservative lag.

## What is preserved and verified

Only this new research directory is added. Original models, weight files, manifests, live builders, current forecasts, first saved forecasts, graded outcomes, dashboard and previous historical reports are unchanged. No rejected model is frozen or sent into a live/shadow prediction ledger. Input source boundaries use the earlier guarded loaders: CFB through season 2025, NHL through 2024–25. NHL 2025–26 is not opened for selection. Controls reproduce the earlier bounded experiment within 1e-12.

Seven new tests check future/target/previous-day outcome mutation, team-side symmetry, CFB prior transitions and missingness, opportunity-weighted arithmetic, valid zero opportunities versus missing data, chronological source limits, source-order independence, and duplicate rejection. Thirteen existing observer/challenger tests pass. Independent full reruns reproduced every prediction, new feature vector, decision, metric and temporal boundary exactly. Compressed feature matrices and NHL source boundaries make the experiment auditable.

Historical CFB efficiency features inherit the original upstream pregame-source assumptions; regenerating old rows does not independently prove their original publication vintage. This limitation, repeated use of development data, and excluded seasons prevent claiming live improvement. Existing raw feature receipts collect future provenance; they do not reconstruct missing historical receipts.

## Already-tested NHL shot quality

The existing NHL branch factor tournament was inspected before choosing this test. MoneyPuck-based exploratory shot-quality features had already been evaluated and did not improve aggregate winner accuracy; their historical model vintage remained unverified. This experiment does not rerun those candidates or treat that data as verified pregame history. See `prior_research_inspection.json` for pinned branch/file references and hashes.

## Reproduce

Use the pinned research dependencies in `research/challengers_20261028/requirements-research.txt` and the historical downloads from that directory. The new source manifest hashes the exact selected raw files and helpers; source URLs and extraction details are preserved in the prior manifest.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m unittest discover -s research/feature_challengers_20261028 -p 'test_features.py'
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/feature_challengers_20261028/experiment.py --sport cfb
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/feature_challengers_20261028/experiment.py --sport nhl
```

Outputs default to `runtime/feature_challengers_20261028/`, preserving committed results. Same source and dependency hashes are necessary for exact reproduction.

## Next boundary

Do not combine or recalibrate these recipes after seeing the results and call it confirmation. Any further hypothesis needs a separate preregistered protocol, honest accounting for reused development seasons and fresh pregame input provenance. The live confidence evidence remains descriptive; it is not an installed calibration correction. A future qualifying candidate must freeze a distinct specification and collect new paired outcomes before a promotion review.

## Separately registered CFB postseason finding

Input inspection found 31 explicit postseason source rows with week=1; all 31 have both current and previous home EPA, and the original k7 blend returns previous-season EPA because its current-season weight is zero at week1. `POSTSEASON_PROTOCOL.md` was registered before testing a separate correction. The original source, V1 recipe, model and forecasts remain untouched.

`postseason.py` prototypes a new prior input recipe: explicit postseason rows receive effective prior-progress week8 (100% current-season weighting), while regular-season week handling stays unchanged. It retains the original feature set, 25/75 ensemble and logistic settings; it is not combined with the expanded-feature test.

Across the 28 postseason games in evaluation seasons 2018–2025, both models picked 19 winners; the source's other three postseason rows occur in training-only seasons. Postseason Brier improved from .187549 to .174178 and log loss from .545105 to .519144, but this is a tiny, reused subgroup. Refitting earlier seasons with the corrected input also affects later regular-season predictions: full-cohort accuracy fell from 4,170 to 4,168 correct out of 5,733. The full gate fails, including recent results and ECE. This input-recipe issue is now documented and reproducibly tested; the correction has not been installed into frozen V1 or promoted as a better general model. No postseason historical forecast is rewritten.

A seventh safety test proves the corrected research mapping uses current efficiency for postseason, preserves regular-season prior handling, rejects unknown season types and leaves original source values unchanged. To reproduce this separately registered test:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/feature_challengers_20261028/postseason.py
```
