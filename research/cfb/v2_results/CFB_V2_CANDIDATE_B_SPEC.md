# CFB V2 Candidate B — Prospective Shadow Spec

Status: **FROZEN FOR PROSPECTIVE SHADOW TESTING**

Candidate B is selected from 2018–2025 chronological OOF research. The already-opened 2026 completed games are not validation evidence for Candidate B and will not be used to tune it.

## Architecture

Candidate B is deliberately simpler than rejected Candidate A.

- Base signal: frozen market-free CFB V1 probability.
- Independent signal: Ridge score-margin model using the leakage-safe V1 context feature set.
- Ridge alpha: 100.
- Margin probability conversion: normal CDF using residual standard deviation learned only from the fixed 2015–2025 training sample.
- Final probability: 65% V1 + 35% context score-margin probability.
- Winner: side with final probability >= 0.50.
- No travel addition.
- No nonlinear tree layer.
- No market input.

## Historical development evidence

2018–2025 chronological OOF:
- 5,733 games
- 72.93% accuracy
- 0.176851 Brier
- 0.526069 log loss
- improved Brier versus V1 in 6 of 8 seasons

2021–2025:
- 3,755 games
- 71.80% accuracy
- approximately 0.182368 Brier

Frozen V1 on the same 2021–2025 games:
- 71.53% accuracy
- 0.183011 Brier

## Promotion rule

Candidate B does not replace V1 based on these historical results. It runs in shadow mode only.

Prospective evidence begins with Candidate B snapshots created after this spec is frozen. Candidate B must demonstrate a meaningful advantage over V1 on genuinely unseen games, including winner accuracy, Brier score, log loss, calibration, and confidence buckets, before promotion can be considered.

Any change to alpha, blend weight, feature set, margin conversion, or winner rule creates a new candidate and restarts prospective evidence.
