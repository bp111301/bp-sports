# Same-input confidence shadow trial

The same-input shadow trial is active and verified in GitHub Actions. Initial capture saved59 CFB and11 NHL paired pregame forecasts; scheduled collection has since increased NHL to14. At the2026-10-29T13:22:36Z verification cutoff, all73 records are pending. Live counts and grading results are in data/confidence_shadow_20261029/summary.json.

The corrected startup and seven subsequent scheduled runs succeeded. Latest verified shadow run:40881217946; all23 focused checks passed, original reference replay passed, both live source checks passed, and the job preserved the research records. Production run40878047900 also passed all108 tests. Collection and official-final settlement are scheduled hourly; GitHub may delay execution. No live shadow final had settled by this cutoff, so the settlement safeguards and scheduled path are verified, not a completed real-world shadow grade.

Both probabilities use the same timestamped input snapshot. The reference is freshly reconstructed for this paired comparison; it is not the earlier official first forecast. Original official ledgers and live displayed confidence remain unchanged. Every challenger pick matches its reference pick.

## Model and input identity

Frozen references run under their original sklearn1.9.1 environment; confidence challengers run under their pinned sklearn1.8.0 environment. Artifact, producer-code, feature-helper and dependency hashes are checked. All58 existing CFB input receipts replayed within2e-16 locally and in Actions. No reference is refitted.

The exact25 historical input files are retained in frozen_history.tar.gz, checked against the already-frozen bundle source hashes. This avoids regenerating CSVs with a different byte representation or silently consuming revised remote history. Only runtime input caches may be restored. No model, original forecast, historical evaluation or grade can be restored or overwritten by this path.

Fresh CFB states are verified using exact ESPN event summaries because the schedule export has blank status fields. Missing newly final NHL team-stat rows can use equivalent official game-center counts after strict identity/score/count checks. Five actual completed games (ten team rows) verify equivalence; see SOURCE_ADAPTER.md and fixtures/. Both models consume the same supplemented snapshot.

## Capture and grading

Forecast JSONL and settlement JSONL are append-only and digest-checked. Compressed, content-addressed snapshots retain raw model inputs; receipts retain both feature vectors, source/model/code hashes and exact capture/start times. At least ten minutes must remain to publish a new pregame receipt. Each sport preserves its valid records even if the other source fails. Operational failures remain explicit.

Only verified official final results can create a separate settlement event. Changed identities/start times, nonfinal scores and conflicting grades require review. A settlement issue cannot discard valid new pregame captures. Replays cannot overwrite an existing probability or grade. Empty horizons and duplicate-free reruns are explicit health results.

Minimum review samples remain200 NEW paired settled CFB games or300 NHL games; reaching a count alone does not authorize promotion. Historical development gains and the act of collecting predictions do not establish better live confidence or accuracy.

## Checks

```sh
python -m pytest --import-mode=importlib -q research/confidence_shadow_20261029 research/confidence_projection_20261028/test_projection.py research/confidence_projection_20261028/test_final_bundle.py
python research/confidence_shadow_20261029/validate_reference.py --reference-python PATH_TO_PRODUCER_ENV_PYTHON
python research/confidence_shadow_20261029/collect.py --reference-python PATH_TO_PRODUCER_ENV_PYTHON --nhl-root PATH_TO_PINNED_NHL_REFERENCE_CHECKOUT
```

Read data/confidence_shadow_20261029/summary.json for sample sizes and, after settlements, paired probability metrics, confidence buckets and Wilson intervals. health.json distinguishes actual failures, coverage and new records. GitHub schedules may be delayed; the horizon and pregame validation remain enforced on actual execution.

## Integrity verification at rollout completion

All73 event digests, five compressed input-snapshot hashes and pregame timestamps were independently verified. All reference winners are preserved. The original first70 forecast bytes remain an exact prefix of the current ledger, with zero duplicate keys. Existing frozen model weights and pre-existing research-result files match their pre-rollout Git blob hashes. See validation.json for the verification cutoff and run IDs.
