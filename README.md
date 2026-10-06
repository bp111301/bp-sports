# B.P. Sports — NFL Prediction System

B.P. Sports is an independent NFL forecasting project. The production dashboard displays the frozen V4 forward test; betting-market prices are deliberately excluded from winner selection.

## Production architecture

- `app.py` — Streamlit dashboard.
- `model/v4/bundle.part.*` — versioned deployment bundle, stored as base64 chunks and restored by CI.
- `model/v4/BP_V4_FROZEN_SPEC.md` — frozen model contract.
- `pipeline/refresh_data.py` — downloads fresh nflverse schedule and play-by-play snapshots.
- `pipeline/build_predictions.py` — builds leakage-safe current-season features and V3/V4 predictions, applies frozen confidence rules, and appends immutable pregame snapshots.
- `pipeline/settle_predictions.py` — grades completed games without changing prediction fields and calculates accuracy, Brier score, and log loss.
- `data/current/website_feed.csv` — current dashboard feed.
- `data/ledger/prediction_ledger.csv` — append-only pregame ledger.
- `.github/workflows/update_predictions.yml` — Thursday/Sunday automation plus manual dispatch.

## Frozen V4

Core deployment formula:

`0.50 × V3 + 0.50 × (0.75 × QB-change model + 0.25 × QB-quality model)`

Secondary layers may change confidence but may not flip the winner: extreme last-5 explosive matchup, last-5 turnover mismatch, and last-5 early-down success mismatch.

Pressure/sack proxy, third down, red-zone TD rate, and special-teams proxy remain outside the core model after failing broader historical stability tests.

Historical reused-sample V4 accuracy was 65.02% (1,279–688 over 2018–2025). That figure is exploratory because those seasons were used during development. The 2026 forward ledger is the evidence that matters now.

## Automation

The GitHub Action runs at 8 AM America/Chicago on Thursday and Sunday. It downloads current nflverse inputs into an untracked runtime directory, settles completed ledger entries, generates only legitimate pregame predictions for unstarted games, preserves already-started games on the dashboard, runs integrity tests, and commits only the small generated feed/ledger/summary files.

The workflow can also be run manually from GitHub Actions with a season and optional week.

## Guardrails

1. No post-kickoff prediction creation.
2. No market odds in the B.P. winner model.
3. Confidence layers cannot flip the V4 winner.
4. Existing prediction snapshots are never overwritten.
5. Settlement may change only outcome/settlement fields.
6. Model changes require a new version; Week 5 results do not change frozen V4.
