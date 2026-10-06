# NBA V1 baseline handoff

NBA research is isolated on `nba-v1-research`. Production UI, NFL, CFB, and NHL
models and prospective ledgers were not changed.

The fixed 14-feature logistic baseline uses team efficiency, recent form, Elo,
home/neutral context, rest, and back-to-backs. Season histories reset; Elo is
regressed toward average each offseason. Features use only earlier dates and
model/scaler fitting uses earlier seasons. No player availability or markets.

Development: 8,288 games from 2018–19 through 2024–25. Initial training starts
in 2015–16. Weights are fit once before each test season, then held fixed.

| Model | Correct / games | Accuracy | Brier | Log loss |
|---|---:|---:|---:|---:|
| Team logistic | 5,414 / 8,288 | 65.32% | .217395 | .624300 |
| Fixed Elo | 5,325 / 8,288 | 64.25% | .220687 | .631220 |
| Training home frequency | 4,620 / 8,288 | 55.74% | .247011 | .687168 |

The team baseline improves Brier and log loss in all seven development seasons,
and accuracy in six of seven. Its accuracy ranges from 62.31% to 68.02% across
seasons. Calendar-date paired bootstrap accuracy gain is +1.07 percentage
points (95% interval +0.43 to +1.69); Brier delta −.003292 (−.004361 to −.002193).
These conditional development intervals do not establish live performance.

Source audit excludes All-Star/Rising Stars, Cup championship, postponed/canceled
entries, two missing box pairs in initial training seasons, and one inconsistent
2024–25 shooting box (ESPN 401704652). Schedule/box teams and final scores match
for included games. One 2020 archived date is corrected from an NBA scorer's
report; details in PROTOCOL.md. Neutral 2020 bubble games have no home advantage.

Eight safety checks cover outcome isolation, prior-date history/rest, neutral
context, season reset, ordering, training-only fitting, schema, and same-date
team conflicts. GitHub Actions reproduces the run and saves source hashes and
outputs. `baseline_summary.json` and `baseline_by_season.csv` are authoritative.

2025–26 (ending year 2026) has not been downloaded or evaluated. Keep it closed
while developing. The bounded advanced-stat tournament is complete (see below). Next: a small
preregistered nonlinear-model/calibration comparison, then freeze the chosen
specification before opening 2025–26 once. Player availability
requires archived pregame data or a separately captured prospective experiment.
The baseline remains research-only; it has not been promoted or added to the UI.


## Advanced team-stat tournament

The 12-entry tournament (baseline plus 11 challengers) retained baseline_control.
No challenger passed the rules registered in TOURNAMENT_PROTOCOL.md. The original
baseline predictions were reproduced to absolute tolerance 1e-12 on the identical
8,288-game population. All 16 baseline/tournament safety tests passed.

| Candidate | Accuracy | Brier | Log loss | Seasons with lower Brier | Eligible |
|---|---:|---:|---:|---:|---|
| advanced20 | 65.07% | 0.217302 | 0.624042 | 5/7 | No |
| baseline_control | 65.32% | 0.217395 | 0.624300 | 0/7 | Reference |
| advanced30 | 64.97% | 0.217434 | 0.624212 | 3/7 | No |
| windows30 | 65.12% | 0.217469 | 0.624358 | 3/7 | No |
| fatigue20 | 65.20% | 0.217521 | 0.624540 | 3/7 | No |
| advanced10 | 65.17% | 0.217575 | 0.624631 | 2/7 | No |
| opponent_adjusted20 | 65.21% | 0.217594 | 0.624753 | 2/7 | No |
| recency2 | 65.26% | 0.217617 | 0.624845 | 3/7 | No |
| season_history | 64.72% | 0.217686 | 0.624687 | 3/7 | No |
| opponent_adjusted30 | 65.01% | 0.217716 | 0.624936 | 2/7 | No |
| advanced_season | 64.84% | 0.217839 | 0.624943 | 3/7 | No |
| windows10 | 64.93% | 0.217846 | 0.625298 | 2/7 | No |

The lowest-Brier challenger, advanced20, improved Brier by only .000093 and
log loss by .000258, while losing 21 correct picks (65.07% versus 65.32%). It also
failed the latest-two-season stability rule; its probability-score bootstrap
intervals cross zero. This is insufficient evidence to replace the baseline.
Window changes, fatigue features, opponent-adjusted residuals and recency weighting
did not improve the pooled probability scores. No candidate was promoted.

Matched predictions, season metrics, eligibility checks, descriptive bootstrap
intervals and reproducibility hashes are saved in tournament_oof_predictions.csv,
tournament_by_season.csv and tournament_summary.json. The bootstrap intervals do
not correct for candidate selection. The 2025–26 evaluation season remains unopened.
