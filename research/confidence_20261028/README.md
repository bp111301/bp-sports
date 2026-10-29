# Confidence reliability work — October 28, 2026

The new live confidence display diagnoses probability reliability; it does not claim that either frozen model became more accurate. Three new calibration mappings were tested against registered rules and all failed. Existing saved probabilities/picks stay unchanged. Protocol was committed before results.

## Live evidence at the audit cutoff

CFB: 175 settled first forecasts, 111–64, 63.43% accuracy versus 70.38% mean model confidence (+6.95 percentage-point gap). The 80–90% bucket is 21–12 (63.64%) at 84.02% mean confidence; it is only 33 games. The 90%+ bucket is 10–3 (13 games). Samples do not establish a corrected probability for a particular upcoming game.

NHL reference: 155 settled first forecasts, 91–64, 58.71% accuracy versus 59.33% mean confidence. Overall confidence is comparatively close, but only two 80–90% games and one 90%+ game exist. Recency and regulation models are presented separately; their repeated outcomes are not counted as additional independent games.

`live_audit.json` preserves the exact cutoff, source hashes and descriptive summaries. Every bucket includes count, mean confidence, actual win rate and a 95% Wilson interval. These intervals assume independent games; correlated game days and repeated comparisons can increase uncertainty. Fewer than 100 games is explicitly limited support. There is no statistically established per-game correction here.

## Finite historical confidence experiment

One recipe uses fixed-bin, pseudo-count-regularized isotonic regression, fit only to up to three strictly earlier seasons of original-control OOF predictions. CFB additionally tests conference-group mappings (historical P4 vs P4 / other). NHL tests pooled only. No selected winner changes. The first available development season is warmup, so counts below differ from earlier full backtests. No live labels or NHL 2025–26 labels enter training or selection.

| Sport | Mapping | Games | Accuracy | Mean confidence | Brier ↓ | Log loss ↓ | ECE ↓ |
|---|---|---:|---:|---:|---:|---:|---:|
| CFB | control | 4,999 | 72.29% | 74.46% | 0.179442 | 0.533684 | 0.0217 |
| CFB | group_isotonic | 4,999 | 72.29% | 73.49% | 0.179665 | 0.534714 | 0.0149 |
| CFB | pooled_isotonic | 4,999 | 72.29% | 73.32% | 0.179523 | 0.534372 | 0.0136 |
| NHL | control | 3,936 | 60.24% | 61.33% | 0.233072 | 0.657892 | 0.0138 |
| NHL | pooled_isotonic | 3,936 | 60.24% | 62.99% | 0.234303 | 0.660434 | 0.0300 |

CFB mappings reduce fixed-bin calibration error and the average overconfidence gap, but both worsen Brier and log loss overall and recently. The NHL mapping worsens Brier, log loss and calibration error. All are rejected under predeclared criteria. No adjustment was made after viewing the results. These are reused development seasons, not independent holdouts; further searching on them adds selection bias.

## Dashboard change

`confidence_audit.py` validates first forecasts, timing, outcomes, grades and model/game identity. `confidence_ui.py` displays descriptive confidence evidence in the CFB and NHL detailed boards and Model Record tabs. NHL has a separate candidate selector. Original Overview already had basic confidence buckets; this work expands the detailed boards with uncertainty ranges, support labels, validation and candidate-specific summaries. Data refreshes with the existing feed/cache; no new polling workflow is needed.

CFB raw percentages are explicitly labeled unvalidated, and CFB confidence-based STRONG/SOLID badges become numeric model bands. NFL badges are unchanged. Source/model percentages, ordering, selected winners and grading are unchanged. Original frozen artifacts, forecasts, evaluations and schedules are untouched. No calibrated forecast is presented as live.

## Reproduce

Use pinned research requirements from `research/challengers_20261028/requirements-research.txt` and the already committed original-control OOF archives. CFB grouping uses the original guarded 2015–2025 matchup source with hashes in the prior source manifest. From repository root:

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/confidence_20261028/experiment.py
python -m unittest discover -s research/confidence_20261028 -p 'test_calibration.py'
python -m pytest -q tests/test_confidence_audit.py tests/test_confidence_ui.py
```

Defaults write into runtime rather than committed historical outputs. Research tests read generated runtime results; run the experiment first. Full runs repeated with exact result reproduction. See `validation.json` for final test counts and code/source hashes.

## Accuracy work remains open

The previous opponent-strength/nonlinear challengers did not earn promotion. These confidence tests also do not improve winner selection. The next accuracy work must establish point-in-time availability and coverage of richer inputs before another bounded experiment: CFB player/QB availability and efficiency/prior coverage, NHL pregame goalie confirmation and shot-quality data. Existing goalie layers and source helpers must be audited before adding duplicate layers. No historical realized starter or postgame revised availability can stand in for pregame evidence. A future candidate requires a new frozen shadow and fresh paired results, not a relabeling of these tests.
