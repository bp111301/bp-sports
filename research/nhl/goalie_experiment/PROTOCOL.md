# Confirmed-goalie paired experiment — 2026-10-06

New unpromoted research experiment. Existing NHL V1, the three-model watchlist,
their predictions, the UI, CFB V1 and Candidate B remain unchanged.

Use one fixed goalie feature from the earlier bounded research: the difference
between home and away shot-weighted save percentages over at most 20 prior
appearances within 365 days, shrunk toward .905 with 300 prior shots. Player
history follows NHL player ID across teams and seasons. Infer the probable
starter using prior ten team starts in the current season, most recent start
breaking ties. With no current-season team starts, use the .905 prior.

Fit one 19-feature logistic model: the original 18 team features plus this
goalie difference, C=.5, raw probabilities, training-only preprocessing.
Training is completed 2018–19 through 2025–26. Historical features must infer
the starter before a game; realized starters update history only after all
games on a date receive features. Do not train using realized starter identity
as a pregame feature. Do not score alternatives on the failed 2025–26 season.
Freeze this new model, feature code, dependency versions, training inputs and
configuration before any prospective prediction. No in-season weight refitting.

Record each game's first eligible paired prediction inside the final 60 minutes
before its current scheduled start. Require both goalies to be confirmed and
uniquely mapped to NHL roster IDs in observations captured by the input cutoff.
The latest observed state at that cutoff controls availability, including
downgrades or substitutions. Publication time cannot backdate availability.
Games without both eligible confirmations are excluded, with coverage recorded.
Polling delay may miss confirmations or the entire window.

Three predictions share the exact input cutoff, team features, creation time
and outcome population:
1. Team control: the existing frozen watchlist reference, recomputed at this
   cutoff without changing its original earlier prediction.
2. Inferred goalie: the new 19-feature model with prior-start goalie estimates.
3. Confirmed goalie: the identical 19-feature weights, substituting each
   confirmed goalie's prior-only save-percentage history.

Primary comparison is confirmed versus inferred goalie, isolating information
about identity. Confirmed versus team-only measures the complete goalie layer.
Do not compare these late forecasts to earlier daily forecasts as evidence of
goalie benefit. No source-provided performance statistics or market prices.
Goalie histories conservatively exclude the entire current game date, matching
the historical batch-by-day feature construction. Current final team results
may update team features equally in all three predictions.

Append all three predictions atomically before start; preserve their first
probabilities, feature snapshot, hashes and observation IDs. No partial pairs,
historical backfill or post-start creation. Settle only final games and reject
rows whose recorded creation is at/after either recorded or current start.
Pending results never enter descriptive paired accuracy, Brier or log loss.

The first formal review is after 500 fully settled valid paired games. Report
paired Brier/log-loss differences and chronological stability; both probability
scores must improve without losing accuracy before considering a new release
decision. Coverage and the both-confirmed selection population must be reported.
Do not tune or choose a winner from early results, promote automatically or
claim the confirmed subset represents every NHL game.
