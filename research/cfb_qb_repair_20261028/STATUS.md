# Status of the QB join investigation

The preserved historical QB result reports zero coverage for every QB feature. The old loader converts the team-name field `pos_team` to numeric and then removes missing values, instead of using numeric `pos_team_id`. The original claim that this empty experiment meaningfully tested QB information is withdrawn; the original result and code are preserved for provenance.

A subsequent local count-based investigation reported92.1% both-team prior-QB coverage and no recipe passing its registered joint gate. Its final code and prediction artifacts were not committed before the local workspace was cleared. Treat that run as preliminary, not a reproduced or deployable model. Rebuild it from PROTOCOL.md and verify source identities, temporal limits, nonempty coverage, all predictions and complete gate results before relying on it. Do not fabricate rows or a replacement historical evaluation from console summaries.

The separately saved confidence-projection package does not use QB features and does not depend on this unfinished investigation. Frozen CFB V1 and all saved forecasts remain unchanged.
