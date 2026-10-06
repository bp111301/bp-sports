# CFB V2 Candidate A — Pre-2026 Validation Lock

Status: LOCKED FOR ONE-SHOT 2026 DIAGNOSTIC

This specification is fixed before Candidate A is evaluated on 2026 outcomes. Candidate A was selected only from 2015–2025 training/development data and 2018–2025 chronological out-of-fold evidence.

## Architecture

Candidate A keeps the CFB V1 dynamic-prior structure but adds two leakage-safe changes:

1. Travel distance is added to the context feature set for non-neutral games. Distance is great-circle miles from the away school's listed venue coordinates to the home school's listed venue coordinates. Neutral-site distance is missing because the matchup-line table does not provide the neutral venue coordinates in this feature block.
2. A shallow histogram-gradient-boosting signal is blended with the regularized logistic signal.

Both model families retain the frozen V1 internal weighting:
- 25% context model
- 75% dynamic-prior model
- dynamic prior transition k = 7

Final Candidate A probability:
- 65% logistic distance-enhanced ensemble
- 35% nonlinear distance-enhanced ensemble

Nonlinear model:
- HistGradientBoostingClassifier
- log loss
- learning rate 0.03
- 180 iterations
- max leaf nodes 7
- minimum samples per leaf 35
- L2 regularization 2.0
- early stopping disabled
- random state 42
- prior-season-only median imputation with missing indicators

## Development evidence

2018–2025 chronological OOF:
- 5,733 games
- 72.84% accuracy
- 0.176337 Brier
- 0.525072 log loss

2021–2025:
- 3,755 games
- 71.50% accuracy
- 0.182043 Brier
- 0.539224 log loss

For comparison, frozen V1 on 2021–2025:
- 71.53% accuracy
- 0.183011 Brier
- 0.542658 log loss

Candidate A improved Brier versus the otherwise-identical nonlinear architecture in each season from 2021 through 2025.

## Firewall

- No spread, total, moneyline, prediction-market price, or other market input enters winner selection.
- No retrospective realized-season QB identity fields.
- No retrospective transfer/portal reconstruction.
- No 2026 result was used to choose this architecture or its hyperparameters.

After the one-shot 2026 diagnostic is opened, Candidate A will not be modified. Any subsequent architecture change becomes Candidate B (or later) and cannot claim 2026 as untouched selection evidence.
