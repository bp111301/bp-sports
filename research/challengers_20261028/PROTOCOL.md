# Bounded challenger development — October 28, 2026
Status: research only. Registered before this experiment's historical results. No production promotion, alteration of existing bundles, code-hash manifests, first forecasts or historical evaluations.

## CFB — exactly two variants versus the original recipe
Data: sportsdataverse matchup-line 2015–2025 only. Reject 2026 or later in the training/evaluation loader. Development folds 2018–2025, earlier seasons only for every target fold. Previously reused development is not a fresh holdout.
Control: original 25% expanding context / 75% expanding k=7 prior model, same feature schema and C=.5.
1. Calibration: positive logit slope, no intercept, bounded [.25,2], fit by log loss on control out-of-fold predictions from at most three prior seasons only. Target-season labels never enter its calibrator. It cannot change selected winners.
2. Winner selection: three most recent earlier seasons, 50% context / 50% k=7 prior ensemble, same C=.5 and feature schema. No tuning grid or live-2026 optimization.
Research eligibility: calibration lowers aggregate Brier and log loss, changes no winners and improves Brier in at least 5/8 seasons. Winner variant improves aggregate accuracy by at least .5 percentage point, preserves or improves Brier/log loss and 2023–2025 accuracy, and improves Brier in at least 5/8 seasons. Failure remains a reported rejection; no picking a different rule after seeing the result.

## NHL — exactly two missingness variants versus the original recipe
Development folds 2021–22 through 2024–25; each trains only on earlier seasons. Reject 2025–26 and 2026–27 from selection. The observed-failure 2025–26 season may be used only for later final fitting, never as alternative evaluation or tuning.
Control: original 18-feature logistic C=.5 with training-only median imputation, indicators and scaling.
1. Same 18 features and C=.5, median imputation and scaling without learned missingness indicators.
2. Same no-indicator model with an explicit feature-availability guard: when any advanced team difference is missing/nonfinite, use a separately trained no-indicator 10-feature team baseline. This handles sparse season-start inputs without injecting a learned missingness signal.
Research eligibility: aggregate Brier and log loss improve, accuracy is preserved, Brier improves in at least 3/4 seasons. If both pass, choose lower Brier then log loss; if neither passes, promote neither to shadow collection by this protocol. Existing historical production-release gates still apply.

## New prospective safeguards
Any eligible bundle gets a new identity, package/source/spec hashes, explicit freeze/capture start and independent append-only ledgers. All inputs and component probabilities are retained separately. No retroactive captures or reuse of inspected October games as a new candidate's fresh test. First checkpoints remain >=200 new paired CFB finals / >=300 new paired NHL finals; these are review checkpoints, not automatic promotion.
Operational input-receipt collection and source coverage reporting may proceed even if every candidate fails historical research eligibility. No claim of improved live accuracy until new prospective evidence exists.
