# B.P. Sports CFB V1 Research

CFB is a sister model to NFL V4. College games are never mixed into the NFL training set.

## Objective

Build a leakage-safe FBS winner-probability model, backtest it chronologically, calibrate its probabilities, then freeze a CFB V1 before using the remaining 2026 season as a prospective test.

## Data

Primary research source: sportsdataverse/cfbfastR play-by-play release assets. The classic FBS line contains EPA/WPA-enriched PBP from 2014 onward and currently includes 2026 assets.

Initial development seasons: 2014–2025.
Prospective holdout: remaining 2026 games after CFB V1 freeze.

Raw PBP is downloaded locally and is never committed to this repository.

## V1 baseline feature families

- opponent-adjusted offensive and defensive EPA/play
- offensive and defensive success rate
- passing and rushing efficiency splits
- explosive pass/rush rates
- turnover margin and turnover rates
- scoring margin / drive efficiency
- Elo-style team strength
- home field and neutral-site handling
- rest
- strength of schedule
- recent-form rolling windows

## CFB-specific challengers

These are tested only after the baseline exists:

- recruiting/talent composite
- returning production / transfer turnover
- conference-strength adjustment
- coach/coordinator changes
- quarterback continuity and quality
- FBS/FCS opponent treatment
- dynamic early-season priors
- nonlinear / ensemble challenger

## Evaluation

Every candidate must use chronological walk-forward evaluation. Primary scorecard:

- winner accuracy
- Brier score
- log loss
- calibration by confidence bucket
- performance by season
- performance by conference / favorite strength / home-neutral
- upset detection

No market line is used to choose the winner. Market comparison can be evaluated separately later.

## Freeze rule

Once CFB V1 is frozen, 2026 forward predictions are immutable after kickoff. Results can grade the prediction but cannot rewrite it. A CFB V2 must be developed separately.
