# Confidence-only challengers: development qualification

**Both CFB and NHL passed the separately registered confidence-only research gate. Neither is deployed or proven prospectively.** All original winner selections remain identical. This is a confidence-reliability result, not improved winner accuracy. The original joint winner-and-confidence failures remain failed; their accuracy thresholds were not lowered.

The exact projection was registered in `PROTOCOL.md` before projected results were calculated. It was motivated by previously inspected development results, so these are adaptively selected, reused historical tests. A future independent comparison is necessary.

| Sport | Games | Winner accuracy | Brier ↓ | Log loss ↓ | Fixed-bin confidence error ↓ | Seasons with better Brier |
|---|---:|---:|---:|---:|---:|---:|
| CFB | 5,733 | 72.74% → 72.74% | 0.177341 → 0.176462 | 0.528055 → 0.525200 | 1.794 → 1.428 pp | 7 |
| NHL | 5,248 | 61.34% → 61.34% | 0.231620 → 0.231367 | 0.655148 → 0.654604 | 0.919 → 0.470 pp | 4 |

CFB compares the original control with the earlier strength/nonlinear model's confidence, projected to preserve the original pick. NHL uses the earlier opportunity-weighted rate model in the same way. If the underlying model disagrees with the reference winner, the shadow expresses effectively50% confidence rather than a high-confidence pick in the opposite direction. When they agree, it retains the underlying probability. Original percentages are never overwritten.

## Evidence and limits

Both sports improve aggregate Brier and log loss, do not worsen fixed-bin ECE, preserve recent probability scores, meet the predeclared season-consistency rule, and retain every original selected winner. The complete JSON results include all confidence buckets with sample counts and Wilson intervals, per-season results, recent results, increased/decreased confidence counts and every gate decision.

CFB paired season/week block-bootstrap intervals for probability-score differences exclude zero in this development sample: Brier difference−.000879,95% interval[−.001665,−.000090]; logloss difference−.002855, interval[−.005430,−.000432]. NHL's intervals include zero: Brier difference−.000253, interval[−.000648,+.000136]; logloss difference−.000543, interval[−.001386,+.000274]. These intervals are descriptive, not adjusted for repeated research or adaptive selection, and do not prove a live improvement. ECE also depends on the fixed bins and sample composition.

CFB and NHL accuracy remain exactly72.737% and61.338% respectively on these historical cohorts. These figures are not current live-season hit rates. No current2026 label was used to select or fit the projection, and no winner-selection challenger is promoted by this package.

## Reproducibility

Sources are existing immutable compressed prediction archives in this repository. The evaluator verifies their Git blob SHA before use, joins identical game/season/outcome keys and rejects duplicate games or excluded seasons. Both evaluations were independently rerun byte-for-byte, and their core metrics match the earlier recorded run exactly. Six safety tests cover winner preservation, ties/extremes, invalid probabilities, outcome independence, CSV round trips and source validation. `source_manifest.json` and `validation.json` preserve hashes and checks.

The previous local experiment workspace was cleared before the final files were committed. This package was rebuilt from the registered protocol and existing GitHub archives, then rerun. It does not recreate missing prediction rows from remembered numbers or claim that unarchived structural/QB runs are fully reproduced. Those investigations remain separate and unfinished at the artifact/reproduction stage.

```sh
python -m unittest discover -s research/confidence_projection_20261028 -p 'test_projection.py'
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/confidence_projection_20261028/evaluate.py
```

Defaults write new results into runtime. Committed evaluations and original archives remain unchanged. The evaluator requires the original `confidence_audit.py` whose hash is recorded in the manifest.

## What remains before a live confidence change

`qualification_package.json` records the exact stage: development-qualified; no prospective bundle built; no shadow ledger started; production unchanged. The underlying model must be fit once under a separately fixed training specification, artifact hashes and dependencies frozen, and input provenance verified. Then capture reference and challenger on the SAME pregame inputs and timestamp into a separate append-only ledger. No backfilled predictions for started games, and no comparison between a refreshed challenger and an earlier official forecast presented as same-time evidence.

Review only after at least200 NEW paired settled CFB games or300 NHL games. The original first forecasts, model weights, grades and historical evaluations stay intact. Finding a better winner-selection model remains a separate open objective.

## Correction to the earlier CFB quarterback claim

The archived `research/cfb/results/qb_layer_experiment.json` reports0% coverage for every QB feature. Its loader converts `pos_team`—a team-name field—to numeric and drops the resulting NaNs; the source's numeric field is `pos_team_id`. That empty-join experiment did not establish that useful quarterback data fails to improve predictions. The old result and experiment are preserved. A new investigation needs validated IDs, date-safe joins and a nonempty coverage gate before any model comparison. The CFB dashboard's description is corrected accordingly; this does not add QB inputs to V1.
