# B.P. Sports Multisport Roadmap

## Production
- NFL V4: frozen, automated, prospectively graded.

## Build now
- CFB V1: historical research -> chronological backtest -> freeze -> 2026 forward test.

## Next
- NBA V1: begin data engineering/research before the Oct. 20, 2026 regular-season opener. Basketball requires player availability, rest/back-to-backs, travel, lineup quality, pace, offensive/defensive efficiency and shooting-profile features.
- NHL V1: begin after the CFB baseline is stable. Hockey requires goalie confirmation, expected goals, shot quality, special teams, rest/travel and starting-goalie uncertainty.

## Platform rule
Each sport has its own training data, features, model version and forward ledger. Shared infrastructure may handle scheduling, calibration, grading, dashboards and deployment, but observations from one sport never become training rows for another sport's winner model.
