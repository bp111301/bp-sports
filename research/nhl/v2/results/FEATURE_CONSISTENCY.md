# NHL Feature Consistency Audit

Read-only source diagnosis; excluded-season labels never train or select V2 candidates.
Team-game join coverage: 100.00%.
Missingness warnings: [].

| Feature | Development missing | Failed-season missing | Mean shift (SD) | PSI |
|---|---:|---:|---:|---:|
| elo_diff | 0.00% | 0.00% | -0.005127957503127869 | 0.19780551845958927 |
| home_field | 0.00% | 0.00% | — | — |
| win10_diff | 1.54% | 1.52% | -0.005921783382202306 | 0.008395334934701904 |
| gd10_diff | 1.54% | 1.52% | 0.008204286862720324 | 0.025586195803211233 |
| gf10_diff | 1.54% | 1.52% | -0.0006303711716012049 | 0.01225914577318476 |
| ga10_diff | 1.54% | 1.52% | -0.013331887300772722 | 0.011287531797778418 |
| rest_diff | 1.54% | 1.52% | -0.019524682727422533 | 0.03825041234767032 |
| home_b2b | 0.00% | 0.00% | 0.08476015120334021 | — |
| away_b2b | 0.00% | 0.00% | -0.006107923249069065 | — |
| games_played_diff | 0.00% | 0.00% | -0.01170702778251512 | 0.10427214651910521 |
| shots_for_20_diff | 4.13% | 4.04% | 0.0051782816846246615 | 0.018813812764761666 |
| shots_against_20_diff | 4.13% | 4.04% | 0.0054585763914591365 | 0.0033746260282098237 |
| shot_diff_20_diff | 4.13% | 4.04% | 2.9693592616303135e-05 | 0.030946813184652384 |
| shoot_pct_20_diff | 4.13% | 4.04% | -0.014962356694583881 | 0.007293719225164632 |
| save_pct_20_diff | 4.13% | 4.04% | 0.0030291550839270367 | 0.020539673460776404 |
| faceoff_pct_20_diff | 4.13% | 4.04% | 0.018209909802404205 | 0.010822917404729446 |
| pp_rate_20_diff | 4.15% | 4.12% | -0.010044534990559208 | 0.012018871518919038 |
| pk_rate_20_diff | 4.13% | 4.04% | -0.02741437028605132 | 0.012376634690999349 |

PSI and mean shifts are descriptive; no thresholds are tuned against 2025-26. Identical joins alone do not prove features are equally predictive.
