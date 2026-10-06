# NHL V2 research handoff — 2026-10-06

CFB V1 and Candidate B remain frozen. The original NHL V1 bundle and failed
release decision remain unchanged. No NHL production or betting deployment.

## Audit and development results

The separate read-only source audit found complete team-game joins and no
material feature-coverage break. It did not establish a cause for the 2025–26
decline and did not score alternative models on that failed season.

Both tournaments used the same 5,248 chronological development games from
2021–22 through 2024–25. Earlier seasons alone trained each fold. These seasons
have been reused, so the results are exploratory rather than fresh validation.

| Procedure | Accuracy | Brier | Log loss | Seasons with better Brier |
|---|---:|---:|---:|---:|
| Original reference | 61.34% | .231620 | .655148 | — |
| Two-season half-life logistic | 61.70% | .231583 | .655071 | 2/4 |
| Fixed regulation blend | 61.32% | .231470 | .654772 | 3/4 |

No candidate passed the recorded gate. Recency weighting missed season
consistency; the regulation blend lost one correct prediction relative to the
reference. Recent-only training, the small boosted tree, the linear/tree blend,
regulation-form logistic, three-way regulation and regulation Poisson also did
not qualify. Do not tune thresholds or blend weights to rescue these outcomes.

Runs: model comparison 37497046491; combined/regulation comparison 37497832963.
Saved predictions reproduce all reported metrics and reference parity.
All 33 local safety tests pass, including four model, four regulation and three
pregame ledger tests in addition to the original 22.

## Fixed experimental pregame watchlist

`research/nhl/prospective/PROTOCOL.md` records the next evidence boundary.
`model/nhl/v2_research/spec.json` locks reference control, recency weighting and
the regulation blend as unpromoted research hypotheses. They fit completed
2018–19 through 2025–26 once, then keep weights fixed throughout 2026–27.
The failed season is fitting data, never another independent candidate test.

The ledger records first probabilities before scheduled starts, preserves model
and specification hashes, and settles only valid pregame records. No historical
backfill. Current completed games update lagged features, not weights.
`data/nhl/v2_research/summary.json` contains descriptive results as they arrive.

The daily workflow launcher is registered on main and explicitly checks out and
writes only `nhl-v1-research`. It runs at 11:15 UTC, subject to GitHub scheduling
delay, with a 36-hour forecast horizon and manual refresh available.
No application, CFB model or CFB workflow was changed on main.

Next: monitor source health and pregame ledger integrity, accumulate later
results, and document a separate release decision before any deployment. Do not
declare a winner from an early small sample or silently refit the locked bundle.
