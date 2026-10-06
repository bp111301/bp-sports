# NHL Deterioration Audit

Read-only audit. No model fitting, tuning, release, or excluded-season rerun.

| Season | Accuracy | Home win rate | Home pick rate | Mean confidence |
|---|---:|---:|---:|---:|
| 20212022 | 64.63% | 53.66% | 58.23% | 61.98% |
| 20222023 | 61.13% | 52.36% | 59.98% | 62.27% |
| 20232024 | 59.91% | 54.12% | 59.30% | 61.45% |
| 20242025 | 59.68% | 56.25% | 59.83% | 60.28% |
| 20252026 | 53.43% | 52.21% | 64.63% | 58.96% |

## Independent NHL schedule/stat-summary agreement

```json
{
  "schedule_games": 1312,
  "schedule_duplicate_ids": 0,
  "tied_final_scores": 0,
  "game_state_counts": {
    "OFF": 1312
  },
  "team_stat_rows": 2624,
  "team_stat_duplicate_keys": 0,
  "home_team_stats_matched": 1312,
  "away_team_stats_matched": 1312,
  "home_win_label_disagreements_vs_stats": 0,
  "away_win_label_disagreements_vs_stats": 0,
  "noncomplementary_stats_winners": 0,
  "saved_label_disagreements_vs_new_schedule": 0,
  "saved_home_team_disagreements": 0,
  "saved_away_team_disagreements": 0,
  "stat_home_road_values": {
    "H": 1312,
    "R": 1312
  },
  "home_score_disagreements_vs_stats": 56,
  "away_score_disagreements_vs_stats": 63
}
```

Descriptive diagnostics cannot uniquely attribute deterioration to roster changes, injuries, parity, or model overfitting. No alternative candidate is scored on the excluded season.
