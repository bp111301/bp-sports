# NHL V2 bounded model-structure protocol — 2026-10-06

V1 is immutable and research-only after failing its release gate. CFB V1 and
Candidate B are untouched. This protocol records choices before V2 results.

Use the existing 18-feature team-stat leader to isolate the effect of model
structure. Audit join coverage, duplicates and feature distributions first.
Development is 2021–22 through 2024–25, with only earlier seasons used for each
fold. Do not load 2025–26 labels into this tournament or compare alternatives
against that failed season. That season is no longer fresh validation evidence.

Exactly five candidates, no hyperparameter grid:
- Original V1 logistic reference, expanding training, C=.5.
- Same logistic with the three most recent completed training seasons.
- Same logistic with two-season half-life sample weights, normalized to mean 1.
- Small histogram boosted tree: 150 iterations, .05 learning rate, max depth 3,
  7 leaves, 100 minimum samples per leaf, L2=10, seed 17, no random early-stopping
  validation split. Expanding training and training-only preprocessing.
- Fixed 75% original logistic / 25% small tree blend; no weight tuning.

Choose a research candidate only if aggregate Brier and log loss improve,
accuracy is preserved and season Brier improves in at least three of four
seasons. Otherwise retain the V1 reference as the comparator, with no release.
All results remain exploratory because development was previously reused.
Persist all OOF predictions and training boundaries. A new candidate requires
predictions timestamped before later games for prospective validation; it cannot
claim an independent historical test by reusing 2025–26 after observing failure.

A separate read-only source audit may load 2025–26 into an audit-only folder to
check team-game joins, units and missingness. It never fits a model, selects a
candidate or scores alternative predictions on that season. A join mismatch or
>10 percentage-point increase in feature missingness halts the tournament for
investigation. The actual tournament loader rejects any season beyond 2024–25.
