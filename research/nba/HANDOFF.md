# NBA V1 handoff

NBA V1 is frozen on `nba-v1-research` and passed its preregistered excluded-season gate. It is eligible for prospective collection, not automatically production-promoted. NFL, CFB, NHL and the production UI were unchanged.

## Model and evaluation

The original 14-feature logistic baseline remains selected. Team efficiency, recent form, Elo, home/neutral context, rest and back-to-backs use only earlier completed dates. Rolling histories reset each season; Elo carries with preseason regression. Scaler and weights were trained on 11,976 audited 2015–16 through 2024–25 games. No markets or retrospective player-availability features.

| Evaluation | Model | Correct / games | Accuracy | Brier | Log loss |
|---|---|---:|---:|---:|---:|
| Chronological development | Selected baseline | 5,414 / 8,288 | 65.32% | .217395 | .624300 |
| Chronological development | Fixed Elo | 5,325 / 8,288 | 64.25% | .220687 | .631220 |
| Reserved 2025–26 | Frozen selected baseline | 851 / 1,230 | 69.19% | .205543 | .598606 |
| Reserved 2025–26 | Fixed Elo | 834 / 1,230 | 67.80% | .209748 | .608214 |
| Reserved 2025–26 | Training home frequency | 682 / 1,230 | 55.45% | .247154 | .687447 |

The frozen artifact was committed before 2025–26 data retrieval. Frozen at 2026-10-06T19:07:04.589214+00:00; evaluated at 2026-10-06T19:07:53.130259+00:00. Freeze commit: `0e8a7399bafaa861b6bbbed71a7f53f1d2453063`. Bundle SHA256: `c57d804ab9062542e9e456a9585327bbb677732e5ad55b0186f91ddbdf5e079f`. The evaluation used earlier completed 2025–26 games to update team state, while keeping weights/scaler fixed. All 1,230 eligible regular-season games were included; four exhibition entries, four unfinished entries and the Cup championship were excluded. No alternate candidate was selected from this season.

All seven release-gate checks passed: minimum 1,000 games, at least 99% coverage, at least 60% accuracy, and better Brier/log loss than both controls. This is a historical reserved-season result, not a prospective live record or promised hit rate. December was 58.88% and January 60.09%; March/April were much stronger. Probability calibration is still imperfect, including only 84% wins among the 25 home forecasts in the 90–100% bin. Report the full season and monthly results together.

## Completed development comparisons

The advanced-stat tournament tested baseline plus 11 challengers: windows, defensive/shooting factors, opponent adjustment, fatigue and recency. None passed preregistered replacement rules. The lowest-Brier challenger, advanced20, lost 21 correct picks (65.07%) with only .000093 Brier improvement and failed recent-season stability. Its descriptive intervals crossed zero.

The final comparison tested nine entries: baseline, two shallow gradient-boosting trees, two equal blends, baseline Platt/temperature calibration, and calibrated trees. None qualified. Temperature calibration retained accuracy but its .000094 Brier improvement was too small and failed recent-season stability. Calibration used only earlier-season OOF predictions. The baseline remained selected at 65.32%.

Selection rules in both tournaments required Brier gain >=.0005, lower log loss, preserved accuracy, better Brier in at least five of seven seasons and both latest seasons. All candidate predictions/season scores and decisions are retained. Development comparisons reused development data and were not independently validated; only the frozen selected candidate and preregistered controls were scored for the reserved-season release decision.

## Sources and safeguards

Source: ESPN schedule/team boxes distributed by SportsDataverse, archived with hashes. Development excludes All-Star/Rising Stars, Cup championship, unfinished entries, two missing initial-training box pairs and one inconsistent 2024–25 shooting box. One 2020 archived date was corrected against an NBA official scorer's report. Neutral 2020 bubble games have no home advantage. Full protocols/source audit remain in the repository.

All 22 safety tests passed locally and in GitHub Actions. They cover date-batched feature updates, outcome isolation, season reset, order invariance, neutral context, prior-season model/scaler/calibration fitting, bounded candidates, selection checks, and refusal to retrieve holdout data without a frozen artifact. Repeat evaluation checks hashes and preserves the first result without rescoring.

## Prospective collection enabled

NBA UI is published on main. `nba_prospective.yml` is registered on main and checks hourly at minute 17, explicitly checking out and writing `nba-v1-research`. Both initial production collection runs succeeded on October 6, 2026. `data/nba/prospective/dashboard.json` is the UI feed; `predictions.jsonl` and `results.jsonl` are separate append-only records created when eligible events exist. Seven prospective safety tests pass. No regular-season game was within the 36-hour forecast window at activation, so the official record is 0–0 with no predictions. Preseason remains excluded.

The existing V1 bundle and first reserved-season result remain unchanged. There is no deployment refit. Earlier completed 2025–26 games and current regular-season games advance date-batched team state only. Missing validated current team boxes block new predictions until complete history is available. Finals for saved forecasts can still settle; missed games are never backfilled. Read `prospective/PROTOCOL.md` for timing, source receipts and settlement rules.

Next: collect opening-day pregame forecasts, verify result settlement, and track live accuracy/Brier/log loss without tuning. Player availability needs archived pregame information or a separate prospective experiment. Any future refit must be a separately identified artifact and must preserve this historical evaluation.

Authoritative outputs: `baseline_summary.json`, `tournament_summary.json`, `final_comparison_summary.json`, `excluded_season_evaluation.json`, and their matched prediction/season files. Frozen identity: `model/nba/v1/manifest.json`.
