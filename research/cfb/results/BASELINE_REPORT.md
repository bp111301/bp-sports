# CFB V1 Baseline Results

Completed FBS-vs-FBS games loaded: 7,915
Walk-forward test begins: 2018

| Candidate | Accuracy | Brier | Log loss | Games |
|---|---:|---:|---:|---:|
| elo_only | 72.07% | 0.1833 | 0.5426 | 5,733 |
| efficiency | 72.30% | 0.1811 | 0.5374 | 5,733 |
| cfb_context | 72.67% | 0.1780 | 0.5294 | 5,733 |

Current baseline leader by Brier: **cfb_context**.

Market spreads/totals and retrospective realized-QB fields are excluded from every candidate.
These are development backtests, not prospective accuracy claims.
