# Research decisions following the October 28, 2026 review

Status: proposed research work, not new trained models, release authorization, or production changes. All current frozen models, first forecasts, completed settlements, and historical evaluations remain intact.

## CFB priorities

1. Persist separate append-only input receipts for future captures: source content hashes, source time, complete as-of feature vectors, missingness, frozen bundle identity, and component probabilities. Preserve the official first-snapshot ledger and its semantics. Historical capture-time inputs cannot be reconstructed from today's source.
2. Investigate major-conference and away-pick weaknesses using historical pre-2026 walk-forward data. Audit team joins, units, missingness, seasonal priors and home/away treatment before deciding whether any feature or weighting change is justified. These are hypotheses, not diagnosed causes.
3. Develop two separate research hypotheses: a probability calibrator and a winner-selection challenger. Fit/calibrate only with pre-2026 held-out-season predictions; label reused development data honestly. The October live results have now been inspected and are diagnosis/development evidence, not a fresh holdout for selecting a new model. Probability shrinkage alone generally will not improve winner accuracy.
4. Add explicit coverage reporting for the three observed FBS-vs-FCS source omissions. Do not synthesize missing inputs or retrospectively add forecasts for completed games. Future expansion requires an eligibility rule and separately validated feature coverage.

## NHL priorities

1. Keep the reference, recency, regulation blend and goalie models in their existing research status. Continue their frozen, paired collections without changing probabilities or inclusion rules.
2. Develop one separately versioned missing-feature treatment candidate using pre-2026 walk-forward development data. Test removal or conservative treatment of unstable missingness indicators and an explicit early-season feature-availability rule. A diagnostic counterfactual is not an eligible forecast; do not cap or patch the frozen reference probabilities.
3. Persist explicit feature-availability diagnostics for future candidate inputs and test isolated missing power-play inputs, season-start sparse data, units, and home/away symmetry. Validate historical extraction and current extraction use the same semantics.
4. Preserve the goalie experiment's same-game, same-capture-time team control. Report eligibility coverage alongside paired results; do not compare its selected sample directly with the full watchlist.

## Proposed future acceptance protocol

These are additional research safeguards, not a replacement for existing historical release gates:

- Before collection starts, commit a fixed candidate specification, training cutoff, bundle hash, candidate count, eligibility rule, metric priorities, and collection start. No changing the rule after looking at its future results.
- Start a new prospective evaluation after the new candidate is frozen. Do not merge these inspected October games into that candidate's untouched test.
- First planned evaluation after at least 200 new CFB paired finals or 300 new NHL paired finals. These are review checkpoints, not claims of sufficient statistical power or promises of promotion.
- Show accuracy, Brier and log loss on identical eligible games, paired day-block uncertainty, winner disagreements, coverage, missingness and calibration. Date-block intervals still do not account for every repeated-team dependency; very few CFB weeks warrant caution.
- Proposed material probability-quality target: at least 0.005 lower Brier, with no log-loss deterioration and no material accuracy regression. A winner-selection upgrade additionally needs a credible accuracy gain. If confidence intervals still span no improvement, continue testing or reject; do not promote on a point estimate alone.
- Meet the existing historical release gates and pass leakage, identity, pregame-timing and immutable-record checks before any production promotion. The NHL historical gate is currently unmet.
- Do not optimize a confidence threshold on October results and advertise the resulting subset as a validated hit rate. Any threshold selected now must be tested on new games. No claims of a betting edge without archived as-of market comparisons and prices.

## Immediate decisions

- No challenger promotion in this review.
- No alteration to any frozen bundle, weights, configuration, saved forecast, settlement, or historical evaluation.
- Preserve this review's source cutoff and calculations as a new audit artifact.
- Prioritize CFB input observability and winner-quality research; NHL missingness robustness; continued paired evidence collection.
