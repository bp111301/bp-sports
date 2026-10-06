# Confirmed-goalie experiment handoff — 2026-10-06

Initial run: https://github.com/bp111301/bp-sports/actions/runs/37508365099
(success). Nine new paired-experiment safety tests and nine capture tests pass
locally and in CI. The new bundle froze at 18:05:31 UTC on 9,781 completed games
from 2018–19 through 2025–26. No alternative 2025–26 evaluation was performed.

The watchlist reference bundle is unchanged. The new goalie model uses the
original 18 team features plus one fixed weighted goalie-quality difference.
Historical fitting infers starters from earlier team starts, never realized
current starters. The confirmed/inferred comparisons share the same learned
19-feature weights; the team control uses the existing frozen reference.

Initial paired ledger is empty because no game was within the last-hour
prediction window. This is correct; do not backfill or widen the protocol to
create immediate results. Each later eligible game gets all three predictions
atomically at one timestamp, only with two eligible pregame confirmations.

The default-branch launcher is registered and triggers after each successful
`NHL pregame goalie capture` workflow, plus manual dispatch. It explicitly
checks out and writes only the research branch. The already-frozen bundle
retains historical feature inputs so subsequent runs load rather than refit or
re-download training history. The source capture runs every 30 minutes subject
to GitHub scheduling delay. Games without confirmations may be missed.

Read `data/nhl/goalie_experiment/summary.json` for coverage and descriptive paired
metrics. The first formal review is after 500 valid settled pairs. No automatic
promotion, early winner selection, UI activation or change to existing NHL or
CFB predictions. See PROTOCOL.md and the frozen spec before continuing.
