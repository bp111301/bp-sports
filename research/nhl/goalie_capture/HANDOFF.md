# Starting-goalie capture handoff — 2026-10-06

First collector run: https://github.com/bp111301/bp-sports/actions/runs/37503652531
(success). Nine capture safety tests passed locally and in CI.

Saved 24 observations covering both teams in 12 upcoming regular-season games.
Nine had explicit confirmed status, valid pregame report timing, a source link,
and a unique NHL roster player match. All 24 roster mappings resolved. No source
or matchup errors. The earliest start was more than five hours after capture.
These are source-availability observations, not 24 new model predictions.

The recurring launcher is installed on main, runs at minute 7 and 37 of each
hour, and explicitly checks out and writes the research branch. GitHub scheduling
delay can miss late confirmations. Read `data/nhl/goalie_capture/summary.json`
for health and coverage; `observations.jsonl` and compact hashed snapshots
preserve the first observed state and subsequent changes.

The first capture occurred after the existing three-model watchlist predictions.
Do not attach these confirmations to those earlier forecasts. Use `available_at`
with the exact future prediction cutoff. No goalie model has been fit, activated
or scored by this collector; no existing NHL probability or CFB artifact changed.

Next research step: record a fixed goalie hypothesis and timing/control protocol,
then collect separate goalie-adjusted forecasts before future games. Keep a
same-cutoff control and coverage reporting so updated team state and the ability
to obtain a confirmation are not confused with goalie-model improvement.
Goalie histories must include only completed earlier games at each cutoff.
