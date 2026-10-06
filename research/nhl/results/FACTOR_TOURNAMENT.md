# NHL Additional Factor Tournament

Development only: 2021–22 to 2024–25. 2025–26 removed before features. Same-date outcomes update state after prediction.

| Candidate | Accuracy | Brier | Log loss | Seasons improving | Eligible |
|---|---:|---:|---:|---:|---|
| shot_quality_exploratory | 61.34% | 0.231586 | 0.655027 | 2 | False |
| advanced_all_w20 | 61.34% | 0.231620 | 0.655148 | 0 | False |
| opponent_adjusted | 61.49% | 0.231757 | 0.655494 | 1 | False |
| schedule_travel | 61.51% | 0.231767 | 0.655461 | 1 | False |
| all_factors_exploratory | 61.19% | 0.231832 | 0.655590 | 1 | False |
| opponent_plus_schedule | 61.59% | 0.231897 | 0.655800 | 1 | False |

MoneyPuck.com is credited for exploratory expected-goals inputs. Historical model vintage is unverified; xG candidates cannot be promoted.
Quality source status: {'available': True, 'source': 'MoneyPuck.com', 'url': 'https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv', 'historical_model_vintage_verified': False, 'rows': 16938, 'team_aliases_applied': {'L.A': 'LAK', 'N.J': 'NJD', 'S.J': 'SJS', 'T.B': 'TBL'}, 'date_offset_days': {'0': 16938}, 'missing_by_season_team': {}, 'date_rule': 'NHL game ID and club define identity; NHL game_date defines post-game availability; vendor dates audited only'}; matched coverage: 1.0.
Travel uses approximate arena-to-arena distances; actual itineraries and neutral-site adjustments are unavailable.
Opponent scoring residuals compare prior results with each opponent’s scoring/conceding record available before that prior game.

improve both Brier/log loss, preserve accuracy, improve Brier in >=3/4 seasons; unverified retrospective xG ineligible
