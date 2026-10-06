# NBA V1 bounded team-stat tournament

Registered before running candidates. Research only; 2025–26 stays unopened.
Use exactly the baseline's audited games and expanding-season folds, 2019–2025
ending years. Fit scaler/logistic weights only on earlier seasons; no calibration,
market fields, injury backfills, or new source downloads. Logistic C=1 throughout.

Twelve fixed entries:
1. baseline_control: original 14 features, 20-game history.
2–4. windows10, windows30, season_history: baseline with rolling means/history
count changed to last 10, last 30, or all current-season games; same five priors.
5–8. advanced20, advanced10, advanced30, advanced_season: matching baseline plus
opponent eFG, turnover, offensive rebound and free-throw attempt rates; own
three-point attempt share and assists per FGA. Five fixed priors (.50, .13, .25,
.25, .35, .25 respectively). These are game means, not possession-weighted totals.
9–10. opponent_adjusted20, opponent_adjusted30: matching baseline plus prior-game
offensive/defensive residuals against opponent's pre-date shrunk efficiency.
Off residual = game ORtg − opposing prior DRtg; def residual = game DRtg −
opposing prior ORtg. Five zero residual priors. The opponent reference always
uses last 20 games, so candidate windows do not alter the adjustment target.
11. fatigue20: baseline plus separate home/away capped rest and back-to-back,
games in preceding three/five days (3-in-4, 4-in-6 context). Current game excluded.
12. recency2: baseline, logistic training sample weights with two-season half-life.

Every game's features are calculated before its date's outcomes update any
history. Histories reset each season; Elo carries/regresses as in the baseline.
Do not add candidates or change settings after observing the results.

Eligibility against baseline: pooled Brier improves by at least .0005, pooled
log loss improves, accuracy retains at least 5,414 correct games, Brier improves
in at least five of seven seasons and in both latest seasons (2024 and 2025).
Rank eligible candidates by Brier, then log loss, then name. If none pass, retain
baseline. Report every candidate/season, matched OOF predictions, code/protocol/
input hashes and date-block bootstrap comparisons. Those intervals are descriptive
after multiple comparisons; they do not validate the selected winner independently.
Never automatically promote, freeze a production artifact, or open the holdout.
