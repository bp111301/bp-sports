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
while developing. Next: register a bounded advanced-stat/window tournament,
compare accuracy and probability scores on these same development games, then
freeze the chosen specification before opening 2025–26 once. Player availability
requires archived pregame data or a separately captured prospective experiment.
The baseline remains research-only; it has not been promoted or added to the UI.
