# CFB Portal Feature Timing Audit

Status: **REJECTED AS CURRENTLY CONSTRUCTED FOR LEAKAGE-SAFE V2 SELECTION**

The transfer/roster-churn experiment produced promising historical scores, but the upstream `cfb_team_portal` release is reconstructed from season-S ESPN rosters and season S-1 rosters. The upstream builder explicitly notes that the season-S roster does not exist before the season's first kickoff. The published season roster is therefore not a preserved preseason snapshot.

That means the experiment is useful as a hypothesis generator, not as valid evidence for promoting portal features into CFB V2. The attractive result (73.07% accuracy / 0.176695 Brier for `portal_prior`) must not be treated as leakage-safe performance.

## What would make this feature family admissible

A future portal layer must be rebuilt from information timestamped before the prediction:
- transfer records with reported/commit dates before kickoff, or
- archived preseason roster snapshots, or
- per-game roster snapshots restricted to information demonstrably available before that game.

Until then:
1. Frozen CFB V1 is unchanged.
2. The margin challenger remains the leading leakage-safe V2 architecture.
3. Portal features are quarantined from model selection and production.
4. The portal experiment may guide future data engineering, but its score cannot justify promotion.
