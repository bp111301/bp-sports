# CBB V1 development

Status: data access verified on October 13, 2026; no trained or released model yet.
Initial scope: men's Division I college basketball, pregame winner probabilities.
Existing NFL, CFB, NHL and NBA models remain independent.

## Data access

Source: SportsDataverse/hoopR ESPN men's college basketball team box scores.
https://github.com/sportsdataverse/sportsdataverse-data/releases/tag/espn_mens_college_basketball_team_boxscores

Verified public Parquet assets for ending-year seasons 2022 through 2026.
The 2026 asset opened successfully and contained 12,598 team-game rows.
This is a raw row count, not a count of eligible paired Division I games.
Fields include game timestamps, season type, stable team and opponent IDs,
scores, shooting attempts/makes, rebounds, free throws and turnovers.
Schedules are also required to verify neutral venues and eligible opponents.

## Baseline and evaluation

1. Audit schedules and paired box scores: duplicate IDs, reciprocal opponents,
   missing statistics, final status, timestamps, Division I eligibility and neutral sites.
   Exclude preseason/exhibition games. Do not infer home advantage from the
   administrative home label at a neutral venue.
2. Build a simple Elo/home-or-neutral baseline before testing richer inputs.
3. Compare logistic models using lagged efficiency, effective shooting,
   turnovers, offensive rebounds, free-throw rate, pace, rest and opponent strength.
   Update state only after a game's final; process simultaneous games together.
   Use conservative offseason regression and early-season priors.
4. Reserve ending-year 2026 as an untouched evaluation season. Select features
   and calibration using earlier chronological folds; do not tune on the holdout.
   Report accuracy, Brier score, log loss and season/confidence breakdowns.
   Full-season ratings computed with future games are forbidden as pregame inputs.
5. Freeze a version only after evaluation, archive prospective forecasts before
   tipoff for the 2026-27 season, and grade confirmed finals without revising picks.

Rosters, transfer continuity and injuries are later experiments only when
dated pregame data can be reliably archived. No live CBB board until the
forecast pipeline, eligibility checks and grading are validated.
