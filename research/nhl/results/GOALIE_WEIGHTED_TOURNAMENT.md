# NHL Weighted Goalie Follow-up

Development results only; 2025–26 excluded. Fixed .905 / 300-shot prior; no prior tuning. Starter usage uses prior team starts; player shot-weighted history follows identity across teams/seasons and expires after 365 days. All outcomes update after the entire date is predicted.

| Candidate | Accuracy | Brier | Log loss | Seasons improving Brier | Eligible |
|---|---:|---:|---:|---:|---|
| advanced_weighted_probable | 61.03% | 0.231465 | 0.654763 | 3 | False |
| advanced_weighted_mixture | 60.94% | 0.231587 | 0.655081 | 3 | False |
| advanced_all_w20 | 61.34% | 0.231620 | 0.655148 | 0 | False |
| advanced_weighted_workload | 61.01% | 0.231874 | 0.655638 | 2 | False |

keep team-stat leader unless a goalie candidate improves aggregate Brier/log loss, does not reduce accuracy, and improves Brier in at least 3 of 4 seasons
