# NHL Additional Factor Tournament

Development only: 2021–22 to 2024–25. 2025–26 removed before features. Same-date outcomes update state after prediction.

| Candidate | Accuracy | Brier | Log loss | Seasons improving | Eligible |
|---|---:|---:|---:|---:|---|
| advanced_all_w20 | 61.34% | 0.231620 | 0.655148 | 0 | False |
| opponent_adjusted | 61.49% | 0.231757 | 0.655494 | 1 | False |
| schedule_travel | 61.51% | 0.231767 | 0.655461 | 1 | False |
| opponent_plus_schedule | 61.59% | 0.231897 | 0.655800 | 1 | False |

MoneyPuck.com is credited for exploratory expected-goals inputs. Historical model vintage is unverified; xG candidates cannot be promoted.
Quality source status: {'available': True, 'source': 'MoneyPuck.com', 'url': 'https://moneypuck.com/moneypuck/playerData/careers/gameByGame/all_teams.csv', 'historical_model_vintage_verified': False, 'rows': 16938, 'reason': 'Insufficient team-game match coverage; shot-quality candidates not run'}; matched coverage: 0.950938717676231.
Travel uses approximate arena-to-arena distances; actual itineraries and neutral-site adjustments are unavailable.
Opponent scoring residuals compare prior results with each opponent’s scoring/conceding record available before that prior game.

improve both Brier/log loss, preserve accuracy, improve Brier in >=3/4 seasons; unverified retrospective xG ineligible
