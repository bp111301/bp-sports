# NBA V1 final comparison and excluded-season evaluation

Register before seeing results. No further development variants in this stage.
Same audited 8,288 games/folds, original 14 features and baseline defaults.
Nine fixed entries: baseline_control; tree7; tree15; blend7; blend15;
linear_platt; linear_temperature; tree7_platt; tree15_platt.

Trees: HistGradientBoostingClassifier, log loss, learning_rate=.05, max_iter=150,
max_leaf_nodes=7 or15, min_samples_leaf=60, l2_regularization=5, early_stopping=False,
random_state=42. Blends: equal baseline logistic/tree home-win probabilities.
Platt: logistic regression C=1, raw clipped probability logit as sole predictor.
Temperature: choose T from [.8,.9,1,1.1,1.25] minimizing prior OOF log loss,
tie toward1. Calibration learns only expanding-season OOF forecasts from earlier
seasons: first calibration OOF is 2017–18, trained on2015–16 and2016–17. Each
2019–2025 ending-year evaluation is calibrated only with earlier OOF labels.
Baseline control must reproduce stored OOF probabilities within1e-12.

Apply the existing tournament eligibility rule: Brier gain>=.0005, lower log loss,
no fewer correct picks, Brier better in>=5/7seasons and both2024/2025. Rank eligible
by Brier/logloss/name; otherwise retainbaseline. Report all entries. Multiple-use
development results do not constitute independent validation.

Freeze chosen configuration and refit on2016–2025endingyears only. For calibrated
winner, freeze calibration fit using earlier-model OOF predictions2018–2025.
Save bundle, SHA256, input/config/code/runtime hashes, training dates and candidate.
Commit frozen artifact before fetching2026. The evaluation process refuses to
download/evaluate without this committed artifact and checks identity on load.
Never refit from2026 or choose an alternate based on2026results.

Evaluate2025–26(endingyear2026)once. Start teamstate/Elo fromdevelopment history;
weights/scaler/calibration are fixed throughout. Shifted features may use earlier
completed2025–26games exactly as in live operation. Score only selectedcandidate
and preregisteredElo/home-frequency controls. Release gate:>=1000validregular-season
games, >=99%completedeligiblegamecoverage, accuracy>=60%, lowerBrier/logloss than
bothcontrols. Report season/month/calibration and source exclusions. Gate failure
keeps candidate research-only; gatepass marks eligible for prospective collection,
not automatically production-promoted. Existing NFL/CFB/NHL/UI stay unchanged.
Preserve the first evaluation forever; repeat invocation verifies hashes and exits.
