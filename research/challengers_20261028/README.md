# October 28 challenger development: completed bounded experiment

**Decision: reject all four proposed variants under the registered research criteria. No new candidate is promoted or activated.** Existing frozen CFB/NHL models and collections continue unchanged.

The protocol was committed before this experiment's outcomes were examined. The complete results, per-season boundaries, input diagnostics, source receipts and out-of-fold predictions are preserved here. This is reused historical development, not a new independent historical holdout or evidence of better live accuracy.

## CFB — 5,733 held-out-season games, 2018–2025

| Recipe | Accuracy | Brier ↓ | Log loss ↓ | Seasons with better Brier | Decision |
|---|---:|---:|---:|---:|---|
| Original-recipe control | 72.7368% | 0.177341 | 0.528055 | — | Comparator |
| Prior-OOF positive-slope calibration | 72.7368% | 0.177544 | 0.529108 | 4/8 | Reject |
| Recent-three-season 50/50 ensemble | 72.8066% | 0.178715 | 0.533040 | 1/8 | Reject |

The calibration changed no winner choices, as intended, but slightly worsened probability quality. Reducing mean confidence is not by itself an improvement. The winner variant gained four correct picks across 5,733 games (0.07 percentage point), below the pre-set 0.5-point research threshold, while worsening Brier and log loss. Its 2023–25 accuracy improved slightly, but that did not rescue the failed aggregate/stability checks. No alternative calibration window, mixture weight, or training window was selected after seeing these results.

Each target season trains on earlier seasons only. Calibration uses only control out-of-fold predictions from at most three earlier seasons; target-season outcomes never enter its fit. The historical loader rejects live 2026 labels. Market/QB retrospective fields are excluded from the existing approved feature schema.

The regenerated control matches the archived tournament's winner accuracy exactly. Its Brier differs by about 0.0000034 and log loss by about 0.0000113 from that archive. Inputs/dependencies are newly regenerated, so the original evaluation is preserved and all variants are compared against the same regenerated control. No old model binary was refitted.

## NHL — 5,248 held-out-season games, 2021–22 through 2024–25

| Recipe | Accuracy | Brier ↓ | Log loss ↓ | Seasons with better Brier | Decision |
|---|---:|---:|---:|---:|---|
| Original-recipe control | 61.3377% | 0.231620 | 0.655148 | — | Comparator |
| Median imputation without missingness indicators | 61.3948% | 0.231576 | 0.655075 | 1/4 | Reject |
| No indicators + sparse-input baseline fallback | 61.4139% | 0.231536 | 0.654989 | 2/4 | Reject |

Average gains are tiny and neither variant meets the registered three-of-four-season consistency rule. The guarded variant gains four correct picks, but this is not evidence of a reliable live upgrade. The existing historical production release gate remains unmet and unchanged.

The selection loader opens only 2018–19 through 2024–25 source files. Neither the observed-failure 2025–26 season nor the live 2026–27 season enters selection. The downloader retained 2025–26 reports for potential final-fitting provenance, but no eligible bundle was frozen and those labels were not opened by the selection loader.

Official team-game reports are paired by game and team identity. Raw regulation/OT goals exclude the shootout award, so the adapter adds one goal only for the official shootout winner when the raw scores tie. The rolling team-stat features keep the unadjusted team reports. This adapter reproduces the archived NHL reference's development accuracy exactly and Brier/log loss within 1e-12, supporting source/feature parity. The selected historical game set has complete team-game joins and no duplicate game IDs.

## Operational improvement: separate CFB input receipts

`capture_cfb_inputs.py` is an observer run immediately after the unchanged V1 slate builder. It does not fit a model, change a weight, create a pick, grade a game, or rewrite the official forecast ledger.

For each fresh current-slate forecast it:

- verifies the frozen bundle against its existing manifest;
- stores hashes of the raw matchup source, schedule and current-slate file;
- retains exact context/prior feature vectors, component probabilities and ensemble weights;
- replays the frozen calculation and requires agreement with the current saved probability within 1e-12;
- records a timestamped, integrity-hashed observation in a separate append-only log;
- explicitly labels a later refresh as **not the inputs to the original first forecast**;
- reports FBS-vs-FBS and FBS-vs-FCS source/forecast coverage separately;
- rejects stale or late input captures and verifies the official ledger, current predictions and binary bundle remain byte-unchanged by observation.

Old October capture-time features are not recovered. First-capture receipts become available only for genuinely new official first snapshots after this observer is deployed. Existing games receive clearly labeled refresh observations. No completed game receives a retroactive forecast.

Output paths are new: `data/cfb/input_receipts/observations.jsonl` and `data/cfb/input_receipts/coverage.json`. The existing CFB workflow retains its frozen model, V1 builder, Candidate B builder, settling and collection schedule; it adds observer safety checks and the separate receipt step.

## Validation and provenance

- 13 focused checks cover season boundaries, target-season exclusion, calibration symmetry/winner preservation, indicator-free preprocessing, isolated power-play missingness, shifted rolling features, shootout labels, input replay, append-only/idempotent receipts, stale captures and coverage omissions.
- An end-to-end local rehearsal used the existing checksum-verified frozen CFB bundle and the unchanged builder, captured 58 fresh local observations and found full 58-game FBS-vs-FBS source coverage. These local rehearsal forecasts/receipts are **not** published as official historical captures. The local sklearn version differed from the frozen binary's producer; production validation must use the existing workflow's pinned frozen dependencies.
- The old frozen CFB builder source and NHL frozen sources/manifests are untouched. The NHL feature helpers here are isolated research copies from `nhl-v1-research` commit `1b58a6c802c525f2659b38a16a71cc6970365d0e`, not edits to the frozen pipeline. Source-code hashes and package versions are recorded.
- The source inventory contains source-response hashes, URL, year and byte/row counts. Re-downloads can change; matching historical results requires the same source content and package versions. No original historical evaluation files were overwritten.
- Compressed out-of-fold CSVs retain every candidate probability, outcome, target season and training boundary. New `development_results.json` files contain eligibility decisions and per-season metrics. No trained challenger bundle was created because every candidate failed research eligibility.

## Reproduce without overwriting saved evaluations

Use a separate environment with `requirements-research.txt`. All default training outputs go into `runtime/challengers_20261028/`, not the saved results folder.

```bash
python research/challengers_20261028/download_history.py
python research/challengers_20261028/download_nhl_history.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/challengers_20261028/cfb.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/challengers_20261028/nhl.py
python -m unittest discover -s research/challengers_20261028 -p 'test_safety.py'
```

## Next evidence-driven step

Use the newly captured inputs to investigate whether major-conference and away-pick CFB weaknesses involve source quality, feature availability, or model specification. Do not infer that from losing picks alone. A further modeling experiment needs a new pre-registered hypothesis; do not broaden this failed tournament until a lucky variant appears. Continue the existing frozen prospective collections and compare any future accepted candidate only on games captured after its separate freeze.
