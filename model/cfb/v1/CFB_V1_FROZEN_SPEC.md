# B.P. Sports CFB V1 — Frozen Specification

Freeze timestamp: 2026-10-06T03:22:19Z

## Status

CFB V1 is frozen before any 2026 result is opened for model selection. The 2018-2025 development tournament selected the specification below. 2026 may now be used only as an untouched diagnostic and, from this freeze forward, as a prospective prediction ledger.

No 2026 result may change CFB V1. Any algorithm change becomes CFB V2.

## Scope

- FBS vs FBS, non-bowl games from the cfbfastR matchup-line dataset.
- Winner probability only.
- Betting spreads, totals, and market prices are excluded from winner selection.
- Retrospective realized-season quarterback identity fields are excluded.
- Pregame/as-of features are calculated strictly from games before kickoff by the source matchup builder.

## Model

CFB V1 is a probability ensemble of two regularized logistic regressions:

P(V1 home win) = 0.25 × P(context) + 0.75 × P(dynamic-prior)

Both components use median imputation with missingness indicators, standard scaling, and logistic regression with C=0.5.

The context component uses Elo, home field, conference-game status, current and prior efficiency, opponent strength, talent, returning production and head-coach tenure.

The dynamic-prior component uses a 7-week transition from prior-season to current-season efficiency for offense/defense EPA, pass/rush EPA and success rate:

current_weight = min(1, max(0, (week - 1) / 7))

## Development evidence

Expanding-window walk-forward, 2018-2025; each season trained only on earlier seasons:

- Games: 5,733
- Accuracy: 72.74%
- Brier: 0.1773
- Log loss: 0.5280
- Mean confidence: 74.53%

Recent stability check, 2023-2025:
- Games: 2,287
- Accuracy: 72.10%
- Brier: 0.1801

These are historical development results, not prospective performance claims.

## Rejected / deferred for V1

- Histogram gradient boosting: worse Brier/log loss.
- Expanded 36-feature linear set: no probability-quality improvement.
- Platt calibration: did not beat the selected ensemble.
- Prior-week QB layer: essentially no incremental historical improvement in the tested form; deferred rather than forced into V1.
- Market data: never part of winner selection.

## Guardrails

1. No 2026 result may alter this specification.
2. No post-kickoff prediction may be inserted into the prospective ledger.
3. Existing ledger snapshots are immutable.
4. Market prices remain a separate comparison/value layer.
5. Model changes require a new version.
