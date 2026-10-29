# Winner-preserving confidence challengers — 2026-10-28 Central

Registered before computing projected results. This is a different objective from a winner-selection upgrade: original selections must remain EXACTLY unchanged. The earlier joint accuracy-and-confidence failures remain failed. Do not relabel them as eligible winner challengers or lower their thresholds. User separately prioritizes probability confidence; evaluate a separate confidence-only layer with an explicit accuracy-invariance requirement.

This protocol is adaptively motivated by inspected historical development results: CFB strength_nonlinear50 improved Brier/logloss in7/8 seasons but reduced accuracy; NHL pooled_rates improved Brier/logloss in4/4 seasons but selected one fewer winner. Prior results and adaptive choice are disclosed. Development data are reused, no new independent holdout. Future paired validation required.

Exactly one projection per sport, no fitting or hyperparameter search:
- CFB underlying probability: archived strength_challengers_20261028 strength_nonlinear50; original reference control on same2018–2025 games.
- NHL underlying probability: archived feature_challengers_20261028 pooled_rates; original reference control on same2021–22 through2024–25 games.

For original reference p>=.5, confidence-shadow home probability q=max(new_probability,.5). For original p<.5, keep new_probability when it is below.5; when it crosses to>=.5, set q=.499999. Thus a disagreement becomes an effectively50% confidence estimate while retaining the original selected side. Never turn a disagreement into a high-confidence selection of the original winner. Do not change any original percentage or forecast. No source row, target-year label or live2026 outcome participates in the projection.

Confidence-only research eligibility: exact original winner selections on every evaluated row; strictly better aggregate Brier AND logloss; fixed-bin ECE (50/60/70/80/90/100) no worse; Brier improved in>=5/8 CFB or>=3/4 NHL seasons; recent2023–2025 CFB /2023–24–2024–25 NHL Brier AND logloss no worse. Accuracy must be identical by construction, and that is explicitly not an accuracy upgrade. Report each check, support/Wilson intervals, number of disagreements projected to50%, confidence increase/decrease counts, and paired season/week or game-date block-bootstrap Brier/logloss difference intervals2000 draws seed20261028. Intervals are not adjusted for adaptive selection and multiple comparisons.

Qualification only permits a separately frozen PROSPECTIVE confidence shadow with exact immutable reference and challenger probabilities, same-time pregame input provenance and >=200 NEW paired settled CFB games or>=300 NHL games before a review. No retrospective forecasts or production substitution. If the confidence-only gate fails, reject without retuning. A confidence challenger is not a claim of a better winner-selection model or improved live accuracy.
