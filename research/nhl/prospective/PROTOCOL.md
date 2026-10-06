# NHL V2 experimental prospective watchlist — 2026-10-06

This does not promote any candidate or reverse the V1 failed release decision.
No V1 model or CFB artifact is modified. The purpose is collecting genuinely new
pregame evidence for two fixed, unpromoted hypotheses and a reference control.

Development evidence: recency weighting reached 61.70%, .231583 Brier and .655071
log loss, but improved Brier in only two seasons. The fixed regulation blend
reached 61.32%, .231470 and .654772, improving Brier in three seasons but losing
one correct pick relative to V1 across 5,248 games. Both failed the existing gate.
They are watched for research, not declared validated or recommended for betting.

Train fixed weights on completed 2018–19 through 2025–26 games. Using the failed
season as training data for future predictions is allowed; it is not re-evaluated
as independent evidence. Lock the model/spec/code/dependency identities before
first 2026–27 prediction. No weight refitting during this experiment. Reference
control is the same original 18-feature logistic procedure trained on that same
expanded history, kept separate from the immutable V1 bundle.

Record only games whose scheduled start is strictly later than prediction creation.
Save each candidate/game's first prediction permanently. Include model/spec hashes,
creation time and source-snapshot time. Settle only recorded, valid pregame rows
after NHL final results. Preserve pending rows, mark timing violations, and never
backfill past games. Future team-stat placeholders contain no observed statistic;
lagged features use completed games only. Forecast horizon is 36 hours.

Current-season completed games update feature state only. They never retrain the
fixed weights. Do not choose a winner from small live samples. Publish descriptive
metrics only; no automatic promotion, site activation or betting recommendations.
The GitHub workflow refreshes this research ledger daily and can be run manually.
