# Dashboard efficiency — November 15, 2026

## Changes

- Cache each published feed independently for 120 seconds, retaining background refresh. Sport boards and Weekly results request only their own feeds; pages share those cached sources when navigating. Overview still reads every sport and experiment it displays.
- Load one score snapshot for an Overview or Weekly results render and pass it through identity-checked lookups. This avoids thousands of repeated unpickles of the same score archive.
- Build the favorites menu from a small cached navigation catalog rather than downloading the CBB forecast archive or reparsing the 2.5 MB matchup-preview file on every rerun. The catalog includes 365 CBB teams and the existing CFB aliases.
- Render at most 40 cards at a time on the detailed CBB board. Filters reset pagination, and the download retains all matching forecasts, across every page.
- Cache NHL's fixed historical input directories using the frozen manifest and download-script hashes. Current-season inputs are still refreshed on every run; a cache miss follows the existing download path. Model/ledger safety checks remain in place. Add pip download caching to NHL, score-refresh and final-grading jobs without changing their schedules or dependency versions.
- Show the release marker `dashboard-efficiency-20261115` under About B.P. Sports so the hosted runtime can be checked independently of GitHub's branch state.

## Local measurements

Two fixture-based AppTest trials per revision used the same saved data and code paths with remote feed reads replaced by local fixtures. Medians below include Python/Streamlit render work, not real network transit or browser paint time. Small samples and shared-machine load mean these are comparative measurements, not production latency guarantees.

| View | Before | After | Reduction |
|---|---:|---:|---:|
| Overview | 10.667 s | 3.338 s | 68.7% |
| NFL Weekly results | 4.407 s | 0.306 s | 93.0% |
| NFL compact board | 1.881 s | 0.888 s | 52.8% |
| CBB detailed board, first page | 2.119 s | 0.450 s | 78.8% |

Cold forecast-source reads for the NFL compact board decreased from 20 to 2, and fixture bytes from 5,384,408 to 1,056,215. Weekly NFL source reads decreased from 20 to 1. These counts exclude the separate live-score provider requests. Overview's score-snapshot cache reads decreased from 4,278 to 5; NFL Weekly results decreased from 2,052 to 1. CBB's initial archive view renders 40 cards rather than 1,784 while retaining access to all rows through pagination and the complete filtered export.

## Validation and limits

The main suite passed 154 tests in a disposable checkout with the committed NFL bundle restored there. New coverage checks scoped feed loading and cross-page reuse, a network-independent favorites menu, Weekly results isolation from unrelated feeds, and CBB page/filter/export behavior. All 11 saved-data projections (Overview, five compact boards and five Weekly results views) have identical before/after SHA-256 hashes, including saved picks, probabilities, timestamps and grades. The preservation gate and whitespace checks passed. Edited workflow YAML and embedded Bash parsed successfully.

Frozen model files, forecast ledgers and historical evaluation outputs are unchanged. The navigation catalog is derived display data, not a forecast or evaluation. No inference formulas or grading rules changed. No polling schedule or watchdog interval was removed or slowed down.

A production NHL historical-cache hit has not yet been measured; the first run for this key is expected to miss. Cache savings should be checked on a later run. The hosted Streamlit app previously served older UI code despite current branch data. A merged PR alone does not prove this release is running there: verify the About release marker and the CBB Page control in a fresh session. If absent, inspect Community Cloud's configured branch, running revision and deployment logs before restarting/redeploying the app.
