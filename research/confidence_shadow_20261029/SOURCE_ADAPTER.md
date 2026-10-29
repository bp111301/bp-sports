# Source adapter clarification before first NHL shadow capture

The CFB schedule release leaves status blank. Each target is independently checked using its ESPN event summary: exact game/team identity, kickoff equality, scheduled pregame state and no completed result. A blank exported field never establishes pregame eligibility.

The NHL per-game team-stat report temporarily lacks one newly final game. For a missing or partial completed-game pair only, allow official NHL game-center landing + right-rail counts after validating identity, regular-season type, FINAL/OFF state, exact score/start/team agreement, shot totals, faceoff counts and power-play counts. These are the SAME numerical inputs required by the existing recipe, not new predictors. Remove the shootout award from unadjusted goals exactly as the original report adapter does. Never infer missing opportunities or substitute a nonfinal game.

Compare available primary rows with the game-center adapter; conflicting fields fail. Equivalence is checked against reported completed games before first use. Preserve complete source response hashes and the supplemented input rows. The frozen reference and challenger both consume this exact same supplemented snapshot. This comparison remains a newly reconstructed same-input reference; it is never represented as the original earlier dashboard forecast.

Each sport appends only its independently valid receipts. A failure in NHL must not discard valid CFB records; report the failed sport explicitly and return a failed operational status. Retain a ten-minute publication margin before scheduled start, in addition to the strict pregame requirement. No new model, changed weight, relaxed qualification gate, live outcome selection, or backfilled forecast.
