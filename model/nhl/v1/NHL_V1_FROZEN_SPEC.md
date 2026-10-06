# NHL V1 frozen research specification — 2026-10-06

Candidate advanced_all_w20 is locked before its excluded-season evaluation.
This is a research freeze, not a production release or website deployment.
CFB V1 and Candidate B remain frozen and untouched.

Use the exact 18 feature names and settings in config.json: prior-game Elo,
10-game win/goal form, rest, back-to-back and games-played differences plus
shifted 20-game shots, shot differential, shooting/save percentage, faceoffs,
power-play and penalty-kill differences. Team statistics reset each season,
require three earlier games, and exclude the current game. The classifier is
training-median imputation with missing indicators, StandardScaler, and logistic
regression C=.5, max_iter=3000, lbfgs. Market prices are excluded. No goalie,
opponent-adjustment, travel or retrospective expected-goals layer is included.

Retain raw probabilities. Chronological temperature and sigmoid calibration
failed the preregistered probability-score/stability requirements. They were
fitted only on earlier OOF seasons; 2021–22 was calibration warm-up. Development
accuracy remains 61.34% across 5,248 games, Brier .231620, log loss .655148.

Train frozen weights on completed regular-season games from 2018–19 through
2024–25 only. Record source checksums, dependency versions, feature list and
bundle checksum. Do not refit weights on any 2025–26 results during evaluation.
Within 2025–26, rolling features may use already-completed earlier games, as
would be available when making each subsequent prediction.

Evaluate 2025–26 once after this specification is committed. This season is
excluded from candidate selection; earlier baseline-only reports already viewed
it, so it is not a pristine unseen holdout. Compare the frozen leader and fixed
baseline on identical games. A prospective shadow candidate requires both better
Brier and log loss without reduced accuracy. Failure leaves it research-only;
do not adjust features, calibration, or thresholds in response to this season.

Confidence buckets remain descriptive, not guaranteed win rates. Small high-
confidence samples have wide uncertainty. No production bundle activation,
live predictions or UI changes are authorized by this research workflow.
