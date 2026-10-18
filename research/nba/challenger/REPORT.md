# NBA availability challenger: completed development comparison

**October 18, 2026: minutes-weighted availability shortlisted and frozen for separate prospective shadow testing. NBA V1 remains the public model.**

The original blocked checkpoint was resumed after official report access returned. The unchanged source gate passed, the original V1 development predictions replayed across 8,288 games (maximum error 1.11e-16), and all three locked availability variants were evaluated. No variant or threshold was added after viewing results.

## Same-game development comparison

The following results cover the identical 3,689 eligible regular-season games in seasons ending 2023–25. Unknown contexts retain the exact V1 probability. Lower Brier and log loss are better.

| Variant | Correct | Accuracy | Brier | Log loss | Shortlisted |
|---|---:|---:|---:|---:|---|
| v1_replay | 2,430/3,689 | 65.87% | 0.214343 | 0.617067 | Control |
| coverage_control | 2,408/3,689 | 65.28% | 0.214947 | 0.618281 | Control |
| status_counts | 2,435/3,689 | 66.01% | 0.213491 | 0.615067 | Yes |
| minutes_weighted | 2,451/3,689 | 66.44% | 0.211297 | 0.609931 | Yes |
| combined | 2,436/3,689 | 66.03% | 0.211816 | 0.611152 | Yes |

The strongest candidate is minutes_weighted: **21 additional correct picks (+0.57 percentage points)**, Brier improvement 0.003046 and log-loss improvement 0.007136. It beats the coverage-only control and passes all locked development checks. Its Brier/log-loss results improve in 2024 and 2025, while 2023 is slightly worse. Counts and the combined variant also pass, but have weaker pooled Brier scores; they are not additional live variants.

| Ending season | V1 accuracy | Minutes-weighted accuracy | V1 Brier | Minutes-weighted Brier |
|---|---:|---:|---:|---:|
| 2023 | 62.93% | 63.50% | 0.225964 | 0.226120 |
| 2024 | 66.67% | 67.24% | 0.209977 | 0.206020 |
| 2025 | 68.02% | 68.59% | 0.207083 | 0.201744 |

## Coverage and limits

| Ending season | Eligible games | Both teams known | Coverage |
|---|---:|---:|---:|
| 2021 | 1,080 | 992 | 91.85% |
| 2022 | 1,230 | 1,209 | 98.29% |
| 2023 | 1,230 | 1,208 | 98.21% |
| 2024 | 1,230 | 1,198 | 97.40% |
| 2025 | 1,229 | 1,217 | 99.02% |

All evaluation seasons exceed the locked 70% requirement. There are 66 fallback games in the full comparison. Of 35,853 listed impact-player entries, 33,555 matched a unique identity with earlier player history (93.59%). The player source audit reconciled 149,529 positive-minute player-game rows. All 20 frozen V1 team-source hashes and six recorded player-source hashes match. Compressed source receipts, contexts and paired predictions accompany the machine-readable comparison.

The minutes-weighted descriptive date-cluster bootstrap gives an accuracy-change interval of approximately **−0.44 to +1.61 percentage points**. Accuracy improvement is therefore uncertain. Brier-change interval: −0.005021 to −0.000971; log-loss-change interval: −0.011711 to −0.002298. These are exploratory development intervals, not an independent holdout or proof of future gain, and are not adjusted for comparing multiple variants.

The earlier development cohort is different from the reserved V1 2025–26 result of **851/1,230 (69.19%)**. That historical evaluation was not reopened or used for challenger selection. No 2026 injury or player input was used in the comparison or residual fit. No preseason games were tested. Reports are earlier snapshots rather than guaranteed final active lists, and prior minutes/points are a simple importance proxy.

## Frozen shadow follow-through

The final minutes-weighted residual fits 5,824 earlier OOF rows from 2021–25 with both reports known. Its coefficients and scaling are frozen in `model/nba/availability-shadow/frozen.json`. Its paired prospective protocol is `shadow/PROTOCOL.md`. It recomputes the frozen V1 control at the same pregame capture time, records both forecasts separately, and grades confirmed finals without altering public V1 snapshots.

Prior 2025–26 player/team records may be used only as operational forward state for future games; no 2026 outcomes are scored for this challenger or fitted into its coefficients. Missing/invalid reports, missing player state or low player-identity coverage produce an explicit exact-V1 fallback. Records are append-only. First live reports will be checked as the regular season begins.

No public model, CFB V1/Candidate B weights, NBA V1 weights, historical evaluation, saved pregame prediction or other-sport model was changed. This is readiness for prospective observation, not production promotion. See `README.md` for reproduction and `results/comparison.json` for every metric and fold parameter.
