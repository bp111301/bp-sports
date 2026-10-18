# NBA availability shadow: prospective protocol, October 18, 2026

This is a separate append-only paired experiment for season-ending-2027 NBA
regular-season games. V1 remains the public model. No public V1 weights,
predictions, grades, historical evaluation or other-sport data may be changed.
Preseason, postseason, non-NBA exhibitions and the NBA Cup championship are excluded.

The selected candidate is the shortlisted development variant with the lowest
pooled Brier score: minutes_weighted. Its final residual uses 2021–25 genuine OOF
V1 predictions with both teams known. No 2026 game outcome is evaluated for
selection or used for fitting residual coefficients. The reserved 69.19% V1 result
remains unchanged. This protocol is frozen before prospective outcomes.

The paired control is V1 recomputed with its original frozen bundle at the same
capture time and on the same earlier-date team state as the challenger. It is
separate from the public 36-hour V1 snapshot. Live probabilities are never trained
or recalibrated automatically.

Capture begins at the earlier of tipoff minus 60 minutes and 18:00 Eastern on the
game date, matching development. The latest allowed injury PDF corresponds to
the hour before the floored cutoff (legacy XXPM, or modern XX_30PM for the same
publication instant), with at most two earlier hours. Require both embedded and
PDF creation timestamps before cutoff, publication no later than capture, exact
game date/matchup, both teams explicitly submitted, and no parser issue. Missing
reports may be retried before tipoff; no report after the fixed cutoff is usable.
Until 15 minutes before tipoff, unknown reports delay capture. Then capture an
explicit exact-V1 fallback. Every saved pair is immutable, even if a later report
appears. A skipped/postponed game never gets a backfilled forecast after tipoff.

Player importance uses at most 20 earlier eligible appearances and names learned
only before the game's Eastern date. Prior 2025–26 regular-season records may be
read only as forward state, never for selection, evaluation or coefficient fitting.
Current season boxes also update state only on earlier dates. Minutes and points
are the only player quantities used in features; outcomes only validate source
identity. Prior-season source is required. Current-season player boxes are
required once prior-date current-season games exist. Missing player source or
less than 80% identity matching among listed impact players forces exact V1
fallback. Zero listed impact players is allowed when both reports are explicit.

Each pair records control/candidate probabilities, model hashes, all features,
source URLs and hashes, availability timestamp/knownness/match coverage, cutoff,
history cutoff and capture time. Grades are appended only for confirmed completed
regular-season finals after tipoff. Changed start times invalidating pregame timing
cannot settle. Report full paired-cohort results, adjusted-only results and fallback
coverage; never quietly drop fallbacks to advertise performance.

No promotion decision is made from opening-week accuracy. Accumulate prospective
evidence and inspect source coverage and probability quality before any separately
reviewed model change. The collector runs after the existing V1 job, fails without
modifying V1 if sources are invalid, and stores only its own data paths.
