# CFB near-qualifier failure audit — 2026-10-29

Investigate the existing, unpromoted cat_d5_l2_5_halfblend research candidate against its original control. Its overall and per-season summary results have already been inspected: +30 wins/5,733 games, better aggregate Brier/logloss/ECE and recent metrics; Brier improves4/8 seasons rather than the required5. These are reused historical development results, not a fresh holdout.

## Fixed descriptive audit before subgroup inspection
Use the existing immutable2018–2025 structural OOF prediction archive, joined one-to-one to the same2015–2025 historical matchup files. Verify archived Git blob SHA and original source SHA256 values; reject duplicate or mismatched game IDs/seasons/labels, nonfinite probabilities and incomplete candidate cohorts. Never reconstruct original historical forecasts from refreshed live data.

Report all seasons and the following fixed disjoint groupings: regular-season weeks1–4,5–8,9+ and separately postseason; original-control confidence50–60/60–70/70–80/80–90/90–100%; control/candidate pick agreement; both-correct/both-wrong/fixed-original-error/broke-original-correct classifications; weighted-talent-difference present vs missing; number of missing original-context features0/1/2+. Report early/mid/late crossed with talent availability, and season crossed with pick agreement and talent availability. Report team involvement only where>=75 evaluation games; these groups overlap and may not be summed as independent cohorts. Keep every group regardless of result. Retain the20 largest adverse game-level Brier changes for diagnosis only, never exclusions.

For each group, retain exact support, wins, accuracy, Brier and logloss for both models, signed paired differences and counts of fixed/broken picks. Do not call subgroup discovery significance or pick a favorable cohort as a deployment rule. Quantify how much of each failed season's net loss comes from unchanged picks versus changed picks. Team and game outcomes are explanatory diagnostics, not additional features fed to a model.

## Live feature-quality audit
Separately inspect the already captured2026 CFB shadow input vectors and their original timestamped input snapshots. Compare missingness, finiteness, range and median against historical inputs matched by source week and season type. No2026 target outcome is read, scored, trained on, or used for challenger selection. These receipts are fresh shadow captures, not the unavailable first-input receipts of older official forecasts; do not pretend to diagnose the exact original175 live decisions.

## Next experiment boundary
Only after this audit, register a small fixed experiment addressing a specific observed failure pattern, before fitting any new recipe. Use prior-season OOF training only if probabilities are combined/calibrated; preserve a common cohort, the existing accuracy/probability/calibration/season-consistency/recent gates and all failures. Disclose adaptive historical reuse. No production promotion, no original weight/evaluation/forecast/grade change, and no relaxation of a gate to manufacture a winner.
