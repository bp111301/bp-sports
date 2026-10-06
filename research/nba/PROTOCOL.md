# NBA V1 baseline protocol

Research only. No production promotion or NBA UI change in this run.

Register one logistic baseline (C=1, training-only StandardScaler, no calibration)
before viewing results. Compare with training-only home-win frequency and fixed
Elo (K=20, home advantage 65, preseason regression 25%, probability scale 400).
No markets, retrospective injury information, standings, or final season totals.

Use ESPN NBA schedule and team box scores distributed by SportsDataverse.
Archive source files and hashes. Seasons use ending years: download 2016–2025
(2015–16 through 2024–25). Never download/evaluate 2026 (2025–26) in development.
Regular season only (the 30 NBA franchises, excluding All-Star/Rising Stars
exhibitions mislabeled by the source). Exclude Cup championship, play-in, postseason, preseason,
unfinished games, and invalid/missing box scores. Audit every exclusion and
join. Neutral games, including the 2020 Orlando bubble, get no home advantage.

Source correction: ESPN game 401161536 has an erroneous March 1 morning
timestamp. Use February 29, 2020 for date batching/rest, confirmed by the NBA
official scorer's report at
https://statsdmz.nba.com/pdfs/20200229/20200229_GSWPHX_book.pdf.
The archived source timestamp stays unchanged; it is not an actual prediction
creation timestamp. Missing/inconsistent box games are omitted and counted;
their outcomes do not enter state. This is a small documented coverage gap.

Features: prior-game Elo difference; shrunk 20-game offensive and defensive
points per estimated 100 possessions, pace, eFG%, turnover rate, offensive
rebound rate, free-throw attempt rate, win rate; 5-game net efficiency; capped
rest and back-to-back difference; home advantage and history count difference.
Possessions estimated as the average of both teams' FGA + .44 FTA − OREB + TOV.
Current-season rolling histories reset each season and have five fixed prior
games (108 offensive/defensive rating, 100 possessions, .50 eFG, .13 turnover,
.25 offensive rebound/free-throw rates, .50 wins). Elo carries across seasons.

All games on an Eastern calendar date get features before any outcomes from
that date enter state. Rest uses earlier played dates. No same-day outcomes.
Use three initial training seasons (2016–2018); evaluate 2019–2025 expanding
by whole season, with coefficients and scaler fit only on previous seasons.
In-season team state updates with earlier completed results; weights do not.

Report season/pooled accuracy, Brier, log loss, calibration bins and paired
bootstrap intervals against Elo (resample calendar dates, 2,000 draws, seed42).
COVID seasons are reported separately, not silently removed. These are
chronological development estimates, not pristine holdout or live results.
Keep 2025–26 unopened until a chosen model/configuration is frozen separately.
