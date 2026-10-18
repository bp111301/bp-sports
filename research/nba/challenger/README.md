# NBA player-availability challenger

This is isolated development research. The public NBA V1 bundle, prospective
predictions, reserved 2025–26 historical evaluation and other sports are unchanged.
See [REPORT.md](REPORT.md) for the completed comparison and frozen shadow decision.

The experiment was committed in `EXPERIMENT_LOCK.json` before candidate outcomes
were evaluated. Season numbers are ending years: 2023 means 2022–23. Only regular
season games accepted by the original V1 data checks are eligible. No preseason
games or season-ending-2026 inputs are used.

## Comparison

The fixed baseline logit receives a separately fitted availability residual. Its
coefficient remains one. Three locked additions are compared with original V1 and
an intercept-only coverage control:

* Separate Out, Doubtful, Questionable and Probable player counts.
* Separate prior-minute loads for those statuses, plus prior points for Out players.
* Both groups of features together.

Player importance is the mean of up to 20 earlier eligible appearances. Names and
IDs are learned only from earlier Eastern calendar dates; current-game box scores
cannot define availability or importance. This simple proxy is not a causal
estimate of player value. Unknown identities contribute no invented weight.

Official injury reports must pass both their embedded publication timestamp and
PDF creation timestamp checks. The cutoff is the earlier of 60 minutes before
tipoff and 6 PM Eastern on the game date. Legacy filename hours do not equal exact
publication times. The first requested filename hour is one hour before the
floored cutoff; at most two earlier filename hours may replace an unavailable or
invalid document. A valid report with a team not yet submitted remains unknown;
the code does not search for a preferred set of player statuses.

If either team is unknown, V1's probability is copied exactly. Unknown reports are
never treated as healthy teams. Evaluation stops without candidate metrics unless
at least 70% of games have both teams explicitly submitted in each evaluation
season. All full-cohort candidates use the same games, with a secondary comparison
restricted to games where both teams are known.

Residuals fit only earlier-season genuine out-of-fold V1 probabilities, starting
in 2021. Evaluation folds are 2023, 2024 and 2025. Scaling uses training rows only;
the regularization is fixed. The original 8,288-game V1 development predictions
must replay within 1e-12 before any candidate comparison runs.

The locked shortlist checks require a pooled Brier improvement of at least
0.0005, improved log loss, no loss in correct picks, Brier gains in at least two
seasons including both latest seasons, and gains over the coverage-only control.
Passing is a development shortlist, not release approval. These development
seasons were previously inspected; the bootstrap is descriptive, not independent
confirmation. The reserved 2025–26 evaluation is not reopened for selection.

## Reproduce

From a complete checkout of this branch, install Python 3.12, Poppler's
`pdftotext`, and `requirements.txt`, then run:

```sh
python research/nba/challenger/fetch_inputs.py
python research/nba/challenger/prepare.py
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/nba/challenger/study.py
python -m pytest research/nba/test_safety.py research/nba/challenger/test_availability.py -q
```

Use `python research/nba/challenger/prepare.py --offline` to rebuild an audit from
cached documents without attempting any downloads. Incomplete coverage remains
unknown and stops candidate evaluation.

Downloads and intermediate PDFs stay in `runtime/nba/`; team Parquet files stay
at their existing V1 source paths. Source hashes must match the original frozen
manifest and `PLAYER_SOURCES.json`. The helper never fetches 2026 inputs.
`prepare.py` performs source checks without fitting a candidate. Download caches
record missing documents as well as accepted ones. Delete an unavailable JSON
receipt only when deliberately retrying a transient download error, then rebuild
the audit; never substitute a later report into an earlier cutoff.

`results/comparison.json` is the machine-readable decision. Compressed records
preserve report URL/hash/timestamps, selected availability contexts and paired
predictions when the source gate passes. Archived PDF hashes must be checked if
rerunning later: source files can be revised at the original URL. Reports are
afternoon snapshots and do not guarantee final active lineups. Historical
shortlisting does not automatically promote a model. The frozen prospective collector and
protocol are in `shadow/`; its weights live in `model/nba/availability-shadow/`
and its append-only data live in `data/nba/availability-shadow/`. The existing NBA
workflow runs that collector after V1 on the same scheduled cadence. It never
rewrites the public V1 snapshots.
