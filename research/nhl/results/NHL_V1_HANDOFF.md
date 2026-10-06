# NHL V1 research handoff — 2026-10-06

Research branch: `nhl-v1-research`. CFB V1 and Candidate B remain frozen and were not modified.

## Current development leader

`advanced_all_w20`: baseline features plus eight shifted 20-game team-stat differences. Development evaluation uses 2021–22 through 2024–25, each season trained only on earlier seasons. Across 5,248 games: 61.34% accuracy, Brier 0.231620, log loss 0.655148. The 60.63% development baseline has Brier 0.2339 and log loss 0.6600. These are reused development results, not prospective performance.

## Goalie decision

The initial inferred-starter goalie layer worsened aggregate accuracy and probability scores. A bounded follow-up used shot-weighted player histories, a fixed .905 save percentage / 300-shot prior, prior-start mixtures, and workload/rest. Outcomes update only after all games on a date receive features; player history carries across trades/seasons with a 365-day cutoff. Four synthetic safety tests passed locally and in CI. Three additional local tests passed for season resets with player-history retention, player-history expiration, and quality following trades only after a prior new-team start; seven local tests pass in total.

Run: https://github.com/bp111301/bp-sports/actions/runs/37487405792 (success).

The weighted probable-starter estimate improved Brier to 0.231465 and log loss to 0.654763, with Brier improvement in 3/4 seasons, but reduced winner accuracy to 61.03%. No goalie candidate met the prespecified promotion rule (improve both probability scores, preserve accuracy, improve Brier in at least 3/4 seasons). Keep the team-stat leader; retain weighted goalie estimates as research only. Realized historical starters were never used as pregame inputs.

## Additional factor tournament completed

Run: https://github.com/bp111301/bp-sports/actions/runs/37490956703 (success).
All six candidates were evaluated on the same 5,248 development games. Opponent
adjustment reached 61.49%, travel/congestion 61.51%, and their combination 61.59%,
but each worsened aggregate Brier/log loss and improved Brier in only 1/4 seasons.
No candidate meets the promotion rule. Retain advanced_all_w20 at 61.34%.

The exploratory expected-goals block reached 61.34%, Brier .231586, log loss
.655027, with Brier improvement in only 2/4 seasons. The all-factor exploratory
combination reached 61.19%, .231832, .655590. Historical MoneyPuck aliases
L.A/N.J/S.J/T.B were normalized to LAK/NJD/SJS/TBL; all 16,938 team-games match
on NHL game ID, team, and date. No missing source teams or date offsets remain.

MoneyPuck's current documentation describes its 2026–27 expected-goals model as
trained on 2023–24 through 2025–26. The exact model vintage attached to each
historical team-game CSV row is unverified. These xG results are exploratory,
not evidence from a leakage-safe historical xG model. Source:
https://moneypuck.com/about.htm . A clean future shot-quality experiment requires
archived point-in-time scores or an independently chronological shot model.

Eight factor tests and seven goalie tests pass locally. All six sets of saved
OOF predictions reproduce reported accuracy, Brier and log loss; 31,488 rows,
unique by candidate/game ID, only development seasons. CFB remains unchanged.

## Next development step

Persist candidate-specific chronological out-of-fold predictions and review calibration, confidence buckets, and season stability for the retained team-stat leader. Lock the exact candidate and calibration procedure before a one-time 2025–26 evaluation. Do not tune against that evaluation. No NHL production model or deployment freeze has yet been declared.

2025–26 is excluded from both goalie selection and team-stat selection; the weighted script explicitly truncates game inputs at 2024–25. Earlier baseline-only reports already include 2025–26, so describe it as excluded from candidate selection rather than claiming every historical result is unseen.
