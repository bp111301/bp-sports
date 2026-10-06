# CFB V1 Baseline Results

Completed FBS-vs-FBS games loaded: 8,186
Walk-forward test begins: 2018

| Candidate | Accuracy | Brier | Log loss | Games |
|---|---:|---:|---:|---:|
| elo_only | 72.34% | 0.1823 | 0.5404 | 6,004 |
| efficiency | 72.53% | 0.1799 | 0.5347 | 6,004 |
| cfb_context | 72.87% | 0.1770 | 0.5272 | 6,004 |

Current baseline leader by Brier: **cfb_context**.

Market spreads/totals and retrospective realized-QB fields are excluded from every candidate.
These are development backtests, not prospective accuracy claims.
