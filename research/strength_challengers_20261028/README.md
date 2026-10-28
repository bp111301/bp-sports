# CFB and NHL opponent-adjusted strength challengers — October 28, 2026

Four new recipes were tested after registering `PROTOCOL.md` on GitHub. **None met the predefined research eligibility rules. No model or live prediction was replaced.** This round implements a new opponent-adjusted scoring feature and a nonlinear learner, rather than only changing calibration or existing blend weights.

These are reused historical development results. The CFB accuracy figures below are not current live-season accuracy. NHL 2025–26 and both current live seasons were excluded from selection. No rejected recipe was retuned after viewing these results.

| Sport | Recipe | Games | Accuracy | Net correct vs control | Brier ↓ | Log loss ↓ | Decision |
|---|---|---:|---:|---:|---:|---:|---|
| CFB | control | 5,733 | 72.737% | +0 | 0.177341 | 0.528055 | control |
| CFB | strength_linear | 5,733 | 72.667% | -4 | 0.177415 | 0.528273 | reject |
| CFB | strength_nonlinear50 | 5,733 | 72.667% | -4 | 0.176440 | 0.525155 | reject |
| NHL | control | 5,248 | 61.338% | +0 | 0.231620 | 0.655148 | control |
| NHL | strength_linear | 5,248 | 61.585% | +13 | 0.231435 | 0.654777 | reject |
| NHL | strength_nonlinear50 | 5,248 | 61.223% | -6 | 0.231808 | 0.655514 | reject |

## What the evidence says

CFB: the nonlinear blend improved Brier and log loss, with better Brier in seven of eight development seasons, but selected four fewer winners overall and two fewer in the most recent three seasons. Better probability scores alone do not satisfy the registered goal of better winner selection. The strength linear blend also selected four fewer winners and worsened aggregate probability scores. Both fail.

NHL: strength linear selected 13 more winners (+0.2477 percentage points), improved both probability scores and Brier in three of four seasons, and improved recent accuracy. It still falls below the registered +0.3-point threshold. Its paired game-date block bootstrap accuracy-difference interval is **−0.113 to +0.613 percentage points**, which includes no improvement. It remains an unqualified research lead, not a deployable challenger. It combines added strength with removal of imputation indicators, so its gain cannot be attributed solely to the strength feature. Nonlinear50 selected six fewer winners and worsened both aggregate probability scores.

## Implementation and safeguards

`experiment.py` fits a ridge team-strength system from clipped historical score margins, adjusting for opponent and home field. Each target date uses only games between 2 and 365 calendar days earlier. A full-season label is never used to create an earlier game's strength. Original training folds remain expanding, strictly earlier seasons. The extra two-day lag avoids relying on final-status assumptions for same-day or previous-day games. NHL uses stable official team IDs; CFB uses source team IDs. Zero-strength priors cover unseen teams.

Both original controls reproduced the preceding experiment within 1e-12 for all reported metrics. Original source/feature helpers and all prior results remain unchanged. New historical rows include every candidate on identical game IDs; `strength_boundaries.json.gz` preserves each target date's maximum source date and training count. The source manifest hashes actual selected raw files, helpers, code, protocol and dependency versions. The earlier manifest records source URLs and extraction details.

Five new tests cover target/future/previous-day outcome mutation, same-day ordering, source expiry and date boundaries, bad identities, and neutral-site adjustment. Thirteen existing input-receipt/challenger safety tests also pass. Both complete experiment runs were repeated independently; probabilities, scores, decisions, and temporal boundaries reproduced exactly. `validation.json` records the checks.

This change adds only this research directory. Frozen weights/manifests, official prediction ledgers, grades, workflow schedules, dashboard, and all existing evaluations are untouched. No rejected bundles or shadow picks are emitted.

## Reproduce

From repository root, install the pinned dependencies in `research/challengers_20261028/requirements-research.txt`. Fetch historical sources using the two download helpers there. Inputs are shared with that experiment; use `source_manifest.json` to verify the exact raw file hashes. Downloaded source revisions can differ; the control parity guard will reject a changed control.

```sh
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python -m unittest discover -s research/strength_challengers_20261028 -p 'test_strength.py'
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/strength_challengers_20261028/experiment.py --sport cfb
OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 python research/strength_challengers_20261028/experiment.py --sport nhl
```

Defaults write into `runtime/strength_challengers_20261028/`, preserving committed results. Compressed results can be read with Python gzip or pandas.

## Next research boundary

These development seasons have now been reused several times; further gains on them carry increasing selection bias. Do not lower eligibility thresholds or repeatedly search the live losing games. A larger feature set is a research direction, not an established solution: CFB needs timestamped QB/availability data and an audit of efficiency/prior coverage; NHL needs reliably archived pregame goalie confirmation and richer shot-quality data, with full coverage and timestamp checks. Existing goalie shadow evidence is small and selected, so do not advertise it as a proven full-slate upgrade.

Before proposing another data-driven challenger, demonstrate a point-in-time source, sufficient historical coverage, and a reproducible join that excludes postgame information. Register the next finite experiment first. Any eventual shadow must freeze a new specification, capture future inputs, and earn at least 200 new paired CFB or 300 NHL settled games before a promotion review. No claim here establishes a betting edge or a future 75–80% full-slate hit rate.
