# CFB V2 Transfer / Roster-Churn Experiment

Season-level roster-diff features are tested as preseason context. 2026 is excluded. These features cannot be promoted until their historical point-in-time semantics pass a separate timing audit.

| Candidate | Accuracy | Brier | Δ Brier | Recent Brier | Weeks 1-3 Brier |
|---|---:|---:|---:|---:|---:|
| portal_prior | 73.07% | 0.176695 | -0.000643 | 0.179448 | 0.161902 |
| portal_context | 72.82% | 0.176879 | -0.000459 | 0.179668 | 0.163833 |
| portal_both | 73.00% | 0.177040 | -0.000298 | 0.179701 | 0.161242 |
| v1 | 72.74% | 0.177338 | +0.000000 | 0.180105 | 0.165262 |

Feature coverage: roster_n 100.0%, transfers_in_n 100.0%, transfers_out_n 100.0%, portal_share 100.0%, transfer_talent_in 100.0%, transfer_talent_out 100.0%, net_transfer_talent 100.0%.
