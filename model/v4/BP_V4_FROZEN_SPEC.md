# B.P. Sports NFL V4 — Frozen Candidate Specification

Freeze date: 2026-10-05
Status: Frozen for prospective 2026 comparison; no algorithm changes based on Week 5 results.

## Core winner model
- V3 efficiency foundation: opponent-adjusted EPA, success/form, Elo/team strength, rest/context.
- QB-aware ensemble: V3 + leakage-safe QB change/continuity + prior QB quality.
- Historical reused-sample winner accuracy (2018–2025): 65.02% (1,279 / 1,967) for the selected QB-aware candidate.
- This historical figure is exploratory, not a pristine estimate of future accuracy.

## Confidence/risk layers
1. Explosive plays: ACTIVE confidence modifier. Extreme last-5 net explosive matchup can modestly raise confidence on agreement and reduce confidence on disagreement; it never flips the winner by itself.
2. Turnovers: TRACKED risk modifier/flag. Recent turnover mismatch is useful primarily as a warning when it contradicts the core model. Keep its effect conservative.
3. Early-down efficiency: TRACKED risk flag. Extreme last-5 early-down success mismatch can reduce confidence when it contradicts the core model; do not let it flip the winner.

## Rejected as core coefficients
- Raw pressure/sack/QB-hit proxy
- Third-down conversion matchup
- Red-zone TD efficiency
- Special teams proxy
- Simple explosive-play regression coefficients
- Simple interaction expansion

These can remain visible in matchup explanations even when they do not receive core model weight.

## Final feature-hunt validation
On the comparable 2019–2024 development sample (1,480 games), the QB core was 65.41% with 0.22332 Brier / 0.63752 log loss. The explosive confidence layer improved probability quality to 0.22262 / 0.63562 without changing picks. The combined explosive + turnover + early-down risk version was 0.22266 / 0.63571.

On the separately reported 2025 diagnostic (252 games), the QB core was 63.10% with 0.22354 Brier / 0.63542 log loss. Explosive + turnover + early-down risk improved probability quality to 0.22173 / 0.63043 without changing picks.

Because the combined version was marginally worse than explosive-only on development but stronger in 2025, turnover and early-down are retained as conservative risk flags rather than justification for further historical tuning.

## Prospective rule
Freeze now. Generate V3 and V4 predictions before kickoff, timestamp them, and grade both after games. Do not alter the algorithm because of a single week's results. Market odds remain outside the prediction engine and are evaluated only afterward as a separate value/challenger layer.
