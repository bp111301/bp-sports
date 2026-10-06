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

## Calibration, freeze and excluded-season evaluation completed

Chronological calibration retained raw probabilities: on the same 3,936
calibratable development games, raw Brier/log loss were .233072/.657892;
temperature .233089/.657957; sigmoid .233077/.657928. Neither calibrated method
passed the recorded promotion rule. The full development leader remains 61.34%.

The exact specification was committed at 9fc848d before the evaluation workflow
ran. Frozen weights were trained on 8,469 games from 2018–19 through 2024–25
before downloading the excluded season. Bundle/config/feature-code checksums
and dependency versions are recorded in model/nhl/v1/bundle_manifest.json.

Run: https://github.com/bp111301/bp-sports/actions/runs/37493361746 (success).
On 1,312 games in 2025–26, frozen V1 accuracy is 53.43%, Brier .249421, log loss
.692045. Fixed baseline accuracy is also 53.43%, Brier .248543, log loss .690427.
The release gate failed. V1 remains research-only and is not eligible for
prospective shadow under this specification. No live NHL or UI deployment.

Saved prediction integrity checks reproduce every metric. Baseline probabilities
and outcomes match the earlier saved baseline run for all 1,312 games (maximum
probability difference below 1e-12). Frozen checksums match. All 22 safety tests
pass locally and in CI. This confirms the poor excluded-season baseline result
was already present; it does not establish the underlying cause of deterioration.

## Next development step

The source audit and bounded V2 comparisons are complete. See
`research/nhl/v2/HANDOFF.md` for results and the separate locked experimental
pregame watchlist. No alternative passed the development promotion gate. Do not modify V1 or select another
candidate using 2025–26. A future version needs a newly documented development
boundary and genuinely later/prospective validation; this failed season cannot
serve repeatedly as independent confirmation. CFB V1 and Candidate B remain
frozen and untouched.

2025–26 was excluded from candidate selection, but earlier baseline-only reports
already viewed it. Do not describe it as a pristine unseen holdout.
