# CFB V2 Candidate B — Prospective Shadow

Candidate B is frozen for prospective shadow testing. It does not alter the public CFB V1 feed.

Architecture:
- 65% frozen CFB V1 winner probability
- 35% context score-margin probability
- Ridge margin model, alpha 100
- V1 leakage-safe context feature set
- margin probability from normal CDF using 2015–2025 training residual standard deviation
- market data excluded

Historical 2018–2025 chronological OOF:
- 5,733 games
- 72.93% accuracy
- 0.176851 Brier
- 0.526069 log loss

Historical 2021–2025:
- 71.80% accuracy
- approximately 0.182368 Brier

The completed 2026 games already inspected during Candidate A research are not validation evidence for Candidate B. Only Candidate B snapshots created before kickoff after this freeze count as prospective evidence.

Any architecture, feature, alpha, blend-weight, or decision-rule change creates a new candidate and restarts the prospective ledger.
