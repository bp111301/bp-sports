# NBA availability challenger: source audit checkpoint

**Decision, October 18, 2026: comparison not completed; no model promoted.**

The implementation and source checks are saved, but the runtime blocked access to
the official NBA PDF host before the last evaluation season finished downloading.
The source-quality gate correctly stopped the experiment before candidate outcome
evaluation. There is no measured availability accuracy improvement to report.

NBA V1 remains the public model. Its reserved 2025–26 historical result remains
**851/1,230 (69.19%)**. That season was not downloaded, reopened or used to select
this challenger. No production workflow, public snapshot, grading record, frozen
weight or other-sport file was changed.

## Source coverage

Season labels are ending years. These are eligible V1 regular-season games,
not preseason or postseason. A game is both-known only when both teams explicitly
submitted a valid report before the locked cutoff.

| Season | Role | Eligible games | Both-known games | Both-known coverage |
|---|---|---:|---:|---:|
| 2020–21 | Earlier residual training | 1,080 | 985 | 91.20% |
| 2021–22 | Earlier residual training | 1,230 | 1,209 | 98.29% |
| 2022–23 | Development evaluation | 1,230 | 1,208 | 98.21% |
| 2023–24 | Development evaluation | 1,230 | 1,198 | 97.40% |
| 2024–25 | Development evaluation | 1,229 | 205 | 16.68% |

The locked rule requires at least 70% coverage in **every** evaluation season.
The final season fails because retrieval is incomplete; this does not establish
that the underlying official archive lacks those reports. The preceding seasons
were not evaluated on their own after encountering this failure.

The offline audit records 1,633 requested report selections: 959 parsed receipts,
48 unavailable receipts and 626 not retrieved. Those document counts include the
locked earlier-hour fallbacks and may cover more than one game's context. None
of the parsed receipts had a parser issue. A parsed document can still be rejected
by its timestamps or omit a particular game's team. Missing, malformed or not-yet-
submitted contexts cannot become healthy teams or adjusted predictions.

## Work completed

* Locked the protocol in commit `883279e20206a8390fffea2ee87791b9c651f446` before
  evaluating any challenger.
* Verified all 20 original team-source hashes and six recorded player-source hashes.
* Reconciled 149,529 positive-minute player-game rows with accepted V1 game, team,
  opponent and score identities. Only earlier appearances can define importance.
* Implemented physical-column PDF parsing for both historical layouts, including
  wrapped team labels, headerless page continuations and suffix-preserving names.
* Checked embedded publication and PDF creation timestamps, exact game date and
  matchup, local-time cutoffs including daylight-saving transition dates, and
  explicit unknown-report handling.
* Implemented the locked chronological offset comparison, coverage-only control,
  probability-quality metrics and development shortlist checks. These performance
  calculations have **not** run on the historical evaluation cohort.
* Passed 21 tests covering original V1 safety and new availability behavior,
  including exact V1 fallback for every candidate when reports are unknown.
* Saved compressed report receipts and selected contexts, source hashes and the
  machine-readable blocked decision. No fitted challenger or performance claim
  is included.

## Resume

When official PDF access is available, follow `README.md`. Re-fetch the missing
files and explicitly retry transient proxy/network-error receipts, retaining
their audit history. Rebuild the full source audit. The same locked 70% rule must
pass before the unchanged three candidate variants may be evaluated. Do not loosen
coverage, drop the last season or add/tune variants to force a result.

The immediate next step is completing report retrieval, then exact V1 replay and
the original locked comparison. A candidate that passes development checks would
still need separate prospective testing; it would not replace V1 automatically.
